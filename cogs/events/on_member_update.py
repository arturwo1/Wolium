import nextcord
from nextcord.ext import commands
from cogs.utils.get_data import GetData
from cogs.utils.log_member_activity import LogMemberActivity
from Utils.get_member_or_user_updated_data import object_to_dict, deep_compare
from cogs.utils.send_embed import SendEmbed
from cogs.utils.translate_message import TranslateMessage

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
  async def on_member_update(self, before:nextcord.Member, after:nextcord.Member):
    user_id = before.id
    guild_id = before.guild.id
    activity_type = 'update'
    guild =  before.guild
    guild_locale = guild.preferred_locale if guild else None

    before_data = object_to_dict(before)
    after_data = object_to_dict(after)

    changes = deep_compare(before_data, after_data)

    if changes:
      await (LogMemberActivity(self.bot)).log_member_activity(user_id, guild_id, activity_type, changes)
      
      guild_config = await (GetData(self.bot)).get_data(guild_id,['mod_log_channel'],'guild_settings','guild_id',guild)
      mod_log_channel = guild_config['mod_log_channel']
      
      if mod_log_channel and guild and guild.get_channel(mod_log_channel):
        mod_lang = guild_locale if guild_locale !='en-US' and guild_locale !='en-GB' and guild_locale !='es-ES' and guild_locale !='sv-SE' else 'en' if guild_locale =='en-US' or guild_locale =='en-GB' and guild_locale !='es-ES' and guild_locale !='sv-SE' else 'es' if guild_locale !='en-US' and guild_locale !='en-GB' and guild_locale =='es-ES' and guild_locale !='sv-SE' else 'sv'
        fields = [{
            'name':await (TranslateMessage(self.bot)).translate_message('Пользователь',mod_lang),
            'value':f"{user_id} | {before.mention} | {before.name}",
            'inline':False
          }
        ]
        await (SendEmbed(self.bot)).send_embed(
          title=await (TranslateMessage(self.bot)).translate_message("Изменение Пользователя",mod_lang),
          description=str("\n".join(f"# **{key}**:\n{format_value(value, 2)}" for key, value in changes.items()))[:4000],
          color=nextcord.Colour.yellow(),
          fields=fields,
          footer_text=await (TranslateMessage(self.bot)).translate_message("Изменение Пользователя",mod_lang),
          author_text=before.name,
          author_icon=before.display_avatar.url,
          guild_id=guild_id,
          channel_id=mod_log_channel
        )

def setup(bot:commands.Bot):
  bot.add_cog(OnMemberUpdate(bot))