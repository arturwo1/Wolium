from time import time
from nextcord.ext.commands import Cog, Bot
from nextcord import slash_command, SlashOption, Interaction, User, Embed, Colour
from Utils.config import slash_command_cooldown
import Utils.translate_to_all_languages
from datetime import datetime, timezone
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

class UnBan(Cog):
  def __init__(self, bot:Bot):
    self.bot:Bot=bot

  @slash_command(default_member_permissions=16,
  description="Unban a user",
  name_localizations=translate_to_all_languages('moderation.unban_name', 'name'),
  description_localizations=translate_to_all_languages('moderation.unban_desc', 'description'))
  async def unban(self,
    interaction: Interaction,
    user: User=SlashOption(name="user", description="User to unban", required=True, name_localizations=translate_to_all_languages('moderation.unban_param_user', 'name'), description_localizations=translate_to_all_languages('moderation.unban_param_user_desc', 'description')),
    reason: str=SlashOption(name="reason", description="Unban reason", required=True, name_localizations=translate_to_all_languages('moderation.unban_param_reason', 'name'), description_localizations=translate_to_all_languages('moderation.unban_param_reason_desc', 'description')),
  ):
    try:
      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")
      av = self.bot.get_cog("AddViolation")

      user_id = interaction.user.id
      member_id = user.id
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

      send_unban_message = await interaction.response.send_message(
        await tm.translate_message("moderation.loading", language),
        ephemeral=True
      )

      async with self.bot.db_pool.acquire() as conn:
        mod_id: int = await conn.fetchval(
          "SELECT mod_id FROM violations "
          "WHERE user_id = $1 AND guild_id = $2 AND type = 'ban' "
          "ORDER BY timestamp DESC LIMIT 1;",
          member_id, interaction.guild.id
        )

      if str(member_id)==str(user_id):
        await send_unban_message.edit(
          await tm.translate_message("moderation.cannot_unban_self", language)
        )
        return

      if interaction.guild.me.guild_permissions.ban_members==False:
        await send_unban_message.edit(
          await tm.translate_message("moderation.bot_no_unban_perms", language)
        )
        return

      if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<(interaction.guild.get_member(mod_id).guild_permissions.value if mod_id else 0):
        await send_unban_message.edit(
          await tm.translate_message("moderation.insufficient_unban_perms", language)
        )
        return

      try:
        await interaction.guild.fetch_ban(user)
      except Exception:
        await send_unban_message.edit(
          await tm.translate_message("moderation.user_not_banned", language, variables={"user": f"{user.mention}"})
        )
        return

      try:
        await interaction.guild.unban(user=user, reason=reason)
        timestamp = int(interaction.created_at.timestamp())
        await av.add_violation(member_id, interaction.guild.id, "unban", reason, None, timestamp, user_id)
        try:
          member = await self.bot.fetch_user(member_id)
          dm = await member.create_dm()
          await dm.send(
            await tm.translate_message("moderation.unban_dm_notification", language, variables={
              "reason": f"`{reason}`",
              "server": f"`{interaction.guild.name}`",
              "moderator": f"**{interaction.user.name}**(`{interaction.user.id}`)"
            })
          )
        except Exception:
          pass

        success_unban = Embed(
          title=await tm.translate_message("moderation.unban_title", language),
          description=f"""
**{await tm.translate_message("moderation.user", language)}**: **`{user}`**(**{user.mention}**)
**{await tm.translate_message("moderation.reason", language)}**: **`{reason}`**
          """,
          color=Colour.green(),
          timestamp=datetime.now(timezone.utc)
        )
        success_unban.set_footer(
          text=f"UnBan",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )
        await send_unban_message.edit('', embed=success_unban)
      except Exception as e:
        await send_unban_message.edit(
          await tm.translate_message("moderation.unban_failed", language, variables={"error": str(e)})
        )
    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      invite = await gi.invite(interaction.guild)
      
      log = Embed(
        title=f"User: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Command executed: ||/unban user: {user} reason: {reason}||",
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
  bot.add_cog(UnBan(bot))