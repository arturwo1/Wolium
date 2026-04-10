from nextcord.ext import commands
from sys import _current_frames
from traceback import format_stack
from datetime import datetime
from threading import Thread, Event, enumerate as thread_enumerate
from time import time

THRESHOLD = 2.0
INTERVAL = 0.2
COOLDOWN = 10.0

def _frame_key(frame):
  return (frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name)

class Watchdog(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self._stop = Event()
    self._seen: dict[int, tuple] = {}
    self._thread = Thread(target=self._monitor, daemon=True, name="watchdog")
    self._thread.start()

  def cog_unload(self):
    self._stop.set()

  def _is_idle(self, frame) -> bool:
    return "DiscordBot" not in frame.f_code.co_filename

  def _monitor(self):
    while not self._stop.wait(INTERVAL):
      now = time()
      frames = _current_frames()

      for tid in list(self._seen):
        if tid not in frames:
          del self._seen[tid]

      for tid, frame in frames.items():
        if tid == self._thread.ident:
          continue

        if self._is_idle(frame):
          self._seen.pop(tid, None)
          continue

        key = _frame_key(frame)
        prev_key, first_seen, reported_until = self._seen.get(tid, (None, now, 0))

        if key != prev_key:
          self._seen[tid] = (key, now, 0)
          continue

        lag = now - first_seen

        if lag < THRESHOLD or now < reported_until:
          self._seen[tid] = (key, first_seen, reported_until)
          continue

        self._seen[tid] = (key, first_seen, now + COOLDOWN)

        thread_name = next(
          (t.name for t in thread_enumerate() if t.ident == tid),
          f"tid={tid}"
        )
        stack = "".join(format_stack(frame, limit=20))

        print(f"\n\033[38;5;196m⛔ Завис\033[0m \033[38;5;33m{thread_name}\033[0m на \033[38;5;226m{lag:.1f}s\033[0m | {datetime.now()}\n\033[38;5;240m{'─'*50}\033[0m\n\033[38;5;220m{frame.f_code.co_name}\033[0m @ \033[38;5;37m{frame.f_code.co_filename}:{frame.f_lineno}\033[0m\n{stack}\033[38;5;240m{'─'*50}\033[0m\n")

def setup(bot: commands.Bot) -> None:
  bot.add_cog(Watchdog(bot))