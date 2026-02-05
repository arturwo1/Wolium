from nextcord.ext import commands
from nextcord import TextInputStyle, slash_command, Interaction, Colour, Embed, SelectOption, ButtonStyle, ChannelType
from nextcord.ui import View, Button, Select, Modal, TextInput, ChannelSelect
from datetime import datetime, timezone
from time import time
import Utils.translate_to_all_languages
from cogs.utils.translate_message import TranslateMessage
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot, slash_command_cooldown
from traceback import format_exception
from cogs.utils.send_embed import SendEmbed
from cogs.utils.get_data import GetData
from cogs.utils.update_data import UpdateData
from cogs.utils.get_invite import GetInvite
from json import dumps

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class rulesmodal(Modal):
  def __init__(self, user_id:int, language:str, update_callback, guild_config:dict, bot:commands.Bot,timeout=60*5):
    super().__init__(title=translate_to_all_languages("Введите Правила", 'message', language),timeout=timeout)
    self.bot = bot
    self.user_id = user_id
    self.language = language
    self.update_callback = update_callback
    self.guild_config = guild_config
    self.rules = TextInput(
      label=translate_to_all_languages("Правила:", 'message', language),
      style=TextInputStyle.paragraph,
      max_length=4000,
      required=True,
      default_value=guild_config['rules'],
      placeholder=translate_to_all_languages("Правила Которые Нейросеть Будет Использовать При Сканировании Сообщений Пользователей.", 'message', language)
    )
    self.add_item(self.rules)
      
  async def callback(self, interaction: Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    rules = self.rules.value
    if rules:
      data = {
        'rules': rules
      }
      await (UpdateData(self.bot)).update_data(interaction.guild.id, data, 'guild_settings', 'guild_id', interaction.guild)
      if self.guild_config['mod_log_channel'] and interaction.guild and interaction.guild.get_channel(self.guild_config['mod_log_channel']):
        await (SendEmbed(self.bot)).send_embed(
          title=await (TranslateMessage(self.bot)).translate_message("Изменение Конфига Бота",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
          description="### "+await (TranslateMessage(self.bot)).translate_message("Изменение Правил Для Автомодерации\nТак Как Правила Могут Превышать Лимит Максимального Размера Файла В Дискорде, То Показать Изменения Я Не Согу.",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
          color=Colour.yellow(),
          fields=None,
          footer_text=await (TranslateMessage(self.bot)).translate_message("Изменение Правил Для Автомодерации",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
          author_text=interaction.user.name,
          author_icon=interaction.user.display_avatar.url,
          guild_id=interaction.guild.id,
          channel_id=self.guild_config['mod_log_channel']
        )
      await self.update_callback("rules",rules)
    else:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Ничего Не Вписали.",self.language),ephemeral=True)
      return

class конфиг(View):
  def __init__(self, user_id:int, language:str, update_callback, value:str, guild_config:dict, bot:commands.Bot, timeout=60*30):
    super().__init__(timeout=timeout)
    self.language = language
    self.user_id = user_id
    self.update_callback = update_callback
    self.guild_config = guild_config
    self.bot = bot
    self.mod_log_channel = guild_config['mod_log_channel']
    if value=="logs":
      self.add_logs()
    elif value=="automoderation":
      self.automoderation = guild_config['moderation']
      self.moderation_type = guild_config['moderation_type']
      self.add_automoderation_buttons()
    elif value=='AI':
      self.aibot = guild_config['aibot']
      self.add_AI()
    elif value=='games':
      self.word_channel = guild_config['word_channel']
      self.number_channel = guild_config['number_channel']
      self.add_games_buttons()
    self.add_select()

  def add_select(self):
    options = [
      {
        "label": '📘'+translate_to_all_languages("Канал Логов", 'message', self.language),
        "value": "logs",
        "description": translate_to_all_languages("Можете Изменить Текущий Канал Логов.", 'message', self.language)
      },
      {
        "label": '👮‍♂️'+translate_to_all_languages("Автомодерация", 'message', self.language),
        "value": "automoderation",
        "description": translate_to_all_languages("Можешь Выключить/Изменить Тип Автомодерации.", 'message', self.language)
      },
      {
        "label": '🤖'+translate_to_all_languages("AI", 'message', self.language),
        "value": "AI",
        "description": translate_to_all_languages("Если Включить, То Я Смогу Общаться С Вами!", 'message', self.language)
      },
      {
        "label": '🎮'+translate_to_all_languages("Настройки Игр", 'message', self.language),
        "value": "games",
        "description": translate_to_all_languages("Вы Сможете Настроить Здесь Игры.", 'message', self.language)
      }
    ]

    select_menu = Select(
      placeholder='❓'+translate_to_all_languages("Выберите Категорию!", 'message', self.language),
      options=[
        SelectOption(label=opt['label'], description=opt.get('description', ''), value=opt['value'])
        for opt in options
      ]
    )
    select_menu.callback = self.select_callback
    self.add_item(select_menu)

  def add_logs(self):
    self.clear_items()
    channel_id = ChannelSelect(
      placeholder=translate_to_all_languages("Выберите Канал Для Логов", 'message', self.language),
      channel_types=[ChannelType.text]
    )
    channel_id.callback = self.modlogchannel_callback
    self.add_item(channel_id)

  def add_automoderation_buttons(self):
    self.clear_items()
    automoderation_button = Button(
      style=ButtonStyle.success if self.automoderation==False else ButtonStyle.danger,
      emoji="✔" if self.automoderation==False else "❌",
      label=translate_to_all_languages("Enable", 'message', self.language) if self.automoderation==False else translate_to_all_languages("Disable", 'message', self.language)
    )
    automoderation_button.callback = self.automoderationbuttonenable_callback
    self.add_item(automoderation_button)

    automoderationchangemod_button = Button(
      style=ButtonStyle.primary,
      emoji='👮‍♂️',
      label=translate_to_all_languages("AI", 'message', self.language) if self.moderation_type=='AI' else translate_to_all_languages("Algorithm", 'message', self.language)
    )
    automoderationchangemod_button.callback = self.automoderationbuttonchangemod_callback
    self.add_item(automoderationchangemod_button)

    automoderationaddrules_button = Button(
      style=ButtonStyle.primary,
      emoji='📘',
      label=translate_to_all_languages("Rules", 'message', self.language)
    )
    automoderationaddrules_button.callback = self.automoderationbuttonaddrules_callback
    self.add_item(automoderationaddrules_button)

  def add_AI(self):
    self.clear_items()
    AI_button = Button(
      style=ButtonStyle.success if self.aibot==False else ButtonStyle.danger,
      emoji="✔" if self.aibot==False else "❌",
      label=translate_to_all_languages("Enable", 'message', self.language) if self.aibot==False else translate_to_all_languages("Disable", 'message', self.language)
    )
    AI_button.callback = self.AIbuttonenable_callback
    self.add_item(AI_button)

  def add_games_buttons(self):
    self.clear_items()
    word_channel_button = ChannelSelect(
      row=0,
      placeholder='🔤'+translate_to_all_languages("Канал Для Игры В Слова", 'message', self.language)
    )
    word_channel_button.callback = self.wordchannel_callback
    self.add_item(word_channel_button)
    
    words_reset_button = Button(
      row=1,
      style=ButtonStyle.danger,
      emoji="❌",
      label=translate_to_all_languages("Сбросить словарь", 'message', self.language)
    )
    words_reset_button.callback = self.wordsreset_callback
    self.add_item(words_reset_button)

    options = [
      {
        "label": '✅'+translate_to_all_languages("Нормально", 'message', self.language),
        "value": "normal",
        "description": translate_to_all_languages("Легкий Фильтр Который Проверяет Только Базовые Моменты.", 'message', self.language)
      },
      {
        "label": '📛'+translate_to_all_languages("Экстрим", 'message', self.language),
        "value": "extreme",
        "description": translate_to_all_languages("Очень Строгий Фильтр, Большинство Языков Могут Не Поддерживаться.", 'message', self.language)
      }]
    filter_selection = Select(
      row=2,
      placeholder='⛔'+translate_to_all_languages("Выберите Фильтр!", 'message', self.language),
      options=[
        SelectOption(label=opt['label'], description=opt.get('description', ''), value=opt['value'])
        for opt in options
      ]
    )
    filter_selection.callback = self.filter_callback
    self.add_item(filter_selection)

    number_channel_button = ChannelSelect(
      row=3,
      placeholder='🧮'+translate_to_all_languages("Канал Для Игры В Счет", 'message', self.language)
    )
    number_channel_button.callback = self.numberchannel_callback
    self.add_item(number_channel_button)

  async def select_callback(self, interaction: Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    selected_value = interaction.data['values'][0]
    await interaction.response.defer()
    if selected_value:
      await self.update_callback(selected_value)
  
  async def modlogchannel_callback(self,interaction:Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    channel_id:int = int(interaction.data['values'][0])
    data = {
      'mod_log_channel': channel_id
    }
    await (UpdateData(self.bot)).update_data(interaction.guild.id, data, 'guild_settings', 'guild_id', interaction.guild)
    if self.guild_config['mod_log_channel'] and interaction.guild and interaction.guild.get_channel(self.guild_config['mod_log_channel']):
      fields=[{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение До",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':f"{self.guild_config['mod_log_channel']} | <#{self.guild_config['mod_log_channel']}>",
        'inline':True
      },{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение После",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':f"{channel_id} | <#{channel_id}>",
        'inline':True
      }]
      await (SendEmbed(self.bot)).send_embed(
        title=await (TranslateMessage(self.bot)).translate_message("Изменение Конфига Бота",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        description="### "+await (TranslateMessage(self.bot)).translate_message(f"Изменение Канала Логов",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+f"\n**`<#{self.guild_config['mod_log_channel']}>`** "+await (TranslateMessage(self.bot)).translate_message("Заменен На",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+f"\n**`<#{channel_id}>`** ",
        color=Colour.yellow(),
        fields=fields,
        footer_text=await (TranslateMessage(self.bot)).translate_message(f"Изменение Канала Логов",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=channel_id if channel_id else self.guild_config['mod_log_channel']
      )
    await self.update_callback("logs",channel_id)

  async def automoderationbuttonenable_callback(self, interaction:Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    guild_config = await (GetData(self.bot)).get_data(interaction.guild.id,['moderation'],'guild_settings','guild_id',interaction.guild)
    self.automoderation = guild_config['moderation']
    data = {
      'moderation': not self.automoderation
    }
    if self.mod_log_channel and interaction.guild and interaction.guild.get_channel(self.mod_log_channel):
      fields=[{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение До",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':str(self.automoderation),
        'inline':True
      },{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение После",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':str(not self.automoderation),
        'inline':True
      }]
      await (SendEmbed(self.bot)).send_embed(
        title=await (TranslateMessage(self.bot)).translate_message("Изменение Конфига Бота",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        description="### "+await (TranslateMessage(self.bot)).translate_message("Изменение Авто-модерации",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'\n**`'+await (TranslateMessage(self.bot)).translate_message(str(self.automoderation),interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'`** '+await (TranslateMessage(self.bot)).translate_message("Заменен На",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+' **`'+await (TranslateMessage(self.bot)).translate_message(str(not self.automoderation),interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'`**.',
        color=Colour.yellow(),
        fields=fields,
        footer_text=await (TranslateMessage(self.bot)).translate_message("Изменение Авто-модерации",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=self.mod_log_channel
      )
    await (UpdateData(self.bot)).update_data(interaction.guild.id, data, 'guild_settings', 'guild_id', interaction.guild)
    self.automoderation = not self.automoderation
    self.add_automoderation_buttons()
    self.add_select()
    await interaction.edit_original_message(view=self)
    # await interaction.edit_original_message(view=self)
  
  async def automoderationbuttonchangemod_callback(self, interaction:Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    guild_config = await (GetData(self.bot)).get_data(interaction.guild.id,['moderation_type'],'guild_settings','guild_id',interaction.guild)
    self.moderation_type = guild_config['moderation_type']
    data = {
      'moderation_type': 'AI' if self.moderation_type=='normal' else 'normal'
    }
    if self.mod_log_channel and interaction.guild and interaction.guild.get_channel(self.mod_log_channel):
      fields=[{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение До",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':str(self.moderation_type),
        'inline':True
      },{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение После",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':str('AI' if self.moderation_type=='normal' else 'normal'),
        'inline':True
      }]
      await (SendEmbed(self.bot)).send_embed(
        title=await (TranslateMessage(self.bot)).translate_message("Изменение Конфига Бота",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        description="### "+await (TranslateMessage(self.bot)).translate_message("Изменение Авто-модерации",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'\n**`'+await (TranslateMessage(self.bot)).translate_message(str(self.moderation_type),interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'`** '+await (TranslateMessage(self.bot)).translate_message("Заменен На",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+' **`'+await (TranslateMessage(self.bot)).translate_message(str('AI' if self.moderation_type=='normal' else 'normal'),interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'`**.',
        color=Colour.yellow(),
        fields=fields,
        footer_text=await (TranslateMessage(self.bot)).translate_message("Изменение Авто-модерации",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=self.mod_log_channel
      )
    await (UpdateData(self.bot)).update_data(interaction.guild.id, data, 'guild_settings', 'guild_id', interaction.guild)
    self.moderation_type = 'AI' if self.moderation_type=='normal' else 'normal'
    self.add_automoderation_buttons()
    self.add_select()
    await interaction.edit_original_message(view=self)
    # await interaction.edit_original_message(view=self)

  async def automoderationbuttonaddrules_callback(self,interaction:Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.send_modal(rulesmodal(self.user_id,self.language,self.update_callback,self.guild_config,self.bot))

  async def AIbuttonenable_callback(self, interaction:Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    guild_config = await (GetData(self.bot)).get_data(interaction.guild.id,['aibot'],'guild_settings','guild_id',interaction.guild)
    self.aibot = guild_config['aibot']
    data = {
      'aibot': not self.aibot
    }
    if self.mod_log_channel and interaction.guild and interaction.guild.get_channel(self.mod_log_channel):
      fields=[{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение До",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':str(self.aibot),
        'inline':True
      },{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение После",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':str(not self.aibot),
        'inline':True
      }]
      await (SendEmbed(self.bot)).send_embed(
        title=await (TranslateMessage(self.bot)).translate_message("Изменение Конфига Бота",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        description="### "+await (TranslateMessage(self.bot)).translate_message("Изменение ИИ",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'\n**`'+await (TranslateMessage(self.bot)).translate_message(str(self.aibot),interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'`** '+await (TranslateMessage(self.bot)).translate_message("Заменен На",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+' **`'+await (TranslateMessage(self.bot)).translate_message(str(not self.aibot),interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'`**.',
        color=Colour.yellow(),
        fields=fields,
        footer_text=await (TranslateMessage(self.bot)).translate_message("Изменение ИИ",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=self.mod_log_channel
      )
    await (UpdateData(self.bot)).update_data(interaction.guild.id, data, 'guild_settings', 'guild_id', interaction.guild)
    self.aibot = not self.aibot
    self.add_AI()
    self.add_select()
    await interaction.edit_original_message(view=self)
    # await interaction.edit_original_message(view=self)

  async def wordchannel_callback(self,interaction:Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    channel_id:int = int(interaction.data['values'][0])
    data = {
      'word_channel': channel_id
    }
    await (UpdateData(self.bot)).update_data(interaction.guild.id, data, 'guild_settings', 'guild_id', interaction.guild)
    if self.guild_config['word_channel'] and interaction.guild and interaction.guild.get_channel(self.guild_config['word_channel']):
      fields=[{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение До",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':f"{self.guild_config['word_channel']} | <#{self.guild_config['word_channel']}>",
        'inline':True
      },{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение После",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':f"{channel_id} | <#{channel_id}>",
        'inline':True
      }]
      await (SendEmbed(self.bot)).send_embed(
        title=await (TranslateMessage(self.bot)).translate_message("Изменение Конфига Бота",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        description="### "+await (TranslateMessage(self.bot)).translate_message(f"Изменение Канала Для Игры В Слова",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+f"\n**`<#{self.guild_config['word_channel']}>`** "+await (TranslateMessage(self.bot)).translate_message("Заменен На",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+f"\n**`<#{channel_id}>`** ",
        color=Colour.yellow(),
        fields=fields,
        footer_text=await (TranslateMessage(self.bot)).translate_message(f"Изменение Канала Для Игры В Слова",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=channel_id if channel_id else self.guild_config['mod_log_channel']
      )
    await self.update_callback("words",channel_id)
  
  async def numberchannel_callback(self,interaction:Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    channel_id:int = int(interaction.data['values'][0])
    data = {
      'number_channel': channel_id
    }
    await (UpdateData(self.bot)).update_data(interaction.guild.id, data, 'guild_settings', 'guild_id', interaction.guild)
    if self.guild_config['number_channel'] and interaction.guild and interaction.guild.get_channel(self.guild_config['number_channel']):
      fields=[{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение До",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':f"{self.guild_config['number_channel']} | <#{self.guild_config['number_channel']}>",
        'inline':True
      },{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение После",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':f"{channel_id} | <#{channel_id}>",
        'inline':True
      }]
      await (SendEmbed(self.bot)).send_embed(
        title=await (TranslateMessage(self.bot)).translate_message("Изменение Конфига Бота",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        description="### "+await (TranslateMessage(self.bot)).translate_message(f"Изменение Канала Для Игры В Счет",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+f"\n**`<#{self.guild_config['number_channel']}>`** "+await (TranslateMessage(self.bot)).translate_message("Заменен На",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+f"\n**`<#{channel_id}>`** ",
        color=Colour.yellow(),
        fields=fields,
        footer_text=await (TranslateMessage(self.bot)).translate_message(f"Изменение Канала Для Игры В Счет",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=channel_id if channel_id else self.guild_config['mod_log_channel']
      )
    await self.update_callback("numbers",channel_id)
  
  async def wordsreset_callback(self,interaction:Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    guild_config = await (GetData(self.bot)).get_data(interaction.guild.id,['words'],'guild_settings','guild_id',interaction.guild)
    self.words = guild_config['words']
    self.words = str(self.words)[:500]+'...' if len(str(self.words))>=500 else str(self.words)
    data = {
      'words': dumps([])
    }
    if self.mod_log_channel and interaction.guild and interaction.guild.get_channel(self.mod_log_channel):
      fields=[{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение До",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':str(self.words),
        'inline':True
      },{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение После",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':str([]),
        'inline':True
      }]
      await (SendEmbed(self.bot)).send_embed(
        title=await (TranslateMessage(self.bot)).translate_message("Изменение Конфига Бота",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        description="### "+await (TranslateMessage(self.bot)).translate_message("Сброс Словаря",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'\n**`'+await (TranslateMessage(self.bot)).translate_message(str(self.words),interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'`** '+await (TranslateMessage(self.bot)).translate_message("Заменен На",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+' **`'+await (TranslateMessage(self.bot)).translate_message(str([]),interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'`**.',
        color=Colour.yellow(),
        fields=fields,
        footer_text=await (TranslateMessage(self.bot)).translate_message("Сброс Словаря",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=self.mod_log_channel
      )
    await (UpdateData(self.bot)).update_data(interaction.guild.id, data, 'guild_settings', 'guild_id', interaction.guild)
    await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Словарь Сброшен.", self.language),ephemeral=True)

  async def filter_callback(self, interaction: Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    filter = interaction.data['values'][0]
    dataa = await (GetData(self.bot)).get_data(interaction.guild.id,['filter'],'guild_settings','guild_id',interaction.guild)
    old_filter = dataa['filter']
    data = {
      'filter': filter
    }
    if self.mod_log_channel and interaction.guild and interaction.guild.get_channel(self.mod_log_channel):
      fields=[{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение До",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':str(old_filter),
        'inline':True
      },{
        'name':await (TranslateMessage(self.bot)).translate_message("Значение После",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        'value':str(filter),
        'inline':True
      }]
      await (SendEmbed(self.bot)).send_embed(
        title=await (TranslateMessage(self.bot)).translate_message("Изменение Конфига Бота",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        description="### "+await (TranslateMessage(self.bot)).translate_message("Изменение Фильтра Для Игры В Слова",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'\n**`'+await (TranslateMessage(self.bot)).translate_message(str(old_filter),interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'`** '+await (TranslateMessage(self.bot)).translate_message("Заменен На",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+' **`'+await (TranslateMessage(self.bot)).translate_message(str(filter),interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv')+'`**.',
        color=Colour.yellow(),
        fields=fields,
        footer_text=await (TranslateMessage(self.bot)).translate_message("Изменение Фильтра Для Игры В Слова",interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=self.mod_log_channel
      )
    await (UpdateData(self.bot)).update_data(interaction.guild.id, data, 'guild_settings', 'guild_id', interaction.guild)
 

class Config(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
  
  @slash_command(default_member_permissions=8,
  description="Команда Для Настройки Меня.",
  name_localizations=translate_to_all_languages('settings', 'name'),
  description_localizations=translate_to_all_languages('Команда Для Настройки Меня.', 'description'))
  async def настройки(self,interaction: Interaction):
    try:
      if ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://sites.google.com/view/arturwolium/main-page/rules) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
        return
      user_id = interaction.user.id
      current_time = time()

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"You write commands so fast,",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **<t:{round(last_command_time+10)}:R>** "+await (TranslateMessage(self.bot)).translate_message(f"you can write commands.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}
      if interaction.guild:
        guild_settings = await (GetData(self.bot)).get_data(interaction.guild.id,['banned'],'guilds','guild_id',interaction.guild)
      user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation','banned'],'users','user_id',interaction.guild)
      language = user_settings['language']

      if user_settings['banned'] or (guild_settings['banned'] if interaction.guild else False):
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://sites.google.com/view/arturwolium/main-page/rules) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",language), ephemeral=True)
        servers_with_no_acces_for_bot.append(interaction.guild.id)
        users_with_no_acces_for_bot.append(user_id)
        return
      
      await interaction.response.defer(ephemeral=True)

      if not interaction.guild:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Эта команда работает только на серверах.",language), ephemeral=True)
        return
      if not interaction.user.guild_permissions.administrator:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Ты Не Администратор.",language), ephemeral=True)
        return
      
      invite = await (GetInvite(self.bot)).invite(interaction.guild)
      
      guild_config = await (GetData(self.bot)).get_data(interaction.guild.id,['moderation','aibot','moderation_type','mod_log_channel','rules','word_channel','number_channel'],'guild_settings','guild_id',interaction.guild)
      async def update_config(value:str,data=None):
        update_config_embed = Embed(
          title=await (TranslateMessage(self.bot)).translate_message(f"Настройки", language),
          description="### "+await (TranslateMessage(self.bot)).translate_message(f"**Выберите, Что Хотите Изменить Во мне!**", language),
          color=Colour.brand_green(),
          timestamp=datetime.now(timezone.utc)
        )
        update_config_embed.set_author(
          name=interaction.user.name,
          icon_url=interaction.user.display_avatar.url
        )
        if value:
          update_config_embed.description="## "+await (TranslateMessage(self.bot)).translate_message(f"**Вы Выбрали**", language)+f"\n{value}"
          if data:
            if value in['logs','words','numbers']:
              update_config_embed.add_field(
                name=await (TranslateMessage(self.bot)).translate_message("ID Нового Канала",language),
                value=f"<#{str(data)}>"
              )
            if value=='rules':
              update_config_embed.description=(update_config_embed.description+"\n### "+await (TranslateMessage(self.bot)).translate_message("Правила",language)+f"\n{data}")[:3800]
              if len(update_config_embed.description)>=3800:
                update_config_embed.description+="..."
        update_config_embed.set_footer(
          text=value,
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )
        view = конфиг(interaction.user.id, language, update_config, value, guild_config, self.bot)
        await update_config_embed_message.edit(embed=update_config_embed,view=view)
      update_config_embed = Embed(
        title=await (TranslateMessage(self.bot)).translate_message(f"Настройки", language),
        description="### "+await (TranslateMessage(self.bot)).translate_message(f"**Выберите, Что Хотите Изменить Во мне!**", language),
        color=Colour.brand_green(),
        timestamp=datetime.now(timezone.utc)
      )
      update_config_embed.set_author(
        name=interaction.user.name,
        icon_url=interaction.user.display_avatar.url
      )
      view = конфиг(interaction.user.id, language, update_config, None, guild_config, self.bot)
      update_config_embed_message = await interaction.followup.send(embed=update_config_embed,view=view,wait=True)
      await update_config(None)

      fields = [
        {
          'name':'Модератор',
          'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline':True
        },
        {
          'name':'Сервер',
          'value':f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "ЛС",
          'inline':True
        },
        {
          'name':'Канал',
          'value':f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else f'[<@{interaction.user.id}>({interaction.user.id} | {interaction.user.name}({interaction.user.display_name})]'}`)",
          'inline':True
        }
      ]
      await (SendEmbed(self.bot)).send_embed(
        title="Ввод команды",
        description=f"Пользователь ввёл: ||**/{interaction.application_command.name}** {' '.join(f'`{option['name']}` **{option['value']}** ' for option in interaction.data.get('options',[]))}||",
        color=Colour.yellow(),
        fields=fields,
        footer_text=interaction.application_command.name,
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        channel_id=1348577723097808977
      )

    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      fields = [
        {
          'name':'Пользователь',
          'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline':True
        },
        {
          'name':'Сервер',
          'value':f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "ЛС",
          'inline':True
        },
        {
          'name':'Канал',
          'value':f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else f'[<@{interaction.user.id}>({interaction.user.id} | {interaction.user.name}({interaction.user.display_name})]'}`)",
          'inline':True
        },
        {
          'name':'Ошибка',
          'value':traceback_msg,
          'inline':False
        }
      ]
      await (SendEmbed(self.bot)).send_embed(
        title=f"Произошла ошибка при вводе команды /{interaction.application_command.name}",
        description=str(e)[:2048],
        color=Colour.red(),
        fields=fields,
        footer_text=f'Ошибка в cogs.commands.🔧other.help',
        author_text='ЕРРОР',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      await interaction.followup.send(await(TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)

  setattr(настройки,"extras",{"description": "С Помощью Этой Команды Вы Можете На Своем Сервере Полностью Изменить Меня!"})

def setup(bot:commands.Bot):
  bot.add_cog(Config(bot))