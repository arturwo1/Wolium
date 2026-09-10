from collections import defaultdict, deque
from nextcord import Color
from nextcord.ext import commands
from json import loads, dumps
from traceback import format_exception
from asyncio import Lock, sleep
from time import time

class CheckPostgreSQLData(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot: commands.Bot = bot
    self.change_history: defaultdict[str, deque[float]] = defaultdict(deque)
    self.change_limit = 10
    self.lock = Lock()

  async def cog_load(self):
    bus = None
    while bus is None:
      bus = self.bot.get_cog("PostgresNotifyBus")
      if not bus:
        await sleep(5)

    bus.add_handler("data_changes", self.handle_PostgreSQL_changes)
    bus.add_handler("ddl_changes", self.handle_ddl_PostgreSQL_changes)

  async def track_change(self, key_id: str):
    async with self.lock:
      now_ts = time()
      history: deque = self.change_history[key_id]

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
      data:dict[str,dict[str,int|any]|str] = loads(payload)
      operation:str = data.get('operation')
      table:str = data.get('table')
      timestamp:str = data.get('timestamp')
      user:str = data.get('user')
      query:str = data.get('query')
      dont_track = ['messages', 'guild_settings','inventory','users_members_activity','violations','equipment','topgg','voice']
      old_data = data.get('old_data')
      new_data = data.get('new_data')
      any_data = old_data or new_data

      user_id = any_data.get('user_id')
      guild_id = any_data.get('guild_id')
      channel_id = any_data.get('channel_id')

      se = self.bot.get_cog("SendEmbed")
      gi = self.bot.get_cog("GetInvite")
      tm = self.bot.get_cog("TranslateMessage")

      fields.append({
        'name': 'Information',
        'value': (
          f"User: **`{user}`**\n"+
          f"Query: **```sql\n{query}```**\n"+
          f"Time: **`{timestamp}`**"
        ),
        'inline': False
      })

      if 'old_data' in data and table not in dont_track:
        fields.append({
          'name': 'Old Data',
          'value': '**```json\n'+str(dumps(old_data, indent=2, ensure_ascii=False))+'```**',
          'inline': False
        })

      if 'new_data' in data and table not in dont_track:
        fields.append({
          'name': 'New Data',
          'value': '**```json\n'+str(dumps(new_data, indent=2, ensure_ascii=False))+'```**',
          'inline': True
        })

      if data.get('truncated'):
        pk = data.get('pk', {}) or {}
        fields.append({
          'name': 'Truncated',
          'value': 'Payload was too large, old/new data omitted.\nPK: **```json\n'+dumps(pk, indent=2, ensure_ascii=False)[:800]+'```**',
          'inline': False
        })

      if operation=='UPDATE' and new_data!=old_data and table not in dont_track:
        something = {
          key: {
            'before': old_data.get(key),
            'after': new_data.get(key)
          }
          for key in old_data
          if key in new_data and old_data.get(key) != new_data.get(key)
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
            if (name== 'xp' and abs(value_key_value_after-value_key_value_before)<256) or (name in ['bank_balance','balance'] and abs(value_key_value_after-value_key_value_before)<1000):
              continue
            diff += name+ ': '+str(abs(value_key_value_after - value_key_value_before)) + '('+str(abs(len(str(value_key_value_after)) - len(str(value_key_value_before))))+')\n'
          else:
            diff += name+': 0('+str(abs(len(str(value_key_value_after)) - len(str(value_key_value_before))))+')\n'
        
        if not diff:
          return

        fields.append({
          'name': 'Difference',
          'value': (
            f"Key name(s): **```json\n{key_name.strip()}```**\n"+
            f"Key value(s) before: **```json\n{key_value_before.strip()}```**\n"+
            f"Key value(s) after: **```json\n{key_value_after.strip()}```**\n"+
            (f"Difference: **```json\n{diff}```**")
          ),
          'inline': False
        })
      elif operation=='UPDATE' and new_data==old_data and table not in dont_track:
        return
      if user_id:
        discord_user = self.bot.get_user(user_id)
        if discord_user:
          fields.append({
            'name':'User',
            'value':f"{user_id} | {discord_user.mention} | {discord_user.name}",
            'inline':False
          })
      if guild_id:
        guild = self.bot.get_guild(guild_id)
        invite = await gi.invite(guild)
        if guild:
          fields.append({
            'name':'Server',
            'value':f"{guild_id} | {invite} | {guild.name}" if guild else "DM",
            'inline':True
          })
      if channel_id:
        channel = self.bot.get_channel(channel_id)
        if channel:
          fields.append({
            'name':'Channel',
            'value':f"{channel_id} | {channel.mention} | {channel.name}",
            'inline':True
          })
      if operation=='INSERT':
        if any(needle in query for needle in ["SELECT x.guild_id, x.channel_id, x.user_id, x.date_time, x.content, x.message_url, x.attachments"]):
          return
        user_id = new_data.get('user_id')
        guild_id = new_data.get('guild_id')
        key_id = f"{user_id}:{guild_id}:{table}:message_insert"
        count = await self.track_change(key_id)

        if count > self.change_limit:
          fields.append({
            'name': await tm.translate_message('error.table_spam', 'en'),
            'value': await tm.translate_message('spam.user_sent_tables', 'en', variables={"count": str(count)}),
            'inline': False
          })
          self.change_history[key_id] = deque()
      elif operation=='UPDATE':
        something = {
          key: {
            'before': old_data.get(key),
            'after': new_data.get(key)
          }
          for key in old_data
          if key in new_data and old_data.get(key) != new_data.get(key)
        }
        value_=''
        for name, value in something.items():
          key_id = f"{user_id}:{guild_id}:{table}:{name}"
          count = await self.track_change(key_id)
          if count > self.change_limit:
            value_+=f'Key `{name}` was changed **{count} times** in the last minute.\n'
        if value_:
          fields.append({
            'name': 'Limit Exceeded',
            'value': value_,
            'inline': False
          })
          self.change_history[key_id] = deque()
      color = {"INSERT": Color.green(), "UPDATE": Color.gold(), "DELETE": Color.red()}.get(operation, Color.blurple())

      if any(field['name']in['Difference','Old Data','New Data','Limit Exceeded','TABLE SPAM'] for field in fields):
        await se.send_embed(
          title=f'PostgreSQL | Data Changes({operation})',
          description=f'Table: `{table}`',
          color=color,
          fields=fields,
          footer_text=f'Data Changes({operation})',
          author_text=f'DATA PostgreSQL',
          author_icon=self.bot.get_user(user_id).display_avatar.url if user_id and self.bot.get_user(user_id) else None,
          guild_id=807304463449849938,
          channel_id=1294702500435198105
        )
    except Exception as e:
      traceback_msg = str((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      if user_id:
        exc_user = self.bot.get_user(user_id)
        if exc_user:
          fields.append({
            'name':'User',
            'value':f"{user_id} | {exc_user.mention} | {exc_user.name}",
            'inline':True
          })
      if guild_id:
        guild = self.bot.get_guild(guild_id)
        invite = gi.invite(guild)
        fields.append({
          'name':'Server',
          'value':f"{guild_id} | {invite} | {guild.name}" if guild else "DM",
          'inline':True
        })

      fields.append({
        'name': 'ERROR',
        'value': '**```py\n'+traceback_msg+'```**',
        'inline': False
      })
      await se.send_embed(f'PostgreSQL | Data Changes',f'Error in handle_data_changes PostgreSQL\n\n{e}',Color.red(),fields,f'Data Changes | ERROR',f'DATA PostgreSQL | ERROR',None,807304463449849938,1159138280651104256)

  async def handle_ddl_PostgreSQL_changes(self,conn,pid,channel,payload):
    try:
      fields = []
      data = loads(payload)
      event = data.get('event')
      obj = data.get('object')
      schema = data.get('schema')
      timestamp = data.get('timestamp')
      query = data.get('query')
      user = data.get('user')

      se = self.bot.get_cog("SendEmbed")

      fields.append({
        'name': 'Information',
        'value': (
          f"Time: **`{timestamp}`**\n"+
          f"Schema: **`{schema}`**\n"+
          f"Event: **`{event}`**\n"+
          f"Object: **```sql\n{obj}```**\n"+
          f"Query: **```sql\n{query}```**\n"+
          f"User: **`{user}`**"
        ),
        'inline': False
      })

      await se.send_embed(f'PostgreSQL | DB Structure Change({event})',f'DB structure was changed:',Color.purple(),fields,f'DB Structure Change({event})',f'STRUCTURE PostgreSQL',None,807304463449849938,1294702500435198105)
    except Exception as e:
      traceback_msg = str((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      fields.append({
        'name': 'ERROR',
        'value': '**```py\n'+traceback_msg+'```**',
        'inline': False
      })
      await se.send_embed(f'PostgreSQL | DB Structure Change',f'Error in handle_ddl_changes PostgreSQL\n\n{e}',Color.red(),fields,f'DB Structure Change | ERROR',f'STRUCTURE PostgreSQL | ERROR',807304463449849938,1159138280651104256)

def setup(bot:commands.Bot):
  bot.add_cog(CheckPostgreSQLData(bot))