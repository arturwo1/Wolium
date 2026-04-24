import nextcord
from nextcord.ext import commands
from datetime import datetime,timezone
import traceback
from asyncio import sleep

class EnsureGuildExists(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  async def ensure_guild_exists(self,guild_id:int):
    try:
      while True:
        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          try:
            async with self.bot.db_pool.acquire() as conn:
              async with conn.transaction():
                await conn.execute(
                  "INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO NOTHING",
                  guild_id
                )
                
                await conn.execute(
                  "INSERT INTO guild_settings (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO NOTHING",
                  guild_id
                )
          except Exception as e:
            await sleep(10)
            continue
          break
        else:
          await sleep(10)
      
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      guild = self.bot.get_guild(guild_id)
      invite = await self.bot.get_cog("GetInvite").invite(guild)
      log = nextcord.Embed(
        title="PostgreSQL | Error adding guild to database",
        description=(f"{e}")[:500],
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.set_author(
        name=f"ERROR",
      )
      log.add_field(
        name="Server",
        value=f"{guild_id} | {invite} | {guild.name}" if guild else "DM",
        inline=False
      )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
          name="Error",
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
  bot.add_cog(EnsureGuildExists(bot))