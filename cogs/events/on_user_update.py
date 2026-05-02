from nextcord import User
from nextcord.ext import commands
# from Utils.get_member_or_user_updated_data import object_to_dict, deep_compare
from Utils.config import users_with_no_acces_for_bot

def format_value(value:dict|list|str, tag=1):
  tag_ = ("#"*tag) if tag<=3 else "-#"
  if isinstance(value, dict):
    return "\n".join(f"\n{tag_} **{key}**: {format_value(val, tag+1)}" for key, val in value.items())
  elif isinstance(value, list):
    return "\n".join(f"\n{tag_} {format_value(val, tag+1)}" for val in value)
  else:
    return f"**{value}**"

class OnUserUpdate(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_user_update(self, before: User, after: User):
    user_id = before.id

    if user_id in users_with_no_acces_for_bot:
      return
    
    gd = self.bot.get_cog("GetData")
    ud = self.bot.get_cog("UpdateData")
    tracker = self.bot.get_cog("ActivityTracker")

    user_settings = await gd.get_data(user_id,['banned'],'users','user_id',None)

    if user_settings['banned']:
      users_with_no_acces_for_bot.append(user_id)
      return
    
    if before.name!=after.name:
      await ud.update_data(user_id, {"username": after.name}, "users", "user_id")
    
    if tracker is None:
      return

    await tracker.handle_user_update(before, after)

def setup(bot:commands.Bot):
  bot.add_cog(OnUserUpdate(bot))