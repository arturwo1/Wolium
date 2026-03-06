from __future__ import annotations
from json import loads, dumps
from asyncio import Lock, Semaphore, create_task
from time import time
from decimal import Decimal
from datetime import datetime, timezone
from traceback import format_exception
from turtle import up
from nextcord.ext import commands, tasks
from nextcord import Embed, Colour, channel
from sympy import use
from Utils.calculate_LvL import calculate_LvL

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

    if not self.loop.is_running():
      self.loop.start()
    if not self.cache_gc.is_running():
      self.cache_gc.start()

  def cog_unload(self):
    if self.loop.is_running():
      self.loop.cancel()
    if self.cache_gc.is_running():
      self.cache_gc.cancel()

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
    if isinstance(obj, list):
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

    return frm_ms, to_ms, bucket_ms, limit

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
      create_task(self._handle_job(job))

  @tasks.loop(seconds=5)
  async def cache_gc(self):
    await self.cache.cleanup()

  async def _claim_jobs(self, limit_n: int):
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

        except Exception as e:
          await self._log_error(e, {"job": dict(job) if job else None})
          try:
            await self._set_error(conn, job["id"], str(e))
          except:
            pass

  async def _process_kind(self, conn, kind: str, discord_id: int, payload: dict, job: dict):
    get_data = self.bot.get_cog("GetData")
    if not get_data: return {"error": "Failed to get data."}

    user_info = await get_data.get_data(discord_id, ["banned", "auth_user_id"], "users", "user_id", None)

    if user_info.get("banned"):
      return {"error": "You are banned."}
    
    if not user_info.get("auth_user_id"):
      update_data = self.bot.get_cog("UpdateData")
      if update_data:
        await update_data.update_data(discord_id, {"auth_user_id": job["user_id"]}, "users", "user_id", None)
    else:
      return {"error": "You already logged in another account."}

    u = self.bot.get_user(discord_id)
    username = u.display_name if u else "Unknown Name"

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

          coalesce((select bank_balance + balance from bal), 0) as total_balance,
          coalesce((select bank_balance from bal), 0) as bank_balance,
          coalesce((select balance from bal), 0) as balance;
      """, discord_id)
      result = dict(row) if row else {}

      user_data = await get_data.get_data(discord_id, ["xp"], "user_data", "user_id", None)
      xp = user_data.get("xp") or 0

      lvl, xp_need, xp_now = calculate_LvL(xp)
      result["xp"] = xp
      result["lvl"] = lvl
      result["xp_need"] = xp_need
      result["xp_now"] = xp_now
      result["user_name"] = username
      return result

    if kind == "messages_series":
      frm_ms, to_ms, bucket_ms, limit_n = self._series_params(payload)

      rows = await conn.fetch("""
        with base as (
          select
            (extract(epoch from date_time) * 1000)::bigint as ts_ms,
            content,
            guild_id,
            channel_id,
            message_url
          from messages
          where user_id = $1::bigint
            and date_time >= to_timestamp($2::bigint / 1000.0)
            and date_time <= to_timestamp($3::bigint / 1000.0)
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
            message_url as sample_url
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
          s.sample_channel_id
        from buck b
        left join sample s using (bucket_start)
        order by b.bucket_start asc
        limit $5;
      """, discord_id, frm_ms, to_ms, bucket_ms, limit_n)

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
      frm_ms, to_ms, bucket_ms, limit_n = self._series_params(payload)

      rows = await conn.fetch("""
        with base as (
          select
            (extract(epoch from enter_time) * 1000)::bigint as ts_ms,
            greatest(0, extract(epoch from (leave_time - enter_time)))::bigint as seconds,
            guild_id,
            after_channel_id
          from voice
          where user_id = $1::bigint
            and enter_time >= to_timestamp($2::bigint / 1000.0)
            and enter_time <= to_timestamp($3::bigint / 1000.0)
        ),
        buck as (
          select
            ((ts_ms / $4::bigint) * $4::bigint) as bucket_start,
            coalesce(sum(seconds), 0)::bigint as y,
            max(guild_id) as guild_id,
            max(after_channel_id) as channel_id
          from base
          group by 1
        )
        select
          (bucket_start + ($4::bigint / 2))::bigint as ts,
          y::bigint as y,
          bucket_start::bigint as bucket_start,
          (bucket_start + $4::bigint)::bigint as bucket_end,
          jsonb_build_object('guild_id', guild_id, 'channel_id', channel_id) as meta
        from buck
        order by bucket_start asc
        limit $5;
      """, discord_id, frm_ms, to_ms, bucket_ms, limit_n)

      return [dict(r) for r in rows]

    if kind == "activities_series":
      return []

    if kind == "messages_rows":
      frm_ms = int(payload.get("from", 0) or 0)
      to_ms = int(payload.get("to", 0) or 0)
      rows = await conn.fetch("""
        select id,
               (extract(epoch from date_time) * 1000)::bigint as ts,
               content
        from messages
        where user_id=$1
          and date_time between to_timestamp(($2::bigint)/1000) and to_timestamp(($3::bigint)/1000)
        order by date_time asc
      """, discord_id, frm_ms, to_ms)
      return [dict(r) for r in rows]

    if kind == "voice_rows":
      frm_ms = int(payload.get("from", 0) or 0)
      to_ms = int(payload.get("to", 0) or 0)
      rows = await conn.fetch("""
        select id,
               (extract(epoch from enter_time) * 1000)::bigint as ts,
               (extract(epoch from (leave_time - enter_time)))::int as seconds,
               guild_id, before_channel_id, after_channel_id
        from voice
        where user_id=$1
          and enter_time between to_timestamp(($2::bigint)/1000) and to_timestamp(($3::bigint)/1000)
        order by enter_time asc
      """, discord_id, frm_ms, to_ms)
      return [dict(r) for r in rows]

    if kind == "activities_rows":
      return []

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