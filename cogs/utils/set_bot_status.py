from textwrap import indent
import nextcord
from nextcord.ext import commands,tasks
import json
from collections import Counter
import aiohttp
import asyncio
from traceback import format_exception

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

      expr = status_info.get("name", "")

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
              name_1 = await ns["__render__"]()
            break
          except Exception as e:
            await asyncio.sleep(10)
            continue
        await asyncio.sleep(10)
      activity_type = status_info['activity']
      url = status_info['url']
      status = status_info['status']
      emoji_name = status_info['emoji_name']
      emoji_id = status_info['emoji_id']
      emoji_animated = status_info['emoji_animated']

      tm = self.bot.get_cog("TranslateMessage")
      se = self.bot.get_cog("SendEmbed")

      for shard in self.bot.shards:
        shard_guilds = [guild for guild in self.bot.guilds if guild.shard_id==shard]
        locales = []
        for shard_guild in shard_guilds:
          locales.append(shard_guild.preferred_locale)
          locale_count = Counter(locales)
          locale, _ = locale_count.most_common(1)[0]

        name = await tm.translate_message(name_1, locale if locale!='en-US' and locale!='en-GB' and locale!='es-ES' and locale!='sv-SE' else 'en' if locale=='en-US' or locale=='en-GB' and locale!='es-ES' and locale!='sv-SE' else 'es' if locale!='en-US' and locale!='en-GB' and locale=='es-ES' and locale!='sv-SE' else 'sv',save=False)
        if activity_type=="play":
          activity=nextcord.Game(name)
        elif activity_type=="stream":
          activity=nextcord.Streaming(name=name,url=url)
        elif activity_type in ["listening","watching","competing"]:
          activity=nextcord.Activity(
            type=nextcord.ActivityType[activity_type],
            name=name,
            url=(url if url else None),
            emoji=(
              {
                'name': emoji_name,
                'id': emoji_id,
                'animated': emoji_animated
              } if (emoji_name!=None and emoji_id!=None and emoji_animated!=None) else None
            )
          )
        if status:
          while True:
            try:
              await self.bot.change_presence(status=nextcord.Status[status], activity=activity, shard_id=shard)
              break
            except aiohttp.client_exceptions.ClientConnectionResetError as e:
              await asyncio.sleep(15)
              traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
              fields = [
                {
                  'name':'Error',
                  'value':traceback_msg,
                  'inline':False
                }
              ]
              await se.send_embed(
                title='Error while changing status',
                description=str(e)[:2048],
                color=nextcord.Color.red(),
                fields=fields,
                footer_text='Error in set_bot_status',
                channel_id=1159138280651104256
              )
    except Exception as e:
      await asyncio.sleep(15)
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      fields = [
        {
          'name':'Error',
          'value':traceback_msg,
          'inline':False
        }
      ]
      await se.send_embed(
        title='Error in code',
        description=str(e)[:2048],
        color=nextcord.Color.red(),
        fields=fields,
        footer_text='Error in set_bot_status',
        channel_id=1159138280651104256
      )

  @set_bot_status.before_loop
  async def before_set_bot_status(self):
    await self.bot.wait_until_ready()

def setup(bot:commands.Bot):
  bot.add_cog(SetBotStatus(bot))