import nextcord
from nextcord.ext import commands
from datetime import datetime, timezone

from cogs.utils.ensure_guild_exists import EnsureGuildExists
from cogs.utils.get_invite import GetInvite

class OnGuildRemove(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_guild_remove(self,guild:nextcord.Guild):
    log = nextcord.Embed(
      title=f"Сервер",
      description=f"## **Бот был удален с сервера**",
      color=nextcord.Colour.red(),
      timestamp=datetime.now(timezone.utc)
    )
    if guild:
      await (EnsureGuildExists(self.bot)).ensure_guild_exists(guild.id)
      if guild.me:
        try:
          invite = await (GetInvite(self.bot)).invite(guild)
          log.add_field(
            name="Сервер",
            value=f"{guild.id} | {invite} | {guild.name}",
            inline=False
          )
        except Exception as e:
          log.add_field(
            name="Сервер",
            value=f"{guild.id} | Ошибка получения инвайтов: {e} | {guild.name}",
            inline=False
          )
      else:
        log.add_field(
          name="Сервер",
          value=f"{guild.id} | **API Discord не вернул данные `guild.me`, так что невозможно проверить многие данные.** | {guild.name}",
          inline=False
        )
    else:
      log.add_field(
        name="Сервер",
        value="**API Discord не вернул данные о сервере.**",
        inline=False
      )
    log.set_footer(
      text=f"Сервер #{len(self.bot.guilds)}",
      icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
    )
    await self.bot.get_guild(807304463449849938).get_channel(1149318436615364618).send(embed=log) 

def setup(bot:commands.Bot):
  bot.add_cog(OnGuildRemove(bot))