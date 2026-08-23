from nextcord.ext import commands
from datetime import datetime
from aiohttp import web
from traceback import format_exception
from asyncpg import create_pool
from main import time_when_bot_run_firts, bot_started_launch
from helper import restore_feedback_views, JsonFeedbackStore
from Utils.lazylightshow import lazylightshow
from Utils.config import DATABASE_CONFIG

store = JsonFeedbackStore("channel_feedback.json")

bot_started = False

class OnReady(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
    self.bot.db_pool = None

  async def init_database(self):
    return await create_pool(**DATABASE_CONFIG)

  @commands.Cog.listener()
  async def on_ready(self):
    global bot_started
    if bot_started: print(f'🔗\033[38;5;51m{self.bot.user}\033[0m \033[38;5;82mготов снова,\033[0m \033[38;5;226m{datetime.now()}\033[0m');return
    else:
      import Utils.translate_to_all_languages
      номер_перевода = Utils.translate_to_all_languages.номер_перевода
      DISCORD_LANGUAGES = Utils.translate_to_all_languages.DISCORD_LANGUAGES
      print(f"\033[38;5;51m{self.bot.user}\033[0m \033[38;5;82mзакончил запуск в\033[0m \033[38;5;226m{datetime.now()}\033[0m\033[38;5;82m, запуск длился\033[0m \033[38;5;226m{datetime.now()-bot_started_launch}\033[0m")
      bot_started_launch2 = datetime.now()
      print(f"Начало загрузки переменных \033[38;5;51m{self.bot.user}\033[0m")
  
      self.bot.db_pool = await self.init_database()
      db_buffer = self.bot.get_cog("DBBuffer")
      self.bot.db_pool = db_buffer.enable(self.bot.db_pool)
      
      app = web.Application()

      app.router.add_post('/discord', self.bot.get_cog("DiscordWebhook").discord_info)
      app.router.add_get('/.well-known/discord', self.bot.get_cog("VerifyWebsiteForDiscord").discord_verification)

      _ = await restore_feedback_views(self.bot, store)

      try:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8082)
        await site.start()
      except Exception as e:
        print('Произошла ошибка в on_ready при старте сайта\n',''.join(format_exception(type(e), e, e.__traceback__)))

      text = f"Переведено {номер_перевода} текста на {len(DISCORD_LANGUAGES)} языка при запуске бота.\nСо всего было переведено {номер_перевода*len(DISCORD_LANGUAGES)} текста учитывая языки."
      await self.bot.get_guild(807304463449849938).get_channel(807366228670152764).send(f'```ansi\nтокен от: \033[1;34m{self.bot.user}\033[0m\n\nБот Начал Запуск В: {time_when_bot_run_firts}\nБот Закончил Запуск В: {str(datetime.now())}\nБот Запускался: {datetime.now()-time_when_bot_run_firts}```\n```ansi\n{lazylightshow(text)[:1700]}```')
      print(f'\033[38;5;51m{self.bot.user}\033[0m полностью запустился в \033[38;5;226m{datetime.now()}\033[0m, заняло времени: \033[38;5;226m{datetime.now()-bot_started_launch2}\033[0m')
      print(f"В общем запуск длился \033[38;5;226m{datetime.now()-time_when_bot_run_firts}\033[0m")
      print("\033[38;5;240m-" * 50 + "\033[0m")
      bot_started = True

def setup(bot):
  bot.add_cog(OnReady(bot))