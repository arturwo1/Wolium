from textwrap import indent

import nextcord
from nextcord.ext import commands,tasks
import json
from collections import Counter
import aiohttp
import asyncio

import nextcord.gateway
from cogs.utils.translate_message import TranslateMessage
from traceback import format_exception
from cogs.utils.send_embed import SendEmbed

class SetBotStatus(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
    self.set_bot_status.start()

  def cog_unload(self):
    self.set_bot_status.cancel()

  @tasks.loop(minutes=15) 
  async def set_bot_status(self):
    try:
      status_info = {}
      try:
        with open('status_data.json', 'r', encoding='utf-8') as f:
          status_info = json.load(f).get('status', {})
      except FileNotFoundError:
        pass

      expr = status_info.get("название", "")

      while True:
        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          try:
            async with self.bot.db_pool.acquire() as conn:
              ctx = {
                "self": self,
                "conn": conn,
              }

              code = (
                "async def __render__():\n"
                + indent(expr, "  ")
              )

              ns = {}
              exec(code, ctx, ns)
              название_1 = await ns["__render__"]()
            break
          except Exception as e:
            await asyncio.sleep(10)
            continue
        await asyncio.sleep(10)
      активность = status_info['активность']
      ссылка = status_info['ссылка']
      статус = status_info['статус']
      название_эмодзи = status_info['название_эмодзи']
      id_эмодзи = status_info['id_эмодзи']
      анимировано_эмодзи = status_info['анимировано_эмодзи']

      for shard in self.bot.shards:
        shard_guilds = [guild for guild in self.bot.guilds if guild.shard_id==shard]
        locales = []
        for shard_guild in shard_guilds:
          locales.append(shard_guild.preferred_locale)
          locale_count = Counter(locales)
          locale, _ = locale_count.most_common(1)[0]

        название = await (TranslateMessage(self.bot)).translate_message(название_1, locale if locale!='en-US' and locale!='en-GB' and locale!='es-ES' and locale!='sv-SE' else 'en' if locale=='en-US' or locale=='en-GB' and locale!='es-ES' and locale!='sv-SE' else 'es' if locale!='en-US' and locale!='en-GB' and locale=='es-ES' and locale!='sv-SE' else 'sv',save=False)
        if активность=="play":
          activity=nextcord.Game(название)
        elif активность=="stream":
          activity=nextcord.Streaming(name=название,url=ссылка)
        elif активность in ["listening","watching","competing"]:
          activity=nextcord.Activity(
            type=nextcord.ActivityType[активность],
            name=название,
            url=(ссылка if ссылка else None),
            emoji=(
              {
                'name': название_эмодзи,
                'id': id_эмодзи,
                'animated': анимировано_эмодзи
              } if (название_эмодзи!=None and id_эмодзи!=None and анимировано_эмодзи!=None) else None
            )
          )
        if статус:
          while True:
            try:
              await self.bot.change_presence(status=nextcord.Status[статус], activity=activity, shard_id=shard)
              break
            except aiohttp.client_exceptions.ClientConnectionResetError as e:
              await asyncio.sleep(15)
              traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
              fields = [
                {
                  'name':'Ошибка',
                  'value':traceback_msg,
                  'inline':False
                }
              ]
              await (SendEmbed(self.bot)).send_embed(
                title='Ошибка при попытке изменить статус',
                description=str(e)[:2048],
                color=nextcord.Color.red(),
                fields=fields,
                footer_text='Ошибка в set_bot_status',
                channel_id=1159138280651104256
              )
    except Exception as e:
      await asyncio.sleep(15)
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      fields = [
        {
          'name':'Ошибка',
          'value':traceback_msg,
          'inline':False
        }
      ]
      await (SendEmbed(self.bot)).send_embed(
        title='Ошибка где то в коде',
        description=str(e)[:2048],
        color=nextcord.Color.red(),
        fields=fields,
        footer_text='Ошибка в set_bot_status',
        channel_id=1159138280651104256
      )

  @set_bot_status.before_loop
  async def before_set_bot_status(self):
    await self.bot.wait_until_ready()

def setup(bot:commands.Bot):
  bot.add_cog(SetBotStatus(bot))