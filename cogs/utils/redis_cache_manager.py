from nextcord.ext import commands, tasks
from logging import getLogger
from asyncio import sleep
from json import loads
from time import time
from uuid import uuid4
from datetime import datetime
from Utils.redis_keys import build_key, parse_key, serialize_row, deserialize_row

logger = getLogger(__name__)

ACTIVE_FLUSH_KEY = "sys:active_flush"
FLUSH_KEYS_PREFIX = "flush_keys:"
SYNC_QUEUE_KEY = "sys:sync_queue"
FLUSHING_SUFFIX = ":flushing"
SCAN_PREFIXES = ("insert:", "delta:", "override:", "delete:")

class RedisCacheManager(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.global_sync_worker.start()

    self._last_sync_time = time()
    self._sync_counter = 0

  def cog_unload(self):
    self.global_sync_worker.cancel()

  async def cog_load(self):
    bus = None
    while bus is None:
      bus = self.bot.get_cog("PostgresNotifyBus")
      if not bus:
        await sleep(1)

    bus.add_handler("data_changes", self.handle_data_change_invalidation)

  async def handle_data_change_invalidation(self, conn, pid, channel, payload):
    try:
      data = loads(payload)
      table = data.get('table')
      pk: dict = data.get('pk') or {}
      operation = data.get('operation')

      if not table or not pk:
        return

      ident = build_key(table, pk)
      key = f"db:{ident}"
      tombstone_key = f"tombstone:{ident}"

      if operation == 'DELETE':
        pipe = self.bot.redis.pipeline()
        pipe.delete(key)
        pipe.delete(f"dtype:{ident}")
        pipe.delete(f"override:{ident}")
        pipe.delete(f"delta:{ident}")
        pipe.set(tombstone_key, "1", ex=300)
        await pipe.execute()
        return

      new_data = data.get('new_data')
      if not new_data:
        return

      values, types = serialize_row(new_data)
      if not values:
        return

      pipe = self.bot.redis.pipeline()
      pipe.delete(tombstone_key)
      pipe.delete(key)
      pipe.hset(key, mapping=values)
      pipe.expire(key, 300)
      if types:
        pipe.hset(f"dtype:{ident}", mapping=types)
        pipe.expire(f"dtype:{ident}", 300)
      await pipe.execute()
    except Exception:
      logger.exception("data_changes invalidation failed for payload=%r", payload)

  @tasks.loop(seconds=1)
  async def global_sync_worker(self):
    try:
      active_flush_id = await self.bot.redis.get(ACTIVE_FLUSH_KEY)
      if active_flush_id:
        await self._resume_batch(active_flush_id)
        return

      await self._maybe_start_new_batch()
    except Exception:
      logger.exception("global_sync_worker tick failed")

  @global_sync_worker.before_loop
  async def before_global_sync_worker(self):
    await self.bot.wait_until_ready()

  async def _maybe_start_new_batch(self):
    now = int(time())
    
    earliest = await self.bot.redis.zrange(SYNC_QUEUE_KEY, 0, 0, withscores=True)
    if not earliest or earliest[0][1] > now:
      return

    fresh_keys = []
    for prefix in SCAN_PREFIXES:
      cursor = 0
      while True:
        cursor, keys = await self.bot.redis.scan(cursor=cursor, match=f"{prefix}*", count=200)
        fresh_keys.extend(k for k in keys if not k.endswith(FLUSHING_SUFFIX))
        if cursor == 0:
          break

    if not fresh_keys:
      await self.bot.redis.delete(SYNC_QUEUE_KEY)
      return

    flush_id = uuid4().hex
    renamed = [f"{k}{FLUSHING_SUFFIX}" for k in fresh_keys]

    pipe = self.bot.redis.pipeline(transaction=True)
    for src, dst in zip(fresh_keys, renamed):
      pipe.rename(src, dst)
    pipe.set(ACTIVE_FLUSH_KEY, flush_id)
    pipe.sadd(f"{FLUSH_KEYS_PREFIX}{flush_id}", *renamed)
    pipe.delete(SYNC_QUEUE_KEY)
    await pipe.execute()

    await self._process_batch(flush_id)

  async def _resume_batch(self, flush_id: str):
    async with self.bot.db_pool.acquire() as conn:
      row = await conn.fetchrow("SELECT 1 FROM sync_batches WHERE flush_id = $1", flush_id)

    if row:
      await self._cleanup_batch(flush_id)
      return

    await self._process_batch(flush_id)

  async def _process_batch(self, flush_id: str):
    now = time()
    elapsed = round(now - self._last_sync_time, 1)
    self._last_sync_time = now
    self._sync_counter += 1

    with open("sync_stats.log", "a", encoding="utf-8") as f:
      f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Сброс #{self._sync_counter} | Прошло с прошлого раза: {elapsed} сек.\n")

    flushing_keys = list(await self.bot.redis.smembers(f"{FLUSH_KEYS_PREFIX}{flush_id}"))

    if not flushing_keys:
      await self._cleanup_batch(flush_id)
      return

    inserts: dict[str, list[dict]] = {}
    overrides: dict[str, list[tuple[dict, dict]]] = {}
    deltas: dict[str, list[tuple[dict, dict]]] = {}
    deletes: dict[str, list[dict]] = {}

    for key in flushing_keys:
      body = key[:-len(FLUSHING_SUFFIX)]

      if body.startswith("insert:"):
        table = body[len("insert:"):]
        raw_rows = await self.bot.redis.lrange(key, 0, -1)
        if raw_rows:
          inserts.setdefault(table, []).extend(loads(r) for r in raw_rows)

      elif body.startswith("override:"):
        ident = body[len("override:"):]
        table, keys_dict = parse_key(ident)
        raw = await self.bot.redis.hgetall(key)
        if raw:
          types = await self.bot.redis.hgetall(f"dtype:{ident}")
          fields = deserialize_row(raw, types or {})
          overrides.setdefault(table, []).append((keys_dict, fields))

      elif body.startswith("delta:"):
        ident = body[len("delta:"):]
        table, keys_dict = parse_key(ident)
        raw = await self.bot.redis.hgetall(key)
        if raw:
          deltas.setdefault(table, []).append((keys_dict, {col: float(v) for col, v in raw.items()}))

      elif body.startswith("delete:"):
        table = body[len("delete:"):]
        for member in await self.bot.redis.smembers(key):
          _, keys_dict = parse_key(member)
          deletes.setdefault(table, []).append(keys_dict)

    async with self.bot.db_pool.acquire() as conn:
      async with conn.transaction():
        await self._flush_inserts(conn, inserts)
        await self._flush_overrides(conn, overrides)
        await self._flush_deltas(conn, deltas)
        await self._flush_deletes(conn, deletes)
        await conn.execute("INSERT INTO sync_batches (flush_id) VALUES ($1) ON CONFLICT DO NOTHING", flush_id)

    await self._cleanup_batch(flush_id)

  async def _cleanup_batch(self, flush_id: str):
    flush_keys_set = f"{FLUSH_KEYS_PREFIX}{flush_id}"
    members = await self.bot.redis.smembers(flush_keys_set)

    pipe = self.bot.redis.pipeline()
    for member in members:
      pipe.delete(member)
    pipe.delete(flush_keys_set)
    pipe.delete(ACTIVE_FLUSH_KEY)
    await pipe.execute()

    async with self.bot.db_pool.acquire() as conn:
      await conn.execute("DELETE FROM sync_batches WHERE flush_id = $1", flush_id)

  async def _flush_inserts(self, conn, inserts: dict[str, list[dict]]):
    for table, rows in inserts.items():
      if not rows:
        continue

      if table == "users":
        for row in rows:
          if not row.get("language"):
            row["language"] = "en"

      cols = sorted({col for row in rows for col in row.keys()})
      placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
      query = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
      values_list = [[row.get(col) for col in cols] for row in rows]
      
      fixed_values = []
      for row in values_list:
        fixed_row = []
        for val in row:
          if isinstance(val, str) and len(val) >= 19:
            try:
              val = datetime.fromisoformat(val)
            except ValueError:
              pass
          fixed_row.append(val)
        fixed_values.append(fixed_row)
      values_list = fixed_values

      await conn.executemany(query, values_list)

  async def _flush_overrides(self, conn, overrides: dict[str, list[tuple[dict, dict]]]):
    for table, entries in overrides.items():
      for keys_dict, fields in entries:
        if not fields:
          continue
        set_cols = list(fields.keys())
        set_clause = ", ".join(f"{col} = ${i + 1}" for i, col in enumerate(set_cols))
        where_clause, where_values = self._build_where(len(set_cols), keys_dict)
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        await conn.execute(query, *[fields[col] for col in set_cols], *where_values)

  async def _flush_deltas(self, conn, deltas: dict[str, list[tuple[dict, dict]]]):
    for table, entries in deltas.items():
      for keys_dict, delta_fields in entries:
        if not delta_fields:
          continue
        delta_cols = list(delta_fields.keys())
        set_clause = ", ".join(f"{col} = {col} + ${i + 1}" for i, col in enumerate(delta_cols))
        where_clause, where_values = self._build_where(len(delta_cols), keys_dict)
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        await conn.execute(query, *[delta_fields[col] for col in delta_cols], *where_values)

  async def _flush_deletes(self, conn, deletes: dict[str, list[dict]]):
    for table, entries in deletes.items():
      for keys_dict in entries:
        where_clause, where_values = self._build_where(0, keys_dict)
        query = f"DELETE FROM {table} WHERE {where_clause}"
        await conn.execute(query, *where_values)

  @staticmethod
  def _build_where(offset: int, keys_dict: dict) -> tuple[str, list]:
    cols = list(keys_dict.keys())
    clause = " AND ".join(f"{col} = ${offset + i + 1}" for i, col in enumerate(cols))
    return clause, [keys_dict[col] for col in cols]

def setup(bot: commands.Bot):
  bot.add_cog(RedisCacheManager(bot))