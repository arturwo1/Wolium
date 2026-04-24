import asyncio
from nextcord.ext import commands
from nextcord import Guild
from time import time

class GetInvite(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self.invites: dict[str, tuple[str, float]] = {}
    self._locks: dict[str, asyncio.Lock] = {}

  def _get_lock(self, guild_id: str) -> asyncio.Lock:
    if guild_id not in self._locks:
      self._locks[guild_id] = asyncio.Lock()
    return self._locks[guild_id]

  async def invite(self, guild: Guild = None, *args):
    if not guild:
      return "DM"

    gid = str(guild.id)
    now = time()

    if gid in self.invites and self.invites[gid][1] + 60 > now:
      url = self.invites[gid][0]
      return f'[**`invite`**]({url})' if not args else url

    async with self._get_lock(gid):
      now = time()
      if gid in self.invites and self.invites[gid][1] + 60 > now:
        url = self.invites[gid][0]
        return f'[**`invite`**]({url})' if not args else url

      try:
        if not (guild.me and guild.me.guild_permissions.manage_guild):
          return "No permissions to view invites"

        invites = await guild.invites()
        if not invites:
          return "No invites"

        best = next(
          (i for i in invites if i.max_age == 0 and i.max_uses == 0),
          invites[0]
        )
        self.invites[gid] = (best.url, time())
        return f'[**`invite`**]({best.url})' if not args else best.url

      except Exception as e:
        return f"Error {e} while viewing invites"

def setup(bot: commands.Bot):
  bot.add_cog(GetInvite(bot))