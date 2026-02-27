import nextcord
from nextcord.ext import commands
from cogs.utils.ensure_guild_exists import EnsureGuildExists
from cogs.utils.ensure_user_exists import EnsureUserExists
from cogs.utils.log_member_activity import LogMemberActivity
from Utils.config import users

class OnMemberRemove(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_member_remove(self,member:nextcord.Member):
    user_id = member.id
    guild = member.guild
    guild_id = guild.id
    if guild:
      if user_id not in users:
        language = guild.preferred_locale if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'en' if guild.preferred_locale=='en-US' or guild.preferred_locale=='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'es' if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale=='es-ES' and guild.preferred_locale!='sv-SE' else 'sv'
        await (EnsureGuildExists(self.bot)).ensure_guild_exists(guild.id)
        await (EnsureUserExists(self.bot)).ensure_user_exists(user_id,member.name,language,guild) 
        users.add(user_id)
    elif not guild and member:
      await (EnsureUserExists(self.bot)).ensure_user_exists(user_id, member.name)
    activity_type = 'leave'
    data = {
      "user": member.name,
      "guild": guild.name
    }
    await (LogMemberActivity(self.bot)).log_member_activity(user_id, guild_id, activity_type, data)

def setup(bot:commands.Bot):
  bot.add_cog(OnMemberRemove(bot))