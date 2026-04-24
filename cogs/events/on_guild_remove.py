import nextcord
from nextcord.ext import commands
from datetime import datetime, timezone

class OnGuildRemove(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_guild_remove(self,guild:nextcord.Guild):
    log = nextcord.Embed(
      title="Server",
      description="Bot was removed from server",
      color=nextcord.Colour.red(),
      timestamp=datetime.now(timezone.utc)
    )
    if guild:
      ege = self.bot.get_cog("EnsureGuildExists")
      gi = self.bot.get_cog("GetInvite")
      await ege.ensure_guild_exists(guild.id)
      if guild.me:
        try:
          invite = await gi.invite(guild)
          log.add_field(
            name="Server",
            value=f"{guild.id} | {invite} | {guild.name}",
            inline=False
          )
        except Exception as e:
          log.add_field(
            name="Server",
            value=f"{guild.id} | Invite fetch error: {e} | {guild.name}",
            inline=False
          )
      else:
        log.add_field(
          name="Server",
          value=f"{guild.id} | **Discord API did not return `guild.me` data, unable to verify data.** | {guild.name}",
          inline=False
        )
    else:
      log.add_field(
        name="Server",
        value="**Discord API did not return server data.**",
        inline=False
      )
    log.set_footer(
      text=f"Server #{len(self.bot.guilds)}",
      icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
    )
    await self.bot.get_guild(807304463449849938).get_channel(1149318436615364618).send(embed=log) 

def setup(bot:commands.Bot):
  bot.add_cog(OnGuildRemove(bot))