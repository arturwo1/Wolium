from collections import defaultdict,deque
from nextcord import Color
from nextcord.ext import commands, tasks
import json
import traceback
import asyncio
from cogs.utils.get_invite import GetInvite
from cogs.utils.send_embed import SendEmbed
from main import init_database
import asyncpg
from time import time

class CheckPostgreSQLData(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
    self.listen_PostgreSQL_changes.start()
    self.change_history: defaultdict[str, deque[float]] = defaultdict(deque)
    self.change_limit = 10
    self.lock = asyncio.Lock()

  def cog_unload(self):
    self.listen_PostgreSQL_changes.cancel()

  async def track_change(self, key_id: str):
    async with self.lock:
      now_ts = time()
      history:deque = self.change_history[key_id]

      if not isinstance(history, deque):
        history = deque(history)
        self.change_history[key_id] = history

      history.append(now_ts)

      while history and now_ts - history[0] > 60:
        history.popleft()

      return len(history)
  
  async def handle_PostgreSQL_changes(self,conn,pid,channel,payload):
    try:
      user_id=None
      guild_id=None
      channel_id=None
      fields = []
      data:dict[str,dict[str,int|any]|str] = json.loads(payload)
      operation:str = data['operation']
      table:str = data['table']
      timestamp:str = data['timestamp']
      user:str = data['user']
      query:str = data['query']
      dont_track = ['messages', 'guild_settings','inventory','users_members_activity','violations','equipment','topgg','voice']
      any_data = data.get('old_data') or data.get('new_data')

      user_id = any_data.get('user_id')
      guild_id = any_data.get('guild_id')
      channel_id = any_data.get('channel_id')

      fields.append({
        'name': 'Информация',
        'value': (
          f"Юзер: **`{user}`**\n"+
          f"Запрос: **```sql\n{query}```**"+
          f"Время: **`{timestamp}`**"
        ),
        'inline': False
      })
      if 'old_data' in data and table not in dont_track:
        fields.append({
          'name': 'Старые Данные',
          'value': '**```json\n'+str(json.dumps(data['old_data'], indent=2, ensure_ascii=False))+'```**',
          'inline': False
        })
      if 'new_data' in data and table not in dont_track:
        fields.append({
          'name': 'Новые Данные',
          'value': '**```json\n'+str(json.dumps(data['new_data'], indent=2, ensure_ascii=False))+'```**',
          'inline': True
        })
      if operation=='UPDATE' and data['new_data']!=data['old_data'] and table not in dont_track:
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
            if (name=='xp' and abs(value_key_value_after-value_key_value_before)<256) or (name in['bank_balance','balance'] and abs(value_key_value_after-value_key_value_before)<1000):
              continue
            diff += name+': '+str(abs(value_key_value_after - value_key_value_before))+'('+str(abs(len(str(value_key_value_after)) - len(str(value_key_value_before))))+')\n'
          else:
            diff += name+': 0('+str(abs(len(str(value_key_value_after)) - len(str(value_key_value_before))))+')\n'
        
        if not diff:
          return

        fields.append({
          'name': 'Разница',
          'value': (
            f"Название ключа/ей: **```json\n{key_name.strip()}```**\n"+
            f"Значение ключа/ей до: **```json\n{key_value_before.strip()}```**"+
            f"Значение ключа/ей после: **```json\n{key_value_after.strip()}```**"+
            (f"Разница: **```json\n{diff}```**")
          ),
          'inline': False
        })
      elif operation=='UPDATE' and data['new_data']==data['old_data'] and table not in dont_track:
        return
      if user_id:
        discord_user = self.bot.get_user(user_id)
        if discord_user:
          fields.append({
            'name':'Пользователь',
            'value':f"{user_id} | {discord_user.mention} | {discord_user.name}",
            'inline':False
          })
      if guild_id:
        guild = self.bot.get_guild(guild_id)
        invite = await (GetInvite(self.bot)).invite(guild)
        if guild:
          fields.append({
            'name':'Сервер',
            'value':f"{guild_id} | {invite} | {guild.name}" if guild else "ЛС",
            'inline':True
          })
      if channel_id:
        channel = self.bot.get_channel(channel_id)
        if channel:
          fields.append({
            'name':'Канал',
            'value':f"{channel_id} | {channel.mention} | {channel.name}",
            'inline':True
          })
      if operation=='INSERT':
        if any(needle in query for needle in ["SELECT x.guild_id, x.channel_id, x.user_id, x.date_time, x.content, x.message_url, x.attachments"]):
          return
        user_id = data['new_data'].get('user_id')
        guild_id = data['new_data'].get('guild_id')
        key_id = f"{user_id}:{guild_id}:{table}:message_insert"
        count = await self.track_change(key_id)

        if count > self.change_limit:
          fields.append({
            'name': 'СПАМ таблицами',
            'value': f"Пользователь отправил **{count} новых таблиц** за последнюю минуту.",
            'inline': False
          })
          self.change_history[key_id] = deque()
      elif operation=='UPDATE':
        something = {
          key: {
            'before': data['old_data'][key],
            'after': data['new_data'][key]
          }
          for key in data['old_data']
          if key in data['new_data'] and data['old_data'][key] != data['new_data'][key]
        }
        value_=''
        for name, value in something.items():
          key_id = f"{user_id}:{guild_id}:{table}:{name}"
          count = await self.track_change(key_id)
          if count > self.change_limit:
            value_+=f'Ключ `{name}` был изменён **{count} раз** за последнюю минуту.\n'
        if value_:
          fields.append({
            'name': 'Превышен лимит изменений',
            'value': value_,
            'inline': False
          })
          self.change_history[key_id] = deque()
      color = {"INSERT": Color.green(), "UPDATE": Color.gold(), "DELETE": Color.red()}.get(operation, Color.blurple())

      if any(field['name']in['Разница','Старые Данные','Новые Данные','Превышен лимит изменений','СПАМ таблицами'] for field in fields):
        await (SendEmbed(self.bot)).send_embed(
          title=f'PostgreSQL | Изменение данных({operation})',
          description=f'Таблица: `{table}`',
          color=color,
          fields=fields,
          footer_text=f'Изменение данных({operation})',
          author_text=f'ДАННЫЕ PostgreSQL',
          author_icon=self.bot.get_user(user_id).display_avatar.url if user_id and self.bot.get_user(user_id) else None,
          guild_id=807304463449849938,
          channel_id=1294702500435198105
        )
    except Exception as e:
      traceback_msg = str((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      if user_id:
        exc_user = self.bot.get_user(user_id)
        if exc_user:
          fields.append({
            'name':'Пользователь',
            'value':f"{user_id} | {exc_user.mention} | {exc_user.name}",
            'inline':True
          })
      if guild_id:
        guild = self.bot.get_guild(guild_id)
        invite = await (GetInvite(self.bot)).invite(guild)
        fields.append({
          'name':'Сервер',
          'value':f"{guild_id} | {invite} | {guild.name}" if guild else "ЛС",
          'inline':True
        })

      fields.append({
        'name': 'ERROR',
        'value': '**```py\n'+traceback_msg+'```**',
        'inline': False
      })
      await (SendEmbed(self.bot)).send_embed(f'PostgreSQL | Изменение данных',f'Произошла ошибка в handle_data_changes PostgreSQL\n\n{e}',Color.red(),fields,f'Изменение данных | ОШИБКА',f'ДАННЫЕ PostgreSQL | ОШИБКА',None,807304463449849938,1159138280651104256)

  async def handle_ddl_PostgreSQL_changes(self,conn,pid,channel,payload):
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

      await (SendEmbed(self.bot)).send_embed(f'PostgreSQL | Изменение структуры БД({event})',f'Структура БД была изменена:',Color.purple(),fields,f'Изменение структуры БД({event})',f'СТРУКТУРА PostgreSQL',None,807304463449849938,1294702500435198105)
    except Exception as e:
      traceback_msg = str((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      fields.append({
        'name': 'ERROR',
        'value': '**```py\n'+traceback_msg+'```**',
        'inline': False
      })
      await (SendEmbed(self.bot)).send_embed(f'PostgreSQL | Изменение структуры БД',f'Произошла ошибка в handle_ddl_changes PostgreSQL\n\n{e}',Color.red(),fields,f'Изменение структуры БД | ОШИБКА',f'СТРУКТУРА PostgreSQL | ОШИБКА',807304463449849938,1159138280651104256)

  @tasks.loop(count=1)
  async def listen_PostgreSQL_changes(self):
    while True:
      await self.bot.wait_until_ready()
      conn = None
      try:
        conn = await (await init_database()).acquire()

        await conn.add_listener("data_changes", self.handle_PostgreSQL_changes)
        await conn.add_listener("ddl_changes", self.handle_ddl_PostgreSQL_changes)
        print("🔌 Соединение с PostgreSQL установлено и слушатели добавлены.")

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
        await (SendEmbed(self.bot)).send_embed(
          "PostgreSQL | Ошибка Прослушивания БД",
          f"Произошла ошибка: {e}",
          Color.red(),
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
          await conn.remove_listener("data_changes", self.handle_PostgreSQL_changes)
          await conn.remove_listener("ddl_changes", self.handle_ddl_PostgreSQL_changes)
          await conn.close()
          print("🔌 Соединение закрыто")
      
  @listen_PostgreSQL_changes.before_loop
  async def before_listen_PostgreSQL_changes(self):
    await self.bot.wait_until_ready()

def setup(bot:commands.Bot):
  bot.add_cog(CheckPostgreSQLData(bot))