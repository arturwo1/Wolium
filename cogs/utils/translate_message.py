from asyncio import Lock, to_thread
from nextcord import Colour
from nextcord.ext import commands
from deep_translator import GoogleTranslator
from traceback import format_exception
from json import load, dump, loads
from os import replace, path, makedirs, listdir
from time import time
from google import genai
from google.genai import types
from Utils.config import gemini_api_keys, system_instruction, gemini_model, g_temperature, g_top_p, g_top_k

json_lock = Lock()
gemini_idx = 0
gemini_cooldown = 0

def get_gemini_model():
  global gemini_idx, gemini_cooldown
  if time() < gemini_cooldown:
    return None
    
  client = genai.Client(api_key=gemini_api_keys[gemini_idx])

  config = types.GenerateContentConfig(
    system_instruction=system_instruction,
    response_mime_type="application/json",
    temperature=g_temperature,
    top_p=g_top_p,
    top_k=g_top_k,
    safety_settings=[
      types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE
      ),
      types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_NONE
      ),
      types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE
      ),
      types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE
      )
    ]
  )

  return client, config

def switch_gemini_key():
  global gemini_idx, gemini_cooldown
  gemini_idx += 1
  if gemini_idx >= len(gemini_api_keys):
    gemini_idx = 0
    gemini_cooldown = time.time() + 60
    print("[LOCALIZATION] All Gemini API keys exhausted. Cooldown 60 seconds.")

def parse_gemini_json(text: str) -> dict:
  text = text.strip()
  if text.startswith("```json"):
    text = text[7:-3]
  elif text.startswith("```"):
    text = text[3:-3]
  return loads(text.strip())

def _gemini_translate_sync(source_text: str, source_lang: str, target_lang: str) -> str:
  prompt = f'Translate "{source_text}" from {source_lang} to {target_lang}. Keep formatting and variables intact. Return ONLY a JSON object: {{"translation": "text"}}'
  for _ in range(len(gemini_api_keys)):
    client, config = get_gemini_model()
    if not client:
      raise Exception("Gemini on cooldown")
    
    try:
      response = client.models.generate_content(
        model=gemini_model,
        contents=prompt,
        config=config
      )
      data = parse_gemini_json(response.text)
      return data["translation"]
    except Exception as e:
      err = str(e).lower()
      if "429" in err or "quota" in err or "exhausted" in err:
        switch_gemini_key()
      else:
        raise e
  raise Exception("All Gemini keys failed")

def format_text(text: str, variables: dict | None) -> str:
  if not variables:
    return text
  try:
    return text.format(**variables)
  except Exception:
    return text

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
    for filename in listdir(folder):
      if filename.endswith('.json'):
        lang_code = filename.replace('.json', '')
        data = await read_locale_async(category, lang_code)
        if key in data:
          return data[key], lang_code
  return None, None

class TranslateMessage(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  async def tm(self, text: str, message_language: str | None = None, message_language_for_now: str | None = None, save: bool = True, variables: dict | None = None):
    if not text: return "<None>"
    
    lang = message_language_for_now if message_language_for_now else message_language
    if not lang:
      lang = 'en'

    new_data = await read_locale_async('messages', lang)
    if save and text in new_data:
      return format_text(new_data[text], variables)

    source_text, source_lang = await find_base_text_async(text, 'messages')
    
    if not source_text and save:
      print(f"[ОШИБКА] Ключ перевода '{text}' не найден ни в одном файле.")
      return format_text(text, variables)

    if lang == source_lang:
      return format_text(source_text, variables)

    try:
      translated = await to_thread(_gemini_translate_sync, source_text or text, source_lang or "auto", lang)
      if translated and save:
        await write_locale_async('messages', lang, text, translated)
      return format_text(translated, variables)
    except Exception:
      pass

    try:
      translation = await to_thread(GoogleTranslator(source=source_lang or "auto", target=lang).translate, source_text or text)
      if translation:
        if save:
          await write_locale_async('messages', lang, text, translation)
        return format_text(translation, variables)
      return format_text(source_text, variables)
    except Exception as a:
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
    
    async with json_lock:
      try:
        with open('command_translations.json', 'r', encoding='utf-8') as f:
          command_data = load(f)
      except Exception:
        command_data = {}

    if save and text in command_data and lang in command_data[text]:
      print(f"Используется запасная структура (command_translations.json) для: {text}")
      return format_text(command_data[text][lang], variables)
    
    return format_text(source_text, variables)

def setup(bot: commands.Bot):
  bot.add_cog(TranslateMessage(bot))