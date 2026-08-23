VALID_FLAGS = {
  "save_message_data",
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

SECTION_FLAGS = {
  "messages": ["save_message_data"],
  "voice": [],
  "activity": ["save_activity_data", "save_activity_profile"],
  "diagnostics": ["track_activity"],
  "visibility": ["publicity"],
}

FLAG_TEXTS = {
  "save_message_data": "privacy.flag_save_message_data",
  "save_activity_data": "privacy.flag_save_activity_data",
  "save_activity_profile": "privacy.flag_save_activity_profile",
  "track_activity": "privacy.flag_track_activity",
  "publicity": "privacy.flag_publicity",
}

PRESETS = {
  "private": {
    "save_message_data": False,
    "save_activity_data": False,
    "save_activity_profile": False,
    "track_activity": False,
    "publicity": False,
  },
  "balanced": {
    "save_message_data": False,
    "save_activity_data": False,
    "save_activity_profile": False,
    "track_activity": True,
    "publicity": False,
  },
  "analytics": {
    "save_message_data": True,
    "save_activity_data": True,
    "save_activity_profile": True,
    "track_activity": True,
    "publicity": True,
  },
}