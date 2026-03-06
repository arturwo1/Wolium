from nextcord.ext import commands, tasks
from time import perf_counter
from sys import _current_frames
from traceback import format_stack
from datetime import datetime
from threading import main_thread
from asyncio import get_running_loop

threshold = 2.0
interval = 0.2

class Watchdog(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.last = None
    self.cooldown_until = 0
    self.freeze_watcher.start()

  def cog_unload(self):
    self.freeze_watcher.cancel()

  @staticmethod
  def _collect_main_stack(limit: int = 20) -> str:
    frame = _current_frames().get(main_thread().ident)
    if not frame:
      return "Неизвестен виновник\n"
    return "".join(format_stack(frame, limit=limit))

  @tasks.loop(seconds=interval)
  async def freeze_watcher(self):
    loop = get_running_loop()
    now = loop.time()
    lag = (now - self.last) - interval
    self.last = now

    if now < self.cooldown_until or lag < threshold:
      return

    self.cooldown_until = perf_counter() + 10

    print(f"\n\033[38;5;196m⛔ Event Loop завис на\033[0m \033[38;5;226m{lag:.1f}\033[0m \033[38;5;196mсекунд в\033[0m \033[38;5;226m{datetime.now()}\033[0m\n\033[38;5;240m{'-'*50}\033[0m")

    print(self._collect_main_stack(20), end="")

    print(f"\033[38;5;240m{'-'*50}\033[0m\n")

  @freeze_watcher.before_loop
  async def before_freeze_watcher(self):
    await self.bot.wait_until_ready()
    self.last = get_running_loop().time()

def setup(bot: commands.Bot) -> None:
  bot.add_cog(Watchdog(bot))