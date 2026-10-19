from nextcord import Interaction
from nextcord.ext import commands
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot

def get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class ApplicationCommandCheck(commands.Cog):
  def __init__(self, bot:commands.Bot):
    self.bot = bot

    bot.add_application_command_check(self.application_command_check)

  def cog_unload(self):
    self.bot.remove_application_command_check(self.application_command_check)

  async def application_command_check(self, interaction: Interaction) -> bool:
    lang = get_locale(interaction.locale)
    dm = self.bot.get_cog("DataManager")
    tm = self.bot.get_cog("TranslateMessage")

    user = interaction.user
    guild = interaction.guild

    if not (dm and tm):
      text = await tm.translate_message("error.module_loading_failed", lang) if tm else "Module loading failed."
      await interaction.response.send_message(text, ephemeral=True)
      return False

    if ((guild.id if guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
      await interaction.response.send_message(await tm.translate_message("error.banned_by_bot", lang), ephemeral=True)
      return False

    guild_settings = {}
    if guild:
      guild_settings = await dm.get_row("guilds", {"guild_id": guild.id}, ["banned"], guild=guild, user=user) or {}

    user_settings = await dm.get_row("users", {"user_id": user.id}, ["language", "variation", "banned", "interacted"], guild=guild, user=user) or {}
    language = user_settings.get("language", lang)

    if not user_settings.get("interacted", False):
      language = lang
      await dm.set_fields("users", {"user_id": user.id}, {"language": language, "interacted": True}, ttl_seconds=600, guild=guild, user=user)

    user_banned = bool(user_settings.get("banned", False))
    guild_banned = bool(guild_settings.get("banned", False))
    if user_banned or guild_banned:
      await interaction.response.send_message(await tm.translate_message("error.banned_by_bot", language), ephemeral=True)
      if guild_banned and guild:
        servers_with_no_acces_for_bot.append(guild.id)
      if user_banned:
        users_with_no_acces_for_bot.append(user.id)
      return False

    return True

def setup(bot:commands.Bot):
  bot.add_cog(ApplicationCommandCheck(bot))