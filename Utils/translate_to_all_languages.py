from requests import get
from Utils.clean_cyryllic_command_name import clean_cyryllic_command_name
from Utils.clean_latin_command_name import clean_latin_command_name
from Utils.lightshow import lightshow
from json import load, dump, loads, dumps
from Utils.config import номер_перевода, DISCORD_LANGUAGES, gemini_api_keys, system_instruction, gemini_models, g_temperature, g_top_p, g_top_k
from threading import Lock, Thread
from os import replace, path, makedirs, listdir
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from google.genai import types
from time import time, sleep
from re import compile as re_compile
from typing import Callable
import traceback

_file_mtime = {}

_cache: dict[str, dict[str, dict[str, str]]] = {}
_cache_lock = Lock()

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
    text = text.replace(token, original)
  return text

def _is_valid_translation(value) -> bool:
  return isinstance(value, str) and bool(value.strip())

def _file_changed(file_path: str) -> bool:
  try:
    mtime = path.getmtime(file_path)
  except OSError:
    return False
  old = _file_mtime.get(file_path)
  if old is None or mtime > old:
    _file_mtime[file_path] = mtime
    return True
  return False

def _load_all_locales():
  total = 0
  for category in ('commands', 'messages'):
    folder = f'locales/{category}'
    if not path.exists(folder):
      print(f"[LOCALISATION] Folder not found: {folder}")
      continue
    _cache.setdefault(category, {})
    for filename in listdir(folder):
      if not filename.endswith('.json'):
        continue
      lang = filename[:-5]
      file_path = f'{folder}/{filename}'
      if not _file_changed(file_path):
        continue
      try:
        with open(file_path, 'r', encoding='utf-8') as f:
          raw = load(f)
        _cache[category][lang] = {
          k: v for k, v in raw.items()
          if _is_valid_translation(v)
        }
        count = len(_cache[category][lang])
        total += count
        print(f"[LOCALISATION] Loaded {file_path}: {count} keys")
      except Exception:
        print(f"[LOCALISATION] Failed to load {file_path}:")
        traceback.print_exc()
        _cache[category][lang] = {}
  if total>0:
    print(f"[LOCALISATION] Total keys loaded: {total}")

_load_all_locales()

def reload_locales():
  _load_all_locales()

def _locale_watcher():
  while True:
    sleep(5)
    _load_all_locales()

Thread(target=_locale_watcher, daemon=True).start()

def _cache_get(category: str, lang: str, key: str) -> str | None:
  with _cache_lock:
    value = _cache.get(category, {}).get(lang, {}).get(key)
    if not _is_valid_translation(value):
      return None
    return value

def _cache_set(category: str, lang: str, key: str, value: str):
  with _cache_lock:
    _cache.setdefault(category, {}).setdefault(lang, {})[key] = value

BATCH_MAX_KEYS = 120
BATCH_WAIT_SEC = 3.0

_pending: dict[str, dict] = {}
_pending_lock = Lock()
_batch_running = False
_batch_lock = Lock()

json_lock = Lock()
translation_executor = ThreadPoolExecutor(max_workers=8)

gemini_idx = 0
gemini_cooldown = 0
gemini_usage_stats = {}

def get_gemini_model():
  global gemini_idx, gemini_cooldown, gemini_usage_stats
  with json_lock:
    current_time = time()
    if current_time < gemini_cooldown:
      return None, None, None

    if not gemini_usage_stats:
      for key in gemini_api_keys:
        gemini_usage_stats[key] = {
          m: {"rpm": 0, "rpd": 0, "last_reset": current_time}
          for m in gemini_models
        }

    start_idx = gemini_idx
    while True:
      current_key = gemini_api_keys[gemini_idx]
      key_stats = gemini_usage_stats[current_key]

      for model_name, limits in gemini_models.items():
        stats = key_stats[model_name]
        if current_time - stats["last_reset"] >= 60:
          stats["rpm"] = 0
          stats["last_reset"] = current_time

        rpd_ok = limits["rpd"] == -1 or stats["rpd"] < limits["rpd"]
        rpm_ok = limits["rpm"] == -1 or stats["rpm"] < limits["rpm"]

        if rpd_ok and rpm_ok:
          stats["rpm"] += 1
          stats["rpd"] += 1
          client = genai.Client(api_key=current_key)
          config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=g_temperature,
            top_p=g_top_p,
            top_k=g_top_k,
            system_instruction=system_instruction,
            safety_settings=[
              types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
              types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
              types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
              types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            ]
          )
          return client, config, model_name

      gemini_idx += 1
      if gemini_idx >= len(gemini_api_keys):
        gemini_idx = 0

      if gemini_idx == start_idx:
        gemini_cooldown = current_time + 60
        print("\n[LOCALISATION] All API Keys and model limits exhausted. Cooldown 60s.")
        return None, None, None

def switch_gemini_key():
  global gemini_idx, gemini_cooldown
  with json_lock:
    if time() < gemini_cooldown:
      return
    gemini_idx += 1
    if gemini_idx >= len(gemini_api_keys):
      gemini_idx = 0
      gemini_cooldown = time() + 60
      print("\n[LOCALISATION] All API keys Gemini exhausted. Cooldown 60s.")

def parse_gemini_json(text: str) -> dict:
  text = text.strip()
  if text.startswith("```json"):
    text = text[7:-3]
  elif text.startswith("```"):
    text = text[3:-3]
  return loads(text.strip())

def _write_locale_disk(category: str, lang: str, key: str, value: str):
  folder = f'locales/{category}'
  if not path.exists(folder):
    makedirs(folder)
  file_path = f'{folder}/{lang}.json'
  with json_lock:
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

def _store(category: str, lang: str, key: str, value: str):
  _cache_set(category, lang, key, value)
  _write_locale_disk(category, lang, key, value)

def _apply_translation(result: dict, lng: str, translated: str, thing: str, source_text: str):
  if thing == 'name':
    latin = clean_latin_command_name(translated)
    cyrillic = clean_cyryllic_command_name(translated) or source_text
    val = cyrillic if lng in ('bg', 'ru', 'uk') else latin
    limit = 32
  else:
    val = translated
    limit = 100

  val = val[:limit]

  if lng == 'en':
    result['en-US'] = val
    result['en-GB'] = val
  elif lng == 'es':
    result['es-ES'] = val
  elif lng == 'sv':
    result['sv-SE'] = val
  else:
    result[lng] = val

def _google_translate_one(source_text: str, source_lang: str, lang: str, headers: dict) -> str | None:
  try:
    url = (
      f"https://translate.googleapis.com/translate_a/single"
      f"?client=gtx&sl={source_lang}&tl={lang}&dt=t&dj=1&source=input&q={source_text}"
    )
    response = get(url, headers=headers, timeout=15).json()
    return response['sentences'][0]['trans']
  except Exception:
    return None

def _run_batch_worker():
  global _batch_running, номер_перевода
  try:
    sleep(BATCH_WAIT_SEC)

    while True:
      with _pending_lock:
        if not _pending:
          break
        batch_keys = list(_pending.keys())[:BATCH_MAX_KEYS]
        batch = {k: _pending.pop(k) for k in batch_keys}

      with _pending_lock:
        has_more = bool(_pending)

      prompt_map = {}
      placeholder_maps = {}
      for key, task in batch.items():
        if task['thing'] == 'name':
          protected_text = task['source_text']
          mapping = {}
        else:
          protected_text, mapping = protect_placeholders(task['source_text'])
        placeholder_maps[key] = mapping
        for lng in task['langs']:
          prompt_map[f"{key}|||{lng}"] = protected_text

      prompt = (
        f"Translate the following texts. "
        f"Each entry has a unique ID as key and text to translate as value. "
        f"The ID format is 'TRANSLATION_KEY|||TARGET_LANG'. "
        f"Return ONLY a JSON object with the same IDs as keys and translations as values. "
        f"Keep formatting, tokens like §0§, §1§ and Discord markdown intact - do not translate or alter them.\n"
        f"{dumps(prompt_map, ensure_ascii=False)}"
      )

      max_attempts = len(gemini_api_keys) * len(gemini_models)
      translated_map = {}
      for _ in range(max_attempts):
        client, config, selected_model = get_gemini_model()
        if not client:
          sleep(2)
          continue
        try:
          response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
            config=config
          )
          translated_map = parse_gemini_json(response.text)
          sleep(1)
          break
        except Exception as e:
          err = str(e).lower()
          if "429" in err or "quota" in err or "exhausted" in err or "504" in err:
            switch_gemini_key()
          else:
            print(f"\n[LOCALISATION] Gemini batch error: {e}")
            break

      for prompt_id, translation in translated_map.items():
        if '|||' not in prompt_id:
          continue
        key, lng = prompt_id.split('|||', 1)
        if key not in batch:
          continue
        if not _is_valid_translation(translation):
          continue
        task = batch[key]
        translation = restore_placeholders(translation, placeholder_maps.get(key, {}))
        _store(task['category'], lng, key, translation)
        номер_перевода += 1
        console_text = f"\rTranslates {номер_перевода} text to {len(DISCORD_LANGUAGES)} language."
        print(f"{lightshow(console_text)}\033[0m", end="")

        for cb in task.get('callbacks', []):
          try:
            cb(lng, translation)
          except Exception:
            pass

      failed = {}
      for prompt_id in prompt_map:
        if prompt_id not in translated_map or not _is_valid_translation(translated_map.get(prompt_id)):
          key, lng = prompt_id.split('|||', 1)
          failed.setdefault(key, []).append(lng)

      if failed:
        headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en;q=0.5,ru;q=0.5"}
        fallback_futures = {}
        for key, langs in failed.items():
          task = batch[key]
          if task['thing'] == 'name':
            protected_text = task['source_text']
            mapping = {}
          else:
            protected_text, mapping = protect_placeholders(task['source_text'])
          for lng in langs:
            fut = translation_executor.submit(
              _google_translate_one,
              protected_text, task['source_lang'], lng, headers
            )
            fallback_futures[fut] = (key, lng, task, mapping)

        for fut in as_completed(fallback_futures):
          key, lng, task, mapping = fallback_futures[fut]
          try:
            translated = fut.result()
            if _is_valid_translation(translated):
              translated = restore_placeholders(translated, mapping)
              _store(task['category'], lng, key, translated)
              номер_перевода += 1
              console_text = f"\rTranslated {номер_перевода} text to {len(DISCORD_LANGUAGES)} languages."
              print(f"{lightshow(console_text)}\033[0m", end="")
          except Exception:
            pass

      if not has_more:
        break

  finally:
    with _batch_lock:
      _batch_running = False

def _enqueue_background(
  key: str,
  source_text: str,
  source_lang: str,
  category: str,
  thing: str,
  langs: list[str],
  callback: Callable | None = None
):
  global _batch_running
  with _pending_lock:
    if key in _pending:
      _pending[key]['langs'].update(langs)
      if callback:
        _pending[key]['callbacks'].append(callback)
    else:
      _pending[key] = {
        'source_text': source_text,
        'source_lang': source_lang,
        'category': category,
        'thing': thing,
        'langs': set(langs),
        'callbacks': [callback] if callback else []
      }

  with _batch_lock:
    if not _batch_running:
      _batch_running = True
      t = Thread(target=_run_batch_worker, daemon=True)
      t.start()

def format_text(text: str, variables: dict) -> str:
  if not variables:
    return text
  try:
    return text.format(**variables)
  except Exception:
    return text

def find_base_text(key: str, category: str) -> tuple[str | None, str | None]:
  with _cache_lock:
    en_data = _cache.get(category, {}).get('en', {})
    if key in en_data:
      return en_data[key], 'en'
    for lang, data in _cache.get(category, {}).items():
      if key in data:
        return data[key], lang
  return None, None

def search(data: list[dict[str, str]], target: str, thing) -> dict[str, str] | None:
  for item in data:
    for key, value in item.items():
      if value == target:
        limit = 32 if thing == 'name' else 100
        return {k: v[:limit] for k, v in item.items()}
  return None

def translate_to_all_languages(
  text: str | dict | set | list,
  thing: str,
  message_language: str | None = None,
  save: bool = True,
  variables: dict = None
):
  global номер_перевода

  if thing == 'choice':
    return

  category = "messages" if thing == 'message' else "commands"

  if thing == 'message':
    lang = message_language or 'en'

    cached = _cache_get(category, lang, text)
    if cached:
      return format_text(cached, variables)

    source_text, source_lang = find_base_text(text, category)
    if not source_text:
      print(f"\n[ERROR] Translations key '{text}' didnt found in any files.")
      return format_text(text, variables)

    if lang == source_lang:
      return format_text(source_text, variables)

    _enqueue_background(text, source_text, source_lang, category, thing, [lang])
    return format_text(source_text, variables)

  source_text, source_lang = find_base_text(text, category)
  if not source_text:
    print(f"\n[ERROR] Commands key '{text}' didnt found in any files.")
    return {}

  result = {}
  missing_langs = []

  for lng in DISCORD_LANGUAGES:
    cached = _cache_get(category, lng, text)
    if cached:
      _apply_translation(result, lng, cached, thing, source_text)
    else:
      missing_langs.append(lng)

  if missing_langs:
    _enqueue_background(text, source_text, source_lang, category, thing, missing_langs)

  return result