from time import time
from nextcord.ext.commands import Cog, Bot
from nextcord import slash_command, SlashOption, Interaction, Member, Embed, Colour
from Utils.parse_time import parse_time
from Utils.config import slash_command_cooldown
import Utils.translate_to_all_languages
from datetime import datetime, timedelta, timezone
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

class Ban(Cog):
  def __init__(self, bot:Bot):
    self.bot:Bot=bot

  @slash_command(default_member_permissions=16,
  description="Ban a user from the server",
  name_localizations=translate_to_all_languages('moderation.ban_name', 'name'),
  description_localizations=translate_to_all_languages('moderation.ban_desc', 'description'))
  async def ban(self,
    interaction: Interaction,
    member: Member=SlashOption(name="user", description="Member to ban",required=True, name_localizations=translate_to_all_languages('moderation.param_user', 'name'), description_localizations=translate_to_all_languages('moderation.param_user_desc', 'description')),
    reason: str=SlashOption(name="reason", description="Ban reason",required=True, name_localizations=translate_to_all_languages('moderation.param_reason', 'name'), description_localizations=translate_to_all_languages('moderation.param_reason_desc', 'description'),max_length=128),
    delete_messages: str=SlashOption(name="delete_messages", description="Delete messages (s,m,h,d,w)",required=False, name_localizations=translate_to_all_languages('moderation.param_purge', 'name'), description_localizations=translate_to_all_languages('moderation.param_purge_desc', 'description'),default=0),
    duration: str=SlashOption(name="duration", description="Ban duration (s,m,h,d,w)",required=False, name_localizations=translate_to_all_languages('moderation.param_duration', 'name'), description_localizations=translate_to_all_languages('moderation.param_duration_desc', 'description'),default=None),
  ):
    try:
      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")
      av = self.bot.get_cog("AddViolation")

      user_id = interaction.user.id
      member_id = member.id
      current_time = time()
      lang = _get_locale(interaction.locale)

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(await tm.translate_message("error.rate_limit", lang, variables={"time": f"<t:{round(last_command_time+10)}:R>"}), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      user_settings = await gd.get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']

      send_ban_message = await interaction.response.send_message(await tm.translate_message("moderation.loading", language),ephemeral=True)
      if str(member_id)==str(user_id):
        await send_ban_message.edit(await tm.translate_message("moderation.cannot_ban_self", language))
        return
      if interaction.guild.me.guild_permissions.ban_members==False:
        await send_ban_message.edit(await tm.translate_message("moderation.bot_no_ban_perms", language))
        return
      if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<interaction.guild.get_member(member_id).guild_permissions.value:
        await send_ban_message.edit(await tm.translate_message("moderation.insufficient_perms", language, variables={"user": member.mention}))
        return

      duration_seconds = parse_time(duration)

      try:
        try:
          member_obj = await self.bot.fetch_user(member_id)
          dm = await member_obj.create_dm()
          await dm.send(await tm.translate_message("moderation.ban_dm_notification", language) + f" `{reason}`")
        except Exception:
          pass
        success_ban = Embed(
          title=await tm.translate_message("moderation.ban_title", language),
          description=f"""
          **{await tm.translate_message("moderation.user", language)}**: **`{member}`**(**{member.mention}**)
          **{await tm.translate_message("moderation.reason", language)}**: **`{reason}`**
          **{await tm.translate_message("moderation.duration", language)}**: **`{timedelta(seconds=duration_seconds)}`**
          """,
          color=Colour.green(),
          timestamp=datetime.now(timezone.utc)
        )
        success_ban.set_footer(
          text=f"Ban",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )

        await interaction.guild.ban(user=member,reason=reason,delete_message_seconds=delete_messages)
        timestamp = int(interaction.created_at.timestamp())
        await av.add_violation(member_id, interaction.guild.id, "ban", reason, duration_seconds, timestamp, user_id)

        await send_ban_message.edit('',embed=success_ban)
      except Exception as e:
        await send_ban_message.edit(await tm.translate_message("moderation.bot_insufficient_perms", language, variables={"user": member.mention, "error": str(e)}))
    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      invite = await gi.invite(interaction.guild)
      log = Embed(
        title=f"User: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Command: ||/ban user: {member} reason: {reason} delete_messages: {delete_messages} duration: {duration}||",
        color=Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.set_author(
        name=f"Server ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=f"{interaction.user.display_avatar.url}"
      )
      log.add_field(
        name="Server",
        value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
        inline=False
      )
      log.add_field(
        name="Channel",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
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
      lang = _get_locale(interaction.locale)
      try:
        await interaction.response.send_message(await tm.translate_message("error.occurred_logs_saved_review", lang), ephemeral=True)
      except Exception:
        await interaction.followup.send(await tm.translate_message("error.occurred_logs_saved_review", lang), ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

def setup(bot:Bot):
  bot.add_cog(Ban(bot))
