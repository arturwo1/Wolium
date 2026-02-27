from nextcord.ext import commands
from nextcord import Message, Invite, Color
from nextcord.errors import HTTPException
from asyncio import sleep, to_thread, create_task
from string import ascii_letters
from re import sub, search, match
from traceback import format_exception
from cogs.utils.get_invite import GetInvite
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot, гласные, согласные
from cogs.utils.ensure_guild_exists import EnsureGuildExists
from cogs.utils.ensure_user_exists import EnsureUserExists
from cogs.utils.send_embed import SendEmbed
from Utils.config import users, pending
from Utils.parse_time import parse_time
from cogs.utils.get_data import GetData
from cogs.utils.update_data import UpdateData
from cogs.utils.translate_message import TranslateMessage
from json import dumps, loads
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from spellchecker import SpellChecker
from datetime import timezone

class OnMessage(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
    self.spellcheckers = {}

  def _dt_to_ts(self, dt) -> int:
    if getattr(dt, "tzinfo", None) is None:
      dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

  async def get_spellchecker_cached(self, lang: str) -> SpellChecker:
    if lang in self.spellcheckers:
      return self.spellcheckers[lang]
    spell = await to_thread(SpellChecker, language=lang)
    self.spellcheckers[lang] = spell
    return spell

  async def GPTTalk(self,message:Message, language:str, invite: Invite):
    bot_triggers = [f"<@{self.bot.user.id}>",f"<@!{self.bot.user.id}>","Wolium","Волиум","Wolio","Волио"]
    try:
      if message.author!=self.bot.user and (any(trigger in message.content.lower() for trigger in bot_triggers) or (self.bot.user in message.mentions) or ((((message.reference.resolved if message.reference.resolved else (await message.channel.fetch_message(message.reference.message_id))).author.id if message.reference.message_id else 0) if message.reference else 0) == self.bot.user.id)) and message.author.id!=self.bot.user.id and len(message.content.strip()) > 1 and (message.guild.me.guild_permissions.send_messages if message.guild else True):
        try:
          if message.guild:
            guild_config = await (GetData(self.bot)).get_data(message.guild.id,['aibot'],'guild_settings','guild_id',message.guild)
            if guild_config['aibot']==False:
              return
          async with message.channel.typing():
            await sleep(1)
            GPT = self.bot.get_cog("GPT").GPT
            edited, AI_message = await GPT(message,language,invite)
            # print('in on_message',edited,AI_message)
            await sleep(1)
            if AI_message not in [None,'None','']:
              try:
                for i in range(0, len(AI_message), 2000):
                  if i==0:
                    if edited:
                      await message.channel.get_partial_message(edited["message_id"]).edit(content=str(AI_message[i:i+2000]))
                    else:
                      await message.reply(AI_message[i:i+2000], delete_after=5*60)
                  else:
                    await message.channel.send(AI_message[i:i+2000], delete_after=30)
                if not "Не Удалось Сгенерировать Сообщение." in str(AI_message):
                  fields = [
                    {
                      'name':'Пользователь',
                      'value':f"{message.author.id} | {message.author.mention} | {message.author.name}",
                      'inline':True
                    },
                    {
                      'name':'Сервер',
                      'value':f"{message.guild.id} | {invite} | {message.guild.name}" if message.guild else "ЛС",
                      'inline':True
                    },
                    {
                      'name':'Канал',
                      'value':f"<#{message.channel.id}>(`{message.channel.id}` | `{message.channel.name if message.guild else f'[<@{message.author.id}>({message.author.id} | {message.author.name}({message.author.display_name})]'}`)",
                      'inline':True
                    },
                    {
                      'name':'Сообщение пользователя',
                      'value':message.content[:1000],
                      'inline':False
                    },
                    {
                      'name':'Ответ от нейросети',
                      'value':str(AI_message)[:1000],
                      'inline':True
                    }
                  ]
                  await (SendEmbed(self.bot)).send_embed(
                    title='Общение с нейросетью',
                    description=f'**{message.author.mention}** отправил **`{message.content[:1000]}`** в **{message.channel.mention}**\nполучил в ответ: **`{str(AI_message)[:1000]}`**.',
                    color=Color.yellow(),
                    fields=fields,
                    footer_text='Общение с нейросетью',
                    author_text='НЕЙРОСЕТЬ',
                    author_icon=message.author.display_avatar.url,
                    channel_id=1348577132099538966
                  )
                try:
                  await message.delete(delay=5*60)
                except HTTPException:
                  pass
              except HTTPException as e:
                if "Unknown Message" in str(e):
                  return
                traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
                fields = [
                  {
                    'name':'Пользователь',
                    'value':f"{message.author.id} | {message.author.mention} | {message.author.name}",
                    'inline':True
                  },
                  {
                    'name':'Сервер',
                    'value':f"{message.guild.id} | {invite} | {message.guild.name}" if message.guild else "ЛС",
                    'inline':True
                  },
                  {
                    'name':'Канал',
                    'value':f"<#{message.channel.id}>(`{message.channel.id}` | `{message.channel.name if message.guild else f'[<@{message.author.id}>({message.author.id} | {message.author.name}({message.author.display_name})]'}`)",
                    'inline':True
                  },
                  {
                    'name':'Ошибка',
                    'value':traceback_msg,
                    'inline':False
                  }
                ]
                await (SendEmbed(self.bot)).send_embed(
                  title='Ошибка при попытке фильтра/отправки сообщения',
                  description=str(e)[:2048],
                  color=Color.red(),
                  fields=fields,
                  footer_text='Ошибка в GPTTalk',
                  author_text='ЕРРОР',
                  author_icon=message.author.display_avatar.url,
                  channel_id=1159138280651104256
                )
            else:
              try:
                await message.reply(await (TranslateMessage(self.bot)).translate_message('М-м, не знаю, что сказать 🤔',language), delete_after=7)
              except Exception:
                pass

        except Exception as e:
          if "Unknown Message" in str(e):
            return
          elif 'Список API-ключей пуст' in str(e):
            return
          elif 'Нет доступных API-ключей' in str(e):
            return
        
          traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
          fields = [
            {
              'name':'Пользователь',
              'value':f"{message.author.id} | {message.author.mention} | {message.author.name}",
              'inline':True
            },
            {
              'name':'Сервер',
              'value':f"{message.guild.id} | {invite} | {message.guild.name}" if message.guild else "ЛС",
              'inline':True
            },
            {
              'name':'Канал',
              'value':f"<#{message.channel.id}>(`{message.channel.id}` | `{message.channel.name if message.guild else f'[<@{message.author.id}>({message.author.id} | {message.author.name}({message.author.display_name})]'}`)",
              'inline':True
            },
            {
              'name':'Ошибка',
              'value':traceback_msg,
              'inline':False
            }
          ]
          await (SendEmbed(self.bot)).send_embed(
            title='Ошибка при отправке сообщения от ИИ',
            description=str(e)[:2048],
            color=Color.red(),
            fields=fields,
            footer_text='Ошибка в GPTTalk',
            author_text='ЕРРОР',
            author_icon=message.author.display_avatar.url,
            channel_id=1159138280651104256
          )
    except Exception as e:
      if "Unknown Message" in str(e):
        return
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      fields = [
        {
          'name':'Пользователь',
          'value':f"{message.author.id} | {message.author.mention} | {message.author.name}",
          'inline':True
        },
        {
          'name':'Сервер',
          'value':f"{message.guild.id} | {invite} | {message.guild.name}" if message.guild else "ЛС",
          'inline':True
        },
        {
          'name':'Канал',
          'value':f"<#{message.channel.id}>(`{message.channel.id}` | `{message.channel.name if message.guild else f'[<@{message.author.id}>({message.author.id} | {message.author.name}({message.author.display_name})]'}`)",
          'inline':True
        },
        {
          'name':'Ошибка',
          'value':traceback_msg,
          'inline':False
        }
      ]
      await (SendEmbed(self.bot)).send_embed(
        title='Ошибка при попытке фильтра сообщения',
        description=str(e)[:2048],
        color=Color.red(),
        fields=fields,
        footer_text='Ошибка в GPTTalk',
        author_text='ЕРРОР',
        author_icon=message.author.display_avatar.url,
        channel_id=1159138280651104256
      )

  async def games(self, message: Message, language: str):
    async def detect_language(text: str) -> str:
      return await to_thread(detect, text)

    async def get_candidates(spell: SpellChecker, word: str):
      return await to_thread(spell.candidates, word)
    
    if not message.guild:
      return
    perms = message.guild.me.guild_permissions
    if not all([perms.read_messages, perms.read_message_history, perms.send_messages, perms.add_reactions, perms.manage_messages]):
      return
    if message.author.id==self.bot.user.id:
      return

    guild_config = await (GetData(self.bot)).get_data(message.guild.id,['word_channel', 'number_channel', 'words', 'filter'],'guild_settings','guild_id',message.guild)
    word_channel: int = guild_config['word_channel']
    number_channel: int = guild_config['number_channel']
    words: list[str] = loads(guild_config['words'])
    filter:str = guild_config['filter']

    if message.channel.id not in [word_channel, number_channel]:
      return
    
    # symbols = {
    #   "e": "е",
    #   "r": "р",
    #   "t": "т",
    #   "u": "у",
    #   "i": "и",
    #   "o": "о",
    #   "p": "п",
    #   "a": "а",
    #   "s": "с",
    #   "d": "д",
    #   "f": "ф",
    #   "g": "г",
    #   "h": "х",
    #   "k": "к",
    #   "l": "л",
    #   "z": "з",
    #   "v": "в",
    #   "b": "б",
    #   "n": "н",
    #   "m": "м",
    # }

    content = sub(r'ё','е',(sub(r'[,/.\-_=ъыь!"№;%:?*()+\-@#$^& ]', '', message.content.lower()))).strip()#.replace(symbols)
    messages = [m async for m in message.channel.history(limit=5, before=message)]
    last_message = next((m for m in messages if m.id != message.id), None)

    if word_channel and message.channel.id == word_channel:
      if last_message and last_message.author.id == self.bot.user.id and message.author.id != self.bot.user.id:
        await message.reply(await (TranslateMessage(self.bot)).translate_message('Подождите Пока Я Удалю Сообщения Лишние И Потом Уже Пишите!', language), delete_after=3)
        await message.delete(delay=1)
        return

      if content in words:
        await message.reply(await (TranslateMessage(self.bot)).translate_message('Это Слово Уже Было!', language), delete_after=7)
        await message.delete(delay=7)
        return

      if last_message and message.author.id == last_message.author.id:
        await message.reply(await (TranslateMessage(self.bot)).translate_message('Не Ваша Очередь!', language), delete_after=7)
        await message.delete(delay=7)
        return

      if last_message:
        last_content = sub(r'ё','е',(sub(r'[,/.\-_=ъыь!"№;%:?*()+\-@#$^& ]', '', last_message.content.lower()))).strip()
        first_current_letter = content[:1]
        last_last_letter = last_content[-1:]
        if first_current_letter != last_last_letter:
          await message.reply(await (TranslateMessage(self.bot)).translate_message('Ваше Слово Должно Начинаться На', language) + f' **`{last_last_letter}`**!\n' +await (TranslateMessage(self.bot)).translate_message('Ваше Слово Начинается На', language) + f' **`{first_current_letter}`**!',delete_after=7)
          await message.delete(delay=7)
          return
        
      if filter=='extreme':
        checked=None
        if last_message.reactions:
          reactions = last_message.reactions
          for reaction in reactions:
            print(reaction.emoji)
            if reaction.emoji!='✅':
              checked=False
            else:
              checked=True
        if not checked:
          await message.reply(await (TranslateMessage(self.bot)).translate_message('Я Еще Не Проверил Сообщение! Подождите Пока Я Поставлю Галочку.', language), delete_after=15)
          await message.delete(delay=7)
          return
        supp_langs = ["en", "es", "fr", "it", "pt", "de", "ru", "ar", "lv", "eu", "nl"]
        try:
          lang_code = await detect_language(content)
        except LangDetectException as e:
          await message.reply(await (TranslateMessage(self.bot)).translate_message('Произошла Ошибка При Определении Языка Вашего Сообщения:', language)+f" **```py\n{e}```**\n"+await (TranslateMessage(self.bot)).translate_message('Если Вы Не Знаете, Что Делать, Пришлите Скриншот Этой Ошибке На Оффициальном Моем Сервере В Канале Нужном!\nВозможно Сообщение Слишком Короткое.', language), delete_after=15)
          await message.delete(delay=7)
          return
        lang_code = "ru" if lang_code in ['bg','uk','mk'] else lang_code
        if lang_code not in supp_langs:
          await message.reply(await (TranslateMessage(self.bot)).translate_message('Язык Вашего Сообщения Не Добавлен В Базу',language)+f'(`{lang_code}`)!\n'+await (TranslateMessage(self.bot)).translate_message('Выключите Сильный Фильтр Слов в `/настройки`.\n-# когда вы все настроите, удалите это сообщение.\n-# Поддерживаемые языки:', language)+f" **`{'; '.join(f'{supp_lang}' for supp_lang in supp_langs)}`**",delete_after=15)
          await message.delete(delay=7)
          return
        try:
          spell = await self.get_spellchecker_cached(lang_code)
        except ValueError as e:
          await message.reply(await (TranslateMessage(self.bot)).translate_message('Словарь для этого языка не установлен. Пожалуйста, выберите другой язык.', language)+f"\n**```py\n{e}```**\n", delete_after=15)
          await message.delete(delay=7)
          return
        if content not in spell:
          suggs = await get_candidates(spell, content)
          if suggs:
            sugg:str = list(suggs)[0]
            await message.reply(await (TranslateMessage(self.bot)).translate_message('Ваше Слово Содержит Ошибку!\nВозможно Вы Имели Ввиду:', language)+f" `{sugg}`", delete_after=7)
            await message.delete(delay=7)
            return
          await message.reply(await (TranslateMessage(self.bot)).translate_message('Недействительное Слово!', language), delete_after=7)
          await message.delete(delay=7)
          return

      words.append(content)
      await (UpdateData(self.bot)).update_data(message.guild.id, {'words': dumps(words)}, 'guild_settings', 'guild_id', message.guild)
      await message.add_reaction('✅')

    if number_channel and message.channel.id == number_channel:
      if last_message and last_message.author.id == self.bot.user.id and message.author.id != self.bot.user.id:
        await message.reply(await (TranslateMessage(self.bot)).translate_message('Подождите Пока Я Удалю Сообщения Лишние И Потом Уже Пишите!', language), delete_after=3)
        await message.delete(delay=1)
        return

      if last_message and message.author.id == last_message.author.id:
        await message.reply(await (TranslateMessage(self.bot)).translate_message('Не Ваша Очередь!', language), delete_after=7)
        await message.delete(delay=7)
        return

      current_number_match = search(r'\d+', content)
      last_number_match=None
      if last_message:
        last_number_match = search(r'\d+', last_message.content)

      if not current_number_match:
        await message.reply(await (TranslateMessage(self.bot)).translate_message('Вы Ввели Не Число!', language), delete_after=7)
        await message.delete(delay=7)
        return

      if last_message and not last_number_match:
        await message.reply(await (TranslateMessage(self.bot)).translate_message('В Прошлом Сообщении Не Число, Я Его Щас Удалю.', language), delete_after=7)
        await message.delete(delay=7)
        await last_message.delete(delay=5)
        return

      current_number = int(current_number_match.group())
      last_number = int(last_number_match.group()) if last_number_match else 0
      if current_number != last_number + 1:
        await message.reply(await (TranslateMessage(self.bot)).translate_message('Ваше Число Не Подходит!', language), delete_after=7)
        await message.delete(delay=7)
        return

      await message.add_reaction('✅')

  @commands.Cog.listener()
  async def on_message(self, message: Message):
    user_id = message.author.id
    if ((message.guild.id if message.guild else 0) in servers_with_no_acces_for_bot or user_id in users_with_no_acces_for_bot):
      return
    if not self.bot.get_user(user_id):
      return
    if message.guild:
      guild_settings = await (GetData(self.bot)).get_data(message.guild.id,['banned'],'guilds','guild_id',message.guild)
    user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation','banned'],'users','user_id',message.guild)
    language = user_settings['language']

    if user_settings['banned'] or (guild_settings['banned'] if message.guild else False):
      servers_with_no_acces_for_bot.append(message.guild.id)
      users_with_no_acces_for_bot.append(user_id)
      return

    if not message.content:
      return
    
    invite = await (GetInvite(self.bot)).invite(message.guild)
    create_task(self.GPTTalk(message, language, invite))
    await self.games(message,language)
    
    # if search(f"[{гласные}]{3}",message.content) or search(f"[{согласные}]{3}",message.content) or not any(c in ascii_letters + " " for c in message.content) or match(r"^[\W\d_]+$", message.content.strip()) or len(message.content.strip()) < 3 or not message.guild:
    #   return
    # if 'http' in message.content:
    #   return

    if message.guild:
      guild_config = await (GetData(self.bot)).get_data(message.guild.id,['mod_log_channel','moderation','moderation_type','rules', 'ttl_channel'],'guild_settings','guild_id',message.guild)
      if guild_config['mod_log_channel'] and guild_config['moderation'] and guild_config['moderation_type']=='AI' and message.guild.get_channel(int(guild_config['mod_log_channel'])):
        guild_locale = message.guild.preferred_locale
        mod_lang = guild_locale if guild_locale !='en-US' and guild_locale !='en-GB' and guild_locale !='es-ES' and guild_locale !='sv-SE' else 'en' if guild_locale =='en-US' or guild_locale =='en-GB' and guild_locale !='es-ES' and guild_locale !='sv-SE' else 'es' if guild_locale !='en-US' and guild_locale !='en-GB' and guild_locale =='es-ES' and guild_locale !='sv-SE' else 'sv'
        automod = self.bot.get_cog("GPT").automod
        await automod(message,mod_lang,invite,guild_config)

      ttl_channels = loads(guild_config["ttl_channel"])
      ttl_str = ttl_channels.get(str(message.channel.id))
      if ttl_str:
        ttl_sec = int(parse_time(ttl_str) or 0)
        if ttl_sec > 0:
          guild_id = message.guild.id
          ch_key = str(message.channel.id)
          created_ts = self._dt_to_ts(message.created_at)

          g = pending.setdefault(guild_id, {})
          bucket = g.setdefault(ch_key, {})
          bucket[str(message.id)] = created_ts

    if message.author!=self.bot.user:
      user_privacy = await (GetData(self.bot)).get_data(user_id,['save_messages', 'save_message_data'], 'user_privacy', 'user_id', message.guild)
      if user_privacy['save_messages']:
        guild_id = message.guild.id
        channel_id = message.channel.id
        date_time = message.created_at.replace(tzinfo=None)
        content = message.content if user_privacy['save_message_data'] else None
        message_url = message.jump_url
        attachments = str(message.attachments) if user_privacy['save_message_data'] else None

        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          async with self.bot.db_pool.acquire() as connection:
            query = """
            INSERT INTO messages (guild_id, channel_id, user_id, date_time, content, message_url, attachments)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            await connection.execute(query, guild_id, channel_id, user_id, date_time, content, message_url, attachments)

            if user_id not in users:
              await (EnsureGuildExists(self.bot)).ensure_guild_exists(message.guild.id)
              await (EnsureUserExists(self.bot)).ensure_user_exists(user_id,message.author.name,language,message.guild) 
              users.add(user_id)
      
      user_data = await (GetData(self.bot)).get_data(user_id,['xp','bank_balance','balance','upgrade'],'user_data','user_id',message.guild)
      xp = user_data['xp']
      bank_balance = user_data['bank_balance']
      balance = user_data['balance']
      upgrade = user_data['upgrade']

      reward_per_message = (0.001*upgrade)

      data = {
        'xp': xp+1,
        'bank_balance': bank_balance+reward_per_message,
        'balance': balance+reward_per_message,
      }
      await (UpdateData(self.bot)).update_data(user_id, data, 'user_data', 'user_id', message.guild)

    # await self.bot.process_commands(message)

def setup(bot:commands.Bot):
  bot.add_cog(OnMessage(bot))