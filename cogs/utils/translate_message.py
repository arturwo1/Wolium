import asyncio
from nextcord import Colour
from nextcord.ext import commands
from deep_translator import GoogleTranslator
from cogs.utils.send_embed import SendEmbed
from traceback import format_exception
from json import load,dump
from asyncio import Lock
from os import replace
json_lock = Lock()

async def write_json(data:dict[str,dict[str,str]]):
  async with json_lock:
    temp_file = 'command_translations_temp.json'
    try:
      with open(temp_file, 'w', encoding='utf-8') as f:
        dump(data, f, ensure_ascii=False, indent=2)
      replace(temp_file, 'command_translations.json')
    except Exception as e:
      print(f"Ошибка при сохранении JSON: {e}")

class TranslateMessage(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
  
  async def translate(self, text:str,lang:str): 
    return await asyncio.to_thread(GoogleTranslator(source='auto',target=lang).translate,text)

  async def translate_message(self,text:str,message_language:str|None=None,message_language_for_now:str|None=None,save:bool=True):
    async with json_lock:
      with open('command_translations.json','r',encoding='utf-8') as f:
        try:
          data=load(f)
        except Exception as e:
          print(f"Файл переводов поврежден, ошибка: {e}")
          data={}
      
    lang = message_language_for_now if message_language_for_now else message_language
    if not lang:
      return text
    if save and text in data and message_language in data[text]:
      return data[text][message_language]
    try:
      translation = await self.translate(text, lang)
      if translation:
        if save:
          if text not in data:
            data[text] = {}
          data[text][message_language] = translation
          await write_json(data)
        return translation
      return text
    except Exception as a:
      traceback_exception = ''.join(format_exception(type(a), a, a.__traceback__))[:4000]
      fields = [
        {
          'name':'Текст для перевода',
          'value':text,
          'inline':True
        },
        {
          'name':'Язык сообщения',
          'value':message_language,
          'inline':True
        },
        {
          'name':'Ошибка',
          'value':f"**```py\n{traceback_exception}```**",
          'inline':False
        }
      ]
      await (SendEmbed(self.bot)).send_embed(
        title="Ошибка при переводе сообщения",
        description=f"Ошибка: {a}",
        color=Colour.red(),
        fields=fields,
        footer_text="translate_message",
      )
      return text

def setup(bot:commands.Bot):
  bot.add_cog(TranslateMessage(bot))