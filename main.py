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
import random
import nextcord
from nextcord.ext import commands
from nextcord import SlashOption, IntegrationType, InteractionContextType
import json
import asyncio
import sympy
import re
from sympy.parsing.sympy_parser import (parse_expr, standard_transformations, implicit_multiplication_application)
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

# POSTGRESQL
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


    restored = await restore_feedback_views(bot, store)

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

if __name__=='__main__i':
# pyright: reportUndefinedVariable=false


  # try:
  #   @bot.slash_command(
  #     description="Отправить Полный Эмбед. Стоимость €250.",
  #     name_localizations=translate_to_all_languages('Embed', 'name'),
  #     description_localizations=translate_to_all_languages('Send Full Embed. cost €250.', 'description'),
  #     integration_types=[
  #           IntegrationType.user_install,
  #           IntegrationType.guild_install,
  #       ],
  #     contexts=[
  #           InteractionContextType.guild,
  #           InteractionContextType.bot_dm,
  #           InteractionContextType.private_channel,
  #     ],)
  #   async def эмбед(
  #     interaction: nextcord.Interaction,
      
  #     эмбед_заголовок: str=SlashOption(name="эмбед_заголовок", description="Надпись В Заголовке Эмбеда.",max_length=2000,required=True, name_localizations=translate_to_all_languages('embed header', 'name'), description_localizations=translate_to_all_languages('Embed Headline Inscription.', 'description')),
  #     эмбед_описание: str=SlashOption(name="эмбед_описание", description="Надпись В Описании Эмбеда.",max_length=2000,required=True, name_localizations=translate_to_all_languages('embed description', 'name'), description_localizations=translate_to_all_languages('The inscription in the Description of Embed.', 'description')),
      
  #     автор: bool=SlashOption(name="автор", description="True - Автор В Эмбеде Будет, False - Не Будет.",required=False, name_localizations=translate_to_all_languages('author', 'name'), description_localizations=translate_to_all_languages('True - There will be an author in Embed, False - There will not.', 'description'),default=False),
      
  #     миниатюра: bool=SlashOption(name="миниатюра", description="True - Миниатюра В Эмбеде Будет, False - Не Будет.",required=False, name_localizations=translate_to_all_languages('miniature', 'name'), description_localizations=translate_to_all_languages('True - There will be a Miniature in Embed, False - There will not.', 'description'),default=False),
      
  #     поле1: bool=SlashOption(name="поле1", description="True - Первое Поле В Эмбеде Будет, False - Не Будет.",required=False, name_localizations=translate_to_all_languages('field one', 'name'), description_localizations=translate_to_all_languages('True - The first field in the Embed will be, False - It will not.', 'description'),default=False),
  #     поле1_вывод_строки: bool=SlashOption(name="поле1_вывод_строки", description="True - Вывода Строки Не Будет, False - Будет.",required=False, name_localizations=translate_to_all_languages('field one line output', 'name'), description_localizations=translate_to_all_languages('True - String will not be output, False - will be output.', 'description'),default=False),
      
  #     поле2_вывод_строки: bool=SlashOption(name="поле2_вывод_строки", description="True - Вывода Строки Не Будет, False - Будет.",required=False, name_localizations=translate_to_all_languages('second field line output', 'name'), description_localizations=translate_to_all_languages('True - String will not be output, False - will be output.', 'description'),default=False),
      
  #     футер: bool=SlashOption(name="футер", description="True - Футер Будет, False - Не Будет.",required=False, name_localizations=translate_to_all_languages('footer', 'name'), description_localizations=translate_to_all_languages('True - It will, False - It won\'t.', 'description'),default=False),

  #     эмбед_изображение: bool=SlashOption(name="эмбед_изображение", description="True - Изображение В Эмбеде Будет, False - Не Будет.",required=False, name_localizations=translate_to_all_languages('embed image bool', 'name'), description_localizations=translate_to_all_languages('True - There will be an image in Embed, False - There will not.', 'description'),default=False),

  #     поле2: bool=SlashOption(name="поле2", description="True - Второе Поле В Эмбеде Будет, False - Не Будет.",required=False, name_localizations=translate_to_all_languages('field two', 'name'), description_localizations=translate_to_all_languages('True - There will be a second field in Embed, False - There will not.', 'description'),default=False),

  #     эмбед_r: int=SlashOption(name="эмбед_r", description="Номер Красного Цвета Сбоку От Эмбеда До 255.",required=False, name_localizations=translate_to_all_languages('embed Red', 'name'), description_localizations=translate_to_all_languages('Red Color Side Number From Embed to 255.', 'description')),
  #     эмбед_g: int=SlashOption(name="эмбед_g", description="Номер Зеленого Цвета Сбоку От Эмбеда До 255.",required=False, name_localizations=translate_to_all_languages('embed Green', 'name'), description_localizations=translate_to_all_languages('The green-colored number on the side of Embed to 255.', 'description')),
  #     эмбед_b: int=SlashOption(name="эмбед_b", description="Номер Синего Цвета Сбоку От Эмбеда До 255.",required=False, name_localizations=translate_to_all_languages('embed Blue', 'name'), description_localizations=translate_to_all_languages('Blue-colored number on the side from Embed to 255.', 'description')),
  #     эмбед_ссылка: str=SlashOption(name="эмбед_ссылка", description="Ссылка на Заголовок Эмбеда, Начало с `https`.",max_length=2000,required=False, name_localizations=translate_to_all_languages('URL to embed HERE', 'name'), description_localizations=translate_to_all_languages('Link to Embed Header, Beginning with `https`.', 'description')),

  #     автор_имя: str=SlashOption(name="автор_имя", description="Имя Автора.",max_length=2000,required=False, name_localizations=translate_to_all_languages('name of the author', 'name'), description_localizations=translate_to_all_languages('Author\'s Name', 'description')),
  #     автор_ссылка_иконка: str=SlashOption(name="автор_ссылка_иконка", description="Иконка Автора, Начало с `https`.",required=False, name_localizations=translate_to_all_languages('author url to icon', 'name'), description_localizations=translate_to_all_languages('Author icon, Start with `https`.', 'description')),
  #     автор_ссылка: str=SlashOption(name="автор_ссылка", description="Ссылка На Автора.",required=False, name_localizations=translate_to_all_languages('link to author', 'name'), description_localizations=translate_to_all_languages('Author Link.', 'description')),

  #     миниатюра_ссылка: str=SlashOption(name="миниатюра_ссылка", description="Ссылка На Миниатюру.",required=False, name_localizations=translate_to_all_languages('miniature link', 'name'), description_localizations=translate_to_all_languages('Link to Miniature.', 'description')),

  #     поле1_имя: str=SlashOption(name="поле1_имя", description="Имя Первого Поля.",max_length=2000,required=False, name_localizations=translate_to_all_languages('field FIRST name', 'name'), description_localizations=translate_to_all_languages('First Field\'s name.', 'description')),
  #     поле1_значение: str=SlashOption(name="поле1_значение", description="Текст/Значение Первого Поля.",max_length=2000,required=False, name_localizations=translate_to_all_languages('field FIRST value', 'name'), description_localizations=translate_to_all_languages('Text/Value of the First Field.', 'description')),

  #     поле2_имя: str=SlashOption(name="поле2_имя", description="Имя Второго Поля.",max_length=2000,required=False, name_localizations=translate_to_all_languages('second name field', 'name'), description_localizations=translate_to_all_languages('Field Two\'s name.', 'description')),
  #     поле2_значение: str=SlashOption(name="поле2_значение", description="Текст/Значение Второго Поля.",max_length=2000,required=False, name_localizations=translate_to_all_languages('SECOND field value', 'name'), description_localizations=translate_to_all_languages('Text/Value of the Second Field.', 'description')),

  #     эмбед_ссылка_изображение: str=SlashOption(name="эмбед_ссылка_изображение", description="Изображение Эмбеда, Начало с `https`.",required=False, name_localizations=translate_to_all_languages('embed image URL', 'name'), description_localizations=translate_to_all_languages('Image by Embed, Started from `https`.', 'description')),

  #     футер_текст: str=SlashOption(name="футер_текст", description="Текст В Футере.",max_length=2000,required=False, name_localizations=translate_to_all_languages('footer text', 'name'), description_localizations=translate_to_all_languages('Text in the Footer.', 'description')),
  #     футер_ссылка_иконка: str=SlashOption(name="футер_ссылка_иконка", description="Иконка Футера, Начало с `https`.",required=False, name_localizations=translate_to_all_languages('footer link icon', 'name'), description_localizations=translate_to_all_languages('Footer Icon, Starting with `https`.', 'description')),
  #   ):
  #     try:
  #       if ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
  #         await interaction.response.send_message(await translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
  #         return
  #       global slash_command_cooldown
  #       user_id = interaction.user.id
  #       current_time = time.time()

  #       if user_id in slash_command_cooldown:
  #         last_command_time = slash_command_cooldown[user_id]['time']
  #         if current_time - last_command_time < 60:
  #           await interaction.response.send_message(await translate_message(f"You write commands so fast, <t:{round(last_command_time+60)}:R> you can write commands.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
  #           return
  #         else:
  #           slash_command_cooldown[user_id]['time'] = current_time
  #       else:
  #         slash_command_cooldown[user_id] = {'time': current_time}
        
  #       guild_settings = await get_data(interaction.guild.id,['banned'],'guilds','guild_id',interaction.guild)
  #       user_settings = await get_data(user_id,['language','variation','banned'],'users','user_id',interaction.guild)
  #       language = user_settings['language']

  #       if user_settings['banned'] or guild_settings['banned']:
  #         await interaction.response.send_message(await translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",language), ephemeral=True)
  #         servers_with_no_acces_for_bot.append(interaction.guild.id)
  #         users_with_no_acces_for_bot.append(user_id)
  #         return
        
  #       user_data = await get_data(user_id,['bank_balance','balance'],'user_data','user_id',interaction.guild)
        
  #       bank_balance = user_data['bank_balance']
  #       balance = user_data['balance']
  #       variation = user_settings['variation']

  #       mod_guild = bot.get_guild(807304463449849938)
  #       mod_chan = mod_guild.get_channel(1149318436615364618)

  #       if bank_balance<=250 or balance<=250:
  #         await interaction.response.send_message(translate_to_all_languages(f"Вам Не Хватает Налички/Банк Валюты Чтоб Отправить Сообщения От Имени Бота!\nСтоимость: `€{round(250,2)}`)", 'message', language), ephemeral=True)
  #         return
        
  #       embed = nextcord.Embed(
  #           title=f"{эмбед_заголовок}",
  #           description=f"{эмбед_описание}",
  #           color=(nextcord.Color.from_rgb(эмбед_r or 0, эмбед_g or 0, эмбед_b or 0) if эмбед_r!=None and эмбед_g!=None and эмбед_b!=None else None),
  #           timestamp=datetime.now(timezone.utc)
  #       )

  #       if bank_balance>250:
  #         sbank_balance = await suffics(number=bank_balance-50, variation=variation)
  #         embed_message = await interaction.response.send_message(await translate_message(f"Вложение успешно отправлено.\nС Вашего Счета В Банке Снято `€50`. У Вас Осталось: `€{sbank_balance}`",language), ephemeral=True)
  #         data = {
  #           'bank_balance': bank_balance-250
  #         }
  #         await update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
  #       else:
  #         sbalance = await suffics(number=balance-50, variation=variation)
  #         embed_message = await interaction.response.send_message(await translate_message(f"Вложение успешно отправлено.\nС Вас Снято `€50`. У Вас Осталось: `€{sbalance}`",language), ephemeral=True)
  #         data = {
  #           'balance': balance-250
  #         }
        
  #       if эмбед_ссылка:
  #         embed.url = эмбед_ссылка
        
  #       if автор:
  #         if автор_имя:
  #           embed.set_author(
  #             name=f"{автор_имя}",
  #             icon_url=автор_ссылка_иконка,
  #             url=автор_ссылка,
  #           )
        
  #       if миниатюра and миниатюра_ссылка:
  #         embed.set_thumbnail(url=миниатюра_ссылка)

  #       if поле1 and поле1_имя and поле1_значение:
  #         embed.add_field(
  #           name=поле1_имя,
  #           value=поле1_значение,
  #           inline=поле1_вывод_строки
  #         )

  #       if поле2 and поле2_имя and поле2_значение:
  #         embed.add_field(
  #           name=поле2_имя,
  #           value=поле2_значение,
  #           inline=поле2_вывод_строки
  #         )

  #       if эмбед_изображение and эмбед_ссылка_изображение:
  #         embed.set_image(url=эмбед_ссылка_изображение)

  #       if футер and футер_текст:
  #         embed.set_footer(
  #           text=футер_текст,
  #           icon_url=футер_ссылка_иконка
  #         )
  #       try:
  #         await interaction.channel.send(embed=embed)
  #       except nextcord.errors.Forbidden:
  #         await embed_message.edit(embed=embed)
  #     except Exception as e:
  #       traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
  #       log = nextcord.Embed(
  #         title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
  #         description=f"Пользователь Скорее Всего вписал: ||**/эмбед** `эмбед_заголовок`  **{эмбед_заголовок}** `эмбед_описание`  **{эмбед_описание}** `эмбед_r`  **{эмбед_r}** `эмбед_g`  **{эмбед_g}** `эмбед_b` **{эмбед_b}** `эмбед_ссылка`  **{эмбед_ссылка}** `автор`  **{автор}** `автор_имя`  **{автор_имя}** `автор_ссылка_иконка`  **{автор_ссылка_иконка}** `автор_ссылка`  **{автор_ссылка}** `миниатюра` **{миниатюра}** `миниатюра_ссылка`  **{миниатюра_ссылка}** `поле1`  **{поле1}** `поле1_имя`  **{поле1_имя}** `поле1_значение`  **{поле1_значение}** `поле1_вывод_строки`  **{поле1_вывод_строки}** `поле2` **{поле2}** `поле2_имя`  **{поле2_имя}** `поле2_значение`  **{поле2_значение}** `поле2_вывод_строки`  **{поле2_вывод_строки}** `эмбед_изображение`  **{эмбед_изображение}** `эмбед_ссылка_изображение`  **{эмбед_ссылка_изображение}** `футер` **{футер}** `футер_текст`  **{футер_текст}** `футер_ссылка_иконка`  **{футер_ссылка_иконка}**||",
  #         color=nextcord.Colour.red(),
  #         timestamp=datetime.now(timezone.utc)
  #       )
  #       log.set_author(
  #         name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
  #         icon_url=f"{interaction.user.display_avatar.url}"
  #       )
  #       log.add_field(
  #         name="Сервер",
  #         value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
  #         inline=False
  #       )
  #       log.add_field(
  #         name="Канал",
  #         value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
  #         inline=False
  #       )
  #       for i in range(0, len(traceback_msg), 1000):
  #         log.add_field(
  #           name="Ошибка",
  #           value=f"```py\n{traceback_msg[i:i+1000]}```",
  #           inline=False
  #         )
  #       log.set_footer(
  #         text=f"{str(datetime.now())}",
  #         icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
  #       )
  #       await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
  #       await bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
  # except nextcord.errors.HTTPException as a:
  #   traceback_msg = ''.join(traceback.format_exception(type(a), a, a.__traceback__))
  #   print(f"произошла ошибка при регистрации команды /эмбед, {a}\n\n{traceback_msg}")



  @bot.slash_command(
    description="Магазин Предметов",
    name_localizations=translate_to_all_languages('магазин', 'name'),
    description_localizations=translate_to_all_languages('Магазин Предметов.', 'description'),
    integration_types=[
          IntegrationType.user_install,
          IntegrationType.guild_install,
      ],
    contexts=[
          InteractionContextType.guild,
          InteractionContextType.bot_dm,
          InteractionContextType.private_channel,
    ],)
  async def магазин(
    interaction: nextcord.Interaction,
    роль: nextcord.Role=SlashOption(name="роль", description="Название Роли Которую Хотите Купить(Смотреть В Магазине).",required=False, name_localizations=translate_to_all_languages('роль', 'name'), description_localizations=translate_to_all_languages('Название Роли Которую Хотите Купить(Смотреть В Магазине).', 'description')),
    предмет: str=SlashOption(name="предмет", description="Название Предмета Который Хотите Купить(Смотреть В Магазине).",required=False, name_localizations=translate_to_all_languages('предмет', 'name'), description_localizations=translate_to_all_languages('Название Предмета Который Хотите Купить(Смотреть В Магазине).', 'description')),
    буст: bool=SlashOption(name="буст", description="Если True И У Вас Достаточно Бустов То Получите Скидку Больше, Если False/None - Обычную.",required=False, name_localizations=translate_to_all_languages('boost', 'name'), description_localizations=translate_to_all_languages('If True and you have enough Boosts you will get a bigger discount, else you will get a normal.', 'description')),
  ):
    
    try:
      if not ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
        
        user_id = interaction.user.id
      
        try:
            with open('economy_data.json', 'r', encoding='utf-8') as f:
                economy_data = json.load(f)
        except FileNotFoundError:
            economy_data = {}


        mod_guild = bot.get_guild(807304463449849938)
        mod_chan = mod_guild.get_channel(1149318288908750960)

        matching_key = next((key for key in economy_data if key.startswith(str(user_id) + '_')), None)
        if matching_key:
          user_data = economy_data[matching_key]
          if user_data.get('bank_balance') is not None:
            bank_balance = user_data.get('bank_balance', 0)
          else:
            economy_data[matching_key]['bank_balance'] = 0
          if user_data.get('balance') is not None:
            balance = user_data.get('balance', 0)
          else:
            economy_data[matching_key]['balance'] = 0
          if user_data.get('upgrade') is not None:
            upgrade = user_data.get('upgrade', 1)
          else:
            economy_data[matching_key]['upgrade'] = 1
          if user_data.get('x2workamount') is not None:
            x2workamount = user_data.get('x2workamount', 0)
          else:
            economy_data[matching_key]['x2workamount'] = 0
          if user_data.get('x2buyamount') is not None:
            x2buyamount = user_data.get('x2buyamount', 0)
          else:
            economy_data[matching_key]['x2buyamount'] = 0
          if user_data.get('bank_balance') is not None and user_data.get('balance') is not None:
            total_balance = bank_balance + balance
          else:
            economy_data[matching_key]['bank_balance'] = 0
            economy_data[matching_key]['balance'] = 0
          if user_data.get('variation', "None"):
            variation = user_data.get('variation', "None")
          else:
            economy_data[matching_key]['variation'] = "None"
          if user_data.get('language') is not None:
            language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
          else:
            economy_data[matching_key]['language'] = interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' 
          with open('economy_data.json', 'w', encoding='utf-8') as f:
            json.dump(economy_data, f, ensure_ascii=False, indent=4)
          bank_balance = user_data.get('bank_balance', 0)
          balance = user_data.get('balance', 0)
          upgrade = user_data.get('upgrade', 1)
          x2workamount = user_data.get('x2workamount', 0)
          x2buyamount = user_data.get('x2buyamount', 0)
          total_balance = bank_balance + balance
          variation = user_data.get('variation', "None")
          language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
        else:
          await interaction.response.send_message(translate_to_all_languages(f"Напишите Команду `/профиль` Что-Бы Зарегестрировать Свой Аккаунт В Базе Данных Экономики.", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
          return

        boost=None
        upgrade_cost = 540*upgrade

        if буст is True:
          if x2buyamount>0:
            if роль is not None or предмет is not None:
              if bank_balance >= x2buyamountPrice:
                boost=False
                economy_data[matching_key]['x2buyamount'] = x2buyamount-1
                x2buyamount = x2buyamount-1
                upgrade_cost=upgrade_cost/2
            else:
              boost=True
              upgrade_cost=upgrade_cost
          else:
            boost=True
            upgrade_cost=upgrade_cost
        else:
          if буст is False:
            boost=False
            upgrade_cost=upgrade_cost
          else:
            boost=False
            upgrade_cost=upgrade_cost

        matching_key = next((key for key in economy_data if key.startswith(str(user_id) + '_')), None)
        if matching_key:
          user_data = economy_data[matching_key]
          user_data = economy_data[matching_key]
          economy_data[matching_key]['bank_balance'] = bank_balance
          economy_data[matching_key]['balance'] = balance
          economy_data[matching_key]['total_balance'] = balance+bank_balance
          economy_data[matching_key]['upgrade'] = upgrade
          economy_data[matching_key]['x2buyamount'] = x2buyamount
          economy_data[matching_key]['x2workamount'] = x2workamount
          economy_data[matching_key]['variation'] = variation
          bank_balance = bank_balance
          balance = balance
          total_balance = bank_balance+balance
          upgrade = upgrade
          x2buyamount = x2buyamount
          x2workamount = x2workamount
          variation = variation
        else:
          await interaction.response.send_message(translate_to_all_languages(f"Напишите Команду `/профиль` Что-Бы Зарегестрировать Свой Аккаунт В Базе Данных Экономики.", 'message', language), ephemeral=True)

        now = datetime.today()
        holiday = await holiday_type_choose("current_holiday", holidays)
        if now.weekday() in [5,6] and not holiday:
          upgrade_cost = upgrade_cost/2
          if буст is True:
            if x2buyamount>0:
              description = translate_to_all_languages(f"Сб-Вс Скидки Активированы! И Ещё Ваш ***Буст*** Тоже! Ваша Скидка: `x{2*1*2}`.", 'message', language)
            else:
              description = translate_to_all_languages(f"Сб-Вс Скидки Активированы! Ваша Скидка: **`x{2*1*1}`**.", 'message', language)
          else:
            if буст is False:
              description = translate_to_all_languages(f"Сб-Вс Скидки Активированы! Ваша Скидка: **`x{2*1*1}`**.", 'message', language)
            else:
              description = translate_to_all_languages(f"Сб-Вс Скидки Активированы! Ваша Скидка: **`x{2*1*1}`**.", 'message', language)
        elif now.weekday() not in [5,6] and not holiday:
          if буст is True:
            if x2buyamount>0:
              description = translate_to_all_languages(f"Сб-Вс Скидки Не Активированы! Но Зато Ваш ***Буст*** Активирован! Ваша Скидка: `x{1*1*2}`.", 'message', language)
            else:
              description = translate_to_all_languages(f"Сб-Вс Скидки Не Активированы! Ваша Скидка: **`x{1*1*1}`**.", 'message', language)
          else:
            if буст is False:
              description = translate_to_all_languages(f"Сб-Вс Скидки Не Активированы! Ваша Скидка: **`x{1*1*1}`**.", 'message', language)
            else:
              description = translate_to_all_languages(f"Сб-Вс Скидки Не Активированы! Ваша Скидка: **`x{1*1*1}`**.", 'message', language)
        elif now.weekday() not in [5,6] and holiday:
          upgrade_cost = upgrade_cost/2
          if буст is True:
            if x2buyamount>0:
              description = translate_to_all_languages(f"Сб-Вс Скидки Не Активированы! Но Зато Ваш ***Буст*** Активирован, А Также Щас Идет Праздник `{holiday['name']}`, Который Начался В `{holiday['start_date'].strftime('%d.%m.%Y')}` И Закончится В `{holiday['end_date'].strftime('%d.%m.%Y')}`(Длительность: *`{holiday['duration']} дней`*)! Ваша Скидка: `x{1*2*2}`.", 'message', language)
            else:
              description = translate_to_all_languages(f"Сб-Вс Скидки Не Активированы, Но Зато Щас Идет Праздник `{holiday['name']}`, Который Начался В `{holiday['start_date'].strftime('%d.%m.%Y')}` И Закончится В `{holiday['end_date'].strftime('%d.%m.%Y')}`(Длительность: *`{holiday['duration']} дней`*)! Ваша Скидка: **`x{1*2*1}`**.", 'message', language)
          else:
            if буст is False:
              description = translate_to_all_languages(f"Сб-Вс Скидки Не Активированы, Но Зато Щас Идет Праздник `{holiday['name']}`, Который Начался В `{holiday['start_date'].strftime('%d.%m.%Y')}` И Закончится В `{holiday['end_date'].strftime('%d.%m.%Y')}`(Длительность: *`{holiday['duration']} дней`*)! Ваша Скидка: **`x{1*2*1}`**.", 'message', language)
            else:
              description = translate_to_all_languages(f"Сб-Вс Скидки Не Активированы, Но Зато Щас Идет Праздник `{holiday['name']}`, Который Начался В `{holiday['start_date'].strftime('%d.%m.%Y')}` И Закончится В `{holiday['end_date'].strftime('%d.%m.%Y')}`(Длительность: *`{holiday['duration']} дней`*)! Ваша Скидка: **`x{1*2*1}`**.", 'message', language)
        elif now.weekday() in [5,6] and holiday:
          upgrade_cost = upgrade_cost/(2*2)
          if буст is True:
            if x2buyamount>0:
              description = translate_to_all_languages(f"Сб-Вс Скидки Активированы! И Ещё Ваш ***Буст*** Тоже! А Также Щас Идет Праздник `{holiday['name']}`, Который Начался В `{holiday['start_date'].strftime('%d.%m.%Y')}` И Закончится В `{holiday['end_date'].strftime('%d.%m.%Y')}`(Длительность: *`{holiday['duration']} дней`*)! Вам Очень СИЛЬНО ПОВЕЗЛО! Ваша Скидка: `x{2*2*2}`.", 'message', language)
            else:
              description = translate_to_all_languages(f"Сб-Вс Скидки Активированы! А Также Щас Идет Праздник `{holiday['name']}`, Который Начался В `{holiday['start_date'].strftime('%d.%m.%Y')}` И Закончится В `{holiday['end_date'].strftime('%d.%m.%Y')}`(Длительность: *`{holiday['duration']} дней`*)! Ваша Скидка: **`x{2*2*1}`**.", 'message', language)
          else:
            if буст is False:
              description = translate_to_all_languages(f"Сб-Вс Скидки Активированы! А Также Щас Идет Праздник `{holiday['name']}`, Который Начался В `{holiday['start_date'].strftime('%d.%m.%Y')}` И Закончится В `{holiday['end_date'].strftime('%d.%m.%Y')}`(Длительность: *`{holiday['duration']} дней`*)! Ваша Скидка: **`x{2*2*1}`**.", 'message', language)
            else:
              description = translate_to_all_languages(f"Сб-Вс Скидки Активированы! А Также Щас Идет Праздник `{holiday['name']}`, Который Начался В `{holiday['start_date'].strftime('%d.%m.%Y')}` И Закончится В `{holiday['end_date'].strftime('%d.%m.%Y')}`(Длительность: *`{holiday['duration']} дней`*)! Ваша Скидка: **`x{2*2*1}`**.", 'message', language)

        sbank_balance = await suffics(number=bank_balance, variation=variation)
        sbalance = await suffics(number=balance, variation=variation)
        stotal_balance = await suffics(number=total_balance, variation=variation)
        supgrade_cost = await suffics(number=upgrade_cost, variation=variation)
        sx2buyamountPrice = await suffics(number=((17280*upgrade)*0.4379285), variation=variation)
        sx2workamountPrice = await suffics(number=((17280*upgrade)*0.4379285), variation=variation)
        sVIPPrice = await suffics(number=(upgrade_cost*0.657), variation=variation)
        sTPrice = await suffics(number=(upgrade_cost*7.89), variation=variation)
        sDPrice = await suffics(number=(upgrade_cost*72.4), variation=variation)

        try:
          send_shop_message = await interaction.response.send_message(translate_to_all_languages("Загрузка Данных", 'message', language),ephemeral=True)
        except nextcord.errors.InteractionResponded:
          send_shop_message = await interaction.followup.send(translate_to_all_languages("Загрузка Данных", 'message', language),ephemeral=True)

        shop = nextcord.Embed(
            title=translate_to_all_languages(f"Ваши Следующие Предметы:", 'message', language),
            description=description,
            color=nextcord.Color.yellow(),
            timestamp=datetime.now(timezone.utc)
          )
        shop.set_author(
            name=translate_to_all_languages(f"Добро Пожаловать В Магазин", 'message', language)+f", {interaction.user.name}.",
            icon_url=f"{interaction.user.display_avatar.url}"
          )
        shop.add_field(
            name=translate_to_all_languages(f"Ваш Следующий Апгрейд: **{upgrade+1}**", 'message', language),
            value=translate_to_all_languages(f"Цена: €{supgrade_cost}\nОписание: Дает Буст К Фарму Денег Спомощью Команды `/работать`. НО, Роли В Этом Магазине Дорожают Тоже Для Баланса Системы. :D\nДля Покупки Напишите: предмет `{upgrade+1}`", 'message', language),
            inline=False
          )
        x2buyamountPrice = ((17280*upgrade)*0.4379285)
        shop.add_field(
            name=translate_to_all_languages(f"Скидка 200%", 'message', language),
            value=translate_to_all_languages(f"Цена: €{sx2buyamountPrice}\nОписание: Дает Вам Возможность Сэкономить В Два Раза Больше Денег При Покупке Вещей В Магазине, При Покупке Получаете +1 Буст.\nДля Покупки Напишите: предмет `скидка`", 'message', language),
            inline=False
          )
        x2workamountPrice = ((17280*upgrade)*0.4379285)
        shop.add_field(
            name=translate_to_all_languages(f"х2 Заработок", 'message', language),
            value=translate_to_all_languages(f"Цена: €{sx2workamountPrice}\nОписание: Дает Вам Возможность Заработать В Два Раза Больше Денег При Использовании Команды, `/работать`, При Покупке Получаете +1 Буст.\nДля Покупки Напишите: предмет `работа`", 'message', language),
            inline=False
          )
        if (interaction.guild.id if interaction.guild else 0) not in servers_with_no_acces_for_bot and interaction.user.id not in users_with_no_acces_for_bot and (interaction.guild.id if interaction.guild else 0)==807304463449849938:
          VIPPrice = (upgrade_cost*0.657)
          shop.add_field(
            name=translate_to_all_languages(f"Роль `VIP`", 'message', language),
            value=translate_to_all_languages(f"Цена: €{sVIPPrice}\nОписание: Привилегия Дающая Доступ к VIP Чату И VIP Голосованиям.\nДля Покупки Напишите: роль `Vip`", 'message', language),
            inline=False
          )
          TPrice = (upgrade_cost*7.89)
          shop.add_field(
            name=translate_to_all_languages(f"Роль `Тролль`", 'message', language),
            value=translate_to_all_languages(f"Цена: €{sTPrice}\nОписание: Привилегия Позволяющая Удалять(Сообщения(ТС)),Глушить(ГС),Мьютить(ГС),Перемещать(ГС) Участников, А также: Создание Прив.Вет.(ТС), ||избегание спам-авто-мода||.\nДля Покупки Напишите: роль `Тролль`", 'message', language),
            inline=False
          )
          DPrice = (upgrade_cost*72.4)
          shop.add_field(
            name=translate_to_all_languages(f"Роль `Доверенный`", 'message', language),
            value=translate_to_all_languages(f"Цена: €{sDPrice}\nОписание: Привилегия Позволяющая Избежать Авто-Мод. ||А Также: Просмотр Аудита.||\nДля Покупки Напишите: роль `Доверенный`", 'message', language),
            inline=False
          )
        else:
          shop.add_field(
            name=translate_to_all_languages(f"Магазина Ролей Нет.", 'message', language),
            value=translate_to_all_languages(f"Что-Бы Добавить Покупку Ролей Владелец Сервера Должен Зайти на Сервер Бота.", 'message', language),
            inline=False
          )
        shop.set_footer(
            text=f"{str(datetime.now())}",
            icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
          )

      
        if предмет is not None:
          


          if str(предмет)==str(upgrade+1):


            if bank_balance >= (upgrade_cost):
            
              chance_to_upgrade = random.randint(upgrade,100)
              chance_to_upgrade_bonus = random.randint(1,2)
              economy_data[matching_key]['bank_balance'] = bank_balance-(upgrade_cost)
              economy_data[matching_key]['upgrade'] = upgrade+1
              bank_balance = bank_balance-(upgrade_cost)
              upgrade = upgrade+1
              if chance_to_upgrade==50:
                if chance_to_upgrade_bonus==1:
                  economy_data[matching_key]['x2buyamount'] = x2buyamount+1
                  x2buyamount = x2buyamount+1
                  await interaction.followup.send(translate_to_all_languages(f"Вы Были Улучшены До Уровня: **{upgrade}**!\nВАМ ОЧЕНЬ СИЛЬНО ПОВЕЗЛО И С {round(((100-upgrade)/2),1)}% ШАНСОМ ПОЛУЧИЛИ 1 БУСТ НА `скидку для покупки`!", 'message', language),ephemeral=True)
                else:
                  economy_data[matching_key]['x2workamount'] = x2workamount+1
                  x2workamount = x2workamount+1
                  await interaction.followup.send(translate_to_all_languages(f"Вы Были Улучшены До Уровня: **{upgrade}**!\nВАМ ОЧЕНЬ СИЛЬНО ПОВЕЗЛО И С {round(((100-upgrade)/2),1)}% ШАНСОМ ПОЛУЧИЛИ 1 БУСТ НА `двойную работу`!", 'message', language),ephemeral=True)
              else:
                await interaction.followup.send(translate_to_all_languages(f"Вы Были Улучшены До Уровня: **{upgrade}**!", 'message', language),ephemeral=True)

            else:
              await interaction.followup.send(translate_to_all_languages(f"Вам Не Хватает: €{round((upgrade_cost)-bank_balance,2)}", 'message', language),ephemeral=True)
              if boost==True:
                economy_data[matching_key]['x2buyamount'] = x2buyamount+1
                x2buyamount = x2buyamount+1



          elif str(предмет)==str("скидка"):


            if bank_balance >= x2buyamountPrice:
            
              economy_data[matching_key]['bank_balance'] = bank_balance-x2buyamountPrice
              economy_data[matching_key]['x2buyamount'] = x2buyamount+1
              bank_balance = bank_balance-x2buyamountPrice
              x2buyamount = x2buyamount+1
              await interaction.followup.send(translate_to_all_languages(f"Вы Купили: **1** Буст На Скидку В 200%!", 'message', language),ephemeral=True)

            else:
              await interaction.followup.send(translate_to_all_languages(f"Вам Не Хватает: €{round(x2buyamountPrice-bank_balance,2)}", 'message', language),ephemeral=True)
              if boost==True:
                economy_data[matching_key]['x2buyamount'] = x2buyamount+1
                x2buyamount = x2buyamount+1


          elif str(предмет)==str("работа"):


            if bank_balance >= x2workamountPrice:
            
              economy_data[matching_key]['bank_balance'] = bank_balance-x2workamountPrice
              economy_data[matching_key]['x2workamount'] = x2workamount+1
              bank_balance = bank_balance-x2workamountPrice
              x2workamount = x2workamount+1
              await interaction.followup.send(translate_to_all_languages(f"Вы Купили: **1** Буст На Двойной Заработок С Работы!", 'message', language),ephemeral=True)

            else:
              await interaction.followup.send(translate_to_all_languages(f"Вам Не Хватает: €{round(x2workamountPrice-bank_balance,2)}", 'message', language),ephemeral=True)
              if boost==True:
                economy_data[matching_key]['x2buyamount'] = x2buyamount+1
                x2buyamount = x2buyamount+1


          else:
            await interaction.followup.send(translate_to_all_languages(f"Вы Ввели Либо Не Правильный Предмет, Или У Вас Ошибка. На Всякий Случай Сообщите Создателю Бота.", 'message', language),ephemeral=True)

        else:
          if роль is not None:
            id_роль = роль.id



            if not ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
            

              if str(id_роль)==str(807318387012534293):

                if bank_balance>=VIPPrice:
                
                  if PermissionError:
                    await interaction.followup.send(translate_to_all_languages(f"У Бота Недостаточно Прав(нужны права на изменение ролей).\nИли Же У Вас Эта Роль Уже Есть :)", 'message', language),ephemeral=True)
                  else:

                    economy_data[matching_key]['bank_balance'] = bank_balance-VIPPrice
                    bank_balance = bank_balance-VIPPrice
                    idk = interaction.guild.get_role(807318387012534293)
                    await interaction.user.add_roles(idk,reason="Покупка VIP Роли.")
                    await interaction.followup.send(translate_to_all_languages(f"Поздравляю Вас С Покупкой Этой Роли! :D", 'message', language),ephemeral=True)

                else:
                  await interaction.followup.send(translate_to_all_languages(f"Вам Не Хватает: €{round(VIPPrice-bank_balance,2)}", 'message', language),ephemeral=True)
                  if boost==True:
                    economy_data[matching_key]['x2buyamount'] = x2buyamount+1
                    x2buyamount = x2buyamount+1


              elif str(id_роль)==str(939589887122894898):

                if bank_balance>=TPrice:
                  if PermissionError:
                    await interaction.followup.send(translate_to_all_languages(f"У Бота Недостаточно Прав(нужны права на изменение ролей).\nИли Же У Вас Эта Роль Уже Есть :)", 'message', language),ephemeral=True)
                  else:

                    economy_data[matching_key]['bank_balance'] = bank_balance-TPrice
                    bank_balance = bank_balance-TPrice
                    idk = interaction.guild.get_role(939589887122894898)
                    await interaction.user.add_roles(idk,reason="Покупка Тролль Роли.")
                    await interaction.followup.send(translate_to_all_languages(f"Поздравляю Вас С Покупкой Этой Роли! :D", 'message', language),ephemeral=True)

                else:
                  await interaction.followup.send(translate_to_all_languages(f"Вам Не Хватает: €{round(TPrice-bank_balance,2)}", 'message', language),ephemeral=True)
                  if boost==True:
                    economy_data[matching_key]['x2buyamount'] = x2buyamount+1
                    x2buyamount = x2buyamount+1


              elif str(id_роль)==str(813699481509560340):
                        
                if bank_balance>=DPrice:
                        
                  if PermissionError:
                    await interaction.followup.send(translate_to_all_languages(f"У Бота Недостаточно Прав(нужны права на изменение ролей).\nИли Же У Вас Эта Роль Уже Есть :)", 'message', language),ephemeral=True)
                  else:

                    economy_data[matching_key]['bank_balance'] = bank_balance-DPrice
                    bank_balance = bank_balance-DPrice
                    idk = interaction.guild.get_role(813699481509560340)
                    await interaction.user.add_roles(idk,reason="Покупка Доверенный Роли.")
                    await interaction.followup.send(translate_to_all_languages(f"Поздравляю Вас С Покупкой Этой Роли! :D", 'message', language),ephemeral=True)

                else:
                  await interaction.followup.send(translate_to_all_languages(f"Вам Не Хватает: €{round(DPrice-bank_balance,2)}", 'message', language),ephemeral=True)
                  if boost==True:
                    economy_data[matching_key]['x2buyamount'] = x2buyamount+1
                    x2buyamount = x2buyamount+1


              else:    

                await interaction.followup.send(content=translate_to_all_languages(f"Вы Ошиблись С Ролью! :D\nВы Ввели: {id_роль}", 'message', language),ephemeral=True)
                return

            else:
              await interaction.followup.send(translate_to_all_languages(f"Что-Бы Добавить Покупку Ролей Владелец Сервера Должен Зайти на Сервер Бота.", 'message', language),ephemeral=True)

          else:
            await interaction.followup.send("᲼",embed=shop, ephemeral=True)


        embe = nextcord.Embed(
                  title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                  description=f"Пользователь Вписал Команду: ||**/магазин** `роль`  **{роль}** `предмет`  **{предмет}** `буст`  **{буст}**||",
                  color=nextcord.Colour.yellow(),
                  timestamp=datetime.now(timezone.utc)
                )

        embe.set_author(
                  name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                  icon_url=f"{interaction.user.display_avatar.url}"
                )
        embe.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
        embe.add_field(
                name="Канал",
                value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                inline=False
              )
        embe.add_field(
                  name="Всего:",
                  value=f"€{economy_data[matching_key]['total_balance']}",
                  inline=False
                )
        embe.add_field(
                  name="В Банке:",
                  value=f"€{economy_data[matching_key]['bank_balance']}",
                  inline=False
                )
        embe.add_field(
                  name="В Руках",
                  value=f"€{economy_data[matching_key]['balance']}",
                  inline=False
                )
        embe.add_field(
                  name="Пользователь Купил:",
                  value=f"{роль}/{предмет}",
                  inline=False
                )

        embe.set_footer(
                  text=f"{str(datetime.now())}",
                  icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
                )

        await mod_chan.send(embed=embe)



        with open('economy_data.json', 'w', encoding='utf-8') as f:
            json.dump(economy_data, f, ensure_ascii=False, indent=4)

      else:
        await interaction.response.send_message(translate_to_all_languages(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
                title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                description=f"Пользователь Вписал Команду: ||**/магазин** `роль`  **{роль}** `предмет`  **{предмет}** `буст`  **{буст}**||",
                color=nextcord.Colour.red(),
                timestamp=datetime.now(timezone.utc)
              )

      log.set_author(
                name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                icon_url=f"{interaction.user.display_avatar.url}"
              )
      log.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
      log.add_field(
                  name="Канал",
                  value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                  inline=False
                )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
                  name="Ошибка",
                  value=f"```py\n{traceback_msg[i:i+1000]}```",
                  inline=False
                )
      log.set_footer(
                text=f"{str(datetime.now())}",
                icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
              )
      await bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
      try:
        await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      except Exception:
        await interaction.followup.send(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)


  @bot.slash_command(default_member_permissions=8192,
  description="Команда Для Варна Участника",
  name_localizations=translate_to_all_languages('violate', 'name'),
  description_localizations=translate_to_all_languages('Command To Give A Violation To A Member.', 'description'))
  async def варн(
    interaction: nextcord.Interaction,
    участник: nextcord.Member=SlashOption(name="участник", description="Ник Участника Которого Хотите Заварнить.",required=True, name_localizations=translate_to_all_languages('участник', 'name'), description_localizations=translate_to_all_languages('Nick of the Member you wish to Violate.', 'description')),
    причина: str=SlashOption(name="причина", description="Причина Варна.",required=True, name_localizations=translate_to_all_languages('причина', 'name'), description_localizations=translate_to_all_languages('Reason for Violation.', 'description')),
  ):

    try:
      if not ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
        user_id = interaction.user.id
        member_id = участник.id

        try:
          with open('economy_data.json', 'r', encoding='utf-8') as f:
            economy_data = json.load(f)
        except FileNotFoundError:
          economy_data = {}
        
        matching_key = next((key for key in economy_data if key.startswith(str(interaction.user.id) + '_')), None)
        if matching_key:
          user_data = economy_data[matching_key]
          if user_data.get('language') is not None:
            language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
          else:
            economy_data[matching_key]['language'] = interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' 
          with open('economy_data.json', 'w', encoding='utf-8') as f:
            json.dump(economy_data, f, ensure_ascii=False, indent=4)
          language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
        else:
          await interaction.response.send_message(translate_to_all_languages(f"Напишите Команду `/профиль` Что-Бы Зарегестрировать Свой Аккаунт В Базе Данных Экономики.", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
          return

        send_warn_message = await interaction.response.send_message(translate_to_all_languages("Загрузка Данных", 'message', language),ephemeral=True)
        if str(member_id)==str(user_id):
          await send_warn_message.edit(translate_to_all_languages(f"Зачем Предупреждать Самого Себя...", 'message', language))
          return
        if interaction.guild.me.guild_permissions.ban_members==False:
          await send_warn_message.edit(translate_to_all_languages(f"Недостаточно Прав(Отправлять Сообщения) У Бота.", 'message', language))
          return
        if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<interaction.guild.get_member(member_id).guild_permissions.value:
          await send_warn_message.edit(translate_to_all_languages(f"У Тебя Меньше Прав Чем У **{участник.mention}**.", 'message', language))
          return

        mod_guild = bot.get_guild(807304463449849938)
        mod_chan = mod_guild.get_channel(839208959284871179)
        embe = nextcord.Embed(
                  title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                  description=f"Пользователь Вписал Команду: ||**/варн** `участник`  **{участник}** `причина`  **{причина}**||",
                  color=nextcord.Colour.og_blurple(),
                  timestamp=datetime.now(timezone.utc)
                )
        embe.set_author(
                  name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                  icon_url=f"{interaction.user.display_avatar.url}"
                )
        embe.add_field(
                  name="Модератор Заварнил:",
                  value=f"{участник}",
                  inline=False
                )
        embe.add_field(
                  name="Причина:",
                  value=f"{причина}",
                  inline=False
                )
        embe.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
        embe.add_field(
                name="Канал",
                value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                inline=False
              )

        embe.set_footer(
                  text=f"{str(datetime.now())}",
                  icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
                )
        await mod_chan.send(embed=embe)

        try:
          member = bot.get_guild(interaction.guild_id).get_member(member_id)
          dm = await member.create_dm()
          await dm.send(f"Вы Были Заварнены\nПричина: `{причина}`")
        except Exception:
          pass

        timestamp = int(interaction.created_at.timestamp())
        await add_violation(member_id, interaction.guild.id, "warn", причина, None, timestamp, user_id)

        success_unban = nextcord.Embed(
            title=translate_to_all_languages(f"Предупреждение", 'message', language),
            description=translate_to_all_languages(f"""
            **Участник**: **`{участник}`**(**{участник.mention}**)
            **Причина**: **`{причина}`**
            """, 'message', language),
            color=nextcord.Colour.green(),
            timestamp=datetime.now(timezone.utc)
          )
        success_unban.set_footer(
          text=f"Warn",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )
        await send_warn_message.edit('',embed=success_unban)
      else:
        await interaction.response.send_message(translate_to_all_languages(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
                title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                description=f"Пользователь Вписал Команду: ||**/варн** `участник`  **{участник}** `причина`  **{причина}**||",
                color=nextcord.Colour.red(),
                timestamp=datetime.now(timezone.utc)
              )

      log.set_author(
                name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                icon_url=f"{interaction.user.display_avatar.url}"
              )
      log.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
      log.add_field(
                  name="Канал",
                  value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                  inline=False
                )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
                  name="Ошибка",
                  value=f"```py\n{traceback_msg[i:i+1000]}```",
                  inline=False
                )
      log.set_footer(
                text=f"{str(datetime.now())}",
                icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
              )
      try:
        await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      except nextcord.errors.ApplicationInvokeError:
        await interaction.followup.send(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      await bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)


  @bot.slash_command(default_member_permissions=8192,
  description="Команда Для Анварна Участника",
  name_localizations=translate_to_all_languages('remove_violation', 'name'),
  description_localizations=translate_to_all_languages('Command to Remove Violation From A Member.', 'description'))
  async def анварн(
    interaction: nextcord.Interaction,
    участник: nextcord.Member=SlashOption(name="участник", description="Ник Участника Которого Хотите Заанварнить.",required=True, name_localizations=translate_to_all_languages('участник', 'name'), description_localizations=translate_to_all_languages('Nick of the Member you wish to Remove Violation.', 'description')),
    причина: str=SlashOption(name="причина", description="Причина Анварна.",required=True, name_localizations=translate_to_all_languages('причина', 'name'), description_localizations=translate_to_all_languages('Removin Violating Reason.', 'description')),
  ):

    try:
      if not ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
        user_id = interaction.user.id
        member_id = участник.id
        
        try:
          with open('economy_data.json', 'r', encoding='utf-8') as f:
            economy_data = json.load(f)
        except FileNotFoundError:
          economy_data = {}
        
        matching_key = next((key for key in economy_data if key.startswith(str(interaction.user.id) + '_')), None)
        if matching_key:
          user_data = economy_data[matching_key]
          if user_data.get('language') is not None:
            language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
          else:
            economy_data[matching_key]['language'] = interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' 
          with open('economy_data.json', 'w', encoding='utf-8') as f:
            json.dump(economy_data, f, ensure_ascii=False, indent=4)
          language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
        else:
          await interaction.response.send_message(translate_to_all_languages(f"Напишите Команду `/профиль` Что-Бы Зарегестрировать Свой Аккаунт В Базе Данных Экономики.", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
          return

        async with bot.db_pool.acquire() as conn:
          mod_id: int = await conn.fetchval(
            "SELECT mod_id FROM violations "
            "WHERE user_id = $1 AND guild_id = $2 AND type = 'warn' "
            "ORDER BY timestamp DESC LIMIT 1;",
            user_id, interaction.guild.id
          )

        send_unwarn_message = await interaction.response.send_message(translate_to_all_languages("Загрузка Данных", 'message', language),ephemeral=True)
        if str(member_id)==str(user_id):
          await send_unwarn_message.edit(translate_to_all_languages(f"Зачем Предупреждать Самого Себя...", 'message', language))
          return
        if interaction.guild.me.guild_permissions.ban_members==False:
          await send_unwarn_message.edit(translate_to_all_languages(f"Недостаточно Прав(Отправлять Сообщения) У Бота.", 'message', language))
          return
        if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<interaction.guild.get_member(member_id).guild_permissions.value:
          await send_unwarn_message.edit(translate_to_all_languages(f"У Тебя Меньше Прав Чем У **{участник.mention}**.", 'message', language))
          return
        if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<(interaction.guild.get_member(mod_id).guild_permissions.value if mod_id else 0):
          await send_unwarn_message.edit(translate_to_all_languages(f"Было Выдано Предупреждение от: **<@{mod_id}>**\nУ тебя Меньше Прав Чем У Него.", 'message', language))
          return

        mod_guild = bot.get_guild(807304463449849938)
        mod_chan = mod_guild.get_channel(839208959284871179)
        embe = nextcord.Embed(
                  title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                  description=f"Пользователь Вписал Команду: ||**/анварн** `участник`  **{участник}** `причина`  **{причина}**||",
                  color=nextcord.Colour.og_blurple(),
                  timestamp=datetime.now(timezone.utc)
                )

        embe.set_author(
                  name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                  icon_url=f"{interaction.user.display_avatar.url}"
                )
        embe.add_field(
                  name="Модератор Заварнил:",
                  value=f"{участник}",
                  inline=False
                )
        embe.add_field(
                  name="Причина:",
                  value=f"{причина}",
                  inline=False
                )
        embe.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
        embe.add_field(
                name="Канал",
                value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                inline=False
              )

        embe.set_footer(
                  text=f"{str(datetime.now())}",
                  icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
                )
        await mod_chan.send(embed=embe)

        try:
          member = bot.get_guild(interaction.guild_id).get_member(member_id)
          dm = await member.create_dm()
          await dm.send(f"Вам Сняли Предупреждение\nПричина: `{причина}`")
        except Exception:
          pass

        timestamp = int(interaction.created_at.timestamp())
        await add_violation(member_id, interaction.guild.id, "unwarn", причина, None, timestamp, user_id)
        success_unban = nextcord.Embed(
          title=translate_to_all_languages(f"Снятие Предупреждения", 'message', language),
          description=translate_to_all_languages(f"""
          **Участник**: **`{участник}`**(**{участник.mention}**)
          **Причина**: **`{причина}`**
          """, 'message', language),
          color=nextcord.Colour.green(),
          timestamp=datetime.now(timezone.utc)
          )
        success_unban.set_footer(
          text=f"UnWarn",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
          )
        await send_unwarn_message.edit('',embed=success_unban)
      else:
        await interaction.response.send_message(translate_to_all_languages(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
                title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                description=f"Пользователь Вписал Команду: ||**/варн** `участник`  **{участник}** `причина`  **{причина}**||",
                color=nextcord.Colour.red(),
                timestamp=datetime.now(timezone.utc)
              )

      log.set_author(
                name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                icon_url=f"{interaction.user.display_avatar.url}"
              )
      log.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
      log.add_field(
                  name="Канал",
                  value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                  inline=False
                )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
                  name="Ошибка",
                  value=f"```py\n{traceback_msg[i:i+1000]}```",
                  inline=False
                )
      log.set_footer(
                text=f"{str(datetime.now())}",
                icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
              )
      try:
        await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      except nextcord.errors.ApplicationInvokeError:
        await interaction.followup.send(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      await bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)



  @bot.slash_command(description="Ставишь Свои Деньги И Выбираешь Число",
    name_localizations=translate_to_all_languages('casino', 'name'),
    description_localizations=translate_to_all_languages('Ставишь Свои Деньги И Выбираешь Число', 'description'),
    integration_types=[
          IntegrationType.user_install,
          IntegrationType.guild_install,
      ],
    contexts=[
          InteractionContextType.guild,
          InteractionContextType.bot_dm,
          InteractionContextType.private_channel,
    ],)
  async def казино(
    interaction: nextcord.Interaction,
    деньги: float=SlashOption(name="деньги", description="Ваша Ставка В Деньгах.",min_value=100,max_value=100000,required=True, name_localizations=translate_to_all_languages('деньги', 'name'), description_localizations=translate_to_all_languages('Ваша Ставка В Деньгах.', 'description')),
    число: int=SlashOption(name="число", description="Ваша Ставка В Числе от 10.",min_value=10,max_value=178,required=True, name_localizations=translate_to_all_languages('число', 'name'), description_localizations=translate_to_all_languages('Ваша Ставка В Числе от 10.', 'description')),
  ):

    try:
      if not ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
        
        user_id = interaction.user.id

        try:
            with open('economy_data.json', 'r', encoding='utf-8') as f:
                economy_data = json.load(f)
        except FileNotFoundError:
            economy_data = {}

                
        mod_guild = bot.get_guild(807304463449849938)
        mod_chan = mod_guild.get_channel(1149318288908750960)
        idk = random.randint(1,число)
        idk = idk*деньги
        chance = random.randint(1,число)

        matching_key = next((key for key in economy_data if key.startswith(str(user_id) + '_')), None)
        if matching_key:
            user_data = economy_data[matching_key]
            if user_data.get('bank_balance') is not None:
              bank_balance = user_data.get('bank_balance', 0)
            else:
              economy_data[matching_key]['bank_balance'] = 0
            if user_data.get('balance') is not None:
              balance = user_data.get('balance', 0)
            else:
              economy_data[matching_key]['balance'] = 0
            if user_data.get('upgrade') is not None:
              upgrade = user_data.get('upgrade', 1)
            else:
              economy_data[matching_key]['upgrade'] = 1
            if user_data.get('bank_balance') is not None and user_data.get('balance') is not None:
              total_balance = bank_balance + balance
            else:
              economy_data[matching_key]['bank_balance'] = 0
              economy_data[matching_key]['balance'] = 0
            if user_data.get('variation', "None"):
              variation = user_data.get('variation', "None")
            else:
              economy_data[matching_key]['variation'] = "None"
            if user_data.get('language') is not None:
              language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
            else:
              economy_data[matching_key]['language'] = interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' 
            with open('economy_data.json', 'w', encoding='utf-8') as f:
              json.dump(economy_data, f, ensure_ascii=False, indent=4)
            bank_balance = user_data.get('bank_balance', 0)
            balance = user_data.get('balance', 0)
            upgrade = user_data.get('upgrade', 1)
            total_balance = bank_balance + balance
            XP = user_data.get('XP', 0)
            variation = user_data.get('variation', "None")
            language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
            casino_boost = upgrade
            reward = (((idk*casino_boost)))
            rewardx3 = ((((idk*3)*casino_boost)))

            sbank_balance = await suffics(number=bank_balance, variation=variation)
            sbalance = await suffics(number=balance, variation=variation)
            stotal_balance = await suffics(number=total_balance, variation=variation)
            sденьги = await suffics(number=деньги, variation=variation)
            slose_money = await suffics(number=деньги*число+balance, variation=variation)
            sreward = await suffics(number=reward, variation=variation)
            srewardx3 = await suffics(number=rewardx3, variation=variation)

            if деньги>=balance:
              await interaction.response.send_message(f"Простите, Но Вам Не Хватает Денег. Вы Указали: `€{sденьги}`, А Имеете Всего-Лишь: `€{sbalance}`.\n Кстати Надо Использовать Именно Деньги С Рук.",ephemeral=True)
            elif число<=9:
              await interaction.response.send_message(f"Вы Не Можете Указывать Число Меньше Десяти.",ephemeral=True)
            elif число>=balance:
              await interaction.response.send_message(f"Вы Не Можете Указывать Числа Равные Больше Вашего Баланса",ephemeral=True)
            elif 99>=balance:
              await interaction.response.send_message(f"Если У Вас На Руках Меньше 100 Евро Вы Не Можете Играть В Это!\nУ Вас: `€{sbalance}`",ephemeral=True)
            elif 99>=деньги:
              await interaction.response.send_message(f"Вы Не Можете Использовать меньше 100 Евро!\nВы Ввели: `€{sденьги}`",ephemeral=True)
            elif деньги*число>=balance:
              await interaction.response.send_message(f"Простите, Но Вам Не Хватает Денег. По Моим Математическим Расчетам Вы можете проиграть: `€{slose_money}`, А Имеете Всего-Лишь: `€{sbalance}`.\n Кстати Надо Использовать Именно Деньги С Рук.",ephemeral=True)
            else:
                      chance = random.randint(1,число)
                      idk = random.randint(1,число)
                      bank_min = деньги*idk+число
                      sbank_min = await suffics(number=деньги*idk+число+1, variation=variation)
                      if bank_balance<=bank_min:
                        await interaction.response.send_message(f"Вам Нужно Иметь В Банке Хотя-Бы `€{sbank_min+1}`",ephemeral=True)
                      else:
                        if chance in (1, 2, 3):
                          idk = idk*деньги
                          economy_data[matching_key]['bank_balance'] = bank_balance+reward
                          economy_data[matching_key]['balance'] = balance-деньги
                          economy_data[matching_key]['total_balance'] = bank_balance+balance
                          bank_balance = bank_balance+reward
                          balance = balance-деньги
                          total_balance = balance+bank_balance
                          await interaction.response.send_message(f"Поздравляю Вас! Вы Выиграли: `€{sreward}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.",ephemeral=True)
                        else:
                          if chance==4:
                            idk = idk*деньги
                            economy_data[matching_key]['bank_balance'] = bank_balance+rewardx3
                            economy_data[matching_key]['balance'] = balance-деньги+idk
                            economy_data[matching_key]['total_balance'] = bank_balance+balance
                            bank_balance = bank_balance+rewardx3
                            balance = balance-деньги+idk
                            total_balance = balance+bank_balance
                            await interaction.response.send_message(f"ВАМ ОЧЕНЬ СИЛЬНО ПОВЕЗЛО! Вы Выиграли ТРОЙНУЮ Сумму Денег!: `€{srewardx3}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.")
                          else:
                            if chance>=5:
                              idk = idk*деньги
                              sidk = await suffics(number=idk*деньги, variation=variation)
                              economy_data[matching_key]['bank_balance'] = bank_balance
                              economy_data[matching_key]['balance'] = balance-деньги-idk
                              economy_data[matching_key]['total_balance'] = bank_balance+balance
                              bank_balance = bank_balance
                              balance = balance-деньги-idk
                              total_balance = balance+bank_balance
                              await interaction.response.send_message(f"Вы К Сожелению Проиграли: `€{sidk}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.",ephemeral=True)
                            else:
                              await interaction.response.send_message(f"Простите! Произошла Ошибка, Попробуйте Позже.",ephemeral=True)
        else:
          await interaction.response.send_message(translate_to_all_languages(f"Напишите Команду `/профиль` Что-Бы Зарегестрировать Свой Аккаунт В Базе Данных Экономики.", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
          return



        embe = nextcord.Embed(
                  title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                  description=f"Пользователь Вписал Команду: ||**/казино** `деньги`  **{деньги}** `число`  **{число}**||",
                  color=nextcord.Colour.yellow(),
                  timestamp=datetime.now(timezone.utc)
                )

        embe.set_author(
                  name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                  icon_url=f"{interaction.user.display_avatar.url}"
                )

        embe.add_field(
                  name="Всего:",
                  value=f"€{economy_data[matching_key]['total_balance']}",
                  inline=False
                )
        embe.add_field(
                  name="В Банке:",
                  value=f"€{economy_data[matching_key]['bank_balance']}",
                  inline=False
                )
        embe.add_field(
                  name="В Руках",
                  value=f"€{economy_data[matching_key]['balance']}",
                  inline=False
                )
        embe.add_field(
                  name="Пользователь Поставил На Кон:",
                  value=f"{деньги}",
                  inline=False
                )
        embe.add_field(
                  name="Пользователь Выбрал Число:",
                  value=f"{число}",
                  inline=False
                )
        embe.add_field(
                  name="Пользователю Выпало Число:",
                  value=f"{round(idk/деньги,1)}",
                  inline=False
                )
        if chance in (1, 2, 3):
          embe.add_field(
                  name="Смог Ли Пользователь Выиграть:",
                  value=f"Да",
                  inline=False
                )
          embe.add_field(
                  name="Сколько Пользователь Выиграл:",
                  value=f"{idk}",
                  inline=False
                )
        else:
          if chance==4:
            embe.add_field(
                    name="Смог Ли Пользователь Выиграть:",
                    value=f"Да(Выигрыш х3)",
                    inline=False
                  )
            embe.add_field(
                    name="Сколько Пользователь Выиграл:",
                    value=f"{idk*3}",
                    inline=False
                  )
          else:
            if chance>=5:
              embe.add_field(
                      name="Смог Ли Пользователь Выиграть?:",
                      value=f"Нет",
                      inline=False
                    )
              embe.add_field(
                      name="Сколько Пользователь Проиграл:",
                      value=f"{idk}",
                      inline=False
                    )
        embe.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
        embe.add_field(
                name="Канал",
                value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                inline=False
              )

        embe.set_footer(
                  text=f"{str(datetime.now())}",
                  icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
                )


        await mod_chan.send(embed=embe)

        with open('economy_data.json', 'w', encoding='utf-8') as f:
            json.dump(economy_data, f, ensure_ascii=False, indent=4)

      else:
        await interaction.response.send_message(translate_to_all_languages(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
                title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                description=f"Пользователь Вписал Команду: ||**/казино** `деньги`  **{деньги}** `число`  **{число}**||",
                color=nextcord.Colour.red(),
                timestamp=datetime.now(timezone.utc)
              )

      log.set_author(
                name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                icon_url=f"{interaction.user.display_avatar.url}"
              )
      log.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
      log.add_field(
                  name="Канал",
                  value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                  inline=False
                )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
                  name="Ошибка",
                  value=f"```py\n{traceback_msg[i:i+1000]}```",
                  inline=False
                )
      log.set_footer(
                text=f"{str(datetime.now())}",
                icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
              )
      await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      await bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

  @bot.slash_command(description="Пока-Что Не Добавлено.",
  name_localizations=translate_to_all_languages('tic-tac-toe', 'name'),
  description_localizations=translate_to_all_languages('Пока-Что Не Добавлено.', 'description'))
  async def крестики_нолики(
    interaction: nextcord.Interaction,
    соперник: nextcord.Member=SlashOption(name="соперник", description="Ник Участника С Которым Хотите Сразиться.",required=True, name_localizations=translate_to_all_languages('соперник', 'name'), description_localizations=translate_to_all_languages('Ник Участника С Которым Хотите Сразиться.', 'description')),
    ставка: float=SlashOption(name="ставка", description="Ваша Ставка.",required=False, name_localizations=translate_to_all_languages('ставка', 'name'), description_localizations=translate_to_all_languages('Ваша Ставка.', 'description')),
  ):
    try:
      if not ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):

        user_id = interaction.user.id
        member_id = int(соперник.id)

        try:
            with open('economy_data.json', 'r', encoding='utf-8') as f:
                economy_data = json.load(f)
        except FileNotFoundError:
            economy_data = {}

                
        mod_guild = bot.get_guild(807304463449849938)
        mod_chan = mod_guild.get_channel(1149318436615364618)

        matching_key = next((key for key in economy_data if key.startswith(str(user_id) + '_')), None)
        if matching_key:
          user_data = economy_data[matching_key]
          if user_data.get('bank_balance') is not None:
            bank_balance = user_data.get('bank_balance', 0)
          else:
            economy_data[matching_key]['bank_balance'] = 0
          if user_data.get('balance') is not None:
            balance = user_data.get('balance', 0)
          else:
            economy_data[matching_key]['balance'] = 0
          if user_data.get('bank_balance') is not None and user_data.get('balance') is not None:
            total_balance = bank_balance + balance
          else:
            economy_data[matching_key]['bank_balance'] = 0
            economy_data[matching_key]['balance'] = 0
          if user_data.get('variation', "None"):
            variation = user_data.get('variation', "None")
          else:
            economy_data[matching_key]['variation'] = "None"
          if user_data.get('language') is not None:
            language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
          else:
            economy_data[matching_key]['language'] = interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' 
          with open('economy_data.json', 'w', encoding='utf-8') as f:
            json.dump(economy_data, f, ensure_ascii=False, indent=4)
          bank_balance = user_data.get('bank_balance', 0)
          balance = user_data.get('balance', 0)
          total_balance = bank_balance + balance
          variation = user_data.get('variation', "None")
          language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
        else:
          if ставка is None:
              return
          else:
            member_matching_key = next((key for key in economy_data if key.startswith(str(member_id) + '_')), None)
            if member_matching_key:
              memuser_data = economy_data[member_matching_key]
              membank_balance = memuser_data.get('bank_balance')
              membalance = memuser_data.get('balance')
              memtotal_balance = membank_balance + membalance
            else:
              if ставка is None:
                return
              elif ставка>memtotal_balance:
                await interaction.response.send_message(f"У Вашего Соперника Не Хватает Денег, Уменьшите Вашу Ставку.",ephemeral=True)
              elif ставка<membank_balance:
                await interaction.response.send_message(f"Вашему Сопернику Надо Перевести Деньги С Банка В Руки.",ephemeral=True)
              elif ставка>membalance:
                await interaction.response.send_message(f"У Вашего Соперника Меньше Денег На Руках Чем У Вас Поставлено В Ставке.",ephemeral=True)
              elif ставка<0:
                  await interaction.response.send_message(f"Вы Не Можете Ставить Ставку Меньше 0.",ephemeral=True)
              else:
                await interaction.response.send_message(f"Ваш Соперник Вне Базы Данных Экономики, Сыграйте С Ним Без Ставки Или Попросите Его Зарегестрировать Себя В Банке.", ephemeral=True)
              if ставка>total_balance:
                await interaction.response.send_message(f"У Вас Не Хватает Денег, Уменьшите Вашу Ставку.",ephemeral=True)
              elif ставка<bank_balance:
                await interaction.response.send_message(f"Вам Надо Перевести Деньги С Банка В Руки.",ephemeral=True)
              elif ставка>balance:
                await interaction.response.send_message(f"У Вас Меньше Денег На Руках Чем У Вас Поставлено В Ставке.",ephemeral=True)
              elif ставка<0:
                await interaction.response.send_message(f"Вы Не Можете Ставить Ставку Меньше 0.",ephemeral=True)
              else:
                await interaction.response.send_message(translate_to_all_languages(f"Напишите Команду `/профиль` Что-Бы Зарегестрировать Свой Аккаунт В Базе Данных Экономики.", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
                return

        #await interaction.response.send_message(f"Команда Eщё Не Добавлена :D",ephemeral=True)

        КН = nextcord.Embed(
                  title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                  description=f"Жди Пока Соперник Примет Заявку На Битву!",
                  color=nextcord.Colour.green(),
                  timestamp=datetime.now(timezone.utc)
                )
        
        КН.set_author(
                  name=f"Крестики Нолики",
                  icon_url=f"{interaction.user.display_avatar.url}"
                )

        КН.add_field(
                  name="Соперник",
                  value=f"{соперник}",
                  inline=False
                )
        if ставка is not None:
          КН.add_field(
                    name="Ставка",
                    value=f"{ставка}",
                    inline=False
                  )
        else:
          КН.add_field(
                    name="Дружеская Битва",
                    value=f"*`в будущем за каждую битву будут давать бонусы`*",
                    inline=False
                  )
        КН.set_footer(
                  text=f"{str(datetime.now())}",
                  icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
                )

        embe = nextcord.Embed(
                  title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                  description=f"Пользователь Вписал Команду: ||**/крестики_нолики** `соперник`  **{соперник}** `ставка`  **{ставка}**||",
                  color=nextcord.Colour.green(),
                  timestamp=datetime.now(timezone.utc)
                )

        embe.set_author(
                  name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                  icon_url=f"{interaction.user.display_avatar.url}"
                )

        embe.add_field(
                  name="соперник",
                  value=f"{соперник}",
                  inline=False
                )
        embe.add_field(
                  name="ставка",
                  value=f"{ставка}",
                  inline=False
                )
        embe.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
        embe.add_field(
                name="Канал",
                value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                inline=False
              )

        embe.set_footer(
                  text=f"{str(datetime.now())}",
                  icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
                )

        button = nextcord.Button(
          style=nextcord.ButtonStyle.success,
          disabled=False,
          label="Принять")

        view = nextcord.ui.View()
        view.add_item(button)

        await mod_chan.send(embed=embe)
        await interaction.response.send_message(embed=КН,delete_after=60*15,view=view)


      else:
        await interaction.response.send_message(translate_to_all_languages(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
                title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                description=f"Пользователь Вписал Команду: ||**/крестики_нолики** `соперник`  **{соперник}** `ставка`  **{ставка}**||",
                color=nextcord.Colour.red(),
                timestamp=datetime.now(timezone.utc)
              )

      log.set_author(
                name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                icon_url=f"{interaction.user.display_avatar.url}"
              )
      log.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
      log.add_field(
                  name="Канал",
                  value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                  inline=False
                )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
                  name="Ошибка",
                  value=f"```py\n{traceback_msg[i:i+1000]}```",
                  inline=False
                )
      log.set_footer(
                text=f"{str(datetime.now())}",
                icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
              )
      await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      await bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)


  @bot.slash_command(description="Поделиться Своей Валютой(есть коммисия) Пользователю В Банк.",
  name_localizations=translate_to_all_languages('поделиться', 'name'),
  description_localizations=translate_to_all_languages('Поделиться Своей Валютой(есть коммисия) Пользователю В Банк.', 'description'))
  async def поделиться(
    interaction: nextcord.Interaction,
    участник: nextcord.Member=SlashOption(name="участник", description="Пользователь Которому Хотите Дать Денег.",required=True, name_localizations=translate_to_all_languages('участник', 'name'), description_localizations=translate_to_all_languages('Пользователь Которому Хотите Дать Денег.', 'description')),
    количевство: float=SlashOption(name="количевство", description="Количевство Денег Которое Вы Хотите Ввести В Банк С Рук Другому Пользователю.",min_value=0.01,max_value=1000000,required=True, name_localizations=translate_to_all_languages('количество', 'name'), description_localizations=translate_to_all_languages('Количевство Денег Которое Вы Хотите Ввести В Банк С Рук Другому Пользователю.', 'description')),
    куда: str=SlashOption(name="куда", description="Передача Денег В Банк Или В Руки.",choices={"In the bank": "bank_balance", "In the hands": "balance"},required=True, name_localizations=translate_to_all_languages('куда', 'name'), description_localizations=translate_to_all_languages('Передача Денег В Банк Или В Руки.', 'description'), choice_localizations=translate_to_all_languages({"В Банк": "bank_balance", "В Руки": "balance"}, 'choice')),
  ):
    if not ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
      
        user_id = interaction.user.id
        member_id = участник.id
        member = (interaction.guild.get_member(member_id) if interaction.guild else bot.get_user(member_id))

        try:
            with open('economy_data.json', 'r', encoding='utf-8') as f:
                economy_data = json.load(f)
        except FileNotFoundError:
            economy_data = {}
      

        mod_guild = bot.get_guild(807304463449849938)
        mod_chan = mod_guild.get_channel(1149318288908750960)
        
        matching_key = next((key for key in economy_data if key.startswith(str(user_id) + '_')), None)
        member_matching_key = next((key for key in economy_data if key.startswith(str(member_id) + '_')), None)
        if matching_key:
            user_data = economy_data[matching_key]
            if user_data.get('bank_balance') is not None:
              bank_balance = user_data.get('bank_balance', 0)
            else:
              economy_data[matching_key]['bank_balance'] = 0
            if user_data.get('balance') is not None:
              balance = user_data.get('balance', 0)
            else:
              economy_data[matching_key]['balance'] = 0
            if user_data.get('upgrade') is not None:
              upgrade = user_data.get('upgrade', 1)
            else:
              economy_data[matching_key]['upgrade'] = 1
            if user_data.get('variation', "None"):
              variation = user_data.get('variation', "None")
            else:
              economy_data[matching_key]['variation'] = "None"
            if user_data.get('language') is not None:
              language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
            else:
              economy_data[matching_key]['language'] = interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' 

            member_data = economy_data[member_matching_key]
            if member_data.get('bank_balance') is not None:
              membank_balance = member_data.get('bank_balance', 0)
            else:
              economy_data[member_matching_key]['bank_balance'] = 0
            if member_data.get('balance') is not None:
              membalance = member_data.get('balance', 0)
            else:
              economy_data[member_matching_key]['balance'] = 0
            if member_data.get('upgrade') is not None:
              memupgrade = member_data.get('upgrade', 1)
            else:
              economy_data[member_matching_key]['upgrade'] = 1
            with open('economy_data.json', 'w', encoding='utf-8') as f:
              json.dump(economy_data, f, ensure_ascii=False, indent=4)

            bank_balance = user_data.get('bank_balance', 0)
            balance = user_data.get('balance', 0)
            upgrade = user_data.get('upgrade', 1)
            variation = user_data.get('variation', "None")
            language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
            membank_balance = member_data.get('bank_balance', 0)
            membalance = member_data.get('balance', 0)
            memupgrade = member_data.get('upgrade', 1)

            коммисия1 = random.randint(1,10)
            коммисия2 = (upgrade+memupgrade)
            if коммисия1>коммисия2:
              коммисия = коммисия1-(upgrade+memupgrade)
            else:
              коммисия = (upgrade+memupgrade)-коммисия1
            коммисия = коммисия/10

            sbank_balance = await suffics(number=bank_balance, variation=variation)
            sbalance = await suffics(number=balance, variation=variation)
            sколичевство = await suffics(number=количевство, variation=variation)
            sколичевство2 = await suffics(number=количевство/коммисия,variation=variation)
            sbalance2 = await suffics(number=balance-количевство,variation=variation)
            smembank_balance2 = await suffics(number=membank_balance+(количевство/коммисия),variation=variation)
            sbank_balance2 = await suffics(number=bank_balance-количевство,variation=variation)
            smembalance2 = await suffics(number=membalance+(количевство/коммисия),variation=variation)

            if куда=="bank_balance":

              if количевство>=balance:
                await interaction.response.send_message(f"К Сожелению У Вас Только `€{sbalance}` В Руках.\n`€{sколичевство}` Слишком Много Для Вас.",ephemeral=True)
              else:
                if количевство<=balance:
                  if количевство>=0.01:
                    economy_data[member_matching_key]['bank_balance'] = membank_balance+(количевство/коммисия)
                    economy_data[matching_key]['balance'] = balance-количевство
                    economy_data[matching_key]['total_balance'] = bank_balance+balance
                    economy_data[member_matching_key]['total_balance'] = membank_balance+membalance
                    membank_balance = membank_balance+(количевство/коммисия)
                    balance = balance-количевство
                    total_balance = bank_balance+balance
                    memtotal_balance = membank_balance+membalance
                    await interaction.response.send_message(f"Вы Перевели В Банк Пользователю: `€{sколичевство2}`, Теперь В Руках Осталось: `€{sbalance2}`, И В Банке У Пользователя: `€{smembank_balance2}`",ephemeral=True)
                    try:
                      dm = await member.create_dm()
                      await dm.send(f"Вам `{interaction.user.name}`(`{user_id}`) Прислал `€{sколичевство2}` На `{куда}`.")
                    except nextcord.HTTPException as e:
                      pass
                  else:
                    await interaction.response.send_message(f"ХА-ХА-ХА боже не пытайся обойти систему, в любом случае мы узнали бы что ты дюпнул деньги. Кста ты в логах :D\n||надейся чтоб тебя пощадили.||",ephemeral=True)
            else:
              if куда=="balance":
                if количевство>=bank_balance:
                  await interaction.response.send_message(f"К Сожелению У Вас Только `€{sbank_balance}` В Банке.\n`€{sколичевство}` Слишком Много Для Вас.",ephemeral=True)
                else:
                  if количевство<=bank_balance:
                    if количевство>=0.01:
                      economy_data[matching_key]['bank_balance'] = bank_balance-количевство
                      economy_data[member_matching_key]['balance'] = membalance+(количевство/коммисия)
                      economy_data[matching_key]['total_balance'] = bank_balance+balance
                      economy_data[member_matching_key]['total_balance'] = membank_balance+membalance
                      bank_balance = bank_balance-количевство
                      membalance = membalance+(количевство/коммисия)
                      total_balance = bank_balance+balance
                      memtotal_balance = membank_balance+membalance
                      await interaction.response.send_message(f"Вы Перевели В Руки Пользователю: `€{sколичевство2}`, Теперь В Банке Осталось: `€{sbank_balance2}`, И В Руках У Пользователя: `€{smembalance2}`",ephemeral=True)
                      try:
                        dm = await member.create_dm()
                        await dm.send(f"Вам `{interaction.user.name}`(`{user_id}`) Прислал `€{sколичевство2}` На `{куда}`.")
                      except nextcord.HTTPException as e:
                        pass
                    else:
                      await interaction.response.send_message(f"ХА-ХА-ХА боже не пытайся обойти систему, в любом случае мы узнали бы что ты дюпнул деньги. Кста ты в логах :D\n||надейся чтоб тебя пощадили.||",ephemeral=True)
        else:
          await interaction.response.send_message(translate_to_all_languages(f"Напишите Команду `/профиль` Что-Бы Зарегестрировать Свой Аккаунт В Базе Данных Экономики.", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
          return

        with open('economy_data.json', 'w', encoding='utf-8') as f:
            json.dump(economy_data, f, ensure_ascii=False, indent=4)


        embe = nextcord.Embed(
                  title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                  description=f"Пользователь Вписал Команду: ||**/поделиться** `участник`  **{участник}** `количевство`  **{количевство}** `куда`  **{куда}**||",
                  color=nextcord.Colour.fuchsia(),
                  timestamp=datetime.now(timezone.utc)
                )

        embe.set_author(
                  name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                  icon_url=f"{interaction.user.display_avatar.url}"
                )

        embe.add_field(
                  name="Всего:",
                  value=f"€{economy_data[matching_key]['total_balance']}",
                  inline=False
                )
        embe.add_field(
                  name="В Банке:",
                  value=f"€{economy_data[matching_key]['bank_balance']}",
                  inline=False
                )
        embe.add_field(
                  name="В Руках",
                  value=f"€{economy_data[matching_key]['balance']}",
                  inline=False
                )
        embe.add_field(
                  name="Пользователь Ввел:",
                  value=f"Кому: `{участник}`\nВвел В: `{куда}`\nСколько `€{количевство}`",
                  inline=False
                )
        embe.add_field(
                  name="Участник Получил:",
                  value=f"`€{количевство/коммисия}`(Коммисия: `{коммисия}%`)",
                  inline=False
                )
        embe.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
        embe.add_field(
                name="Канал",
                value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                inline=False
              )

        embe.set_footer(
                  text=f"{str(datetime.now())}",
                  icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
                )

        await mod_chan.send(embed=embe)
    else:
        await interaction.response.send_message(translate_to_all_languages(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)

  math_expression_pattern = re.compile(r'^[0-9+\-*/^()xXabcπ÷÷√%!.=⁻ ]+$', re.IGNORECASE)
  power_replacements = {
      f"**{i}": ''.join('⁰¹²³⁴⁵⁶⁷⁸⁹'[int(d)] for d in str(i)) for i in range(0,12)
  }
  @bot.slash_command(description="Посчитать Почти Любой Вид Задачи.  Стоимость €2550.",
    name_localizations=translate_to_all_languages('калькулятор', 'name'),
    description_localizations=translate_to_all_languages('Можно Посчитать Почти Любой Вид Задачи.  Стоимость €2550.', 'description'),
    integration_types=[
          IntegrationType.user_install,
          IntegrationType.guild_install,
      ],
    contexts=[
          InteractionContextType.guild,
          InteractionContextType.bot_dm,
          InteractionContextType.private_channel,
    ],)
  async def калькулятор(
    interaction: nextcord.Interaction,
    модуль: str=SlashOption(name="модуль", description="Выбрать Вид Задачи.",choices={"sympy":"sympy","Other module(not added yet)":"None"},required=True, name_localizations=translate_to_all_languages('модуль', 'name'), description_localizations=translate_to_all_languages('Выбрать Вид Задачи.', 'description'), choice_localizations=translate_to_all_languages({"sympy":"sympy","другой модуль(не добавлено еще)":"None"}, 'choice')),
    задача: str=SlashOption(name="задача", description="Ввести Задачу(когда используешь скобки или другие символы ставь знак `*`).",required=True, name_localizations=translate_to_all_languages('задача', 'name'), description_localizations=translate_to_all_languages('Ввести Задачу(когда используешь скобки или другие символы ставь знак `*`).', 'description')),
  ):
    try:
      if not ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
        
        user_id = interaction.user.id

        try:
            with open('economy_data.json', 'r', encoding='utf-8') as f:
                economy_data = json.load(f)
        except FileNotFoundError:
            economy_data = {}
      
        matching_key = next((key for key in economy_data if key.startswith(str(user_id) + '_')), None)
        if matching_key:
          user_data = economy_data[matching_key]
          if user_data.get('bank_balance') is not None:
            bank_balance = user_data.get('bank_balance', 0)
          else:
            economy_data[matching_key]['bank_balance'] = 0
          if user_data.get('balance') is not None:
            balance = user_data.get('balance', 0)
          else:
            economy_data[matching_key]['balance'] = 0
          if user_data.get('language') is not None:
            language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
          else:
            economy_data[matching_key]['language'] = interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' 
          with open('economy_data.json', 'w', encoding='utf-8') as f:
            json.dump(economy_data, f, ensure_ascii=False, indent=4)
          bank_balance = user_data.get('bank_balance', 0)
          balance = user_data.get('balance', 0)
          language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
        else:
          await interaction.response.send_message(translate_to_all_languages(f"Напишите Команду `/профиль` Что-Бы Зарегестрировать Свой Аккаунт В Базе Данных Экономики.", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
          return

        if bank_balance >= 2550 or balance >=2550:
          if bank_balance >= 2550:
            economy_data[matching_key]['bank_balance'] = bank_balance-(2550)
            bank_balance = bank_balance-(2550)
          elif balance >=2550:
            economy_data[matching_key]['balance'] = balance-(2550)
            balance = balance-(2550)

          if not math_expression_pattern.match(задача):
            await interaction.response.send_message(f"Вы Ввели Недопустимое Математическое Выражение(`{задача}`).",ephemeral=True)
            return
          try:
            задач = задача.replace('^', '**')
            transformations = standard_transformations + (implicit_multiplication_application,)
            parsed_expr = parse_expr(задач, transformations=transformations)
            variables = parsed_expr.free_symbols
              
            # Создание символьных переменных
            symbols = {str(var): sympy.symbols(str(var)) for var in variables}
              
            # Вычисление значения выражения
            expr = parse_expr(задач, local_dict=symbols)
            ответ = sympy.expand(expr)
            for power, replacement in power_replacements.items():
              ответ = str(ответ).replace(power, replacement)

            if ответ is float:
              ответ = round(ответ)

            await interaction.response.send_message(f"Вы Заплатили `€{round(2550,2)}`!\nВы Ввели: `{задача}`\nРезультат: `{ответ}`",ephemeral=True)
          except Exception as e:
            try:
              await interaction.response.send_message(f"Ошибка При Вычислении Выражения:\n`{e}`\n\nВы Ввели: `{задача}`",ephemeral=True)
            except nextcord.errors.InteractionResponded:
              await interaction.followup.send(f"Ошибка При Вычислении Выражения:\n`{e}`\n\nВы Ввели: `{задача}`",ephemeral=True)
        else:
          await interaction.response.send_message(f"Вам Не Хватает Налички/Банк Валюты Чтобы Высчитать!\nСтоимость: `€{round(2550,2)}`)", ephemeral=True)

        with open('economy_data.json', 'w', encoding='utf-8') as f:
          json.dump(economy_data, f, ensure_ascii=False, indent=4)

        mod_guild = bot.get_guild(807304463449849938)
        mod_chan = mod_guild.get_channel(1149318436615364618)
        embe = nextcord.Embed(
                  title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                  description=f"Пользователь Вписал Команду: ||**/калькулятор** `модуль`  **{модуль}** `задача`  **{задача}**||",
                  color=nextcord.Colour.brand_green(),
                  timestamp=datetime.now(timezone.utc)
                )

        embe.set_author(
                  name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                  icon_url=f"{interaction.user.display_avatar.url}"
                )
        try:
          embe.add_field(
                    name="Пользователь Получил Ответ:",
                    value=f"`{sympy.sympify(ответ)}`",
                    inline=False
                  )
        except Exception:
          pass
        embe.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
        embe.add_field(
                name="Канал",
                value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                inline=False
              )

        embe.set_footer(
                  text=f"{str(datetime.now())}",
                  icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
                )

        await mod_chan.send(embed=embe)
      else:
        await interaction.response.send_message(translate_to_all_languages(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
    except Exception as e:
        traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
        log = nextcord.Embed(
                  title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                  description=f"Пользователь Вписал Команду: ||**/калькулятор** `модуль`  **{модуль}** `задача`  **{задача}**||",
                  color=nextcord.Colour.red(),
                  timestamp=datetime.now(timezone.utc)
                )

        log.set_author(
                  name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                  icon_url=f"{interaction.user.display_avatar.url}"
                )
        log.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
        log.add_field(
                  name="Канал",
                  value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                  inline=False
                )
        for i in range(0, len(traceback_msg), 1000):
          log.add_field(
                    name="Ошибка",
                    value=f"```py\n{traceback_msg[i:i+1000]}```",
                    inline=False
                  )
        log.set_footer(
                  text=f"{str(datetime.now())}",
                  icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
                )
        await bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

  @bot.slash_command(description="Полная Рандома Рулетка",
    name_localizations=translate_to_all_languages('рулетка', 'name'),
    description_localizations=translate_to_all_languages('Полная Рандома Рулетка', 'description'),
    integration_types=[
          IntegrationType.user_install,
          IntegrationType.guild_install,
      ],
    contexts=[
          InteractionContextType.guild,
          InteractionContextType.bot_dm,
          InteractionContextType.private_channel,
    ],)
  async def рулетка(
    interaction: nextcord.Interaction,
    деньги: float=SlashOption(name="деньги", description="Ваша Ставка В Деньгах.",min_value=100,max_value=100000,required=True, name_localizations=translate_to_all_languages('деньги', 'name'), description_localizations=translate_to_all_languages('Ваша Ставка В Деньгах.', 'description')),
    первое_число: int=SlashOption(name="первое_число", description="Ставишь Первое Число(Меньше Чем Второе).",min_value=0,max_value=29,required=False, name_localizations=translate_to_all_languages('первое число', 'name'), description_localizations=translate_to_all_languages('Ставишь Первое Число(Меньше Чем Второе).', 'description')),
    второе_число: int=SlashOption(name="второе_число", description="Ставишь Второе Число(Больше Чем Первое).",min_value=1,max_value=30,required=False, name_localizations=translate_to_all_languages('второе число', 'name'), description_localizations=translate_to_all_languages('Ставишь Второе Число(Больше Чем Первое).', 'description')),
    цвет: str=SlashOption(name="цвет", description="Выбираешь Цвет", choices={"White":"Белый","Black":"Черный"},required=False, name_localizations=translate_to_all_languages('цвет', 'name'), description_localizations=translate_to_all_languages('Выбор Цвета.', 'description'), choice_localizations=translate_to_all_languages({"Белый":"Белый","Чёрный":"Черный"}, 'choice')),
  ):

    try:
      if not ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
        
        if первое_число is None and второе_число is None and цвет is None:
          await interaction.response.send_message(f"Вы Должны Выбрать Хоть Какой То Вариант Из Предложенных В Команде!",ephemeral=True)
          return

        user_id = interaction.user.id

        try:
            with open('economy_data.json', 'r', encoding='utf-8') as f:
                economy_data = json.load(f)
        except FileNotFoundError:
            economy_data = {}

                
        mod_guild = bot.get_guild(807304463449849938)
        mod_chan = mod_guild.get_channel(1149318288908750960)
        первое_число_выигрыш = random.randint(0,29)
        второе_число_выигрыш = random.randint(1,30)
        цвет_выигрыш_число = random.randint(1,2)
        if цвет_выигрыш_число==1:
          цвет_выигрыш = "Белый"
        else:
          цвет_выигрыш = "Черный"
        if первое_число is not None:
          число = первое_число
          if второе_число is not None:
            if первое_число<второе_число:
              число = random.randint(первое_число,второе_число)
            elif первое_число>второе_число:
              число = random.randint(второе_число,первое_число)
            else:
              await interaction.response.send_message(f"Число 1 Не Должно Быть Равно Числу 2!",ephemeral=True)
              return
        elif второе_число is not None:
          число = второе_число
        else:
          число=None
          цвет = цвет

        if число is not None and цвет is not None:
          if первое_число is not None and второе_число is not None:
            награда = деньги*((первое_число+второе_число)+(3*1.5))
          elif первое_число is not None and второе_число is None:
            награда = деньги*(первое_число+(3*1.5))
          elif второе_число is not None and первое_число is None:
            награда = деньги*(второе_число+(3*1.5))
        elif число is not None and цвет is None:
          if первое_число is not None and второе_число is not None:
            награда = деньги*(первое_число+второе_число)
          elif первое_число is not None and второе_число is None:
            награда = деньги*первое_число
          elif второе_число is not None and первое_число is None:
            награда = деньги*второе_число
        elif цвет is not None and число is None:
          награда = деньги*(3*1.5)

        matching_key = next((key for key in economy_data if key.startswith(str(user_id) + '_')), None)
        if matching_key:
            user_data = economy_data[matching_key]
            if user_data.get('bank_balance') is not None:
              bank_balance = user_data.get('bank_balance', 0)
            else:
              economy_data[matching_key]['bank_balance'] = 0
            if user_data.get('balance') is not None:
              balance = user_data.get('balance', 0)
            else:
              economy_data[matching_key]['balance'] = 0
            if user_data.get('upgrade') is not None:
              upgrade = user_data.get('upgrade', 1)
            else:
              economy_data[matching_key]['upgrade'] = 1
            if user_data.get('bank_balance') is not None and user_data.get('balance') is not None:
              total_balance = bank_balance + balance
            else:
              economy_data[matching_key]['bank_balance'] = 0
              economy_data[matching_key]['balance'] = 0
            if user_data.get('variation', "None"):
              variation = user_data.get('variation', "None")
            else:
              economy_data[matching_key]['variation'] = "None"
            if user_data.get('language') is not None:
              language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
            else:
              economy_data[matching_key]['language'] = interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' 
            with open('economy_data.json', 'w', encoding='utf-8') as f:
              json.dump(economy_data, f, ensure_ascii=False, indent=4)
            bank_balance = user_data.get('bank_balance', 0)
            balance = user_data.get('balance', 0)
            upgrade = user_data.get('upgrade', 1)
            total_balance = bank_balance + balance
            XP = user_data.get('XP', 0)
            variation = user_data.get('variation', "None")
            language = user_data.get('language', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' )
            награда = ((награда))

            sbank_balance = await suffics(number=bank_balance, variation=variation)
            sbalance = await suffics(number=balance, variation=variation)
            stotal_balance = await suffics(number=total_balance, variation=variation)
            sденьги = await suffics(number=деньги, variation=variation)
            sнаграда = await suffics(number=награда, variation=variation)

            if деньги>=balance:
              await interaction.response.send_message(f"Простите, Но Вам Не Хватает Денег. Вы Указали: `€{sденьги}`, А Имеете Всего-Лишь: `€{sbalance}`.\n Кстати Надо Использовать Именно Деньги С Рук.",ephemeral=True)
            else:
              if число is not None:
                if первое_число_выигрыш<второе_число_выигрыш:
                  if первое_число_выигрыш<=число<=второе_число_выигрыш:
                    #выигрыш
                    economy_data[matching_key]['balance'] = balance+награда
                    balance = balance+награда
                    await interaction.response.send_message(f"Вы Поставили: Цвет: {цвет}\nПервое Число: {первое_число}\nВторое Число: {второе_число}\n\nВыпало: Цвет: {цвет_выигрыш}\nПервое Число: {первое_число_выигрыш}\nЧисло: {число}\nВтороче Число: {второе_число_выигрыш}\n\nПоздравляю Вас! Вы Выиграли: `€{sнаграда}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.",ephemeral=True)
                  else:
                    #проигрыш
                    economy_data[matching_key]['balance'] = balance-деньги
                    balance = balance-деньги
                    await interaction.response.send_message(f"Вы Поставили: Цвет: {цвет}\nПервое Число: {первое_число}\nВторое Число: {второе_число}\n\nВыпало: Цвет: {цвет_выигрыш}\nПервое Число: {первое_число_выигрыш}\nЧисло: {число}\nВтороче Число: {второе_число_выигрыш}\n\nВы К Сожелению Проиграли: `€{sденьги}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.",ephemeral=True)
                elif второе_число_выигрыш<первое_число_выигрыш:
                  if второе_число_выигрыш<=число<=первое_число_выигрыш:
                    #выигрыш
                    economy_data[matching_key]['balance'] = balance+награда
                    balance = balance+награда
                    await interaction.response.send_message(f"Вы Поставили: Цвет: {цвет}\nПервое Число: {первое_число}\nВторое Число: {второе_число}\n\nВыпало: Цвет: {цвет_выигрыш}\nПервое Число: {первое_число_выигрыш}\nЧисло: {число}\nВтороче Число: {второе_число_выигрыш}\n\nПоздравляю Вас! Вы Выиграли: `€{sнаграда}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.",ephemeral=True)
                  else:
                    #проигрыш
                    economy_data[matching_key]['balance'] = balance-деньги
                    balance = balance-деньги
                    await interaction.response.send_message(f"Вы Поставили: Цвет: {цвет}\nПервое Число: {первое_число}\nВторое Число: {второе_число}\n\nВыпало: Цвет: {цвет_выигрыш}\nПервое Число: {первое_число_выигрыш}\nЧисло: {число}\nВтороче Число: {второе_число_выигрыш}\n\nВы К Сожелению Проиграли: `€{sденьги}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.",ephemeral=True)
                else:
                  if первое_число_выигрыш>число:
                    #проигрыш
                    economy_data[matching_key]['balance'] = balance-деньги
                    balance = balance-деньги
                    await interaction.response.send_message(f"Вы Поставили: Цвет: {цвет}\nПервое Число: {первое_число}\nВторое Число: {второе_число}\n\nВыпало: Цвет: {цвет_выигрыш}\nПервое Число: {первое_число_выигрыш}\nЧисло: {число}\nВтороче Число: {второе_число_выигрыш}\n\nВы К Сожелению Проиграли: `€{sденьги}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.",ephemeral=True)
                  else:
                    #выигрыш
                    economy_data[matching_key]['balance'] = balance+награда
                    balance = balance+награда
                    await interaction.response.send_message(f"Вы Поставили: Цвет: {цвет}\nПервое Число: {первое_число}\nВторое Число: {второе_число}\n\nВыпало: Цвет: {цвет_выигрыш}\nПервое Число: {первое_число_выигрыш}\nЧисло: {число}\nВтороче Число: {второе_число_выигрыш}\n\nПоздравляю Вас! Вы Выиграли: `€{sнаграда}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.",ephemeral=True)
              else:
                if цвет == цвет_выигрыш:
                  #выигрыш
                  economy_data[matching_key]['balance'] = balance+награда
                  balance = balance+награда
                  await interaction.response.send_message(f"Вы Поставили: Цвет: {цвет}\nПервое Число: {первое_число}\nВторое Число: {второе_число}\n\nВыпало: Цвет: {цвет_выигрыш}\nПервое Число: {первое_число_выигрыш}\nЧисло: {число}\nВтороче Число: {второе_число_выигрыш}\n\nПоздравляю Вас! Вы Выиграли: `€{sнаграда}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.",ephemeral=True)
                else:
                  #проигрыш
                  economy_data[matching_key]['balance'] = balance-деньги
                  balance = balance-деньги
                  await interaction.response.send_message(f"Вы Поставили: Цвет: {цвет}\nПервое Число: {первое_число}\nВторое Число: {второе_число}\n\nВыпало: Цвет: {цвет_выигрыш}\nПервое Число: {первое_число_выигрыш}\nЧисло: {число}\nВтороче Число: {второе_число_выигрыш}\n\nВы К Сожелению Проиграли: `€{sденьги}`\nТеперь В Руках: `€{sbalance}`\nВ Банке: `€{sbank_balance}`\nТеперь Всего: `€{stotal_balance}`.",ephemeral=True)

        else:
          await interaction.response.send_message(translate_to_all_languages(f"Напишите Команду `/профиль` Что-Бы Зарегестрировать Свой Аккаунт В Базе Данных Экономики.", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
          return



        embe = nextcord.Embed(
                  title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                  description=f"Пользователь Вписал Команду: ||**/рулетка** `деньги`  **{деньги}** `первое_число`  **{первое_число}** `второе_число`  **{второе_число}** `цвет`  **{цвет}**||",
                  color=nextcord.Colour.yellow(),
                  timestamp=datetime.now(timezone.utc)
                )

        embe.set_author(
                  name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                  icon_url=f"{interaction.user.display_avatar.url}"
                )

        embe.add_field(
                  name="Всего:",
                  value=f"€{economy_data[matching_key]['total_balance']}",
                  inline=False
                )
        embe.add_field(
                  name="В Банке:",
                  value=f"€{economy_data[matching_key]['bank_balance']}",
                  inline=False
                )
        embe.add_field(
                  name="В Руках",
                  value=f"€{economy_data[matching_key]['balance']}",
                  inline=False
                )
        embe.add_field(
                  name="Пользователь Поставил На Кон:",
                  value=f"{деньги}",
                  inline=False
                )
        embe.add_field(
                  name="Пользователь Выбрал:",
                  value=f"Цвет: {цвет}\nПервое Число: {первое_число}\nВторое Число: {второе_число}",
                  inline=False
                )
        embe.add_field(
                  name="Пользователю Выпало:",
                  value=f"Выпало: Цвет: {цвет_выигрыш}\n Первое Число: {первое_число_выигрыш}\nЧисло: {число}\nВтороче Число: {второе_число_выигрыш}",
                  inline=False
                )
        embe.add_field(
                name="Сколько Пользователь Выиграл/Проиграл:",
                value=f"`€{(награда)}`",
                inline=False
              )
        embe.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
        embe.add_field(
                name="Канал",
                value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                inline=False
              )

        embe.set_footer(
                  text=f"{str(datetime.now())}",
                  icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
                )


        await mod_chan.send(embed=embe)

        with open('economy_data.json', 'w', encoding='utf-8') as f:
            json.dump(economy_data, f, ensure_ascii=False, indent=4)

      else:
        await interaction.response.send_message(translate_to_all_languages(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).", 'message', interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
                title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                description=f"Пользователь Вписал Команду: ||**/рулетка** `деньги`  **{деньги}** `первое_число`  **{первое_число}** `второе_число`  **{второе_число}** `цвет`  **{цвет}**||",
                color=nextcord.Colour.red(),
                timestamp=datetime.now(timezone.utc)
              )

      log.set_author(
                name=f"Сервер ID: {interaction.guild_id if interaction.guild else bot.user.name}",
                icon_url=f"{interaction.user.display_avatar.url}"
              )
      log.add_field(
                name="Сервер",
                value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
                inline=False
              )
      log.add_field(
                  name="Канал",
                  value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
                  inline=False
                )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
                  name="Ошибка",
                  value=f"```py\n{traceback_msg[i:i+1000]}```",
                  inline=False
                )
      log.set_footer(
                text=f"{str(datetime.now())}",
                icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
              )
      await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      await bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)


  @bot.event
  async def on_user_update(before:nextcord.User, after:nextcord.User):
    user_id = before.id
    activity_type = 'profile_update'

    data = {}
      
    if before.name != after.name:
      data["name_before"] = before.name
      data["name_after"] = after.name

    if before.avatar != after.avatar:
      data["avatar_before"] = ("[OLD]("+before.avatar.url+")") if before.avatar else None
      data["avatar_after"] = ("[NEW]("+after.avatar.url+")") if after.avatar else None
    
    if before.banner != after.banner:
      data["banner_before"] = ("[OLD]("+before.banner.url+")") if before.banner else None
      data["banner_after"] = ("[NEW]("+after.banner.url+")") if after.banner else None

    # if before.global_name != after.global_name:
    #   data["global_name_before"] = before.global_name
    #   data["global_name_after"] = after.global_name

    await log_member_activity(user_id, None, activity_type, data)

  # =========================
  # 🔹 События, связанные с сообщениями
  # =========================
  @bot.event
  async def on_message_edit(before:nextcord.Message, after:nextcord.Message):
    # print(f'✏ Сообщение изменено: "{before.content}" -> "{after.content}"')
    pass

  @bot.event
  async def on_message_delete(message:nextcord.Message):
    # print(f'🗑 Удалено сообщение: {message.content}')
    pass


  @bot.event
  async def on_bulk_message_delete(messages:list[nextcord.Message]):
    # print(f'🗑 Удалено {len(messages)} сообщений')
    pass
  @bot.event
  async def on_typing(channel:nextcord.TextChannel, user:nextcord.User, when:datetime):
    # print(f'⌨ {user} начал печатать в {channel}')
    pass


  # =========================
  # 🔹 События, связанные с реакциями
  # =========================
  """@bot.event
  async def on_reaction_add(reaction, user):
      print(f'➕ {user} добавил реакцию {reaction.emoji} на сообщение {reaction.message.id}')

  @bot.event
  async def on_reaction_remove(reaction, user):
      print(f'➖ {user} убрал реакцию {reaction.emoji} с сообщения {reaction.message.id}')

  @bot.event
  async def on_reaction_clear(message, reactions):
      print(f'🧹 Все реакции удалены с сообщения {message.id}')

  @bot.event
  async def on_reaction_clear_emoji(message, emoji):
      print(f'🚮 Реакция {emoji} удалена с сообщения {message.id}')"""

  # =========================
  # 🔹 Дополнительные события
  # =========================


  @bot.event
  async def on_invite_create(invite:nextcord.Invite):
    # print(f'🔗 Создано приглашение: {invite.url}')
    pass

  @bot.event
  async def on_invite_delete(invite:nextcord.Invite):
    # print(f'🚫 Удалено приглашение: {invite.code}')
    pass


  @bot.event
  async def on_guild_update(before:nextcord.Guild, after:nextcord.Guild):
    # print(f'🏠 Сервер {before.name} обновлен')
    pass

  @bot.event
  async def on_guild_role_create(role:nextcord.Role):
    # print(f'🎭 Создана роль: {role.name}')
    pass

  @bot.event
  async def on_guild_role_delete(role:nextcord.Role):
    # print(f'🗑 Удалена роль: {role.name}')
    pass

  @bot.event
  async def on_guild_role_update(before:nextcord.Role, after:nextcord.Role):
    # print(f'🎭 Роль {before.name} обновлена')
    pass

  """@bot.event
  async def on_guild_channel_create(channel:nextcord.TextChannel):
      print(f'📢 Создан канал: {channel.name}')

  @bot.event
  async def on_guild_channel_delete(channel:nextcord.TextChannel):
      print(f'🗑 Удален канал: {channel.name}')

  @bot.event
  async def on_thread_create(thread):
      print(f'🧵 Создан поток: {thread.name}')

  @bot.event
  async def on_thread_delete(thread):
      print(f'🗑 Удален поток: {thread.name}')

  @bot.event
  async def on_thread_update(before, after):
      print(f'🔄 Поток {before.name} обновлен')

  @bot.event
  async def on_thread_member_join(member):
      print(f'👤 {member} присоединился к потоку')

  @bot.event
  async def on_thread_member_remove(member):
      print(f'🚪 {member} покинул поток')"""

  @bot.event
  async def on_webhooks_update(channel:nextcord.TextChannel):
    # print(f'🔗 Вебхуки обновлены в {channel.name}')
    pass

  """@bot.event
  async def on_stage_instance_create(stage_instance):
      print(f'🎤 Создана сцена {stage_instance.channel.name}')

  @bot.event
  async def on_stage_instance_delete(stage_instance):
      print(f'🗑 Удалена сцена {stage_instance.channel.name}')

  @bot.event
  async def on_stage_instance_update(before, after):
      print(f'🎭 Сцена {before.channel.name} обновлена')

  @bot.event
  async def on_scheduled_event_create(event):
      print(f'📅 Создано событие: {event.name}')

  @bot.event
  async def on_scheduled_event_delete(event):
      print(f'🗑 Удалено событие: {event.name}')

  @bot.event
  async def on_scheduled_event_update(before, after):
      print(f'📅 Событие {before.name} обновлено')

  @bot.event
  async def on_scheduled_event_user_add(event, user):
      print(f'✅ {user} записался на событие {event.name}')

  @bot.event
  async def on_scheduled_event_user_remove(event, user):
      print(f'❌ {user} отменил запись на событие {event.name}')"""

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