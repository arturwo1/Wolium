import logging
import random
from datetime import datetime, timezone
from hashlib import sha1
from types import SimpleNamespace
from uuid import uuid4
from asyncio import CancelledError, Lock, create_task, gather, sleep, wait_for
from json import dumps, loads
from time import monotonic, time
from typing import Optional

from nextcord import NotFound, InteractionType, ChannelType, CategoryChannel, PermissionOverwrite, Forbidden, HTTPException, Interaction, Guild, Member, Color, MessageType
from nextcord.components import Container, TextDisplay, Separator, SelectOption, Button
from nextcord.enums import ButtonStyle, SeparatorSpacingSize
from nextcord.ext.commands import Cog, Bot
from nextcord.ext.tasks import loop
from nextcord.http import Route

from Utils.bunker import (
  BunkerSession, flags,

  PHASE_INITIAL_DISCUSSION, PHASE_REVEAL, PHASE_DISCUSSION, PHASE_VOTING, PHASE_TIEBREAK, PHASE_PAUSE, PHASE_FINISHED,

  CATEGORY_NAME_KEY, CATEGORY_CREATE_REASON_KEY, GAME_CHANNEL_CREATE_REASON_KEY, GAME_CHANNEL_NAME_PREFIX_KEY, THREAD_DEFAULT_NAME_KEY, THREAD_CREATE_REASON_KEY,

  SESSION_KEY_PREFIX, SESSION_TTL_SECONDS, session_key, MATCH_RECORD_PREFIX, MATCH_RECORD_TTL_SECONDS, MATCH_RECOVERY_BATCH, MATCH_RECOVERY_INTERVAL_MINUTES,
  FINISHED_GRACE_SECONDS, match_record_key, build_match_record, encode_payload, client_payload, format_iso, GAME_STATUS_FINISHED, GAME_STATUS_TIMEOUT,

  CHAT_MESSAGE_LIMIT, BOT_REACTION_MIN_SECONDS, BOT_REACTION_MAX_SECONDS, BOARD_CHUNK_LIMIT, HEAL_INTERVAL_SECONDS, HEAL_BUDGET, REPAIR_BUDGET,
  REPAIR_COOLDOWN_SECONDS, HEAL_BACKOFF_MAX_SECONDS, OUTBOX_LIMIT, OUTBOX_MAX_ATTEMPTS, MAX_THREAD_RETRY_ATTEMPTS, MIN_EXTRA_PLAYERS_OVER_CAPACITY,
  GENERATION_PROGRESS_SECONDS, PROGRESS_STAGE_STEPS, PROGRESS_STAGE_KEYS, AI_TEASER_LIMIT, AI_SUMMARY_LIMIT, ACTIVITY_PATH_TEMPLATE,

  AI_STORY_KEY, AI_STORY_DEFAULT, ANONYMITY_KEY, ANONYMITY_DEFAULT, CATASTROPHE_KEY, CATASTROPHE_DEFAULT, DIFFICULTY_OPTIONS, ANONYMITY_OPTIONS,
  AI_STORY_OPTIONS, SETTINGS_CATEGORIES, build_catastrophe_options, get_setting_entry, format_setting_display, format_setting_edit_default,
  validate_setting_value,

  TRAIT_CARD_KEYS, TRAIT_EMOJIS, remaining_trait_types, get_reveal_choice_parts, choose_random_trait_to_reveal, choose_random_vote_target,

  assign_catastrophe_and_cards, phase_duration, phase_timing_lines, quote_text, pack_text_blocks, to_int, get_locale, get_missing_permission_keys,
  build_game_channel_name, build_player_thread_name, clip_text, sanitize_channel_title, sanitize_ai_text, parse_story_response, progress_body,

  build_main_view, build_rules_view, build_game_overview_view, build_phase_view, build_player_phase_view, build_player_profile_view, build_story_view,
  build_game_ended_view, build_reveal_selection_view, build_vote_selection_view, build_settings_view, build_started_view, build_cancelled_view,
  build_setting_modal,

  INFO_THREAD_NAME_KEY, THREAD_PERMISSIONS_OFF, mentions_for, all_trait_choices
)

from Utils.ai_client import AIClient, GenAIConfig
from Utils.config import BUNKER_AI_SYSTEM_PROMPT, BUNKER_AI_RESPONSE_SCHEMA, BUNKER_AI_GENERATION, BUNKER_AI_MIN_OUTPUT_TOKENS

log = logging.getLogger(__name__)

def make_ai_client() -> AIClient:
  return AIClient([GenAIConfig(models=None, strategy="max_context", min_output_tokens=BUNKER_AI_MIN_OUTPUT_TOKENS, priority=1)])

DEFER_UPDATE_ACTIONS = {"join", "bots", "difficulty", "cancel", "endgame", "start", "reveal", "revealall", "vote", "anonymity", "catastrophe", "aistory"}
DEFER_EPHEMERAL_ACTIONS = {"rules", "translate", "myprofile", "phaseaction", "settings", "alive", "repair"}

STRING_KEYS = {
  "title": "bunker.main.title",
  "creator_label": "bunker.main.creator_label",
  "players_label": "bunker.main.players_label",
  "difficulty_label": "bunker.main.difficulty_label",
  "participants_label": "bunker.main.participants_label",
  "bots_label": "bunker.main.bots_label",
  "difficulty_placeholder": "bunker.main.difficulty_placeholder",
  "rules_button": "bunker.main.rules_button",
  "bots_placeholder": "bunker.main.bots_placeholder",
  "only_creator_bots": "bunker.messages.only_creator_bots",
  "settings_button": "bunker.main.settings_button",
  "join_button": "bunker.main.join_button",
  "cancel_button": "bunker.main.cancel_button",
  "start_button": "bunker.main.start_button",
  "rules_title": "bunker.rules.title",
  "rules_body": "bunker.rules.body",
  "settings_title": "bunker.settings.title",
  "setting_modal_placeholder_count": "bunker.settings.modal_placeholder_count",
  "setting_modal_placeholder_duration": "bunker.settings.modal_placeholder_duration",
  "setting_error_parse": "bunker.messages.setting_error_parse",
  "setting_error_range": "bunker.messages.setting_error_range",
  "setting_error_conflict": "bunker.messages.setting_error_conflict",
  "cancelled_title": "bunker.cancelled.title",
  "permission_error_title": "bunker.permission_error.title",
  "permission_error_body": "bunker.permission_error.body",
  "permission_error_hint": "bunker.permission_error.hint",
  "in_category": "bunker.permission_error.in_category",
  "session_inactive": "bunker.messages.session_inactive",
  "trait_already_revealed": "bunker.messages.trait_already_revealed",
  "invalid_vote_target": "bunker.messages.invalid_vote_target",
  "already_joined": "bunker.messages.already_joined",
  "lobby_full": "bunker.messages.lobby_full",
  "only_creator_cancel": "bunker.messages.only_creator_cancel",
  "only_creator_start": "bunker.messages.only_creator_start",
  "need_more_players_than_capacity": "bunker.messages.need_more_players_than_capacity",
  "only_creator_settings": "bunker.messages.only_creator_settings",
  "only_creator_difficulty": "bunker.messages.only_creator_difficulty",
  "only_creator_setting": "bunker.messages.only_creator_setting",
  "already_has_active_game": "bunker.messages.already_has_active_game",
  "guild_game_limit_reached": "bunker.messages.guild_game_limit_reached",
  "status_in_progress": "bunker.main.status_in_progress",
  "game_channel_label": "bunker.main.game_channel_label",
  "start_channel_error": "bunker.messages.start_channel_error",
  "threads_failed_warning": "bunker.messages.threads_failed_warning",
  "threads_retry_success": "bunker.messages.threads_retry_success",
  "threads_retry_exhausted": "bunker.messages.threads_retry_exhausted",
  "game_title": "bunker.game.title",
  "game_subtitle": "bunker.game.subtitle",
  "apocalypse_duration_label": "bunker.game.apocalypse_duration_label",
  "bunker_capacity_label": "bunker.game.bunker_capacity_label",
  "rounds_label": "bunker.game.rounds_label",
  "food_supply_label": "bunker.game.food_supply_label",
  "water_supply_label": "bunker.game.water_supply_label",
  "bunker_description_label": "bunker.game.bunker_description_label",
  "equipment_label": "bunker.game.equipment_label",
  "problems_label": "bunker.game.problems_label",
  "years_label": "bunker.game.years_label",
  "end_game_button": "bunker.game.end_game_button",
  "translate_button": "bunker.game.translate_button",
  "only_creator_endgame": "bunker.messages.only_creator_endgame",
  "game_ended": "bunker.game.ended",
  "player_panel_title": "bunker.player_panel.title",
  "player_panel_body": "bunker.player_panel.body",
  "my_profile_button": "bunker.player_panel.my_profile_button",
  "scenario_button": "bunker.player_panel.scenario_button",
  "reveal_all_button": "bunker.player_panel.reveal_all_button",
  "reveal_all_body": "bunker.player_panel.reveal_all_body",
  "not_a_player": "bunker.messages.not_a_player",
  "profile_title": "bunker.player_panel.profile_title",
  "profile_gender": "bunker.player_panel.profile_gender",
  "profile_age": "bunker.player_panel.profile_age",
  "card_option_gender": "bunker.player_panel.profile_gender",
  "card_option_age": "bunker.player_panel.profile_age",
  "card_option_profession": "bunker.player_panel.card_option_profession",
  "card_option_health": "bunker.player_panel.card_option_health",
  "card_option_hobby": "bunker.player_panel.card_option_hobby",
  "card_option_phobia": "bunker.player_panel.card_option_phobia",
  "card_option_skill": "bunker.player_panel.card_option_skill",
  "card_option_baggage": "bunker.player_panel.card_option_baggage",
  "round_label": "bunker.round.label",
  "repair_button": "bunker.game.repair_button",
  "repair_done": "bunker.game.repair_done",
  "repair_partial": "bunker.game.repair_partial",
  "repair_cooldown": "bunker.game.repair_cooldown",
  "alive_button": "bunker.player_panel.alive_button",
  "activity_button": "bunker.activity.open_button",
  "story_survivors_label": "bunker.result.ai_story.survivors_label",
  "story_status_survived": "bunker.result.ai_story.status_survived",
  "story_status_lost": "bunker.result.ai_story.status_lost",
  "status_finished": "bunker.main.status_finished",
  "status_ended": "bunker.main.status_ended",
  "board_title": "bunker.board.title",
  "board_eliminated": "bunker.board.eliminated",
  "board_nothing": "bunker.board.nothing",
  "duration_label": "bunker.round.duration_label",
  "player_eliminated": "bunker.player_panel.eliminated",
  "panel_reveal_body": "bunker.player_panel.reveal_body",
  "panel_vote_body": "bunker.player_panel.vote_body",
  "time_remaining_label": "bunker.round.time_remaining",
  "phase_initial_discussion": "bunker.phase.initial_discussion",
  "phase_reveal": "bunker.phase.reveal",
  "phase_discussion": "bunker.phase.discussion",
  "phase_voting": "bunker.phase.voting",
  "phase_tiebreak": "bunker.phase.tiebreak",
  "phase_pause": "bunker.phase.pause",
  "phase_finished": "bunker.phase.finished",
  "phase_initial_discussion_body": "bunker.phase.initial_discussion.body",
  "phase_reveal_body": "bunker.phase.reveal.body",
  "phase_discussion_body": "bunker.phase.discussion.body",
  "phase_voting_body": "bunker.phase.voting.body",
  "phase_pause_body": "bunker.phase.pause.body",
  "phase_finished_body": "bunker.phase.finished.body",
  "reveal_title": "bunker.reveal.title",
  "reveal_body": "bunker.reveal.body",
  "reveal_placeholder": "bunker.reveal.placeholder",
  "vote_title": "bunker.vote.title",
  "vote_body": "bunker.vote.body",
  "vote_placeholder": "bunker.vote.placeholder",
  "tiebreak_title": "bunker.tiebreak.title",
  "tiebreak_body": "bunker.tiebreak.body",
  "vote_recorded": "bunker.vote.recorded",
  "reveal_recorded": "bunker.reveal.recorded",
  "result_reveal_title": "bunker.result.reveal.title",
  "result_reveal_body": "bunker.result.reveal.body",
  "result_reveal_item": "bunker.result.reveal.item",
  "result_vote_title": "bunker.result.vote.title",
  "result_vote_body": "bunker.result.vote.body",
  "result_vote_item": "bunker.result.vote.item",
  "result_eliminated": "bunker.result.vote.eliminated",
  "result_tie": "bunker.result.vote.tie",
  "result_game_finished": "bunker.result.game_finished",
  "result_game_finished_title": "bunker.result.game_finished.title",
  "choose_reveal_button": "bunker.reveal.choose_button",
  "choose_vote_button": "bunker.vote.choose_button",
  "game_already_started": "bunker.messages.game_already_started"
}

class BunkerUtils(Cog):
  def __init__(self, bot: Bot):
    self.bot = bot
    self.thread_creation_locks = {}
    self.start_locks = {}
    self.session_locks = {}
    self.background_tasks = set()
    self.game_channels = {}
    self.thread_sessions = {}
    self.completing = set()
    self.activity_locks = {}
    self.rendered = {}
    self.heal_state = {}
    self.heal_locks = {}
    self.repair_cooldowns = {}
    self.announcing = set()
    self.ai_client = make_ai_client()
    self.heal_sessions.start()
    self.recover_matches.start()
    self.advance_game_phases.start()

  def cog_unload(self) -> None:
    self.heal_sessions.cancel()
    self.recover_matches.cancel()
    self.advance_game_phases.cancel()

  def session_lock(self, session_id: str) -> Lock:
    return self.session_locks.setdefault(session_id, Lock())

  async def mutate_session(self, session_id: str, mutator) -> Optional[BunkerSession]:
    async with self.session_lock(session_id):
      current = await self.load_session(session_id)
      if current is None or current.cancelled:
        return None
      mutator(current)
      await self.save_session(current)
      return current

  async def update_session_fields(self, session: BunkerSession, **fields) -> None:
    async with self.session_lock(session.id):
      current = await self.load_session(session.id)
      if current is not None:
        for name, value in fields.items():
          setattr(current, name, value)
        await self.save_session(current)
    for name, value in fields.items():
      setattr(session, name, value)

  async def store_player_thread(self, session: BunkerSession, player_id: str, thread_id: int, panel_message_id: int) -> None:
    async with self.session_lock(session.id):
      current = await self.load_session(session.id)
      if current is not None:
        current.player_threads[player_id] = thread_id
        current.player_panel_message_ids[player_id] = panel_message_id
        await self.save_session(current)
    session.player_threads[player_id] = thread_id
    session.player_panel_message_ids[player_id] = panel_message_id


  async def user_lang(self, user, guild, locale=None, fallback: str = "en") -> str:
    data_manager = self.bot.get_cog("DataManager")
    try:
      row = await data_manager.get_row("users", {"user_id": user.id}, ["language", "interacted"], guild=guild, user=user) or {}
    except Exception:
      log.warning("Bunker: cannot load language of %s", user.id, exc_info=True)
      return get_locale(str(locale)) if locale else fallback
    if row.get("interacted"):
      return row.get("language") or fallback
    if not locale:
      return fallback
    lang = get_locale(str(locale))
    try:
      await data_manager.set_fields("users", {"user_id": user.id}, {"language": lang, "interacted": True}, ttl_seconds=600, guild=guild, user=user)
    except Exception:
      log.warning("Bunker: cannot store first language of %s", user.id, exc_info=True)
    return lang

  async def public_lang(self, session: BunkerSession) -> str:
    guild = self.bot.get_guild(session.guild_id)
    if guild is None:
      return "en"
    if "COMMUNITY" in guild.features and guild.preferred_locale:
      return get_locale(str(guild.preferred_locale))
    creator = guild.get_member(session.creator_id)
    if creator is None:
      return "en"
    return await self.user_lang(creator, guild, None, "en")

  async def public_context(self, session: BunkerSession) -> tuple:
    lang = await self.public_lang(session)
    return lang, await self.get_strings(lang)

  async def player_lang(self, session: BunkerSession, participant_id: str) -> str:
    fallback = await self.public_lang(session)
    guild = self.bot.get_guild(session.guild_id)
    member = guild.get_member(int(participant_id)) if guild is not None and participant_id.isdigit() else None
    if member is None:
      return fallback
    return await self.user_lang(member, guild, None, fallback)

  async def get_lang(self, interaction: Interaction) -> str:
    return await self.user_lang(interaction.user, interaction.guild, interaction.locale)


  @loop(seconds=1)
  async def advance_game_phases(self) -> None:
    mapping = {}
    thread_mapping = {}
    async for data in self.iter_live_sessions():
      session_id = data.get("id")
      if not session_id:
        continue
      if data.get("game_channel_id") and data.get("started") and data.get("round_phase") not in (None, PHASE_FINISHED):
        mapping[data["game_channel_id"]] = session_id
      if data.get("started"):
        for thread_id in (data.get("player_threads") or {}).values():
          thread_mapping[thread_id] = session_id
        if data.get("info_thread_id"):
          thread_mapping[data["info_thread_id"]] = session_id
      try:
        await self._advance_session(session_id)
      except Exception:
        log.exception("Bunker: failed to advance session %s", session_id)
    self.game_channels = mapping
    self.thread_sessions = thread_mapping

  async def handle_chat_message(self, message) -> None:
    if message.guild is None:
      return
    if message.type == MessageType.pins_add:
      if self.game_channels.get(message.channel.id) or self.thread_sessions.get(message.channel.id):
        try:
          await message.delete()
        except (Forbidden, HTTPException):
          pass
      return
    if message.author.bot:
      return
    session_id = self.game_channels.get(message.channel.id)
    if not session_id:
      return
    text = message.content.strip()
    if not text:
      return
    try:
      await self.record_chat_message(session_id, message.author.id, text[:CHAT_MESSAGE_LIMIT])
    except Exception:
      log.exception("Bunker: failed to record chat message for session %s", session_id)

  async def handle_message_delete(self, payload) -> None:
    session_id = self.game_channels.get(payload.channel_id) or self.thread_sessions.get(payload.channel_id)
    if not session_id:
      return
    try:
      await self.handle_deleted_messages(session_id, {payload.message_id})
    except Exception:
      log.exception("Bunker: failed to handle deleted message in session %s", session_id)

  async def handle_bulk_message_delete(self, payload) -> None:
    session_id = self.game_channels.get(payload.channel_id) or self.thread_sessions.get(payload.channel_id)
    if not session_id:
      return
    try:
      await self.handle_deleted_messages(session_id, set(payload.message_ids))
    except Exception:
      log.exception("Bunker: failed to handle deleted messages in session %s", session_id)

  async def handle_deleted_messages(self, session_id: str, message_ids: set) -> None:
    session = await self.load_session(session_id)
    if session is None:
      return
    if session.phase_message_id in message_ids:
      self.rendered.pop(("phase", session_id), None)
    if session.overview_message_id in message_ids:
      self.rendered.pop(("overview", session_id), None)
    if message_ids & set(session.board_message_ids):
      self.rendered.pop(("board", session_id), None)
    for participant_id, panel_id in session.player_panel_message_ids.items():
      if panel_id in message_ids:
        self.rendered.pop(("panel", session_id, participant_id), None)
    if session.phase_announcement_id in message_ids:
      await self.update_session_fields(session, phase_announcement_id=None)

  async def record_chat_message(self, session_id: str, user_id: int, text: str) -> None:
    async with self.session_lock(session_id):
      session = await self.load_session(session_id)
      if session is None or session.cancelled or not session.started:
        return
      if session.round_phase in (None, PHASE_FINISHED):
        return
      if user_id not in session.player_ids or str(user_id) not in {str(value) for value in session.alive_participant_ids}:
        return
      session.add_chat_message(user_id, text, int(time()))
      await self.save_session(session)

  def schedule_bot_actions(self, session: BunkerSession) -> None:
    session.bot_action_at = {}
    if session.round_phase not in (PHASE_REVEAL, PHASE_VOTING):
      return
    now = time()
    for participant_id in session.alive_participant_ids:
      key = str(participant_id)
      if key.startswith("bot_"):
        session.bot_action_at[key] = now + random.uniform(BOT_REACTION_MIN_SECONDS, BOT_REACTION_MAX_SECONDS)

  def apply_bot_actions(self, session: BunkerSession) -> bool:
    if session.round_phase not in (PHASE_REVEAL, PHASE_VOTING):
      return False
    now = time()
    changed = False
    for participant_id in list(session.alive_participant_ids):
      key = str(participant_id)
      if not key.startswith("bot_"):
        continue
      if session.bot_action_at.get(key, 0) > now:
        continue
      if session.round_phase == PHASE_REVEAL:
        if key in session.round_reveals:
          continue
        choice = choose_random_trait_to_reveal(session, key)
        if choice is None:
          continue
        session.set_reveal(key, choice)
      else:
        if key in session.round_votes:
          continue
        target = choose_random_vote_target(session, key)
        if target is None:
          continue
        session.set_vote(key, target)
      changed = True
    return changed

  async def mute_eliminated(self, session: BunkerSession, participant_id: str) -> None:
    if participant_id.startswith("bot_"):
      return
    channel = self.bot.get_channel(session.game_channel_id) if session.game_channel_id else None
    member = channel.guild.get_member(int(participant_id)) if channel is not None else None
    if member is None:
      return
    try:
      await channel.set_permissions(member, overwrite=PermissionOverwrite(view_channel=True, send_messages=False, **THREAD_PERMISSIONS_OFF))
    except (Forbidden, HTTPException):
      log.warning("Bunker %s: cannot mute eliminated player %s", session.id, participant_id, exc_info=True)

  async def ping_player(self, session: BunkerSession, participant_id: str) -> None:
    thread_id = session.player_threads.get(participant_id)
    if not thread_id or participant_id.startswith("bot_"):
      return
    try:
      message = await self.bot.http.send_message(thread_id, f"<@{participant_id}>", allowed_mentions=mentions_for([participant_id]))
    except (Forbidden, HTTPException):
      return

    async def cleanup() -> None:
      await sleep(5)
      try:
        await self.bot.http.delete_message(thread_id, int(message["id"]))
      except (Forbidden, HTTPException):
        pass

    task = create_task(cleanup())
    self.background_tasks.add(task)
    task.add_done_callback(self.background_tasks.discard)

  async def notify_phase(self, session: BunkerSession, eliminated: Optional[str]) -> None:
    targets = [str(item) for item in session.alive_participant_ids] if session.round_phase in (PHASE_REVEAL, PHASE_VOTING) else []
    if eliminated is not None:
      targets.append(str(eliminated))
    if targets:
      await gather(*(self.ping_player(session, participant_id) for participant_id in targets), return_exceptions=True)

  async def _advance_session(self, session_id: str) -> None:
    phase_order = {
      PHASE_INITIAL_DISCUSSION: PHASE_REVEAL,
      PHASE_REVEAL: PHASE_DISCUSSION,
      PHASE_DISCUSSION: PHASE_VOTING,
      PHASE_VOTING: PHASE_PAUSE,
      PHASE_TIEBREAK: PHASE_PAUSE,
      PHASE_PAUSE: PHASE_REVEAL
    }
    eliminated = None
    finished = False
    timed_out = False

    async with self.session_lock(session_id):
      session = await self.load_session(session_id)
      if session is None or session.cancelled or not session.started or not session.round_phase or session.round_phase == PHASE_FINISHED:
        return
      ended_phase = session.round_phase
      old_announcement_id = session.phase_announcement_id

      game_duration = to_int(session.settings.get("game_duration", 0))
      if session.game_started_at and game_duration and time() - session.game_started_at >= game_duration:
        timed_out = True
        finished = True
      else:
        bots_acted = self.apply_bot_actions(session)
        if bots_acted:
          await self.end_phase_early_if_ready(session)
        if session.phase_ends_at and session.phase_ends_at > time():
          if bots_acted:
            await self.save_session(session)
          return

      if timed_out:
        pass
      elif ended_phase == PHASE_REVEAL:
        for participant_id in list(session.alive_participant_ids):
          key = str(participant_id)
          if key not in session.round_reveals:
            choice = choose_random_trait_to_reveal(session, key)
            if choice is not None:
              session.set_reveal(key, choice)

      elif ended_phase == PHASE_VOTING:
        session.phase_result = {
          "auto_voters": [
            str(participant_id) for participant_id in session.alive_participant_ids
            if not str(participant_id).startswith("bot_") and str(participant_id) not in session.round_votes
          ]
        }
        for participant_id in list(session.alive_participant_ids):
          key = str(participant_id)
          if key not in session.round_votes:
            target = choose_random_vote_target(session, key)
            if target is not None:
              session.set_vote(key, target)

        eliminated = await self.resolve_vote(session)
        vote_record = session.phase_record(PHASE_VOTING)
        vote_record["auto_voters"] = session.phase_result.get("auto_voters", [])
        vote_record["tied"] = session.phase_result.get("tied", [])
        vote_record["eliminated"] = eliminated
        if eliminated is not None:
          session.alive_participant_ids = [participant for participant in session.alive_participant_ids if str(participant) != eliminated]
        if len(session.alive_participant_ids) <= session.bunker_capacity():
          finished = True

      if finished:
        session.round_phase = PHASE_FINISHED
        session.phase_ends_at = None
        session.finished_at = int(time())
        session.end_reason = "timeout" if timed_out else "capacity"
      else:
        next_phase = phase_order.get(ended_phase)
        if next_phase is None:
          return
        if ended_phase == PHASE_PAUSE:
          session.round_number += 1
          session.begin_round(int(time()))
          session.round_votes.clear()
          session.tiebreak_votes.clear()
          session.tiebreak_candidates.clear()
          session.round_reveals.clear()
        session.round_phase = next_phase
        session.phase_ends_at = int(time()) + phase_duration(session, next_phase)
        session.begin_phase(int(time()))
        self.schedule_bot_actions(session)

      session.phase_announcement_id = None
      await self.save_session(session)

    await self.delete_game_message(session, old_announcement_id)

    if not timed_out:
      if ended_phase == PHASE_REVEAL:
        await self.announce_reveal_result(session)
      elif ended_phase == PHASE_VOTING:
        await self.announce_vote_result(session, eliminated)
        if eliminated is not None:
          await self.mute_eliminated(session, eliminated)
    if timed_out:
      await self.announce_game_timeout(session)
    elif finished:
      await self.announce_game_finished(session)
    await self.update_game_phase_messages(session)
    if not finished:
      await self.notify_phase(session, eliminated)
    if ended_phase in (PHASE_REVEAL, PHASE_VOTING) or finished:
      await self.refresh_board(session)
    if finished:
      await self.refresh_overview(session)
      await self.store_match_record(session)
    await self.refresh_main_message(session, await self.public_lang(session))
    if not finished:
      self.announcing.add(session.id)
      try:
        announcement_id = await self.announce_phase(session)
      finally:
        self.announcing.discard(session.id)
      await self.update_session_fields(session, phase_announcement_id=announcement_id)
    else:
      with_story = not timed_out and session.settings.get(AI_STORY_KEY, AI_STORY_DEFAULT) == "on"
      task = create_task(self.complete_game(session, with_story))
      self.background_tasks.add(task)
      task.add_done_callback(self.background_tasks.discard)

  @advance_game_phases.before_loop
  async def before_advance_game_phases(self) -> None:
    await self.bot.wait_until_ready()

  def heal_ready(self, key: tuple) -> bool:
    entry = self.heal_state.get(key)
    return entry is None or entry[1] <= monotonic()

  def heal_result(self, key: tuple, ok: bool) -> None:
    if ok:
      self.heal_state.pop(key, None)
      return
    failures = self.heal_state.get(key, (0, 0.0))[0] + 1
    self.heal_state[key] = (failures, monotonic() + min(2 ** failures, HEAL_BACKOFF_MAX_SECONDS))

  def reset_heal_state(self, session_id: str) -> None:
    for store in (self.rendered, self.heal_state):
      for key in [item for item in store if len(item) > 1 and item[1] == session_id]:
        store.pop(key, None)

  def clear_session_state(self, session_id: str) -> None:
    self.reset_heal_state(session_id)
    self.heal_locks.pop(session_id, None)
    self.repair_cooldowns.pop(session_id, None)
    self.announcing.discard(session_id)

  def phase_key(self, session: BunkerSession) -> str:
    return f"{session.round_number}|{session.round_phase}|{session.phase_ends_at}"

  def panel_key(self, session: BunkerSession, participant_id: str) -> str:
    alive = participant_id in {str(value) for value in session.alive_participant_ids}
    parts = (
      session.round_number, session.round_phase, session.phase_ends_at, int(alive), int(participant_id in session.round_reveals),
      int(participant_id in session.round_votes),
      len(session.revealed_traits.get(participant_id, []))
    )
    return "|".join(str(part) for part in parts)

  def public_choices(self, session: BunkerSession, participant_id: str) -> list:
    choices = list(session.revealed_traits.get(participant_id, []))
    pending = session.round_reveals.get(participant_id)
    if session.round_phase == PHASE_REVEAL and pending in choices:
      del choices[len(choices) - 1 - choices[::-1].index(pending)]
    return choices

  def board_key(self, session: BunkerSession) -> str:
    public = {participant_id: self.public_choices(session, participant_id) for participant_id in session.all_participant_ids()}
    raw = dumps([session.alive_participant_ids, public], sort_keys=True, ensure_ascii=False)
    return sha1(raw.encode("utf-8")).hexdigest()

  def main_key(self, session: BunkerSession) -> str:
    return f"{int(session.started)}|{int(session.cancelled)}|{session.round_number}|{session.round_phase}"

  async def queue_outbox(self, session_id: str, item: dict) -> None:
    async with self.session_lock(session_id):
      current = await self.load_session(session_id)
      if current is None:
        return
      current.outbox.append({"id": uuid4().hex[:8], "attempts": 0, **item})
      del current.outbox[:-OUTBOX_LIMIT]
      await self.save_session(current)

  async def resolve_outbox_item(self, session_id: str, item_id: str, delivered: bool) -> None:
    async with self.session_lock(session_id):
      current = await self.load_session(session_id)
      if current is None:
        return
      kept = []
      for entry in current.outbox:
        if entry.get("id") != item_id:
          kept.append(entry)
          continue
        if delivered:
          continue
        entry["attempts"] = entry.get("attempts", 0) + 1
        if entry["attempts"] < OUTBOX_MAX_ATTEMPTS:
          kept.append(entry)
      current.outbox = kept
      await self.save_session(current)

  async def bump_thread_attempts(self, session_id: str) -> int:
    async with self.session_lock(session_id):
      current = await self.load_session(session_id)
      if current is None:
        return 0
      current.thread_retry_attempts += 1
      await self.save_session(current)
      return current.thread_retry_attempts

  async def forget_player_thread(self, session_id: str, participant_id: str) -> None:
    async with self.session_lock(session_id):
      current = await self.load_session(session_id)
      if current is None:
        return
      current.player_threads.pop(participant_id, None)
      current.player_panel_message_ids.pop(participant_id, None)
      await self.save_session(current)

  async def store_panel_id(self, session: BunkerSession, participant_id: str, message_id: int) -> None:
    async with self.session_lock(session.id):
      current = await self.load_session(session.id)
      if current is not None:
        current.player_panel_message_ids[participant_id] = message_id
        await self.save_session(current)
    session.player_panel_message_ids[participant_id] = message_id

  async def heal_threads(self, session: BunkerSession, force: bool) -> tuple[bool, int]:
    missing = [player_id for player_id in session.player_ids if str(player_id) not in session.player_threads]
    if not missing:
      return False, 0
    target = ("threads", session.id)
    if not force and not self.heal_ready(target):
      return False, len(missing)
    channel = self.bot.get_channel(session.game_channel_id)
    if channel is None:
      self.heal_result(target, False)
      return False, len(missing)
    lang = await self.public_lang(session)
    strings = await self.get_strings(lang)
    failed = await self.create_player_threads(session, channel, lang)
    self.heal_result(target, not failed)
    attempts = await self.bump_thread_attempts(session.id)
    if failed:
      if attempts == MAX_THREAD_RETRY_ATTEMPTS:
        mentions = ", ".join(f"<@{player_id}>" for player_id in failed)
        await self.announce_to_game(
          session, None, f"<@{session.creator_id}> {strings['threads_retry_exhausted']}: {mentions}", queue=True, mention_users=[session.creator_id]
        )
    else:
      await self.announce_to_game(session, None, strings["threads_retry_success"], queue=True)
    return True, len(failed)

  async def reconcile_session(self, session_id: str, force: bool = False, budget: int = HEAL_BUDGET) -> int:
    guard = self.heal_locks.setdefault(session_id, Lock())
    if guard.locked():
      return -1
    async with guard:
      session = await self.load_session(session_id)
      if session is None or session.cancelled or not session.started or not session.game_channel_id:
        return 0
      if force:
        self.reset_heal_state(session_id)
      lang = await self.public_lang(session)
      remaining = budget
      pending = 0

      def take(cost: int = 1) -> bool:
        nonlocal remaining
        if remaining < cost:
          return False
        remaining -= cost
        return True

      async def ensure(target: tuple, desired: str, action, cost: int = 1) -> None:
        nonlocal pending
        if not force and self.rendered.get(target) == desired:
          return
        if (not force and not self.heal_ready(target)) or not take(cost):
          pending += 1
          return
        ok = await action()
        self.heal_result(target, ok)
        if not ok:
          pending += 1

      missing_before = [player_id for player_id in session.player_ids if str(player_id) not in session.player_threads]
      if missing_before and take(len(missing_before) * 3):
        touched, failed_count = await self.heal_threads(session, force)
        pending += failed_count
        if touched:
          reloaded = await self.load_session(session_id)
          if reloaded is None:
            return 0
          session = reloaded
      elif missing_before:
        pending += len(missing_before)

      finished = session.round_phase == PHASE_FINISHED
      await ensure(("phase", session_id), self.phase_key(session), lambda: self.refresh_phase_message(session))
      for player_id in session.player_ids:
        participant_id = str(player_id)
        if participant_id not in session.player_threads:
          continue
        await ensure(("panel", session_id, participant_id), self.panel_key(session, participant_id), lambda participant_id=participant_id: self.refresh_player_panel(session, participant_id))
      await ensure(("overview", session_id), str(int(finished)), lambda: self.refresh_overview(session))
      await ensure(("board", session_id), self.board_key(session), lambda: self.refresh_board(session), 2)
      await ensure(("main", session_id), self.main_key(session), lambda: self.refresh_main_message(session, lang))

      if not session.phase_announcement_id and not finished and session.round_phase and session.phase_ends_at and session_id not in self.announcing:
        started_at = session.phase_record().get("started_at") or 0
        if time() - started_at >= 6 and session.phase_ends_at - time() > 3:
          if take():
            self.announcing.add(session_id)
            try:
              announcement_id = await self.announce_phase(session)
            finally:
              self.announcing.discard(session_id)
            if announcement_id:
              await self.update_session_fields(session, phase_announcement_id=announcement_id)
            else:
              pending += 1
          else:
            pending += 1

      for item in list(session.outbox):
        if not take():
          pending += 1
          continue
        message_id = await self.send_to_game(
          session, self.build_announcement_component(item.get("title"), item.get("body", ""), item.get("footer")), item.get("mention_users", ()),
          item.get("channel_id")
        )
        await self.resolve_outbox_item(session_id, item["id"], message_id is not None)
        if message_id is None:
          pending += 1
          break
      return pending

  async def settle_game(self, session_id: str) -> None:
    for _ in range(10):
      pending = await self.reconcile_session(session_id, budget=REPAIR_BUDGET)
      if pending == 0:
        return
      await sleep(3)

  @loop(seconds=HEAL_INTERVAL_SECONDS)
  async def heal_sessions(self) -> None:
    async for data in self.iter_live_sessions():
      if not data.get("started") or data.get("cancelled"):
        continue
      session_id = data.get("id")
      if not session_id:
        continue
      try:
        await self.reconcile_session(session_id)
      except Exception:
        log.exception("Bunker: failed to heal session %s", session_id)

  @heal_sessions.before_loop
  async def before_heal_sessions(self) -> None:
    await self.bot.wait_until_ready()


  async def save_session(self, session: BunkerSession) -> None:
    raw = dumps(session.to_dict(), ensure_ascii=False)
    await self.bot.redis.set(session_key(session.id), raw, ex=SESSION_TTL_SECONDS)

  async def load_session(self, session_id: str) -> Optional[BunkerSession]:
    raw = await self.bot.redis.get(session_key(session_id))
    if not raw:
      return None
    if isinstance(raw, bytes):
      raw = raw.decode("utf-8")
    return BunkerSession.from_dict(loads(raw))

  async def delete_session(self, session_id: str) -> None:
    await self.bot.redis.delete(session_key(session_id))
    self.session_locks.pop(session_id, None)
    self.start_locks.pop(session_id, None)
    self.thread_creation_locks.pop(session_id, None)
    self.clear_session_state(session_id)

  async def iter_live_sessions(self):
    cursor = 0
    while True:
      cursor, keys = await self.bot.redis.scan(cursor=cursor, match=f"{SESSION_KEY_PREFIX}*", count=100)
      for key in keys:
        raw = await self.bot.redis.get(key)
        if not raw:
          continue
        if isinstance(raw, bytes):
          raw = raw.decode("utf-8")
        yield loads(raw)
      if cursor == 0:
        break

  async def count_guild_sessions(self, guild_id: int) -> int:
    count = 0
    async for data in self.iter_live_sessions():
      if data.get("guild_id") == guild_id and data.get("round_phase") != PHASE_FINISHED:
        count += 1
    return count

  async def has_active_session(self, user_id: int) -> bool:
    async for data in self.iter_live_sessions():
      if data.get("creator_id") == user_id and data.get("round_phase") != PHASE_FINISHED:
        return True
    return False


  async def send_component_message(self, channel, component, mention_users=()) -> dict:
    return await self.bot.http.send_message(
      channel.id, None, components=[component.to_dict()], flags=flags.value, allowed_mentions=mentions_for(mention_users)
    )

  async def edit_component_message(self, channel_id: int, message_id: int, component) -> None:
    await self.bot.http.edit_message(channel_id, message_id, components=[component.to_dict()], allowed_mentions=mentions_for())

  def info_id(self, session: BunkerSession) -> Optional[int]:
    return session.info_thread_id or session.game_channel_id

  async def pin_message(self, channel_id: int, message_id: int) -> None:
    try:
      await self.bot.http.pin_message(channel_id, message_id)
    except (Forbidden, HTTPException):
      log.warning("Bunker: cannot pin message %s", message_id, exc_info=True)

  async def create_info_thread(self, session: BunkerSession, channel, lang: str) -> None:
    tm = self.bot.get_cog("TranslateMessage")
    name = await tm.translate_message(INFO_THREAD_NAME_KEY, lang)
    try:
      thread = await channel.create_thread(name=name[:100], type=ChannelType.public_thread, auto_archive_duration=10080)
    except (Forbidden, HTTPException):
      log.warning("Bunker %s: cannot create the info thread", session.id, exc_info=True)
      return
    await self.update_session_fields(session, info_thread_id=thread.id)
    self.thread_sessions[thread.id] = session.id
    pointer = await tm.translate_message("bunker.game_channel.info_pointer", lang, variables={"thread": f"<#{thread.id}>"})
    try:
      message = await self.send_component_message(channel, self.build_announcement_component(None, pointer))
      await self.pin_message(channel.id, int(message["id"]))
    except (Forbidden, HTTPException):
      log.warning("Bunker %s: cannot post the info pointer", session.id, exc_info=True)

  async def unarchive_thread(self, thread_id: int) -> bool:
    try:
      thread = self.bot.get_channel(thread_id) or await self.bot.fetch_channel(thread_id)
      await thread.edit(archived=False)
      return True
    except (Forbidden, HTTPException):
      return False

  async def refresh_player_panel(self, session: BunkerSession, participant_id: str) -> bool:
    thread_id = session.player_threads.get(participant_id)
    if not thread_id:
      return False
    key = self.panel_key(session, participant_id)
    lang = await self.player_lang(session, participant_id)
    component = await self.build_player_phase_component(session, participant_id, lang)
    panel_id = session.player_panel_message_ids.get(participant_id)
    if panel_id:
      try:
        await self.edit_component_message(thread_id, panel_id, component)
        self.rendered[("panel", session.id, participant_id)] = key
        return True
      except NotFound:
        pass
      except HTTPException as exc:
        if getattr(exc, "code", None) == 50083:
          await self.unarchive_thread(thread_id)
        log.warning("Bunker %s: cannot edit panel of %s", session.id, participant_id, exc_info=True)
        return False
    try:
      await self.bot.fetch_channel(thread_id)
    except NotFound:
      await self.forget_player_thread(session.id, participant_id)
      session.player_threads.pop(participant_id, None)
      session.player_panel_message_ids.pop(participant_id, None)
      return False
    except HTTPException:
      return False
    try:
      message = await self.send_component_message(SimpleNamespace(id=thread_id), component)
    except HTTPException:
      log.warning("Bunker %s: cannot resend panel of %s", session.id, participant_id, exc_info=True)
      return False
    await self.store_panel_id(session, participant_id, int(message["id"]))
    self.rendered[("panel", session.id, participant_id)] = key
    return True

  async def send_to_game(self, session: BunkerSession, component: Container, mention_users=(), channel_id: Optional[int] = None) -> Optional[int]:
    target = channel_id or self.info_id(session)
    if not target:
      return None
    try:
      message = await self.send_component_message(SimpleNamespace(id=target), component, mention_users)
      return int(message["id"])
    except NotFound:
      if not channel_id and session.info_thread_id:
        log.warning("Bunker %s: info thread is gone, falling back to the game channel", session.id)
        await self.update_session_fields(session, info_thread_id=None)
        return await self.send_to_game(session, component, mention_users)
      log.warning("Bunker %s: cannot send message to the game channel", session.id, exc_info=True)
      return None
    except (Forbidden, HTTPException):
      log.warning("Bunker %s: cannot send message to the game channel", session.id, exc_info=True)
      return None

  async def refresh_phase_message(self, session: BunkerSession) -> bool:
    key = self.phase_key(session)
    component = await self.build_phase_component(session, await self.public_lang(session))
    if session.phase_message_id and self.info_id(session):
      try:
        await self.edit_component_message(self.info_id(session), session.phase_message_id, component)
        self.rendered[("phase", session.id)] = key
        return True
      except NotFound:
        pass
      except HTTPException:
        log.warning("Bunker %s: cannot edit phase message", session.id, exc_info=True)
        return False
    message_id = await self.send_to_game(session, component)
    if message_id is None:
      return False
    await self.update_session_fields(session, phase_message_id=message_id)
    self.rendered[("phase", session.id)] = key
    return True

  async def update_game_phase_messages(self, session: BunkerSession) -> None:
    await self.refresh_phase_message(session)
    for player_id in session.player_ids:
      await self.refresh_player_panel(session, str(player_id))

  async def participant_label(self, session: BunkerSession, participant_id: str) -> str:
    participant_id = str(participant_id)
    if participant_id.startswith("bot_"):
      index = int(participant_id.split("_", 1)[1]) - 1
      name = session.bot_names[index] if 0 <= index < len(session.bot_names) else participant_id
      return f"🤖 {name}"
    return f"<@{participant_id}>"

  def build_announcement_component(self, title: Optional[str], body: str, footer: Optional[str] = None) -> Container:
    parts = []
    if title:
      parts.extend([TextDisplay(f"## {title}"), Separator(divider=True, spacing=SeparatorSpacingSize.small)])
    parts.append(TextDisplay(body))
    if footer:
      parts.extend([Separator(divider=True, spacing=SeparatorSpacingSize.small), TextDisplay(footer)])
    return Container(parts, Color.blurple().value, spoiler=False)

  async def announce_to_game(
    self, session: BunkerSession, title: Optional[str], body: str, footer: Optional[str] = None, queue: bool = False, mention_users=(),
    channel_id: Optional[int] = None
  ) -> Optional[int]:
    message_id = await self.send_to_game(session, self.build_announcement_component(title, body, footer), mention_users, channel_id)
    if message_id is None and queue:
      await self.queue_outbox(
        session.id, {"title": title, "body": body, "footer": footer, "mention_users": [str(user) for user in mention_users], "channel_id": channel_id}
      )
    return message_id

  async def edit_announcement(
    self, session: BunkerSession, message_id: Optional[int], title: Optional[str], body: str, footer: Optional[str] = None,
    channel_id: Optional[int] = None
  ) -> Optional[int]:
    target = channel_id or self.info_id(session)
    if message_id and target:
      try:
        await self.edit_component_message(target, message_id, self.build_announcement_component(title, body, footer))
        return message_id
      except (Forbidden, HTTPException):
        log.warning("Bunker %s: cannot edit announcement", session.id, exc_info=True)
    return await self.announce_to_game(session, title, body, footer, channel_id=channel_id)

  async def delete_game_message(self, session: BunkerSession, message_id: Optional[int]) -> None:
    if not message_id or not self.info_id(session):
      return
    try:
      await self.bot.http.delete_message(self.info_id(session), message_id)
    except (Forbidden, HTTPException):
      log.warning("Bunker %s: cannot delete message %s", session.id, message_id, exc_info=True)

  def phase_body_text(self, strings: dict, phase: str) -> str:
    body = strings.get(f"phase_{phase}_body", "")
    return (body .replace("{reveal_button}", strings["choose_reveal_button"]) .replace("{vote_button}", strings["choose_vote_button"]))

  async def announce_phase(self, session: BunkerSession) -> Optional[int]:
    strings = await self.get_strings(await self.public_lang(session))
    phase_key = f"phase_{session.round_phase}"
    title = strings.get(phase_key, session.round_phase)
    body = quote_text(self.phase_body_text(strings, session.round_phase))
    timing_lines = phase_timing_lines(session, strings)
    if timing_lines:
      body = f"{body}\n\n" + "\n".join(timing_lines)
    return await self.announce_to_game(session, f"{strings['round_label']} {session.round_number}: {title}", body)

  async def result_header(self, key: str, placeholder: str, lang: str) -> str:
    tm = self.bot.get_cog("TranslateMessage")
    return (await tm.translate_message(key, lang, variables={placeholder: ""})).strip()

  async def announce_reveal_result(self, session: BunkerSession) -> None:
    lang = await self.public_lang(session)
    strings = await self.get_strings(lang)
    blocks = []
    for participant_id in session.alive_participant_ids:
      described = await self.describe_choice(session, str(participant_id), session.round_reveals.get(str(participant_id)), strings, lang)
      if described is None:
        continue
      trait_label, value = described
      player = await self.participant_label(session, str(participant_id))
      blocks.append(f"👤 {player}\n> {trait_label}: **{value}**")
    header = await self.result_header("bunker.result.reveal.body", "reveals", lang)
    body = f"{header}\n\n" + "\n\n".join(blocks)
    await self.announce_to_game(session, f"{strings['round_label']} {session.round_number}: {strings['result_reveal_title']}", body, queue=True)

  async def describe_choice(self, session: BunkerSession, participant_id: str, choice: Optional[str], strings: dict, lang: str, emoji: bool = True):
    trait, index = get_reveal_choice_parts(choice)
    if trait is None or index is None:
      return None
    card = session.player_cards.get(str(participant_id), {})
    value_keys = card.get(TRAIT_CARD_KEYS[trait], card.get(trait, []))
    values = value_keys if isinstance(value_keys, list) else [value_keys]
    if index >= len(values):
      return None
    value = str(values[index]) if trait == "age" else await self.translate_card_values([values[index]], lang)
    label = strings[f"card_option_{trait}"]
    if emoji:
      label = f"{TRAIT_EMOJIS[trait]} {label}"
    return label, value

  def board_name(self, session: BunkerSession, participant_id: str) -> str:
    name = self.plain_participant_name(session, participant_id)
    return f"🤖 {name}" if participant_id.startswith("bot_") else name

  async def build_board_blocks(self, session: BunkerSession, strings: dict, lang: str, alive_only: bool = False) -> list:
    alive = {str(value) for value in session.alive_participant_ids}
    blocks = []
    for participant_id in session.all_participant_ids():
      if alive_only and participant_id not in alive:
        continue
      items = []
      for choice in self.public_choices(session, participant_id):
        described = await self.describe_choice(session, participant_id, choice, strings, lang)
        if described is not None:
          items.append(f"• **{described[0]}:** {described[1]}")
      name = self.board_name(session, participant_id)
      if participant_id in alive:
        header = f"### 🟢 {name}"
      else:
        header = f"### 💀 ~~{name}~~ ({strings['board_eliminated']})"
      details = "\n".join(items) if items else f"-# {strings['board_nothing']}"
      blocks.append(f"{header}\n{details}")
    return blocks

  async def refresh_board(self, session: BunkerSession) -> bool:
    target = self.info_id(session)
    if not target:
      return False
    channel = SimpleNamespace(id=target)
    healthy = True
    lang = await self.public_lang(session)
    strings = await self.get_strings(lang)
    blocks = await self.build_board_blocks(session, strings, lang)
    known_ids = list(session.board_message_ids)
    new_ids = []
    for index, chunk in enumerate(pack_text_blocks(blocks, BOARD_CHUNK_LIMIT)):
      texts = [TextDisplay(f"## {strings['board_title']}")] if index == 0 else []
      texts.append(TextDisplay(chunk))
      component = Container(texts, Color.gold().value, spoiler=False)
      if index < len(known_ids):
        try:
          await self.edit_component_message(target, known_ids[index], component)
          new_ids.append(known_ids[index])
          continue
        except (Forbidden, HTTPException):
          log.warning("Bunker %s: cannot edit board message", session.id, exc_info=True)
      try:
        message = await self.send_component_message(channel, component)
        new_ids.append(int(message["id"]))
      except (Forbidden, HTTPException):
        healthy = False
        log.warning("Bunker %s: cannot send board message", session.id, exc_info=True)
    if new_ids != known_ids:
      await self.update_session_fields(session, board_message_ids=new_ids)
    if healthy:
      self.rendered[("board", session.id)] = self.board_key(session)
    return healthy

  async def refresh_overview(self, session: BunkerSession) -> bool:
    if not self.info_id(session):
      return False
    key = str(int(session.round_phase == PHASE_FINISHED))
    component = await self.build_game_overview(session, await self.public_lang(session))
    if session.overview_message_id:
      try:
        await self.edit_component_message(self.info_id(session), session.overview_message_id, component)
        self.rendered[("overview", session.id)] = key
        return True
      except NotFound:
        pass
      except HTTPException:
        log.warning("Bunker %s: cannot edit overview message", session.id, exc_info=True)
        return False
    message_id = await self.send_to_game(session, component)
    if message_id is None:
      return False
    await self.update_session_fields(session, overview_message_id=message_id)
    self.rendered[("overview", session.id)] = key
    return True

  async def resolve_vote(self, session: BunkerSession) -> Optional[str]:
    totals = {}
    for target in session.round_votes.values():
      totals[target] = totals.get(target, 0) + 1
    if not totals:
      return None
    highest = max(totals.values())
    candidates = [target for target, count in totals.items() if count == highest]
    session.phase_result.update({"vote_totals": totals, "tied": candidates if len(candidates) > 1 else []})
    return random.choice(candidates)

  async def announce_vote_result(self, session: BunkerSession, eliminated: Optional[str]) -> None:
    lang = await self.public_lang(session)
    strings = await self.get_strings(lang)
    tm = self.bot.get_cog("TranslateMessage")
    result = session.phase_result or {}
    totals = result.get("vote_totals", {})
    anonymous = session.settings.get(ANONYMITY_KEY, ANONYMITY_DEFAULT) == "on"
    voters_by_target = {}
    for voter_id, target_id in session.round_votes.items():
      voters_by_target.setdefault(str(target_id), []).append(voter_id)
    blocks = []
    if anonymous:
      grouped = {}
      for target, count in sorted(totals.items(), key=lambda item: item[0]):
        grouped.setdefault(count, []).append(target)
      for count in sorted(grouped, reverse=True):
        labels = [await self.participant_label(session, target) for target in grouped[count]]
        if len(labels) == 1:
          line = await tm.translate_message("bunker.result.vote.item", lang, variables={"player": labels[0], "votes": count})
        else:
          line = await tm.translate_message("bunker.result.vote.group", lang, variables={"votes": count, "players": ", ".join(labels)})
        blocks.append(f"🗳️ {line}")
    else:
      for target, count in sorted(totals.items(), key=lambda item: (-item[1], item[0])):
        player = await self.participant_label(session, target)
        item = await tm.translate_message("bunker.result.vote.item", lang, variables={"player": player, "votes": count})
        block = f"🗳️ {item}"
        voters = ", ".join([await self.participant_label(session, voter_id) for voter_id in voters_by_target.get(str(target), [])])
        if voters:
          block += f"\n> 👥 {voters}"
        blocks.append(block)
    header = await self.result_header("bunker.result.vote.body", "votes", lang)
    body = f"{header}\n\n" + "\n\n".join(blocks)
    footer_parts = []
    auto_voters = result.get("auto_voters", [])
    if auto_voters:
      players = ", ".join([await self.participant_label(session, participant) for participant in auto_voters])
      footer_parts.append("-# " + await tm.translate_message("bunker.result.vote.auto_vote", lang, variables={"players": players}))
    if result.get("tied") and eliminated is not None:
      chosen = await self.participant_label(session, eliminated)
      footer_parts.append("🎲 " + await tm.translate_message("bunker.result.vote.tie", lang, variables={"player": chosen}))
    if eliminated is not None:
      player = await self.participant_label(session, eliminated)
      footer_parts.append("### 💀 " + await tm.translate_message("bunker.result.vote.eliminated", lang, variables={"player": player}))
    footer = "\n\n".join(footer_parts) if footer_parts else None
    await self.announce_to_game(session, f"{strings['round_label']} {session.round_number}: {strings['result_vote_title']}", body, footer, queue=True)

  async def announce_game_finished(self, session: BunkerSession) -> None:
    lang = await self.public_lang(session)
    strings = await self.get_strings(lang)
    survivors = "\n".join(["• " + await self.participant_label(session, participant) for participant in session.alive_participant_ids])
    header = await self.result_header("bunker.result.game_finished", "survivors", lang)
    await self.announce_to_game(session, strings["result_game_finished_title"], f"{header}\n\n{survivors}", queue=True)

  async def announce_game_timeout(self, session: BunkerSession) -> None:
    lang = await self.public_lang(session)
    tm = self.bot.get_cog("TranslateMessage")
    survivors = "\n".join(["• " + await self.participant_label(session, participant) for participant in session.alive_participant_ids])
    title = await tm.translate_message("bunker.result.timeout.title", lang)
    header = await self.result_header("bunker.result.timeout.body", "survivors", lang)
    await self.announce_to_game(session, title, f"{header}\n\n{survivors}", queue=True)

  def plain_participant_name(self, session: BunkerSession, participant_id: str) -> str:
    if participant_id.startswith("bot_"):
      index = int(participant_id.split("_", 1)[1]) - 1
      return session.bot_names[index] if 0 <= index < len(session.bot_names) else participant_id
    guild = self.bot.get_guild(session.guild_id)
    member = guild.get_member(int(participant_id)) if guild is not None else None
    return member.display_name if member is not None else participant_id


  async def generate_story(self, session: BunkerSession) -> Optional[dict]:
    payload = await self.export_ai_json(session)
    result = await self.ai_client.complete(
      [{"role": "system", "content": BUNKER_AI_SYSTEM_PROMPT}, {"role": "user", "content": payload}],
      temperature=BUNKER_AI_GENERATION["temperature"], max_tokens=0, top_p=BUNKER_AI_GENERATION["top_p"], top_k=BUNKER_AI_GENERATION["top_k"],
      response_json=True, response_schema=BUNKER_AI_RESPONSE_SCHEMA
    )
    parsed = parse_story_response(result.content)
    if parsed is not None:
      parsed["provider"] = result.provider
      parsed["model"] = result.model
      parsed["finish_reason"] = result.finish_reason
    return parsed

  async def rename_game_channel(self, session: BunkerSession, name: str, lang: str) -> Optional[str]:
    channel = self.bot.get_channel(session.game_channel_id) if session.game_channel_id else None
    if channel is None or not name:
      return None
    tm = self.bot.get_cog("TranslateMessage")
    reason = await tm.translate_message("bunker.game_channel.rename_reason", lang)
    try:
      await channel.edit(name=name, reason=reason)
      return name
    except (Forbidden, HTTPException):
      log.warning("Bunker %s: cannot rename game channel", session.id, exc_info=True)
      return None

  async def animate_generation(self, session: BunkerSession, message_id: int, title: str, text: str, stages: list) -> None:
    started = monotonic()
    step = 0
    while True:
      await sleep(GENERATION_PROGRESS_SECONDS)
      step += 1
      stage = stages[(step // PROGRESS_STAGE_STEPS) % len(stages)]
      body = progress_body(step, int(monotonic() - started), text, stage)
      try:
        await self.edit_component_message(session.game_channel_id, message_id, self.build_announcement_component(title, body))
      except (Forbidden, HTTPException):
        log.warning("Bunker %s: cannot update generation progress", session.id, exc_info=True)

  async def store_match_record(self, session: BunkerSession) -> None:
    try:
      names = {participant_id: self.plain_participant_name(session, participant_id) for participant_id in session.all_participant_ids()}
      channel = self.bot.get_channel(session.game_channel_id) if session.game_channel_id else None
      record = build_match_record(session, names, getattr(channel, "name", None), await self.public_lang(session))
      await self.bot.redis.set(match_record_key(session.id), dumps(record, ensure_ascii=False), ex=MATCH_RECORD_TTL_SECONDS)
    except Exception:
      log.exception("Bunker %s: cannot store match record", session.id)

  async def edit_or_send(self, session: BunkerSession, message_id: Optional[int], component: Container) -> Optional[int]:
    target = session.game_channel_id
    if message_id and target:
      try:
        await self.edit_component_message(target, message_id, component)
        return message_id
      except (Forbidden, HTTPException):
        log.warning("Bunker %s: cannot edit story message", session.id, exc_info=True)
    if not target:
      return None
    try:
      message = await self.send_component_message(SimpleNamespace(id=target), component)
      return int(message["id"])
    except (Forbidden, HTTPException):
      log.warning("Bunker %s: cannot send story message", session.id, exc_info=True)
      return None

  async def save_activity_redirect(self, interaction: Interaction, path: str) -> None:
    data_manager = self.bot.get_cog("DataManager")
    user = interaction.user
    if len(self.activity_locks) > 1000:
      self.activity_locks.clear()
    async with self.activity_locks.setdefault(user.id, Lock()):
      await data_manager.get_row("users", {"user_id": user.id}, ["language"], guild=interaction.guild, user=user)
      keys = {"user_id": user.id}
      moment = datetime.now(timezone.utc).isoformat()
      existing = await data_manager.get_row("activity_redirects", keys, ["target_path"], guild=interaction.guild, user=user)
      if existing:
        await data_manager.set_fields(
          "activity_redirects", keys, {"target_path": path, "created_at": moment}, ttl_seconds=5, guild=interaction.guild, user=user
        )
      else:
        await data_manager.insert_row("activity_redirects", keys, {"user_id": user.id, "target_path": path, "created_at": moment}, ttl_seconds=5)

  async def prepare_activity_redirect(self, interaction: Interaction, game_id: str) -> None:
    path = ACTIVITY_PATH_TEMPLATE.format(game_id=game_id)
    try:
      await wait_for(self.save_activity_redirect(interaction, path), timeout=2.0)
    except Exception:
      log.warning("Bunker: cannot save activity redirect for game %s", game_id, exc_info=True)

  async def launch_activity(self, interaction: Interaction) -> None:
    route = Route("POST", "/interactions/{interaction_id}/{interaction_token}/callback", interaction_id=interaction.id, interaction_token=interaction.token)
    await self.bot.http.request(route, json={"type": 12})

  async def post_ai_story(self, session: BunkerSession) -> None:
    lang = await self.public_lang(session)
    tm = self.bot.get_cog("TranslateMessage")
    strings = await self.get_strings(lang)
    chronicle_title = await tm.translate_message("bunker.result.ai_story.title", lang)
    generating_text = await tm.translate_message("bunker.result.ai_story.generating", lang)
    stages = [await tm.translate_message(key, lang) for key in PROGRESS_STAGE_KEYS]
    generating_id = await self.announce_to_game(session, chronicle_title, progress_body(0, 0, generating_text, stages[0]), channel_id=session.game_channel_id)
    progress_task = create_task(self.animate_generation(session, generating_id, chronicle_title, generating_text, stages)) if generating_id else None
    started = monotonic()
    story_data = None
    try:
      story_data = await self.generate_story(session)
    except Exception:
      log.exception("Bunker %s: AI story failed", session.id)
    finally:
      if progress_task is not None:
        progress_task.cancel()
        try:
          await progress_task
        except CancelledError:
          pass

    if await self.load_session(session.id) is None:
      return

    if story_data is None:
      await self.edit_announcement(
        session, generating_id, chronicle_title, await tm.translate_message("bunker.result.ai_story.unavailable", lang), channel_id=session.game_channel_id
      )
      return

    human_ids = {str(player_id) for player_id in session.player_ids}
    finalists = [str(item) for item in session.alive_participant_ids]
    teaser = sanitize_ai_text(clip_text(story_data["teaser"], AI_TEASER_LIMIT), human_ids)
    summary = sanitize_ai_text(clip_text(story_data["summary"], AI_SUMMARY_LIMIT), human_ids)
    story = sanitize_ai_text(story_data["story"], human_ids)
    survivors = None if story_data["survivors"] is None else [item for item in story_data["survivors"] if item in finalists]

    status_text = None
    survivors_text = None
    if survivors is not None:
      status_text = strings["story_status_survived"] if survivors else strings["story_status_lost"]
    if survivors:
      lines = [f"• {await self.participant_label(session, item)}" for item in survivors]
      survivors_text = f"### {strings['story_survivors_label']}\n" + "\n".join(lines)

    component = build_story_view(session.id, strings, chronicle_title, story_data["title"], teaser, summary, status_text, survivors_text)
    summary_message_id = await self.edit_or_send(session, generating_id, component)
    channel_name = await self.rename_game_channel(session, sanitize_channel_title(story_data["title"]), lang)

    ai_result = {
      "title": story_data["title"],
      "teaser": teaser,
      "summary": summary,
      "story": story,
      "survivors": survivors,
      "finalists": finalists,
      "provider": story_data.get("provider"),
      "model": story_data.get("model"),
      "finish_reason": story_data.get("finish_reason"),
      "generated_at": int(time()),
      "seconds": int(monotonic() - started),
      "channel_name": channel_name,
      "summary_message_id": summary_message_id
    }
    await self.update_session_fields(session, ai_result=ai_result)
    await self.store_match_record(session)

  async def insert_archive_row(self, table: str, keys: dict, data: dict) -> None:
    data_manager = self.bot.get_cog("DataManager")
    await data_manager.insert_row(table, keys, data, ttl_seconds=120)

  async def row_exists(self, table: str, keys: dict, guild, user) -> bool:
    data_manager = self.bot.get_cog("DataManager")
    row = await data_manager.get_row(table, keys, list(keys), guild=guild, user=user)
    return bool(row)

  async def archive_record(self, record: dict) -> bool:
    game_id = record["id"]
    guild_id = int(record["guild_id"])
    creator_id = int(record["creator_id"])
    guild = self.bot.get_guild(guild_id)
    creator = guild.get_member(creator_id) if guild is not None else None
    status = GAME_STATUS_TIMEOUT if record.get("end_reason") == "timeout" else GAME_STATUS_FINISHED
    game_row = {
      "id": game_id,
      "guild_id": guild_id,
      "creator_id": creator_id,
      "status": status,
      "created_at": format_iso(record.get("started_at")),
      "finished_at": format_iso(record.get("finished_at")),
      "payload": encode_payload(client_payload(record))
    }
    try:
      if not await self.row_exists("bunker_games", {"id": game_id}, guild, creator):
        await self.insert_archive_row("bunker_games", {"id": game_id}, game_row)
    except Exception:
      log.exception("Bunker %s: cannot archive game", game_id)
      return False
    winners = {str(item) for item in record.get("winners", [])}
    complete = True
    for participant_id, entry in (record.get("players") or {}).items():
      if entry.get("bot") or not str(participant_id).isdigit():
        continue
      keys = {"game_id": game_id, "user_id": int(participant_id)}
      player_row = {**keys, "guild_id": guild_id, "won": str(participant_id) in winners}
      member = guild.get_member(int(participant_id)) if guild is not None else None
      try:
        if not await self.row_exists("bunker_game_players", keys, guild, member):
          await self.insert_archive_row("bunker_game_players", keys, player_row)
      except Exception:
        complete = False
        log.exception("Bunker %s: cannot archive player %s", game_id, participant_id)
    return complete

  async def archive_game(self, session: BunkerSession) -> bool:
    channel = self.bot.get_channel(session.game_channel_id) if session.game_channel_id else None
    names = {participant_id: self.plain_participant_name(session, participant_id) for participant_id in session.all_participant_ids()}
    record = build_match_record(session, names, getattr(channel, "name", None), await self.public_lang(session))
    if not await self.archive_record(record):
      await self.store_match_record(session)
      return False
    await self.delete_session(session.id)
    await self.bot.redis.delete(match_record_key(session.id))
    return True

  async def complete_game(self, session: BunkerSession, with_story: bool) -> None:
    self.completing.add(session.id)
    try:
      if with_story:
        try:
          await self.post_ai_story(session)
        except Exception:
          log.exception("Bunker %s: story flow failed", session.id)
      await self.settle_game(session.id)
      await self.archive_game(session)
    finally:
      self.completing.discard(session.id)

  async def recover_finished_sessions(self) -> None:
    handled = 0
    async for data in self.iter_live_sessions():
      if not data.get("started") or data.get("round_phase") != PHASE_FINISHED:
        continue
      session_id = data.get("id")
      if not session_id or session_id in self.completing:
        continue
      if time() - (data.get("finished_at") or 0) < FINISHED_GRACE_SECONDS:
        continue
      if handled >= MATCH_RECOVERY_BATCH:
        return
      handled += 1
      session = await self.load_session(session_id)
      if session is not None:
        await self.complete_game(session, False)

  async def recover_match_records(self) -> None:
    redis = self.bot.redis
    cursor = 0
    handled = 0
    while True:
      cursor, keys = await redis.scan(cursor=cursor, match=f"{MATCH_RECORD_PREFIX}*", count=100)
      for key in keys:
        raw = await redis.get(key)
        if not raw:
          continue
        if isinstance(raw, bytes):
          raw = raw.decode("utf-8")
        record = loads(raw)
        game_id = record.get("id")
        if not game_id or await redis.get(session_key(game_id)) is not None:
          continue
        ttl = await redis.ttl(key)
        if ttl < 0 or ttl > MATCH_RECORD_TTL_SECONDS:
          await redis.expire(key, MATCH_RECORD_TTL_SECONDS)
        if handled >= MATCH_RECOVERY_BATCH:
          continue
        handled += 1
        if await self.archive_record(record):
          await redis.delete(key)
      if cursor == 0:
        break

  @loop(minutes=MATCH_RECOVERY_INTERVAL_MINUTES)
  async def recover_matches(self) -> None:
    try:
      await self.recover_finished_sessions()
      await self.recover_match_records()
    except Exception:
      log.exception("Bunker: match recovery failed")

  @recover_matches.before_loop
  async def before_recover_matches(self) -> None:
    await self.bot.wait_until_ready()

  def format_utc(self, timestamp) -> Optional[str]:
    if not timestamp:
      return None
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

  def export_message_line(self, name: str, value: str, round_start: Optional[str]) -> str:
    if value[19:22] != " - ":
      return f"{name}: {value}"
    stamp = value[:19]
    text = value[22:].replace("\n\n", "\n")
    shown = stamp[11:] if round_start and stamp[:10] == round_start[:10] else stamp
    return f"{shown} {name}: {text}"

  def compact_export(self, value):
    if isinstance(value, dict):
      result = {}
      for key, item in value.items():
        cleaned = self.compact_export(item)
        if cleaned is None or cleaned == "" or cleaned == [] or cleaned == {}:
          continue
        result[key] = cleaned
      return result
    if isinstance(value, list):
      cleaned_items = [self.compact_export(item) for item in value]
      return [item for item in cleaned_items if item is not None and item != "" and item != [] and item != {}]
    return value

  async def build_ai_export(self, session: BunkerSession) -> dict:
    lang = await self.public_lang(session)
    tm = self.bot.get_cog("TranslateMessage")
    strings = await self.get_strings(lang)
    fallback_name = await tm.translate_message(THREAD_DEFAULT_NAME_KEY, lang)
    names = {}
    used = set()
    for index, participant_id in enumerate(session.all_participant_ids(), 1):
      name = self.plain_participant_name(session, participant_id)
      if name == participant_id and not participant_id.startswith("bot_"):
        name = f"{fallback_name}{index}"
      base_name = name
      suffix = 2
      while name in used:
        name = f"{base_name}{suffix}"
        suffix += 1
      used.add(name)
      names[participant_id] = name

    scenario = session.catastrophe or {}
    difficulty_options = await self.get_difficulty_options(lang)
    difficulty_label = next((label for value, label, _ in difficulty_options if value == session.difficulty), session.difficulty)
    export = {
      "lang": lang,
      "rules": await tm.translate_message("bunker.rules.body", lang),
      "difficulty": difficulty_label,
      "catastrophe": {
        "type": await tm.translate_message(scenario["type_key"], lang) if scenario.get("type_key") else None,
        "story": await tm.translate_message(scenario["history_key"], lang) if scenario.get("history_key") else None,
        "duration_years": session.apocalypse_duration_years
      },
      "bunker": {
        "description": await tm.translate_message(session.bunker_description_key, lang) if session.bunker_description_key else None,
        "capacity": session.bunker_capacity(),
        "rounds": session.rounds_count(),
        "food_years": session.food_supply_years,
        "water_years": session.water_supply_years,
        "equipment": await self.translate_card_items(session.equipment_keys, lang),
        "problems": await self.translate_card_items(session.problem_keys, lang)
      }
    }

    out_round = {}
    for round_key, record in session.rounds.items():
      eliminated = record.get("phases", {}).get(PHASE_VOTING, {}).get("eliminated")
      if eliminated:
        out_round[str(eliminated)] = int(round_key)

    players = {}
    for participant_id in session.all_participant_ids():
      card = session.player_cards.get(participant_id) or {}
      entry = {"id": participant_id}
      if participant_id.startswith("bot_"):
        entry["bot"] = 1
      if card.get("gender_key"):
        entry["gender"] = await tm.translate_message(card["gender_key"], lang)
      entry["age"] = card.get("age")
      for trait in ("profession", "health", "hobby", "phobia", "skill", "baggage"):
        items = await self.translate_card_items(card.get(TRAIT_CARD_KEYS[trait], []), lang)
        entry[trait] = items[0] if len(items) == 1 else items
      entry["out_round"] = out_round.get(participant_id)
      players[names[participant_id]] = entry
    export["players"] = players

    phase_order = (PHASE_INITIAL_DISCUSSION, PHASE_REVEAL, PHASE_DISCUSSION, PHASE_VOTING, PHASE_PAUSE)
    rounds = []
    for round_key in sorted(session.rounds, key=int):
      record = session.rounds[round_key]
      round_start = self.format_utc(record.get("started_at"))
      round_export = {"n": int(round_key), "start": round_start}
      for phase in phase_order:
        data = record.get("phases", {}).get(phase)
        if not data:
          continue
        lines = []
        for entry in data.get("messages", []):
          for user_id, value in entry.items():
            lines.append(self.export_message_line(names.get(user_id, user_id), value, round_start))
        reveals = {}
        for participant_id, choice in data.get("reveals", {}).items():
          described = await self.describe_choice(session, participant_id, choice, strings, lang, False)
          if described is not None:
            reveals[names.get(participant_id, participant_id)] = f"{described[0]}: {described[1]}"
        votes = {}
        for voter_id, target_id in data.get("votes", {}).items():
          votes.setdefault(names.get(target_id, target_id), []).append(names.get(voter_id, voter_id))
        eliminated = data.get("eliminated")
        round_export[strings[f"phase_{phase}"]] = {
          "msgs": lines,
          "reveals": reveals,
          "votes": votes,
          "auto": [names.get(item, item) for item in data.get("auto_voters", [])],
          "tie": [names.get(item, item) for item in data.get("tied", [])],
          "out": names.get(eliminated, eliminated) if eliminated else None
        }
      rounds.append(round_export)
    export["rounds"] = rounds

    alive_names = [names[str(item)] for item in session.alive_participant_ids if str(item) in names]
    export["survivors" if session.round_phase == PHASE_FINISHED else "alive"] = alive_names
    return self.compact_export(export)

  async def export_ai_json(self, session: BunkerSession) -> str:
    return dumps(await self.build_ai_export(session), ensure_ascii=False, separators=(",", ":"))

  async def end_phase_early_if_ready(self, session: BunkerSession) -> None:
    alive = {str(value) for value in session.alive_participant_ids}
    if not alive:
      return
    if session.round_phase == PHASE_REVEAL:
      pending = {participant_id for participant_id in alive if participant_id not in session.round_reveals and remaining_trait_types(session, participant_id)}
      complete = not pending
    elif session.round_phase == PHASE_VOTING:
      complete = alive <= set(session.round_votes)
    else:
      return
    if complete:
      session.phase_ends_at = int(time())


  async def get_strings(self, lang: str) -> dict:
    tm = self.bot.get_cog("TranslateMessage")
    return {name: await tm.translate_message(key, lang) for name, key in STRING_KEYS.items()}

  async def _get_options(self, options_source: list, lang: str) -> list:
    tm = self.bot.get_cog("TranslateMessage")
    options = []
    for value, label_key, description_key in options_source:
      label = await tm.translate_message(label_key, lang)
      description = await tm.translate_message(description_key, lang) if description_key else None
      options.append((value, label, description))
    return options

  async def get_difficulty_options(self, lang: str) -> list:
    return await self._get_options(DIFFICULTY_OPTIONS, lang)

  async def get_anonymity_options(self, lang: str) -> list:
    return await self._get_options(ANONYMITY_OPTIONS, lang)

  async def get_ai_story_options(self, lang: str) -> list:
    return await self._get_options(AI_STORY_OPTIONS, lang)

  async def get_catastrophe_options(self, lang: str) -> list:
    return await self._get_options(build_catastrophe_options(), lang)

  async def translate_permission_labels(self, keys: list, lang: str) -> list:
    tm = self.bot.get_cog("TranslateMessage")
    return [await tm.translate_message(key, lang) for key in keys]

  async def get_settings_titles(self, lang: str) -> dict:
    tm = self.bot.get_cog("TranslateMessage")
    titles = {key: await tm.translate_message(title_key, lang) for key, title_key, *_ in SETTINGS_CATEGORIES}
    titles[ANONYMITY_KEY] = await tm.translate_message("bunker.settings.anonymity.title", lang)
    titles[CATASTROPHE_KEY] = await tm.translate_message("bunker.settings.catastrophe_mode.title", lang)
    titles[AI_STORY_KEY] = await tm.translate_message("bunker.settings.ai_story.title", lang)
    return titles

  async def load_base_settings(self, guild: Guild, user: Member):
    data_manager = self.bot.get_cog("DataManager")
    columns = [key for key, *_ in SETTINGS_CATEGORIES] + ["category_id"]
    row = await data_manager.get_row("guild_settings_bunker", {"guild_id": guild.id}, columns, guild=guild, user=user) or {}

    settings = {}
    for key, *_, default_value in SETTINGS_CATEGORIES:
      db_value = row.get(key)
      settings[key] = str(to_int(db_value)) if db_value is not None else str(default_value)

    settings[ANONYMITY_KEY] = ANONYMITY_DEFAULT
    settings[CATASTROPHE_KEY] = CATASTROPHE_DEFAULT
    settings[AI_STORY_KEY] = AI_STORY_DEFAULT

    return settings, row.get("category_id")

  async def resolve_category(self, guild: Guild, user: Member, category_id: Optional[int], lang: str) -> Optional[CategoryChannel]:
    channel = guild.get_channel(category_id) if category_id else None
    category = channel if isinstance(channel, CategoryChannel) else None
    if category is not None:
      return category

    tm = self.bot.get_cog("TranslateMessage")
    category_name = await tm.translate_message(CATEGORY_NAME_KEY, lang)
    create_reason = await tm.translate_message(CATEGORY_CREATE_REASON_KEY, lang)

    try:
      category = await guild.create_category(category_name, reason=create_reason)
    except (Forbidden, HTTPException):
      return None

    data_manager = self.bot.get_cog("DataManager")
    await data_manager.set_fields("guild_settings_bunker", {"guild_id": guild.id}, {"category_id": category.id}, ttl_seconds=600, guild=guild, user=user)
    return category

  async def create_game_channel(self, session: BunkerSession, lang: str):
    guild = self.bot.get_guild(session.guild_id)
    if guild is None:
      return None, "guild_unavailable"

    category = guild.get_channel(session.category_id) if session.category_id else None
    if not isinstance(category, CategoryChannel):
      return None, "category_missing"

    missing_keys = get_missing_permission_keys(category.permissions_for(guild.me))
    if missing_keys:
      return None, "missing_permissions"

    overwrites = {
      guild.default_role: PermissionOverwrite(send_messages=False, **THREAD_PERMISSIONS_OFF),
      guild.me: PermissionOverwrite(
        view_channel=True, send_messages=True, send_messages_in_threads=True, create_public_threads=True, create_private_threads=True,
        manage_threads=True, manage_messages=True, read_message_history=True
      )
    }
    for player_id in session.player_ids:
      member = guild.get_member(player_id)
      if member is None:
        try:
          member = await guild.fetch_member(player_id)
        except (Forbidden, HTTPException):
          continue
      overwrites[member] = PermissionOverwrite(view_channel=True, send_messages=True, **THREAD_PERMISSIONS_OFF)

    tm = self.bot.get_cog("TranslateMessage")
    reason = await tm.translate_message(GAME_CHANNEL_CREATE_REASON_KEY, lang)
    name_prefix = await tm.translate_message(GAME_CHANNEL_NAME_PREFIX_KEY, lang)
    existing_count = sum(1 for channel in category.channels if channel.name.startswith(name_prefix))

    try:
      channel = await guild.create_text_channel(
        name=build_game_channel_name(name_prefix, existing_count + 1),
        category=category, overwrites=overwrites, reason=reason
      )
    except (Forbidden, HTTPException):
      return None, "create_failed"

    return channel, None

  async def create_player_threads(self, session: BunkerSession, channel, lang: str) -> list:
    lock = self.thread_creation_locks.setdefault(session.id, Lock())
    async with lock:
      current_session = await self.load_session(session.id)
      if current_session is not None:
        session = current_session
      return await self._create_player_threads(session, channel, lang)

  async def _create_player_threads(self, session: BunkerSession, channel, lang: str) -> list:
    guild = self.bot.get_guild(session.guild_id)
    if guild is None:
      return list(session.player_ids)

    tm = self.bot.get_cog("TranslateMessage")
    reason = await tm.translate_message(THREAD_CREATE_REASON_KEY, lang)
    default_thread_name = await tm.translate_message(THREAD_DEFAULT_NAME_KEY, lang)

    failed_player_ids = []

    for player_id in session.player_ids:
      if str(player_id) in session.player_threads:
        continue

      member = guild.get_member(player_id)
      if member is None:
        try:
          member = await guild.fetch_member(player_id)
        except (Forbidden, HTTPException):
          failed_player_ids.append(player_id)
          continue

      thread_name = build_player_thread_name(member.display_name, default_thread_name)

      try:
        thread = await channel.create_thread(name=thread_name, type=ChannelType.private_thread, invitable=False, auto_archive_duration=10080, reason=reason)
      except (Forbidden, HTTPException):
        log.warning("Bunker %s: cannot create thread for %s", session.id, player_id, exc_info=True)
        failed_player_ids.append(player_id)
        continue

      try:
        await thread.add_user(member)
      except (Forbidden, HTTPException):
        log.warning("Bunker %s: cannot add %s to thread", session.id, player_id, exc_info=True)
        failed_player_ids.append(player_id)
        try:
          await thread.delete()
        except (Forbidden, HTTPException):
          pass
        continue

      try:
        member_lang = await self.player_lang(session, str(player_id))
        panel_component = await self.build_player_phase_component(session, str(player_id), member_lang)
        panel_message = await self.send_component_message(thread, panel_component)
      except (Forbidden, HTTPException):
        log.warning("Bunker %s: cannot send panel to %s", session.id, player_id, exc_info=True)
        failed_player_ids.append(player_id)
        try:
          await thread.delete()
        except (Forbidden, HTTPException):
          pass
        continue

      await self.store_player_thread(session, str(player_id), thread.id, int(panel_message["id"]))
      self.rendered[("panel", session.id, str(player_id))] = self.panel_key(session, str(player_id))

    return failed_player_ids

  async def build_game_overview(self, session: BunkerSession, lang: str, controls: bool = True):
    tm = self.bot.get_cog("TranslateMessage")
    strings = await self.get_strings(lang)
    scenario = session.catastrophe or {}
    scenario_type = await tm.translate_message(scenario.get("type_key", "bunker.game.unknown_catastrophe"), lang)
    scenario_history = await tm.translate_message(scenario.get("history_key", "bunker.game.unknown_catastrophe"), lang)
    bunker_description = await tm.translate_message(session.bunker_description_key, lang) if session.bunker_description_key else "—"
    equipment = await self.translate_card_list(session.equipment_keys, lang)
    problems = await self.translate_card_list(session.problem_keys, lang)

    overview_text = "\n".join([
      f"⏳ **{strings['apocalypse_duration_label']}:** {session.apocalypse_duration_years} {strings['years_label']}",
      f"🏠 **{strings['bunker_capacity_label']}:** {session.bunker_capacity()}",
      f"🔁 **{strings['rounds_label']}:** {session.rounds_count()}",
      f"🍖 **{strings['food_supply_label']}:** {session.food_supply_years} {strings['years_label']}",
      f"💧 **{strings['water_supply_label']}:** {session.water_supply_years} {strings['years_label']}"
    ])

    participants = "\n".join(f"• <@{player_id}>" for player_id in session.player_ids)
    if session.bots:
      participants += f"\n🤖 **{strings['bots_label']}:** {session.bots}"
    finished = session.round_phase == PHASE_FINISHED
    status_text = strings["status_finished"] if finished else None
    return build_game_overview_view(
      session, strings, scenario_type, scenario_history, overview_text, bunker_description, equipment, problems, participants, status_text, finished,
      show_buttons=controls
    )

  async def build_phase_component(self, session: BunkerSession, lang: str):
    strings = await self.get_strings(lang)
    phase_key = f"phase_{session.round_phase}"
    title = strings.get(phase_key, session.round_phase)
    return build_phase_view(session, strings, title, self.phase_body_text(strings, session.round_phase))

  async def build_reveal_options(self, session: BunkerSession, player_id: str, strings: dict, lang: str) -> list:
    card = session.player_cards.get(str(player_id), {})
    options = []
    for choice in remaining_trait_types(session, player_id):
      trait, index = get_reveal_choice_parts(choice)
      if trait is None or index is None:
        continue
      values = card.get(TRAIT_CARD_KEYS[trait], card.get(trait, []))
      values = values if isinstance(values, list) else [values]
      if index >= len(values):
        continue
      value = str(values[index]) if trait == "age" else await self.translate_card_values([values[index]], lang)
      options.append(SelectOption(label=f"{TRAIT_EMOJIS[trait]} {strings[f'card_option_{trait}']}: {value}"[:100], value=choice))
    return options

  def build_vote_options(self, session: BunkerSession, candidates: list, guild: Optional[Guild] = None) -> list:
    if guild is None:
      guild = self.bot.get_guild(session.guild_id)
    options = []
    for candidate in candidates:
      candidate_id = str(candidate)
      if candidate_id.startswith("bot_"):
        index = int(candidate_id.split("_", 1)[1]) - 1
        name = session.bot_names[index] if 0 <= index < len(session.bot_names) else candidate_id
        label = f"🤖 {name}"
      else:
        member = guild.get_member(int(candidate_id)) if guild is not None else None
        label = member.display_name if member is not None else candidate_id
      options.append(SelectOption(label=label[:100], value=candidate_id))
    return options

  async def build_player_phase_component(self, session: BunkerSession, player_id: str, lang: str):
    strings = await self.get_strings(lang)
    phase_key = f"phase_{session.round_phase}"
    phase_title = strings.get(phase_key, session.round_phase or "")

    alive_ids = {str(value) for value in session.alive_participant_ids}
    if player_id not in alive_ids:
      if session.round_phase == PHASE_FINISHED:
        return build_player_phase_view(session, strings, phase_title, self.phase_body_text(strings, PHASE_FINISHED))
      body = strings["player_eliminated"]
      button = None
      if remaining_trait_types(session, player_id):
        body = f"{body}\n{strings['reveal_all_body']}"
        button = Button(style=ButtonStyle.secondary, label=f"🃏 {strings['reveal_all_button']}", custom_id=f"bunker|revealall|{session.id}")
      return build_player_phase_view(session, strings, phase_title, body, button)

    if session.round_phase == PHASE_REVEAL:
      if player_id in session.round_reveals:
        return build_player_phase_view(session, strings, phase_title, strings["reveal_recorded"])
      if remaining_trait_types(session, player_id):
        button = Button(style=ButtonStyle.primary, label=strings["choose_reveal_button"], custom_id=f"bunker|phaseaction|{session.id}")
        body = strings["panel_reveal_body"].replace("{button}", strings["choose_reveal_button"])
        return build_player_phase_view(session, strings, phase_title, body, button)
      return build_player_phase_view(session, strings, phase_title, "")

    if session.round_phase in (PHASE_VOTING, PHASE_TIEBREAK):
      is_tiebreak = session.round_phase == PHASE_TIEBREAK
      votes = session.tiebreak_votes if is_tiebreak else session.round_votes
      if player_id in votes:
        return build_player_phase_view(session, strings, phase_title, strings["vote_recorded"])

      candidates = session.tiebreak_candidates if is_tiebreak else session.alive_participant_ids
      if self.build_vote_options(session, candidates):
        button = Button(style=ButtonStyle.primary, label=strings["choose_vote_button"], custom_id=f"bunker|phaseaction|{session.id}")
        body = strings["panel_vote_body"].replace("{button}", strings["choose_vote_button"])
        return build_player_phase_view(session, strings, phase_title, body, button)

    body = self.phase_body_text(strings, session.round_phase) if session.round_phase else ""
    return build_player_phase_view(session, strings, phase_title, body)

  async def translate_card_items(self, keys: list, lang: str) -> list:
    tm = self.bot.get_cog("TranslateMessage")
    return [await tm.translate_message(key, lang) for key in keys]

  async def translate_card_list(self, keys: list, lang: str) -> str:
    values = await self.translate_card_items(keys, lang)
    return "\n".join(f"• {value}" for value in values) if values else "—"

  async def translate_card_values(self, keys: list, lang: str) -> str:
    tm = self.bot.get_cog("TranslateMessage")
    values = [await tm.translate_message(key, lang) for key in keys]
    return ", ".join(values) if values else "—"

  async def build_profile_view(self, card: dict, lang: str, strings: dict):
    tm = self.bot.get_cog("TranslateMessage")
    gender = await tm.translate_message(card["gender_key"], lang)
    sections = []
    for trait, card_key in (
      ("profession", "profession_keys"), ("health", "health_condition_keys"), ("hobby", "hobby_keys"), ("phobia", "phobia_keys"), ("skill", "skill_keys"),
      ("baggage", "baggage_keys")
    ):
      title = f"{TRAIT_EMOJIS[trait]} {strings[f'card_option_{trait}']}"
      sections.append((title, await self.translate_card_list(card[card_key], lang)))
    return build_player_profile_view(strings, gender, card["age"], sections)

  async def build_settings_summary_lines(self, session: BunkerSession, lang: str) -> list:
    settings_titles = await self.get_settings_titles(lang)
    lines = []
    for key, *_ in SETTINGS_CATEGORIES:
      entry = get_setting_entry(key)
      kind = entry[2] if entry else "count"
      value = session.settings.get(key, "")
      lines.append(f"• {settings_titles.get(key, key)}: **{format_setting_display(kind, value)}**")

    anonymity_options = await self.get_anonymity_options(lang)
    anonymity_value = session.settings.get(ANONYMITY_KEY, ANONYMITY_DEFAULT)
    anonymity_label = next((label for value, label, _ in anonymity_options if value == anonymity_value), anonymity_value)
    lines.append(f"• {settings_titles.get(ANONYMITY_KEY, ANONYMITY_KEY)}: **{anonymity_label}**")

    catastrophe_options = await self.get_catastrophe_options(lang)
    catastrophe_value = session.settings.get(CATASTROPHE_KEY, CATASTROPHE_DEFAULT)
    catastrophe_label = next((label for value, label, _ in catastrophe_options if value == catastrophe_value), catastrophe_value)
    lines.append(f"• {settings_titles.get(CATASTROPHE_KEY, CATASTROPHE_KEY)}: **{catastrophe_label}**")

    ai_story_options = await self.get_ai_story_options(lang)
    ai_story_value = session.settings.get(AI_STORY_KEY, AI_STORY_DEFAULT)
    ai_story_label = next((label for value, label, _ in ai_story_options if value == ai_story_value), ai_story_value)
    lines.append(f"• {settings_titles.get(AI_STORY_KEY, AI_STORY_KEY)}: **{ai_story_label}**")

    return lines

  async def build_settings_component(self, session: BunkerSession, lang: str, strings: dict):
    return build_settings_view(
      session, strings, await self.get_settings_titles(lang), await self.get_anonymity_options(lang), await self.get_catastrophe_options(lang),
      await self.get_ai_story_options(lang)
    )

  async def build_status_text(self, session: BunkerSession, strings: dict) -> str:
    if session.cancelled:
      return f"## {strings['status_ended']}"
    if session.round_phase == PHASE_FINISHED:
      return f"## {strings['status_finished']}"
    phase_title = strings.get(f"phase_{session.round_phase}", "")
    return f"## {strings['status_in_progress']}\n### {strings['round_label']} {session.round_number}: {phase_title}"

  async def build_started_component(self, session: BunkerSession, lang: str, extra_text: str = ""):
    strings = await self.get_strings(lang)
    difficulty_options = await self.get_difficulty_options(lang)
    difficulty_label = next((label for value, label, _ in difficulty_options if value == session.difficulty), session.difficulty)
    settings_lines = await self.build_settings_summary_lines(session, lang)
    participants_text = "\n".join(f"• <@{player_id}>" for player_id in session.player_ids)
    if session.bots:
      participants_text += f"\n🤖 **{strings['bots_label']}:** {session.bots}"
    participants_text += extra_text
    status_text = await self.build_status_text(session, strings)
    return build_started_view(session, strings, difficulty_label, settings_lines, participants_text, status_text)

  async def refresh_main_message(self, session: BunkerSession, lang: str) -> bool:
    if not session.channel_id or not session.message_id:
      return True
    if session.started:
      component = await self.build_started_component(session, lang)
    else:
      strings = await self.get_strings(lang)
      difficulty_options = await self.get_difficulty_options(lang)
      component = build_main_view(session, strings, difficulty_options)
    try:
      await self.bot.http.edit_message(session.channel_id, session.message_id, components=[component.to_dict()], allowed_mentions=mentions_for())
      self.rendered[("main", session.id)] = self.main_key(session)
      return True
    except NotFound:
      await self.update_session_fields(session, message_id=None)
      return True
    except HTTPException:
      log.warning("Bunker %s: cannot edit main message", session.id, exc_info=True)
      return False

  def build_setting_error_message(self, strings: dict, result: dict) -> str:
    if result["reason"] == "parse_error":
      return strings["setting_error_parse"]
    min_display = format_setting_display(result["kind"], result["min"])
    max_display = format_setting_display(result["kind"], result["max"])
    return f"{strings['setting_error_range']}: {min_display} – {max_display}"


  async def handle_interaction(self, interaction: Interaction) -> bool:
    try:
      return await self._handle_interaction(interaction)
    except NotFound:
      log.warning("Bunker: interaction expired before the response was sent", exc_info=True)
      return True

  async def _handle_interaction(self, interaction: Interaction) -> bool:
    if interaction.type != InteractionType.component:
      return False

    custom_id = interaction.data.get("custom_id") if interaction.data else None
    if not custom_id or not custom_id.startswith("bunker|"):
      return False

    parts = custom_id.split("|")
    action = parts[1]
    mode = None
    if action in DEFER_UPDATE_ACTIONS:
      mode = "update"
      await interaction.response.defer()
    elif action in DEFER_EPHEMERAL_ACTIONS:
      mode = "ephemeral"
      await interaction.response.defer(ephemeral=True, with_message=True)

    async def say(text: str) -> None:
      if mode == "ephemeral":
        await interaction.edit_original_message(content=text)
      elif mode == "update":
        await interaction.followup.send(text, ephemeral=True)
      else:
        await interaction.response.send_message(text, ephemeral=True)

    async def show(components: list) -> None:
      if mode == "ephemeral":
        await interaction.edit_original_message(components=components)
      else:
        await interaction.response.send_message(components=components, flags=flags, ephemeral=True)

    async def update(components: list) -> None:
      if mode == "update":
        await interaction.edit_original_message(components=components)
      else:
        await interaction.response.edit_message(components=components)

    if action == "activity":
      await self.prepare_activity_redirect(interaction, parts[-1])
      await self.launch_activity(interaction)
      return True

    lang = await self.get_lang(interaction)
    strings = await self.get_strings(lang)

    if action == "rules":
      await show([build_rules_view(strings)])
      return True

    session_id = parts[-1]
    session = await self.load_session(session_id)

    if session is None or session.cancelled:
      await say(strings["session_inactive"])
      return True

    if action == "endgame":
      if interaction.user.id != session.creator_id:
        await say(strings["only_creator_endgame"])
        return True
      async with self.session_lock(session.id):
        session.cancelled = True
        await self.delete_session(session.id)
      public, public_strings = await self.public_context(session)
      await update([build_game_ended_view(public_strings)])
      await self.refresh_main_message(session, public)
      return True

    if action == "translate":
      await show([await self.build_game_overview(session, lang, controls=False)])
      return True

    if action == "phaseaction":
      participant_id = str(interaction.user.id)
      alive_ids = {str(value) for value in session.alive_participant_ids}
      if interaction.user.id not in session.player_ids or participant_id not in alive_ids:
        await say(strings["not_a_player"])
        return True

      if session.round_phase == PHASE_REVEAL:
        if participant_id in session.round_reveals:
          await say(strings["reveal_recorded"])
          return True
        options = await self.build_reveal_options(session, participant_id, strings, lang)
        if options:
          await show([build_reveal_selection_view(session, strings, options)])
          return True

      elif session.round_phase in (PHASE_VOTING, PHASE_TIEBREAK):
        is_tiebreak = session.round_phase == PHASE_TIEBREAK
        votes = session.tiebreak_votes if is_tiebreak else session.round_votes
        if participant_id in votes:
          await say(strings["vote_recorded"])
          return True
        candidates = session.tiebreak_candidates if is_tiebreak else session.alive_participant_ids
        options = self.build_vote_options(session, candidates, interaction.guild)
        if options:
          await show([build_vote_selection_view(session, strings, options, is_tiebreak)])
          return True

      await say(strings["session_inactive"])
      return True

    if action == "reveal":
      if interaction.user.id not in session.player_ids:
        await say(strings["not_a_player"])
        return True
      trait_name = interaction.data["values"][0]
      participant_id = str(interaction.user.id)
      error = None

      async with self.session_lock(session.id):
        session = await self.load_session(session.id)
        if session is None or session.cancelled or session.round_phase != PHASE_REVEAL:
          error = "session_inactive"
        elif participant_id not in {str(value) for value in session.alive_participant_ids}:
          error = "not_a_player"
        elif participant_id in session.round_reveals:
          error = "reveal_recorded"
        elif trait_name not in remaining_trait_types(session, participant_id):
          error = "trait_already_revealed"
        else:
          session.set_reveal(participant_id, trait_name)
          await self.end_phase_early_if_ready(session)
          await self.save_session(session)

      if error:
        await say(strings[error])
        return True

      await update([await self.build_player_phase_component(session, participant_id, lang)])
      await self.refresh_player_panel(session, participant_id)
      return True

    if action == "vote":
      if interaction.user.id not in session.player_ids:
        await say(strings["not_a_player"])
        return True
      target = str(interaction.data["values"][0])
      participant_id = str(interaction.user.id)
      error = None

      async with self.session_lock(session.id):
        session = await self.load_session(session.id)
        if session is None or session.cancelled or session.round_phase != PHASE_VOTING:
          error = "session_inactive"
        else:
          alive = {str(value) for value in session.alive_participant_ids}
          if participant_id not in alive:
            error = "not_a_player"
          elif target not in alive:
            error = "invalid_vote_target"
          elif participant_id in session.round_votes:
            error = "vote_recorded"
          else:
            session.set_vote(participant_id, target)
            await self.end_phase_early_if_ready(session)
            await self.save_session(session)

      if error:
        await say(strings[error])
        return True

      await update([await self.build_player_phase_component(session, participant_id, lang)])
      await self.refresh_player_panel(session, participant_id)
      return True

    if action == "revealall":
      if interaction.user.id not in session.player_ids:
        await say(strings["not_a_player"])
        return True
      participant_id = str(interaction.user.id)
      error = None

      async with self.session_lock(session.id):
        session = await self.load_session(session.id)
        if session is None or session.cancelled:
          error = "session_inactive"
        elif participant_id in {str(value) for value in session.alive_participant_ids}:
          error = "not_a_player"
        else:
          session.revealed_traits[participant_id] = all_trait_choices(session, participant_id)
          await self.save_session(session)

      if error:
        await say(strings[error])
        return True

      await update([await self.build_player_phase_component(session, participant_id, lang)])
      await self.refresh_board(session)
      public, _ = await self.public_context(session)
      tm = self.bot.get_cog("TranslateMessage")
      text = await tm.translate_message("bunker.result.reveal_all", public, variables={"player": f"<@{participant_id}>"})
      await self.announce_to_game(session, None, text)
      return True

    if action == "repair":
      if interaction.user.id not in session.player_ids:
        await say(strings["not_a_player"])
        return True
      if monotonic() - self.repair_cooldowns.get(session.id, -REPAIR_COOLDOWN_SECONDS) < REPAIR_COOLDOWN_SECONDS:
        await say(strings["repair_cooldown"])
        return True
      self.repair_cooldowns[session.id] = monotonic()
      pending = await self.reconcile_session(session.id, force=True, budget=REPAIR_BUDGET)
      if pending < 0:
        await say(strings["repair_cooldown"])
      elif pending > 0:
        await say(strings["repair_partial"])
      else:
        await say(strings["repair_done"])
      return True

    if action == "alive":
      if interaction.user.id not in session.player_ids:
        await say(strings["not_a_player"])
        return True
      blocks = await self.build_board_blocks(session, strings, lang, alive_only=True)
      chunks = pack_text_blocks(blocks, BOARD_CHUNK_LIMIT)
      if not chunks:
        await say(strings["session_inactive"])
        return True
      for index, chunk in enumerate(chunks):
        texts = [TextDisplay(f"## 📋 {strings['alive_button']}")] if index == 0 else []
        texts.append(TextDisplay(chunk))
        component = Container(texts, Color.gold().value, spoiler=False)
        if index == 0:
          await show([component])
        else:
          await interaction.followup.send(components=[component], flags=flags, ephemeral=True)
      return True

    if action == "myprofile":
      if interaction.user.id not in session.player_ids:
        await say(strings["not_a_player"])
        return True
      card = session.player_cards.get(str(interaction.user.id))
      if card is None:
        await say(strings["session_inactive"])
        return True
      await show([await self.build_profile_view(card, lang, strings)])
      return True

    if action == "join":
      error = None
      async with self.session_lock(session.id):
        session = await self.load_session(session.id)
        if session is None or session.cancelled:
          error = "session_inactive"
        elif session.started:
          error = "game_already_started"
        elif interaction.user.id in session.player_ids:
          error = "already_joined"
        elif session.player_count() >= session.max_players():
          error = "lobby_full"
        else:
          session.player_ids.append(interaction.user.id)
          await self.save_session(session)
      if error:
        await say(strings[error])
        return True
      public, public_strings = await self.public_context(session)
      await update([build_main_view(session, public_strings, await self.get_difficulty_options(public))])
      return True

    if action == "bots":
      if interaction.user.id != session.creator_id:
        await say(strings["only_creator_bots"])
        return True
      bots_count = to_int(interaction.data["values"][0])
      error = None
      async with self.session_lock(session.id):
        session = await self.load_session(session.id)
        if session is None or session.cancelled:
          error = "session_inactive"
        elif session.started:
          error = "game_already_started"
        elif bots_count < 0 or bots_count + len(session.player_ids) > session.max_players():
          error = "lobby_full"
        else:
          session.bots = bots_count
          await self.save_session(session)
      if error:
        await say(strings[error])
        return True
      public, public_strings = await self.public_context(session)
      await update([build_main_view(session, public_strings, await self.get_difficulty_options(public))])
      return True

    if action == "cancel":
      if interaction.user.id != session.creator_id:
        await say(strings["only_creator_cancel"])
        return True
      async with self.session_lock(session.id):
        session.cancelled = True
        await self.delete_session(session.id)
      _, public_strings = await self.public_context(session)
      await update([build_cancelled_view(public_strings)])
      return True

    if action == "start":
      if interaction.user.id != session.creator_id:
        await say(strings["only_creator_start"])
        return True

      start_lock = self.start_locks.setdefault(session.id, Lock())
      if start_lock.locked():
        await say(strings["game_already_started"])
        return True

      async with start_lock:
        error = None
        async with self.session_lock(session.id):
          latest_session = await self.load_session(session.id)
          if latest_session is None or latest_session.cancelled:
            error = "session_inactive"
          elif latest_session.started:
            error = "game_already_started"
          elif not latest_session.can_start():
            error = "need_more_players_than_capacity"
          else:
            latest_session.started = True
            await self.save_session(latest_session)
            session = latest_session
        if error:
          await say(strings[error])
          return True

      guild_lang, public_strings = await self.public_context(session)
      channel, error = await self.create_game_channel(session, guild_lang)
      if error is not None:
        await self.update_session_fields(session, started=False)
        difficulty_options = await self.get_difficulty_options(guild_lang)
        await interaction.edit_original_message(components=[build_main_view(session, public_strings, difficulty_options)])
        await interaction.followup.send(
          components=[Container([TextDisplay(strings["start_channel_error"])], Color.red().value, spoiler=False)],
          flags=flags, ephemeral=True
        )
        return True

      async with self.session_lock(session.id):
        latest_session = await self.load_session(session.id)
        if latest_session is None:
          latest_session = None
        else:
          session = latest_session
          session.game_channel_id = channel.id
          assign_catastrophe_and_cards(session)
          session.game_started_at = int(time())
          session.round_number = 1
          session.begin_round(session.game_started_at)
          session.round_phase = PHASE_INITIAL_DISCUSSION
          session.begin_phase(session.game_started_at)
          session.phase_ends_at = int(time()) + phase_duration(session, PHASE_INITIAL_DISCUSSION)
          await self.save_session(session)

      if latest_session is None:
        await interaction.edit_original_message(components=[build_cancelled_view(public_strings)])
        return True

      self.game_channels[channel.id] = session.id

      try:
        await self.create_info_thread(session, channel, guild_lang)
        overview_message = await self.send_component_message(SimpleNamespace(id=self.info_id(session)), await self.build_game_overview(session, guild_lang))
        phase_message = await self.send_component_message(SimpleNamespace(id=self.info_id(session)), await self.build_phase_component(session, guild_lang))
        await self.update_session_fields(session, overview_message_id=int(overview_message["id"]), phase_message_id=int(phase_message["id"]))
        await self.pin_message(self.info_id(session), int(overview_message["id"]))
        self.rendered[("phase", session.id)] = self.phase_key(session)
        self.rendered[("overview", session.id)] = "0"
        await self.refresh_board(session)
        self.announcing.add(session.id)
        try:
          announcement_id = await self.announce_phase(session)
        finally:
          self.announcing.discard(session.id)
        await self.update_session_fields(session, phase_announcement_id=announcement_id)
      except (Forbidden, HTTPException):
        log.warning("Bunker %s: cannot post initial game messages", session.id, exc_info=True)

      failed_player_ids = await self.create_player_threads(session, channel, guild_lang)

      extra_text = ""
      if failed_player_ids:
        failed_mentions = ", ".join(f"<@{player_id}>" for player_id in failed_player_ids)
        extra_text = f"\n\n⚠️ {public_strings['threads_failed_warning']}: {failed_mentions}"

      await interaction.edit_original_message(components=[await self.build_started_component(session, guild_lang, extra_text)])
      self.rendered[("main", session.id)] = self.main_key(session)
      return True

    if action == "settings":
      if interaction.user.id != session.creator_id:
        await say(strings["only_creator_settings"])
        return True
      await show([await self.build_settings_component(session, lang, strings)])
      return True

    if action == "difficulty":
      if interaction.user.id != session.creator_id:
        await say(strings["only_creator_difficulty"])
        return True
      value = interaction.data["values"][0]

      def apply_difficulty(current: BunkerSession) -> None:
        current.difficulty = value

      session = await self.mutate_session(session.id, apply_difficulty)
      if session is None:
        await say(strings["session_inactive"])
        return True
      public, public_strings = await self.public_context(session)
      await update([build_main_view(session, public_strings, await self.get_difficulty_options(public))])
      return True

    if action == "setedit":
      key = parts[2]
      if interaction.user.id != session.creator_id:
        await say(strings["only_creator_setting"])
        return True
      settings_titles = await self.get_settings_titles(lang)
      title = settings_titles.get(key, key)
      entry = get_setting_entry(key)
      kind = entry[2] if entry else "count"
      current_value = session.settings.get(key, "")
      current_display = format_setting_edit_default(kind, current_value)
      placeholder = strings["setting_modal_placeholder_duration"] if kind == "duration" else strings["setting_modal_placeholder_count"]
      modal, text_input = build_setting_modal(title, f"bunker|setsubmit|{key}|{session.id}", placeholder, current_display)
      edited_session_id = session.id
      public = await self.public_lang(session)

      async def on_submit(modal_interaction: Interaction) -> None:
        result = validate_setting_value(key, text_input.value)
        if not result["valid"]:
          await modal_interaction.response.send_message(self.build_setting_error_message(strings, result), ephemeral=True)
          return

        error_key = None
        updated = None
        async with self.session_lock(edited_session_id):
          current = await self.load_session(edited_session_id)
          if current is None or current.cancelled:
            error_key = "session_inactive"
          elif current.started:
            error_key = "game_already_started"
          else:
            candidate = dict(current.settings)
            candidate[key] = str(result["value"])
            max_players = to_int(candidate["max_players"])
            capacity = to_int(candidate["bunker_capacity"])
            if max_players < capacity + MIN_EXTRA_PLAYERS_OVER_CAPACITY or max_players < current.player_count():
              error_key = "setting_error_conflict"
            else:
              current.settings = candidate
              await self.save_session(current)
              updated = current
        if error_key is not None:
          await modal_interaction.response.send_message(strings[error_key], ephemeral=True)
          return
        await modal_interaction.response.edit_message(components=[await self.build_settings_component(updated, lang, strings)])
        await self.refresh_main_message(updated, public)

      modal.callback = on_submit
      await interaction.response.send_modal(modal)
      return True

    if action in ("anonymity", "catastrophe", "aistory"):
      if interaction.user.id != session.creator_id:
        await say(strings["only_creator_setting"])
        return True
      setting_key = {"anonymity": ANONYMITY_KEY, "catastrophe": CATASTROPHE_KEY, "aistory": AI_STORY_KEY}[action]
      value = interaction.data["values"][0]

      def apply_select(current: BunkerSession) -> None:
        current.settings[setting_key] = value

      session = await self.mutate_session(session.id, apply_select)
      if session is None:
        await say(strings["session_inactive"])
        return True
      await update([await self.build_settings_component(session, lang, strings)])
      await self.refresh_main_message(session, await self.public_lang(session))
      return True

    return False

def setup(bot: Bot) -> None:
  bot.add_cog(BunkerUtils(bot))