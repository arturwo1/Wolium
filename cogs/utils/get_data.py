from nextcord import Guild, User, Embed, Colour
from nextcord.ext import commands
from datetime import datetime,timezone
from traceback import format_exception

class GetData(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  async def get_data(self,user_id:str,data:list,table:str,checker:str,guild:Guild=None,user:User=None):
    try:
      dm = self.bot.get_cog("DataManager")
      user = user or self.bot.get_user(user_id)
      get_user_data = "None"
      
      get_user_data = await dm.get_row(table, {checker:user_id}, data, guild, user)
      row_data = {got_data: get_user_data[got_data] for got_data in data} if get_user_data else {name: None for name in data}
      return row_data
    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = Embed(
        title=f"PostgreSQL | Error retrieving user data",
        description=(f"{e}")[:500],
        color=Colour.red(),
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
    
    return {name: None for name in data}

def setup(bot:commands.Bot):
  bot.add_cog(GetData(bot))