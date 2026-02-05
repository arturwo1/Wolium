import nextcord
from nextcord.ext import commands
from datetime import datetime,timezone
from cogs.utils.ensure_guild_exists import EnsureGuildExists
from cogs.utils.ensure_user_exists import EnsureUserExists
from cogs.utils.ensure_user_data_exists import EnsureUserDataExists
from cogs.utils.ensure_guild_user_exists import EnsureGuildUserExists
from Utils.config import users
import traceback
from asyncio import sleep

from cogs.utils.get_invite import GetInvite

class GetData(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
    
  async def get_data(self,user_id:str,data:list,table:str,checker:str,guild:nextcord.Guild=None):
    try:
      data_str = ', '.join(data)
      get_user_data = 'None'
      try:
        user = self.bot.get_user(user_id)
      except Exception:
        user = None
      while True:
        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          async with self.bot.db_pool.acquire() as conn:
            if guild and not user:
              language = guild.preferred_locale if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'en' if guild.preferred_locale=='en-US' or guild.preferred_locale=='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'es' if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale=='es-ES' and guild.preferred_locale!='sv-SE' else 'sv'
              await (EnsureGuildExists(self.bot)).ensure_guild_exists(guild.id)
            elif not guild and user:
              await (EnsureUserExists(self.bot)).ensure_user_exists(user_id, user.name)
              await (EnsureUserDataExists(self.bot)).ensure_user_data_exists(user_id)
            elif guild and user:
              if user_id not in users:
                language = guild.preferred_locale if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'en' if guild.preferred_locale=='en-US' or guild.preferred_locale=='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'es' if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale=='es-ES' and guild.preferred_locale!='sv-SE' else 'sv'
                await (EnsureGuildExists(self.bot)).ensure_guild_exists(guild.id)
                await (EnsureUserExists(self.bot)).ensure_user_exists(user_id,user.name,language,guild) 
                await (EnsureGuildUserExists(self.bot)).ensure_guild_user_exists(guild.id, user_id)
                await (EnsureUserDataExists(self.bot)).ensure_user_data_exists(user_id, guild)
                users.add(user_id)

            query = f"SELECT {data_str} FROM {table} WHERE {checker} = $1"
            get_user_data = await conn.fetchrow(query,user_id)
            return {got_data:get_user_data[got_data] for got_data in data}
          break
        else:
          await sleep(10)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
        title=f"Postgresql | Ошибка при получении данных пользователя",
        description=(f"{e}")[:500],
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      if guild:
        invite = await (GetInvite(self.bot)).invite(guild)
        log.add_field(
          name="Сервер",
          value=f"{guild.id} | {invite} | {guild.name}" if guild else "ЛС",
          inline=False
        )
      if user:
        log.add_field(
          name="Пользователь",
          value=f"{user_id} | {user.mention} | {user.name}",
          inline=True
        )
      log.add_field(
        name="Данные",
        value=f"Изначально: ```json\n{data}```\nПолучено: ```json\n{get_user_data}```\nТаблица: `{table}`\nЧекер: `{checker}`",
        inline=True
      )
      log.set_author(
        name=f"ЕРРОР",
      )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
          name="Ошибка",
          value=f"```py\n{traceback_msg[i:i+1000]}```",
          inline=False
        )
      log.set_footer(
        text=f"get_data",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
    return None

def setup(bot:commands.Bot):
  bot.add_cog(GetData(bot))