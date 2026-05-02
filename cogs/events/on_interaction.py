import nextcord
from nextcord.ext import commands
from datetime import datetime, timezone
from traceback import format_exception
from Utils.components_v2 import Container, TextDisplay, Separator, V2Sender

content_map = {
  "economy_help": {
    "title_key": "help.economy.title",
    "description_key": "help.economy.description",
    "fields": [
      ("help.economy.work.title", "help.economy.work.value"),
      ("help.economy.balance.title", "help.economy.balance.value"),
      ("help.economy.transfer.title", "help.economy.transfer.value"),
      ("help.economy.leaderboard.title", "help.economy.leaderboard.value"),
      ("help.economy.tip.title", "help.economy.tip.value")
    ]
  },
  "mod_help": {
    "title_key": "help.mod.title",
    "description_key": "help.mod.description",
    "fields": [
      ("help.mod.core.title", "help.mod.core.value"),
      ("help.mod.settings.title", "help.mod.settings.value"),
      ("help.mod.automod.title", "help.mod.automod.value"),
      ("help.mod.reports.title", "help.mod.reports.value"),
      ("help.mod.chat_magic.title", "help.mod.chat_magic.value")
    ]
  },
  "social_help": {
    "title_key": "help.social.title",
    "description_key": "help.social.description",
    "fields": [
      ("help.social.profile.title", "help.social.profile.value"),
      ("help.social.graphs.title", "help.social.graphs.value"),
      ("help.social.translator.title", "help.social.translator.value"),
      ("help.social.link.title", "help.social.link.value"),
      ("help.social.fun.title", "help.social.fun.value")
    ]
  },
  "ai_help": {
    "title_key": "help.ai.title",
    "description_key": "help.ai.description",
    "fields": [
      ("help.ai.chat.title", "help.ai.chat.value"),
      ("help.ai.web.title", "help.ai.web.value"),
      ("help.ai.memory.title", "help.ai.memory.value"),
      ("help.ai.toggle.title", "help.ai.toggle.value")
    ]
  },
  "privacy_help": {
    "title_key": "help.privacy.title",
    "description_key": "help.privacy.description",
    "fields": [
      ("help.privacy.default.title", "help.privacy.default.value"),
      ("help.privacy.enabled.title", "help.privacy.enabled.value"),
      ("help.privacy.panel.title", "help.privacy.panel.value"),
      ("help.privacy.note.title", "help.privacy.note.value")
    ]
  },
  "getting_started": {
    "title_key": "help.start.title",
    "description_key": "help.start.description",
    "fields": [
      ("help.start.activation.title", "help.start.activation.value"),
      ("help.start.permissions.title", "help.start.permissions.value"),
      ("help.start.logs.title", "help.start.logs.value"),
      ("help.start.language.title", "help.start.language.value"),
      ("help.start.learn_more.title", "help.start.learn_more.value")
    ]
  },
  "faq_help": {
    "title_key": "help.faq.title",
    "description_key": "help.faq.description",
    "fields": [
      ("help.faq.errors.title", "help.faq.errors.value"),
      ("help.faq.codes.title", "help.faq.codes.value"),
      ("help.faq.permissions.title", "help.faq.permissions.value"),
      ("help.faq.cooldown.title", "help.faq.cooldown.value"),
      ("help.faq.ai.title", "help.faq.ai.value")
    ]
  }
}

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class OnComponentInteraction(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  async def _handle_welcome_select(self, interaction: nextcord.Interaction):
    tm = self.bot.get_cog("TranslateMessage")
    lang = _get_locale(interaction.locale)

    values = interaction.data.get("values", [])
    if not values:
      return

    selected_value = values[0]

    content = content_map.get(selected_value)
    if not content:
      await interaction.response.send_message(
        await tm.translate_message("welcome.category_not_found", lang),
        ephemeral=True
      )
      return

    title = await tm.translate_message(content["title_key"], lang)
    description = await tm.translate_message(content["description_key"], lang)

    fields = []
    for field_name_key, field_value_key in content["fields"]:
      field_name = await tm.translate_message(field_name_key, lang)
      field_value = await tm.translate_message(field_value_key, lang)
      fields.append((field_name, field_value))

    container = Container(accent_color=0x5865F2, spoiler=False)

    container.add(TextDisplay(f"# {title}"))
    container.add(Separator(spacing=1, divider=False))
    container.add(TextDisplay(description))
    container.add(Separator(spacing=2, divider=True))

    for field_name, field_value in fields:
      container.add(TextDisplay(f"{field_name}\n{field_value}"))
      container.add(Separator(spacing=1, divider=False))

    container.add(Separator(spacing=1, divider=True))
    container.add(TextDisplay(await tm.translate_message("help.footer", lang)))

    try:
      sender = V2Sender(self.bot)
      await sender.send_msg(interaction, [container], ephemeral=True)
    except Exception:
      embed = nextcord.Embed(
        title=title,
        description=description,
        color=nextcord.Colour.blurple(),
        timestamp=datetime.now(timezone.utc)
      )
      for field_name, field_value in fields:
        embed.add_field(name=field_name, value=field_value, inline=False)

      await interaction.response.send_message(embed=embed, ephemeral=True)

  @commands.Cog.listener()
  async def on_interaction(self, interaction: nextcord.Interaction):
    try:
      if interaction.type == nextcord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        if not custom_id:
          return
        if custom_id == "welcome_menu_select":
          await self._handle_welcome_select(interaction)

    except Exception as e:
      traceback_msg = ''.join(format_exception(type(e), e, e.__traceback__))[:2000]
      error_log = nextcord.Embed(
        title="Error in on_interaction",
        description=str(e)[:500],
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      error_log.add_field(name="Trace", value=f"```py\n{traceback_msg}```", inline=False)
      try:
        await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=error_log)
      except:
        print(f"Component interaction error: {e}")

def setup(bot: commands.Bot):
  bot.add_cog(OnComponentInteraction(bot))