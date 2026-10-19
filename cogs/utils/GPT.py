from nextcord import Message, Color, Invite
from nextcord.ext import commands
from time import time
from traceback import format_exception
from asyncio import sleep, create_task, wait, get_running_loop
from re import DOTALL, compile
from json import loads, JSONDecodeError, dumps
from Utils.config import tools, temperature, max_tokens, top_p, automod_history, rules_data, o_models, o_url, message_for_wolium
from Utils.ai_client import AIClient, HuggingFaceConfig, OllamaConfig, GroqConfig
from Utils.config import hf_api_keys, hf_models, q_api_keys
from Utils.gpt_views import ViolationsView, GptActionConfirmView, load_views
from Utils.gpt_tools import dispatch_tool
import Utils.translate_to_all_languages
from uuid import uuid4
from io import BytesIO
from base64 import b64encode
from PIL import Image

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _make_ai_client() -> AIClient:
  configs = []

  if hf_api_keys and hf_models:
    configs.append(HuggingFaceConfig(
      api_keys=list(hf_api_keys),
      models=list(hf_models),
      priority=1,
    ))

  configs.append(OllamaConfig(
    base_url=o_url,
    models=o_models,
    priority=999,
  ))

  if q_api_keys:
    configs.append(GroqConfig(
      api_keys=list(q_api_keys),
      priority=0,
    ))

  return AIClient(configs)

def _turn_length(items: list, start: int) -> int:
  msg = items[start]
  if msg.get("role") == "assistant" and msg.get("tool_calls"):
    call_ids = {tc["id"] for tc in msg["tool_calls"]}
    length = 1
    i = start + 1
    while i < len(items) and items[i].get("role") == "tool" and items[i].get("tool_call_id") in call_ids:
      length += 1
      i += 1
    return length
  return 1

def _estimate_tokens(msg: dict) -> int:
  parts = []
  content = msg.get("content", "")
  if isinstance(content, list):
    parts.append(" ".join(b.get("text", "") for b in content if isinstance(b, dict)))
  else:
    parts.append(str(content or ""))
  if msg.get("tool_calls"):
    parts.append(dumps(msg["tool_calls"], ensure_ascii=False))
  if msg.get("tool_call_id"):
    parts.append(str(msg["tool_call_id"]))

  return len(" ".join(parts)) // 2 + 10

def _trim_history_sync(items: list, max_size: int = 22, max_tokens_budget: int = 3200):
  while True:
    turn_count = 0
    idx = 1
    turn_starts = []
    while idx < len(items):
      turn_starts.append(idx)
      idx += _turn_length(items, idx)
      turn_count += 1

    total_tokens = sum(_estimate_tokens(m) for m in items)
    if turn_count <= max_size and total_tokens <= max_tokens_budget:
      break

    if not turn_starts:
      break

    latest_user_start = max(
      (start for start in turn_starts if items[start].get("role") == "user"),
      default=None,
    )
    removable = [start for start in turn_starts if latest_user_start is None or start < latest_user_start]
    if not removable:
      break

    oldest_start = removable[0]
    oldest_len = _turn_length(items, oldest_start)
    del items[oldest_start: oldest_start + oldest_len]

async def _trim_history(items: list, max_size: int = 22):
  await sleep(0)
  _trim_history_sync(items, max_size)
  return items

_RETRYABLE = (
  'Connection aborted', 'Payment Required', 'Bad Gateway',
  'Gateway Timeout', 'overloaded', 'Model too busy', 'Internal Server Error',
)

def _history_has_image(history: list) -> bool:
  for m in history:
    content = m.get("content")
    if isinstance(content, list):
      for block in content:
        if isinstance(block, dict) and block.get("type") == "image_url":
          return True
  return False

_MAX_TOOL_ITERATIONS = 6

_XML_TOOL_RE = compile(r'<:?\w[\w_]*\s[^>]*/>', DOTALL)
_TOOL_CODE_BLOCK_RE = compile(r'<tool_code>.*?</tool_code>', DOTALL)
_TEXT_RESPONSE_WRAPPER_RE = compile(r'<text_response>(.*?)</text_response>', DOTALL)

_FILLER_PREFIXES = (
  "Certainly! ", "Certainly, ", "Of course! ", "Of course, ",
  "Sure! ", "Sure, ", "Absolutely! ", "Absolutely, ",
  "Great! ", "Great, ", "I'd be happy to ", "I'd be happy to help ",
  "I'll help you ", "Let me help you ", "Allow me to ",
)

TOOL_STATUS_KEYS = {
  "search_and_scrape": "gpt.tool_status.search_and_scrape",
  "perform_moderation_action": "gpt.tool_status.perform_moderation_action",
  "get_channels": "gpt.tool_status.get_channels",
  "get_history": "gpt.tool_status.get_history",
  "get_users": "gpt.tool_status.get_users",
  "set_reaction": "gpt.tool_status.set_reaction",
  "get_message": "gpt.tool_status.get_message",
  "get_user_profile": "gpt.tool_status.get_user_profile",
  "save_user_memory": "gpt.tool_status.save_user_memory",
  "remove_user_memory": "gpt.tool_status.remove_user_memory",
  "save_guild_memory": "gpt.tool_status.save_guild_memory",
  "remove_guild_memory": "gpt.tool_status.remove_guild_memory",
}

_STATUS_LABEL_MAX_LEN = 100

def _sanitize_response(text: str) -> str:
  text = _XML_TOOL_RE.sub('', text)
  text = _TOOL_CODE_BLOCK_RE.sub('', text)
  wrapper_match = _TEXT_RESPONSE_WRAPPER_RE.search(text)
  if wrapper_match:
    text = wrapper_match.group(1)
  text = text.strip()
  for prefix in _FILLER_PREFIXES:
    if text.startswith(prefix):
      text = text[len(prefix):].lstrip()
      break
  return text

_TOOL_RESULT_MAX_LEN = 1500

def _make_tool_result(tool_name: str, result: str, is_error: bool = False) -> str:
  if is_error:
    short = result[:200] if len(result) > 200 else result
    return dumps({"tool": tool_name, "status": "error", "message": short}, ensure_ascii=False)
  short = result[:_TOOL_RESULT_MAX_LEN] if len(result) > _TOOL_RESULT_MAX_LEN else result
  truncated = len(result) > _TOOL_RESULT_MAX_LEN
  payload = {"tool": tool_name, "status": "ok", "result": short}
  if truncated:
    payload["truncated"] = True
  return dumps(payload, ensure_ascii=False)

async def _complete_with_retry(ai, *, messages, tools, temperature, max_tokens, top_p, max_retries: int = 5, base_delay: float = 1.0, backoff: float = 1.5):
  attempt = 0
  delay = base_delay
  while True:
    try:
      return await ai.complete(
        messages=messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
      )
    except Exception as e:
      err_str = str(e)
      is_retryable = any(marker in err_str for marker in _RETRYABLE)
      attempt += 1
      if not is_retryable or attempt > max_retries:
        raise
      await sleep(delay)
      delay *= backoff

_IMAGE_MAX_DIMENSION = 1024
_IMAGE_JPEG_QUALITY = 70

def _downscale_image_sync(data: bytes) -> bytes:
  try:
    img = Image.open(BytesIO(data))
    img = img.convert("RGB")
    img.thumbnail((_IMAGE_MAX_DIMENSION, _IMAGE_MAX_DIMENSION), Image.LANCZOS)
    out = BytesIO()
    img.save(out, format="JPEG", quality=_IMAGE_JPEG_QUALITY, optimize=True)
    return out.getvalue()
  except Exception:
    return data

async def _downscale_image(data: bytes) -> bytes:
  loop = get_running_loop()
  return await loop.run_in_executor(None, _downscale_image_sync, data)

class GPT(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.history: dict[int, dict] = {}
    self._automod_perm_warned: dict[int, float] = {}
    self._automod_warn_cooldown = 3600

  @commands.Cog.listener()
  async def on_ready(self):
    data = load_views()
    for view_id, d in data.get("violations", {}).items():
      view = ViolationsView(
        view_id=view_id, member_id=d["member_id"], user_id=d.get("user_id"), guild_id=d["guild_id"],
        channel_id=d["channel_id"], message_id=d["message_id"], language=d["language"],
        reason=d["reason"], mod_log_channel=d["mod_log_channel"], rules=d.get("rules", ""), bot=self.bot
      )
      self.bot.add_view(view)
    for view_id, d in data.get("gpt_actions", {}).items():
      view = GptActionConfirmView(view_id=view_id, user_id=d.get("user_id"), action=d["action"], language=d["language"], bot=self.bot)
      self.bot.add_view(view)

  def _get_guild_entry(self, guild_id: int) -> dict:
    expired = [k for k, v in self.history.items() if v["timestamp"] < time() - 86400]
    for k in expired:
      del self.history[k]
    if guild_id not in self.history:
      self.history[guild_id] = {
        "timestamp": time(),
        "history": [],
        "user_memories": {},
        "guild_memories": [],
      }
    return self.history[guild_id]

  def _memory_ops(self, guild_id: int) -> dict:
    return {
      "save_user":    lambda g, u, t: self._save_user_memory(g, u, t),
      "remove_user":  lambda g, u, i: self._remove_user_memory(g, u, i),
      "save_guild":   lambda g, t:    self._save_guild_memory(g, t),
      "remove_guild": lambda g, i:    self._remove_guild_memory(g, i),
    }

  async def _save_user_memory(self, guild_id, user_id, text) -> str:
    entry = self._get_guild_entry(guild_id)
    uid = str(user_id)
    entry["user_memories"].setdefault(uid, []).append(text)
    return f"Saved. Total for user: {len(entry['user_memories'][uid])}"

  async def _remove_user_memory(self, guild_id: int, user_id, indices: list[int]) -> str:
    entry = self._get_guild_entry(guild_id)
    memories = entry["user_memories"].get(str(user_id), [])
    for i in sorted(indices, reverse=True):
      if 0 <= i < len(memories):
        memories.pop(i)
    return f"Removed. Remaining: {len(memories)}"

  async def _save_guild_memory(self, guild_id: int, text: str) -> str:
    entry = self._get_guild_entry(guild_id)
    entry["guild_memories"].append(text)
    return f"Saved. Total for server: {len(entry['guild_memories'])}"

  async def _remove_guild_memory(self, guild_id: int, indices: list[int]) -> str:
    entry = self._get_guild_entry(guild_id)
    memories = entry["guild_memories"]
    for i in sorted(indices, reverse=True):
      if 0 <= i < len(memories):
        memories.pop(i)
    return f"Removed. Remaining: {len(memories)}"

  async def _build_context(self, message: Message) -> dict | None:
    user = message.author
    guild = message.guild
    channel = message.channel

    ref_msg = None
    if message.reference:
      try:
        ref_msg = (
          message.reference.cached_message or
          await channel.fetch_message(message.reference.message_id)
        )
      except Exception:
        return None

    return {
      "user": user,
      "user_id": user.id,
      "display_name": user.display_name,
      "roles": str([r.name for r in getattr(user, "roles", [])]),
      "guild": guild,
      "guild_id": guild.id if guild else None,
      "guild_name": guild.name if guild else None,
      "channel": channel,
      "channel_id": channel.id,
      "channel_name": getattr(channel, "name", "DM"),
      "can_ban": user.guild_permissions.ban_members if guild else False,
      "can_mute": user.guild_permissions.mute_members if guild else False,
      "can_kick": user.guild_permissions.kick_members if guild else False,
      "message": message,
      "ref_msg": ref_msg,
    }

  async def _build_system_message(self, ctx: dict, language: str) -> dict:
    ec = self.bot.get_cog("EmojiCollector")
    relevant = await ec.get_relevant_emojis(ctx["message"].content, limit=8)
    guild_id = ctx["guild_id"]
    uid = str(ctx["user_id"])
    display_name = ctx["display_name"]

    guild_entry = self.history.get(guild_id, {})
    guild_memories = guild_entry.get("guild_memories", [])
    user_memories = guild_entry.get("user_memories", {}).get(uid, [])

    def _fmt_emoji(e: str) -> str:
      parts = e.split(":")
      if len(parts) == 3:
        animated_flag, name, eid = parts
        prefix = "a" if animated_flag == "1" else ""
        return f"<{prefix}:{name}:{eid}>"
      if ":" in e:
        name, eid = e.rsplit(":", 1)
        return f"<:{name}:{eid}>"
      return e

    emoji_section = "\n".join(f"- {_fmt_emoji(e)}" for e in relevant) if relevant else "- none"

    memory_section = ""
    if guild_memories or user_memories:
      memory_section = "\n## Memory\n"
      if guild_memories:
        memory_section += "### Server\n" + "\n".join(f"{i}. {m}" for i, m in enumerate(guild_memories)) + "\n"
      if user_memories:
        memory_section += f"### User {display_name} ({uid})\n" + "\n".join(f"{i}. {m}" for i, m in enumerate(user_memories)) + "\n"

    context_section = ""
    if ctx["guild"]:
      context_section = (
        f"Roles: {ctx['roles']}\n"
        f"Server: {ctx['guild_name']} (ID: {ctx['guild_id']})\n"
        f"Channel: {ctx['channel_name']} (ID: {ctx['channel_id']})\n"
        f"Permissions: ban={ctx['can_ban']}, mute={ctx['can_mute']}, kick={ctx['can_kick']}\n"
      )

    return {
      "role": "system",
      "content": message_for_wolium + f"""
## Available emojis
{emoji_section}

## Current context
User: {display_name} (ID: {ctx['user_id']})
{context_section}Language: {language}{memory_section}"""
    }

  async def _build_user_message(self, message: Message, ctx: dict) -> dict:
    ref_msg = ctx["ref_msg"]
    text_content = dumps({
      "Author": {
        "Name": str(message.author.name),
        "Display Name": str(message.author.display_name),
        "ID": str(message.author.id),
      },
      "Message": {"Content": str(message.content), "ID": str(message.id)},
      "Time": f"{message.created_at} UTC+0",
      "Reference": (
        {
          "Message": {"Content": str(ref_msg.content), "ID": str(ref_msg.id)},
          "Time": f"{ref_msg.created_at} UTC+0",
          "Author Name": str(ref_msg.author.name),
          "Author Display Name": str(ref_msg.author.display_name),
          "Author ID": str(ref_msg.author.id),
        }
        if ref_msg else "No reference"
      ),
    }, ensure_ascii=False)

    image_attachments = [
      att for att in message.attachments
      if att.content_type and att.content_type.startswith("image/")
    ][:3]

    if not image_attachments:
      return {"role": "user", "content": text_content}

    content = [{"type": "text", "text": text_content}]
    for att in image_attachments:
      try:
        raw = await att.read()
        resized = await _downscale_image(raw)
        b64 = b64encode(resized).decode("ascii")
        content.append({
          "type": "image_url",
          "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
      except Exception:
        continue

    return {"role": "user", "content": content}

  async def GPT(self, message: Message, language: str, invite: Invite, retries: int = 0):
    tm = self.bot.get_cog("TranslateMessage")

    ctx = await self._build_context(message)
    if ctx is None:
      return None, await tm.translate_message('gpt.reply_too_old', language), None

    guild_entry = self._get_guild_entry(message.guild.id)
    history = guild_entry["history"]

    system_msg = await self._build_system_message(ctx, language)
    if history:
      history[0] = system_msg
    else:
      history.insert(0, system_msg)
    history.append(await self._build_user_message(message, ctx))

    blocked_tools = []
    user = message.author
    perms = ["kick_members", "ban_members", "mute_members"]
    for perm in perms:
      if not getattr(user.guild_permissions, perm, False) or not getattr(message.guild.me.guild_permissions, perm, False):
        blocked_tools.append("perform_moderation_action")
        break
    allowed_tools = [tool for tool in tools if tool["function"]["name"] not in blocked_tools]

    ai = _make_ai_client()
    memory_ops = self._memory_ops(message.guild.id)
    response_text = ""
    action_view = None
    status_msg = None

    try:
      _seen_calls: set[tuple[str, str]] = set()

      for _iter in range(_MAX_TOOL_ITERATIONS + 1):
        complete_task = create_task(_complete_with_retry(
          ai,
          messages=history,
          tools=allowed_tools if _iter < _MAX_TOOL_ITERATIONS else [],
          temperature=temperature,
          max_tokens=max_tokens,
          top_p=top_p,
        ))

        if status_msg is None:
          done, _pending = await wait({complete_task}, timeout=8)
          if complete_task not in done:
            thinking_text = await tm.translate_message('gpt.still_thinking', language)
            try:
              status_msg = await message.reply(thinking_text)
            except Exception:
              status_msg = None

        result = await complete_task

        # print(f"[GPT DEBUG] provider={result.provider} model={result.model} content={result.content!r} tool_calls={result.tool_calls}")

        response_text = result.content
        tool_calls = result.tool_calls

        if not tool_calls:
          history.append({"role": "assistant", "content": response_text})
          break

        if _iter >= _MAX_TOOL_ITERATIONS:
          history.append({"role": "assistant", "content": response_text})
          break

        unique_calls = []
        for tc in tool_calls:
          call_sig = (tc.name, tc.arguments)
          if call_sig not in _seen_calls:
            unique_calls.append(tc)

        if not unique_calls:
          history.append({"role": "assistant", "content": response_text})
          break

        history.append({
          "role": "assistant",
          "content": response_text,
          "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
            for tc in unique_calls
          ],
        })

        label = _sanitize_response(response_text or "").strip()
        if not label or len(label) > _STATUS_LABEL_MAX_LEN:
          key = TOOL_STATUS_KEYS.get(unique_calls[0].name, "gpt.tool_status.default")
          label = await tm.translate_message(key, language)
        if status_msg is None:
          try:
            status_msg = await message.reply(label)
          except Exception:
            status_msg = None
        else:
          try:
            await status_msg.edit(content=label)
          except Exception:
            pass

        any_error_in_batch = False
        for tc in unique_calls:
          try:
            args = loads(tc.arguments)
          except JSONDecodeError:
            args = {}
          raw_result, view = await dispatch_tool(tc.name, args, ctx, language, self.bot, memory_ops)
          if view:
            action_view = view
          is_error = isinstance(raw_result, str) and raw_result.startswith("Tool error")
          safe_result = _make_tool_result(tc.name, str(raw_result), is_error=is_error)
          history.append({"role": "tool", "tool_call_id": tc.id, "content": safe_result})
          _seen_calls.add((tc.name, tc.arguments))
          if is_error:
            any_error_in_batch = True

        guild_entry["timestamp"] = time()
        await _trim_history(history)

      response_text = _sanitize_response(response_text)

    except Exception as e:
      err_str = str(e)
      request_had_image = _history_has_image(history)

      if not request_had_image:
        for marker, key in [
          ('Connection aborted', "gpt.connection_aborted"),
          ('Payment Required', "gpt.payment_required"),
          ('Bad Gateway', "gpt.bad_gateway"),
          ('Gateway Timeout',"gpt.gateway_timeout"),
          ('overloaded', "gpt.overloaded"),
          ('Model too busy', "gpt.model_too_busy"),
          ('Internal Server Error', "gpt.internal_server_error"),
        ]:
          if marker in err_str:
            return None, await tm.translate_message(key, language), status_msg

      traceback_msg = "".join(format_exception(type(e), e, e.__traceback__))[:5000]
      se = self.bot.get_cog("SendEmbed")
      fields = []
      if request_had_image:
        fields.append({'name': "Debug", 'value': "Request contained an image (vision path)", 'inline': False})
      if message.guild:
        fields.append({'name': "Server", 'value': f"{message.guild.id} | {message.guild.name}", 'inline': False})
        fields.append({'name': "Channel", 'value': f"{message.channel.name} | {message.channel.id}", 'inline': False})
      fields.append({'name': "Error", 'value': f"```py\n{traceback_msg[:800]}```", 'inline': False})
      await se.send_embed(
        title=await tm.translate_message("gpt.ai_error_title", language),
        description=str(e)[:500],
        color=Color.red(),
        fields=fields,
        footer_text="AI | GPT",
        author_text="ERROR",
        guild_id=807304463449849938,
        channel_id=1159138280651104256,
      )
      return None, await tm.translate_message("gpt.generation_error", language), status_msg

    return action_view, response_text, status_msg

  def _check_automod_permissions(self, message: Message, mod_log_channel_id: int) -> tuple[bool, list[str]]:
    missing = []
    guild = message.guild
    me = guild.me if guild else None
    if me is None:
      return False, ["not_in_guild"]

    chan_perms = message.channel.permissions_for(me)
    if not chan_perms.manage_messages:
      missing.append("manage_messages (channel)")
    if not chan_perms.read_message_history:
      missing.append("read_message_history (channel)")

    mod_channel = self.bot.get_channel(mod_log_channel_id)
    if mod_channel is None:
      missing.append("mod_log_channel_not_found")
    else:
      mod_perms = mod_channel.permissions_for(me)
      if not mod_perms.send_messages:
        missing.append("send_messages (mod_log)")
      if not mod_perms.embed_links:
        missing.append("embed_links (mod_log)")

    return (len(missing) == 0), missing

  async def _warn_missing_perms_once(self, guild_id: int, missing: list[str], language: str):
    now = time()
    last = self._automod_perm_warned.get(guild_id, 0)
    if now - last < self._automod_warn_cooldown:
      return
    self._automod_perm_warned[guild_id] = now

    tm = self.bot.get_cog("TranslateMessage")
    se = self.bot.get_cog("SendEmbed")
    await se.send_embed(
      title=await tm.translate_message("automod.missing_permissions_title", language),
      description=", ".join(missing),
      color=Color.red(),
      fields=[{'name': "Guild", 'value': str(guild_id), 'inline': False}],
      footer_text="AI | AutoMod",
      author_text="ERROR",
      guild_id=807304463449849938,
      channel_id=1159138280651104256,
    )

  def _build_automod_system_message(self, rules: str, language: str) -> dict:
    content = (
      f"Server Rules:\n\n"
      f"{rules or 'Prohibited: Insults, Spam, Profanity, Advertising, Flood, Disrespect to Staff, Threats, Discrimination and other violations.'}\n\n"
      f"{rules_data}\n\n"
      f"Server language: {language}\n"
      f"Write the \"reason\" field in this language.\n"
    )
    return {"role": "system", "content": content}

  def _parse_automod_verdict(self, response_text: str) -> tuple[bool, str | None, int]:
    try:
      verdict = loads(response_text)
      flagged = bool(verdict.get("violation"))
      reason = verdict.get("reason")
      delete_previous = max(0, min(int(verdict.get("delete_previous") or 0), 10))
      return flagged, reason, delete_previous
    except (JSONDecodeError, AttributeError, TypeError, ValueError):
      return False, None, 0

  async def _delete_previous_messages(self, message: Message, count: int) -> list[Message]:
    if count <= 0:
      return []

    found = []
    try:
      async for prev in message.channel.history(limit=100, before=message):
        if prev.author.id == message.author.id:
          found.append(prev)
          if len(found) >= count:
            break
    except Exception:
      return []

    for prev in found:
      try:
        await prev.delete()
      except Exception:
        pass

    return found

  def _format_deleted_listing(self, deleted_previous: list[Message]) -> str:
    listing = "\n".join(
      f"{i + 1}. {(m.content or '-')[:80]}"
      for i, m in enumerate(reversed(deleted_previous))
    )
    return listing[:1000]

  async def automod(self, message: Message, language: str, invite: Invite, guild_config: dict, retries: int = 0):
    tm = self.bot.get_cog("TranslateMessage")
    channel_id = guild_config['mod_log_channel']
    rules: str = guild_config.get('rules', '')
    guild_id = message.guild.id
    history_key = str(message.channel.id)

    ok, missing = self._check_automod_permissions(message, channel_id)
    if not ok:
      if retries == 0:
        await self._warn_missing_perms_once(guild_id, missing, language)
      return

    ai = _make_ai_client()

    try:
      if history_key not in automod_history:
        automod_history[history_key] = [self._build_automod_system_message(rules, language)]

      history = automod_history[history_key]
      history[0] = self._build_automod_system_message(rules, language)

      history.append({
        "role": "user",
        "content": dumps({
          "author_id": message.author.id,
          "author": message.author.display_name,
          "content": message.content,
          "ts": int(message.created_at.timestamp()),
        }, ensure_ascii=False)
      })

      result = await ai.complete(
        messages=history,
        temperature=temperature,
        max_tokens=80,
        top_p=top_p,
        response_format={"type": "json_object"},
      )
      response_text = result.content

      history.append({"role": "assistant", "content": response_text})
      await _trim_history(history)

      flagged, reason, delete_previous = self._parse_automod_verdict(response_text)
      if not flagged:
        return

      try:
        await message.delete()
      except Exception:
        pass

      deleted_previous = await self._delete_previous_messages(message, delete_previous)

      se = self.bot.get_cog("SendEmbed")
      fields = [
        {'name': await tm.translate_message('general.channel', language), 'value': f"{message.channel.id} | {message.channel.mention} | {message.channel.name}", 'inline': True},
        {'name': await tm.translate_message('report.user_message', language), 'value': str(message.content), 'inline': True},
      ]
      if reason:
        fields.append({'name': await tm.translate_message('punishment.violation_reason', language), 'value': str(reason)[:1000], 'inline': True})

      if deleted_previous:
        fields.append({
          'name': await tm.translate_message('automod.also_deleted', language),
          'value': self._format_deleted_listing(deleted_previous),
          'inline': False,
        })

      description = (
        f"## {await tm.translate_message('general.message', language)} **{message.author.mention}** {await tm.translate_message('automod.suspected_suspicious', language)}\n"
        f"### {await tm.translate_message('general.text_label', language)}\n-# {message.content}\n"
        f"### {await tm.translate_message('automod.what_it_counts', language)}\n-# {reason or ''}"
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
        channel_id=channel_id,
      )

      view_id = str(uuid4())[:8]
      view = ViolationsView(
        view_id=view_id, member_id=message.author.id, user_id=message.author.id, guild_id=guild_id,
        channel_id=embed_message.channel.id, message_id=embed_message.id,
        language=language, reason=reason, mod_log_channel=channel_id, rules=rules, bot=self.bot
      )
      view.save()
      self.bot.add_view(view)
      await embed_message.edit(embed=embed, view=view)

    except Exception as e:
      try:
        automod_history[history_key].pop()
      except Exception:
        pass

      err_str = str(e)
      if any(marker in err_str for marker in _RETRYABLE):
        if retries < 5:
          await self.automod(message, language, invite, guild_config, retries + 1)
        return

      traceback_msg = "".join(format_exception(type(e), e, e.__traceback__))[:5000]
      se = self.bot.get_cog("SendEmbed")
      fields = [
        {'name': "Server", 'value': f"{message.guild.id} | {invite} | {message.guild.name}", 'inline': False},
        {'name': "Channel", 'value': f"<#{message.channel.id}> (`{message.channel.id}` | `{message.channel.name}`)", 'inline': False},
      ]
      for i in range(0, len(traceback_msg), 1000):
        fields.append({'name': "Error", 'value': f"```py\n{traceback_msg[i:i + 1000]}```", 'inline': False})
      await se.send_embed(
        title=await tm.translate_message("gpt.ai_automod_error_title", language),
        description=f"{e}"[:500],
        color=Color.red(),
        fields=fields,
        footer_text="AI | AutoMod",
        author_text="ERROR",
        guild_id=807304463449849938,
        channel_id=1159138280651104256,
      )

def setup(bot: commands.Bot):
  bot.add_cog(GPT(bot))