from asyncio import Lock, to_thread, sleep as a_sleep
from threading import Lock as ThreadLock
from nextcord import Colour
from nextcord.ext import commands, tasks
from deep_translator import GoogleTranslator
from traceback import format_exception
from json import load, dump, loads
from os import replace, path, makedirs, listdir
from time import time
from re import compile as re_compile
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from Utils.config import system_instruction, g_temperature, g_top_p, g_top_k
from Utils.ai_client import AIClient, GenAIConfig

json_lock = Lock()
stats_lock = ThreadLock()
gemini_idx = 0
gemini_cooldown = 0
gemini_usage_stats = {}
ai = AIClient([GenAIConfig(models=None, strategy="default", priority=1)])
schema = {
  "type": "object",
  "properties": {"translation": {"type": "string"}},
  "required": ["translation"]
}

PLACEHOLDER_RE = re_compile(r'\{[^{}]*\}')

def protect_placeholders(text: str) -> tuple[str, dict]:
  mapping = {}
  def repl(m):
    idx = len(mapping)
    token = f"§{idx}§"
    mapping[token] = m.group(0)
    return token
  protected = PLACEHOLDER_RE.sub(repl, text)
  return protected, mapping

def restore_placeholders(text: str, mapping: dict) -> str:
  for token, original in mapping.items():
    text = str(text).replace(token, original)
  return str(text)

async def gemini_translate(source_text: str, source_lang: str, target_lang: str) -> str:
  protected_text, mapping = protect_placeholders(source_text)
  prompt = f'Translate "{protected_text}" from {source_lang} to {target_lang}. Do NOT translate or alter tokens like §0§, §1§ - keep them exactly as-is.'
  for _ in range(10):
    try:
      result = await ai.complete(
        [{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
        temperature=g_temperature,
        top_p=g_top_p,
        top_k=g_top_k,
        max_tokens=2048,
        response_json=True,
        response_schema=schema
      )
      return restore_placeholders(loads(result.content)["translation"], mapping)
    except RuntimeError:
      await a_sleep(5)
  raise RuntimeError("translation failed")

def format_text(text: str, variables: dict | None) -> str:
  if not variables:
    return str(text)
  try:
    return str(text).format(**variables)
  except Exception:
    return str(text)

async def read_locale_async(category: str, lang: str) -> dict:
  file_path = f'locales/{category}/{lang}.json'
  async with json_lock:
    if path.exists(file_path):
      try:
        with open(file_path, 'r', encoding='utf-8') as f:
          return load(f)
      except Exception:
        pass
  return {}

async def write_locale_async(category: str, lang: str, key: str, value: str):
  async with json_lock:
    folder = f'locales/{category}'
    if not path.exists(folder):
      makedirs(folder)
    file_path = f'{folder}/{lang}.json'
    data = {}
    if path.exists(file_path):
      try:
        with open(file_path, 'r', encoding='utf-8') as f:
          data = load(f)
      except Exception:
        pass
    data[key] = value
    temp_file = f'{folder}/{lang}_temp.json'
    try:
      with open(temp_file, 'w', encoding='utf-8') as f:
        dump(data, f, ensure_ascii=False, indent=2)
      replace(temp_file, file_path)
    except Exception:
      pass

async def find_base_text_async(key: str, category: str):
  en_data = await read_locale_async(category, 'en')
  if key in en_data:
    return en_data[key], 'en'
  
  folder = f'locales/{category}'
  if path.exists(folder):
    for filename in sorted(listdir(folder)):
      if filename.endswith('.json') and filename != 'en.json':
        lang_code = filename.replace('.json', '')
        data = await read_locale_async(category, lang_code)
        if key in data:
          return data[key], lang_code
  return None, None

async def detect_language(text: str) -> str:
  try:
    return await to_thread(detect, text)
  except LangDetectException:
    return None

class TranslateMessage(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot

    self.cache = {}
    self.clear_cache.start()

    self.translate_lock = Lock()
    self.translate_last_request = 0.0

  def cog_unload(self):
    self.clear_cache.cancel()

  @tasks.loop(seconds=3600)
  async def clear_cache(self):
    for key in list(self.cache.keys()):
      data = self.cache[key]
      for lang in list(data.keys()):
        entry = data[lang]
        timestamp = entry.get("timestamp", 0)
        if time() - timestamp > 3600:
          del self.cache[key][lang]
      if not self.cache[key]:
        del self.cache[key]

  async def _background_translate(self, text: str, lang: str, source_text: str | None, source_lang: str | None, save: bool = True):
    translated = None
    try:
      translated = await gemini_translate(source_text or text, source_lang or "auto", lang)
    except Exception:
      try:
        protected_text, mapping = protect_placeholders(source_text or text)
        
        async with self.translate_lock:
          now = time()
          wait = 0.25 - (now - self.translate_last_request)
          if wait > 0:
            await a_sleep(wait)
          self.translate_last_request = time()

        translation = await to_thread(GoogleTranslator(source=source_lang or "auto", target=lang).translate, protected_text)
        if translation:
          translated = restore_placeholders(translation, mapping)
      except Exception as a:
        a = str(a)
        if "too many requests" in a:
          return str(text)

        traceback_exception = ''.join(format_exception(type(a), a, a.__traceback__))[:4000]
        fields = [
          {
            'name': 'Ключ / Текст для перевода',
            'value': text,
            'inline': True
          },
          {
            'name': 'Оригинал',
            'value': source_text,
            'inline': True
          },
          {
            'name': 'Язык сообщения',
            'value': lang,
            'inline': True
          },
          {
            'name': 'Ошибка',
            'value': f"**```py\n{traceback_exception}```**",
            'inline': False
          }
        ]
        await self.bot.get_cog("SendEmbed").send_embed(
          title="Ошибка при переводе сообщения",
          description=f"Ошибка: {a}",
          color=Colour.red(),
          fields=fields,
          footer_text="translate_message",
        )

    if translated:
      if save:
        await write_locale_async('messages', lang, text, translated)
      self.cache.setdefault(text, {})[lang] = {"translation": translated, "timestamp": time()}
    else:
      self.cache.get(text, {}).pop(lang, None)
    
    return str(translated or text)

  async def translate_message(self, text: str, message_language: str | None = None, message_language_for_now: str | None = None, save: bool = True, variables: dict | None = None):
    if not text: return "<None>"
    
    lang = message_language_for_now if message_language_for_now else message_language
    if not lang:
      lang = 'en'

    cache_translation = self.cache.get(text, {}).get(lang, {})
    if cache_translation:
      translation = cache_translation.get("translation")
      if translation:
        return format_text(translation, variables)
      if cache_translation.get("pending"):
        source_text, _ = await find_base_text_async(text, 'messages')
        return format_text(source_text or text, variables)

    if not save:
      source_lang = await detect_language(text)
      if source_lang==lang:
        return format_text(text, variables)

      translation = await self._background_translate(text, lang, None, None, save)
      self.cache.setdefault(text, {})[lang] = {
        "translation": translation,
        "timestamp": time()
      }

      return format_text(translation or text, variables)

    new_data = await read_locale_async('messages', lang)
    if text in new_data:
      if new_data[text]:
        self.cache.setdefault(text, {})[lang] = {
          "translation": new_data[text],
          "timestamp": time()
        }
        return format_text(new_data[text], variables)

    source_text, source_lang = await find_base_text_async(text, 'messages')

    if not source_text:
      print(f"[ОШИБКА] Ключ перевода '{text}' не найден ни в одном файле.")
      return format_text(text, variables)

    if lang == source_lang:
      self.cache.setdefault(text, {})[lang] = {
        "translation": source_text,
        "timestamp": time()
      }
      return format_text(source_text, variables)

    fallback = source_text or text
    self.cache.setdefault(text, {})[lang] = {"pending": True, "timestamp": time()}
    self.bot.loop.create_task(self._background_translate(text, lang, source_text, source_lang))

    return format_text(fallback, variables)

  @clear_cache.before_loop
  async def before_clear_cache(self):
    await self.bot.wait_until_ready()

def setup(bot: commands.Bot):
  bot.add_cog(TranslateMessage(bot))