from nextcord import Member, Message, Embed, Color, Invite, ButtonStyle, TextInputStyle, Interaction, Object
from nextcord.ext import commands
from nextcord.ui import View, Button, Modal, TextInput
from datetime import datetime, timedelta, timezone
from huggingface_hub import AsyncInferenceClient
from Utils.search_and_scrape import async_web_search_tool
import Utils.translate_to_all_languages
from time import time
from random import randint
from traceback import format_exception
from Utils.config import tools, temperature, max_tokens, top_p, models, history, automod_history, api_keys, rules_data
from Utils.parse_time import parse_time
from asyncio import sleep
from re import search, DOTALL
from json import loads, JSONDecodeError, dumps
from uuid import uuid4
import os

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

_VIEWS_FILE = "data/gpt_views.json"

_RETRYABLE = (
  'Connection aborted', 'Payment Required', 'Bad Gateway',
  'Gateway Timeout', 'overloaded', 'Model too busy', 'Internal Server Error',
)

_ACTION_LABELS = {
  'ban':    ('🔨', 'gpt.action_ban'),
  'unban':  ('🔓', 'gpt.action_unban'),
  'kick':   ('👢', 'gpt.action_kick'),
  'mute':   ('🔇', 'gpt.action_mute'),
  'unmute': ('🔊', 'gpt.action_unmute'),
}

def _get_locale(locale: str) -> str:
  """Normalize Discord locales to supported language codes."""
  if locale in ('en-US', 'en-GB'):
    return 'en'
  elif locale == 'es-ES':
    return 'es'
  elif locale == 'sv-SE':
    return 'sv'
  return 'en'


def _load_views() -> dict:
  if os.path.exists(_VIEWS_FILE):
    try:
      with open(_VIEWS_FILE) as f:
        return loads(f.read())
    except Exception:
      pass
  return {"violations": {}, "gpt_actions": {}}


def _save_views(data: dict):
  os.makedirs("data", exist_ok=True)
  with open(_VIEWS_FILE, "w") as f:
    f.write(dumps(data))


def _make_client(api_keys: list, models: list) -> AsyncInferenceClient:
  return AsyncInferenceClient(
    model=models[randint(0, len(models) - 1)],
    api_key=api_keys[randint(0, len(api_keys) - 1)]
  )


async def _trim_history(items: list, max_size: int = 22):
  await sleep(0)
  while len(items) > max_size:
    del items[1]
  return items


async def _extract_automod_verdict(text: str):
  await sleep(0)
  match = search(r'(True|False)\s*`([^`]*)`', text, DOTALL)
  if match:
    flagged = match.group(1) == "True"
    reason = match.group(2).strip() or None
    return flagged, reason
  return None, None


class MuteModal(Modal):
  def __init__(self, member: Member, language: str, reason: str, message: Message, embed: Embed, bot: commands.Bot, timeout=60 * 5):
    super().__init__(title=translate_to_all_languages("moderation.enter_timeout_duration", 'message', language), timeout=timeout)
    self.bot = bot
    self.member = member
    self.language = language
    self.reason = reason
    self.message = message
    self.embed = embed

    self.duration_input = TextInput(
      label=translate_to_all_languages("general.duration_label", 'message', language),
      style=TextInputStyle.short,
      max_length=28,
      required=True,
      placeholder=translate_to_all_languages(
        "moderation.timeout_format_hint",
        'message', language
      )
    )
    self.add_item(self.duration_input)

  async def callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    tm = self.bot.get_cog("TranslateMessage")
    av = self.bot.get_cog("AddViolation")

    duration = parse_time(self.duration_input.value)

    if not duration:
      await interaction.followup.send(await tm.translate_message("error.invalid_time_format", self.language), ephemeral=True)
      return
    if duration > 60 * 60 * 24 * 7 * 2:
      await interaction.followup.send(await tm.translate_message("error.timeout_max_duration", self.language), ephemeral=True)
      return
    if not interaction.guild or not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await tm.translate_message("error.user_does_not_exist", self.language), ephemeral=True)
      return
    if not getattr(interaction.guild.me.guild_permissions, 'moderate_members', False):
      await interaction.followup.send(await tm.translate_message("error.bot_missing_perms", self.language), ephemeral=True)
      return
    if not getattr(interaction.user.guild_permissions, 'moderate_members', False):
      await interaction.followup.send(await tm.translate_message("error.user_missing_perms", self.language), ephemeral=True)
      return
    if (interaction.user != interaction.guild.owner and
        interaction.user.guild_permissions.value < self.member.guild_permissions.value):
      await interaction.followup.send(
        await self.tm.translate_message("error.less_perms_than_target", self.language, variables={"member": str(self.member.mention)}), ephemeral=True
      )
      return

    try:
      await self.member.timeout(timeout=timedelta(seconds=duration), reason=self.reason)
      await av.add_violation(self.member.id, interaction.guild.id, 'mute', self.reason, duration, round(time()), interaction.user.id)
      try:
        await self.member.send(await tm.translate_message("punishment.timeout_dm", 'en', variables={"duration": str(timedelta(seconds=duration))}))
      except Exception:
        pass
      timeout_text = await tm.translate_message("punishment.timeout_success_until", self.language)
      reason_text = await tm.translate_message("punishment.by_reason", self.language)
      self.embed.add_field(
        name=await tm.translate_message("moderation.verdict", self.language),
        value=await tm.translate_message("mute_modal.verdict", self.language, variables={
          "member": self.member.mention,
          "timeout_text": timeout_text,
          "duration": f"<t:{round(time()) + duration}:R>",
          "reason_text": reason_text,
          "reason": self.reason
        })
      )
      
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await tm.translate_message("error.timeout_failed", self.language), ephemeral=True)


class ViolationsView(View):
  def __init__(self, view_id: str, member_id: int, guild_id: int, channel_id: int, message_id: int, language: str, reason: str, mod_log_channel: int, rules: str, bot: commands.Bot):
    super().__init__(timeout=None)
    self.view_id = view_id
    self.member_id = member_id
    self.guild_id = guild_id
    self.channel_id = channel_id
    self.message_id = message_id
    self.language = language
    self.reason = reason
    self.mod_log_channel = mod_log_channel
    self.rules = rules
    self.bot = bot

    self.tm = self.bot.get_cog("TranslateMessage")
    self.av = self.bot.get_cog("AddViolation")

    for cid, emoji, label_key, cb in [
      ("ban",  "🔨", "gpt.action_ban",     self._ban),
      ("kick", "👢", "gpt.action_kick",    self._kick),
      ("mute", "🔇", "gpt.action_mute",    self._mute),
      ("warn", "⚠️", "gpt.action_warn",    self._warn),
    ]:
      btn = Button(custom_id=f"vv_{cid}_{view_id}", style=ButtonStyle.primary, emoji=emoji, label=translate_to_all_languages(label_key, 'message', language))
      btn.callback = cb
      self.add_item(btn)

  def save(self):
    data = _load_views()
    data["violations"][self.view_id] = {
      "member_id": self.member_id,
      "guild_id": self.guild_id,
      "channel_id": self.channel_id,
      "message_id": self.message_id,
      "language": self.language,
      "reason": self.reason,
      "mod_log_channel": self.mod_log_channel,
      "rules": self.rules,
    }
    _save_views(data)

  def delete(self):
    data = _load_views()
    data["violations"].pop(self.view_id, None)
    _save_views(data)

  async def _get_message_and_embed(self, interaction: Interaction):
    try:
      ch = interaction.guild.get_channel(self.channel_id)
      msg = await ch.fetch_message(self.message_id)
      embed = msg.embeds[0] if msg.embeds else Embed()
      return msg, embed
    except Exception:
      return None, None

  async def _base_checks(self, interaction: Interaction, perm: str) -> bool:
    member = interaction.guild.get_member(self.member_id)

    if not interaction.guild or not member:
      await interaction.followup.send(await self.tm.translate_message("error.user_does_not_exist", self.language), ephemeral=True)
      return False
    if not getattr(interaction.guild.me.guild_permissions, perm, False):
      await interaction.followup.send(await self.tm.translate_message("error.bot_missing_perms", self.language), ephemeral=True)
      return False
    if not getattr(interaction.user.guild_permissions, perm, False):
      await interaction.followup.send(await self.tm.translate_message("error.user_missing_perms", self.language), ephemeral=True)
      return False
    if (interaction.user != interaction.guild.owner and
        interaction.user.guild_permissions.value < member.guild_permissions.value):
      await interaction.followup.send(
        await self.tm.translate_message("error.less_perms_than_target", self.language, variables={"member": str(member.mention)}), ephemeral=True
      )
      return False
    return True

  async def _ban(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if not await self._base_checks(interaction, 'ban_members'):
      return
    member = interaction.guild.get_member(self.member_id)
    msg, embed = await self._get_message_and_embed(interaction)
    try:
      await member.ban(reason=self.reason)
      await self.av.add_violation(member.id, interaction.guild.id, 'ban', self.reason, None, round(time()), interaction.user.id)
      try:
        await member.send(await self.tm.translate_message("punishment.banned_dm", 'en', variables={"reason": self.reason}))
      except Exception:
        pass
      if embed and msg:
        embed.add_field(
          name=await self.tm.translate_message("moderation.verdict", self.language),
          value=await self.tm.translate_message("punishment.ban_success_reason", self.language, variables={"member": str(member.mention), "reason": self.reason})
        )
        await msg.edit(embed=embed)
    except Exception:
      await interaction.followup.send(await self.tm.translate_message("error.ban_failed", self.language), ephemeral=True)

  async def _kick(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if not await self._base_checks(interaction, 'kick_members'):
      return
    member = interaction.guild.get_member(self.member_id)
    msg, embed = await self._get_message_and_embed(interaction)
    try:
      await member.kick(reason=self.reason)
      await self.av.add_violation(member.id, interaction.guild.id, 'kick', self.reason, None, round(time()), interaction.user.id)
      try:
        await member.send(await self.tm.translate_message("punishment.kicked_dm", 'en', variables={"reason": self.reason}))
      except Exception:
        pass
      if embed and msg:
        embed.add_field(
          name=await self.tm.translate_message("moderation.verdict", self.language),
          value=await self.tm.translate_message("punishment.kick_success_reason", self.language, variables={"member": str(member.mention), "reason": self.reason})
        )
        await msg.edit(embed=embed)
    except Exception:
      await interaction.followup.send(await self.tm.translate_message("error.kick_failed", self.language), ephemeral=True)

  async def _mute(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    msg, embed = await self._get_message_and_embed(interaction)
    member = interaction.guild.get_member(self.member_id)
    await interaction.response.send_modal(MuteModal(member, self.language, self.reason, msg, embed, self.bot))

  async def _warn(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if not interaction.guild or not interaction.guild.get_member(self.member_id):
      await interaction.followup.send(await self.tm.translate_message("error.user_does_not_exist", self.language), ephemeral=True)
      return
    member = interaction.guild.get_member(self.member_id)
    if (interaction.user != interaction.guild.owner and
        interaction.user.guild_permissions.value < member.guild_permissions.value):
      await interaction.followup.send(
        await self.tm.translate_message("error.less_perms_than_target", self.language, variables={"member": str(member.mention)}), ephemeral=True
      )
      return
    msg, embed = await self._get_message_and_embed(interaction)
    try:
      await self.av.add_violation(member.id, interaction.guild.id, 'warn', self.reason, None, round(time()), interaction.user.id)
      try:
        await member.send(await self.tm.translate_message("punishment.warned_dm", 'en', variables={"reason": self.reason, "user": str(interaction.user.mention)}))
      except Exception:
        pass
      if embed and msg:
        embed.add_field(
          name=await self.tm.translate_message("moderation.verdict", self.language),
          value=await self.tm.translate_message("punishment.warn_success_reason", self.language, variables={"member": str(member.mention), "reason": self.reason})
        )
        await msg.edit(embed=embed)
    except Exception:
      await interaction.followup.send(await self.tm.translate_message("error.warn_failed", self.language), ephemeral=True)


class GptMuteDurationModal(Modal):
  def __init__(self, member: Member, language: str, reason: str, bot: commands.Bot, timeout=60 * 5):
    super().__init__(title=translate_to_all_languages("moderation.enter_timeout_duration", "message", language), timeout=timeout)
    self.member = member
    self.language = language
    self.reason = reason
    self.bot = bot

    self.duration_input = TextInput(
      label=translate_to_all_languages("general.duration_label", "message", language),
      style=TextInputStyle.short,
      max_length=28,
      required=True,
      placeholder=translate_to_all_languages("moderation.timeout_format_hint", "message", language)
    )
    self.add_item(self.duration_input)

  async def callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    tm = self.bot.get_cog("TranslateMessage")
    av = self.bot.get_cog("AddViolation")
    duration = parse_time(self.duration_input.value)
    if not duration:
      await interaction.followup.send(await tm.translate_message("error.invalid_time_format", self.language), ephemeral=True)
      return
    if duration > 60 * 60 * 24 * 7 * 2:
      await interaction.followup.send(await tm.translate_message("error.timeout_max_duration", self.language), ephemeral=True)
      return
    if not getattr(interaction.guild.me.guild_permissions, 'moderate_members', False):
      await interaction.followup.send(await tm.translate_message("error.bot_missing_perms", self.language), ephemeral=True)
      return
    if not getattr(interaction.user.guild_permissions, 'moderate_members', False):
      await interaction.followup.send(await tm.translate_message("error.user_missing_perms", self.language), ephemeral=True)
      return
    try:
      await self.member.timeout(timeout=timedelta(seconds=duration), reason=self.reason)
      await av.add_violation(self.member.id, interaction.guild.id, 'mute', self.reason, duration, round(time()), interaction.user.id)
      try:
        await self.member.send(await tm.translate_message("mute_modal.dm_timeout", self.language, variables={"duration": str(timedelta(seconds=duration)), "reason": self.reason}))
      except Exception:
        pass
      await interaction.followup.send(await tm.translate_message("punishment.mute_success", self.language, variables={"member": self.member.mention, "duration": str(timedelta(seconds=duration)), "reason": self.reason}))
    except Exception as e:
      await interaction.followup.send(await tm.translate_message("gpt.action_execution_error", self.language, variables={"error": str(e)}), ephemeral=True)


class GptActionConfirmView(View):
  def __init__(self, view_id: str, action: dict, language: str, bot: commands.Bot):
    super().__init__(timeout=None)
    self.view_id = view_id
    self.action = action
    self.language = language
    self.bot = bot

    action_type = action.get('action_type', '').lower()
    emoji, label_key = _ACTION_LABELS.get(action_type, ('✅', 'general.confirm'))

    confirm_btn = Button(style=ButtonStyle.success, emoji=emoji, label=translate_to_all_languages(label_key, 'message', language), custom_id=f"gpt_confirm_{view_id}")
    confirm_btn.callback = self.confirm
    cancel_btn = Button(style=ButtonStyle.danger, emoji='❌', label=translate_to_all_languages('general.cancel', 'message', language), custom_id=f"gpt_cancel_{view_id}")
    cancel_btn.callback = self.cancel

    self.add_item(confirm_btn)
    self.add_item(cancel_btn)

    self.av = self.bot.get_cog("AddViolation")
    self.tm = self.bot.get_cog("TranslateMessage")

  def save(self, guild_id: int, channel_id: int, message_id: int):
    data = _load_views()
    data["gpt_actions"][self.view_id] = {
      "action": self.action,
      "language": self.language,
      "guild_id": guild_id,
      "channel_id": channel_id,
      "message_id": message_id,
    }
    _save_views(data)

  def delete(self):
    data = _load_views()
    data["gpt_actions"].pop(self.view_id, None)
    _save_views(data)

  async def _disable_all(self, interaction: Interaction):
    for item in self.children:
      item.disabled = True
    try:
      await interaction.message.edit(view=self)
    except Exception:
      pass

  async def confirm(self, interaction: Interaction):
    if interaction.response.is_done():
      return

    action_type = self.action.get('action_type', '').lower()
    reason = self.action.get('reason') or await self.tm.translate_message("general.no_reason", self.language)
    duration = self.action.get('duration') or 0
    raw_user_id = self.action.get('user_id', '')

    try:
      user_id = int(raw_user_id)
    except (ValueError, TypeError):
      await interaction.response.send_message(await self.tm.translate_message("gpt.cannot_determine_user", self.language), ephemeral=True)
      return

    if action_type == 'mute' and not duration:
      member = interaction.guild.get_member(user_id)
      if not member:
        await interaction.response.send_message(await self.tm.translate_message("error.user_not_found_on_server", self.language), ephemeral=True)
        return
      await interaction.response.send_modal(GptMuteDurationModal(member, self.language, reason, self.bot))
      await self._disable_all(interaction)
      self.delete()
      return

    await interaction.response.defer()

    try:
      if action_type == 'ban':
        member = interaction.guild.get_member(user_id)
        if not member:
          await interaction.followup.send(await self.tm.translate_message("error.user_not_found_cross", self.language), ephemeral=True); return
        if not getattr(interaction.guild.me.guild_permissions, 'ban_members', False):
          await interaction.followup.send(await self.tm.translate_message("error.bot_missing_ban_perms", self.language), ephemeral=True); return
        if not getattr(interaction.user.guild_permissions, 'ban_members', False):
          await interaction.followup.send(await self.tm.translate_message("error.user_missing_ban_perms", self.language), ephemeral=True); return
        await member.ban(reason=reason)
        await self.av.add_violation(member.id, interaction.guild.id, 'ban', reason, None, round(time()), interaction.user.id)
        try:
          await member.send(await self.tm.translate_message("punishment.banned_dm", self.language, variables={"reason": reason}))
        except Exception:
          pass
        await interaction.followup.send(await self.tm.translate_message("punishment.ban_success", self.language, variables={"member": member.mention, "reason": reason}))

      elif action_type == 'unban':
        if not getattr(interaction.guild.me.guild_permissions, 'ban_members', False):
          await interaction.followup.send(await self.tm.translate_message("error.bot_missing_unban_perms", self.language), ephemeral=True); return
        if not getattr(interaction.user.guild_permissions, 'ban_members', False):
          await interaction.followup.send(await self.tm.translate_message("error.user_missing_unban_perms", self.language), ephemeral=True); return
        await interaction.guild.unban(Object(id=user_id), reason=reason)
        await interaction.followup.send(await self.tm.translate_message("punishment.unban_success", self.language, variables={"user_id": user_id, "reason": reason}))

      elif action_type == 'kick':
        member = interaction.guild.get_member(user_id)
        if not member:
          await interaction.followup.send(await self.tm.translate_message("error.user_not_found_cross", self.language), ephemeral=True); return
        if not getattr(interaction.guild.me.guild_permissions, 'kick_members', False):
          await interaction.followup.send(await self.tm.translate_message("error.bot_missing_kick_perms", self.language), ephemeral=True); return
        if not getattr(interaction.user.guild_permissions, 'kick_members', False):
          await interaction.followup.send(await self.tm.translate_message("error.user_missing_kick_perms", self.language), ephemeral=True); return
        await member.kick(reason=reason)
        await self.av.add_violation(member.id, interaction.guild.id, 'kick', reason, None, round(time()), interaction.user.id)
        try:
          await member.send(await self.tm.translate_message("punishment.kicked_dm", self.language, variables={"reason": reason}))
        except Exception:
          pass
        await interaction.followup.send(await self.tm.translate_message("punishment.kick_success", self.language, variables={"member": member.mention, "reason": reason}))

      elif action_type == 'mute':
        member = interaction.guild.get_member(user_id)
        if not member:
          await interaction.followup.send(await self.tm.translate_message("error.user_not_found_cross", self.language), ephemeral=True); return
        if not getattr(interaction.guild.me.guild_permissions, 'moderate_members', False):
          await interaction.followup.send(await self.tm.translate_message("error.bot_missing_timeout_perms", self.language), ephemeral=True); return
        if not getattr(interaction.user.guild_permissions, 'moderate_members', False):
          await interaction.followup.send(await self.tm.translate_message("error.user_missing_timeout_perms", self.language), ephemeral=True); return
        await member.timeout(timeout=timedelta(seconds=duration), reason=reason)
        await self.av.add_violation(member.id, interaction.guild.id, 'mute', reason, duration, round(time()), interaction.user.id)
        try:
          await member.send(await self.tm.translate_message("punishment.timeout_dm", self.language, variables={"duration": str(timedelta(seconds=duration)), "reason": reason}))
        except Exception:
          pass
        await interaction.followup.send(await self.tm.translate_message("punishment.mute_success", self.language, variables={"member": member.mention, "duration": str(timedelta(seconds=duration)), "reason": reason}))

      elif action_type == 'unmute':
        member = interaction.guild.get_member(user_id)
        if not member:
          await interaction.followup.send(await self.tm.translate_message("error.user_not_found_cross", self.language), ephemeral=True); return
        if not getattr(interaction.guild.me.guild_permissions, 'moderate_members', False):
          await interaction.followup.send(await self.tm.translate_message("error.bot_missing_perms_short", self.language), ephemeral=True); return
        if not getattr(interaction.user.guild_permissions, 'moderate_members', False):
          await interaction.followup.send(await self.tm.translate_message("error.user_missing_perms_cross", self.language), ephemeral=True); return
        await member.timeout(timeout=None, reason=reason)
        await interaction.followup.send(await self.tm.translate_message("punishment.unmute_success", self.language, variables={"member": member.mention, "reason": reason}))

      else:
        await interaction.followup.send(await self.tm.translate_message("error.unknown_action_type", self.language), ephemeral=True)
        return

      await self._disable_all(interaction)
      self.delete()

    except Exception as e:
      await interaction.followup.send(await self.tm.translate_message("gpt.action_execution_error", self.language, variables={"error": str(e)}), ephemeral=True)

  async def cancel(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    await self._disable_all(interaction)
    self.delete()
    await interaction.followup.send(await self.tm.translate_message("action.cancelled", self.language), ephemeral=True)


class GPT(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot

  @commands.Cog.listener()
  async def on_ready(self):
    data = _load_views()

    for view_id, d in data.get("violations", {}).items():
      view = ViolationsView(
        view_id=view_id,
        member_id=d["member_id"],
        guild_id=d["guild_id"],
        channel_id=d["channel_id"],
        message_id=d["message_id"],
        language=d["language"],
        reason=d["reason"],
        mod_log_channel=d["mod_log_channel"],
        rules=d.get("rules", ""),
        bot=self.bot
      )
      self.bot.add_view(view)

    for view_id, d in data.get("gpt_actions", {}).items():
      view = GptActionConfirmView(
        view_id=view_id,
        action=d["action"],
        language=d["language"],
        bot=self.bot
      )
      self.bot.add_view(view)

  async def GPT(self, message: Message, language: str, invite: Invite, retries: int = 0):
    global history, models, api_keys

    tm = self.bot.get_cog("TranslateMessage")

    if not api_keys:
      return None, await tm.translate_message('gpt.no_tokens', language)

    client = _make_client(api_keys, models)

    try:
      if message.reference:
        ref_msg = (
          message.reference.cached_message or
          await message.channel.fetch_message(message.reference.message_id)
        )
        reference_block = f'''
          "Reference": {{
            "Content": "{ref_msg.content}",
            "Author Name": "{ref_msg.author.name}",
            "Author Display Name": "{ref_msg.author.display_name}",
            "Author ID": "{ref_msg.author.id}"
          }},'''
      else:
        reference_block = ""
    except Exception:
      return None, await tm.translate_message('gpt.reply_too_old', language)

    source_block = (
      f'"Source": {{"Server": "{message.guild.name}", "Server ID": "{message.guild.id}", '
      f'"Channel": "{message.channel.name}", "Channel ID": "{message.channel.id}"}}'
      if message.guild else '"Source": "DM"'
    )
    perms_block = (
      f'"can_ban": {message.author.guild_permissions.ban_members}, '
      f'"can_mute": {message.author.guild_permissions.mute_members}, '
      f'"can_kick": {message.author.guild_permissions.kick_members}'
      if message.guild else ''
    )

    user_message_content = f'''{{
      "User": {{"Name": "{message.author.name}", "Display Name": "{message.author.display_name}", "ID": "{message.author.id}"}},
      "Message": {{"Content": "{message.content}", "ID": "{message.id}"}},
      {source_block},
      "Additional": {{"Time": "{message.created_at} UTC+0", {perms_block}, "User_Language": "{language}"}}{reference_block}
    }}'''

    history.append({"role": "user", "content": user_message_content})

    response_text = ""
    action_view = None

    try:
      for _ in range(6):
        completion = await client.chat.completions.create(
          model=client.model,
          messages=history,
          max_tokens=max_tokens,
          temperature=temperature,
          top_p=top_p,
          tools=tools,
          tool_choice="auto"
        )

        msg = completion.choices[0].message
        response_text = msg.content or ""
        tool_calls = getattr(msg, 'tool_calls', None) or []

        if not tool_calls:
          history.append({"role": "assistant", "content": response_text})
          break

        history.append({
          "role": "assistant",
          "content": response_text,
          "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in tool_calls
          ]
        })

        for tc in tool_calls:
          fn_name = tc.function.name
          try:
            args = loads(tc.function.arguments)
          except JSONDecodeError:
            args = {}

          if fn_name == "search_and_scrape":
            query = args.get("query", "")
            try:
              result = await async_web_search_tool(query)
              tool_result = str(result)
            except Exception as e:
              tool_result = f"Search error: {e}"
            history.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result})

          elif fn_name == "perform_moderation_action":
            action_user_id = args.get("user_id", "")
            action_type = args.get("action_type", "")

            if str(action_user_id) == str(self.bot.user.id):
              history.append({"role": "tool", "tool_call_id": tc.id, "content": "Cannot perform action on self."})
              response_text = await tm.translate_message('gpt.cannot_apply_to_self', language, variables={"action_type": action_type})
              continue

            view_id = str(uuid4())[:8]
            action_view = GptActionConfirmView(view_id=view_id, action=args, language=language, bot=self.bot)
            history.append({"role": "tool", "tool_call_id": tc.id, "content": "Action queued for user confirmation."})

        await _trim_history(history)

    except Exception as e:
      traceback_msg = ''.join(format_exception(type(e), e, e.__traceback__))[:5000]
      log = Embed(title=await tm.translate_message("gpt.ai_error_title", language), description=str(e)[:500], color=Color.red(), timestamp=datetime.now(timezone.utc))
      if message.guild:
        log.add_field(name="Server", value=f"{message.guild.id} | {message.guild.name}", inline=False)
        log.add_field(name="Channel", value=f"{message.channel.name} | {message.channel.id}", inline=False)
      log.add_field(name="Error", value=f"**```py\n{traceback_msg[:800]}```**", inline=False)
      await self.bot.get_channel(1159138280651104256).send(embed=log)
      return None, await tm.translate_message('gpt.generation_error', language)

    return action_view, response_text

  async def automod(self, message: Message, language: str, invite: Invite, guild_config: dict, retries: int = 0):
    global automod_history, models, api_keys

    if not api_keys:
      return

    client = _make_client(api_keys, models)
    channel_id = guild_config['mod_log_channel']
    rules: str = guild_config.get('rules', '')
    guild_id = message.guild.id

    try:
      tm = self.bot.get_cog("TranslateMessage")
      if str(guild_id) not in automod_history:
        rules_header = await tm.translate_message('gpt.rules_header', language)
        automod_history[str(guild_id)] = [{
          "role": "system",
          "content": f"{rules_header}\n\n{rules or 'Prohibited: Insults, Spam, Profanity, Advertising, Flood, Disrespect to Staff, Threats, Discrimination and other violations.'}\n\n{rules_data}"
        }]

      source_block = (
        f'"Source": {{"Channel": "{message.channel.name}"}}'
        if message.guild else '"Source": "DM"'
      )

      user_message_content = f'''{{
        "User": {{"Name": "{message.author.name}", "Display Name": "{message.author.display_name}"}},
        "Message": {{"Content": "{message.content}"}},
        {source_block},
        "Additional": {{"Time": "{message.created_at} UTC+0", "User_Language": "{language}"}}
      }}'''

      automod_history[str(guild_id)].append({"role": "user", "content": user_message_content})

      response = await client.chat.completions.create(
        model=client.model,
        messages=automod_history[str(guild_id)],
        temperature=temperature,
        max_tokens=100,
        top_p=top_p
      )
      response_text = response.choices[0].message.content

      automod_history[str(guild_id)].append({"role": "assistant", "content": response_text})
      await _trim_history(automod_history[str(guild_id)])

      flagged, reason = await _extract_automod_verdict(response_text)
      if not flagged:
        return

      try:
        await message.delete()
      except Exception:
        pass

      tm = self.bot.get_cog("TranslateMessage")
      se = self.bot.get_cog("SendEmbed")

      fields = [
        {
          'name': await tm.translate_message('general.channel', language),
          'value': f"{message.channel.id} | {message.channel.mention} | {message.channel.name}",
          'inline': True
        },
        {
          'name': await tm.translate_message('report.user_message', language),
          'value': str(message.content),
          'inline': True
        },
      ]
      if reason:
        fields.append({
          'name': await tm.translate_message('punishment.violation_reason', language),
          'value': str(await tm.translate_message(reason, language, save=False))[:1000],
          'inline': True
        })

      reason_translated = await tm.translate_message(reason, language, save=False) if reason else ''
      msg_label = await tm.translate_message('general.message', language)
      suspicious_label = await tm.translate_message('automod.suspected_suspicious', language)
      text_label = await tm.translate_message('general.text_label', language)
      counts_label = await tm.translate_message('automod.what_it_counts', language)

      description = (
        f"## {msg_label} **{message.author.mention}** {suspicious_label}\n"
        f"### {text_label}\n-# {message.content}\n"
        f"### {counts_label}\n-# {reason_translated}"
      )[:4000]

      embed_message, embed = await se.send_embed(
        title=await tm.translate_message("automod.title", language),
        description=description,
        color=Color.orange(),
        fields=fields,
        footer_text=await tm.translate_message("automod.title", language),
        author_text=message.author.name,
        author_icon=message.author.display_avatar.url,
        guild_id=guild_id,
        channel_id=channel_id
      )

      view_id = str(uuid4())[:8]
      view = ViolationsView(
        view_id=view_id,
        member_id=message.author.id,
        guild_id=guild_id,
        channel_id=embed_message.channel.id,
        message_id=embed_message.id,
        language=language,
        reason=reason,
        mod_log_channel=channel_id,
        rules=rules,
        bot=self.bot
      )
      view.save()
      self.bot.add_view(view)
      await embed_message.edit(embed=embed, view=view)

    except Exception as e:
      try:
        automod_history[str(guild_id)].pop()
      except Exception:
        pass

      err_str = str(e)
      if any(marker in err_str for marker in _RETRYABLE):
        if retries < 5:
          await self.automod(message, language, invite, guild_config, retries + 1)
        return

      traceback_msg = ''.join(format_exception(type(e), e, e.__traceback__))[:5000]
      tm = self.bot.get_cog("TranslateMessage")
      log = Embed(
        title=await tm.translate_message("gpt.ai_automod_error_title", language),
        description=f"{client.model if client else 'AI'}: {e}"[:500],
        color=Color.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.set_author(name="ERROR")
      log.add_field(name="Server", value=f"{message.guild.id} | {invite} | {message.guild.name}" if message.guild else "DM", inline=False)
      log.add_field(
        name="Channel",
        value=f"<#{message.channel.id}> (`{message.channel.id}` | `{getattr(message.channel, 'name', None) or f'[<@{message.author.id}>]'}`)",
        inline=False
      )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(name="Error", value=f"```py\n{traceback_msg[i:i + 1000]}```", inline=False)
      log.set_footer(
        text="AI | AutoMod",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)


def setup(bot: commands.Bot):
  bot.add_cog(GPT(bot))