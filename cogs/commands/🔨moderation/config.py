from nextcord.ext import commands
from nextcord import TextInputStyle, slash_command, Interaction, Colour, Embed, SelectOption, ButtonStyle, ChannelType
from nextcord.ui import View, Button, Select, Modal, TextInput, ChannelSelect
from datetime import datetime, timezone
from time import time
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from Utils.discord_locale import locale
from traceback import format_exception
from json import dumps

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class rulesmodal(Modal):
  def __init__(self, user_id: int, language: str, update_callback, guild_config: dict, bot: commands.Bot, timeout=60*5):
    super().__init__(title=translate_to_all_languages("Введите Правила", 'message', language), timeout=timeout)
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
      default_value=guild_config.get('rules') or '',
      placeholder=translate_to_all_languages("Правила Которые Нейросеть Будет Использовать При Сканировании Сообщений Пользователей.", 'message', language)
    )
    self.add_item(self.rules)

  async def callback(self, interaction: Interaction):
    if interaction.user.id != self.user_id:
      return
    if not interaction.guild:
      return
    if not interaction.user.guild_permissions.administrator:
      tm = self.bot.get_cog("TranslateMessage")
      if tm:
        await interaction.response.send_message(await tm.translate_message("Ты Не Администратор.", self.language), ephemeral=True)
      return
    if interaction.response.is_done():
      return

    await interaction.response.defer()
    rules = (self.rules.value or '').strip()
    if not rules:
      tm = self.bot.get_cog("TranslateMessage")
      if tm:
        await interaction.followup.send(await tm.translate_message("Вы Ничего Не Вписали.", self.language), ephemeral=True)
      return

    ud = self.bot.get_cog("UpdateData")
    if ud:
      await ud.update_data(interaction.guild.id, {'rules': rules}, 'guild_settings', 'guild_id', interaction.guild)

    mod_log_channel = self.guild_config.get('mod_log_channel')
    if mod_log_channel and interaction.guild.get_channel(mod_log_channel):
      tm = self.bot.get_cog("TranslateMessage")
      se = self.bot.get_cog("SendEmbed")
      if tm and se:
        gl = locale(interaction.guild_locale)
        await se.send_embed(
          title=await tm.translate_message("Изменение Конфига Бота", gl),
          description="### " + await tm.translate_message("Изменение Правил Для Автомодерации\nТак Как Правила Могут Превышать Лимит Максимального Размера Файла В Дискорде, То Показать Изменения Я Не Согу.", gl),
          color=Colour.yellow(),
          fields=None,
          footer_text=await tm.translate_message("Изменение Правил Для Автомодерации", gl),
          author_text=interaction.user.name,
          author_icon=interaction.user.display_avatar.url,
          guild_id=interaction.guild.id,
          channel_id=mod_log_channel
        )

    await self.update_callback("automoderation", translate_to_all_languages("Rules saved", "message", self.language))


class конфиг(View):
  def __init__(self, user_id: int, language: str, update_callback, value: str, guild_config: dict, bot: commands.Bot, timeout=60*30):
    super().__init__(timeout=timeout)
    self.language = language
    self.user_id = user_id
    self.update_callback = update_callback
    self.guild_config = guild_config
    self.bot = bot
    self.mod_log_channel = guild_config.get('mod_log_channel')

    if value == "logs":
      self.add_logs()
    elif value == "automoderation":
      self.automoderation = bool(guild_config.get('moderation'))
      self.moderation_type = guild_config.get('moderation_type') or 'normal'
      self.add_automoderation_buttons()
    elif value == 'AI':
      self.aibot = bool(guild_config.get('aibot'))
      self.add_AI()
    elif value == 'games':
      self.word_channel = guild_config.get('word_channel')
      self.number_channel = guild_config.get('number_channel')
      self.add_games_buttons()
    elif value == 'updates':
      self.news = bool(guild_config.get('news'))
      self.important = bool(guild_config.get('important'))
      self.news_channel = guild_config.get('news_channel')
      self.important_channel = guild_config.get('important_channel')
      self.critical_channel = guild_config.get('critical_channel')
      self.add_updates_buttons()

    self.add_select()

  def add_select(self):
    options = [
      {
        "label": '📘' + translate_to_all_languages("Канал Логов", 'message', self.language),
        "value": "logs",
        "description": translate_to_all_languages("Можете Изменить Текущий Канал Логов.", 'message', self.language)
      },
      {
        "label": '👮‍♂️' + translate_to_all_languages("Автомодерация", 'message', self.language),
        "value": "automoderation",
        "description": translate_to_all_languages("Можешь Выключить/Изменить Тип Автомодерации.", 'message', self.language)
      },
      {
        "label": '🤖' + translate_to_all_languages("AI", 'message', self.language),
        "value": "AI",
        "description": translate_to_all_languages("Если Включить, То Я Смогу Общаться С Вами!", 'message', self.language)
      },
      {
        "label": '🎮' + translate_to_all_languages("Настройки Игр", 'message', self.language),
        "value": "games",
        "description": translate_to_all_languages("Вы Сможете Настроить Здесь Игры.", 'message', self.language)
      },
      {
        "label": '📰' + translate_to_all_languages("Уведомления", 'message', self.language),
        "value": "updates",
        "description": translate_to_all_languages("Настройка News/Important/Critical уведомлений.", 'message', self.language)
      }
    ]

    select_menu = Select(
      placeholder='❓' + translate_to_all_languages("Выберите Категорию!", 'message', self.language),
      options=[
        SelectOption(label=opt['label'], description=opt.get('description', ''), value=opt['value'])
        for opt in options
      ]
    )
    select_menu.callback = self.select_callback
    self.add_item(select_menu)

  async def guard(self, interaction: Interaction) -> bool:
    if interaction.user.id != self.user_id:
      return False
    if not interaction.guild:
      return False
    if not interaction.user.guild_permissions.administrator:
      tm = self.bot.get_cog("TranslateMessage")
      if tm and not interaction.response.is_done():
        await interaction.response.send_message(await tm.translate_message("Ты Не Администратор.", self.language), ephemeral=True)
      return False
    return True

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
      style=ButtonStyle.success if self.automoderation == False else ButtonStyle.danger,
      emoji="✔" if self.automoderation == False else "❌",
      label=translate_to_all_languages("Enable", 'message', self.language) if self.automoderation == False else translate_to_all_languages("Disable", 'message', self.language)
    )
    automoderation_button.callback = self.automoderationbuttonenable_callback
    self.add_item(automoderation_button)

    automoderationchangemod_button = Button(
      style=ButtonStyle.primary,
      emoji='👮‍♂️',
      label=translate_to_all_languages("AI", 'message', self.language) if self.moderation_type == 'AI' else translate_to_all_languages("Algorithm", 'message', self.language)
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
      style=ButtonStyle.success if self.aibot == False else ButtonStyle.danger,
      emoji="✔" if self.aibot == False else "❌",
      label=translate_to_all_languages("Enable", 'message', self.language) if self.aibot == False else translate_to_all_languages("Disable", 'message', self.language)
    )
    AI_button.callback = self.AIbuttonenable_callback
    self.add_item(AI_button)

  def add_games_buttons(self):
    self.clear_items()
    word_channel_button = ChannelSelect(
      row=0,
      placeholder='🔤' + translate_to_all_languages("Канал Для Игры В Слова", 'message', self.language),
      channel_types=[ChannelType.text]
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
        "label": '✅' + translate_to_all_languages("Нормально", 'message', self.language),
        "value": "normal",
        "description": translate_to_all_languages("Легкий Фильтр Который Проверяет Только Базовые Моменты.", 'message', self.language)
      },
      {
        "label": '📛' + translate_to_all_languages("Экстрим", 'message', self.language),
        "value": "extreme",
        "description": translate_to_all_languages("Очень Строгий Фильтр, Большинство Языков Могут Не Поддерживаться.", 'message', self.language)
      }
    ]
    filter_selection = Select(
      row=2,
      placeholder='⛔' + translate_to_all_languages("Выберите Фильтр!", 'message', self.language),
      options=[
        SelectOption(label=opt['label'], description=opt.get('description', ''), value=opt['value'])
        for opt in options
      ]
    )
    filter_selection.callback = self.filter_callback
    self.add_item(filter_selection)

    number_channel_button = ChannelSelect(
      row=3,
      placeholder='🧮' + translate_to_all_languages("Канал Для Игры В Счет", 'message', self.language),
      channel_types=[ChannelType.text]
    )
    number_channel_button.callback = self.numberchannel_callback
    self.add_item(number_channel_button)

  def add_updates_buttons(self):
    self.clear_items()

    news_toggle = Button(
      row=0,
      style=ButtonStyle.danger if self.news else ButtonStyle.success,
      emoji="❌" if self.news else "✔",
      label=translate_to_all_languages("Disable News", 'message', self.language) if self.news else translate_to_all_languages("Enable News", 'message', self.language)
    )
    news_toggle.callback = self.newstoggle_callback
    self.add_item(news_toggle)

    important_toggle = Button(
      row=0,
      style=ButtonStyle.danger if self.important else ButtonStyle.success,
      emoji="❌" if self.important else "✔",
      label=translate_to_all_languages("Disable Important", 'message', self.language) if self.important else translate_to_all_languages("Enable Important", 'message', self.language)
    )
    important_toggle.callback = self.importanttoggle_callback
    self.add_item(important_toggle)

    critical_label = Button(
      row=0,
      style=ButtonStyle.secondary,
      emoji="🚨",
      label=translate_to_all_languages("Critical всегда включен", 'message', self.language),
      disabled=True
    )
    self.add_item(critical_label)

    news_channel_select = ChannelSelect(
      row=1,
      placeholder='📰 ' + translate_to_all_languages("Канал News", 'message', self.language),
      channel_types=[ChannelType.text]
    )
    news_channel_select.callback = self.newschannel_callback
    self.add_item(news_channel_select)

    important_channel_select = ChannelSelect(
      row=2,
      placeholder='⭐ ' + translate_to_all_languages("Канал Important", 'message', self.language),
      channel_types=[ChannelType.text]
    )
    important_channel_select.callback = self.importantchannel_callback
    self.add_item(important_channel_select)

    critical_channel_select = ChannelSelect(
      row=3,
      placeholder='🚨 ' + translate_to_all_languages("Канал Critical", 'message', self.language),
      channel_types=[ChannelType.text]
    )
    critical_channel_select.callback = self.criticalchannel_callback
    self.add_item(critical_channel_select)

  async def select_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    selected_value = interaction.data['values'][0]
    await interaction.response.defer()
    if selected_value:
      await self.update_callback(selected_value)

  async def modlogchannel_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    channel_id = int(interaction.data['values'][0])

    gd = self.bot.get_cog("GetData")
    ud = self.bot.get_cog("UpdateData")
    tm = self.bot.get_cog("TranslateMessage")
    se = self.bot.get_cog("SendEmbed")

    old = None
    if gd:
      dataa = await gd.get_data(interaction.guild.id, ['mod_log_channel'], 'guild_settings', 'guild_id', interaction.guild)
      old = dataa.get('mod_log_channel')

    if ud:
      await ud.update_data(interaction.guild.id, {'mod_log_channel': channel_id}, 'guild_settings', 'guild_id', interaction.guild)

    if old and interaction.guild.get_channel(old) and tm and se:
      gl = locale(interaction.guild_locale)
      fields = [{
        'name': await tm.translate_message("Значение До", gl),
        'value': f"{old} | <#{old}>",
        'inline': True
      }, {
        'name': await tm.translate_message("Значение После", gl),
        'value': f"{channel_id} | <#{channel_id}>",
        'inline': True
      }]
      await se.send_embed(
        title=await tm.translate_message("Изменение Конфига Бота", gl),
        description="### " + await tm.translate_message("Изменение Канала Логов", gl),
        color=Colour.yellow(),
        fields=fields,
        footer_text=await tm.translate_message("Изменение Канала Логов", gl),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=channel_id
      )

    await self.update_callback("logs", f"<#{channel_id}>")

  async def automoderationbuttonenable_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    gd = self.bot.get_cog("GetData")
    ud = self.bot.get_cog("UpdateData")
    tm = self.bot.get_cog("TranslateMessage")
    se = self.bot.get_cog("SendEmbed")

    cfg = {}
    if gd:
      cfg = await gd.get_data(interaction.guild.id, ['moderation', 'mod_log_channel'], 'guild_settings', 'guild_id', interaction.guild)
    old_val = bool(cfg.get('moderation'))
    new_val = not old_val
    mod_log = cfg.get('mod_log_channel')

    if ud:
      await ud.update_data(interaction.guild.id, {'moderation': new_val}, 'guild_settings', 'guild_id', interaction.guild)

    if mod_log and interaction.guild.get_channel(mod_log) and tm and se:
      gl = locale(interaction.guild_locale)
      fields = [{
        'name': await tm.translate_message("Значение До", gl),
        'value': str(old_val),
        'inline': True
      }, {
        'name': await tm.translate_message("Значение После", gl),
        'value': str(new_val),
        'inline': True
      }]
      await se.send_embed(
        title=await tm.translate_message("Изменение Конфига Бота", gl),
        description="### " + await tm.translate_message("Изменение Авто-модерации", gl),
        color=Colour.yellow(),
        fields=fields,
        footer_text=await tm.translate_message("Изменение Авто-модерации", gl),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=mod_log
      )

    await self.update_callback("automoderation", translate_to_all_languages("Toggled", "message", self.language))

  async def automoderationbuttonchangemod_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    gd = self.bot.get_cog("GetData")
    ud = self.bot.get_cog("UpdateData")
    tm = self.bot.get_cog("TranslateMessage")
    se = self.bot.get_cog("SendEmbed")

    cfg = {}
    if gd:
      cfg = await gd.get_data(interaction.guild.id, ['moderation_type', 'mod_log_channel'], 'guild_settings', 'guild_id', interaction.guild)
    old_type = cfg.get('moderation_type') or 'normal'
    new_type = 'AI' if old_type == 'normal' else 'normal'
    mod_log = cfg.get('mod_log_channel')

    if ud:
      await ud.update_data(interaction.guild.id, {'moderation_type': new_type}, 'guild_settings', 'guild_id', interaction.guild)

    if mod_log and interaction.guild.get_channel(mod_log) and tm and se:
      gl = locale(interaction.guild_locale)
      fields = [{
        'name': await tm.translate_message("Значение До", gl),
        'value': str(old_type),
        'inline': True
      }, {
        'name': await tm.translate_message("Значение После", gl),
        'value': str(new_type),
        'inline': True
      }]
      await se.send_embed(
        title=await tm.translate_message("Изменение Конфига Бота", gl),
        description="### " + await tm.translate_message("Изменение Авто-модерации", gl),
        color=Colour.yellow(),
        fields=fields,
        footer_text=await tm.translate_message("Изменение Авто-модерации", gl),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=mod_log
      )

    await self.update_callback("automoderation", translate_to_all_languages("Changed type", "message", self.language))

  async def automoderationbuttonaddrules_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.send_modal(rulesmodal(self.user_id, self.language, self.update_callback, self.guild_config, self.bot))

  async def AIbuttonenable_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    gd = self.bot.get_cog("GetData")
    ud = self.bot.get_cog("UpdateData")
    tm = self.bot.get_cog("TranslateMessage")
    se = self.bot.get_cog("SendEmbed")

    cfg = {}
    if gd:
      cfg = await gd.get_data(interaction.guild.id, ['aibot', 'mod_log_channel'], 'guild_settings', 'guild_id', interaction.guild)
    old_val = bool(cfg.get('aibot'))
    new_val = not old_val
    mod_log = cfg.get('mod_log_channel')

    if ud:
      await ud.update_data(interaction.guild.id, {'aibot': new_val}, 'guild_settings', 'guild_id', interaction.guild)

    if mod_log and interaction.guild.get_channel(mod_log) and tm and se:
      gl = locale(interaction.guild_locale)
      fields = [{
        'name': await tm.translate_message("Значение До", gl),
        'value': str(old_val),
        'inline': True
      }, {
        'name': await tm.translate_message("Значение После", gl),
        'value': str(new_val),
        'inline': True
      }]
      await se.send_embed(
        title=await tm.translate_message("Изменение Конфига Бота", gl),
        description="### " + await tm.translate_message("Изменение ИИ", gl),
        color=Colour.yellow(),
        fields=fields,
        footer_text=await tm.translate_message("Изменение ИИ", gl),
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        guild_id=interaction.guild.id,
        channel_id=mod_log
      )

    await self.update_callback("AI", translate_to_all_languages("Toggled", "message", self.language))

  async def wordchannel_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    channel_id = int(interaction.data['values'][0])

    ud = self.bot.get_cog("UpdateData")
    if ud:
      await ud.update_data(interaction.guild.id, {'word_channel': channel_id}, 'guild_settings', 'guild_id', interaction.guild)

    await self.update_callback("games", f"word_channel: <#{channel_id}>")

  async def numberchannel_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    channel_id = int(interaction.data['values'][0])

    ud = self.bot.get_cog("UpdateData")
    if ud:
      await ud.update_data(interaction.guild.id, {'number_channel': channel_id}, 'guild_settings', 'guild_id', interaction.guild)

    await self.update_callback("games", f"number_channel: <#{channel_id}>")

  async def wordsreset_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    ud = self.bot.get_cog("UpdateData")
    if ud:
      await ud.update_data(interaction.guild.id, {'words': dumps([])}, 'guild_settings', 'guild_id', interaction.guild)

    tm = self.bot.get_cog("TranslateMessage")
    if tm:
      await interaction.followup.send(await tm.translate_message("Словарь Сброшен.", self.language), ephemeral=True)

    await self.update_callback("games", translate_to_all_languages("Words reset", "message", self.language))

  async def filter_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    filt = interaction.data['values'][0]

    ud = self.bot.get_cog("UpdateData")
    if ud:
      await ud.update_data(interaction.guild.id, {'filter': filt}, 'guild_settings', 'guild_id', interaction.guild)

    await self.update_callback("games", f"filter: `{filt}`")

  async def newstoggle_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    gd = self.bot.get_cog("GetData")
    ud = self.bot.get_cog("UpdateData")

    cfg = {}
    if gd:
      cfg = await gd.get_data(interaction.guild.id, ['news'], 'guild_settings', 'guild_id', interaction.guild)
    old_val = bool(cfg.get('news'))
    new_val = not old_val

    if ud:
      await ud.update_data(interaction.guild.id, {'news': new_val}, 'guild_settings', 'guild_id', interaction.guild)

    await self.update_callback("updates", f"news: `{new_val}`")

  async def importanttoggle_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    gd = self.bot.get_cog("GetData")
    ud = self.bot.get_cog("UpdateData")

    cfg = {}
    if gd:
      cfg = await gd.get_data(interaction.guild.id, ['important'], 'guild_settings', 'guild_id', interaction.guild)
    old_val = bool(cfg.get('important'))
    new_val = not old_val

    if ud:
      await ud.update_data(interaction.guild.id, {'important': new_val}, 'guild_settings', 'guild_id', interaction.guild)

    await self.update_callback("updates", f"important: `{new_val}`")

  async def newschannel_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    channel_id = int(interaction.data['values'][0])

    ud = self.bot.get_cog("UpdateData")
    if ud:
      await ud.update_data(interaction.guild.id, {'news_channel': channel_id}, 'guild_settings', 'guild_id', interaction.guild)

    await self.update_callback("updates", f"news_channel: <#{channel_id}>")

  async def importantchannel_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    channel_id = int(interaction.data['values'][0])

    ud = self.bot.get_cog("UpdateData")
    if ud:
      await ud.update_data(interaction.guild.id, {'important_channel': channel_id}, 'guild_settings', 'guild_id', interaction.guild)

    await self.update_callback("updates", f"important_channel: <#{channel_id}>")

  async def criticalchannel_callback(self, interaction: Interaction):
    if not await self.guard(interaction):
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    channel_id = int(interaction.data['values'][0])

    ud = self.bot.get_cog("UpdateData")
    if ud:
      await ud.update_data(interaction.guild.id, {'critical_channel': channel_id}, 'guild_settings', 'guild_id', interaction.guild)

    await self.update_callback("updates", f"critical_channel: <#{channel_id}>")


class Config(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @slash_command(
    default_member_permissions=8,
    description="Команда Для Настройки Меня.",
    name_localizations=translate_to_all_languages('settings', 'name'),
    description_localizations=translate_to_all_languages('Команда Для Настройки Меня.', 'description')
  )
  async def настройки(self, interaction: Interaction):
    try:
      user_id = interaction.user.id
      current_time = time()

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          tm = self.bot.get_cog("TranslateMessage")
          if tm:
            ul = locale(interaction.locale)
            await interaction.response.send_message(
              await tm.translate_message("You write commands so fast,", ul) + f" **<t:{round(last_command_time+10)}:R>** " + await tm.translate_message("you can write commands.", ul),
              ephemeral=True
            )
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      gd = self.bot.get_cog("GetData")
      tm = self.bot.get_cog("TranslateMessage")
      gi = self.bot.get_cog("GetInvite")

      user_settings = {}
      if gd:
        user_settings = await gd.get_data(user_id, ['language', 'variation'], 'users', 'user_id', interaction.guild)
      language = user_settings.get('language') or 'en'

      await interaction.response.defer(ephemeral=True)

      if not interaction.guild:
        if tm:
          await interaction.followup.send(await tm.translate_message("Эта команда работает только на серверах.", language), ephemeral=True)
        return
      if not interaction.user.guild_permissions.administrator:
        if tm:
          await interaction.followup.send(await tm.translate_message("Ты Не Администратор.", language), ephemeral=True)
        return

      invite = None
      if gi:
        invite = await gi.invite(interaction.guild)

      async def update_config(value: str, data=None):
        gd2 = self.bot.get_cog("GetData")
        cfg = {}
        if gd2:
          cfg = await gd2.get_data(
            interaction.guild.id,
            ['moderation', 'aibot', 'moderation_type', 'mod_log_channel', 'rules', 'word_channel', 'number_channel', 'filter',
             'news_channel', 'important_channel', 'critical_channel', 'news', 'important'],
            'guild_settings',
            'guild_id',
            interaction.guild
          )

        update_config_embed = Embed(
          title=await tm.translate_message("Настройки", language) if tm else "Настройки",
          description="### " + (await tm.translate_message("**Выберите, Что Хотите Изменить Во мне!**", language) if tm else "**Выберите, Что Хотите Изменить Во мне!**"),
          color=Colour.brand_green(),
          timestamp=datetime.now(timezone.utc)
        )
        update_config_embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)

        if value:
          update_config_embed.description = "## " + (await tm.translate_message("**Вы Выбрали**", language) if tm else "**Вы Выбрали**") + f"\n{value}"

        if data:
          update_config_embed.add_field(
            name=await tm.translate_message("Изменено", language) if tm else "Изменено",
            value=str(data)[:1024],
            inline=False
          )

        view = конфиг(interaction.user.id, language, update_config, value, cfg, self.bot)
        await update_config_embed_message.edit(embed=update_config_embed, view=view)

      update_config_embed = Embed(
        title=await tm.translate_message("Настройки", language) if tm else "Настройки",
        description="### " + (await tm.translate_message("**Выберите, Что Хотите Изменить Во мне!**", language) if tm else "**Выберите, Что Хотите Изменить Во мне!**"),
        color=Colour.brand_green(),
        timestamp=datetime.now(timezone.utc)
      )
      update_config_embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)

      cfg0 = {}
      if gd:
        cfg0 = await gd.get_data(
          interaction.guild.id,
          ['moderation', 'aibot', 'moderation_type', 'mod_log_channel', 'rules', 'word_channel', 'number_channel', 'filter',
           'news_channel', 'important_channel', 'critical_channel', 'news', 'important'],
          'guild_settings',
          'guild_id',
          interaction.guild
        )

      view = конфиг(interaction.user.id, language, update_config, None, cfg0, self.bot)
      update_config_embed_message = await interaction.followup.send(embed=update_config_embed, view=view, wait=True)
      await update_config(None)

    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      fields = [
        {
          'name': 'Пользователь',
          'value': f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline': True
        },
        {
          'name': 'Сервер',
          'value': f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "ЛС",
          'inline': True
        },
        {
          'name': 'Канал',
          'value': f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'DM'}`)",
          'inline': True
        },
        {
          'name': 'Ошибка',
          'value': traceback_msg,
          'inline': False
        }
      ]
      se = self.bot.get_cog("SendEmbed")
      if se:
        await se.send_embed(
          title=f"Произошла ошибка при вводе команды /{interaction.application_command.name}",
          description=str(e)[:2048],
          color=Colour.red(),
          fields=fields,
          footer_text='Ошибка в cogs.commands.🔧other.config',
          author_text='ERROR',
          author_icon=interaction.user.display_avatar.url,
          channel_id=1159138280651104256
        )
      tm = self.bot.get_cog("TranslateMessage")
      if tm:
        ul = locale(interaction.locale)
        await interaction.followup.send(await tm.translate_message("Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ul), ephemeral=True)

  setattr(настройки, "extras", {"description": "С Помощью Этой Команды Вы Можете На Своем Сервере Полностью Изменить Меня!"})


def setup(bot: commands.Bot):
  bot.add_cog(Config(bot))
