import nextcord
from nextcord.ext import commands
from datetime import datetime,timezone
from cogs.utils.ensure_user_exists import EnsureUserExists
import traceback
from asyncio import sleep

from cogs.utils.get_invite import GetInvite

class EnsureUserDataExists(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  async def ensure_user_data_exists(self,user_id:int,guild:nextcord.Guild=None):
    try:
      try:
        user = self.bot.get_user(user_id)
      except Exception:
        return
      while True:
        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          async with self.bot.db_pool.acquire() as conn:
            if guild:
              language = guild.preferred_locale if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'en' if guild.preferred_locale=='en-US' or guild.preferred_locale=='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'es' if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale=='es-ES' and guild.preferred_locale!='sv-SE' else 'sv'
              await (EnsureUserExists(self.bot)).ensure_user_exists(user_id, user.name,language,guild) 
            if not guild and user:
              await (EnsureUserExists(self.bot)).ensure_user_exists(user_id, user.name)
            await conn.execute(
              "INSERT INTO user_data (user_id) VALUES ($1) "
              "ON CONFLICT (user_id) DO NOTHING",
              user_id
            )
          break
        else:
          await sleep(10)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
        title=f"Postgresql | Ошибка В Привязке Пользователя К Дате",
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
        text=f"{str(datetime.now())}",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
    return

def setup(bot:commands.Bot):
  bot.add_cog(EnsureUserDataExists(bot))