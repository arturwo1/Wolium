import requests
from datetime import datetime
from Utils.clean_cyryllic_command_name import clean_cyryllic_command_name
from Utils.clean_latin_command_name import clean_latin_command_name
from Utils.lightshow import lightshow
from json import load, dump
from Utils.config import номер_перевода, DISCORD_LANGUAGES, номер_перевода_символы
from threading import Lock
from os import replace
json_lock = Lock()

def write_command_json(command_data:dict[str,dict[str,str]]):
  with json_lock:
    temp_file = 'command_translations_temp.json'
    try:
      with open(temp_file, 'w', encoding='utf-8') as f:
        dump(command_data, f, ensure_ascii=False, indent=2)
      replace(temp_file, 'command_translations.json')
    except Exception as e:
      print(f"Ошибка при сохранении JSON: {e}")

def write_json(data):
  with json_lock:
    with open('translations.json','w',encoding='utf-8') as f:
      try:
        data=dump(data,f,ensure_ascii=False,indent=2)
      except Exception as e:
        print(f"Файл переводов поврежден, ошибка: {e}")
        data=[]

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

def translate_to_all_languages(text: str|dict|set|list, thing: str, message_language: str|None=None,save:bool=True):
  if thing=='choice':
    return
  if thing!='message':
    with json_lock:
      with open('translations.json','r',encoding='utf-8') as f:
        try:
          data=load(f)
        except Exception as e:
          print(f"Файл переводов поврежден, ошибка: {e}")
          data=[]
  if thing!='message' and (translations:=search(data,text,thing)):
    return translations
  global номер_перевода, номер_перевода_символы
  headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "en;q=0.5,ru;q=0.5"
  }
  translations = {}
  if thing!='message':
    if len(DISCORD_LANGUAGES)>1 and thing!='message':
      for lang in DISCORD_LANGUAGES:
        #translations[lang] = {}
        try:
          if thing!='choice':
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang}&dt=t&dj=1&source=input&q={text}"
            response = requests.get(url, headers=headers).json()
            translated = response['sentences'][0]['trans']
            cleaned_translation = clean_latin_command_name(translated)
            cleaned_russian_translation = clean_cyryllic_command_name(translated)
          """elif thing=='choice':
            try:
              for key, value in text.items():
                if value not in translations:
                  translations[value] = {}
                url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang}&dt=t&dj=1&source=input&q={key}"
                response = requests.get(url, headers=headers).json()
                translated = response['sentences'][0]['trans']
                if lang == 'en':
                  try:
                    del translations['en']
                  except Exception:
                    pass
                  translations[value]['en-US'] = translated
                  translations[value]['en-GB'] = translated
                elif lang == 'es':
                  try:
                    del translations['es']
                  except Exception:
                    pass
                  translations[value]['es-ES'] = translated
                elif lang == 'sv':
                  try:
                    del translations['sv']
                  except Exception:
                    pass
                  translations[value]['sv-SE'] = translated
                elif lang=='ru':
                  translations[value][lang] = translated
                else:
                  translations[value][lang] = translated
            except Exception as a:
              print(''.join(traceback.format_exception(type(a), a, a.__traceback__)))
              url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang}&dt=t&dj=1&source=input&q={key}"
              response = requests.get(url, headers=headers).json()
              translated = response['sentences'][0]['trans']
              if lang == 'en':
                translations[translated] = ['en-US']
                translations[translated] = ['en-GB']
              elif lang == 'es':
                translations[translated] = ['es-ES']
              elif lang == 'sv':
                translations[translated] = ['sv-SE']
              elif lang=='ru':
                translations[translated] = [lang]
              else:
                translations[translated] = [lang]
            номер_перевода_символы += len(translated)
          """
          if thing == 'name':
            if lang == 'en':
              try:
                translations['en-US'] = cleaned_translation[:32]
                translations['en-GB'] = cleaned_translation[:32]
              except Exception:
                translations['en-US'] = (cleaned_translation+"01")[:32]
                translations['en-GB'] = (cleaned_translation+"01")[:32]
            elif lang == 'es':
              try:
                translations['es-ES'] = cleaned_translation[:32]
              except Exception:
                translations['es-ES'] = (cleaned_translation+"01")[:32]
            elif lang == 'sv':
              try:
                translations['sv-SE'] = cleaned_translation[:32]
              except Exception:
                translations['sv-SE'] = (cleaned_translation+"01")[:32]
            elif lang=='bg' or lang=='ru' or lang=='uk':
              try:
                translations[lang] = cleaned_russian_translation[:32]
              except Exception:
                translations[lang] = (cleaned_russian_translation+"01")[:32]
            else:
              try:
                translations[lang] = cleaned_translation[:32]
              except Exception:
                translations[lang] = (cleaned_translation+"01")[:32]
            номер_перевода_символы += len(translated)
          elif thing == 'description':
            if lang == 'en':
              translations['en-US'] = translated[:100]
              translations['en-GB'] = translated[:100]
            elif lang == 'es':
              translations['es-ES'] = translated[:100]
            elif lang == 'sv':
              translations['sv-SE'] = translated[:100]
            else:
              translations[lang] = translated[:100]
            номер_перевода_символы += len(translated)

        except Exception as a:
          pass
      try:
        for bad_lang in ['en','es','sv']:
          try:
            del translations[bad_lang]
          except Exception:
            pass
      except Exception:
        pass
      номер_перевода += 1

      text1 = f"\r{datetime.now()}: Было переведено {номер_перевода} текста на {len(DISCORD_LANGUAGES)} языка, cо всего можно сказать было переведено {номер_перевода*len(DISCORD_LANGUAGES)} текста."
      print(f"{lightshow(text1)}\033[0m", end="")

      if translations:
        data.append(translations)
        write_json(data)
      return translations
    else:
      номер_перевода += 1
      text = f"\rБыло переведено {номер_перевода} текста на {len(DISCORD_LANGUAGES)} языка, cо всего можно сказать было переведено {номер_перевода*len(DISCORD_LANGUAGES)} текста."
      print(f"{lightshow(text)}\033[0m", end="")
      return
  elif thing=='message':
    with json_lock:
      with open('command_translations.json','r',encoding='utf-8') as f:
        try:
          command_data=load(f)
        except Exception as e:
          print(f"Файл переводов поврежден, ошибка: {e}")
          command_data={}
    if save and text in command_data and message_language in command_data[text]:
      return command_data[text][message_language]
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={message_language}&dt=t&dj=1&source=input&q={text}"
    response = requests.get(url, headers=headers).json()
    translated = response['sentences'][0]['trans']
    if translated:
      if save:
        if text not in command_data:
          command_data[text] = {}
        command_data[text][message_language] = translated
        write_command_json(command_data)
      return translated
    return text
    #print(translation)