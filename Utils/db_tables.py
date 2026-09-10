resolvers = {
  "user_id": ("author.id", "user.id", "id", "user_id"),
  "guild_id": ("guild.id", "id", "guild_id")
}

tables = {
  "users": {
    "user_id": resolvers["user_id"],
    "username": ("author.name", "user.name", "name"),
    "language": ("lang", "language"),
    "discord_id": resolvers["user_id"],
    "badges": ("badges",)
  },
  "user_data": {
    "user_id": resolvers["user_id"]
  },
  "user_privacy": {
    "user_id": resolvers["user_id"]
  },
  "topgg": {
    "user_id": resolvers["user_id"]
  },
  "guild_users": {
    "user_id": resolvers["user_id"],
    "guild_id": resolvers["guild_id"]
  },
  "guilds": {
    "guild_id": resolvers["guild_id"]
  },
  "guild_settings": {
    "guild_id": resolvers["guild_id"]
  },
  "guild_settings_privacy": {
    "guild_id": resolvers["guild_id"]
  }
}

table_pk = {
  "users": ("user_id",),
  "user_data": ("user_id",),
  "user_privacy": ("user_id",),
  "topgg": ("user_id",),
  "guild_users": ("user_id", "guild_id"),
  "guilds": ("guild_id",),
  "guild_settings": ("guild_id",),
  "guild_settings_privacy": ("guild_id",)
}