from nextcord import Member, Message, Embed, Color, ButtonStyle, TextInputStyle, Interaction, Object
from nextcord.ext import commands
from nextcord.ui import View, Button, Modal, TextInput
from datetime import timedelta
from time import time
from json import loads, dumps
from os import path, makedirs
from uuid import uuid4

import Utils.translate_to_all_languages
from Utils.parse_time import parse_time

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

_VIEWS_FILE = "data/gpt_views.json"

_ACTION_LABELS = {
  'ban':    ('🔨', 'gpt.action_ban'),
  'unban':  ('🔓', 'gpt.action_unban'),
  'kick':   ('👢', 'gpt.action_kick'),
  'mute':   ('🔇', 'gpt.action_mute'),
  'unmute': ('🔊', 'gpt.action_unmute'),
}

def load_views() -> dict:
  if path.exists(_VIEWS_FILE):
    try:
      with open(_VIEWS_FILE) as f:
        return loads(f.read())
    except Exception:
      pass
  return {"violations": {}, "gpt_actions": {}}

def save_views(data: dict):
  makedirs("data", exist_ok=True)
  with open(_VIEWS_FILE, "w") as f:
    f.write(dumps(data))

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
      placeholder=translate_to_all_languages("moderation.timeout_format_hint", 'message', language)
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
        await tm.translate_message("error.less_perms_than_target", self.language, variables={"member": str(self.member.mention)}), ephemeral=True
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
  def __init__(self, view_id: str, member_id: int, user_id: int, guild_id: int, channel_id: int, message_id: int, language: str, reason: str, mod_log_channel: int, rules: str, bot: commands.Bot):
    super().__init__(timeout=None)
    self.view_id = view_id
    self.member_id = member_id
    self.user_id = user_id
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
      ("ban",  "🔨", "gpt.action_ban",  self._ban),
      ("kick", "👢", "gpt.action_kick", self._kick),
      ("mute", "🔇", "gpt.action_mute", self._mute),
      ("warn", "⚠️", "gpt.action_warn", self._warn),
    ]:
      btn = Button(custom_id=f"vv_{cid}_{view_id}", style=ButtonStyle.primary, emoji=emoji, label=translate_to_all_languages(label_key, 'message', language))
      btn.callback = cb
      self.add_item(btn)

  def save(self):
    data = load_views()
    data["violations"][self.view_id] = {
      "member_id": self.member_id,
      "user_id": self.user_id,
      "guild_id": self.guild_id,
      "channel_id": self.channel_id,
      "message_id": self.message_id,
      "language": self.language,
      "reason": self.reason,
      "mod_log_channel": self.mod_log_channel,
      "rules": self.rules,
    }
    save_views(data)

  def delete(self):
    data = load_views()
    data["violations"].pop(self.view_id, None)
    save_views(data)

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
  def __init__(self, view_id: str, user_id: int, action: dict, language: str, bot: commands.Bot):
    super().__init__(timeout=None)
    self.view_id = view_id
    self.user_id = user_id
    self.action = action
    self.language = language
    self.bot = bot
    self.av = self.bot.get_cog("AddViolation")
    self.tm = self.bot.get_cog("TranslateMessage")

    action_type = action.get('action_type', '').lower()
    emoji, label_key = _ACTION_LABELS.get(action_type, ('✅', 'general.confirm'))

    confirm_btn = Button(style=ButtonStyle.success, emoji=emoji, label=translate_to_all_languages(label_key, 'message', language), custom_id=f"gpt_confirm_{view_id}")
    confirm_btn.callback = self.confirm
    cancel_btn = Button(style=ButtonStyle.danger, emoji='❌', label=translate_to_all_languages('general.cancel', 'message', language), custom_id=f"gpt_cancel_{view_id}")
    cancel_btn.callback = self.cancel
    self.add_item(confirm_btn)
    self.add_item(cancel_btn)

  def save(self, guild_id: int, channel_id: int, message_id: int):
    data = load_views()
    data["gpt_actions"][self.view_id] = {
      "action": self.action,
      "language": self.language,
      "guild_id": guild_id,
      "channel_id": channel_id,
      "message_id": message_id,
    }
    save_views(data)

  def delete(self):
    data = load_views()
    data["gpt_actions"].pop(self.view_id, None)
    save_views(data)

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
    if interaction.user.id != self.user_id:
      await interaction.response.send_message(await self.tm.translate_message("error.not_your_interaction", self.language), ephemeral=True)
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
    if interaction.user.id != self.user_id:
      await interaction.response.send_message(await self.tm.translate_message("error.not_your_interaction", self.language), ephemeral=True)
      return
    await interaction.response.defer()
    await self._disable_all(interaction)
    self.delete()
    await interaction.followup.send(await self.tm.translate_message("action.cancelled", self.language), ephemeral=True)