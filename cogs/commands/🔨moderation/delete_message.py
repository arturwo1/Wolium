from nextcord.ext import commands
from nextcord import slash_command, SlashOption, Interaction, Member, Embed, Colour, Permissions
from nextcord.errors import Forbidden, HTTPException
from datetime import datetime, timezone, timedelta
from time import time
from asyncio import sleep
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from traceback import format_exception

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

active_purges = set()

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
  description="Delete messages from this channel",
  name_localizations=translate_to_all_languages('moderation.purge_name', 'name'),
  description_localizations=translate_to_all_languages('moderation.purge_desc', 'description'))
  async def purge(self,
    interaction: Interaction,
    amount: int=SlashOption(name="amount", description="Number of messages to delete", required=True, name_localizations=translate_to_all_languages('moderation.purge_param_amount', 'name'), description_localizations=translate_to_all_languages('moderation.purge_param_amount_desc', 'description'), min_value=1),
    member: Member=SlashOption(name="member", description="Only delete this member's messages", required=False, name_localizations=translate_to_all_languages('moderation.purge_param_member', 'name'), description_localizations=translate_to_all_languages('moderation.purge_param_member_desc', 'description')),
  ):
    gi = self.bot.get_cog("GetInvite")
    tm = self.bot.get_cog("TranslateMessage")
    try:
      gd = self.bot.get_cog("GetData")

      user_id = interaction.user.id
      current_time = time()

      user_settings = await gd.get_data(user_id, ['language','variation'], 'users', 'user_id', interaction.guild)
      language = user_settings['language']

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(await tm.translate_message("error.rate_limit", language, variables={"time": f"<t:{round(last_command_time+10)}:R>"}), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      if not interaction.guild:
        await interaction.response.send_message(await tm.translate_message("moderation.purge_guild_only", language), ephemeral=True)
        return

      channel_id = interaction.channel.id

      if channel_id in active_purges:
        await interaction.response.send_message(await tm.translate_message("moderation.purge_already_running", language), ephemeral=True)
        return

      await interaction.response.defer(ephemeral=True)

      channel_perms = interaction.channel.permissions_for(interaction.guild.me)
      if not channel_perms.manage_messages:
        await interaction.followup.send(await tm.translate_message("moderation.purge_no_perms", language), ephemeral=True)
        return

      user_channel_perms = interaction.channel.permissions_for(interaction.user)
      if not user_channel_perms.manage_messages:
        await interaction.followup.send(await tm.translate_message("moderation.purge_user_no_perms", language), ephemeral=True)
        return

      active_purges.add(channel_id)
      try:
        deleted_count = await self._delete_messages(interaction.channel, amount, member)
      except Forbidden:
        await interaction.followup.send(await tm.translate_message("moderation.purge_forbidden", language), ephemeral=True)
        return
      except Exception as e:
        await interaction.followup.send(await tm.translate_message("moderation.purge_error", language, variables={"error": str(e)}), ephemeral=True)
        return
      finally:
        active_purges.discard(channel_id)

      deleted_messages_embed = Embed(
        title=await tm.translate_message("moderation.purge_title", language),
        description=await tm.translate_message("moderation.purge_success", language, variables={"count": f"**`{deleted_count}`**"}) + ((await tm.translate_message("moderation.purge_from_user", language, variables={"count": f"**`{deleted_count}`**", "user": f"{member.mention}"})) if member else "."),
        color=Colour.green(),
        timestamp=datetime.now(timezone.utc)
      )
      deleted_messages_embed.add_field(
        name=await tm.translate_message("moderation.purge_amount", language),
        value=f"**`{deleted_count}`**",
      )
      if member:
        deleted_messages_embed.add_field(
          name=await tm.translate_message("moderation.param_member", language),
          value=f"**{member.mention}**",
        )
      deleted_messages_embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
      deleted_messages_embed.set_footer(text=await tm.translate_message("moderation.purge_count", language)+f" {deleted_count} messages")
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
            'name':await tm.translate_message('moderation.purge_amount', mod_lang),
            'value':f"**`{deleted_count}`**",
            'inline':True
          },
        ]
        await se.send_embed(
          title=await tm.translate_message("moderation.purge_title", mod_lang),
          description=f"**{interaction.user.mention}** deleted **`{deleted_count}`** messages" + (f" from **{member.mention}**" if member else ''),
          color=Colour.red(),
          fields=fields,
          footer_text=await tm.translate_message("moderation.purge_title", mod_lang),
          author_text=interaction.user.name,
          author_icon=interaction.user.display_avatar.url,
          guild_id=interaction.guild.id,
          channel_id=mod_log_channel
        )
    except Exception as e:
      active_purges.discard(interaction.channel.id if interaction.channel else None)
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      invite = await gi.invite(interaction.guild) if interaction.guild else "DM"
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
        await interaction.response.send_message(await tm.translate_message("error.logs_saved", language), ephemeral=True)
      except Exception:
        await interaction.followup.send(await tm.translate_message("error.logs_saved", language), ephemeral=True)

  async def _delete_messages(self, channel, amount: int, member: Member=None) -> int:
    check = (lambda m: m.author.id == member.id) if member else (lambda m: True)
    deleted_count = 0
    scan_limit = 500
    last_message = None

    while deleted_count < amount:
      to_delete = []
      async for msg in channel.history(limit=scan_limit, before=last_message):
        last_message = msg
        if check(msg):
          to_delete.append(msg)
          if len(to_delete) >= (amount - deleted_count):
            break

      if not to_delete:
        break

      two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
      fresh = [m for m in to_delete if m.created_at > two_weeks_ago]
      old = [m for m in to_delete if m.created_at <= two_weeks_ago]

      for i in range(0, len(fresh), 100):
        chunk = fresh[i:i+100]
        try:
          await channel.delete_messages(chunk)
          deleted_count += len(chunk)
        except HTTPException:
          pass
        await sleep(1.2)

      for msg in old:
        while True:
          try:
            await msg.delete()
            deleted_count += 1
            break
          except HTTPException as e:
            retry_after = getattr(e, "retry_after", None) or 1.0
            await sleep(retry_after + 0.2)
        await sleep(0.25)
        if deleted_count >= amount:
          break

    return deleted_count

  setattr(purge,"extras",{"description": "commands.purge.description"})

def setup(bot:commands.Bot):
  bot.add_cog(DeleteMessage(bot))