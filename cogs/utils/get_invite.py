from nextcord.ext import commands
from nextcord import Guild
from time import time

class GetInvite(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self.invites: dict[str, tuple[str, float]] = {}

  async def invite(self,guild:Guild=None,*args):
    if guild:
      try:
        if str(guild.id) in self.invites and self.invites[str(guild.id)][1] + 60 > time():
          return '[**`инвайт`**]('+str(self.invites[str(guild.id)][0])+')' if not args else str(self.invites[str(guild.id)][0])
        
        if guild.me and guild.me.guild_permissions.manage_guild:
          invites = await guild.invites()
          if invites:
            invite_url = invites[0].url
            self.invites[str(guild.id)] = (invite_url, time())
            return '[**`инвайт`**]('+str(invite_url)+')' if not args else str(invite_url)
          else:
            return "Нет инвайтов"
        else:
          return "Нет прав для просмотра инвайтов"
      except Exception as e:
        return f"Ошибка {e} при просмотре инвайтов"
    return "ЛС"

def setup(bot:commands.Bot):
  bot.add_cog(GetInvite(bot))