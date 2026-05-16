from nextcord import Guild, Message, TextChannel, Member, PartialEmoji
from nextcord.ext import commands
from json import dumps
from uuid import uuid4

from Utils.search_and_scrape import async_web_search_tool
from Utils.calculate_LvL import calculate_LvL
from Utils.gpt_views import GptActionConfirmView

async def _tool_search_and_scrape(args: dict, ctx: dict, language: str, bot: commands.Bot, **kwargs):
  result = await async_web_search_tool(args.get("query", ""))
  return str(result), None

async def _tool_perform_moderation_action(args: dict, ctx: dict, language: str, bot: commands.Bot, **kwargs):
  tm = bot.get_cog("TranslateMessage")
  action_user_id = args.get("user_id", "")
  action_type = args.get("action_type", "")
  if str(action_user_id) == str(bot.user.id):
    msg = await tm.translate_message('gpt.cannot_apply_to_self', language, variables={"action_type": action_type})
    return msg, None
  view_id = str(uuid4())[:8]
  view = GptActionConfirmView(view_id=view_id, user_id=ctx["user_id"], action=args, language=language, bot=bot)
  return "Action queued for user confirmation.", view

async def _tool_get_channels(args: dict, ctx: dict, language: str, bot: commands.Bot, **kwargs):
  guild: Guild = ctx["guild"]
  limit = args.get("limit", 20)
  channels = [
    {"id": str(c.id), "name": c.name, "type": str(c.type)}
    for c in guild.channels
    if hasattr(c, "send")
  ][:limit]
  return dumps(channels), None

async def _tool_get_history(args: dict, ctx: dict, language: str, bot: commands.Bot, **kwargs):
  guild: Guild = ctx["guild"]
  channel: TextChannel = ctx["channel"]
  cid = args.get("channel_id")
  target_channel = guild.get_channel(int(cid)) if cid else channel
  uid = args.get("user_id")
  user: Member | None = guild.get_member(int(uid)) if uid else None
  limit = args.get("limit", 20)

  messages = []
  async for msg in target_channel.history(limit=limit):
    if user and msg.author.id != user.id:
      continue
    messages.append({
      "id": str(msg.id),
      "author": msg.author.display_name,
      "author_id": str(msg.author.id),
      "content": msg.content,
      "time": str(msg.created_at),
    })
  return dumps(messages), None

async def _tool_get_users(args: dict, ctx: dict, language: str, bot: commands.Bot, **kwargs):
  guild: Guild = ctx["guild"]
  q = args.get("query", "").lower()
  limit = args.get("limit", 20)
  results = [
    {
      "id": str(m.id),
      "name": m.name,
      "display_name": m.display_name,
      "roles": [r.name for r in m.roles],
    }
    for m in guild.members
    if q in m.name.lower() or q in m.display_name.lower()
  ][:limit]
  return dumps(results), None

async def _tool_set_reaction(args: dict, ctx: dict, language: str, bot: commands.Bot, **kwargs):
  guild: Guild = ctx["guild"]
  channel: TextChannel = ctx["channel"]
  ec = bot.get_cog("EmojiCollector")

  cid = args.get("channel_id")
  target_channel = guild.get_channel(int(cid)) if cid else channel
  target_msg: Message = await target_channel.fetch_message(int(args["message_id"]))

  errors = ""
  for emoji_str in args.get("reactions", []):
    try:
      cleaned = emoji_str.strip()
      if cleaned.startswith("<:") and cleaned.endswith(">"):
        cleaned = cleaned[2:-1]  # "<:name:id>" -> "name:id"

      if ":" in cleaned:
        name, eid_str = cleaned.rsplit(":", 1)
        emoji_id = int(eid_str)
        emoji_obj = bot.get_emoji(emoji_id)
        if emoji_obj:
          await target_msg.add_reaction(emoji_obj)
        else:
          await target_msg.add_reaction(PartialEmoji(name=name, id=emoji_id))
        if ec:
          await ec.increment_emoji_usage(emoji_id)
      else:
        await target_msg.add_reaction(cleaned)
    except Exception as e:
      errors += f"Failed: {emoji_str} - {e}\n"
  return errors or "ok", None

async def _tool_get_message(args: dict, ctx: dict, language: str, bot: commands.Bot, **kwargs):
  guild: Guild = ctx["guild"]
  channel: TextChannel = ctx["channel"]
  cid = args.get("channel_id")
  target_channel = guild.get_channel(int(cid)) if cid else channel
  msg: Message = await target_channel.fetch_message(int(args["message_id"]))
  return dumps({
    "id": str(msg.id),
    "author": msg.author.display_name,
    "author_id": str(msg.author.id),
    "content": msg.content,
    "time": str(msg.created_at),
  }), None

async def _tool_get_user_profile(args: dict, ctx: dict, language: str, bot: commands.Bot, **kwargs):
  guild: Guild = ctx["guild"]
  user_id = int(args["user_id"])
  gd = bot.get_cog("GetData")
  try:
    privacy = await gd.get_data(user_id, ['publicity'], 'user_privacy', 'user_id', guild)
    if not privacy.get("publicity", True):
      return "Profile is private.", None
    user_data = await gd.get_data(user_id, ['xp', 'bank_balance', 'balance', 'upgrade'], 'user_data', 'user_id', guild)
    user = await gd.get_data(user_id, ['reg_data', 'variation'], 'users', 'user_id', guild)
    bank_balance = user_data["bank_balance"]
    balance = user_data["balance"]
    xp = user_data["xp"]
    LvL, XP_need, XP_now = calculate_LvL(xp)
    return dumps({
      "xp": xp,
      "total_balance": bank_balance + balance,
      "bank_balance": bank_balance,
      "balance": balance,
      "upgrade": user_data["upgrade"],
      "LvL": LvL,
      "XP_need": XP_need,
      "XP_now": XP_now,
      "reg_data": user["reg_data"],
      "number_format_variation": user["variation"],
    }), None
  except Exception as e:
    return f"Profile fetch error: {e}", None

async def _tool_save_user_memory(args: dict, ctx: dict, language: str, bot: commands.Bot, memory_ops=None, **kwargs):
  if memory_ops:
    return await memory_ops["save_user"](ctx["guild_id"], args["user_id"], args["text"]), None
  return "Memory ops unavailable.", None

async def _tool_remove_user_memory(args: dict, ctx: dict, language: str, bot: commands.Bot, memory_ops=None, **kwargs):
  if memory_ops:
    return await memory_ops["remove_user"](ctx["guild_id"], args["user_id"], args.get("indices", [])), None
  return "Memory ops unavailable.", None

async def _tool_save_guild_memory(args: dict, ctx: dict, language: str, bot: commands.Bot, memory_ops=None, **kwargs):
  if memory_ops:
    return await memory_ops["save_guild"](ctx["guild_id"], args["text"]), None
  return "Memory ops unavailable.", None

async def _tool_remove_guild_memory(args: dict, ctx: dict, language: str, bot: commands.Bot, memory_ops=None, **kwargs):
  if memory_ops:
    return await memory_ops["remove_guild"](ctx["guild_id"], args.get("indices", [])), None
  return "Memory ops unavailable.", None

TOOL_HANDLERS: dict = {
  "search_and_scrape":         _tool_search_and_scrape,
  "perform_moderation_action": _tool_perform_moderation_action,
  "get_channels":              _tool_get_channels,
  "get_history":               _tool_get_history,
  "get_users":                 _tool_get_users,
  "set_reaction":              _tool_set_reaction,
  "get_message":               _tool_get_message,
  "get_user_profile":          _tool_get_user_profile,
  "save_user_memory":          _tool_save_user_memory,
  "remove_user_memory":        _tool_remove_user_memory,
  "save_guild_memory":         _tool_save_guild_memory,
  "remove_guild_memory":       _tool_remove_guild_memory,
}

async def dispatch_tool(fn: str, args: dict, ctx: dict, language: str, bot: commands.Bot, memory_ops: dict | None = None) -> tuple[str, object]:
  handler = TOOL_HANDLERS.get(fn)
  if not handler:
    return f"Unknown tool: {fn}", None
  try:
    return await handler(args, ctx, language, bot, memory_ops=memory_ops)
  except Exception as e:
    return f"Tool error ({fn}): {e}", None