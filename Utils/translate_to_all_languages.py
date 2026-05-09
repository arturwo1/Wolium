from requests import get
from Utils.clean_cyryllic_command_name import clean_cyryllic_command_name
from Utils.clean_latin_command_name import clean_latin_command_name
from Utils.lightshow import lightshow
from json import load, dump
from Utils.config import номер_перевода, DISCORD_LANGUAGES, номер_перевода_символы, gemini_api_keys, system_instruction, gemini_models, g_temperature, g_top_p, g_top_k
from threading import Lock
from os import replace, path, makedirs
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from google.genai import types
from time import time, sleep
from json import loads

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
              types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE)
            ]
          )
          return client, config, model_name
      
      gemini_idx += 1
      if gemini_idx >= len(gemini_api_keys):
        gemini_idx = 0
      
      if gemini_idx == start_idx:
        gemini_cooldown = current_time + 60
        print("\n[ЛОКАЛИЗАЦИЯ] Все API ключи и лимиты моделей исчерпаны. Кулдаун 60 секунд.")
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
      print("\n[ЛОКАЛИЗАЦИЯ] Все API ключи Gemini исчерпаны. Кулдаун 60 секунд.")

def parse_gemini_json(text: str) -> dict:
  text = text.strip()
  if text.startswith("```json"):
    text = text[7:-3]
  elif text.startswith("```"):
    text = text[3:-3]
  return loads(text.strip())

def translate_gemini_single(source_text: str, source_lang: str, target_lang: str) -> str:
  prompt = f'Translate "{source_text}" from {source_lang} to {target_lang}. Keep formatting and variables intact. Return ONLY a JSON object: {{"translation": "text"}}'
  
  max_attempts = len(gemini_api_keys) * len(gemini_models)
  for _ in range(max_attempts):
    client, config, selected_model = get_gemini_model()
    if not client:
      sleep(1)
      continue
    
    try:
      response = client.models.generate_content(
        model=selected_model,
        contents=prompt,
        config=config
      )
      data = parse_gemini_json(response.text)
      sleep(0.5)
      return data["translation"]
    except Exception as e:
      err = str(e).lower()
      if "429" in err or "quota" in err or "exhausted" in err or "504" in err:
        switch_gemini_key()
      else:
        raise e
  raise Exception("All Gemini keys and models failed")

def translate_gemini_batch(source_text: str, source_lang: str, target_langs: list) -> dict:
  langs_str = ", ".join(target_langs)
  prompt = f'Translate "{source_text}" from {source_lang} to these languages: {langs_str}. Return ONLY JSON where keys are language codes and values are translations.'
  
  max_attempts = len(gemini_api_keys) * len(gemini_models)
  for _ in range(max_attempts):
    client, config, selected_model = get_gemini_model()
    if not client:
      sleep(1)
      continue
    
    try:
      response = client.models.generate_content(
        model=selected_model,
        contents=prompt,
        config=config
      )
      data = parse_gemini_json(response.text)
      sleep(1)
      return data
    except Exception as e:
      err = str(e).lower()
      if "429" in err or "quota" in err or "exhausted" in err or "504" in err:
        switch_gemini_key()
      else:
        raise e
  raise Exception("All Gemini keys and models failed")

def format_text(text: str, variables: dict) -> str:
  if not variables:
    return text
  try:
    return text.format(**variables)
  except Exception:
    return text

def read_locale(category: str, lang: str) -> dict:
  file_path = f'locales/{category}/{lang}.json'
  if path.exists(file_path):
    try:
      with open(file_path, 'r', encoding='utf-8') as f:
        return load(f)
    except Exception:
      pass
  return {}

def write_locale(category: str, lang: str, key: str, value: str):
  with json_lock:
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

def find_base_text(key: str, category: str):
  en_data = read_locale(category, 'en')
  if key in en_data:
    return en_data[key], 'en'
  folder = f'locales/{category}'
  if path.exists(folder):
    import os
    for filename in os.listdir(folder):
      if filename.endswith('.json'):
        lang_code = filename.replace('.json', '')
        data = read_locale(category, lang_code)
        if key in data:
          return data[key], lang_code
  return None, None

def search(data:list[dict[str,str]],target:str,thing)->dict[str,str]|None:
  for item in data:
    for key,value in item.items():
      if value==target:
        if thing=='name':
          for key,value in item.items():
            item[key]=value[:32]
        else:
          for key,value in item.items():
            item[key]=value[:100]
        return item
  return None

def translate_one_google(lang: str, text: str, thing: str, headers: dict, source_text: str, source_lang: str):
  try:
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={lang}&dt=t&dj=1&source=input&q={source_text}"
    response = get(url, headers=headers, timeout=15).json()
    translated = response['sentences'][0]['trans']
    write_locale('commands', lang, text, translated)
  except Exception:
    translated = source_text

  if thing == 'name':
    cleaned_translation = clean_latin_command_name(translated)
    cleaned_russian_translation = clean_cyryllic_command_name(translated) or source_text

    if lang == 'en':
      return {'en-US': cleaned_translation[:32], 'en-GB': cleaned_translation[:32]}
    elif lang == 'es':
      return {'es-ES': cleaned_translation[:32]}
    elif lang == 'sv':
      return {'sv-SE': cleaned_translation[:32]}
    elif lang in ('bg', 'ru', 'uk'):
      return {lang: cleaned_russian_translation[:32]}
    else:
      return {lang: cleaned_translation[:32]}

  elif thing == 'description':
    if lang == 'en':
      return {'en-US': translated[:100], 'en-GB': translated[:100]}
    elif lang == 'es':
      return {'es-ES': translated[:100]}
    elif lang == 'sv':
      return {'sv-SE': translated[:100]}
    else:
      return {lang: translated[:100]}

  return {}

def translate_to_all_languages(text: str | dict | set | list, thing: str, message_language: str | None = None, save: bool = True, variables: dict = None):
  global номер_перевода
  if thing == 'choice':
    return

  category = "messages" if thing == 'message' else "commands"

  headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en;q=0.5,ru;q=0.5"
  }

  if thing == 'message':
    lang = message_language if message_language else 'en'
    
    new_data = read_locale(category, lang)
    if text in new_data:
      return format_text(new_data[text], variables)

    source_text, source_lang = find_base_text(text, category)
    
    if not source_text:
      print(f"\n[ОШИБКА] Ключ перевода '{text}' не найден ни в одном файле.")
      return format_text(text, variables)

    if lang == source_lang:
      return format_text(source_text, variables)

    try:
      translated = translate_gemini_single(source_text, source_lang, lang)
      if translated and save:
        write_locale(category, lang, text, translated)
      return format_text(translated, variables)
    except Exception as e:
      pass

    try:
      url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={lang}&dt=t&dj=1&source=input&q={source_text}"
      response = get(url, headers=headers, timeout=15).json()
      translated = response['sentences'][0]['trans']
      if translated and save:
        write_locale(category, lang, text, translated)
      return format_text(translated or source_text, variables)
    except Exception as e:
      print(f"\n[ОШИБКА] Перевод ключа '{text}' не удался: {e}")
      return format_text(source_text, variables)

  source_text, source_lang = find_base_text(text, category)
  if not source_text:
    print(f"\n[ОШИБКА] Ключ команд '{text}' не найден ни в одном файле.")
    return {}

  new_result = {}
  missing_langs = []
  
  for lng in DISCORD_LANGUAGES:
    new_data = read_locale(category, lng)
    if text in new_data:
      val = new_data[text]
      if thing == 'name':
        if lng == 'en':
          new_result['en-US'] = clean_latin_command_name(val)[:32]
          new_result['en-GB'] = clean_latin_command_name(val)[:32]
        elif lng == 'es':
          new_result['es-ES'] = clean_latin_command_name(val)[:32]
        elif lng == 'sv':
          new_result['sv-SE'] = clean_latin_command_name(val)[:32]
        elif lng in ('bg', 'ru', 'uk'):
          new_result[lng] = clean_cyryllic_command_name(val)[:32] or str(new_data[text])[:32]
        else:
          new_result[lng] = clean_latin_command_name(val)[:32]
      else:
        if lng == 'en':
          new_result['en-US'] = val[:100]
          new_result['en-GB'] = val[:100]
        elif lng == 'es':
          new_result['es-ES'] = val[:100]
        elif lng == 'sv':
          new_result['sv-SE'] = val[:100]
        else:
          new_result[lng] = val[:100]
    else:
      missing_langs.append(lng)

  if not missing_langs:
    return new_result

  try:
    batch_translations = translate_gemini_batch(source_text, source_lang, missing_langs)
    for lng, translated in batch_translations.items():
      if lng in missing_langs:
        write_locale(category, lng, text, translated)
        
        if thing == 'name':
          cleaned_translation = clean_latin_command_name(translated)
          cleaned_russian_translation = clean_cyryllic_command_name(translated) or source_text
          if lng == 'en':
            new_result['en-US'] = cleaned_translation[:32]
            new_result['en-GB'] = cleaned_translation[:32]
          elif lng == 'es':
            new_result['es-ES'] = cleaned_translation[:32]
          elif lng == 'sv':
            new_result['sv-SE'] = cleaned_translation[:32]
          elif lng in ('bg', 'ru', 'uk'):
            new_result[lng] = cleaned_russian_translation[:32]
          else:
            new_result[lng] = cleaned_translation[:32]
        else:
          if lng == 'en':
            new_result['en-US'] = translated[:100]
            new_result['en-GB'] = translated[:100]
          elif lng == 'es':
            new_result['es-ES'] = translated[:100]
          elif lng == 'sv':
            new_result['sv-SE'] = translated[:100]
          else:
            new_result[lng] = translated[:100]
            
        missing_langs.remove(lng)
  except Exception as e:
    pass

  if missing_langs:
    futures = {
      translation_executor.submit(translate_one_google, lng, text, thing, headers, source_text, source_lang): lng
      for lng in missing_langs
    }

    for future in as_completed(futures):
      try:
        part = future.result()
        if part:
          new_result.update(part)
          номер_перевода += 1
          console_text = f"\rБыло переведено {номер_перевода} текста на {len(DISCORD_LANGUAGES)} языка."
          print(f"{lightshow(console_text)}\033[0m", end="")
      except Exception:
        pass

  return new_result