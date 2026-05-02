from datetime import datetime, timezone
import ctypes

kernel32 = ctypes.windll.kernel32
handle = kernel32.GetStdHandle(-11)

mode = ctypes.c_uint()
if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
  kernel32.SetConsoleMode(handle, mode.value | 0x0004)

time_when_bot_run_firts = datetime.now()
if __name__=='__main__':
  print(f"Скрипт запустился в \033[38;5;226m{time_when_bot_run_firts}\033[0m")

import os
import nextcord
from nextcord.ext import commands
import json
import asyncio
import traceback
import subprocess
import tracemalloc
import asyncpg
from dotenv import load_dotenv
from hashlib import md5
import Utils.config
from nextcord.ext import commands
from aiohttp import web
from traceback import format_exception
from Utils.lazylightshow import lazylightshow
from Utils.config import DATABASE_CONFIG
from helper import restore_feedback_views, JsonFeedbackStore

from cogs.utils.send_embed import SendEmbed

if __name__=='__main__':
  import logging
  import hide_to_tray

  logging.basicConfig(level=logging.WARNING)

  print(f"Библиотеки загрузились в: \033[38;5;226m{datetime.now()}\033[0m, загрузка шла: \033[38;5;226m{datetime.now()-time_when_bot_run_firts}\033[0m")
tracemalloc.start()
load_dotenv()


script_directory = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_directory)

intents = nextcord.Intents.all()
intents.message_content = True
intents.typing = True
intents.presences = True
intents.voice_states = True
intents.all()

bot = commands.AutoShardedBot(
  command_prefix="_",
  help_command=None,
  intents=intents,
  owner_id=740543157623848960,
  shard_ids=[0, 1],
  shard_count=2,
  shard_id=0
)

async def init_database():
  return await asyncpg.create_pool(**DATABASE_CONFIG)

async def handle_PostgreSQL_changes(conn,pid,channel,payload):
  try:
    fields = []

    data = json.loads(payload)
    operation = data['operation']
    table = data['table']
    timestamp = data['timestamp']
    user = data['user']
    query = data['query']

    fields.append({
      'name': 'Информация',
      'value': (
        f"Юзер: **`{user}`**\n"+
        f"Запрос: **```sql\n{query}```**"+
        f"Время: **`{timestamp}`**"
      ),
      'inline': False
    })

    if 'old_data' in data:
      fields.append({
        'name': 'Старые Данные',
        'value': '**```json\n'+str(json.dumps(data['old_data'], indent=2, ensure_ascii=False))+'```**',
        'inline': False
      })
    if 'new_data' in data:
      fields.append({
        'name': 'Новые Данные',
        'value': '**```json\n'+str(json.dumps(data['new_data'], indent=2, ensure_ascii=False))+'```**',
        'inline': True
      })
    if operation=='UPDATE' and data['new_data']!=data['old_data']:
      something = {
        key: {
          'before': data['old_data'][key],
          'after': data['new_data'][key]
        }
        for key in data['old_data']
        if key in data['new_data'] and data['old_data'][key] != data['new_data'][key]
      }

      key_name = ""
      key_value_before = ""
      key_value_after = ""
      diff = ''

      for name, value in something.items():
        key_name += name + '\n'
        value_key_value_before = value.get('before', '')
        value_key_value_after = value.get('after', '')

        key_value_before += f"{name}: {value_key_value_before}\n"
        key_value_after += f"{name}: {value_key_value_after}\n"

        if isinstance(value_key_value_before, (int, float)) and isinstance(value_key_value_after, (int, float)):
          diff += name+': '+str(abs(value_key_value_after - value_key_value_before))+'\n'

      fields.append({
        'name': 'Разница',
        'value': (
          f"Название ключа/ей: **```json\n{key_name.strip()}```**"+
          f"Значение ключа/ей до: **```json\n{key_value_before.strip()}```**"+
          f"Значение ключа/ей после: **```json\n{key_value_after.strip()}```**"+
          (f"Разница: **```json\n{diff}```**" if diff else "")
        ),
        'inline': False
      })
    
    color = {"INSERT": nextcord.Color.green(), "UPDATE": nextcord.Color.gold(), "DELETE": nextcord.Color.red()}.get(operation, nextcord.Color.blurple())

    await (SendEmbed(bot)).send_embed(f'PostgreSQL | Изменение данных({operation})',f'Таблица: `{table}`',color,fields,f'Изменение данных({operation})',f'ДАННЫЕ PostgreSQL',None,807304463449849938,1294702500435198105)
  except Exception as e:
    traceback_msg = str((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
    fields.append({
      'name': 'ERROR',
      'value': '**```py\n'+traceback_msg+'```**',
      'inline': False
    })
    await (SendEmbed(bot)).send_embed(f'PostgreSQL | Изменение данных',f'Произошла ошибка в handle_data_changes PostgreSQL\n\n{e}',nextcord.Color.red(),fields,f'Изменение данных | ОШИБКА',f'ДАННЫЕ PostgreSQL | ОШИБКА',None,807304463449849938,1159138280651104256)

async def handle_ddl_PostgreSQL_changes(conn,pid,channel,payload):
  try:
    fields = []
    data = json.loads(payload)
    event = data['event']
    obj = data['object']
    schema = data['schema']
    timestamp = data['timestamp']
    query = data['query']
    user = data['user']
    fields.append({
      'name': 'Информация',
      'value': (
        f"Время: **`{timestamp}`**\n"+
        f"Схема: **`{schema}`**\n"+
        f"Ивент: **`{event}`**\n"+
        f"Объект: **```sql\n{obj}```**\n"+
        f"Запрос: **```sql\n{query}```**\n"+
        f"Юзер: **`{user}`**"
      ),
      'inline': False
    })

    await (SendEmbed(bot)).send_embed(f'PostgreSQL | Изменение структуры БД({event})',f'Структура БД была изменена:',nextcord.Color.purple(),fields,f'Изменение структуры БД({event})',f'СТРУКТУРА PostgreSQL',None,807304463449849938,1294702500435198105)
  except Exception as e:
    traceback_msg = str((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
    fields.append({
      'name': 'ERROR',
      'value': '**```py\n'+traceback_msg+'```**',
      'inline': False
    })
    await (SendEmbed(bot)).send_embed(f'PostgreSQL | Изменение структуры БД',f'Произошла ошибка в handle_ddl_changes PostgreSQL\n\n{e}',nextcord.Color.red(),fields,f'Изменение структуры БД | ОШИБКА',f'СТРУКТУРА PostgreSQL | ОШИБКА',807304463449849938,1159138280651104256)

async def listen_PostgreSQL_changes():
  while True:
    await bot.wait_until_ready()
    conn = None
    try:
      conn = await (await init_database()).acquire()

      await conn.add_listener("data_changes", handle_PostgreSQL_changes)
      await conn.add_listener("ddl_changes", handle_ddl_PostgreSQL_changes)

      while True:
        await asyncio.sleep(60)
      
    except asyncpg.exceptions.ConnectionDoesNotExistError as e:
      print(f"🔴 Потеряно соединение с PostgreSQL: {e}. Переподключение через 5 секунд...")
      await asyncio.sleep(5)

    except Exception as e:
      traceback_msg = str((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      fields = []
      fields.append({
        'name': 'ERROR',
        'value': '**```py\n'+traceback_msg+'```**',
        'inline': False
      })
      await (SendEmbed(bot)).send_embed(
        "PostgreSQL | Ошибка Прослушивания БД",
        f"Произошла ошибка: {e}",
        nextcord.Color.red(),
        fields,
        "Прослушивание БД | ОШИБКА",
        "ПРОСЛУШИВАНИЕ PostgreSQL | ОШИБКА",
        807304463449849938,
        1159138280651104256
      )

    except asyncio.CancelledError:
      print("⏹️  Остановка слушателя PostgreSQL...")

    finally:
      if conn:
        await conn.remove_listener("data_changes", handle_PostgreSQL_changes)
        await conn.remove_listener("ddl_changes", handle_ddl_PostgreSQL_changes)
        await conn.close()
        print("🔌 Соединение закрыто")

async def cleanup_PostgreSQL_backups():
  files = sorted(
    [f for f in os.listdir(f"{script_directory}/PostgreSQL_Backups") if f.endswith('.dump')], reverse=True
  )
  for old_file in files[5:]:
    os.remove(f"{script_directory}/PostgreSQL_Backups/{old_file}")

def get_file_hash(file_path):
  if not os.path.exists(file_path):
    return None
  hash_func = md5()
  with open(file_path, "rb") as f:
    while chunk := f.read(8192):
      hash_func.update(chunk)
  return hash_func.hexdigest()

async def PostgreSQL_backup_data():
  os.environ['PGPASSWORD'] = os.getenv("POSTGRESQL_ADMIN_PASSWORD")
  while True:
    timestamp=datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    backup_file = f"{script_directory}/PostgreSQL_Backups/PostgreSQLBD_{timestamp}.dump"
    
    previous_backups = sorted(
      [f for f in os.listdir(f"{script_directory}/PostgreSQL_Backups") if f.endswith(".dump")],
      key=lambda x: os.path.getmtime(os.path.join(f"{script_directory}/PostgreSQL_Backups", x)),
      reverse=True
    )
    last_backup = os.path.join(f"{script_directory}/PostgreSQL_Backups", previous_backups[0]) if previous_backups else None

    last_size = os.path.getsize(last_backup) if (os.path.exists(last_backup) if last_backup else None) and last_backup else 0 if last_backup else 0
    last_hash = get_file_hash(last_backup) if last_backup else None
    
    result = subprocess.run(
      ['pg_dump', '-U', 'postgres', '-d', 'postgres', '-F', 'c', '-f', backup_file],
      capture_output=True, text=True
    )

    if result.returncode==0:
      while True:
        try:
          new_size = os.path.getsize(backup_file)
          new_hash = get_file_hash(backup_file)
          if last_backup and (new_size == last_size or new_hash == last_hash or abs((new_size)-(last_size))<=262144):
            os.remove(backup_file)
          else:
            log = nextcord.Embed(
              title=f"PostgreSQL | Успешный бекап БД",
              description=f"## Успешно произвезден бекап БД.",
              color=nextcord.Colour.green(),
              timestamp=datetime.now(timezone.utc)
            )
            log.set_author(
              name=f"УСПЕХ",
            )
            if last_backup:
              log.add_field(
                name="Старый Бекап",
                value=f"Путь: **`{last_backup}`**\nНазвание: **`{os.path.basename(last_backup)}`**\nВес: **`{round(last_size/1024, 2)}КБ`** ***(*`{last_size}Байт`*)***\nMD5 хеш-код: **`{last_hash}`**",
                inline=False
              )
            log.add_field(
              name="Новый Бекап",
              value=f"Путь: **`{backup_file}`**\nНазвание: **`PostgreSQLBD_{timestamp}.dump`**\nВес: **`{round(new_size/1024, 2)}КБ`** ***(*`{new_size}Байт`*)***\nMD5 хеш-код: **`{new_hash}`**",
              inline=False
            )
            log.set_footer(
              text=f"Бекап PostgreSQL БД",
              icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
            )
            await bot.get_guild(807304463449849938).get_channel(1294702500435198105).send(embed=log)
            await cleanup_PostgreSQL_backups()
            Utils.config.PGSQL_times_updated += 1
          break
        except PermissionError:
          pass
    else:
      log = nextcord.Embed(
        title=f"PostgreSQL | Ошибка При Бекапе",
        description=f"## Произошла ошибка при попытке бекапнуть БД.",
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.set_author(
        name=f"ЕРРОР",
      )
      for i in range(0, len(result.stderr), 1000):
        log.add_field(
          name="Ошибка",
          value=f"```py\n{result.stderr[i:i+1000]}```",
          inline=False
        )
      log.set_footer(
        text=f"Бекап PostgreSQL БД",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      await bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
    
    await asyncio.sleep(5*60*60)

store = JsonFeedbackStore("channel_feedback.json")

bot_started = False
bot.db_pool = None
@bot.event
async def on_ready():
  global bot_started
  if bot_started: print(f'🔗\033[38;5;51m{bot.user}\033[0m \033[38;5;82mготов снова,\033[0m \033[38;5;226m{datetime.now()}\033[0m');return
  else:
    import Utils.translate_to_all_languages
    номер_перевода = Utils.translate_to_all_languages.номер_перевода
    DISCORD_LANGUAGES = Utils.translate_to_all_languages.DISCORD_LANGUAGES
    номер_перевода_символы = Utils.translate_to_all_languages.номер_перевода_символы
    print(f"\033[38;5;51m{bot.user}\033[0m \033[38;5;82mзакончил запуск в\033[0m \033[38;5;226m{datetime.now()}\033[0m\033[38;5;82m, запуск длился\033[0m \033[38;5;226m{datetime.now()-bot_started_launch}\033[0m")
    bot_started_launch2 = datetime.now()
    print(f"Начало загрузки переменных \033[38;5;51m{bot.user}\033[0m")
 
    bot.db_pool = await init_database()
    app = web.Application()

    app.router.add_post('/discord', bot.get_cog("DiscordWebhook").discord_info)
    app.router.add_get('/.well-known/discord', bot.get_cog("VerifyWebsiteForDiscord").discord_verification)

    _ = await restore_feedback_views(bot, store)

    try:
      runner = web.AppRunner(app)
      await runner.setup()
      site = web.TCPSite(runner, "0.0.0.0", 8082)
      await site.start()
    except Exception as e:
      print('Произошла ошибка в on_ready при старте сайта\n',''.join(format_exception(type(e), e, e.__traceback__)))

    text = f"Переведено {номер_перевода}({номер_перевода_символы} символов) текста на {len(DISCORD_LANGUAGES)} языка при запуске бота.\nСо всего было переведено {номер_перевода*len(DISCORD_LANGUAGES)} текста учитывая языки."
    await bot.get_guild(807304463449849938).get_channel(807366228670152764).send(f'```ansi\nтокен от: \033[1;34m{bot.user}\033[0m\n\nБот Начал Запуск В: {time_when_bot_run_firts}\nБот Закончил Запуск В: {str(datetime.now())}\nБот Запускался: {datetime.now()-time_when_bot_run_firts}```\n```ansi\n{lazylightshow(text)[:1700]}```')
    print(f'\033[38;5;51m{bot.user}\033[0m полностью запустился в \033[38;5;226m{datetime.now()}\033[0m, заняло времени: \033[38;5;226m{datetime.now()-bot_started_launch2}\033[0m')
    print(f"В общем запуск длился \033[38;5;226m{datetime.now()-time_when_bot_run_firts}\033[0m")
    print("\033[38;5;240m-" * 50 + "\033[0m")
    bot_started = True

if __name__=='__main__':
  print(f"Скрипт закончил запуск в \033[38;5;226m{datetime.now()}\033[0m, Скрипт запускался \033[38;5;226m{datetime.now()-time_when_bot_run_firts}\033[0m")
  bot_started_launch = datetime.now()
  print(f"Начало запуска бота: \033[38;5;226m{bot_started_launch}\033[0m")
  async def load_cogs():
    for root, _, files in os.walk("cogs"):
      for file in files:
        if file.endswith(".py"):
          cog_path = f"{root.replace(os.sep, '.')}.{file[:-3]}"
          a = datetime.now()
          print(f"🔹Загружаем cog: \033[38;5;21m{cog_path}\033[0m в \033[38;5;226m{datetime.now()}\033[0m"+" "*50, end="")
          try:
            bot.load_extension(cog_path)
            print(f"\r🔹\033[38;5;82mCog загружен:\033[0m \033[38;5;21m{cog_path}\033[0m \033[38;5;82mв\033[0m \033[38;5;226m{datetime.now()}\033[0m\033[38;5;82m, загрузка длилась\033[0m \033[38;5;226m{datetime.now()-a}\033[0m"+" "*50)
          except Exception as e:
            print(f"\r🔹\033[38;5;196mCog\033[0m \033[38;5;21m{cog_path}\033[0m \033[38;5;196mне загружен, ошибка: {e}\033[0m. \033[38;5;226m{datetime.now()}\033[0m\033[38;5;196m, загрузка длилась\033[0m \033[38;5;226m{datetime.now()-a}\033[0m"+" "*50)

  async def main_code():
    await load_cogs()
    print(f"\033[38;5;82m🔹Все cog'и загружены и запущены в\033[0m \033[38;5;226m{datetime.now()}\033[0m\033[38;5;82m, загрузка длилась\033[0m \033[38;5;226m{datetime.now()-bot_started_launch}\033[0m")
    try:
      await bot.start(os.getenv("DISCORD_BOT_TOKEN"))
    finally:
      tracker = bot.get_cog("ActivityTracker")
      if tracker:
        await tracker.flush_all_open_sessions()

  bot.loop.run_until_complete(main_code())