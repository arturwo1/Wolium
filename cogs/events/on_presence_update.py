from nextcord.ext import commands
from nextcord import Member
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot

class OnPresenceUpdate(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_presence_update(self, before: Member, after: Member):
    user_id = before.id
    guild_id = before.guild.id

    if guild_id in servers_with_no_acces_for_bot or user_id in users_with_no_acces_for_bot:
      return
    
    get_data = self.bot.get_cog("GetData")
    tracker = self.bot.get_cog("ActivityTracker")

    if guild_id:
      guild_settings = await get_data.get_data(guild_id,['banned'],'guilds','guild_id',before.guild)
    user_settings = await get_data.get_data(user_id,['banned'],'users','user_id',before.guild)

    if user_settings['banned'] or (guild_settings['banned'] if before.guild else False):
      servers_with_no_acces_for_bot.append(guild_id)
      users_with_no_acces_for_bot.append(user_id)
      return
    
    if tracker is None:
      return

    await tracker.handle_presence_update(after)

def setup(bot:commands.Bot):
  bot.add_cog(OnPresenceUpdate(bot))