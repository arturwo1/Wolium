from nextcord.ext import commands
from asyncio import sleep
from Utils.redis_keys import build_key
from Utils.db_tables import tables, table_pk

class EnsureAllTablesExists(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot

  async def ensure_all_tables_exists(self, keys, resolved_keys):
    if not (self.bot.redis and self.bot.db_pool): raise RuntimeError("Database or Redis connection is not established")

    dm = self.bot.get_cog("DataManager")
    while not dm:
      dm = self.bot.get_cog("DataManager")
      await sleep(1)

    for name, table in tables.items():
      if any(key not in keys for key in table_pk[name]):
        continue

      pk = {key: keys[key] for key in table_pk[name]}

      ident = build_key(name, pk)

      if await self.bot.redis.exists(f"db:{ident}"):
        continue

      data = {
        key: resolved_keys[key]
        for key in table
        if key not in pk and key in resolved_keys
      }

      await dm.insert_row(name, pk, data, 300)

def setup(bot: commands.Bot):
  bot.add_cog(EnsureAllTablesExists(bot))