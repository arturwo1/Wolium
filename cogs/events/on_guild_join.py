import nextcord
from nextcord.ext import commands
from datetime import datetime, timezone
from Utils.components_v2 import Container, ActionRow, TextDisplay, Separator, Select, V2Sender
from traceback import format_exception
from helper import get_general

feature_keys = [
  "welcome.feature_1",
  "welcome.feature_2",
  "welcome.feature_3",
  "welcome.feature_4"
]

select_keys = [
  ("privacy_help", "welcome.select.privacy.label", "welcome.select.privacy.description"),
  ("mod_help", "welcome.select.mod.label", "welcome.select.mod.description"),
  ("social_help", "welcome.select.social.label", "welcome.select.social.description"),
  ("economy_help", "welcome.select.economy.label", "welcome.select.economy.description"),
  ("ai_help", "welcome.select.ai.label", "welcome.select.ai.description"),
  ("faq_help", "welcome.select.faq.label", "welcome.select.faq.description"),
  ("getting_started", "welcome.select.start.label", "welcome.select.start.description")
]

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class OnGuildJoin(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  async def _send_welcome_components_v2(self, guild: nextcord.Guild):
    tm = self.bot.get_cog("TranslateMessage")
    lang = _get_locale(guild.preferred_locale)

    welcome_title = await tm.translate_message("welcome.title", lang)
    welcome_desc = await tm.translate_message("welcome.description", lang)
    features_text = await tm.translate_message("welcome.features", lang)
    commands_text = await tm.translate_message("welcome.commands", lang)

    container = Container(accent_color=0x5865F2, spoiler=False)

    container.add(TextDisplay(f"# 🎉 {welcome_title}"))
    container.add(Separator(spacing=1, divider=False))
    container.add(TextDisplay(welcome_desc))
    container.add(Separator(spacing=1, divider=False))

    container.add(TextDisplay(f"## ⚡ {features_text}"))

    for feature_key in feature_keys:
      feature_text = await tm.translate_message(feature_key, lang)
      container.add(TextDisplay(feature_text))

    container.add(Separator(spacing=2, divider=True))
    container.add(TextDisplay(f"## 🎮 {commands_text}"))

    select_options = []
    for value, label_key, desc_key in select_keys:
      select_options.append({
        "label": await tm.translate_message(label_key, lang),
        "value": value,
        "description": await tm.translate_message(desc_key, lang)
      })

    select = Select(
      c_type=3,
      custom_id="welcome_menu_select",
      placeholder=await tm.translate_message("welcome.select.placeholder", lang),
      options=select_options,
      min_values=1,
      max_values=1
    )

    action_row = ActionRow()
    action_row.add(select)
    container.add(action_row)

    container.add(Separator(spacing=1, divider=False))
    container.add(TextDisplay(await tm.translate_message("welcome.footer", lang)))

    general = await get_general(guild, self.bot, None)
    if not general:
      return

    try:
      sender = V2Sender(self.bot)
      await sender.send_to_channel(general, [container])
    except Exception:
      fallback_embed = nextcord.Embed(
        title=await tm.translate_message("welcome.title", lang),
        description=await tm.translate_message("welcome.description", lang),
        color=nextcord.Colour.blurple()
      )
      await general.send(embed=fallback_embed)

  @commands.Cog.listener()
  async def on_guild_join(self, guild: nextcord.Guild):
    try:
      log = nextcord.Embed(
        title="Server",
        description="Bot was added to server",
        color=nextcord.Colour.green(),
        timestamp=datetime.now(timezone.utc)
      )
      if guild:
        await self.bot.get_cog("EnsureGuildExists").ensure_guild_exists(guild.id)
        if guild.me:
          try:
            invite = await self.bot.get_cog("GetInvite").invite(guild)

            log.add_field(
              name="Server",
              value=f"{guild.id} | {invite} | {guild.name}",
              inline=False
            )
          except Exception as e:
            log.add_field(
              name="Server",
              value=f"{guild.id} | Invite fetch error: {e} | {guild.name}",
              inline=False
            )
        else:
          log.add_field(
            name="Server",
            value=f"{guild.id} | **Discord API did not return `guild.me` data, unable to verify data.** | {guild.name}",
            inline=False
          )
      else:
        log.add_field(
          name="Server",
          value="**Discord API did not return server data.**",
          inline=False
        )
      log.set_footer(
        text=f"Server #{len(self.bot.guilds)}",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      await self.bot.get_guild(807304463449849938).get_channel(1149318436615364618).send(embed=log)

      if guild:
        await self._send_welcome_components_v2(guild)

    except Exception as e:
      traceback_msg = ''.join(format_exception(type(e), e, e.__traceback__))[:2000]
      error_log = nextcord.Embed(
        title="Error in on_guild_join",
        description=str(e)[:500],
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      error_log.add_field(name="Trace", value=f"```py\n{traceback_msg}```", inline=False)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=error_log)

def setup(bot: commands.Bot):
  bot.add_cog(OnGuildJoin(bot))