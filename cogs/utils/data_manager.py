from nextcord.ext import commands
from json import dumps, loads
from time import time
from hashlib import sha256
from typing import Any, Dict, Optional, Callable, Awaitable
from Utils.redis_keys import build_key, serialize_row, deserialize_row

locale_map = {
  "en-US": "en",
  "en-GB": "en",
  "es-ES": "es",
  "sv-SE": "sv"
}

class DataManager(commands.Cog):
  def __init__(self, bot:commands.Bot):
    self.bot = bot

  async def get_row(self, table: str, keys: Dict[str, Any], expected_fields: Optional[list] = None, guild: Optional[Any] = None, user: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    ident = build_key(table, keys)
    key = f"db:{ident}"

    if await self.bot.redis.exists(f"tombstone:{ident}"):
      return None

    resolved_keys = await self._keys_resolver(keys, guild, user)
    await self.bot.get_cog("EnsureAllTablesExists").ensure_all_tables_exists(keys, resolved_keys)

    cached_data = await self.bot.redis.hgetall(key)
    cache_dict = None

    if cached_data:
      cached_types = await self.bot.redis.hgetall(f"dtype:{ident}")
      cache_dict = deserialize_row(cached_data, cached_types)
      
      if expected_fields:
        if all(field in cache_dict for field in expected_fields):
          return cache_dict 
      else:
        return cache_dict

    where = " AND ".join(f"{col} = ${i+1}" for i, col in enumerate(keys))
    query = f"SELECT * FROM {table} WHERE {where}"
    async with self.bot.db_pool.acquire() as conn:
      row = await conn.fetchrow(query, *keys.values())

    if not row:
      return cache_dict

    data = dict(row)

    values, types = serialize_row(data)
    if values:
      pipe = self.bot.redis.pipeline()
      pipe.hset(key, mapping=values)
      pipe.expire(key, 600)
      if types:
        pipe.hset(f"dtype:{ident}", mapping=types)
        pipe.expire(f"dtype:{ident}", 600)
      await pipe.execute()

    return data

  async def update_delta(self, table: str, keys: Dict[str, Any], deltas: Dict[str, float | int], ttl_seconds: int = 300, guild: Optional[Any] = None, user: Optional[Any] = None):
    ident = build_key(table, keys)
    key = f"db:{ident}"
    delta_key = f"delta:{ident}"
    deadline = int(time()) + ttl_seconds

    if await self.bot.redis.exists(f"tombstone:{ident}"):
      raise ValueError(f"row {keys} in {table} is pending deletion")

    resolved_keys = await self._keys_resolver(keys, guild, user)
    await self.bot.get_cog("EnsureAllTablesExists").ensure_all_tables_exists(keys, resolved_keys)

    if not await self.bot.redis.exists(key) and await self.get_row(table, keys) is None:
      raise ValueError(f"row {keys} in {table} does not exist")

    pipe = self.bot.redis.pipeline()
    for col, val in deltas.items():
      pipe.hincrbyfloat(key, col, float(val))
      pipe.hincrbyfloat(delta_key, col, float(val))

    pipe.execute_command("ZADD", "sys:sync_queue", "NX", deadline, delta_key)
    await pipe.execute()

  async def set_fields(self, table: str, keys: Dict[str, Any], fields: Dict[str, Any], ttl_seconds: int = 300, guild: Optional[Any] = None, user: Optional[Any] = None):
    ident = build_key(table, keys)
    key = f"db:{ident}"
    override_key = f"override:{ident}"
    deadline = int(time()) + ttl_seconds

    values, types = serialize_row(fields)

    if await self.bot.redis.exists(f"tombstone:{ident}"):
      raise ValueError(f"row {keys} in {table} is pending deletion")

    resolved_keys = await self._keys_resolver(keys, guild, user)
    await self.bot.get_cog("EnsureAllTablesExists").ensure_all_tables_exists(keys, resolved_keys)

    pipe = self.bot.redis.pipeline()
    pipe.hset(key, mapping=values)
    pipe.expire(key, ttl_seconds + 120)
    if types:
      pipe.hset(f"dtype:{ident}", mapping=types)
      pipe.expire(f"dtype:{ident}", ttl_seconds + 120)
    pipe.hset(override_key, mapping=values)
    pipe.execute_command("ZADD", "sys:sync_queue", "NX", deadline, override_key)
    await pipe.execute()

  async def insert_row(self, table: str, keys: Dict[str, Any], data: Dict[str, Any], ttl_seconds: int = 300):
    ident = build_key(table, keys)
    key = f"db:{ident}"
    insert_key = f"insert:{table}"
    deadline = int(time()) + ttl_seconds
    full_data = {**keys, **data}

    pipe = self.bot.redis.pipeline()
    pipe.delete(f"tombstone:{ident}")
    pipe.srem(f"delete:{table}", ident)
    values, types = serialize_row(full_data)
    pipe.hset(key, mapping=values)
    pipe.expire(key, ttl_seconds + 120)
    if types:
      pipe.hset(f"dtype:{ident}", mapping=types)
      pipe.expire(f"dtype:{ident}", ttl_seconds + 120)
    pipe.rpush(insert_key, dumps(full_data, ensure_ascii=False, default=str))
    pipe.execute_command("ZADD", "sys:sync_queue", "NX", deadline, insert_key)
    await pipe.execute()

  async def delete_row(self, table: str, keys: Dict[str, Any], ttl_seconds: int = 300):
    ident = build_key(table, keys)
    key = f"db:{ident}"
    tombstone_key = f"tombstone:{ident}"
    delete_key = f"delete:{table}"
    deadline = int(time()) + ttl_seconds

    pipe = self.bot.redis.pipeline()
    pipe.delete(key)
    pipe.delete(f"dtype:{ident}")
    pipe.set(tombstone_key, "1", ex=ttl_seconds + 120)
    pipe.sadd(delete_key, ident)
    pipe.execute_command("ZADD", "sys:sync_queue", "NX", deadline, delete_key)
    await pipe.execute()

  async def get_or_query(self, name: str, params: dict, ttl_seconds: int, query_fn: Callable[[], Awaitable[list]]):
    key = self._query_cache_key(name, params)

    cached = await self.bot.redis.get(key)
    if cached is not None:
      rows = loads(cached)
      return [deserialize_row(values, types) for values, types in rows]

    result = await query_fn()

    rows = [serialize_row(row) for row in result]
    await self.bot.redis.set(key, dumps(rows, ensure_ascii=False), ex=ttl_seconds)

    return result

  def _query_cache_key(self, name: str, params: dict) -> str:
    canon = dumps({k: params[k] for k in sorted(params)}, default=str)
    digest = sha256(canon.encode()).hexdigest()
    return f"qcache:{name}:{digest}"

  async def _keys_resolver(self, keys: Dict[str, Any], guild=None, user=None):
    payload: dict[str, Any] = {}

    user_id = keys.get("user_id") or (user.id if user else None)
    guild_id = keys.get("guild_id") or (guild.id if guild else None)

    if user_id is not None:
      user_id = int(user_id)
      payload["user_id"] = user_id
      payload["discord_id"] = user_id
      payload["badges"] = dumps(["discord"])

      if user is None:
        user = self.bot.get_user(user_id)
        if not user:
          try:
            user = await self.bot.fetch_user(user_id)
          except Exception:
            pass

      if user:
        payload["username"] = user.name
      else:
        payload["username"] = "Unknown"

      payload["language"] = "en"

    if guild_id is not None:
      guild_id = int(guild_id)
      payload["guild_id"] = guild_id

      if guild is None:
        guild = self.bot.get_guild(guild_id)
        if not guild:
          try:
            guild = await self.bot.fetch_guild(guild_id)
          except Exception:
            pass

      if guild:
        payload["language"] = locale_map.get(getattr(guild, "preferred_locale", None), "en")
      else:
        payload["language"] = "en"

    return payload

def setup(bot:commands.Bot):
  bot.add_cog(DataManager(bot))