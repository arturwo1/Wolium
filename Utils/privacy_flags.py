VALID_FLAGS = {
  "save_messages",
  "save_message_data",
  "save_voice",
  "save_activity",
  "save_activity_data",
  "save_activity_profile",
  "track_activity",
  "publicity",
}

SECTION_ORDER = ["overview", "messages", "voice", "activity", "diagnostics", "visibility"]

SECTION_LABELS = {
  "overview": "privacy.section_overview",
  "messages": "privacy.section_messages",
  "voice": "privacy.section_voice",
  "activity": "privacy.section_activity",
  "diagnostics": "privacy.section_diagnostics",
  "visibility": "privacy.section_visibility",
}

FLAG_DEPENDENCIES = {
  "save_message_data": "save_messages",
  "save_activity_data": "save_activity",
  "save_activity_profile": "save_activity",
}

SECTION_FLAGS = {
  "messages": ["save_messages", "save_message_data"],
  "voice": ["save_voice"],
  "activity": ["save_activity", "save_activity_data", "save_activity_profile"],
  "diagnostics": ["track_activity"],
  "visibility": ["publicity"],
}

FLAG_TEXTS = {
  "save_messages": "privacy.flag_save_messages",
  "save_message_data": "privacy.flag_save_message_data",
  "save_voice": "privacy.flag_save_voice",
  "save_activity": "privacy.flag_save_activity",
  "save_activity_data": "privacy.flag_save_activity_data",
  "save_activity_profile": "privacy.flag_save_activity_profile",
  "track_activity": "privacy.flag_track_activity",
  "publicity": "privacy.flag_publicity",
}

PRESETS = {
  "private": {
    "save_messages": False,
    "save_message_data": False,
    "save_voice": False,
    "save_activity": False,
    "save_activity_data": False,
    "save_activity_profile": False,
    "track_activity": False,
    "publicity": False,
  },
  "balanced": {
    "save_messages": True,
    "save_message_data": False,
    "save_voice": True,
    "save_activity": True,
    "save_activity_data": False,
    "save_activity_profile": False,
    "track_activity": True,
    "publicity": False,
  },
  "analytics": {
    "save_messages": True,
    "save_message_data": True,
    "save_voice": True,
    "save_activity": True,
    "save_activity_data": True,
    "save_activity_profile": True,
    "track_activity": True,
    "publicity": True,
  },
}