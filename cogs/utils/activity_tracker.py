from asyncio import Lock
from hashlib import sha256
from json import dumps
from logging import getLogger
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from nextcord import Member, User, BaseActivity, Spotify, CustomActivity
from nextcord.ext import commands
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot

log = getLogger(__name__)

class ActivityTracker(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot

    self._user_locks: dict[int, Lock] = {}
    self._open_sessions: dict[int, dict[str, dict[str, Any]]] = {}

    self._activity_def_cache: dict[str, int] = {}
    self._snapshot_cache: dict[str, int] = {}

    self._primary_guild_by_user: dict[int, int] = {}

    self._max_activity_def_cache = 50000
    self._max_snapshot_cache = 50000
    self._min_session_duration_ms = 60_000

  async def flush_all_open_sessions(self):
    if not hasattr(self.bot, "db_pool") or not self.bot.db_pool:
      self._open_sessions.clear()
      return

    now = self._utc_now()

    for user_id in list(self._open_sessions.keys()):
      lock = self._get_user_lock(user_id)

      async with lock:
        sessions = self._open_sessions.get(user_id)
        if not sessions:
          self._open_sessions.pop(user_id, None)
          continue

        rows = []
        for session in sessions.values():
          if not self._keep_session_row(session["started_at"], now):
            continue

          rows.append((
            user_id,
            session["def_id"],
            session["snapshot_id"],
            session["started_at"],
            now,
          ))

        if rows:
          async with self.bot.db_pool.acquire() as connection:
            async with connection.transaction():
              await connection.executemany(
                """
                INSERT INTO activity_segments (
                  user_id,
                  def_id,
                  snapshot_id,
                  started_at,
                  ended_at
                )
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id, def_id, started_at) DO UPDATE
                SET ended_at = EXCLUDED.ended_at
                """,
                rows,
              )

        self._open_sessions.pop(user_id, None)
        self._primary_guild_by_user.pop(user_id, None)

  async def handle_presence_update(self, member: Member):
    await self._sync_member_state(member)

  async def handle_member_update(self, before: Member, after: Member):
    if not self._member_header_changed(before, after):
      return

    await self._sync_member_state(after)

  async def handle_user_update(self, before: User, after: User):
    if not self._user_header_changed(before, after):
      return

    primary_guild_id = self._get_primary_guild_id(after.id)
    if primary_guild_id is None:
      return

    guild = self.bot.get_guild(primary_guild_id)
    if guild is None:
      return

    member = guild.get_member(after.id)
    if member is None:
      return

    await self._sync_member_state(member, after)

  @staticmethod
  def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

  @staticmethod
  def _str_or_none(value: Any) -> Optional[str]:
    if value is None:
      return None
    value = str(value)
    return value if value else None

  @staticmethod
  def _json_dumps(data: Dict[str, Any]) -> str:
    return dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

  @staticmethod
  def _sha256_hex(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()

  @staticmethod
  def _asset_url(value: Any) -> Optional[str]:
    if value is None:
      return None

    try:
      if hasattr(value, "url"):
        return str(value.url)
      return str(value)
    except Exception:
      return None

  @staticmethod
  def _dt_to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
      return None
    if value.tzinfo is None:
      value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()

  @staticmethod
  def _parse_activity_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
      return None

    if isinstance(value, datetime):
      if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
      return value

    try:
      return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except Exception:
      return None

  @staticmethod
  def _drop_empty(value: Any) -> Any:
    if isinstance(value, dict):
      result = {}
      for k, v in value.items():
        cleaned = ActivityTracker._drop_empty(v)
        if cleaned is None or cleaned == "" or cleaned == [] or cleaned == {}:
          continue
        result[k] = cleaned
      return result

    if isinstance(value, list):
      result = []
      for item in value:
        cleaned = ActivityTracker._drop_empty(item)
        if cleaned is None or cleaned == "" or cleaned == [] or cleaned == {}:
          continue
        result.append(cleaned)
      return result

    return value

  @staticmethod
  def _status_to_string(status: Any) -> str:
    if status is None:
      return "offline"
    raw = str(status).lower()
    if raw == "do_not_disturb":
      return "dnd"
    return raw

  @classmethod
  def _status_to_code(cls, status: Any) -> int:
    mapping = {
      "online": 0,
      "idle": 1,
      "dnd": 2,
      "offline": 3,
      "invisible": 4,
    }
    return mapping.get(cls._status_to_string(status), 3)

  @staticmethod
  def _normalize_buttons(raw_buttons: Any) -> list[str]:
    if not raw_buttons:
      return []

    result: list[str] = []

    for item in raw_buttons:
      if isinstance(item, str):
        if item:
          result.append(item)
      elif isinstance(item, dict):
        label = item.get("label")
        if label:
          result.append(str(label))

    return result[:5]

  @staticmethod
  def _activity_type_code(activity: BaseActivity) -> int:
    raw_type = getattr(activity, "type", None)

    if raw_type is not None and hasattr(raw_type, "value"):
      try:
        return int(raw_type.value)
      except Exception:
        pass

    if raw_type is not None:
      try:
        return int(raw_type)
      except Exception:
        pass

    if hasattr(activity, "to_dict"):
      try:
        raw = activity.to_dict()
        return int(raw.get("type", -1))
      except Exception:
        pass

    return -1

  @staticmethod
  def _source_kind(activity: BaseActivity) -> int:
    return 1 if isinstance(activity, Spotify) else 0

  def _get_user_lock(self, user_id: int) -> Lock:
    if user_id not in self._user_locks:
      self._user_locks[user_id] = Lock()
    return self._user_locks[user_id]

  def _trim_cache(self):
    if len(self._activity_def_cache) > self._max_activity_def_cache:
      self._activity_def_cache.clear()

    if len(self._snapshot_cache) > self._max_snapshot_cache:
      self._snapshot_cache.clear()

  def _keep_session_row(self, started_at: datetime, ended_at: datetime) -> bool:
    try:
      duration_ms = int((ended_at - started_at).total_seconds() * 1000)
    except Exception:
      return False
    return duration_ms >= self._min_session_duration_ms

  def _get_primary_guild_id(self, user_id: int) -> Optional[int]:
    return self._primary_guild_by_user.get(user_id)

  def _set_primary_guild_id(self, user_id: int, guild_id: int):
    if user_id not in self._primary_guild_by_user:
      self._primary_guild_by_user[user_id] = guild_id

  def _extract_custom_status(self, member: Member) -> Dict[str, Any]:
    for activity in member.activities or []:
      is_custom = isinstance(activity, CustomActivity) or self._activity_type_code(activity) == 4
      if not is_custom:
        continue

      raw = activity.to_dict() if hasattr(activity, "to_dict") else {}
      emoji_obj = getattr(activity, "emoji", None)
      emoji_raw = raw.get("emoji") or {}

      emoji_name = None
      emoji_id = None
      emoji_animated = None

      if emoji_obj is not None:
        emoji_name = getattr(emoji_obj, "name", None)
        emoji_id = int(emoji_obj.id) if getattr(emoji_obj, "id", None) else None
        emoji_animated = bool(getattr(emoji_obj, "animated", False))
      else:
        emoji_name = emoji_raw.get("name")
        emoji_id = int(emoji_raw["id"]) if emoji_raw.get("id") else None
        emoji_animated = emoji_raw.get("animated")

      text = getattr(activity, "state", None) or raw.get("state") or getattr(activity, "name", None)

      return self._drop_empty({
        "text": self._str_or_none(text),
        "emoji_name": self._str_or_none(emoji_name),
        "emoji_id": emoji_id,
        "emoji_animated": emoji_animated,
      })

    return {}

  def _build_presence_snapshot(
    self,
    member: Member,
    user_override: Optional[User] = None,
    include_profile: bool = True,
  ) -> Dict[str, Any]:
    user_obj = user_override or member

    username = self._str_or_none(getattr(user_obj, "name", None))
    global_name = self._str_or_none(getattr(user_obj, "global_name", None))
    display_name = global_name or username

    payload = {
      "status": self._status_to_string(member.status),
      "desktop_status": self._status_to_string(member.desktop_status),
      "mobile_status": self._status_to_string(member.mobile_status),
      "web_status": self._status_to_string(member.web_status),
      "custom_status": self._extract_custom_status(member),
    }

    if include_profile:
      payload.update({
        "avatar_url": self._asset_url(getattr(user_obj, "display_avatar", None)),
        "banner_url": self._asset_url(getattr(user_obj, "banner", None) or getattr(member, "banner", None)),
        "username": username,
        "global_name": global_name,
        "display_name": display_name,
      })

    payload = self._drop_empty(payload)

    fingerprint_payload = {
      "user_id": member.id,
      **payload,
    }

    return {
      "fingerprint": self._sha256_hex(self._json_dumps(fingerprint_payload)),
      "status_code": self._status_to_code(member.status),
      "desktop_status_code": self._status_to_code(member.desktop_status),
      "mobile_status_code": self._status_to_code(member.mobile_status),
      "web_status_code": self._status_to_code(member.web_status),
      "payload": payload,
    }

  def _build_activity_definition(self, activity: BaseActivity) -> Dict[str, Any]:
    raw = activity.to_dict() if hasattr(activity, "to_dict") else {}
    assets = raw.get("assets") or {}
    party = raw.get("party") or {}
    timestamps = raw.get("timestamps") or {}
    emoji_raw = raw.get("emoji") or {}

    activity_type = self._activity_type_code(activity)
    source_kind = self._source_kind(activity)

    name = (
      self._str_or_none(getattr(activity, "name", None))
      or self._str_or_none(raw.get("name"))
      or type(activity).__name__
    )

    details = self._str_or_none(getattr(activity, "details", None)) or self._str_or_none(raw.get("details"))
    state = self._str_or_none(getattr(activity, "state", None)) or self._str_or_none(raw.get("state"))
    url = self._str_or_none(getattr(activity, "url", None)) or self._str_or_none(raw.get("url"))

    application_id = getattr(activity, "application_id", None)
    if application_id is None:
      application_id = raw.get("application_id")
    application_id = int(application_id) if application_id else None

    large_image_url = self._asset_url(getattr(activity, "large_image_url", None))
    small_image_url = self._asset_url(getattr(activity, "small_image_url", None))

    emoji_obj = getattr(activity, "emoji", None)
    if emoji_obj is not None:
      emoji_name = self._str_or_none(getattr(emoji_obj, "name", None))
      emoji_id = int(emoji_obj.id) if getattr(emoji_obj, "id", None) else None
      emoji_animated = bool(getattr(emoji_obj, "animated", False))
    else:
      emoji_name = self._str_or_none(emoji_raw.get("name"))
      emoji_id = int(emoji_raw["id"]) if emoji_raw.get("id") else None
      emoji_animated = emoji_raw.get("animated")

    party_size = party.get("size") or []
    party_current = int(party_size[0]) if len(party_size) > 0 and party_size[0] is not None else None
    party_max = int(party_size[1]) if len(party_size) > 1 and party_size[1] is not None else None

    button_labels = self._normalize_buttons(raw.get("buttons"))

    spotify_track_id = None
    spotify_track_url = None
    spotify_title = None
    spotify_artists = None
    spotify_album = None
    spotify_album_cover_url = None
    spotify_duration_seconds = None

    if isinstance(activity, Spotify):
      spotify_track_id = self._str_or_none(getattr(activity, "track_id", None))
      spotify_track_url = self._str_or_none(getattr(activity, "track_url", None))
      spotify_title = self._str_or_none(getattr(activity, "title", None))
      spotify_artists = [str(x) for x in (getattr(activity, "artists", None) or [])]
      spotify_album = self._str_or_none(getattr(activity, "album", None))
      spotify_album_cover_url = self._str_or_none(getattr(activity, "album_cover_url", None))
      duration = getattr(activity, "duration", None)
      spotify_duration_seconds = int(duration.total_seconds()) if duration else None

    payload = self._drop_empty({
      "class_name": type(activity).__name__,
      "source_kind": source_kind,
      "activity_type": activity_type,
      "name": name,
      "details": details,
      "state": state,
      "url": url,
      "application_id": application_id,
      "large_image_url": large_image_url,
      "small_image_url": small_image_url,
      "emoji_name": emoji_name,
      "emoji_id": emoji_id,
      "emoji_animated": emoji_animated,
      "party_current": party_current,
      "party_max": party_max,
      "button_labels": button_labels,
      "spotify_track_id": spotify_track_id,
      "spotify_track_url": spotify_track_url,
      "spotify_title": spotify_title,
      "spotify_artists": spotify_artists,
      "spotify_album": spotify_album,
      "spotify_album_cover_url": spotify_album_cover_url,
      "spotify_duration_seconds": spotify_duration_seconds,
    })

    fingerprint = self._sha256_hex(self._json_dumps(payload))

    return {
      "fingerprint": fingerprint,
      "payload": payload,
      "source_kind": source_kind,
      "activity_type": activity_type,
      "name": name,
    }

  def _build_activity_entries(self, member: Member) -> Dict[str, Dict[str, Any]]:
    items = []

    for activity in member.activities or []:
      if activity is None:
        continue

      activity_type = self._activity_type_code(activity)

      if isinstance(activity, CustomActivity) or activity_type == 4:
        continue

      items.append(self._build_activity_definition(activity))

    items.sort(
      key=lambda item: (
        item["activity_type"],
        item["source_kind"],
        item["name"] or "",
        item["payload"].get("details", ""),
        item["payload"].get("state", ""),
        item["fingerprint"],
      )
    )

    result: Dict[str, Dict[str, Any]] = {}
    duplicate_counter = defaultdict(int)

    for item in items:
      session_base = {
        "fingerprint": item["fingerprint"],
      }

      base_key = self._sha256_hex(self._json_dumps(session_base))
      duplicate_counter[base_key] += 1

      if duplicate_counter[base_key] == 1:
        session_key = base_key
      else:
        session_key = f"{base_key}:{duplicate_counter[base_key]}"

      result[session_key] = {
        "fingerprint": item["fingerprint"],
        "payload": item["payload"],
        "source_kind": item["source_kind"],
        "activity_type": item["activity_type"],
        "name": item["name"],
      }

    return result

  async def _get_or_create_activity_def(
    self,
    connection,
    fingerprint: str,
    source_kind: int,
    activity_type: int,
    name: str,
    payload: Dict[str, Any],
  ) -> int:
    cached = self._activity_def_cache.get(fingerprint)
    if cached is not None:
      return cached

    value = await connection.fetchval(
      """
      INSERT INTO activity_defs (fingerprint, source_kind, activity_type, name, payload)
      VALUES ($1, $2, $3, $4, $5::jsonb)
      ON CONFLICT (fingerprint) DO UPDATE
      SET
        source_kind = EXCLUDED.source_kind,
        activity_type = EXCLUDED.activity_type,
        name = EXCLUDED.name,
        payload = EXCLUDED.payload
      RETURNING id
      """,
      fingerprint,
      source_kind,
      activity_type,
      name,
      self._json_dumps(payload),
    )

    if value is None:
      value = await connection.fetchval(
        "SELECT id FROM activity_defs WHERE fingerprint = $1",
        fingerprint,
      )

    if value is None:
      raise RuntimeError(f"activity_defs id not found for fingerprint={fingerprint}")

    def_id = int(value)
    self._activity_def_cache[fingerprint] = def_id
    self._trim_cache()
    return def_id

  async def _get_or_create_snapshot(
    self,
    connection,
    guild_id: int,
    user_id: int,
    snapshot: Dict[str, Any],
  ) -> int:
    fingerprint = snapshot["fingerprint"]
    cached = self._snapshot_cache.get(fingerprint)
    if cached is not None:
      return cached

    value = await connection.fetchval(
      """
      INSERT INTO presence_snapshots (
        fingerprint,
        guild_id,
        user_id,
        status_code,
        desktop_status_code,
        mobile_status_code,
        web_status_code,
        payload
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
      ON CONFLICT (fingerprint) DO UPDATE
      SET
        guild_id = EXCLUDED.guild_id,
        user_id = EXCLUDED.user_id,
        status_code = EXCLUDED.status_code,
        desktop_status_code = EXCLUDED.desktop_status_code,
        mobile_status_code = EXCLUDED.mobile_status_code,
        web_status_code = EXCLUDED.web_status_code,
        payload = EXCLUDED.payload
      RETURNING id
      """,
      fingerprint,
      guild_id,
      user_id,
      snapshot["status_code"],
      snapshot["desktop_status_code"],
      snapshot["mobile_status_code"],
      snapshot["web_status_code"],
      self._json_dumps(snapshot["payload"]),
    )

    if value is None:
      value = await connection.fetchval(
        "SELECT id FROM presence_snapshots WHERE fingerprint = $1",
        fingerprint,
      )

    if value is None:
      raise RuntimeError(f"presence_snapshots id not found for fingerprint={fingerprint}")

    snapshot_id = int(value)
    self._snapshot_cache[fingerprint] = snapshot_id
    self._trim_cache()
    return snapshot_id

  def _drop_user_open_sessions_without_save(self, user_id: int):
    self._open_sessions.pop(user_id, None)

  async def _get_member_privacy(self, member: Member) -> Optional[dict]:
    guild_id = member.guild.id
    user_id = member.id

    if guild_id in servers_with_no_acces_for_bot or user_id in users_with_no_acces_for_bot:
      return None

    gd = self.bot.get_cog("GetData")
    if gd is None:
      return None

    guild_settings = await gd.get_data(
      guild_id,
      ["banned"],
      "guilds",
      "guild_id",
      member.guild,
    )

    user_settings = await gd.get_data(
      user_id,
      ["banned"],
      "users",
      "user_id",
      member.guild,
    )

    if user_settings["banned"] or guild_settings["banned"]:
      if guild_id not in servers_with_no_acces_for_bot:
        servers_with_no_acces_for_bot.append(guild_id)
      if user_id not in users_with_no_acces_for_bot:
        users_with_no_acces_for_bot.append(user_id)
      return None

    user_privacy = await gd.get_data(user_id, ["save_activity_data", "save_activity_profile"], "user_privacy", "user_id", member.guild)
    guild_privacy = await gd.get_data(guild_id, ["save_activity"], "guild_settings_privacy", "guild_id", member.guild)
    return user_privacy|guild_privacy

  async def _sync_member_state(
    self,
    member: Member,
    user_override: Optional[User] = None,
  ):
    if member is None or member.guild is None:
      return

    if not hasattr(self.bot, "db_pool") or not self.bot.db_pool:
      return

    guild_id = member.guild.id
    user_id = member.id
    lock = self._get_user_lock(user_id)

    primary_guild_id = self._get_primary_guild_id(user_id)

    if primary_guild_id is None:
      self._set_primary_guild_id(user_id, guild_id)
      primary_guild_id = guild_id

    if guild_id != primary_guild_id:
      return

    async with lock:
      try:
        privacy = await self._get_member_privacy(member)

        if privacy is None:
          self._drop_user_open_sessions_without_save(user_id)
          return

        if not privacy.get("save_activity", False):
          self._drop_user_open_sessions_without_save(user_id)
          return

        save_activity_data = bool(privacy.get("save_activity_data", False))
        save_activity_profile = bool(privacy.get("save_activity_profile", False))

        if not save_activity_data:
          self._drop_user_open_sessions_without_save(user_id)
          return

        now = self._utc_now()
        snapshot = self._build_presence_snapshot(
          member,
          user_override=user_override,
          include_profile=save_activity_profile,
        )
        current_entries = self._build_activity_entries(member)

        async with self.bot.db_pool.acquire() as connection:
          async with connection.transaction():
            snapshot_id = await self._get_or_create_snapshot(
              connection,
              guild_id,
              user_id,
              snapshot,
            )

            resolved_entries: dict[str, dict[str, Any]] = {}
            for session_key, entry in current_entries.items():
              def_id = await self._get_or_create_activity_def(
                connection,
                entry["fingerprint"],
                entry["source_kind"],
                entry["activity_type"],
                entry["name"],
                entry["payload"],
              )

              resolved_entries[session_key] = {
                "def_id": def_id,
                "snapshot_id": snapshot_id,
              }

            old_sessions = self._open_sessions.get(user_id, {})

            rows_to_insert = []
            next_open_sessions: dict[str, dict[str, Any]] = {}
            processed_keys: set[str] = set()

            for session_key, old_session in old_sessions.items():
              new_session = resolved_entries.get(session_key)

              if new_session is None:
                rows_to_insert.append((
                  user_id,
                  old_session["def_id"],
                  old_session["snapshot_id"],
                  old_session["started_at"],
                  now,
                ))
                continue

              same_def = old_session["def_id"] == new_session["def_id"]
              same_snapshot = old_session["snapshot_id"] == new_session["snapshot_id"]

              if same_def and same_snapshot:
                next_open_sessions[session_key] = old_session
                processed_keys.add(session_key)
                continue

              if self._keep_session_row(old_session["started_at"], now):
                rows_to_insert.append((
                  user_id,
                  old_session["def_id"],
                  old_session["snapshot_id"],
                  old_session["started_at"],
                  now,
                ))

              next_open_sessions[session_key] = {
                "def_id": new_session["def_id"],
                "snapshot_id": new_session["snapshot_id"],
                "started_at": now,
              }
              processed_keys.add(session_key)

            for session_key, new_session in resolved_entries.items():
              if session_key in processed_keys:
                continue

              next_open_sessions[session_key] = {
                "def_id": new_session["def_id"],
                "snapshot_id": new_session["snapshot_id"],
                "started_at": now,
              }

            if rows_to_insert:
              seen = {}
              deduped_rows = []
              for row in rows_to_insert:
                dedup_key = (row[1], row[3])
                if dedup_key not in seen:
                  seen[dedup_key] = True
                  deduped_rows.append(row)

              await connection.executemany(
                """
                INSERT INTO activity_segments (
                  user_id,
                  def_id,
                  snapshot_id,
                  started_at,
                  ended_at
                )
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id, def_id, started_at) DO UPDATE -- <-- Теперь тут 3 колонки
                SET ended_at = EXCLUDED.ended_at
                """,
                deduped_rows,
              )

            if next_open_sessions:
              self._open_sessions[user_id] = next_open_sessions
            else:
              self._open_sessions.pop(user_id, None)

      except Exception:
        log.exception(
          "Failed to sync member state: guild_id=%s user_id=%s",
          guild_id,
          user_id,
        )

  @staticmethod
  def _member_header_changed(before: Member, after: Member) -> bool:
    before_guild_avatar = getattr(before, "guild_avatar", None)
    after_guild_avatar = getattr(after, "guild_avatar", None)

    return (
      before.nick != after.nick
      or before_guild_avatar != after_guild_avatar
    )

  @staticmethod
  def _user_header_changed(before: User, after: User) -> bool:
    before_avatar = getattr(before, "avatar", None)
    after_avatar = getattr(after, "avatar", None)
    before_banner = getattr(before, "banner", None)
    after_banner = getattr(after, "banner", None)

    return (
      before.name != after.name
      or getattr(before, "global_name", None) != getattr(after, "global_name", None)
      or before_avatar != after_avatar
      or before_banner != after_banner
    )

def setup(bot: commands.Bot):
  bot.add_cog(ActivityTracker(bot))