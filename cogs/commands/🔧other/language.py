import nextcord
from nextcord import SlashOption, IntegrationType, InteractionContextType
from nextcord.ext import commands
from datetime import datetime, timezone
from time import time
import traceback
import Utils.translate_to_all_languages
from Utils.config import DISCORD_LANGUAGES, slash_command_cooldown

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class Language(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
  
  @nextcord.slash_command(description="Select bot language.",
    name_localizations=translate_to_all_languages('general.language_lower', 'name'),
    description_localizations=translate_to_all_languages('settings.select_bot_language', 'description'),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],)
  async def language(self,
    interaction: nextcord.Interaction,
    language_code: str=SlashOption(name="language_code", description="Choose a language.",required=True, name_localizations=translate_to_all_languages('general.language_lower', 'name'), description_localizations=translate_to_all_languages('general.choose_language', 'description')),
    ephemeral: bool=SlashOption(name="ephemeral", description="Only you see the message or everyone.",required=False,default=False, name_localizations=translate_to_all_languages('general.personally', 'name'), description_localizations=translate_to_all_languages('general.ephemeral_desc_typo', 'description')),
  ):
    try:
      user_id = interaction.user.id
      current_time = time()
      tm = self.bot.get_cog("TranslateMessage")
      ud = self.bot.get_cog("UpdateData")
      gi = self.bot.get_cog("GetInvite")
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

      await interaction.response.defer(ephemeral=ephemeral)

      invite = await gi.invite(interaction.guild) if interaction.guild else "No guild"

      if language_code in DISCORD_LANGUAGES:
        await interaction.followup.send("✔", ephemeral=ephemeral)
        data = {
          'language': language_code
        }
        await ud.update_data(user_id, data, 'users', 'user_id', interaction.guild)
      else:
        await interaction.followup.send("✖", ephemeral=ephemeral)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
        title=f"User: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"User entered command: ||**/language** `language_code`  **{language_code}**||",
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )

      log.set_author(
        name=f"Server ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=f"{interaction.user.display_avatar.url}"
      )
      if interaction.guild:
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
        text=f"cogs.commands.🔧other.language",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      try:
        await interaction.response.send_message(f"An error occurred, error logs saved, will be reviewed soon.", ephemeral=True)
      except Exception:
        await interaction.followup.send(f"An error occurred, error logs saved, will be reviewed soon.", ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

  @language.on_autocomplete("language_code")
  async def languages(self, interaction: nextcord.Interaction, language_code: str):
    LANGUAGES = DISCORD_LANGUAGES
    filtered_language = [LANGUAGES for LANGUAGES in LANGUAGES if language_code.lower() in LANGUAGES.lower()]
    filtered_language = filtered_language[:25]
    await interaction.response.send_autocomplete(filtered_language)

  setattr(language, "extras",{"description": "With this command you can choose the language I will respond in!"})

def setup(bot: commands.Bot):
  bot.add_cog(Language(bot))