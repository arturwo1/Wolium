from time import time
from nextcord.ext.commands import Cog, Bot
from nextcord import slash_command, SlashOption, Interaction, Member, Embed, Colour
from Utils.parse_time import parse_time
from Utils.config import slash_command_cooldown
import Utils.translate_to_all_languages
from datetime import datetime, timezone, timedelta
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

class Mute(Cog):
  def __init__(self, bot:Bot):
    self.bot:Bot=bot

  @slash_command(default_member_permissions=536870924,
  description="Mute a user temporarily",
  name_localizations=translate_to_all_languages('moderation.mute_name', 'name'),
  description_localizations=translate_to_all_languages('moderation.mute_desc', 'description'))
  async def mute(self,
    interaction: Interaction,
    member: Member=SlashOption(name="member", description="Member to mute", required=True, name_localizations=translate_to_all_languages('moderation.mute_param_member', 'name'), description_localizations=translate_to_all_languages('moderation.mute_param_member_desc', 'description')),
    duration: str=SlashOption(name="duration", description="Mute duration", required=True, name_localizations=translate_to_all_languages('moderation.mute_param_duration', 'name'), description_localizations=translate_to_all_languages('moderation.mute_param_duration_desc', 'description')),
    reason: str=SlashOption(name="reason", description="Mute reason", required=True, name_localizations=translate_to_all_languages('moderation.mute_param_reason', 'name'), description_localizations=translate_to_all_languages('moderation.mute_param_reason_desc', 'description')),
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

      send_mute_message = await interaction.response.send_message(
        await tm.translate_message("moderation.loading", language),
        ephemeral=True
      )

      duration = parse_time(duration)

      if str(member_id)==str(user_id):
        await send_mute_message.edit(
          await tm.translate_message("moderation.cannot_mute_self", language)
        )
        return

      if interaction.guild.me.guild_permissions.moderate_members==False:
        await send_mute_message.edit(
          await tm.translate_message("moderation.bot_no_mute_perms", language)
        )
        return

      if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<interaction.guild.get_member(member_id).guild_permissions.value:
        await send_mute_message.edit(
          await tm.translate_message("moderation.insufficient_mute_perms", language, variables={"user": f"**{member.mention}**"})
        )
        return

      if duration==None:
        await send_mute_message.edit(
          await tm.translate_message("moderation.invalid_mute_duration", language)
        )
        return

      if duration>2419200:
        await send_mute_message.edit(
          await tm.translate_message("moderation.mute_max_duration", language, variables={"duration": f"`{timedelta(seconds=duration)}`"})
        )
        return

      try:
        member = interaction.guild.get_member(member_id)
        dm = await member.create_dm()
        await dm.send(
          await tm.translate_message("moderation.mute_dm_notification", language, variables={"reason": f"`{reason}`", "duration": f"`{timedelta(seconds=duration)}`"})
        )
      except Exception:
        pass

      try:
        await member.timeout(timeout=timedelta(seconds=duration), reason=reason)
        timestamp = int(interaction.created_at.timestamp())
        await av.add_violation(member_id, interaction.guild.id, "mute", reason, duration, timestamp, user_id)

        success_mute = Embed(
          title=await tm.translate_message("moderation.mute_title", language),
          description=f"""
**{await tm.translate_message("moderation.user", language)}**: **`{member}`**(**{member.mention}**)
**{await tm.translate_message("moderation.reason", language)}**: **`{reason}`**
**{await tm.translate_message("moderation.duration", language)}**: **`{timedelta(seconds=duration)}`**
          """,
          color=Colour.green(),
          timestamp=datetime.now(timezone.utc)
        )
        success_mute.set_footer(
          text=f"Mute",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )
        await send_mute_message.edit('', embed=success_mute)
      except Exception as e:
        await send_mute_message.edit(
          await tm.translate_message("moderation.mute_failed", language, variables={"error": str(e)}),
          ephemeral=True
        )
    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      invite = await gi.invite(interaction.guild)
      
      log = Embed(
        title=f"User: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Command executed: ||/mute member: {member} duration: {duration} reason: {reason}||",
        color=Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.set_author(
        name=f"Guild ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=f"{interaction.user.display_avatar.url}"
      )
      log.add_field(
        name="Guild",
        value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
        inline=False
      )
      log.add_field(
        name="Channel",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'DM'}`)",
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
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)


def setup(bot:Bot):
  bot.add_cog(Mute(bot))