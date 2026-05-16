from nextcord import Guild, Member, Message, Embed, Color, Invite, TextChannel
from nextcord.ext import commands
from datetime import datetime, timezone
from time import time
from traceback import format_exception
from asyncio import sleep
from re import search, DOTALL, compile
from json import loads, JSONDecodeError, dumps
from Utils.config import tools, temperature, max_tokens, top_p, automod_history, rules_data, o_models, o_url, message_for_wolium
from Utils.ai_client import AIClient, HuggingFaceConfig, OllamaConfig
from Utils.config import hf_api_keys, hf_models
from Utils.gpt_views import ViolationsView, GptActionConfirmView, load_views
from Utils.gpt_tools import dispatch_tool
import Utils.translate_to_all_languages
from uuid import uuid4

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _make_ai_client() -> AIClient:
  configs = []

  if hf_api_keys and hf_models:
    configs.append(HuggingFaceConfig(
      api_keys=list(hf_api_keys),
      models=list(hf_models),
      priority=0,
    ))

  configs.append(OllamaConfig(
    base_url=o_url,
    models=o_models,
    priority=10,
  ))

  return AIClient(configs)

def _trim_history_sync(items: list, max_size: int = 22):
  while len(items) > max_size:
    del items[1]

async def _trim_history(items: list, max_size: int = 22):
  await sleep(0)
  _trim_history_sync(items, max_size)
  return items

async def _extract_automod_verdict(text: str):
  await sleep(0)
  match = search(r'(True|False)\s*`([^`]*)`', text, DOTALL)
  if match:
    flagged = match.group(1) == "True"
    reason = match.group(2).strip() or None
    return flagged, reason
  return None, None

_RETRYABLE = (
  'Connection aborted', 'Payment Required', 'Bad Gateway',
  'Gateway Timeout', 'overloaded', 'Model too busy', 'Internal Server Error',
)

_MAX_TOOL_ITERATIONS = 3
 
_XML_TOOL_RE = compile(r'<\w[\w_]*\s[^>]*/>', DOTALL)

_FILLER_PREFIXES = (
  "Certainly! ", "Certainly, ", "Of course! ", "Of course, ",
  "Sure! ", "Sure, ", "Absolutely! ", "Absolutely, ",
  "Great! ", "Great, ", "I'd be happy to ", "I'd be happy to help ",
  "I'll help you ", "Let me help you ", "Allow me to ",
)

def _sanitize_response(text: str) -> str:
  text = _XML_TOOL_RE.sub('', text).strip()
  for prefix in _FILLER_PREFIXES:
    if text.startswith(prefix):
      text = text[len(prefix):].lstrip()
      break
  return text
 
def _make_tool_result(tool_name: str, result: str, is_error: bool = False) -> str:
  if is_error:
    short = result[:200] if len(result) > 200 else result
    return dumps({"tool": tool_name, "status": "error", "message": short}, ensure_ascii=False)
  return dumps({"tool": tool_name, "status": "ok", "result": result}, ensure_ascii=False)

class GPT(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.history: dict[int, dict] = {}

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
    relevant = await ec.get_relevant_emojis(ctx["message"].content, limit=20)
    guild_id = ctx["guild_id"]
    uid = str(ctx["user_id"])
    display_name = ctx["display_name"]

    guild_entry = self.history.get(guild_id, {})
    guild_memories = guild_entry.get("guild_memories", [])
    user_memories = guild_entry.get("user_memories", {}).get(uid, [])

    def _fmt_emoji(e: str) -> str:
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

  def _build_user_message(self, message: Message, ctx: dict) -> dict:
    ref_msg = ctx["ref_msg"]
    content = dumps({
      "Message": {"Content": str(message.content), "ID": str(message.id)},
      "Time": f"{message.created_at} UTC+0",
      "Reference": (
        {
          "Content": str(ref_msg.content),
          "Author Name": str(ref_msg.author.name),
          "Author Display Name": str(ref_msg.author.display_name),
          "Author ID": str(ref_msg.author.id),
        }
        if ref_msg else "No reference"
      ),
    }, ensure_ascii=False)
    return {"role": "user", "content": content}

  async def GPT(self, message: Message, language: str, invite: Invite, retries: int = 0):
    tm = self.bot.get_cog("TranslateMessage")

    ctx = await self._build_context(message)
    if ctx is None:
      return None, await tm.translate_message('gpt.reply_too_old', language)

    guild_entry = self._get_guild_entry(message.guild.id)
    history = guild_entry["history"]

    system_msg = await self._build_system_message(ctx, language)
    if history:
      history[0] = system_msg
    else:
      history.insert(0, system_msg)
    history.append(self._build_user_message(message, ctx))

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

    try:
      _seen_calls: set[tuple[str, str]] = set()

      for _iter in range(_MAX_TOOL_ITERATIONS + 1):
        result = await ai.complete(
          messages=history,
          tools=allowed_tools if _iter < _MAX_TOOL_ITERATIONS else [],
          temperature=temperature,
          max_tokens=max_tokens,
          top_p=top_p,
        )

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
            _seen_calls.add(call_sig)
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

        guild_entry["timestamp"] = time()
        await _trim_history(history)

      response_text = _sanitize_response(response_text)

    except Exception as e:
      err_str = str(e)
      for marker, key in [
        ('Connection aborted', "gpt.connection_aborted"),
        ('Payment Required',   "gpt.payment_required"),
        ('Bad Gateway',        "gpt.bad_gateway"),
        ('Gateway Timeout',    "gpt.gateway_timeout"),
        ('overloaded',         "gpt.overloaded"),
        ('Model too busy',     "gpt.model_too_busy"),
        ('Internal Server Error', "gpt.internal_server_error"),
      ]:
        if marker in err_str:
          return None, await tm.translate_message(key, language)

      traceback_msg = "".join(format_exception(type(e), e, e.__traceback__))[:5000]
      log = Embed(
        title=await tm.translate_message("gpt.ai_error_title", language),
        description=str(e)[:500],
        color=Color.red(),
        timestamp=datetime.now(timezone.utc),
      )
      if message.guild:
        log.add_field(name="Server",  value=f"{message.guild.id} | {message.guild.name}", inline=False)
        log.add_field(name="Channel", value=f"{message.channel.name} | {message.channel.id}", inline=False)
      log.add_field(name="Error", value=f"**```py\n{traceback_msg[:800]}```**", inline=False)
      await self.bot.get_channel(1159138280651104256).send(embed=log)
      return None, await tm.translate_message("gpt.generation_error", language)

    return action_view, response_text

  async def automod(self, message: Message, language: str, invite: Invite, guild_config: dict, retries: int = 0):
    tm = self.bot.get_cog("TranslateMessage")
    channel_id = guild_config['mod_log_channel']
    rules: str = guild_config.get('rules', '')
    guild_id = message.guild.id

    ai = _make_ai_client()

    try:
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

      result = await ai.complete(
        messages=automod_history[str(guild_id)],
        tools=[],
        temperature=temperature,
        max_tokens=100,
        top_p=top_p,
      )
      response_text = result.content

      automod_history[str(guild_id)].append({"role": "assistant", "content": response_text})
      await _trim_history(automod_history[str(guild_id)])

      flagged, reason = await _extract_automod_verdict(response_text)
      if not flagged:
        return

      try:
        await message.delete()
      except Exception:
        pass

      se = self.bot.get_cog("SendEmbed")
      fields = [
        {'name': await tm.translate_message('general.channel', language), 'value': f"{message.channel.id} | {message.channel.mention} | {message.channel.name}", 'inline': True},
        {'name': await tm.translate_message('report.user_message', language), 'value': str(message.content), 'inline': True},
      ]
      if reason:
        fields.append({'name': await tm.translate_message('punishment.violation_reason', language), 'value': str(await tm.translate_message(reason, language, save=False))[:1000], 'inline': True})

      reason_translated = await tm.translate_message(reason, language, save=False) if reason else ''
      description = (
        f"## {await tm.translate_message('general.message', language)} **{message.author.mention}** {await tm.translate_message('automod.suspected_suspicious', language)}\n"
        f"### {await tm.translate_message('general.text_label', language)}\n-# {message.content}\n"
        f"### {await tm.translate_message('automod.what_it_counts', language)}\n-# {reason_translated}"
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
        automod_history[str(guild_id)].pop()
      except Exception:
        pass

      err_str = str(e)
      if any(marker in err_str for marker in _RETRYABLE):
        if retries < 5:
          await self.automod(message, language, invite, guild_config, retries + 1)
        return

      traceback_msg = "".join(format_exception(type(e), e, e.__traceback__))[:5000]
      log = Embed(
        title=await tm.translate_message("gpt.ai_automod_error_title", language),
        description=f"{e}"[:500],
        color=Color.red(),
        timestamp=datetime.now(timezone.utc),
      )
      log.set_author(name="ERROR")
      log.add_field(name="Server",  value=f"{message.guild.id} | {invite} | {message.guild.name}" if message.guild else "DM", inline=False)
      log.add_field(name="Channel", value=f"<#{message.channel.id}> (`{message.channel.id}` | `{getattr(message.channel, 'name', None) or f'[<@{message.author.id}>]'}`)", inline=False)
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(name="Error", value=f"```py\n{traceback_msg[i:i + 1000]}```", inline=False)
      log.set_footer(text="AI | AutoMod", icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png")
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

def setup(bot: commands.Bot):
  bot.add_cog(GPT(bot))