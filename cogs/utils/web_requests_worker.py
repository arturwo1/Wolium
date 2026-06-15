from __future__ import annotations
from json import loads, dumps
from asyncio import Lock, Semaphore, create_task, TimeoutError, sleep
from time import time
from decimal import Decimal
from datetime import datetime, timezone
from traceback import format_exception
from nextcord.ext import commands, tasks
from nextcord import Embed, Colour, CategoryChannel, Guild, VoiceChannel
from Utils.calculate_LvL import calculate_LvL
from asyncpg import ConnectionDoesNotExistError, InterfaceError, PostgresConnectionError
from math import ceil

QUEUE_TABLE = "public.web_requests"

POLL_SECONDS = 0.8

MAX_CONCURRENCY = 8
BATCH_PER_TICK = 12

CACHE_TTL_SECONDS = 30
ROW_TTL_AFTER_DONE_SECONDS = 60

MIN_BUCKET_MS = 1_000
MAX_BUCKET_MS = 30 * 86400_000
MIN_LIMIT = 80
MAX_LIMIT = 800

metrics = {
  "bank_balance": "SELECT user_id, bank_balance AS val FROM user_data",
  "balance": "SELECT user_id, balance AS val FROM user_data",
  "upgrade": "SELECT user_id, upgrade AS val FROM user_data",
  "total_xp": "SELECT user_id, xp AS val FROM user_data",
  "level": "SELECT user_id, xp AS val FROM user_data",
  "experience": "SELECT user_id, xp AS val FROM user_data",
  "total_balance": "SELECT user_id, (bank_balance + balance) AS val FROM user_data",
  "message_count": "SELECT user_id, COUNT(*)::bigint AS val FROM messages GROUP BY user_id",
  "voice_time": "SELECT user_id, COALESCE(SUM(EXTRACT(epoch FROM time_spent))::bigint, 0) AS val FROM voice GROUP BY user_id",
  "streak_votes": "SELECT user_id, streak AS val FROM topgg",
  "votes": "SELECT user_id, votes AS val FROM topgg",
  "commands": "SELECT user_id, COUNT(*)::bigint AS val FROM user_commands GROUP BY user_id",
  "activity_time": """
    SELECT user_id,
    COALESCE(SUM(GREATEST(0, EXTRACT(epoch FROM (COALESCE(ended_at, CURRENT_TIMESTAMP) - started_at))))::bigint, 0) AS val
    FROM (
      SELECT user_id, started_at, ended_at,
      row_number() OVER (
        PARTITION BY def_id, user_id, (EXTRACT(epoch FROM started_at)::bigint / 60)
        ORDER BY started_at ASC, id ASC
      ) AS rn
      FROM activity_segments
    ) deduped
    WHERE rn = 1
    GROUP BY user_id
  """
}

BOT_KINDS = {
  "user_profile_stats",
  "guild_profile_stats",
  "user_messages_series",
  "user_voice_series",
  "user_commands_series",
  "guild_messages_series",
  "guild_voice_series",
  "user_guilds",
  "leaderboard"
}

class TTLCache:
  def __init__(self, ttl_seconds: int):
    self.ttl = ttl_seconds
    self._data = {}
    self._lock = Lock()

  async def get(self, key):
    now = time()
    async with self._lock:
      item = self._data.get(key)
      if not item:
        return None
      exp, val = item
      if exp <= now:
        self._data.pop(key, None)
        return None
      return val

  async def set(self, key, value):
    now = time()
    async with self._lock:
      self._data[key] = (now + self.ttl, value)

  async def cleanup(self):
    now = time()
    async with self._lock:
      dead = [k for k, (exp, _) in self._data.items() if exp <= now]
      for k in dead:
        self._data.pop(k, None)

class WebRequestsWorker(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.sem = Semaphore(MAX_CONCURRENCY)
    self.cache = TTLCache(CACHE_TTL_SECONDS)
    self._started = False
    self._tasks: set = set()

    if not self.loop.is_running():
      self.loop.start()
    if not self.cache_gc.is_running():
      self.cache_gc.start()

  def cog_unload(self):
    if self.loop.is_running():
      self.loop.cancel()
    if self.cache_gc.is_running():
      self.cache_gc.cancel()
    for t in list(self._tasks):
      t.cancel()

  def _parse_payload(self, raw):
    if raw is None:
      return {}
    if isinstance(raw, dict):
      return raw
    if isinstance(raw, str):
      s = raw.strip()
      if not s:
        return {}
      try:
        return loads(s)
      except:
        return {}
    return {}

  def _convert_decimals(self, obj):
    if isinstance(obj, dict):
      return {k: self._convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
      return [self._convert_decimals(x) for x in obj]
    if isinstance(obj, Decimal):
      return float(obj)
    return obj

  def _cache_key(self, kind: str, discord_id: int, payload: dict):
    payload_s = dumps(payload or {}, ensure_ascii=False, sort_keys=True)
    return f"{kind}:{discord_id}:{payload_s}"

  def _clamp_int(self, v, lo, hi, default):
    try:
      x = int(v)
    except:
      x = int(default)
    if x < lo:
      return lo
    if x > hi:
      return hi
    return x

  def _series_params(self, payload: dict):
    frm_ms = self._clamp_int(payload.get("from", 0), 0, 10**18, 0)
    to_ms = self._clamp_int(payload.get("to", 0), 0, 10**18, 0)
    if to_ms <= frm_ms:
      to_ms = frm_ms + 3600_000

    bucket_ms = self._clamp_int(payload.get("bucket_ms", 60_000), MIN_BUCKET_MS, MAX_BUCKET_MS, 60_000)
    limit = self._clamp_int(payload.get("limit", 240), MIN_LIMIT, MAX_LIMIT, 240)

    range_ms = to_ms - frm_ms
    max_points = limit
    min_bucket_needed = max(MIN_BUCKET_MS, range_ms // max_points)
    if bucket_ms < min_bucket_needed:
      bucket_ms = min(min_bucket_needed, MAX_BUCKET_MS)

    guild_id_raw = payload.get("guild_id")
    channel_id_raw = payload.get("channel_id")
    context_raw = payload.get("context") or payload.get("command_name") or payload.get("activity_name")

    guild_id = int(guild_id_raw) if guild_id_raw not in (None, "") else None
    channel_id = int(channel_id_raw) if channel_id_raw not in (None, "") else None
    context = str(context_raw).strip() if context_raw not in (None, "") else None

    return frm_ms, to_ms, bucket_ms, limit, guild_id, channel_id, context

  def _parse_message_id(self, url: str | None):
    if not url or not isinstance(url, str):
      return None
    try:
      part = url.rstrip("/").split("/")[-1]
      if part.isdigit():
        return part
    except:
      pass
    return None

  def _resolve_guild_channel_names(self, guild_id_raw, channel_id_raw):
    gid = None
    cid = None

    try:
      if guild_id_raw not in (None, "", "0", 0):
        gid = int(guild_id_raw)
    except:
      gid = None

    try:
      if channel_id_raw not in (None, "", "0", 0):
        cid = int(channel_id_raw)
    except:
      cid = None

    if not gid:
      return ("DM", "")

    g = self.bot.get_guild(gid)
    guild_name = g.name if g else f"Server {gid}"

    ch_name = None
    if cid:
      ch = None
      if g:
        ch = g.get_channel(cid)
      if not ch:
        ch = self.bot.get_channel(cid)
      if ch:
        ch_name = getattr(ch, "name", None)

    channel_name = f"#{ch_name}" if ch_name else (f"channel {cid}" if cid else "channel")
    return (guild_name, channel_name)
  
  def _safe_int(self, v, default=None):
    try:
      return int(v)
    except:
      return default

  def _clean_text(self, v, max_len=120):
    if v in (None, ""):
      return None
    s = str(v).strip()
    if not s:
      return None
    return s[:max_len]

  def _contains_ci(self, haystack, needle):
    if not needle:
      return True
    if not haystack:
      return False
    return needle.casefold() in str(haystack).casefold()

  def _duration_range_seconds(self, payload: dict):
    min_sec = self._safe_int(payload.get("min_duration_seconds"), None)
    max_sec = self._safe_int(payload.get("max_duration_seconds"), None)

    if min_sec is None and payload.get("min_duration_ms") not in (None, ""):
      min_sec = max(0, self._safe_int(payload.get("min_duration_ms"), 0) // 1000)

    if max_sec is None and payload.get("max_duration_ms") not in (None, ""):
      max_sec = max(0, self._safe_int(payload.get("max_duration_ms"), 0) // 1000)

    if min_sec is not None and min_sec < 0:
      min_sec = 0
    if max_sec is not None and max_sec < 0:
      max_sec = 0

    if min_sec is not None and max_sec is not None and max_sec < min_sec:
      min_sec, max_sec = max_sec, min_sec

    return min_sec, max_sec

  def _voice_series_params(self, payload: dict):
    frm_ms, to_ms, bucket_ms, limit_n, guild_id, channel_id, _ = self._series_params(payload)
    min_sec, max_sec = self._duration_range_seconds(payload)

    return {
      "from_ms": frm_ms,
      "to_ms": to_ms,
      "bucket_ms": bucket_ms,
      "limit": limit_n,
      "guild_id": guild_id,
      "channel_id": channel_id,
      "guild_name": self._clean_text(payload.get("guild_name")),
      "channel_name": self._clean_text(payload.get("channel_name")),
      "role_id": payload.get("role_id", None),
      "min_duration_seconds": min_sec,
      "max_duration_seconds": max_sec
    }
  
  def resolve_user(self, user_id):
    user = self.bot.get_user(int(user_id))
    if not user:
      member = next((m for m in self.bot.get_all_members() if m.id == int(user_id)), None)
      user = member

    return {
      "display_name": getattr(user, "display_name", "Unknown User"),
      "avatar": str(user.display_avatar.url) if user and user.display_avatar else None
    }

  @tasks.loop(seconds=POLL_SECONDS)
  async def loop(self):
    if not self.bot.is_ready() or not getattr(self.bot, "db_pool", None):
      return

    if not self._started:
      self._started = True

    jobs = await self._claim_jobs(BATCH_PER_TICK)
    if not jobs:
      return

    for job in jobs:
      t = create_task(self._handle_job(job))
      self._tasks.add(t)
      t.add_done_callback(self._tasks.discard)

  @tasks.loop(seconds=5)
  async def cache_gc(self):
    await self.cache.cleanup()

  async def _claim_jobs(self, limit_n: int):
    try:
      async with self.bot.db_pool.acquire() as conn:
        rows = await conn.fetch(f"""
          with j as (
            select id
            from {QUEUE_TABLE}
            where status='pending'
            order by created_at
            for update skip locked
            limit $1
          )
          update {QUEUE_TABLE} w
          set status='processing',
              updated_at=now()
          from j
          where w.id = j.id
          returning w.id, w.user_id, w.kind, w.payload;
        """, int(limit_n))
        return rows

    except (
      ConnectionDoesNotExistError,
      InterfaceError,
      PostgresConnectionError,
      ConnectionResetError,
      OSError,
      TimeoutError,
    ):
      return []

  async def _get_discord_id(self, conn, auth_user_id):
    row = await conn.fetchrow("""
      select (raw_user_meta_data->>'sub')::bigint as discord_id
      from auth.users
      where id = $1
      limit 1;
    """, auth_user_id)
    return row["discord_id"] if row and row["discord_id"] else None

  async def _set_done(self, conn, req_id, result_obj, err=None):
    result_json = dumps(result_obj or {}, ensure_ascii=False)
    await conn.execute(f"""
      update {QUEUE_TABLE}
      set status=$1::text,
        result=$2::jsonb,
        error=$3,
        updated_at=now(),
        expires_at=now() + interval '{ROW_TTL_AFTER_DONE_SECONDS} seconds'
      where id=$4
    """, "error" if err else "done", result_json, err, req_id)

  async def _set_error(self, conn, req_id, msg: str):
    await conn.execute(f"""
      update {QUEUE_TABLE}
      set status='error',
        error=$2,
        updated_at=now(),
        expires_at=now() + interval '{ROW_TTL_AFTER_DONE_SECONDS} seconds'
      where id=$1
    """, req_id, (msg or "error")[:1000])

  async def _handle_job(self, job):
    retries = 0
    max_retries = 5

    while retries < max_retries:
      try:
        async with self.sem:
          async with self.bot.db_pool.acquire() as conn:
            try:
              auth_user_id = job["user_id"]
              discord_id = await self._get_discord_id(conn, auth_user_id)
              if discord_id is None:
                await self._set_error(conn, job["id"], "discord_id not found (auth.users.raw_user_meta_data.sub)")
                return

              kind = job["kind"]
              payload = self._parse_payload(job["payload"])

              ck = self._cache_key(kind, discord_id, payload)
              cached = await self.cache.get(ck)
              if cached is not None:
                await self._set_done(conn, job["id"], cached)
                return

              result, err = await self._process_kind(conn, kind, discord_id, payload, job)
              result = self._convert_decimals(result)

              await self.cache.set(ck, result)
              await self._set_done(conn, job["id"], result, err)
              return

            except (
              ConnectionDoesNotExistError,
              InterfaceError,
              PostgresConnectionError,
              ConnectionResetError,
              OSError,
              TimeoutError,
            ):
              raise

            except Exception as e:
              await self._log_error(e, {"job": dict(job) if job else None})
              try:
                await self._set_error(conn, job["id"], str(e))
              except Exception:
                pass
              return

      except (
        ConnectionDoesNotExistError,
        InterfaceError,
        PostgresConnectionError,
        ConnectionResetError,
        OSError,
        TimeoutError,
      ):
        retries += 1
        await sleep(5)

    try:
      async with self.bot.db_pool.acquire() as conn:
        await self._set_error(conn, job["id"], "db unavailable after retries")
    except Exception:
      pass

  async def _process_kind(self, conn, kind: str, discord_id: int, payload: dict, job: dict):
    if kind not in BOT_KINDS:
      return None, f"Kind is handled by Netlify Functions, not bot: {kind}"
    
    gd = self.bot.get_cog("GetData")
    ud = self.bot.get_cog("UpdateData")
    if not gd: return None, "Failed to get data."

    user_info = await gd.get_data(discord_id, ["banned", "auth_user_id", "badges"], "users", "user_id", None)

    if user_info.get("banned"):
      return None, "You are banned."
    
    current_auth_user_id = user_info.get("auth_user_id")
    new_auth_user_id = job["user_id"]

    if not current_auth_user_id:
      if not ud:
        return None, "Failed to update data."

      await ud.update_data(
        discord_id,
        {"auth_user_id": new_auth_user_id},
        "users",
        "user_id",
        None
      )

    elif current_auth_user_id != new_auth_user_id:
      return None, "You already logged in another account."

    if kind == "user_profile_stats":
      req = """
        with
          msg as (
            select count(*)::bigint as messages
            from messages
            where user_id = $1::bigint
          ),
          voice_ms as (
            select coalesce(sum((extract(epoch from time_spent) * 1000)::bigint), 0::bigint) as ms
            from voice
            where user_id = $1::bigint
          ),
          bal as (
            select
              coalesce(bank_balance, 0) as bank_balance,
              coalesce(balance, 0) as balance
            from user_data
            where user_id = $1::bigint
            limit 1
          ),
          
          acts_dedup as (
            select 
              a.started_at,
              a.ended_at,
              row_number() over (
                partition by d.name, (extract(epoch from a.started_at)::bigint / 60)
                order by a.started_at asc, a.id asc
              ) as rn
            from activity_segments a
            join activity_defs d on d.id = a.def_id
            where a.user_id = $1::bigint
          ),
          
          act_sec as (
            select coalesce(
              sum(greatest(0, extract(epoch from (coalesce(ended_at, CURRENT_TIMESTAMP) - started_at)))::bigint),
              0::bigint
            ) as sec
            from acts_dedup
            where rn = 1
          ),
          
          cmd as (
            select count(*)::bigint as user_commands
            from user_commands
            where user_id = $1::bigint
          )
        select
          (select messages from msg) as messages,

          (
            select
              case
                when (ms::bigint) >= 86400000 then
                  ((ms::bigint) / 86400000)::text || ' days ' ||
                  lpad((((ms::bigint) / 3600000) % 24)::text, 2, '0')
                else
                  lpad(((ms::bigint) / 3600000)::text, 2, '0')
              end
              || ':' || lpad((((ms::bigint) / 60000) % 60)::text, 2, '0')
              || ':' || lpad((((ms::bigint) / 1000) % 60)::text, 2, '0')
              || '.' || lpad(((ms::bigint) % 1000)::text, 3, '0')
            from voice_ms
          ) as voice_time,
                                
          (
            select
              case
                when (sec::bigint) >= 86400 then
                  ((sec::bigint) / 86400)::text || ' days ' ||
                  lpad((((sec::bigint) / 3600) % 24)::text, 2, '0')
                else
                  lpad(((sec::bigint) / 3600)::text, 2, '0')
              end
              || ':' || lpad((((sec::bigint) / 60) % 60)::text, 2, '0')
              || ':' || lpad(((sec::bigint) % 60)::text, 2, '0')
            from act_sec
          ) as activity_seconds,

          (select user_commands from cmd) as user_commands,

          coalesce((select bank_balance + balance from bal), 0) as total_balance,
          coalesce((select bank_balance from bal), 0) as bank_balance,
          coalesce((select balance from bal), 0) as balance;
        """
      user_id_raw = payload.get("user_id", None)
      user_id = None

      if user_id_raw:
        if str(user_id_raw).isdigit():
          user = await conn.fetchrow("""
            SELECT user_id
            FROM users
            WHERE user_id = $1
          """, int(user_id_raw))
          if user:
            user_id = int(user["user_id"])
        user = await conn.fetchrow("""
          SELECT user_id
          FROM users
          WHERE username ILIKE $1
          LIMIT 1
        """, str(user_id_raw))
        if user:
          user_id = int(user["user_id"])
          
      if user_id:
        user1_publicity = (await gd.get_data(discord_id, ["publicity"], "user_privacy", "user_id", None))["publicity"]
        if not user1_publicity:
          return None, "Make your profile public to view other users profiles."
        user2_publicity = (await gd.get_data(user_id, ["publicity"], "user_privacy", "user_id", None))["publicity"]
        if not user2_publicity:
          return None, "The user has a private profile."
        discord_id = user_id if user_id else discord_id

      user_data = await gd.get_data(discord_id, ["xp"], "user_data", "user_id", None)
      xp = user_data.get("xp") or 0

      u = self.bot.get_user(discord_id)
      username = u.name if u else f"Unknown username"
      display_name = u.display_name if u else "Unknown name"
      user_avatar = str(u.display_avatar.url)
      member = next((m for m in self.bot.get_all_members() if m.id == discord_id), None)

      mutual_guilds: list[Guild] = getattr(member, "mutual_guilds", [])
      mutual_guilds_row = {}
      for mutual_guild in mutual_guilds:
        mutual_guilds_row[mutual_guild.id] = {"name": mutual_guild.name, "message_channels": {}, "voice_channels": {}}

        message_channels = [ch for ch in mutual_guild.channels if not isinstance(ch, CategoryChannel)] + list(mutual_guild.threads)
        voice_channels = mutual_guild.voice_channels
        
        for channel in message_channels:
          if not all([getattr(channel.permissions_for(member), permission, False) for permission in ["read_message_history", "view_channel"]+(["connect"] if isinstance(channel, VoiceChannel) else [])]):
            continue
          mutual_guilds_row[mutual_guild.id]["message_channels"][channel.id] = {"name": channel.name, "type": channel.__class__.__name__}
        
        for channel in voice_channels:
          if not all([getattr(channel.permissions_for(member), permission, False) for permission in ["connect", "view_channel"]]):
            continue
          mutual_guilds_row[mutual_guild.id]["voice_channels"][channel.id] = {"name": channel.name, "type": channel.__class__.__name__}

      lvl, xp_need, xp_now = calculate_LvL(xp)

      row = await conn.fetchrow(req, user_id or discord_id)
      result = dict(row) if row else {}
      result["xp"] = xp
      result["lvl"] = lvl
      result["xp_need"] = xp_need
      result["xp_now"] = xp_now
      result["user_name"] = username
      result["display_name"] = display_name
      result["user_avatar"] = user_avatar
      result["badges"] = user_info["badges"]
      result["status"] = member and str(member.status) or None
      result["client_status"] = {
        "desktop": str(getattr(member, "desktop_status", "offline")) if member else "offline",
        "mobile": str(getattr(member, "mobile_status", "offline")) if member else "offline",
        "web": str(getattr(member, "web_status", "offline")) if member else "offline"
      }
      result["guilds"] = mutual_guilds_row
      return result, None

    if kind == "user_messages_series":
      frm_ms, to_ms, bucket_ms, limit_n, guild_id, channel_id, context = self._series_params(payload)

      rows = await conn.fetch("""
        with base as (
          select
            (extract(epoch from date_time) * 1000)::bigint as ts_ms,
            content,
            guild_id,
            channel_id,
            message_url,
            attachments
          from messages
          where user_id = $1::bigint
            and date_time >= to_timestamp($2::bigint / 1000.0)
            and date_time <= to_timestamp($3::bigint / 1000.0)
            and ($6::bigint is null or guild_id = $6::bigint)
            and ($7::bigint is null or channel_id = $7::bigint)
            and ($8::text is null or content ilike ('%' || $8::text || '%'))
        ),
        buck as (
          select
            ((ts_ms / $4::bigint) * $4::bigint) as bucket_start,
            count(*)::bigint as y,
            min(ts_ms) as min_ts
          from base
          group by 1
        ),
        sample as (
          select distinct on (((ts_ms / $4::bigint) * $4::bigint))
            ((ts_ms / $4::bigint) * $4::bigint) as bucket_start,
            ts_ms as sample_ts,
            content as sample_content,
            guild_id as sample_guild_id,
            channel_id as sample_channel_id,
            message_url as sample_url,
            attachments as sample_attachments
          from base
          order by ((ts_ms / $4::bigint) * $4::bigint), ts_ms asc
        )
        select
          (case when b.y = 1 then b.min_ts else (b.bucket_start + ($4::bigint / 2)) end)::bigint as ts,
          b.y::bigint as y,
          b.bucket_start::bigint as bucket_start,
          (b.bucket_start + $4::bigint)::bigint as bucket_end,
          s.sample_ts::bigint as sample_ts,
          s.sample_content,
          s.sample_url,
          s.sample_guild_id,
          s.sample_channel_id,
          s.sample_attachments
        from buck b
        left join sample s using (bucket_start)
        order by b.bucket_start asc
        limit $5;
      """, discord_id, frm_ms, to_ms, bucket_ms, limit_n, guild_id, channel_id, context)

      out = []
      for r in rows:
        d = dict(r)

        gid_raw = d.get("sample_guild_id")
        cid_raw = d.get("sample_channel_id")

        guild_name, channel_name = self._resolve_guild_channel_names(gid_raw, cid_raw)

        msg_url = d.get("sample_url") or None

        d["meta"] = {
          "url": msg_url,
          "guild_name": guild_name,
          "channel_name": channel_name
        }
        out.append(d)

      return out, None

    if kind == "user_voice_series":
      p = self._voice_series_params(payload)

      rows = await conn.fetch("""
        select
          (extract(epoch from enter_time) * 1000)::bigint as ts_ms,
          greatest(0, extract(epoch from (leave_time - enter_time)))::bigint as seconds,
          guild_id,
          after_channel_id as channel_id
        from voice
        where user_id = $1::bigint
          and enter_time >= to_timestamp($2::bigint / 1000.0)
          and enter_time <= to_timestamp($3::bigint / 1000.0)
          and ($4::bigint is null or guild_id = $4::bigint)
          and ($5::bigint is null or after_channel_id = $5::bigint)
          and (
            $6::bigint is null
            or greatest(0, extract(epoch from (leave_time - enter_time)))::bigint >= $6::bigint
          )
          and (
            $7::bigint is null
            or greatest(0, extract(epoch from (leave_time - enter_time)))::bigint <= $7::bigint
          )
        order by enter_time asc;
      """,
        discord_id,
        p["from_ms"],
        p["to_ms"],
        p["guild_id"],
        p["channel_id"],
        p["min_duration_seconds"],
        p["max_duration_seconds"]
      )

      buckets = {}

      for r in rows:
        d = dict(r)

        guild_name, channel_name = self._resolve_guild_channel_names(
          d.get("guild_id"),
          d.get("channel_id")
        )

        if not self._contains_ci(guild_name, p["guild_name"]):
          continue
        if not self._contains_ci(channel_name, p["channel_name"]):
          continue

        ts_ms = int(d["ts_ms"])
        seconds = int(d["seconds"])
        bucket_start = (ts_ms // p["bucket_ms"]) * p["bucket_ms"]

        item = buckets.get(bucket_start)
        if not item:
          buckets[bucket_start] = {
            "ts": bucket_start + (p["bucket_ms"] // 2),
            "y": seconds,
            "bucket_start": bucket_start,
            "bucket_end": bucket_start + p["bucket_ms"],
            "meta": {
              "guild_id": d.get("guild_id"),
              "channel_id": d.get("channel_id"),
              "guild_name": guild_name,
              "channel_name": channel_name
            }
          }
        else:
          item["y"] += seconds

      return [buckets[k] for k in sorted(buckets.keys())[:p["limit"]]], None

    if kind == "user_commands_series":
      frm_ms, to_ms, bucket_ms, limit_n, guild_id, channel_id, command_name = self._series_params(payload)

      rows = await conn.fetch("""
        with base as (
          select
            (extract(epoch from uc.timestamp) * 1000)::bigint as ts_ms,
            uc.guild_id,
            uc.channel_id,
            c.name as command_name,
            uc.args
          from user_commands uc
          left join commands c on c.id = uc.command_id
          where uc.user_id = $1::bigint
            and uc.timestamp >= to_timestamp($2::bigint / 1000.0)
            and uc.timestamp <= to_timestamp($3::bigint / 1000.0)
            and ($6::bigint is null or uc.guild_id = $6::bigint)
            and ($7::bigint is null or uc.channel_id = $7::bigint)
            and ($8::text is null or (
              c.name ilike ($8::text || '%')        -- префикс: "le" → leaders, language
              or c.name ilike ('%' || $8::text || '%')  -- подстрока: "le" → reload
              or (length($8::text) >= 3 and similarity(c.name, $8::text) > 0.3)  -- fuzzy только от 3+ символов
            ))
        ),
        buck as (
          select
            ((ts_ms / $4::bigint) * $4::bigint) as bucket_start,
            count(*)::bigint as y,
            min(ts_ms) as min_ts
          from base
          group by 1
        ),
        sample as (
          select distinct on (((ts_ms / $4::bigint) * $4::bigint))
            ((ts_ms / $4::bigint) * $4::bigint) as bucket_start,
            ts_ms as sample_ts,
            command_name as sample_command_name,
            args as sample_args,
            guild_id as sample_guild_id,
            channel_id as sample_channel_id
          from base
          order by ((ts_ms / $4::bigint) * $4::bigint), ts_ms asc
        )
        select
          (case when b.y = 1 then b.min_ts else (b.bucket_start + ($4::bigint / 2)) end)::bigint as ts,
          b.y::bigint as y,
          b.bucket_start::bigint as bucket_start,
          (b.bucket_start + $4::bigint)::bigint as bucket_end,
          s.sample_ts::bigint as sample_ts,
          s.sample_command_name,
          s.sample_args,
          s.sample_guild_id,
          s.sample_channel_id
        from buck b
        left join sample s using (bucket_start)
        order by b.bucket_start asc
        limit $5;
      """, discord_id, frm_ms, to_ms, bucket_ms, limit_n, guild_id, channel_id, command_name)

      out = []
      for r in rows:
        d = dict(r)

        gid_raw = d.get("sample_guild_id")
        cid_raw = d.get("sample_channel_id")

        guild_name, channel_name = self._resolve_guild_channel_names(gid_raw, cid_raw)

        d["meta"] = {
          "guild_name": guild_name,
          "channel_name": channel_name
        }

        out.append(d)
      return out, None

    if kind == "user_guilds":
      publicity = (await gd.get_data(discord_id, ["publicity"], "user_privacy", "user_id", None))["publicity"]
      if not publicity:
        return None, "Make your profile public to view leaderboard."
      
      member = next((m for m in self.bot.get_all_members() if m.id == discord_id), None)
      if not member:
        return None, "I can't find you. Make sure we share at least one server."
      
      mutual_guilds = getattr(member, "mutual_guilds", [])
      mutual_guilds_js = []
      for guild in mutual_guilds:
        mutual_guilds_js.append({
          "id": str(guild.id),
          "name": guild.name
        })
      return mutual_guilds_js, None
  
    if kind == "leaderboard":
      publicity = (await gd.get_data(discord_id, ["publicity"], "user_privacy", "user_id", None))["publicity"]
      if not publicity:
        return None, "Make your profile public to view leaderboard."
      
      metric = payload.get("metric", "total_balance")
      scope = payload.get("scope", "world")
      page = max(1, int(payload.get("page", 1)))
      guild_id = payload.get("guild_id")

      limit = 10
      offset = (page - 1) * limit

      value_cte = metrics.get(metric)
      if not value_cte:
        return None, f"Unknown metric: {metric}"

      if scope == "server":
        if str(guild_id).isdigit():
          guild_id = int(guild_id)
        else:
          guild_id = None

        if not guild_id:
          return None, "guild_id is required for server scope"
        
        query = f"""
          WITH metric_data AS ({value_cte}),
          ranked_data AS (
            SELECT
              md.user_id,
              md.val AS value,
              ROW_NUMBER() OVER (ORDER BY md.val DESC, md.user_id ASC) AS rank
            FROM metric_data md
            JOIN guild_users gu ON md.user_id = gu.user_id
            LEFT JOIN user_privacy up ON md.user_id = up.user_id
            WHERE gu.guild_id = $1
            AND COALESCE(up.publicity, TRUE)
          ),
          totals AS (
            SELECT COUNT(*) AS total_count
            FROM ranked_data
          ),
          global_sum AS (
            SELECT SUM(value) AS total_value
            FROM ranked_data
          )
          SELECT
            ranked_data.*,
            totals.total_count,
            global_sum.total_value
          FROM ranked_data
          CROSS JOIN totals
          CROSS JOIN global_sum
          WHERE (rank > $2 AND rank <= $3) OR user_id = $4
          ORDER BY rank
        """
        args = [guild_id, offset, offset + limit, discord_id]

      elif scope == "world":
        query = f"""
          WITH metric_data AS ({value_cte}),
          ranked_data AS (
            SELECT
              md.user_id,
              md.val AS value,
              ROW_NUMBER() OVER (ORDER BY md.val DESC, md.user_id ASC) AS rank
            FROM metric_data md
            LEFT JOIN user_privacy up ON md.user_id = up.user_id
            WHERE COALESCE(up.publicity, TRUE)
          ),
          totals AS (
            SELECT COUNT(*) AS total_count
            FROM ranked_data
          ),
          global_sum AS (
            SELECT SUM(value) AS total_value
            FROM ranked_data
          )
          SELECT
            ranked_data.*,
            totals.total_count,
            global_sum.total_value
          FROM ranked_data
          CROSS JOIN totals
          CROSS JOIN global_sum
          WHERE (rank > $1 AND rank <= $2) OR user_id = $3
          ORDER BY rank
        """
        args = [offset, offset + limit, discord_id]

      elif scope == "top_servers":
        query = f"""
          WITH metric_data AS ({value_cte}),
          server_sums AS (
            SELECT
              gu.guild_id,
              SUM(md.val) AS value
            FROM metric_data md
            JOIN guild_users gu ON md.user_id = gu.user_id
            LEFT JOIN user_privacy up ON md.user_id = up.user_id
            WHERE COALESCE(up.publicity, TRUE)
            GROUP BY gu.guild_id
          ),
          ranked_data AS (
            SELECT
              guild_id,
              value,
              ROW_NUMBER() OVER (ORDER BY value DESC, guild_id ASC) AS rank
            FROM server_sums
          ),
          totals AS (
            SELECT COUNT(*) AS total_count
            FROM ranked_data
          ),
          global_sum AS (
            SELECT SUM(value) AS total_value
            FROM server_sums
          )
          SELECT
            ranked_data.*,
            totals.total_count,
            global_sum.total_value
          FROM ranked_data
          CROSS JOIN totals
          CROSS JOIN global_sum
          WHERE rank > $1 AND rank <= $2
          ORDER BY rank
        """
        args = [offset, offset + limit]

      else:
        return None, f"Unknown scope: {scope}"

      rows = await conn.fetch(query, *args)

      if not rows:
        return {
          "total_users": 0,
          "total_value": 0,
          "page": page,
          "pages": 0,
          "entries": [],
          "self": None
        }, None

      total_records = rows[0].get("total_count", 0)
      total_pages = ceil(total_records / limit)
      total_value = rows[0].get("total_value", 0)

      entries = []
      self_data = None

      for row in rows:
        if scope == "top_servers":
          guild = self.bot.get_guild(int(row["guild_id"]))

          if metric == "level":
            row = dict(row)
            lvl, _, _ = calculate_LvL(row["value"])
            row["value"] = lvl
          elif metric == "experience":
            row = dict(row)
            _, _, xp_now = calculate_LvL(row["value"])
            row["value"] = xp_now

          entry = {
            "rank": row["rank"],
            "guild_id": str(row["guild_id"]),
            "guild_name": guild.name if guild else "Unknown Server",
            "icon": str(guild.icon.url) if guild and guild.icon else None,
            "value": row["value"]
          }
        else:
          user_data = self.resolve_user(row["user_id"])

          entry = {
            "rank": row["rank"],
            "user_id": str(row["user_id"]),
            "display_name": user_data["display_name"],
            "avatar": user_data["avatar"],
            "value": row["value"]
          }

        if offset < row["rank"] <= offset + limit:
          entries.append(entry)

        if scope != "top_servers" and str(row["user_id"]) == str(discord_id):
          self_data = entry

      if self_data and any(e["user_id"] == self_data["user_id"] for e in entries):
        self_data = None

      return {
        "total_users": total_records,
        "total_value": total_value,
        "page": page,
        "pages": total_pages,
        "entries": entries,
        "self": self_data
      }, None

    if kind == "guild_profile_stats":
      guild_id_raw = payload.get("guild_id", None)
      guild_id = None
      if not guild_id_raw:
        return None, "Invalid guild ID"

      if str(guild_id_raw).isdigit():
        guild = await conn.fetchrow("""
          SELECT guild_id
          FROM guilds
          WHERE guild_id = $1
        """, int(guild_id_raw))
        if guild:
          guild_id = int(guild["guild_id"])
      if not guild_id:
        return {"me": False}, None

      guild = self.bot.get_guild(guild_id)
      if not guild:
        return None, "Invalid guild"

      guild_settings = await gd.get_data(guild_id,['banned'],'guilds','guild_id',guild)
      if guild_settings["banned"]:
        return None, "This guild is banned"

      member = guild.get_member(discord_id)
      if not member:
        return None, "You are not a member of this guild"

      req = """
        with
          guild_members as (
            select distinct user_id
            from guild_users
            where guild_id = $1::bigint
          ),

          msg as (
            select count(*)::bigint as messages
            from messages
            where guild_id = $1::bigint
          ),

          voice_ms as (
            select coalesce(
              sum((extract(epoch from time_spent) * 1000)::bigint),
              0
            )::bigint as ms
            from voice
            where guild_id = $1::bigint
          ),

          bal as (
            select
              coalesce(sum(coalesce(ud.bank_balance, 0)), 0)::bigint as bank_balance,
              coalesce(sum(coalesce(ud.balance, 0)), 0)::bigint as balance,
              coalesce(sum(coalesce(ud.xp, 0)), 0)::bigint as xp
            from guild_members gu
            left join user_data ud on ud.user_id = gu.user_id
          ),

          acts_dedup as (
            select
              a.user_id,
              a.started_at,
              a.ended_at,
              row_number() over (
                partition by a.user_id, d.name, (extract(epoch from a.started_at)::bigint / 60)
                order by a.started_at asc, a.id asc
              ) as rn
            from guild_members gu
            join activity_segments a on a.user_id = gu.user_id
            join activity_defs d on d.id = a.def_id
          ),

          act_sec as (
            select coalesce(
              sum(greatest(0, extract(epoch from (coalesce(ended_at, current_timestamp) - started_at)))::bigint),
              0
            )::bigint as sec
            from acts_dedup
            where rn = 1
          )

        select
          (select messages from msg) as messages,

          (
            select
              case
                when ms >= 86400000 then
                  (ms / 86400000)::text || ' days ' ||
                  lpad(((ms / 3600000) % 24)::text, 2, '0')
                else
                  lpad((ms / 3600000)::text, 2, '0')
              end
              || ':' || lpad(((ms / 60000) % 60)::text, 2, '0')
              || ':' || lpad(((ms / 1000) % 60)::text, 2, '0')
              || '.' || lpad((ms % 1000)::text, 3, '0')
            from voice_ms
          ) as voice_time,

          (
            select
              case
                when sec >= 86400 then
                  (sec / 86400)::text || ' days ' ||
                  lpad(((sec / 3600) % 24)::text, 2, '0')
                else
                  lpad((sec / 3600)::text, 2, '0')
              end
              || ':' || lpad(((sec / 60) % 60)::text, 2, '0')
              || ':' || lpad((sec % 60)::text, 2, '0')
            from act_sec
          ) as activity_seconds,

          coalesce((select bank_balance + balance from bal), 0) as total_balance,
          coalesce((select bank_balance from bal), 0) as bank_balance,
          coalesce((select balance from bal), 0) as balance,
          coalesce((select xp from bal), 0) as xp;
        """

      channels = {
        "message_channels": {},
        "voice_channels": {}
      }
      message_channels = [ch for ch in guild.channels if not isinstance(ch, CategoryChannel)] + list(guild.threads)
      voice_channels = guild.voice_channels
      for message_channel in message_channels:
        if not all([getattr(message_channel.permissions_for(member), permission, False) for permission in ["read_message_history", "view_channel"]+(["connect"] if isinstance(message_channel, VoiceChannel) else [])]):
          continue
        channels["message_channels"][message_channel.id] = {"name": message_channel.name, "type": message_channel.__class__.__name__}
      for voice_channel in voice_channels:
        if not all([getattr(voice_channel.permissions_for(member), permission, False) for permission in ["connect", "view_channel"]]):
          continue
        channels["voice_channels"][voice_channel.id] = {"name": voice_channel.name, "type": voice_channel.__class__.__name__}

      roles = {role.id: {"name": role.name} for role in guild.roles}

      row = await conn.fetchrow(req, guild_id)
      result = dict(row) if row else {}

      lvl, xp_need, xp_now = calculate_LvL(result["xp"])

      result["lvl"] = lvl
      result["xp_need"] = xp_need
      result["xp_now"] = xp_now
      result["name"] = guild.name
      result["icon"] = guild.icon.url if guild.icon else None
      result["badges"] = []
      result["channels"] = channels
      result["roles"] = roles
      result["members"] = guild.member_count
      return result, None

    if kind == "guild_messages_series":
      frm_ms, to_ms, bucket_ms, limit_n, guild_id_raw, channel_id, _ = self._series_params(payload)
      role_id_raw = payload.get("role_id", None)
      try:
        role_id = int(role_id_raw)
      except Exception:
        role_id = None

      guild_id = None
      if not guild_id_raw:
        return None, "Invalid guild ID"

      if str(guild_id_raw).isdigit():
        guild = await conn.fetchrow("""
          SELECT guild_id
          FROM guilds
          WHERE guild_id = $1
        """, int(guild_id_raw))
        if guild:
          guild_id = int(guild["guild_id"])
      if not guild_id:
        return {"me": False}, None

      guild = self.bot.get_guild(guild_id)
      if not guild:
        return None, "Invalid guild"

      guild_settings = await gd.get_data(guild_id,['banned'],'guilds','guild_id',guild)
      if guild_settings["banned"]:
        return None, "This guild is banned"

      member = guild.get_member(discord_id)
      if not member:
        return None, "You are not a member of this guild"

      members_id = None
      if role_id:
        members_id = []
        for member in guild.members:
          if role_id in [role.id for role in member.roles]:
            members_id.append(member.id)

        if not members_id:
          return [], None

      rows = await conn.fetch("""
        with base as (
          select
            (extract(epoch from date_time) * 1000)::bigint as ts_ms,
            guild_id,
            channel_id
          from messages
          where guild_id = $1::bigint
            and date_time >= to_timestamp($2::bigint / 1000.0)
            and date_time <= to_timestamp($3::bigint / 1000.0)
            and ($6::bigint is null or channel_id = $6::bigint)
            and ($7::bigint[] is null or user_id = any($7::bigint[]))
        ),
        buck as (
          select
            ((ts_ms / $4::bigint) * $4::bigint) as bucket_start,
            count(*)::bigint as y,
            min(ts_ms) as min_ts
          from base
          group by 1
        ),
        sample as (
          select distinct on (((ts_ms / $4::bigint) * $4::bigint))
            ((ts_ms / $4::bigint) * $4::bigint) as bucket_start,
            ts_ms as sample_ts,
            guild_id as sample_guild_id,
            channel_id as sample_channel_id
          from base
          order by ((ts_ms / $4::bigint) * $4::bigint), ts_ms asc
        )
        select
          (case when b.y = 1 then b.min_ts else (b.bucket_start + ($4::bigint / 2)) end)::bigint as ts,
          b.y::bigint as y,
          b.bucket_start::bigint as bucket_start,
          (b.bucket_start + $4::bigint)::bigint as bucket_end,
          s.sample_ts::bigint as sample_ts,
          s.sample_guild_id,
          s.sample_channel_id
        from buck b
        left join sample s using (bucket_start)
        order by b.bucket_start asc
        limit $5;
      """, guild_id, frm_ms, to_ms, bucket_ms, limit_n, channel_id, members_id)

      out = []
      for r in rows:
        d = dict(r)

        gid_raw = d.get("sample_guild_id")
        cid_raw = d.get("sample_channel_id")

        guild_name, channel_name = self._resolve_guild_channel_names(gid_raw, cid_raw)

        d["meta"] = {
          "guild_name": guild_name,
          "channel_name": channel_name
        }
        out.append(d)

      return out, None

    if kind == "guild_voice_series":
      p = self._voice_series_params(payload)

      role_id_raw = p["role_id"]
      try:
        role_id = int(role_id_raw)
      except Exception:
        role_id = None

      guild_id_raw = p["guild_id"]
      guild_id = None

      if not guild_id_raw:
        return None, "Invalid guild ID"

      if str(guild_id_raw).isdigit():
        guild_row = await conn.fetchrow("""
          SELECT guild_id
          FROM guilds
          WHERE guild_id = $1
        """, int(guild_id_raw))
        if guild_row:
          guild_id = int(guild_row["guild_id"])

      if not guild_id:
        return {"me": False}, None

      guild = self.bot.get_guild(guild_id)
      if not guild:
        return None, "Invalid guild"

      guild_settings = await gd.get_data(guild_id, ['banned'], 'guilds', 'guild_id', guild)
      if guild_settings["banned"]:
        return None, "This guild is banned"

      member = guild.get_member(discord_id)
      if not member:
        return None, "You are not a member of this guild"

      members_id = None
      if role_id:
        members_id = []
        for guild_member in guild.members:
          if role_id in [role.id for role in guild_member.roles]:
            members_id.append(guild_member.id)

        if not members_id:
          return [], None

      rows = await conn.fetch("""
        select
          (extract(epoch from enter_time) * 1000)::bigint as ts_ms,
          greatest(0, extract(epoch from (leave_time - enter_time)))::bigint as seconds,
          guild_id,
          after_channel_id as channel_id
        from voice
        where guild_id = $1::bigint
          and enter_time >= to_timestamp($2::bigint / 1000.0)
          and enter_time <= to_timestamp($3::bigint / 1000.0)
          and ($4::bigint is null or after_channel_id = $4::bigint)
          and (
            $5::bigint is null
            or greatest(0, extract(epoch from (leave_time - enter_time)))::bigint >= $5::bigint
          )
          and (
            $6::bigint is null
            or greatest(0, extract(epoch from (leave_time - enter_time)))::bigint <= $6::bigint
          )
          and ($7::bigint[] is null or user_id = any($7::bigint[]))
        order by enter_time asc;
      """,
        guild_id,
        p["from_ms"],
        p["to_ms"],
        p["channel_id"],
        p["min_duration_seconds"],
        p["max_duration_seconds"],
        members_id
      )

      buckets = {}

      for r in rows:
        d = dict(r)

        guild_name, channel_name = self._resolve_guild_channel_names(
          d.get("guild_id"),
          d.get("channel_id")
        )

        if not self._contains_ci(guild_name, p["guild_name"]):
          continue
        if not self._contains_ci(channel_name, p["channel_name"]):
          continue

        ts_ms = int(d["ts_ms"])
        seconds = int(d["seconds"])
        bucket_start = (ts_ms // p["bucket_ms"]) * p["bucket_ms"]

        item = buckets.get(bucket_start)
        if not item:
          buckets[bucket_start] = {
            "ts": bucket_start + (p["bucket_ms"] // 2),
            "y": seconds,
            "bucket_start": bucket_start,
            "bucket_end": bucket_start + p["bucket_ms"],
            "meta": {
              "guild_id": d.get("guild_id"),
              "channel_id": d.get("channel_id"),
              "guild_name": guild_name,
              "channel_name": channel_name
            }
          }
        else:
          item["y"] += seconds

      return [buckets[k] for k in sorted(buckets.keys())[:p["limit"]]], None

    return None, f"Unknown kind: {kind}"

  async def _log_error(self, e, raw_payload):
    tb = "".join(format_exception(type(e), e, e.__traceback__))[:5000]
    log = Embed(
      title="PostgreSQL/Frontend | Error processing client request",
      description=(f"{e}")[:500],
      color=Colour.red(),
      timestamp=datetime.now(timezone.utc)
    )
    log.add_field(
      name="Payload",
      value=f"```json\n{str(raw_payload)[:1000]}\n```",
      inline=False
    )
    for i in range(0, len(tb), 1000):
      log.add_field(
        name="Traceback",
        value=f"```py\n{tb[i:i+1000]}\n```",
        inline=False
      )
    log.set_footer(
      text=f"{str(datetime.now())}",
      icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
    )
    try:
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
    except:
      pass

  @loop.before_loop
  async def before_loop_start(self):
    await self.bot.wait_until_ready()

  @cache_gc.before_loop
  async def before_cache_gc_start(self):
    await self.bot.wait_until_ready()

def setup(bot: commands.Bot):
  bot.add_cog(WebRequestsWorker(bot))