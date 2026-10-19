from nextcord import slash_command, Interaction
from nextcord.ext.commands import Cog, Bot
from Utils.translate_to_all_languages import translate_to_all_languages
from Utils.bunker import flags, MAX_GUILD_SESSIONS, BunkerSession, build_main_view, build_permission_error_view, get_missing_permission_keys

class Bunker(Cog):
  def __init__(self, bot: Bot):
    self.bot = bot

  @slash_command(
    description="Start a new Bunker game.",
    name_localizations=translate_to_all_languages('commands.fun.bunker.name', 'name'),
    description_localizations=translate_to_all_languages('commands.fun.bunker.description', 'description'),
  )
  async def bunker(self, interaction: Interaction) -> None:
    await interaction.response.defer()

    utils = self.bot.get_cog("BunkerUtils")
    lang = await utils.get_lang(interaction)
    strings = await utils.get_strings(lang)
    guild = interaction.guild

    if await utils.has_active_session(interaction.user.id):
      await interaction.followup.send(strings["already_has_active_game"], ephemeral=True)
      return

    if await utils.count_guild_sessions(guild.id) >= MAX_GUILD_SESSIONS:
      await interaction.followup.send(strings["guild_game_limit_reached"], ephemeral=True)
      return

    settings, category_id = await utils.load_base_settings(guild, interaction.user)

    if not category_id and not guild.me.guild_permissions.manage_channels:
      missing = await utils.translate_permission_labels(["bunker.permissions.manage_channels"], lang)
      await interaction.followup.send(components=[build_permission_error_view(missing, strings)], flags=flags)
      return

    category = await utils.resolve_category(guild, interaction.user, category_id, lang)
    if category is None:
      missing = await utils.translate_permission_labels(["bunker.permissions.manage_channels"], lang)
      await interaction.followup.send(components=[build_permission_error_view(missing, strings)], flags=flags)
      return

    missing_keys = get_missing_permission_keys(category.permissions_for(guild.me))
    if missing_keys:
      missing = await utils.translate_permission_labels(missing_keys, lang)
      await interaction.followup.send(components=[build_permission_error_view(missing, strings, category.name)], flags=flags)
      return

    session = BunkerSession(guild.id, interaction.user.id, settings)
    session.category_id = category.id
    session.channel_id = interaction.channel.id

    difficulty_options = await utils.get_difficulty_options(lang)
    component = build_main_view(session, strings, difficulty_options)
    message = await interaction.followup.send(components=[component], flags=flags)
    session.message_id = message.id
    await utils.save_session(session)

  setattr(bunker, "extras", {"description": "commands.fun.bunker.detailed_description"})

def setup(bot: Bot) -> None:
  bot.add_cog(Bunker(bot))