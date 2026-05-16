import nextcord
from nextcord.ext import commands, tasks
from datetime import datetime,timezone
from Utils.config import users
import traceback
from asyncio import sleep
from socket import gaierror

GB_CD = 60
CD = 10
cache_TTL = 60*60
users_TTL = 5*60*60
SLEEP = 10

class GetData(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
    self.last_users_TTL = datetime.now(timezone.utc)
    self.temp_cache = {}
    
  @tasks.loop(seconds=1)
  async def TTL_cache_cleanup(self):
    current_time = datetime.now(timezone.utc).timestamp()
    keys_to_delete = [key for key, value in self.temp_cache.items() if current_time - value["timestamp"] > cache_TTL]
    for key in keys_to_delete:
      del self.temp_cache[key]

    if (datetime.now(timezone.utc) - self.last_users_TTL).total_seconds() > users_TTL:
      users.clear()
      self.last_users_TTL = datetime.now(timezone.utc)

    await sleep(SLEEP/len(self.temp_cache))

  async def get_data(self,user_id:str,data:list,table:str,checker:str,guild:nextcord.Guild=None):
    ensure_guild = self.bot.get_cog("EnsureGuildExists")
    ensure_user = self.bot.get_cog("EnsureUserExists")
    try:
      data_str = ', '.join(data)
      get_user_data = 'None'
      try:
        user = self.bot.get_user(user_id)
      except Exception:
        user = None
      while True:
        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          if guild and not user:
            language = guild.preferred_locale if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'en' if guild.preferred_locale=='en-US' or guild.preferred_locale=='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'es' if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale=='es-ES' and guild.preferred_locale!='sv-SE' else 'sv'
            await ensure_guild.ensure_guild_exists(guild.id)
          elif not guild and user:
            await ensure_user.ensure_user_exists(user_id, user.name)
          elif guild and user:
            if user_id not in users:
              language = guild.preferred_locale if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'en' if guild.preferred_locale=='en-US' or guild.preferred_locale=='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'es' if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale=='es-ES' and guild.preferred_locale!='sv-SE' else 'sv'
              await ensure_guild.ensure_guild_exists(guild.id)
              await ensure_user.ensure_user_exists(user_id,user.name,language,guild)
              users.add(user_id)
          try:
            async with self.bot.db_pool.acquire() as conn:
              async with conn.transaction():
                query = f"SELECT {data_str} FROM {table} WHERE {checker} = $1"
                get_user_data = await conn.fetchrow(query,user_id)

                self.temp_cache[(user_id, data_str, table, checker)] = {
                  "data": {got_data:get_user_data[got_data] for got_data in data if get_user_data and got_data},
                  "timestamp": datetime.now(timezone.utc).timestamp()
                }
                return {got_data:get_user_data[got_data] for got_data in data if get_user_data and got_data}
          except Exception as e:
            if isinstance(e, gaierror) and e.errno in {11001, 11002}:
              return self.temp_cache.get((user_id, data_str, table, checker), {"data": {name:None for name in data}})["data"]
            
            raise e
          break
        else:
          await sleep(10)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
        title=f"PostgreSQL | Error retrieving user data",
        description=(f"{e}")[:500],
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      if guild:
        invite = await self.bot.get_cog("GetInvite").invite(guild)
        log.add_field(
          name="Server",
          value=f"{guild.id} | {invite} | {guild.name}" if guild else "DM",
          inline=False
        )
      if user:
        log.add_field(
          name="User",
          value=f"{user_id} | {user.mention} | {user.name}",
          inline=True
        )
      log.add_field(
        name="Data",
        value=f"Expected: ```json\n{data}```\nReceived: ```json\n{get_user_data}```\nTable: `{table}`\nChecker: `{checker}`",
        inline=True
      )
      log.set_author(
        name=f"ERROR",
      )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
          name="Error",
          value=f"```py\n{traceback_msg[i:i+1000]}```",
          inline=False
        )
      log.set_footer(
        text=f"get_data",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
    return self.temp_cache.get((user_id, data_str, table, checker), {"data": {name:None for name in data}})["data"]

def setup(bot:commands.Bot):
  bot.add_cog(GetData(bot))