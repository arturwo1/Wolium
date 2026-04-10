from __future__ import annotations
from json import loads, dumps
from asyncio import Lock, Semaphore, create_task, TimeoutError, sleep
from time import time
from decimal import Decimal
from datetime import datetime, timezone
from traceback import format_exception
from nextcord.ext import commands, tasks
from nextcord import Embed, Colour, CategoryChannel
from Utils.calculate_LvL import calculate_LvL
from asyncpg import ConnectionDoesNotExistError, InterfaceError, PostgresConnectionError

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
    context_raw = payload.get("context")

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
  
  def _activity_type_label(self, activity_type):
    try:
      t = int(activity_type)
    except:
      return "Unknown"

    return {
      0: "Playing",
      1: "Streaming",
      2: "Listening",
      3: "Watching",
      4: "Custom",
      5: "Competing"
    }.get(t, "Unknown")

  def _extract_activity_meta(self, def_payload_raw, snapshot_payload_raw):
    def_payload = self._parse_payload(def_payload_raw)
    snapshot_payload = self._parse_payload(snapshot_payload_raw)

    assets = def_payload.get("assets")
    if not isinstance(assets, dict):
      assets = {}

    party = def_payload.get("party")
    if not isinstance(party, dict):
      party = {}

    party_size = party.get("size")
    if isinstance(party_size, (list, tuple)) and len(party_size) >= 2:
      party_current = party_size[0]
      party_max = party_size[1]
    else:
      party_current = party.get("current_size")
      party_max = party.get("max_size")

    return {
      "application_name": def_payload.get("application_name") or def_payload.get("application"),
      "platform": def_payload.get("platform"),
      "details": def_payload.get("details"),
      "state": def_payload.get("state"),
      "description": def_payload.get("description"),
      "track": def_payload.get("track") or def_payload.get("song"),
      "album": def_payload.get("album"),
      "artist": def_payload.get("artist"),
      "twitch": def_payload.get("twitch") or def_payload.get("url"),
      "large_image": assets.get("large_image"),
      "large_text": assets.get("large_text"),
      "small_image": assets.get("small_image"),
      "small_text": assets.get("small_text"),
      "party_current": party_current,
      "party_max": party_max,
      "raw_payload": def_payload,
      "raw_snapshot_payload": snapshot_payload
    }
  
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
      "min_duration_seconds": min_sec,
      "max_duration_seconds": max_sec
    }

  def _activities_series_params(self, payload: dict):
    frm_ms, to_ms, _, limit_n, _, _, context = self._series_params(payload)
    min_sec, max_sec = self._duration_range_seconds(payload)

    return {
      "from_ms": frm_ms,
      "to_ms": to_ms,
      "limit": limit_n,
      "activity_name": self._clean_text(payload.get("activity_name") or context),
      "track": self._clean_text(payload.get("track")),
      "album": self._clean_text(payload.get("album")),
      "artist": self._clean_text(payload.get("artist")),
      "status": self._clean_text(payload.get("status"), max_len=32),
      "min_duration_seconds": min_sec,
      "max_duration_seconds": max_sec
    }

  def _extract_presence_status(self, status_code_raw, snapshot_payload_raw):
    payload = self._parse_payload(snapshot_payload_raw)

    for key in ("status", "overall_status", "user_status"):
      value = payload.get(key)
      if value not in (None, ""):
        return str(value).strip().lower()

    if status_code_raw not in (None, ""):
      return str(status_code_raw).strip().lower()

    return None

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

  async def _set_done(self, conn, req_id, result_obj):
    result_json = dumps(result_obj, ensure_ascii=False)
    await conn.execute(f"""
      update {QUEUE_TABLE}
      set status='done',
          result=$2::jsonb,
          error=null,
          updated_at=now(),
          expires_at=now() + interval '{ROW_TTL_AFTER_DONE_SECONDS} seconds'
      where id=$1
    """, req_id, result_json)

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

              result = await self._process_kind(conn, kind, discord_id, payload, job)
              result = self._convert_decimals(result)

              await self.cache.set(ck, result)
              await self._set_done(conn, job["id"], result)
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
    get_data = self.bot.get_cog("GetData")
    if not get_data: return {"error": "Failed to get data."}

    user_info = await get_data.get_data(discord_id, ["banned", "auth_user_id", "badges"], "users", "user_id", None)

    if user_info.get("banned"):
      return {"error": "You are banned."}
    
    current_auth_user_id = user_info.get("auth_user_id")
    new_auth_user_id = job["user_id"]

    if not current_auth_user_id:
      update_data = self.bot.get_cog("UpdateData")
      if not update_data:
        return {"error": "Failed to update data."}

      await update_data.update_data(
        discord_id,
        {"auth_user_id": new_auth_user_id},
        "users",
        "user_id",
        None
      )

    elif current_auth_user_id != new_auth_user_id:
      return {"error": "You already logged in another account."}

    if kind == "profile_stats":
      row = await conn.fetchrow("""
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
          act_sec as (
            with acts as (
              select
                s.def_id,
                coalesce(s.activity_started_at, s.started_at) as grp_started_at,
                min(coalesce(s.activity_started_at, s.started_at)) as started_at,
                max(coalesce(s.activity_ended_at, s.ended_at, s.started_at)) as ended_at
              from activity_segments s
              where s.user_id = $1::bigint
              group by
                s.def_id,
                coalesce(s.activity_started_at, s.started_at)
            )
            select coalesce(
              sum(greatest(0, extract(epoch from (ended_at - started_at)))::bigint),
              0::bigint
            ) as sec
            from acts
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

          coalesce((select bank_balance + balance from bal), 0) as total_balance,
          coalesce((select bank_balance from bal), 0) as bank_balance,
          coalesce((select balance from bal), 0) as balance;
      """, discord_id)
      result = dict(row) if row else {}

      user_data = await get_data.get_data(discord_id, ["xp"], "user_data", "user_id", None)
      xp = user_data.get("xp") or 0

      u = self.bot.get_user(discord_id)
      username = u.display_name if u else "Unknown Name"
      member = next((m for m in self.bot.get_all_members() if m.id == discord_id), None)

      mutual_guilds = member and member.mutual_guilds or []
      mutual_guilds_row = {}
      for mutual_guild in mutual_guilds:
        mutual_guilds_row[mutual_guild.id] = {"name": mutual_guild.name, "text_channels": {}, "voice_channels": {}}

        text_channels = [ch for ch in mutual_guild.channels if not isinstance(ch, CategoryChannel)] + list(mutual_guild.threads)
        voice_channels = mutual_guild.voice_channels
        
        for channel in text_channels:
          if not channel.permissions_for(member).view_channel:
            continue
          mutual_guilds_row[mutual_guild.id]["text_channels"][channel.id] = {"name": channel.name, "type": channel.__class__.__name__}
        
        for channel in voice_channels:
          if not channel.permissions_for(member).view_channel:
            continue
          mutual_guilds_row[mutual_guild.id]["voice_channels"][channel.id] = {"name": channel.name, "type": channel.__class__.__name__}

      lvl, xp_need, xp_now = calculate_LvL(xp)
      result["xp"] = xp
      result["lvl"] = lvl
      result["xp_need"] = xp_need
      result["xp_now"] = xp_now
      result["user_name"] = username
      result["badges"] = user_info["badges"]
      result["status"] = member and str(member.status) or None
      result["client_status"] = {
        "desktop": str(getattr(member, "desktop_status", "offline")) if member else "offline",
        "mobile": str(getattr(member, "mobile_status", "offline")) if member else "offline",
        "web": str(getattr(member, "web_status", "offline")) if member else "offline"
      }
      result["guilds"] = mutual_guilds_row
      return result

    if kind == "messages_series":
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

      return out

    if kind == "voice_series":
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

      return [buckets[k] for k in sorted(buckets.keys())[:p["limit"]]]

    if kind == "activities_series":
      p = self._activities_series_params(payload)

      rows = await conn.fetch("""
        with acts as (
          select
            min(s.id)::bigint as id,
            s.def_id::bigint as def_id,
            min(s.snapshot_id)::bigint as snapshot_id,
            min(s.started_at) as started_at,
            max(s.ended_at) as ended_at,
            min(s.activity_started_at) as activity_started_at,
            max(s.activity_ended_at) as activity_ended_at
          from activity_segments s
          where s.user_id = $1::bigint
            and coalesce(s.activity_ended_at, s.ended_at, s.started_at) >= to_timestamp($2::bigint / 1000.0)
            and coalesce(s.activity_started_at, s.started_at) <= to_timestamp($3::bigint / 1000.0)
          group by s.def_id, s.activity_started_at
        )
        select
          a.id,
          a.def_id,

          (extract(epoch from a.started_at) * 1000)::bigint as started_at_ms,
          (extract(epoch from a.ended_at) * 1000)::bigint as ended_at_ms,
          (extract(epoch from coalesce(a.activity_started_at, a.started_at)) * 1000)::bigint as activity_started_at_ms,
          (extract(epoch from coalesce(a.activity_ended_at, a.ended_at)) * 1000)::bigint as activity_ended_at_ms,

          greatest(
            0,
            extract(epoch from (
              coalesce(a.activity_ended_at, a.ended_at) - coalesce(a.activity_started_at, a.started_at)
            ))
          )::bigint as duration_seconds,

          d.source_kind,
          d.activity_type,
          d.name,
          d.payload as activity_def_payload,

          ps.id as presence_snapshot_id,
          ps.fingerprint as presence_snapshot_fingerprint,
          ps.guild_id as presence_snapshot_guild_id,
          ps.user_id as presence_snapshot_user_id,
          ps.status_code,
          ps.desktop_status_code,
          ps.mobile_status_code,
          ps.web_status_code,
          ps.payload as presence_snapshot_payload

        from acts a
        join activity_defs d
          on d.id = a.def_id
        left join presence_snapshots ps
          on ps.id = a.snapshot_id
        where
          ($4::text is null or d.name ilike ('%' || $4::text || '%'))
          and ($5::text is null or coalesce(d.payload->>'track', d.payload->>'song', '') ilike ('%' || $5::text || '%'))
          and ($6::text is null or coalesce(d.payload->>'album', '') ilike ('%' || $6::text || '%'))
          and ($7::text is null or coalesce(d.payload->>'artist', '') ilike ('%' || $7::text || '%'))
          and ($8::bigint is null or greatest(
            0,
            extract(epoch from (
              coalesce(a.activity_ended_at, a.ended_at) - coalesce(a.activity_started_at, a.started_at)
            ))
          )::bigint >= $8::bigint)
          and ($9::bigint is null or greatest(
            0,
            extract(epoch from (
              coalesce(a.activity_ended_at, a.ended_at) - coalesce(a.activity_started_at, a.started_at)
            ))
          )::bigint <= $9::bigint)
        order by coalesce(a.activity_started_at, a.started_at) asc
        limit $10;
      """,
        discord_id,
        p["from_ms"],
        p["to_ms"],
        p["activity_name"],
        p["track"],
        p["album"],
        p["artist"],
        p["min_duration_seconds"],
        p["max_duration_seconds"],
        p["limit"]
      )

      out = []

      for r in rows:
        d = dict(r)

        presence_status = self._extract_presence_status(
          d.get("status_code"),
          d.get("presence_snapshot_payload")
        )

        if p["status"] and presence_status != p["status"].casefold():
          continue

        activity_payload = self._parse_payload(d.get("activity_def_payload"))

        started_at_ms = int(d["activity_started_at_ms"])
        ended_at_ms = int(d["activity_ended_at_ms"])
        duration_seconds = int(d["duration_seconds"])

        out.append({
          "ts": started_at_ms,
          "y": duration_seconds,
          "bucket_start": started_at_ms,
          "bucket_end": ended_at_ms,
          "meta": {
            "id": int(d["id"]),
            "def_id": int(d["def_id"]),
            "source_kind": d.get("source_kind"),
            "activity_type": d.get("activity_type"),
            "activity_type_label": self._activity_type_label(d.get("activity_type")),
            "name": d.get("name"),
            "status": presence_status,

            "track": activity_payload.get("track") or activity_payload.get("song"),
            "album": activity_payload.get("album"),
            "artist": activity_payload.get("artist"),

            "started_at": int(d["started_at_ms"]),
            "ended_at": int(d["ended_at_ms"]),
            "activity_started_at": int(d["activity_started_at_ms"]),
            "activity_ended_at": int(d["activity_ended_at_ms"]),

            "activity_def": {
              "name": d.get("name"),
              "source_kind": d.get("source_kind"),
              "activity_type": d.get("activity_type"),
              "payload": activity_payload
            },

            "presence_snapshot": {
              "id": d.get("presence_snapshot_id"),
              "fingerprint": d.get("presence_snapshot_fingerprint"),
              "guild_id": d.get("presence_snapshot_guild_id"),
              "user_id": d.get("presence_snapshot_user_id"),
              "status_code": d.get("status_code"),
              "desktop_status_code": d.get("desktop_status_code"),
              "mobile_status_code": d.get("mobile_status_code"),
              "web_status_code": d.get("web_status_code"),
              "payload": self._parse_payload(d.get("presence_snapshot_payload"))
            }
          }
        })

      return out

    return {"error": f"Unknown kind: {kind}"}

  async def _log_error(self, e, raw_payload):
    tb = "".join(format_exception(type(e), e, e.__traceback__))[:5000]
    log = Embed(
      title="Postgresql/Frontend | Ошибка при обработке запроса клиента",
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