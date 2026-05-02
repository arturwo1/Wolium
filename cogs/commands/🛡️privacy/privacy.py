from datetime import datetime, timezone
from time import time
from traceback import format_exception

from nextcord import Embed, IntegrationType, InteractionContextType, slash_command, Interaction, Color, ButtonStyle, SelectOption
from nextcord.ui import View, Button, Select
from nextcord.ext import commands

import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from Utils.privacy_flags import SECTION_ORDER, SECTION_LABELS, FLAG_DEPENDENCIES, SECTION_FLAGS, FLAG_TEXTS, PRESETS, VALID_FLAGS

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _locale_to_language(locale: str) -> str:
  if locale in ("en-US", "en-GB"):
    return "en"
  if locale == "es-ES":
    return "es"
  if locale == "sv-SE":
    return "sv"
  return locale

def _state_emoji(value: bool) -> str:
  return "🟢" if value else "🔴"

def _state_style(value: bool) -> ButtonStyle:
  return ButtonStyle.green if value else ButtonStyle.red

def _t(text, lang):
  result = translate_to_all_languages(text, "message", lang)
  return result if isinstance(result, str) else str(result.get(lang, text))

class PrivacySectionSelect(Select):
  def __init__(self, view: "PrivacySettingsView"):
    self.view_ref = view
    options = []
    for section in SECTION_ORDER:
      label = _t(SECTION_LABELS[section], view.language)
      options.append(
        SelectOption(
          label=label,
          value=section,
          default=(section == view.section),
        )
      )
    super().__init__(
      placeholder=_t("privacy.select_section", view.language),
      options=options,
      row=0,
    )

  async def callback(self, interaction: Interaction):
    await self.view_ref.set_section(interaction, self.values[0])

class PrivacyToggleButton(Button):
  def __init__(self, view: "PrivacySettingsView", flag: str, label: str, row: int = 1):
    self.view_ref = view
    self.flag = flag
    value = view.privacy.get(flag, False)
    dependency = FLAG_DEPENDENCIES.get(flag)
    disabled = bool(dependency and not view.privacy.get(dependency, False))
    super().__init__(
      style=_state_style(value),
      label=label,
      emoji=_state_emoji(value),
      row=row,
      disabled=disabled,
    )

  async def callback(self, interaction: Interaction):
    await self.view_ref.toggle_flag(interaction, self.flag)

class PrivacyPresetButton(Button):
  def __init__(self, view: "PrivacySettingsView", preset_key: str, label: str, row: int = 4):
    self.view_ref = view
    self.preset_key = preset_key
    super().__init__(
      style=ButtonStyle.secondary,
      label=label,
      row=row,
    )

  async def callback(self, interaction: Interaction):
    await self.view_ref.apply_preset(interaction, self.preset_key)

class PrivacyResetButton(Button):
  def __init__(self, view: "PrivacySettingsView", label: str, row: int = 4):
    self.view_ref = view
    super().__init__(
      style=ButtonStyle.danger,
      label=label,
      row=row,
    )

  async def callback(self, interaction: Interaction):
    await self.view_ref.reset_all(interaction)

class PrivacySettingsView(View):
  def __init__(self, user_id: int, user_name: str, avatar_url: str, language: str, privacy: dict, update_data, timeout: int = 300):
    super().__init__(timeout=timeout)
    self.user_id = user_id
    self.user_name = user_name
    self.avatar_url = avatar_url
    self.language = language
    self.privacy = privacy
    self.update_data = update_data
    self.section = "overview"
    self.refresh_components()

  def normalize_dependencies(self):
    for child, parent in FLAG_DEPENDENCIES.items():
      if self.privacy.get(child, False) and not self.privacy.get(parent, False):
        self.privacy[parent] = True
      if not self.privacy.get(parent, False):
        self.privacy[child] = False

  def refresh_components(self):
    self.clear_items()
    self.add_item(PrivacySectionSelect(self))

    for idx, flag in enumerate(SECTION_FLAGS.get(self.section, []), start=1):
      label = _t(FLAG_TEXTS[flag], self.language)
      self.add_item(PrivacyToggleButton(self, flag, label, row=idx))

    self.add_item(
      PrivacyPresetButton(
        self,
        "private",
        _t("privacy.preset_strict", self.language),
      )
    )
    self.add_item(
      PrivacyPresetButton(
        self,
        "balanced",
        _t("privacy.preset_balanced", self.language),
      )
    )
    self.add_item(
      PrivacyPresetButton(
        self,
        "analytics",
        _t("privacy.preset_analytics", self.language),
      )
    )
    self.add_item(
      PrivacyResetButton(
        self,
        _t("privacy.reset_all", self.language),
      )
    )

  async def interaction_check(self, interaction: Interaction) -> bool:
    if interaction.user.id != self.user_id:
      if not interaction.response.is_done():
        await interaction.response.send_message(
          _t("privacy.menu_not_yours", self.language),
          ephemeral=True,
        )
      return False
    return True

  async def set_section(self, interaction: Interaction, section: str):
    self.section = section
    self.refresh_components()
    await interaction.response.edit_message(embed=await self.build_embed(), view=self)

  async def toggle_flag(self, interaction: Interaction, flag: str):
    await interaction.response.defer()

    current = bool(self.privacy.get(flag, False))
    self.privacy[flag] = not current
    self.normalize_dependencies()

    changes = {flag: self.privacy[flag]}
    for child, parent in FLAG_DEPENDENCIES.items():
      if flag == parent and not self.privacy.get(parent, False):
        self.privacy[child] = False
        changes[child] = False

    for key, value in changes.items():
      await self.update_data.update_data(
        self.user_id,
        {key: value},
        "user_privacy",
        "user_id",
        interaction.guild,
      )

    self.refresh_components()
    await interaction.edit_original_message(embed=await self.build_embed(), view=self)


  async def apply_preset(self, interaction: Interaction, preset_key: str):
    await interaction.response.defer()

    preset = PRESETS[preset_key].copy()
    self.privacy.update(preset)
    self.normalize_dependencies()

    for key, value in preset.items():
      await self.update_data.update_data(
        self.user_id,
        {key: value},
        "user_privacy",
        "user_id",
        interaction.guild,
      )

    self.refresh_components()
    await interaction.edit_original_message(embed=await self.build_embed(), view=self)


  async def reset_all(self, interaction: Interaction):
    await interaction.response.defer()

    for key in list(self.privacy.keys()):
      self.privacy[key] = False
      await self.update_data.update_data(
        self.user_id,
        {key: False},
        "user_privacy",
        "user_id",
        interaction.guild,
      )

    self.refresh_components()
    await interaction.edit_original_message(embed=await self.build_embed(), view=self)

  async def build_embed(self) -> Embed:
    title = _t("privacy.title", self.language)
    section_name = _t(SECTION_LABELS[self.section], self.language)

    lines = []

    if self.section == "overview":
      lines.append(_t("privacy.overview_description", self.language))
      lines.append("")
      for section in SECTION_ORDER[1:]:
        flags = SECTION_FLAGS[section]
        enabled = sum(1 for f in flags if self.privacy.get(f, False))
        total = len(flags)
        lines.append(
          f"• **{_t(SECTION_LABELS[section], self.language)}** — {enabled}/{total}"
        )
      lines.append("")
      lines.append(_t("privacy.overview_footer", self.language))
    else:
      lines.append(_t("privacy.section_instructions", self.language))
      lines.append("")
      for flag in SECTION_FLAGS[self.section]:
        value = self.privacy.get(flag, False)
        dep = FLAG_DEPENDENCIES.get(flag)
        label = _t(FLAG_TEXTS[flag], self.language)
        line = f"{_state_emoji(value)} **{label}**"
        if dep and not self.privacy.get(dep, False):
          parent_label = _t(FLAG_TEXTS[dep], self.language)
          line += f"\n  └ {_t('privacy.depends_on', self.language)}: **{parent_label}**"
        lines.append(str(line))

    footer = _t(
      "privacy.save_info_footer",
      self.language,
    )

    embed = Embed(
      title=title,
      description="\n".join(map(str, lines)),
      color=Color.blurple(),
      timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
      name=_t("privacy.current_section", self.language),
      value=section_name,
      inline=False,
    )
    embed.set_author(
      name=self.user_name,
      icon_url=self.avatar_url,
    )
    embed.set_footer(text=footer)
    return embed

class Privacy(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @slash_command(
    description="Manage your privacy settings",
    name_localizations=translate_to_all_languages("privacy.command_name", "name"),
    description_localizations=translate_to_all_languages("privacy.command_desc", "description"),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],
  )
  async def privacy(self, interaction: Interaction):
    try:
      user_id = interaction.user.id
      current_time = time()

      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")
      se = self.bot.get_cog("SendEmbed")
      ud = self.bot.get_cog("UpdateData")
      if not (tm and gd and gi and se and ud):
        return

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]["time"]
        if current_time - last_command_time < 10:
          locale = _locale_to_language(interaction.locale)
          await interaction.response.send_message(
            await tm.translate_message("error.rate_limit", locale, variables={"time": f"<t:{round(last_command_time + 10)}:R>"}),
            ephemeral=True,
          )
          return
        slash_command_cooldown[user_id]["time"] = current_time
      else:
        slash_command_cooldown[user_id] = {"time": current_time}

      user_settings = await gd.get_data(user_id, ["language"], "users", "user_id", interaction.guild)
      language = user_settings["language"]

      user_privacy = await gd.get_data(
        user_id,
        list(VALID_FLAGS),
        "user_privacy",
        "user_id",
        interaction.guild,
      )

      view = PrivacySettingsView(
        user_id=user_id,
        user_name=interaction.user.name,
        avatar_url=interaction.user.display_avatar.url,
        language=language,
        privacy=user_privacy,
        update_data=ud,
      )
      embed = await view.build_embed()

      await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    except Exception as e:
      invite = await gi.invite(interaction.guild)
      traceback_msg = "".join(format_exception(type(e), e, e.__traceback__))[:5000]
      fields = [
        {
          "name": "User",
          "value": f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          "inline": True,
        },
        {
          "name": "Server",
          "value": f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
          "inline": True,
        },
        {
          "name": "Channel",
          "value": f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'DM'}`)",
          "inline": True,
        },
        {
          "name": "Error",
          "value": traceback_msg,
          "inline": False,
        },
      ]
      await se.send_embed(
        title=f"Error in command /{interaction.application_command.name}",
        description=str(e)[:2048],
        color=Color.red(),
        fields=fields,
        footer_text="Error in privacy command",
        author_text="ERROR",
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256,
      )
      locale = _locale_to_language(interaction.locale)
      error_text = await tm.translate_message("error.occurred_logs_saved_review", locale)
      if interaction.response.is_done():
        await interaction.followup.send(error_text, ephemeral=True)
      else:
        await interaction.response.send_message(error_text, ephemeral=True)

  setattr(
    privacy,
    "extras",
    {"description": "Configure what data the bot is allowed to collect about your activity."},
  )

def setup(bot: commands.Bot):
  bot.add_cog(Privacy(bot))
