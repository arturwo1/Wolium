import random
import re
import zlib
from datetime import datetime, timezone
from json import dumps, loads
from typing import Optional
from uuid import uuid4

from nextcord import Color, MessageFlags, Permissions
from nextcord.components import Container, TextDisplay, Separator, ActionRow, Button, SelectOption, StringSelect
from nextcord.enums import SeparatorSpacingSize, ButtonStyle, TextInputStyle
from nextcord.ui import Modal, TextInput

from Utils.parse_time import parse_time
from Utils.bunker_config import (
  SCENARIOS, pick_bunker_description_key, pick_equipment_keys, pick_problem_keys, generate_bot_names, CHARACTERISTIC_POOLS, unique_values, pick_gender_key,
  roll_age
)

flags = MessageFlags()
flags.is_components_v2 = True

CATEGORY_NAME_KEY = "bunker.category.name"
CATEGORY_CREATE_REASON_KEY = "bunker.category.create_reason"
GAME_CHANNEL_CREATE_REASON_KEY = "bunker.game_channel.create_reason"
GAME_CHANNEL_NAME_PREFIX_KEY = "bunker.game_channel.name_prefix"
INFO_THREAD_NAME_KEY = "bunker.game_channel.info_thread_name"
THREAD_DEFAULT_NAME_KEY = "bunker.thread.default_name"
THREAD_CREATE_REASON_KEY = "bunker.thread.create_reason"
SESSION_KEY_PREFIX = "bunker:sessions:"
SESSION_TTL_SECONDS = 21600
MAX_GUILD_SESSIONS = 5
MIN_EXTRA_PLAYERS_OVER_CAPACITY = 2
MAX_THREAD_RETRY_ATTEMPTS = 5

DIFFICULTY_PROFILES = {
  "easy": {"apocalypse_years": (1, 10), "supply_ratio": (1.0, 2.0), "equipment": (6, 8), "problems": (1, 2)},
  "normal": {"apocalypse_years": (5, 25), "supply_ratio": (0.5, 1.5), "equipment": (4, 6), "problems": (2, 4)},
  "hard": {"apocalypse_years": (15, 40), "supply_ratio": (0.3, 1.0), "equipment": (3, 5), "problems": (3, 5)},
  "nightmare": {"apocalypse_years": (30, 60), "supply_ratio": (0.1, 0.7), "equipment": (2, 4), "problems": (4, 6)}
}
DEFAULT_DIFFICULTY = "normal"
BOT_REACTION_MIN_SECONDS = 2
BOT_REACTION_MAX_SECONDS = 3
BOARD_CHUNK_LIMIT = 3500
MAX_BOT_OPTIONS = 24
TRAIT_EMOJIS = {"gender": "🧬", "age": "🎂", "profession": "💼", "health": "🩺", "hobby": "🎨", "phobia": "😱", "skill": "🛠️", "baggage": "🎒"}
CHAT_MESSAGE_LIMIT = 1000

AI_TEASER_LIMIT = 400
AI_SUMMARY_LIMIT = 800
GENERATION_PROGRESS_SECONDS = 2
PROGRESS_CLOCKS = ("🕛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚")
PROGRESS_BAR_CELLS = 12
PROGRESS_BAR_WIDTH = 3
PROGRESS_STAGE_STEPS = 4
PROGRESS_STAGE_KEYS = tuple(f"bunker.result.ai_story.stage.{index}" for index in range(6))
ACTIVITY_PATH_TEMPLATE = "/profile/?modal=bunker&game={game_id}"
CLIENT_DROPPED_KEYS = ("id", "guild_id", "creator_id", "winners")
CLIENT_AI_KEYS = ("title", "teaser", "summary", "story")
CLIENT_DISCORD_KEYS = ("channel_id", "channel_name")
CLIENT_DROPPED_PHASE_KEYS = ("started_at", "auto_voters")
HEAL_INTERVAL_SECONDS = 5
HEAL_BUDGET = 10
REPAIR_BUDGET = 40
REPAIR_COOLDOWN_SECONDS = 10
HEAL_BACKOFF_MAX_SECONDS = 60
OUTBOX_LIMIT = 20
OUTBOX_MAX_ATTEMPTS = 40
EXTRA_TRAIT_KINDS = ("skill", "baggage", "phobia", "hobby")
MAX_EXTRA_TRAITS = 5
GAME_STATUS_FINISHED = 1
GAME_STATUS_TIMEOUT = 2
GAME_STATUS_ENDED = 3
MATCH_RECORD_PREFIX = "bunker:matches:"
MATCH_RECORD_TTL_SECONDS = 18000
MATCH_RECOVERY_INTERVAL_MINUTES = 10
MATCH_RECOVERY_BATCH = 20
FINISHED_GRACE_SECONDS = 120

PHASE_INITIAL_DISCUSSION = "initial_discussion"
PHASE_REVEAL = "reveal"
PHASE_DISCUSSION = "discussion"
PHASE_VOTING = "voting"
PHASE_TIEBREAK = "tiebreak"
PHASE_PAUSE = "pause"
PHASE_FINISHED = "finished"

TRAIT_CARD_KEYS = {
  "gender": "gender_key",
  "age": "age",
  "profession": "profession_keys",
  "health": "health_condition_keys",
  "hobby": "hobby_keys",
  "phobia": "phobia_keys",
  "skill": "skill_keys",
  "baggage": "baggage_keys"
}

DIFFICULTY_OPTIONS = [
  ("easy", "bunker.difficulty.easy.label", "bunker.difficulty.easy.description"),
  ("normal", "bunker.difficulty.normal.label", "bunker.difficulty.normal.description"),
  ("hard", "bunker.difficulty.hard.label", "bunker.difficulty.hard.description"),
  ("nightmare", "bunker.difficulty.nightmare.label", "bunker.difficulty.nightmare.description")
]

SETTINGS_CATEGORIES = [
  ("max_players", "bunker.settings.max_players.title", "count", 4, 20, 12),
  ("bunker_capacity", "bunker.settings.bunker_capacity.title", "count", 2, 10, 4),
  ("extra_traits_count", "bunker.settings.extra_traits_count.title", "count", 0, 5, 3),
  ("game_duration", "bunker.settings.game_duration.title", "duration", 1800, 259200, 86400),
  ("trait_selection_duration", "bunker.settings.trait_selection_duration.title", "duration", 15, 300, 60),
  ("discussion_duration", "bunker.settings.discussion_duration.title", "duration", 30, 600, 120),
  ("voting_duration", "bunker.settings.voting_duration.title", "duration", 15, 300, 60),
  ("round_pause_duration", "bunker.settings.round_pause_duration.title", "duration", 5, 120, 15)
]

SETTINGS_BUTTON_GROUPS = (
  ("max_players", "bunker_capacity", "extra_traits_count"),
  ("game_duration",),
  ("trait_selection_duration", "discussion_duration", "voting_duration", "round_pause_duration")
)

ANONYMITY_KEY = "anonymity"
ANONYMITY_DEFAULT = "off"
ANONYMITY_OPTIONS = [
  ("off", "bunker.settings.anonymity.off.label", "bunker.settings.anonymity.off.description"),
  ("on", "bunker.settings.anonymity.on.label", "bunker.settings.anonymity.on.description")
]

AI_STORY_KEY = "ai_story"
AI_STORY_DEFAULT = "on"
AI_STORY_OPTIONS = [
  ("off", "bunker.settings.ai_story.off.label", "bunker.settings.ai_story.off.description"),
  ("on", "bunker.settings.ai_story.on.label", "bunker.settings.ai_story.on.description")
]

CATASTROPHE_KEY = "catastrophe_mode"
CATASTROPHE_DEFAULT = "random"
CATASTROPHE_RANDOM_OPTION = ("random", "bunker.settings.catastrophe.random.label", "bunker.settings.catastrophe.random.description")

def build_catastrophe_options() -> list:
  options = [CATASTROPHE_RANDOM_OPTION]
  for scenario in SCENARIOS:
    options.append((scenario["slug"], scenario["type_key"], None))
  return options

def resolve_catastrophe(catastrophe_mode: str) -> dict:
  if catastrophe_mode and catastrophe_mode != CATASTROPHE_DEFAULT:
    matched = next((scenario for scenario in SCENARIOS if scenario["slug"] == catastrophe_mode), None)
    if matched is not None:
      return matched
  return random.choice(SCENARIOS)

REQUIRED_PERMISSIONS = (
  ("manage_channels", "bunker.permissions.manage_channels"),
  ("manage_messages", "bunker.permissions.manage_messages"),
  ("read_message_history", "bunker.permissions.read_message_history"),
  ("manage_roles", "bunker.permissions.manage_roles"),
  ("manage_threads", "bunker.permissions.manage_threads"),
  ("create_public_threads", "bunker.permissions.create_public_threads"),
  ("create_private_threads", "bunker.permissions.create_private_threads"),
  ("send_messages_in_threads", "bunker.permissions.send_messages_in_threads")
)

THREAD_PERMISSIONS_OFF = {"send_messages_in_threads": False, "create_public_threads": False, "create_private_threads": False}

def mentions_for(users=()) -> dict:
  return {"parse": [], "users": [str(user) for user in users]}

def get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

def session_key(session_id: str) -> str:
  return f"{SESSION_KEY_PREFIX}{session_id}"

def get_missing_permission_keys(permissions: Permissions) -> list:
  return [key for attribute, key in REQUIRED_PERMISSIONS if not getattr(permissions, attribute, False)]

def build_game_channel_name(prefix: str, index: int) -> str:
  return f"{prefix}{index}"

def build_player_thread_name(display_name: str, fallback: str) -> str:
  sanitized = "-".join(display_name.strip().split())
  return sanitized[:100] if sanitized else fallback

def get_setting_entry(key: str) -> Optional[tuple]:
  return next((item for item in SETTINGS_CATEGORIES if item[0] == key), None)

def to_int(value) -> int:
  try:
    return int(value)
  except (ValueError, TypeError):
    return int(float(value))

def pack_text_blocks(blocks: list, limit: int) -> list:
  chunks = []
  current = ""
  for block in blocks:
    block = block[:limit]
    if current and len(current) + 2 + len(block) > limit:
      chunks.append(current)
      current = block
    else:
      current = f"{current}\n\n{block}" if current else block
  if current:
    chunks.append(current)
  return chunks

def format_duration(seconds) -> str:
  seconds = to_int(seconds)
  if seconds >= 86400 and seconds % 86400 == 0:
    return f"{seconds // 86400}d"
  if seconds >= 3600 and seconds % 3600 == 0:
    return f"{seconds // 3600}h"
  if seconds >= 60 and seconds % 60 == 0:
    return f"{seconds // 60}m"
  return f"{seconds}s"

def format_duration_pretty(seconds) -> str:
  seconds = to_int(seconds)
  days, remainder = divmod(seconds, 86400)
  hours, remainder = divmod(remainder, 3600)
  minutes, secs = divmod(remainder, 60)
  parts = []
  if days:
    parts.append(f"{days}d")
  if hours:
    parts.append(f"{hours}h")
  if minutes:
    parts.append(f"{minutes}m")
  if secs or not parts:
    parts.append(f"{secs}s")
  return " ".join(parts)

def format_setting_display(kind: str, value) -> str:
  if value == "":
    return value
  return format_duration_pretty(value) if kind == "duration" else str(value)

def format_setting_edit_default(kind: str, value) -> str:
  if value == "":
    return value
  return format_duration(value) if kind == "duration" else str(value)

def validate_setting_value(key: str, raw_value: Optional[str]) -> dict:
  entry = get_setting_entry(key)
  if entry is None:
    return {"valid": False, "reason": "unknown_setting"}

  _, _, kind, min_value, max_value, _ = entry

  if raw_value is None or str(raw_value).strip() == "":
    return {"valid": False, "reason": "parse_error", "kind": kind, "min": min_value, "max": max_value}

  value = None
  if kind == "duration":
    try:
      value = parse_time(raw_value)
    except (ValueError, TypeError):
      try:
        value = int(raw_value)
      except (ValueError, TypeError):
        value = None
  else:
    try:
      value = int(raw_value)
    except (ValueError, TypeError):
      value = None

  if value is None:
    return {"valid": False, "reason": "parse_error", "kind": kind, "min": min_value, "max": max_value}
  value = to_int(value)
  if value < min_value:
    return {"valid": False, "reason": "too_low", "kind": kind, "min": min_value, "max": max_value, "value": value}
  if value > max_value:
    return {"valid": False, "reason": "too_high", "kind": kind, "min": min_value, "max": max_value, "value": value}

  return {"valid": True, "value": value}

class BunkerSession:
  def __init__(self, guild_id: int, creator_id: int, settings: dict):
    self.id = uuid4().hex[:8]
    self.guild_id = guild_id
    self.creator_id = creator_id
    self.player_ids = [creator_id]
    self.bots = 0
    self.difficulty = "normal"
    self.settings = settings
    self.category_id = None
    self.channel_id = None
    self.message_id = None
    self.game_channel_id = None
    self.info_thread_id = None
    self.player_threads = {}
    self.player_panel_message_ids = {}
    self.thread_retry_attempts = 0
    self.catastrophe = None
    self.apocalypse_duration_years = None
    self.player_cards = {}
    self.bot_names = []
    self.round_number = 0
    self.round_phase = None
    self.phase_ends_at = None
    self.alive_participant_ids = []
    self.revealed_traits = {}
    self.round_reveals = {}
    self.round_votes = {}
    self.tiebreak_votes = {}
    self.tiebreak_candidates = []
    self.phase_message_id = None
    self.phase_result = None
    self.bunker_description_key = None
    self.food_supply_years = None
    self.water_supply_years = None
    self.equipment_keys = []
    self.problem_keys = []
    self.started = False
    self.cancelled = False
    self.game_started_at = None
    self.bot_action_at = {}
    self.phase_announcement_id = None
    self.rounds = {}
    self.overview_message_id = None
    self.board_message_ids = []
    self.finished_at = None
    self.end_reason = None
    self.ai_result = None
    self.outbox = []

  def player_count(self) -> int:
    return len(self.player_ids) + self.bots

  def max_players(self) -> int:
    return to_int(self.settings.get("max_players", 12))

  def bunker_capacity(self) -> int:
    return to_int(self.settings.get("bunker_capacity", 4))

  def rounds_count(self) -> int:
    return max(self.player_count() - self.bunker_capacity(), 0)

  def can_start(self) -> bool:
    return self.player_count() >= self.bunker_capacity() + MIN_EXTRA_PLAYERS_OVER_CAPACITY

  def round_record(self) -> dict:
    record = self.rounds.setdefault(str(self.round_number), {"started_at": None, "phases": {}})
    record.setdefault("phases", {})
    return record

  def phase_record(self, phase: Optional[str] = None) -> dict:
    return self.round_record()["phases"].setdefault(phase or self.round_phase, {"started_at": None, "messages": []})

  def begin_round(self, now: int) -> None:
    self.round_record()["started_at"] = now

  def begin_phase(self, now: int) -> None:
    self.phase_record()["started_at"] = now

  def set_reveal(self, participant_id, choice: str) -> None:
    key = str(participant_id)
    self.revealed_traits.setdefault(key, []).append(choice)
    self.round_reveals[key] = choice
    self.phase_record(PHASE_REVEAL).setdefault("reveals", {})[key] = choice

  def set_vote(self, participant_id, target) -> None:
    key = str(participant_id)
    self.round_votes[key] = str(target)
    self.phase_record(PHASE_VOTING).setdefault("votes", {})[key] = str(target)

  def add_chat_message(self, participant_id, text: str, now: int) -> None:
    record = self.phase_record()
    key = str(participant_id)
    messages = record.setdefault("messages", [])
    if messages and key in messages[-1]:
      messages[-1][key] += f"\n\n{text}"
    else:
      moment = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
      messages.append({key: f"{moment} - {text}"})

  def all_participant_ids(self) -> list:
    ids = [str(player_id) for player_id in self.player_ids]
    ids += [f"bot_{index}" for index in range(1, self.bots + 1)]
    return ids

  def to_dict(self) -> dict:
    return {
      "id": self.id,
      "guild_id": self.guild_id,
      "creator_id": self.creator_id,
      "player_ids": self.player_ids,
      "bots": self.bots,
      "difficulty": self.difficulty,
      "settings": self.settings,
      "category_id": self.category_id,
      "channel_id": self.channel_id,
      "message_id": self.message_id,
      "game_channel_id": self.game_channel_id,
      "info_thread_id": self.info_thread_id,
      "player_threads": self.player_threads,
      "player_panel_message_ids": self.player_panel_message_ids,
      "thread_retry_attempts": self.thread_retry_attempts,
      "catastrophe": self.catastrophe,
      "apocalypse_duration_years": self.apocalypse_duration_years,
      "player_cards": self.player_cards,
      "bot_names": self.bot_names,
      "round_number": self.round_number,
      "round_phase": self.round_phase,
      "phase_ends_at": self.phase_ends_at,
      "alive_participant_ids": self.alive_participant_ids,
      "revealed_traits": self.revealed_traits,
      "round_reveals": self.round_reveals,
      "round_votes": self.round_votes,
      "tiebreak_votes": self.tiebreak_votes,
      "tiebreak_candidates": self.tiebreak_candidates,
      "phase_message_id": self.phase_message_id,
      "phase_result": self.phase_result,
      "bunker_description_key": self.bunker_description_key,
      "food_supply_years": self.food_supply_years,
      "water_supply_years": self.water_supply_years,
      "equipment_keys": self.equipment_keys,
      "problem_keys": self.problem_keys,
      "started": self.started,
      "cancelled": self.cancelled,
      "game_started_at": self.game_started_at,
      "bot_action_at": self.bot_action_at,
      "phase_announcement_id": self.phase_announcement_id,
      "rounds": self.rounds,
      "overview_message_id": self.overview_message_id,
      "board_message_ids": self.board_message_ids,
      "finished_at": self.finished_at,
      "end_reason": self.end_reason,
      "ai_result": self.ai_result,
      "outbox": self.outbox
    }

  @classmethod
  def from_dict(cls, data: dict) -> "BunkerSession":
    session = cls.__new__(cls)
    session.id = data["id"]
    session.guild_id = data["guild_id"]
    session.creator_id = data["creator_id"]
    session.player_ids = data["player_ids"]
    session.bots = data["bots"]
    session.difficulty = data["difficulty"]
    session.settings = data["settings"]
    session.category_id = data.get("category_id")
    session.channel_id = data.get("channel_id")
    session.message_id = data.get("message_id")
    session.game_channel_id = data.get("game_channel_id")
    session.info_thread_id = data.get("info_thread_id")
    session.player_threads = data.get("player_threads", {})
    session.player_panel_message_ids = data.get("player_panel_message_ids", {})
    session.thread_retry_attempts = data.get("thread_retry_attempts", 0)
    session.catastrophe = data.get("catastrophe")
    session.apocalypse_duration_years = data.get("apocalypse_duration_years")
    session.player_cards = data.get("player_cards", {})
    session.bot_names = data.get("bot_names", [])
    session.round_number = data.get("round_number", 0)
    session.round_phase = data.get("round_phase")
    session.phase_ends_at = data.get("phase_ends_at")
    session.alive_participant_ids = data.get("alive_participant_ids", [])
    session.revealed_traits = data.get("revealed_traits", {})
    session.round_reveals = data.get("round_reveals", {})
    session.round_votes = data.get("round_votes", {})
    session.tiebreak_votes = data.get("tiebreak_votes", {})
    session.tiebreak_candidates = data.get("tiebreak_candidates", [])
    session.phase_message_id = data.get("phase_message_id")
    session.phase_result = data.get("phase_result")
    session.bunker_description_key = data.get("bunker_description_key")
    session.food_supply_years = data.get("food_supply_years")
    session.water_supply_years = data.get("water_supply_years")
    session.equipment_keys = data.get("equipment_keys", [])
    session.problem_keys = data.get("problem_keys", [])
    session.started = data["started"]
    session.cancelled = data["cancelled"]
    session.game_started_at = data.get("game_started_at")
    session.bot_action_at = data.get("bot_action_at", {})
    session.phase_announcement_id = data.get("phase_announcement_id")
    session.rounds = data.get("rounds", {})
    session.overview_message_id = data.get("overview_message_id")
    session.board_message_ids = data.get("board_message_ids", [])
    session.finished_at = data.get("finished_at")
    session.end_reason = data.get("end_reason")
    session.ai_result = data.get("ai_result")
    session.outbox = data.get("outbox", [])
    return session

def build_main_view(session: BunkerSession, strings: dict, difficulty_options: list) -> Container:
  players_text = "\n".join(f"• <@{player_id}>" for player_id in session.player_ids)
  max_players = session.max_players()
  is_full = session.player_count() >= max_players
  can_start = session.can_start()
  info_text = "\n".join([
    f"👑 **{strings['creator_label']}:** <@{session.creator_id}>",
    f"👥 **{strings['players_label']}:** {session.player_count()}/{max_players}"
  ])

  return Container([
    TextDisplay(f"# 🏚️ {strings['title']}"),
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    TextDisplay(info_text),
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    TextDisplay(f"### 📋 {strings['participants_label']}\n{players_text}"),
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    TextDisplay(f"⚔️ {select_caption(strings['difficulty_label'], difficulty_options, session.difficulty)}"),
    ActionRow([
      StringSelect(
        custom_id=f"bunker|difficulty|{session.id}",
        options=[
          SelectOption(label=label, value=value, description=description, default=value == session.difficulty)
          for value, label, description in difficulty_options
        ],
        placeholder=strings['difficulty_placeholder'], min_values=1, max_values=1, disabled=session.started
      )
    ]),
    Separator(divider=True, spacing=SeparatorSpacingSize.small),
    TextDisplay(f"🤖 **{strings['bots_placeholder']}:** {session.bots}"),
    ActionRow([
      StringSelect(
        custom_id=f"bunker|bots|{session.id}", options=bot_count_options(session), placeholder=strings['bots_placeholder'], min_values=1, max_values=1,
        disabled=session.started
      )
    ]),
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    ActionRow([
      Button(style=ButtonStyle.secondary, label=strings['rules_button'], custom_id=f"bunker|rules|{session.id}"),
      Button(style=ButtonStyle.secondary, label=strings['settings_button'], custom_id=f"bunker|settings|{session.id}", disabled=session.started)
    ]),
    ActionRow([
      Button(style=ButtonStyle.success, label=strings['join_button'], custom_id=f"bunker|join|{session.id}", disabled=session.started or is_full),
      Button(style=ButtonStyle.danger, label=strings['cancel_button'], custom_id=f"bunker|cancel|{session.id}", disabled=session.started),
      Button(style=ButtonStyle.primary, label=strings['start_button'], custom_id=f"bunker|start|{session.id}", disabled=session.started or not can_start)
    ])
  ], Color.blurple().value, spoiler=False)

def build_rules_view(strings: dict) -> Container:
  return Container([TextDisplay(f"# 📜 {strings['rules_title']}"), TextDisplay(strings['rules_body'])], Color.dark_grey().value, spoiler=False)

def build_game_overview_view(
  session: BunkerSession, strings: dict, scenario_type: str, scenario_history: str, overview_text: str, bunker_description: str, equipment: str,
  problems: str, participants_text: str, status_text: Optional[str] = None, finished: bool = False, show_buttons: bool = True
) -> Container:
  buttons = [
    Button(style=ButtonStyle.secondary, label=strings['rules_button'], custom_id=f"bunker|rules|{session.id}"),
    Button(style=ButtonStyle.primary, label=strings['translate_button'], custom_id=f"bunker|translate|{session.id}")
  ]
  if not finished:
    buttons.append(Button(style=ButtonStyle.secondary, label=f"🛠️ {strings['repair_button']}", custom_id=f"bunker|repair|{session.id}"))
    buttons.append(Button(style=ButtonStyle.danger, label=strings['end_game_button'], custom_id=f"bunker|endgame|{session.id}"))
  components = [TextDisplay(f"# 🏚️ {strings['game_title']}"), TextDisplay(f"-# {strings['game_subtitle']}")]
  if status_text:
    components.append(TextDisplay(f"## {status_text}"))
  components.extend([
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    TextDisplay(f"## ☢️ {scenario_type}\n{quote_text(scenario_history)}"),
    TextDisplay(overview_text),
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    TextDisplay(f"### 🏗️ {strings['bunker_description_label']}\n{quote_text(bunker_description)}"),
    TextDisplay(f"### 🧰 {strings['equipment_label']}\n{equipment}"),
    TextDisplay(f"### ⚠️ {strings['problems_label']}\n{problems}"),
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    TextDisplay(f"### 👥 {strings['participants_label']}\n{participants_text}")
  ])
  if show_buttons:
    components.append(ActionRow(buttons))
  accent = Color.dark_grey() if finished else Color.dark_red()
  return Container(components, accent.value, spoiler=False)

def build_player_thread_view(session: BunkerSession, strings: dict) -> Container:
  return Container([
    TextDisplay(f"# {strings['player_panel_title']}"),
    TextDisplay(strings['player_panel_body']),
    Separator(divider=True, spacing=SeparatorSpacingSize.small),
    ActionRow([Button(style=ButtonStyle.primary, label=strings['my_profile_button'], custom_id=f"bunker|myprofile|{session.id}")])
  ], Color.blurple().value, spoiler=False)

def build_player_phase_view(session: BunkerSession, strings: dict, phase_title: str, body: str, selector=None, spoiler: bool = False) -> Container:
  components = [TextDisplay(f"# {strings['round_label']} {session.round_number}: {phase_title}")]
  if body:
    components.append(TextDisplay(quote_text(body)))
  components.append(Separator(divider=True, spacing=SeparatorSpacingSize.large))
  timing_lines = phase_timing_lines(session, strings)
  if timing_lines:
    components.append(TextDisplay("\n".join(timing_lines)))
  if selector is not None:
    components.append(ActionRow([selector]))
  components.append(ActionRow([
    Button(style=ButtonStyle.primary, label=strings['my_profile_button'], custom_id=f"bunker|myprofile|{session.id}"),
    Button(style=ButtonStyle.secondary, label=f"📜 {strings['scenario_button']}", custom_id=f"bunker|translate|{session.id}"),
    Button(style=ButtonStyle.secondary, label=f"📋 {strings['alive_button']}", custom_id=f"bunker|alive|{session.id}"),
    Button(style=ButtonStyle.secondary, label=f"🛠️ {strings['repair_button']}", custom_id=f"bunker|repair|{session.id}")
  ]))
  return Container(components, Color.blurple().value, spoiler=spoiler)

def build_story_view(session_id: str, strings: dict, chronicle_title: str, heading: str, teaser: str, summary: str, status_text: Optional[str], survivors_text: Optional[str]) -> Container:
  components = [TextDisplay(f"## {chronicle_title}"), Separator(divider=True, spacing=SeparatorSpacingSize.small)]
  if heading:
    components.append(TextDisplay(f"### {heading}"))
  if teaser:
    components.append(TextDisplay(quote_text(teaser)))
  components.append(TextDisplay(summary))
  details = [item for item in (status_text, survivors_text) if item]
  if details:
    components.extend([Separator(divider=True, spacing=SeparatorSpacingSize.small), TextDisplay("\n\n".join(details))])
  components.append(ActionRow([Button(style=ButtonStyle.primary, label=f"📖 {strings['activity_button']}", custom_id=f"bunker|activity|{session_id}")]))
  return Container(components, Color.blurple().value, spoiler=False)

def build_game_ended_view(strings: dict) -> Container:
  return Container([TextDisplay(f"# {strings['game_ended']}")], Color.red().value, spoiler=False)

def build_phase_view(session: BunkerSession, strings: dict, phase_title: str, body: str) -> Container:
  components = [TextDisplay(f"# {strings['round_label']} {session.round_number}: {phase_title}")]
  if body:
    components.append(TextDisplay(quote_text(body)))
  timing_lines = phase_timing_lines(session, strings)
  if timing_lines:
    components.extend([Separator(divider=True, spacing=SeparatorSpacingSize.large), TextDisplay("\n".join(timing_lines))])
  return Container(components, Color.blurple().value, spoiler=False)

def build_reveal_selection_view(session: BunkerSession, strings: dict, options: list) -> Container:
  selector = StringSelect(custom_id=f"bunker|reveal|{session.id}", options=options, placeholder=strings['reveal_placeholder'], min_values=1, max_values=1)
  return build_player_phase_view(session, strings, strings['reveal_title'], strings['reveal_body'], selector, True)

def build_vote_selection_view(session: BunkerSession, strings: dict, options: list, tiebreak: bool) -> Container:
  title = strings['tiebreak_title'] if tiebreak else strings['vote_title']
  body = strings['tiebreak_body'] if tiebreak else strings['vote_body']
  selector = StringSelect(custom_id=f"bunker|vote|{session.id}", options=options, placeholder=strings['vote_placeholder'], min_values=1, max_values=1)
  view = build_player_phase_view(session, strings, title, body, selector, True)
  view.accent_color = Color.orange().value
  return view

def build_player_profile_view(strings: dict, gender: str, age: int, sections: list[tuple[str, str]]) -> Container:
  components = [
    TextDisplay(f"# 🪪 {strings['profile_title']}"),
    TextDisplay(f"{TRAIT_EMOJIS['gender']} **{strings['profile_gender']}:** {gender} • {TRAIT_EMOJIS['age']} **{strings['profile_age']}:** {age}"),
    Separator(divider=True, spacing=SeparatorSpacingSize.large)
  ]
  for index, (title, value) in enumerate(sections):
    components.append(TextDisplay(f"### {title}\n{value}"))
    if index < len(sections) - 1:
      components.append(Separator(divider=True, spacing=SeparatorSpacingSize.small))
  return Container(components, Color.blurple().value, spoiler=True)

def select_caption(title: str, options: list, value: str) -> str:
  for option_value, label, description in options:
    if option_value == value:
      text = f"**{title}:** {label}"
      if description:
        text += f"\n-# {description}"
      return text
  return f"**{title}**"

def build_settings_view(session: BunkerSession, strings: dict, settings_titles: dict, anonymity_options: list, catastrophe_options: list, ai_story_options: list) -> Container:
  rows = []
  for group in SETTINGS_BUTTON_GROUPS:
    buttons = []
    for key in group:
      title = settings_titles.get(key, key)
      entry = get_setting_entry(key)
      kind = entry[2] if entry else "count"
      current_value = session.settings.get(key, "")
      display_value = format_setting_display(kind, current_value)
      buttons.append(Button(style=ButtonStyle.secondary, label=f"{title}: {display_value}", custom_id=f"bunker|setedit|{key}|{session.id}"))
    rows.append(ActionRow(buttons))

  selects = (
    (ANONYMITY_KEY, "anonymity", ANONYMITY_DEFAULT, anonymity_options),
    (CATASTROPHE_KEY, "catastrophe", CATASTROPHE_DEFAULT, catastrophe_options),
    (AI_STORY_KEY, "aistory", AI_STORY_DEFAULT, ai_story_options)
  )
  for setting_key, action, default_value, options in selects:
    current_value = session.settings.get(setting_key, default_value)
    title = settings_titles.get(setting_key, setting_key)
    rows.append(Separator(divider=True, spacing=SeparatorSpacingSize.small))
    rows.append(TextDisplay(select_caption(title, options, current_value)))
    rows.append(ActionRow([
      StringSelect(
        custom_id=f"bunker|{action}|{session.id}",
        options=[SelectOption(label=label, value=value, description=description, default=value == current_value) for value, label, description in options],
        placeholder=title, min_values=1, max_values=1
      )
    ]))

  return Container(
    [TextDisplay(f"# ⚙️ {strings['settings_title']}"), Separator(divider=True, spacing=SeparatorSpacingSize.large), *rows],
    Color.blurple().value, spoiler=False
  )

def build_started_view(session: BunkerSession, strings: dict, difficulty_label: str, settings_lines: list, participants_text: str, status_text: str) -> Container:
  settings_text = "\n".join(settings_lines)
  info_text = "\n".join([f"⚔️ **{strings['difficulty_label']}:** {difficulty_label}", f"📍 **{strings['game_channel_label']}:** <#{session.game_channel_id}>"])
  return Container([
    TextDisplay(f"# 🏚️ {strings['title']}"),
    TextDisplay(status_text),
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    TextDisplay(info_text),
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    TextDisplay(f"### 📋 {strings['participants_label']}\n{participants_text}"),
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    TextDisplay(f"### ⚙️ {strings['settings_title']}\n{settings_text}"),
    Separator(divider=True, spacing=SeparatorSpacingSize.large),
    ActionRow([Button(style=ButtonStyle.secondary, label=strings['rules_button'], custom_id=f"bunker|rules|{session.id}")])
  ], Color.blurple().value, spoiler=False)

def build_cancelled_view(strings: dict) -> Container:
  return Container([TextDisplay(f"# 🏚️ {strings['cancelled_title']}")], Color.red().value, spoiler=False)

def build_permission_error_view(missing_labels: list, strings: dict, category_name: Optional[str] = None) -> Container:
  location = f" {strings['in_category']} «{category_name}»" if category_name else ""
  missing_text = "\n".join(f"• **{label}**" for label in missing_labels)
  return Container([
    TextDisplay(f"# ⚠️ {strings['permission_error_title']}"),
    TextDisplay(f"{strings['permission_error_body']}{location}:\n{missing_text}"),
    TextDisplay(f"-# {strings['permission_error_hint']}")
  ], Color.red().value, spoiler=False)

def build_character_card(extra_count: int) -> dict:
  pools = {kind: unique_values(pool) for kind, pool in CHARACTERISTIC_POOLS.items()}
  extras = {kind: [] for kind in EXTRA_TRAIT_KINDS}
  order = list(EXTRA_TRAIT_KINDS)
  random.shuffle(order)
  for index in range(max(0, min(extra_count, MAX_EXTRA_TRAITS))):
    kind = order[index % len(order)]
    available = [value for value in pools[kind] if value not in extras[kind]]
    if available:
      extras[kind].append(random.choice(available))
  return {
    "profession_keys": [random.choice(pools["profession"])],
    "gender_key": pick_gender_key(),
    "age": roll_age(),
    "health_condition_keys": [random.choice(pools["health"])],
    "hobby_keys": extras["hobby"],
    "phobia_keys": extras["phobia"],
    "skill_keys": extras["skill"],
    "baggage_keys": extras["baggage"]
  }

def roll_supply_years(profile: dict, years: int) -> int:
  return max(0, min(100, round(years * random.uniform(*profile["supply_ratio"]))))

def assign_catastrophe_and_cards(session: BunkerSession) -> None:
  profile = DIFFICULTY_PROFILES.get(session.difficulty, DIFFICULTY_PROFILES[DEFAULT_DIFFICULTY])
  session.catastrophe = resolve_catastrophe(session.settings.get(CATASTROPHE_KEY, CATASTROPHE_DEFAULT))
  years = random.randint(*profile["apocalypse_years"])
  session.apocalypse_duration_years = years
  extra_count = to_int(session.settings.get("extra_traits_count", 3))
  session.player_cards = {participant_id: build_character_card(extra_count) for participant_id in session.all_participant_ids()}
  session.bot_names = generate_bot_names(session.bots)
  session.alive_participant_ids = session.all_participant_ids()
  session.revealed_traits = {participant_id: [] for participant_id in session.all_participant_ids()}
  session.round_reveals = {}
  session.bunker_description_key = pick_bunker_description_key()
  session.food_supply_years = roll_supply_years(profile, years)
  session.water_supply_years = roll_supply_years(profile, years)
  session.equipment_keys = pick_equipment_keys(random.randint(*profile["equipment"]))
  session.problem_keys = pick_problem_keys(random.randint(*profile["problems"]))

PHASE_DURATION_SETTINGS = {
  PHASE_INITIAL_DISCUSSION: "discussion_duration",
  PHASE_REVEAL: "trait_selection_duration",
  PHASE_DISCUSSION: "discussion_duration",
  PHASE_VOTING: "voting_duration",
  PHASE_TIEBREAK: "voting_duration",
  PHASE_PAUSE: "round_pause_duration"
}

def phase_duration(session: BunkerSession, phase: str) -> int:
  return to_int(session.settings.get(PHASE_DURATION_SETTINGS[phase], 0))

def quote_text(text: str) -> str:
  return "\n".join(f"> {line}" if line else ">" for line in text.split("\n"))

def phase_timing_lines(session: BunkerSession, strings: dict) -> list:
  lines = []
  if session.round_phase in PHASE_DURATION_SETTINGS:
    lines.append(f"⏱️ **{strings['duration_label']}:** {format_duration_pretty(phase_duration(session, session.round_phase))}")
  if session.phase_ends_at:
    lines.append(f"⏳ **{strings['time_remaining_label']}:** <t:{session.phase_ends_at}:R>")
  return lines

def bot_count_options(session: BunkerSession) -> list:
  limit = min(MAX_BOT_OPTIONS, max(session.max_players() - len(session.player_ids), 0))
  return [SelectOption(label=str(count), value=str(count), default=count == session.bots) for count in range(limit + 1)]

def choose_random_vote_target(session: BunkerSession, exclude_participant_id: Optional[str] = None) -> Optional[str]:
  alive = [str(pid) for pid in session.alive_participant_ids if str(pid) != str(exclude_participant_id)]
  if not alive:
    alive = [str(pid) for pid in session.all_participant_ids() if str(pid) != str(exclude_participant_id)]
  if not alive:
    return None
  return random.choice(alive)

def get_reveal_choice_parts(choice: str) -> tuple[Optional[str], Optional[int]]:
  try:
    trait, index = str(choice).rsplit(":", 1)
    return trait, int(index)
  except (ValueError, TypeError):
    return None, None

def remaining_trait_types(session: BunkerSession, participant_id: str) -> list[str]:
  participant_key = str(participant_id)
  card = session.player_cards.get(participant_key)
  if card is None:
    return []
  revealed = set(session.revealed_traits.get(participant_key, []))
  choices = []
  for trait_name, card_key in TRAIT_CARD_KEYS.items():
    values = card.get(card_key, card.get(trait_name, []))
    if not isinstance(values, list):
      values = [values] if values else []
    for index, _ in enumerate(values):
      choice = f"{trait_name}:{index}"
      if choice not in revealed:
        choices.append(choice)
  return choices

def all_trait_choices(session: BunkerSession, participant_id: str) -> list:
  return list(session.revealed_traits.get(str(participant_id), [])) + remaining_trait_types(session, participant_id)

def choose_random_trait_to_reveal(session: BunkerSession, participant_id: str) -> Optional[str]:
  choices = remaining_trait_types(session, participant_id)
  return random.choice(choices) if choices else None

def build_setting_modal(title: str, custom_id: str, placeholder: str, current_value_display: str):
  modal = Modal(title, custom_id=custom_id)
  text_input = TextInput(label=title, style=TextInputStyle.short, placeholder=placeholder, required=True, default_value=str(current_value_display))
  modal.add_item(text_input)
  return modal, text_input

def clip_text(text: str, limit: int) -> str:
  text = str(text or "").strip()
  if len(text) <= limit:
    return text
  head = text[:limit]
  boundary = max(head.rfind(". "), head.rfind("! "), head.rfind("? "), head.rfind("…"), head.rfind("\n"))
  if boundary >= limit // 2:
    return head[:boundary + 1].strip()
  space = head.rfind(" ")
  cut_text = head[:space] if space > 0 else head[:limit - 1]
  return cut_text.rstrip(" ,;:-") + "…"

def sanitize_channel_title(title: str, max_words: int = 2, max_length: int = 40) -> str:
  words = [word for word in re.split(r"\s+", str(title or "").strip()) if word][:max_words]
  joined = "-".join(words).lower()
  cleaned = re.sub(r"[^\w\-]", "", joined)
  cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-_")
  return cleaned[:max_length].strip("-_")

def normalize_participant_id(value) -> Optional[str]:
  match = re.search(r"bot_\d+|\d{5,}", str(value))
  return match.group(0) if match else None

def sanitize_ai_text(text: str, allowed_user_ids: set) -> str:
  cleaned = str(text or "").replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")
  cleaned = re.sub(r"<@&\d+>", "", cleaned)

  def keep_known(match):
    return match.group(0) if match.group(1) in allowed_user_ids else ""

  return re.sub(r"<@!?(\d+)>", keep_known, cleaned)

def parse_story_response(text: str) -> Optional[dict]:
  cleaned = str(text or "").strip()
  if cleaned.startswith("```"):
    cleaned = cleaned.strip("`").strip()
    if cleaned.lower().startswith("json"):
      cleaned = cleaned[4:].strip()
  try:
    data = loads(cleaned)
  except ValueError:
    return None
  if not isinstance(data, dict):
    return None
  result = {}
  for key in ("title", "teaser", "summary", "story"):
    value = data.get(key)
    result[key] = value.strip() if isinstance(value, str) else ""
  if not result["summary"]:
    return None
  survivors = data.get("survivors")
  if isinstance(survivors, list):
    ids = []
    for item in survivors:
      participant_id = normalize_participant_id(item)
      if participant_id and participant_id not in ids:
        ids.append(participant_id)
    result["survivors"] = ids
  else:
    result["survivors"] = None
  return result

def strip_empty(value):
  if isinstance(value, dict):
    result = {}
    for key, item in value.items():
      cleaned = strip_empty(item)
      if cleaned is None or cleaned == "" or cleaned == [] or cleaned == {}:
        continue
      result[key] = cleaned
    return result
  if isinstance(value, list):
    cleaned_items = [strip_empty(item) for item in value]
    return [item for item in cleaned_items if item is not None and item != "" and item != [] and item != {}]
  return value

def progress_bar(step: int) -> str:
  span = PROGRESS_BAR_CELLS - PROGRESS_BAR_WIDTH
  offset = step % (span * 2)
  position = offset if offset <= span else span * 2 - offset
  return "⬛" * position + "🟦" * PROGRESS_BAR_WIDTH + "⬛" * (span - position)

def progress_body(step: int, elapsed: int, text: str, stage: str) -> str:
  clock_face = PROGRESS_CLOCKS[step % len(PROGRESS_CLOCKS)]
  return f"{clock_face} **{text}**\n{progress_bar(step)}\n{stage}\n-# ⏱️ {elapsed // 60}:{elapsed % 60:02d}"

def stringify_big_ints(value):
  if isinstance(value, dict):
    return {key: stringify_big_ints(item) for key, item in value.items()}
  if isinstance(value, list):
    return [stringify_big_ints(item) for item in value]
  if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 9007199254740991:
    return str(value)
  return value

def client_payload(record: dict) -> dict:
  payload = {key: value for key, value in record.items() if key not in CLIENT_DROPPED_KEYS}
  ai = record.get("ai") or {}
  payload["ai"] = {key: ai[key] for key in CLIENT_AI_KEYS if key in ai}
  payload["discord"] = {key: value for key, value in (record.get("discord") or {}).items() if key in CLIENT_DISCORD_KEYS}
  rounds = {}
  for number, data in (record.get("rounds") or {}).items():
    phases = {}
    for phase, info in (data.get("phases") or {}).items():
      phases[phase] = {key: value for key, value in info.items() if key not in CLIENT_DROPPED_PHASE_KEYS}
    rounds[number] = {**{key: value for key, value in data.items() if key != "phases"}, "phases": phases}
  payload["rounds"] = rounds
  return strip_empty(payload)

def match_record_key(session_id: str) -> str:
  return f"{MATCH_RECORD_PREFIX}{session_id}"

def build_match_record(session: BunkerSession, names: dict, channel_name: Optional[str], lang: str) -> dict:
  players = {}
  for participant_id in session.all_participant_ids():
    entry = {"name": names.get(participant_id, participant_id), "card": session.player_cards.get(participant_id, {})}
    if participant_id.startswith("bot_"):
      entry["bot"] = 1
    players[participant_id] = entry
  scenario = session.catastrophe or {}
  record = {
    "v": 1,
    "id": session.id,
    "guild_id": session.guild_id,
    "creator_id": session.creator_id,
    "lang": lang,
    "difficulty": session.difficulty,
    "settings": session.settings,
    "started_at": session.game_started_at,
    "finished_at": session.finished_at,
    "end_reason": session.end_reason,
    "catastrophe": {
      "slug": scenario.get("slug"),
      "type_key": scenario.get("type_key"),
      "history_key": scenario.get("history_key"),
      "description_key": scenario.get("description_key"),
      "years": session.apocalypse_duration_years
    },
    "bunker": {
      "description_key": session.bunker_description_key,
      "capacity": session.bunker_capacity(),
      "rounds": session.rounds_count(),
      "food_years": session.food_supply_years,
      "water_years": session.water_supply_years,
      "equipment_keys": session.equipment_keys,
      "problem_keys": session.problem_keys
    },
    "players": players,
    "rounds": session.rounds,
    "finalists": [str(item) for item in session.alive_participant_ids],
    "winners": sorted(determine_winners(session)),
    "ai": session.ai_result,
    "discord": {
      "channel_id": session.game_channel_id,
      "channel_name": channel_name,
      "category_id": session.category_id,
      "lobby_channel_id": session.channel_id,
      "lobby_message_id": session.message_id,
      "overview_message_id": session.overview_message_id,
      "phase_message_id": session.phase_message_id,
      "board_message_ids": session.board_message_ids
    }
  }
  return stringify_big_ints(strip_empty(record))

def encode_payload(record: dict) -> str:
  raw = dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
  return "\\x" + zlib.compress(raw, level=9).hex()

def format_iso(timestamp) -> Optional[str]:
  if not timestamp:
    return None
  return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()

def determine_winners(session: BunkerSession) -> set:
  humans = {str(player_id) for player_id in session.player_ids}
  if session.end_reason == "timeout":
    return set()
  survivors = (session.ai_result or {}).get("survivors")
  if survivors is not None:
    return humans & {str(item) for item in survivors}
  return humans & {str(item) for item in session.alive_participant_ids}