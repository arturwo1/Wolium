from datetime import datetime, timezone
from nextcord import Embed, IntegrationType, InteractionContextType, slash_command, Interaction, Color, ButtonStyle, SelectOption, WebhookMessage
from nextcord.ui import View, Button, Select
from nextcord.ext import commands
import Utils.translate_to_all_languages
from time import time
from cogs.utils.get_invite import GetInvite
from cogs.utils.translate_message import TranslateMessage
from Utils.config import slash_command_cooldown
from traceback import format_exception
from cogs.utils.send_embed import SendEmbed
from cogs.utils.get_data import GetData
from os import sep

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class помощь_меню(View):
  def __init__(self, user_id:int, language:str, update_callback, selected_value:str, max_page:int, commandss:dict[str,dict[str,str]], timeout=60*5):
    super().__init__(timeout=timeout)
    self.language = language
    self.user_id = user_id
    self.update_callback = update_callback
    self.page = 0
    self.max_page = max_page
    self.commands = commandss
    self.selected_value = selected_value

    cogs = []
    for _, keys in self.commands.items():
      category = keys['path'].split('.')[-2]
      if category not in cogs:
        cogs.append(category)
    
    options:list[dict[str,str]] = []
    for cog in cogs:
      options.append({
        "label": cog,
        "value": cog
      })
    options.append({
      "label": '📚'+translate_to_all_languages("About",'message',language),
      "value": "about",
      "description": translate_to_all_languages("Информация Обо Мне",'message',language)
    })
    options.append({
      "label": '📘'+translate_to_all_languages("ToS and Privacy Policy",'message',language),
      "value": "tospp",
      "description": translate_to_all_languages("Мои Правила И Политики Которые Нужно Обязательно прочитать!",'message',language)
    })
    options.append({
      "label": '📖'+translate_to_all_languages("FAQ",'message',language),
      "value": "faq",
      "description": translate_to_all_languages("Ответы На Возможно Частые Вопросы.",'message',language)
    })
    options.append({
      "label": '🧮'+translate_to_all_languages("Формулы",'message',language),
      "value": "formules",
      "description": translate_to_all_languages("Как Идут Подсчеты В Экономике",'message',language)
    })
    # print(cogs, commands, options)

    select_menu = Select(
      row=0,
      placeholder="🌍"+translate_to_all_languages("Выберите Категорию", 'message', language),
      options=[
        SelectOption(label=opt['label'], description=opt.get('description', None), value=opt['value'])
        for opt in options
      ]
    )
    select_menu.callback = self.select_callback
    self.add_item(select_menu)

    back_button = Button(
      style=ButtonStyle.primary,
      label="◀",
      row=1,
      disabled=False if self.page > 0 else True
    )
    back_button.callback = self.button1_callback
    self.add_item(back_button)

    forward_button = Button(
      style=ButtonStyle.primary,
      label="▶",
      row=1,
      disabled=False if self.page < self.max_page else True
    )
    forward_button.callback = self.button2_callback
    self.add_item(forward_button)

  async def select_callback(self, interaction: Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    self.selected_value = interaction.data['values'][0]
    need_commands: dict[str,dict[str,str]] = {}
    for command, keys in self.commands.items():
      if self.selected_value not in keys['path']:
        continue
      # print('allow\n')
      need_commands[command] = keys
    self.max_page = (len(need_commands) - 1) // 5

    await self.update_callback(self.selected_value, self.page, self.max_page, need_commands)
  
  async def button1_callback(self, interaction: Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if self.page > 0:
      self.page -= 1
      await self.update_callback(self.selected_value, self.page, self.max_page, self.commands)

  async def button2_callback(self, interaction: Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if self.page < self.max_page:
      self.page += 1
      await self.update_callback(self.selected_value, self.page, self.max_page, self.commands)

class Help(commands.Cog):
  def __init__(self,bot):
    self.bot:commands.Bot = bot
  
  @slash_command(
    description="Абсолютно всё обо мне.",
    name_localizations=translate_to_all_languages('помощь', 'name'),
    description_localizations=translate_to_all_languages('Абсолютно всё обо мне.', 'description'),
    force_global=True,
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],)
  async def помощь(self,interaction: Interaction):
    try:
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

      user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']
      
      await interaction.response.defer(ephemeral=True)

      invite = await (GetInvite(self.bot)).invite(interaction.guild)

      async def send_help_message(selected_value:str, page:int, max_page:int, commands:dict[str,dict[str,str]]):
        help_embed = Embed(
          title=await (TranslateMessage(self.bot)).translate_message("Помощь",language),
          description='### '+await (TranslateMessage(self.bot)).translate_message("Вся Информация Обо Мне Здесь!",language),
          color=Color.dark_teal(),
          timestamp=datetime.now(timezone.utc)
        )
        help_embed.set_author(
          name=interaction.user.name,
          icon_url=interaction.user.display_avatar.url
        )
        help_embed.set_footer(
          text=await (TranslateMessage(self.bot)).translate_message("Помощь",language)
        )
        # print('этап 3')
        # print(commands)
        # print('')
        if commands:
          start_index = page * 5
          end_index = min(start_index + 5, len(commands))
          for rank, (command, keys) in enumerate(list(commands.items())[start_index:end_index], start=start_index + 1):
            path = keys['path']
            if selected_value not in help_embed.description:
              help_embed.description = "### **"+await (TranslateMessage(self.bot)).translate_message("Вся Информация Обо Мне Здесь!",language)+f" | *{selected_value}***"
            # print(selected_value)
            # print(path)
            if selected_value not in path:
              # print('dont allow')
              continue
            # print('entered')
            description = keys['description']
            try:
              help_embed.add_field(
                name=f'#{rank} '+await (TranslateMessage(self.bot)).translate_message(command,language),
                value=await (TranslateMessage(self.bot)).translate_message(description,language),
                inline=False
              )
            except Exception:
              help_embed.add_field(
                name=f'#{rank}'+await (TranslateMessage(self.bot)).translate_message(str(command),language),
                value=await (TranslateMessage(self.bot)).translate_message("Нет Описания.",language),
                inline=False
              )
            help_embed.set_footer(
              text=await (TranslateMessage(self.bot)).translate_message("Помощь",language)+" | "+await (TranslateMessage(self.bot)).translate_message(f"{page+1}/{max_page+1} | {selected_value}",language,save=False)
            )
            await helper.edit(content=None,embed=help_embed)
        elif selected_value=='about':
          help_embed.description = await (TranslateMessage(self.bot)).translate_message("""
            # **Особенности**:
            ### **1**. *🤖Встроенный ИИ, С Доступом К Интернету.*
            ### **2**. *💥Множество Абсолютно Разных Команд.*
            ### **3**. *💹Развитая+Глобальная Экономика, Которая Может Быть Интегрирована К Каждому Дискорд Серверу.*
            ### **5**. *🎈Вдохновлен Многими Популярными Ботами В Дискорде.*
            ### **6**. *👀Всегда Развивается И Максимально Прислушивается К Комьюнити.*
            ### **7**. *💬Встроенная Поддержка Абсолютно Всех Языков Дискорда Практически Во Всех Командах.*
            ### **8**. *✅Возможность Узнать В Любом Стиле Свою Активность.*
            ### **9**. *📰Есть Разнообразные Квесты.*
            ### **10**. *🎇Интегрированность На Разных Платформах **В будущем**.*
            ### **11**. *📊Поддержка Различных Статистик И Графиков.*
            ### **12**. *🎵Музыкальные Команды С Поддержкой YouTube И Локальных Файлов.*
            ### **13**. *🛠️Инструменты Для Разработчиков И Администраторов.*
            ### **14**. *🔒Безопасность И Конфиденциальность.*
            ### **15**. *🌐Поддержка Многоязычности И Локализации.*
            ### **16**. *📅Автоматическое Обновление И Добавление Новых Функций.*
            ### **17**. *🧩Интеграция С Различными API И Сервисами.*
            ### **18**. *📚Документация И Руководства Для Пользователей.*
            ### **19**. *🎮Игровые Команды И Мини-Игры.*
            ### **20**. *📈Мониторинг И Аналитика Использования Бота.*
            # **Другое**:""", language)+f"""
            ### **🔗[`{await (TranslateMessage(self.bot)).translate_message('Сервер Поддержки Бота', language)}`](https://discord.gg/DhtQr4PGYM)**  |  **🔗[`{await (TranslateMessage(self.bot)).translate_message('Сервер Разработчика', language)}`](https://discord.gg/MXupeAApza)**  |  **🔗[`{await (TranslateMessage(self.bot)).translate_message('Сайт Бота', language)}`](https://wolium.netlify.app/)**  |  **🔗[`{await (TranslateMessage(self.bot)).translate_message('Поддержать', language)}`](https://www.patreon.com/arturwol)**
            """
        elif selected_value=='tospp':
          help_embed.description = f"### **[`{await (TranslateMessage(self.bot)).translate_message('Terms of Service',language)}`](https://wolium.netlify.app/terms-of-service/), [`{await (TranslateMessage(self.bot)).translate_message('Privacy Policy',language)}`](https://wolium.netlify.app/privacy-policy/) {await (TranslateMessage(self.bot)).translate_message('and for bot users',language)} [`{await (TranslateMessage(self.bot)).translate_message('Rules',language)}`](https://wolium.netlify.app/rules/)**"
        elif selected_value=='faq':
          help_embed.description = await (TranslateMessage(self.bot)).translate_message("""
            # **Часто Задаваемые Вопросы**:
            ## **1**. ***ИИ Не Отвечает Или Пишет None.***
            ### **Сервера Нейросети Выключены/Закончились Токены/Другая Ошибка, Если После 3-5 Раз Нейросеть Не Ответила/Написала None То Скорее Всего Закончились Токены, Нужно Будет Будет Ждать Начала Следующего Месяца.**
            ## **2**. ***Где Узнать ID Канала?***
            ### > 1. **Перейдите В Настройки Дискорда.**
            ### > 2. **Во Вкладке `Настройки приложения` Нажмите `Расширенные`.**
            ### > 3. **Включите `Режит разработчика`.**
            ### > 4. **ПКМ По Каналу > `Скопировать ID канала`.**
            """, language)
        elif selected_value=='formules':
          help_embed.description = "### **"+await (TranslateMessage(self.bot)).translate_message("Вся Информация Обо Мне Здесь!",language)+f" | *{selected_value}***"
          # (от **`9.26`** до **`13.98`**) `*` (**`3.5`** `*` **`улучшение`**) `*` (**`2`** если увеличение включен, иначе **`1`**) `*` (**`1.5`** если голосовал за бота, иначе **`1`**)
          help_embed.add_field(
            name='/'+await (TranslateMessage(self.bot)).translate_message("работать",language),
            value='('+await (TranslateMessage(self.bot)).translate_message("От",language)+' **`9.26`** '+await (TranslateMessage(self.bot)).translate_message("До",language)+' **`13.98`**) `*` (**`3.5`** `*` **`'+await (TranslateMessage(self.bot)).translate_message("Upgrade",language)+'`**) `*` (**`2`** '+await (TranslateMessage(self.bot)).translate_message("Если увеличение Включен, иначе",language)+' **`1`**) `*` (**`1.5`** '+await (TranslateMessage(self.bot)).translate_message("Если Голосовал За Бота, Иначе",language)+' **`1`**)\n  **'+await (TranslateMessage(self.bot)).translate_message("Пример",language)+'**: `10.56 * 45.5 * 1 * 1.5`.\n'+await (TranslateMessage(self.bot)).translate_message("УСТАРЕЛО НЕДАВНО",language),
            inline=False
          )
        else:
          help_embed.add_field(
            name=await (TranslateMessage(self.bot)).translate_message("Команды",language),
            value=await (TranslateMessage(self.bot)).translate_message("Выберите Снизу Тип Команды.",language),
            inline=False
          )
        await helper.edit(content=None,embed=help_embed)
      
      bot_commands: dict[str,dict[str,str]] = {}
      # print('этап 1')
      for bot_command in self.bot.get_application_commands(True):
        # print(bot_command.name)
        if bot_command:
          path = bot_command.parent_cog.__module__
          # print(path)
          # print('entered\n')
          if 'owner' in path:
            continue
          bot_commands[await (TranslateMessage(self.bot)).translate_message(bot_command.name,language)] = {'path':path,'description':(await (TranslateMessage(self.bot)).translate_message(str(bot_command.extras['description']),language) if hasattr(bot_command, 'extras') and bot_command.extras else await (TranslateMessage(self.bot)).translate_message("Нет Описания У Команды.",language))}
      need_commands: dict[str,dict[str,str]] = {}
      # print('этап 2')
      for command, keys in bot_commands.items():
        # print(command)
        # print(keys['path'])
        if "🎉fun" not in keys['path']:
          # print('dont allow\n')
          continue
        # print('allow\n')
        need_commands[command] = keys
      max_page = (len(need_commands) - 1) // 5

      view = помощь_меню(interaction.user.id, language, send_help_message, "🎉fun", max_page, bot_commands)
      helper = await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Второй Этап Загрузки Данных.", language),view=view,wait=True)
      # print(max_page, bot_commands, need_commands)
      await send_help_message(None,None,None,None)

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
        color=Color.red(),
        fields=fields,
        footer_text=f'Ошибка в cogs.commands.🔧other.help',
        author_text='ЕРРОР',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      await interaction.followup.send(await(TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)

  setattr(помощь,"extras",{"description": "Эта команда покажет вам всю информацию обо мне, а также список всех моих команд."})

def setup(bot:commands.Bot):
  bot.add_cog(Help(bot))