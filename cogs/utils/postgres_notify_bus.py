from collections import defaultdict
from nextcord.ext import commands
from asyncio import sleep
from asyncpg import create_pool
from asyncpg.exceptions import ConnectionDoesNotExistError
from Utils.config import LISTEN_DATABASE_CONFIG

class PostgresNotifyBus(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self._handlers: defaultdict[str, list] = defaultdict(list)
    self.pool = None
    self.conn = None
    self.task = bot.loop.create_task(self._run())

  def cog_unload(self):
    self.task.cancel()

  def add_handler(self, channel: str, callback):
    self._handlers[channel].append(callback)
    if self.conn and not self.conn.is_closed():
      self.bot.loop.create_task(self.conn.add_listener(channel, self._dispatch))

  async def _dispatch(self, conn, pid, channel, payload):
    for callback in self._handlers.get(channel, []):
      await callback(conn, pid, channel, payload)

  async def _run(self):
    await self.bot.wait_until_ready()
    while True:
      try:
        self.pool = await create_pool(**LISTEN_DATABASE_CONFIG)
        self.conn = await self.pool.acquire()
        for channel in self._handlers:
          await self.conn.add_listener(channel, self._dispatch)
        while True:
          await sleep(60)
      except ConnectionDoesNotExistError:
        await sleep(5)
      except Exception:
        await sleep(5)
      finally:
        if self.conn and self.pool:
          await self.pool.release(self.conn)
          self.conn = None
        if self.pool:
          await self.pool.close()
          self.pool = None

def setup(bot: commands.Bot):
  bot.add_cog(PostgresNotifyBus(bot))