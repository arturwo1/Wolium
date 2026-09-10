from datetime import datetime

time_when_bot_run_firts = datetime.now()

if __name__=='__main__':
  print(f"Скрипт запустился в \033[38;5;226m{time_when_bot_run_firts}\033[0m")

  from os import path, chdir, walk, sep, getenv
  from nextcord import Intents, AllowedMentions
  from nextcord.ext import commands
  from asyncio import sleep
  from tracemalloc import start as t_start
  from dotenv import load_dotenv
  from logging import basicConfig, WARNING, getLogger, ERROR
  from traceback import format_exception
  from redis.asyncio import Redis
  from helper import JsonFeedbackStore
  from Utils.init_database import init_database
  from Utils.nextcord_identify import apply as apply_nextcord_patch

  apply_nextcord_patch()

  basicConfig(level=WARNING)
  getLogger("nextcord.http").setLevel(ERROR)

  print(f"Библиотеки загрузились в: \033[38;5;226m{datetime.now()}\033[0m, загрузка шла: \033[38;5;226m{datetime.now()-time_when_bot_run_firts}\033[0m")
  t_start()
  load_dotenv()

  script_directory = path.dirname(path.abspath(__file__))
  chdir(script_directory)

  store = JsonFeedbackStore("channel_feedback.json")

  bot = commands.AutoShardedBot(
    command_prefix="_",
    help_command=None,
    intents=Intents.all(),
    owner_id=740543157623848960,
    allowed_mentions=AllowedMentions.none()
  )

  bot.db_pool = None
  bot.redis = None

bot_started_launch = datetime.now()
if __name__ == "__main__":
  print(f"Скрипт закончил запуск в \033[38;5;226m{datetime.now()}\033[0m, скрипт запускался \033[38;5;226m{datetime.now() - time_when_bot_run_firts}\033[0m")

  print(f"Начало запуска бота: \033[38;5;226m{bot_started_launch}\033[0m")

  async def load_cog(cog_path: str):
    start = datetime.now()
    print(f"🔹Загружаем cog: \033[38;5;21m{cog_path}\033[0m в \033[38;5;226m{start}\033[0m{' ' * 50}", end="")

    try:
      bot.load_extension(cog_path)
      print(f"\r🔹\033[38;5;82mCog загружен:\033[0m \033[38;5;21m{cog_path}\033[0m \033[38;5;82mв\033[0m \033[38;5;226m{datetime.now()}\033[0m \033[38;5;82m(заняло\033[0m \033[38;5;226m{datetime.now() - start}\033[0m\033[38;5;82m)\033[0m" + " " * 50)
    except Exception as e:
      print(f"\r🔹\033[38;5;196mCog не загружен:\033[0m \033[38;5;21m{cog_path}\033[0m\n\033[38;5;196mОшибка: {e}\033[0m\n\033[38;5;196mВремя:\033[0m \033[38;5;226m{datetime.now()}\033[0m \033[38;5;196m(заняло\033[0m \033[38;5;226m{datetime.now() - start}\033[0m\033[38;5;196m)\033[0m")

  async def load_cogs():
    for root, _, files in walk("cogs"):
      for file in files:
        if file.endswith(".py") and file not in {"on_connect.py"}:
          await load_cog(f"{root.replace(sep, '.')}.{file[:-3]}")

    await sleep(3)

    await load_cog("cogs.events.on_connect")

  async def main():
    try:
      
      bot.db_pool = await init_database()
      bot.redis = Redis(host=getenv("REDIS_HOST"), port=int(getenv("REDIS_PORT")), decode_responses=True)

      await load_cogs()

      print(f"\033[38;5;82m🔹Все cog'и загружены в\033[0m \033[38;5;226m{datetime.now()}\033[0m \033[38;5;82m(общее время:\033[0m \033[38;5;226m{datetime.now() - bot_started_launch}\033[0m\033[38;5;82m)\033[0m")

      await bot.start(getenv("DISCORD_BOT_TOKEN"))

    except Exception as e:
      e = "".join(format_exception(type(e), e, e.__traceback__))[:5000]
      print(e)

    finally:
      await bot.redis.aclose()

      tracker = bot.get_cog("ActivityTracker")
      if tracker:
        await tracker.flush_all_open_sessions()

  bot.loop.run_until_complete(main())