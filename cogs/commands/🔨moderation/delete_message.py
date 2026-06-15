from nextcord.ext import commands
from nextcord import slash_command, SlashOption, Interaction, Member, Embed, Colour, Permissions
from nextcord.errors import Forbidden
from datetime import datetime, timezone
from time import time
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from traceback import format_exception

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class DeleteMessage(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  @slash_command(default_member_permissions=Permissions(send_messages=True, manage_messages=True),
  description="Delete messages from a channel",
  name_localizations=translate_to_all_languages('moderation.purge_name', 'name'),
  description_localizations=translate_to_all_languages('moderation.purge_desc', 'description'))
  async def purge(self,
    interaction: Interaction,
    amount: int=SlashOption(name="amount", description="Number of messages to delete", required=True, name_localizations=translate_to_all_languages('moderation.purge_param_amount', 'name'), description_localizations=translate_to_all_languages('moderation.purge_param_amount_desc', 'description'), min_value=1, max_value=100),
    reason: str=SlashOption(name="reason", description="Deletion reason", required=False, name_localizations=translate_to_all_languages('moderation.purge_param_reason', 'name'), description_localizations=translate_to_all_languages('moderation.purge_param_reason_desc', 'description'), max_length=256),
    member: Member=SlashOption(name="member", description="Member messages to delete", required=False, name_localizations=translate_to_all_languages('moderation.purge_param_member', 'name'), description_localizations=translate_to_all_languages('moderation.purge_param_member_desc', 'description')),
    bulk: bool=SlashOption(name="bulk", description="Delete all at once? (limit 2 weeks)", name_localizations=translate_to_all_languages('moderation.purge_param_bulk', 'name'), description_localizations=translate_to_all_languages('moderation.purge_param_bulk_desc', 'description'), default=True),
  ):
    try:
      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")

      user_id = interaction.user.id
      current_time = time()
      lang = _get_locale(interaction.locale)

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(
            await tm.translate_message("error.rate_limit", lang, variables={"time": f"<t:{round(last_command_time+10)}:R>"}),
            ephemeral=True
          )
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      user_settings = await gd.get_data(user_id, ['language','variation'], 'users', 'user_id', interaction.guild)
      language = user_settings['language']

      await interaction.response.defer(ephemeral=True)

      if not interaction.guild:
        await interaction.followup.send(
          await tm.translate_message("moderation.purge_guild_only", language),
          ephemeral=True
        )
        return

      if not interaction.guild.me.guild_permissions.manage_messages:
        await interaction.followup.send(
          await tm.translate_message("moderation.purge_no_perms", language),
          ephemeral=True
        )
        return

      if not interaction.user.guild_permissions.manage_messages:
        await interaction.followup.send(
          await tm.translate_message("moderation.purge_user_no_perms", language),
          ephemeral=True
        )
        return

      invite = await gi.invite(interaction.guild)

      try:
        if member:
          messages = await interaction.channel.purge(limit=amount, check=lambda m: m.author.id == member.id, bulk=bulk)
        else:
          messages = await interaction.channel.purge(limit=amount, bulk=bulk)
      except Forbidden:
        await interaction.followup.send(
          await tm.translate_message("moderation.purge_forbidden", language),
          ephemeral=True
        )
        return
      except Exception as e:
        await interaction.followup.send(
          await tm.translate_message("moderation.purge_error", language, variables={"error": str(e)}),
          ephemeral=True
        )
        return

      reason = str(reason) if reason else "No reason"
      deleted_messages_embed = Embed(
        title=await tm.translate_message("moderation.purge_title", language),
        description=await tm.translate_message("moderation.purge_success", language, variables={"count": f"**`{len(messages)}`**"}) + ((await tm.translate_message("moderation.purge_from_user", language, variables={"count": f"**`{len(messages)}`**", "user": f"{member.mention}"})) if member else "."),
        color=Colour.green(),
        timestamp=datetime.now(timezone.utc)
      )
      deleted_messages_embed.add_field(
        name=await tm.translate_message("moderation.param_reason", language),
        value=reason,
      )
      deleted_messages_embed.add_field(
        name=await tm.translate_message("moderation.purge_amount", language),
        value=f"**`{len(messages)}`**",
      )
      if member:
        deleted_messages_embed.add_field(
          name=await tm.translate_message("moderation.param_member", language),
          value=f"**{member.mention}**",
        )
      deleted_messages_embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
      deleted_messages_embed.set_footer(text=await tm.translate_message("moderation.purge_count", language)+f" {len(messages)} messages")
      await interaction.followup.send(embed=deleted_messages_embed, ephemeral=True)

      guild_config = await gd.get_data(interaction.guild.id, ['mod_log_channel'], 'guild_settings', 'guild_id', interaction.guild)
      mod_log_channel = guild_config['mod_log_channel']
      if mod_log_channel and interaction.guild and interaction.guild.get_channel(mod_log_channel):
        mod_lang = _get_locale(interaction.locale)
        se = self.bot.get_cog("SendEmbed")
        fields = [({
            'name':await tm.translate_message('general.member', mod_lang),
            'value':f"{member.id} | {member.mention} | {member.name}",
            'inline':False
          } if member else {}),
          {
            'name':await tm.translate_message('moderation.param_reason', mod_lang),
            'value':reason,
            'inline':True
          },
          {
            'name':await tm.translate_message('moderation.purge_amount', mod_lang),
            'value':f"**`{len(messages)}`**",
            'inline':True
          },
        ]
        await se.send_embed(
          title=await tm.translate_message("moderation.purge_title", mod_lang),
          description=f"**{interaction.user.mention}** deleted **`{len(messages)}`** messages" + (" from "+f" **{member.mention}**," if member else ', ') + f" reason: {reason}",
          color=Colour.red(),
          fields=fields,
          footer_text=await tm.translate_message("moderation.purge_title", mod_lang),
          author_text=interaction.user.name,
          author_icon=interaction.user.display_avatar.url,
          guild_id=interaction.guild.id,
          channel_id=mod_log_channel
        )
    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      invite = await gi.invite(interaction.guild)
      se = self.bot.get_cog("SendEmbed")
      
      fields = [
        {
          'name':'User',
          'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline':True
        },
        {
          'name':'Server',
          'value':f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
          'inline':True
        },
        {
          'name':'Channel',
          'value':f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'DM'}`)",
          'inline':True
        },
        {
          'name':'Error',
          'value':traceback_msg,
          'inline':False
        }
      ]
      await se.send_embed(
        title=f"Error executing /{interaction.application_command.name}",
        description=str(e)[:2048],
        color=Colour.red(),
        fields=fields,
        footer_text=f'Error in cogs.commands.🔨moderation.delete_message',
        author_text='ERROR',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      try:
        await interaction.response.send_message(
          await tm.translate_message("error.logs_saved", lang),
          ephemeral=True
        )
      except Exception:
        await interaction.followup.send(
          await tm.translate_message("error.logs_saved", lang),
          ephemeral=True
        )

  setattr(purge,"extras",{"description": "commands.purge.description"})

def setup(bot:commands.Bot):
  bot.add_cog(DeleteMessage(bot))