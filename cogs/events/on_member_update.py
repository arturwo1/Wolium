from nextcord import Member, Colour
from nextcord.ext import commands
from Utils.get_member_or_user_updated_data import object_to_dict, deep_compare
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot

def format_value(value:dict|list|str, tag=1):
  tag_ = ("#"*tag) if tag<=3 else "-#"
  if isinstance(value, dict):
    return "\n".join(f"\n{tag_} **{key}**: {format_value(val, tag+1)}" for key, val in value.items())
  elif isinstance(value, list):
    return "\n".join(f"\n{tag_} {format_value(val, tag+1)}" for val in value)
  else:
    return f"**{value}**"

class OnMemberUpdate(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_member_update(self, before:Member, after:Member):
    user_id = before.id
    guild_id = before.guild.id
    activity_type = 'update'
    guild =  before.guild
    guild_locale = guild.preferred_locale if guild else None

    if guild_id in servers_with_no_acces_for_bot or user_id in users_with_no_acces_for_bot:
      return
    
    log_member_activity =  self.bot.get_cog("LogMemberActivity")
    get_data = self.bot.get_cog("GetData")
    translate_message = self.bot.get_cog("TranslateMessage")
    send_embed = self.bot.get_cog("SendEmbed")
    tracker = self.bot.get_cog("ActivityTracker")

    if guild_id:
      guild_settings = await get_data.get_data(guild_id,['banned'],'guilds','guild_id',before.guild)
    user_settings = await get_data.get_data(user_id,['banned'],'users','user_id',before.guild)

    if user_settings['banned'] or (guild_settings['banned'] if before.guild else False):
      servers_with_no_acces_for_bot.append(guild_id)
      users_with_no_acces_for_bot.append(user_id)
      return
    
    if tracker:
      await tracker.handle_member_update(before, after)

    before_data = object_to_dict(before)
    after_data = object_to_dict(after)

    changes = deep_compare(before_data, after_data)

    if changes:
      await log_member_activity.log_member_activity(user_id, guild_id, activity_type, changes)
      
      guild_config = await get_data.get_data(guild_id,['mod_log_channel'],'guild_settings','guild_id',guild)
      mod_log_channel = guild_config['mod_log_channel']
      
      if mod_log_channel and guild and guild.get_channel(mod_log_channel):
        mod_lang = guild_locale if guild_locale !='en-US' and guild_locale !='en-GB' and guild_locale !='es-ES' and guild_locale !='sv-SE' else 'en' if guild_locale =='en-US' or guild_locale =='en-GB' and guild_locale !='es-ES' and guild_locale !='sv-SE' else 'es' if guild_locale !='en-US' and guild_locale !='en-GB' and guild_locale =='es-ES' and guild_locale !='sv-SE' else 'sv'
        fields = [{
            'name':await translate_message.translate_message('Пользователь',mod_lang),
            'value':f"{user_id} | {before.mention} | {before.name}",
            'inline':False
          }
        ]
        await send_embed.send_embed(
          title=await translate_message.translate_message("Изменение Пользователя",mod_lang),
          description=str("\n".join(f"# **{key}**:\n{format_value(value, 2)}" for key, value in changes.items()))[:4000],
          color=Colour.yellow(),
          fields=fields,
          footer_text=await translate_message.translate_message("Изменение Пользователя",mod_lang),
          author_text=before.name,
          author_icon=before.display_avatar.url,
          guild_id=guild_id,
          channel_id=mod_log_channel
        )

def setup(bot:commands.Bot):
  bot.add_cog(OnMemberUpdate(bot))