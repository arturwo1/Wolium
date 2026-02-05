from nextcord import Member, Message, Embed, Color, Invite, ButtonStyle, TextInputStyle, Interaction
from nextcord.ext import commands
from nextcord.ui import View, Button, Modal, TextInput
from datetime import datetime, timedelta, timezone
from huggingface_hub import AsyncInferenceClient
from Utils.search_and_scrape import async_web_search_tool
from cogs.utils.add_violation import AddViolation
from cogs.utils.send_embed import SendEmbed
from cogs.utils.translate_message import TranslateMessage
import Utils.translate_to_all_languages
from time import time
from random import randint
from traceback import format_exception
from Utils.config import tools, temperature, max_tokens, top_p, models, message_for_wolium, history, automod_history, api_keys, rules_data
from Utils.parse_time import parse_time
from asyncio import sleep
from re import search, DOTALL
from json import loads, JSONDecodeError

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

api_key = api_keys[randint(0,len(api_keys)-1)]
model = models[randint(0,len(models)-1)]
client = AsyncInferenceClient(model=model,api_key=api_key)

class mutemodal(Modal):
  def __init__(self, member:Member, language:str,reason:str, message:Message, embed:Embed, bot:commands.Bot,timeout=60*5):
    super().__init__(title=translate_to_all_languages("Enter The Duration Of The Time-Out", 'message', language),timeout=timeout)
    self.bot = bot
    self.member = member
    self.language = language
    self.reason = reason
    self.message = message
    self.embed = embed
    self.duration = TextInput(
      label=translate_to_all_languages("Длительность:", 'message', language),
      style=TextInputStyle.short,
      max_length=28,
      required=True,
      default_value=None,
      placeholder=translate_to_all_languages("Используйте Формат: 1d 1w 1h 1m 1s. 2 Недели - Макс. Длительность Тайм-Аута.", 'message', language)
    )
    self.add_item(self.duration)
      
  async def callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    duration = parse_time(self.duration.value)
    if duration==None:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Неверный Формат Времени.",self.language),ephemeral=True)
      return
    if duration>60*60*24*7*2:
      await interaction.send(await (TranslateMessage(self.bot)).translate_message("Максимальная Длительность Тайм-Аута 2 Недели.",self.language),ephemeral=True)
      return
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Такого Пользователя Не Существует.",self.language),ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Мы не на сервере.",self.language),ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'moderate_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Меня Недостаточно Прав.",self.language),ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'moderate_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Недостаточно Прав.",self.language),ephemeral=True)
      return
    if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<self.member.guild_permissions.value:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У",self.language)+f" **{self.member.mention}**.",ephemeral=True)
      return
    try:
      await self.member.timeout(timeout=timedelta(seconds=duration if duration else 0),reason=self.reason)
      await (AddViolation(self.bot)).add_violation(self.member.id, interaction.guild.id, 'mute', self.reason, duration, round(time()), interaction.user.id)
      try:
        await self.member.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Тайм-Аутнуты По Причине: `{self.reason}`, на{' '+str(timedelta(seconds=duration)) if duration else 'всегда'}, {interaction.user.mention}-ом", 'en',save=False))
      except Exception:
        pass
      self.embed.add_field(
        name=await (TranslateMessage(self.bot)).translate_message(f"Приговор",self.language),
        value=f'**{self.member.mention}** '+await (TranslateMessage(self.bot)).translate_message("Был Успешно Тайм-Аутнут До",self.language)+f' **<t:{duration}:R>**, '+await (TranslateMessage(self.bot)).translate_message("По Причине",self.language)+f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Не Удалось Тайм-Аутнуть Пользователя.",self.language),ephemeral=True)
    
class violationsview(View):
  def __init__(self, member:Member, language:str,reason:str, guild_config:dict, message:Message, embed:Embed, bot:commands.Bot):
    super().__init__(timeout=None)
    self.language = language
    self.reason = reason
    self.member = member
    self.guild_config = guild_config
    self.message = message
    self.embed = embed
    self.bot = bot
    self.mod_log_channel = guild_config['mod_log_channel']
    self.add_violations()

  def add_violations(self):
    ban_button = Button(
      custom_id="ban",
      style=ButtonStyle.primary,
      emoji="🔨",
      label=translate_to_all_languages("Ban", 'message', self.language)
    )
    ban_button.callback = self.ban_callback
    self.add_item(ban_button)

    kick_button = Button(
      custom_id="kick",
      style=ButtonStyle.primary,
      emoji='👢',
      label=translate_to_all_languages("Выгнать", 'message', self.language)
    )
    kick_button.callback = self.kick_callback
    self.add_item(kick_button)

    mute_button = Button(
      custom_id="mute",
      style=ButtonStyle.primary,
      emoji='🔇',
      label=translate_to_all_languages("Mute", 'message', self.language)
    )
    mute_button.callback = self.mute_callback
    self.add_item(mute_button)

    warn_button = Button(
      custom_id="warn",
      style=ButtonStyle.primary,
      emoji='⚠️',
      label=translate_to_all_languages("Warn", 'message', self.language)
    )
    warn_button.callback = self.warn_callback
    self.add_item(warn_button)

  async def ban_callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Такого Пользователя Не Существует.",self.language),ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Мы не на сервере.",self.language),ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'ban_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Меня Недостаточно Прав.",self.language),ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'ban_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Недостаточно Прав.",self.language),ephemeral=True)
      return
    if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<self.member.guild_permissions.value:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У",self.language)+f" **{self.member.mention}**.",ephemeral=True)
      return
    try:
      await self.member.ban(reason=self.reason)
      await (AddViolation(self.bot)).add_violation(self.member.id, interaction.guild.id, 'ban', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Забанены По Причине: `{self.reason}`, {interaction.user.mention}-ом", 'en',save=False))
      except Exception:
        pass
      self.embed.add_field(
        name=await (TranslateMessage(self.bot)).translate_message(f"Приговор",self.language),
        value=f'**{self.member.mention}** '+await (TranslateMessage(self.bot)).translate_message("Был Успешно Забанен По Причине",self.language)+f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Не Удалось Забанить Пользователя.",self.language),ephemeral=True)
  
  async def kick_callback(self, interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Такого Пользователя Не Существует.",self.language),ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Мы не на сервере.",self.language),ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'kick_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Меня Недостаточно Прав.",self.language),ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'kick_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Недостаточно Прав.",self.language),ephemeral=True)
      return
    if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<self.member.guild_permissions.value:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У",self.language)+f" **{self.member.mention}**.",ephemeral=True)
      return
    try:
      await self.member.kick(reason=self.reason)
      await (AddViolation(self.bot)).add_violation(self.member.id, interaction.guild.id, 'kick', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Выгнаны По Причине: `{self.reason}` {interaction.user.mention}-ом", 'en',save=False))
      except Exception:
        pass
      self.embed.add_field(
        name=await (TranslateMessage(self.bot)).translate_message(f"Приговор",self.language),
        value=f'**{self.member.mention}** '+await (TranslateMessage(self.bot)).translate_message("Был Успешно Выгнан По Причине",self.language)+f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Не Удалось Выгнать Пользователя.",self.language),ephemeral=True)
    
    
  
  async def mute_callback(self, interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.send_modal(mutemodal(self.member, self.language, self.reason, self.message, self.embed, self.bot))
    

  async def warn_callback(self,interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Такого Пользователя Не Существует.",self.language),ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Мы не на сервере.",self.language),ephemeral=True)
      return
    if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<self.member.guild_permissions.value:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У",self.language)+f" **{self.member.mention}**.",ephemeral=True)
      return
    try:
      await (AddViolation(self.bot)).add_violation(self.member.id, interaction.guild.id, 'warn', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Предупреждены По Причине: `{self.reason}` {interaction.user.mention}-ом", 'en',save=False))
      except Exception:
        pass
      self.embed.add_field(
        name=await (TranslateMessage(self.bot)).translate_message(f"Приговор",self.language),
        value=f'**{self.member.mention}** '+await (TranslateMessage(self.bot)).translate_message("Был Успешно Предупрежден По Причине",self.language)+f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Не Удалось Предупредить Пользователя.",self.language),ephemeral=True)

async def parse_list(items:list, max_size=22):
  await sleep(0)
  if len(items) > max_size:
    del items[-2:]
  return items

async def extract_reason_value(text: str):
  await sleep(0)
  match = search(r'(True|False)\s*(?:\s*`([^`]*)`)', text, DOTALL)
  if match:
    value = match.group(1) == "True"
    reason = match.group(2).strip() or None
    return value, reason
  return None, None

class GPT(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  async def GPT(self, message: Message, language: str, invite: Invite, retries: int = 0):
    global history, models, client, api_keys
    # print('getting api_key')
    try:
      if not api_keys:
        raise RuntimeError("Список API-ключей пуст. Добавь хотя бы один ключ Hugging Face.")
      if len(api_keys) == 0:
        raise ValueError("Нет доступных API-ключей для Hugging Face!")
    except Exception:
      return None, await (TranslateMessage(self.bot)).translate_message('Не Удалось Сгенерировать Сообщение.\nКредиты На Использование Нейросети Закончились!\nЖдите Начало Следующего Месяца!',language)
    api_key = api_keys[randint(0,len(api_keys)-1)]
    model = models[randint(0,len(models)-1)]
    client = AsyncInferenceClient(model="openai/gpt-oss-20b",provider="novita",api_key=api_key)
    # print('getting reference')
    try:
      reference = (
        f'''
          "Reference": {{
            "Content": "{message.reference.cached_message.content if message.reference.cached_message else (await message.channel.fetch_message(message.reference.message_id)).content}",
            "Author Name": "{message.reference.cached_message.author.name if message.reference.cached_message else (await message.channel.fetch_message(message.reference.message_id)).author.name}",
            "Author Display Name": "{message.reference.cached_message.author.display_name if message.reference.cached_message else (await message.channel.fetch_message(message.reference.message_id)).author.display_name}", 
            "Author ID": "{message.reference.cached_message.author.id if message.reference.cached_message else (await message.channel.fetch_message(message.reference.message_id)).author.id}", 
          }},
        ''' if message.reference else ""
      )
    except Exception:
      return None, await (TranslateMessage(self.bot)).translate_message('Не Удалось Сгенерировать Сообщение.\nВы Отвечаете На Сообщение Которое Дискорд Либо Не Успел Сохранить, Либо Оно Слишком Старое.',language)

    source = (f'''
      "Source": {{
        "Server": "{message.guild.name}",
        "Server ID": "{message.guild.id}",
        "Channel": "{message.channel.name}",
        "Channel ID": "{message.channel.id}"
      }}''' if message.guild else '"Source": "DM"')

    additional = f'''
      "Additional": {{
        "Time": "{message.created_at} UTC+0",
        {'"can_ban": '+str(message.author.guild_permissions.ban_members)+', '+
        '"can_mute": '+str(message.author.guild_permissions.mute_members)+', '+
        '"can_kick": '+str(message.author.guild_permissions.kick_members) if message.guild else ''},
        "User_Language": "{language}"
      }}'''

    user_message_content = f'''
    {{
      "User": {{
        "Name": "{message.author.name}",
        "Display Name": "{message.author.display_name}",
        "ID": "{message.author.id}"
      }},
      "Message": {{
        "Content": "{message.content}",
        "ID": "{message.id}"
      }},
      {source},
      {additional},
      {reference}
    }}'''

    history.append({"role": "user", "content": user_message_content})
    response = None
    edited = None

    try:
      completion = await client.chat.completions.create(
        model=model,
        messages=history,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        response_format={
          "type": "json_schema",
          "json_schema": {
            "schema": {
              "type": "object",
              "properties": {
                "content": {
                  "type": "string",
                  "items": {
                    "type": "integer"
                  }
                }
              },
              "required": [
                "content"
              ],
              "additionalProperties": False
            },
            "strict": True
          }
        }
      )

      assistant_msg = completion.choices[0].message['content']
      try:
        data = loads(assistant_msg)
      except JSONDecodeError:
        data = {}

      response = data.get('content', '')

      if "type" in message.content.lower():
        try:
          msg_data = loads(user_message_content)
          user_id = int(msg_data["User"]["ID"])
          type_ = "ban"
          reason = "manual test"
          duration = 3600
          mod_id = message.author.id

          if str(user_id) == str(mod_id):
            return edited, f"Зачем {type_} самого себя?"
          if str(user_id) == str(self.bot.user.id):
            return edited, f"Зачем {type_} меня?😥"

          user = message.guild.get_member(user_id)
          if type_ == 'ban':
            await user.ban(reason=reason)
            response += f"\nUser <@{user_id}> was successfully banned."
          elif type_ == 'kick':
            await user.kick(reason=reason)
            response += f"\nUser <@{user_id}> was kicked."
          elif type_ == 'mute':
            await user.timeout(timeout=timedelta(seconds=duration), reason=reason)
            response += f"\nUser <@{user_id}> was muted for {timedelta(seconds=duration)}."

        except Exception as e:
          response += f"\nError handling violation: {e}"

      history.append({"role": "assistant", "content": str(response)})

    except Exception as e:
      history.pop()
      traceback_msg = ''.join(format_exception(type(e), e, e.__traceback__))[:5000]
      log = Embed(
        title=f"Ошибка В ИИ",
        description=str(e)[:500],
        color=Color.red(),
        timestamp=datetime.now(timezone.utc)
      )
      if message.guild:
        log.add_field(name="Сервер", value=f"{message.guild.id} | {message.guild.name}", inline=False)
        log.add_field(name="Канал", value=f"{message.channel.name} | {message.channel.id}", inline=False)
      log.add_field(name="Ошибка", value=f"**```py\n{traceback_msg[:800]}```**", inline=False)
      await self.bot.get_channel(1159138280651104256).send(embed=log)
      response = "Не удалось сгенерировать сообщение."

    return edited, response

  async def automod(self,message:Message,language:str,invite:Invite,guild_config:dict,retries:int=0):
    global automod_history, models, client, api_keys
    try:
      if not api_keys:
        raise RuntimeError("Список API-ключей пуст. Добавь хотя бы один ключ Hugging Face.")
      if len(api_keys) == 0:
        raise ValueError("Нет доступных API-ключей для Hugging Face!")
    except Exception:
      return
    api_key = api_keys[randint(0,len(api_keys)-1)]
    model = models[randint(0,len(models)-1)]
    client = AsyncInferenceClient(model=model,api_key=api_key)
    channel_id = guild_config['mod_log_channel']
    rules:str = guild_config['rules']

    guild_id = message.guild.id

    try:
      if str(guild_id) not in automod_history:
        automod_history[str(guild_id)] = []
        automod_history[str(guild_id)].append({
          "role": "system",
          "content": f"""ПРАВИЛА:  
{rules if rules else 'Запрещены Оскорбления, Спам, Ненормативная Лексика, Реклама, Флуд, Оскорбления Администрации, Угрозы, Дискриминация и Прочие Нарушения.'}


{rules_data}
"""
        })
      source = (f'''
          "Source": {{
            "Channel": "{message.channel.name}"
          }},
        '''
      )if message.guild else '"Source": "DM",'

      additional = f'''
        "Additional": {{
          "Time": "{message.created_at} UTC+0",
          "User_Language": "{language}"
        }}
      '''

      user_message_content = f'''
        {{
          "User": {{
            "Name": "{message.author.name}",
            "Display Name": "{message.author.display_name}"
          }},
          "Message": {{
            "Content": "{message.content}"
          }},
          {source}
          {additional}
        }}
      '''

      automod_history[str(guild_id)].append({"role": "user", "content": user_message_content})
      response = await client.chat.completions.create(
        model=model,
        messages=automod_history[str(guild_id)],
        temperature=temperature,
        max_tokens=100,
        top_p=top_p
      )
      response = response.choices[0].message.content

      automod_history[str(guild_id)].append({"role": "assistant", "content": str(response)})
      await parse_list(automod_history[str(guild_id)])
      value,reason = await extract_reason_value(response)
      if value:
        try:
          await message.delete()
        except Exception:
          pass
        fields = [{
            'name':await (TranslateMessage(self.bot)).translate_message('Канал',language),
            'value':f"{message.channel.id} | {message.channel.mention} | {message.channel.name}",
            'inline':True
          },
          {
            'name':await (TranslateMessage(self.bot)).translate_message('Сообщение Пользователя',language),
            'value':str(message.content),
            'inline':True
          },
          ({
            'name':await (TranslateMessage(self.bot)).translate_message('Причина Нарушения',language),
            'value':str(await (TranslateMessage(self.bot)).translate_message(reason,language,save=False))[:1000],
            'inline':True
          } if reason else {}),
        ]
        embed_message, embed = await (SendEmbed(self.bot)).send_embed(
          title=await (TranslateMessage(self.bot)).translate_message("Автомод",language),
          description=('## '+await (TranslateMessage(self.bot)).translate_message('Сообщение',language)+f" **{message.author.mention}** "+await (TranslateMessage(self.bot)).translate_message('Было Заподозрено Подозрительным.',language)+'\n### '+await (TranslateMessage(self.bot)).translate_message('Текст:',language)+f'\n-# {message.content}\n### '+await (TranslateMessage(self.bot)).translate_message('Что Считает Автомод:',language)+f'\n-# {await (TranslateMessage(self.bot)).translate_message(reason,language,save=False)}')[:4000],
          color=Color.orange(),
          fields=fields,
          footer_text=await (TranslateMessage(self.bot)).translate_message("Автомод",language),
          author_text=message.author.name,
          author_icon=message.author.display_avatar.url,
          guild_id=guild_id,
          channel_id=channel_id
        )
        await embed_message.edit(embed=embed,view=violationsview(message.author, language, reason, guild_config, embed_message, embed, self.bot))
    except Exception as e:
      try:
        automod_history[str(guild_id)].pop()
      except Exception:
        pass
      if 'Connection aborted' in str(e):
        if retries > 5:
          await self.automod(message, language, invite, guild_config, retries+1)
        return
      elif 'Payment Required' in str(e):
        if retries > 5:
          await self.automod(message, language, invite, guild_config, retries+1)
        return
      elif 'Bad Gateway' in str(e):
        if retries > 5:
          await self.automod(message, language, invite, guild_config, retries+1)
        return
      elif 'Gateway Timeout' in str(e):
        if retries > 5:
          await self.automod(message, language, invite, guild_config, retries+1)
        return
      elif 'overloaded' in str(e):
        if retries > 5:
          await self.automod(message, language, invite, guild_config, retries+1)
        return
      elif 'Model too busy' in str(e):
        if retries > 5:
          await self.automod(message, language, invite, guild_config, retries+1)
        return
      elif 'Internal Server Error' in str(e):
        if retries > 5:
          await self.automod(message, language, invite, guild_config, retries+1)
        return
      elif 'Список API-ключей пуст' in str(e):
        return
      elif 'Нет доступных API-ключей' in str(e):
        return
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = Embed(
        title=f"Ошибка В ИИ-Автомоде",
        description=(f"{client.model if client else 'AI'}: {e}")[:500],
        color=Color.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.set_author(
        name=f"ЕРРОР",
      )
      log.add_field(
        name="Сервер",
        value=f"{message.guild.id} | {invite} | {message.guild.name}" if message.guild else "ЛС",
        inline=False
      )
      log.add_field(
        name="Канал",
        value=f"<#{message.channel.id}>(`{message.channel.id}` | `{getattr(message.channel,'name') if message.guild else f'[<@{message.author.id}>({message.author.id} | {message.author.name}({message.author.display_name})]'}`)",
        inline=False
      )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
          name="Ошибка",
          value=f"```py\n{traceback_msg[i:i+1000]}```",
          inline=False
        )
      log.set_footer(
        text=f"AI | AutoMod",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
    

def setup(bot:commands.Bot):
  bot.add_cog(GPT(bot))