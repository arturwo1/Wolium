from datetime import datetime, timezone
from time import time
from traceback import format_exception

import Utils.translate_to_all_languages
from nextcord import ButtonStyle, Color, Embed, IntegrationType, Interaction, InteractionContextType, SelectOption, slash_command
from nextcord.ext import commands
from nextcord.ui import Button, Select, View

from Utils.config import slash_command_cooldown

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

PER_PAGE = 5
SPECIAL_VALUES = {"about", "tospp", "faq", "formules"}

def locale_to_language(locale: str | None) -> str:
  if locale in ("en-US", "en-GB"):
    return "en"
  if locale == "es-ES":
    return "es"
  if locale == "sv-SE":
    return "sv"
  return "en"


class HelpMenu(View):
  def __init__(
    self,
    user_id: int,
    language: str,
    update_callback,
    selected_value: str,
    commandss: dict[str, dict[str, str]],
    timeout: int = 60 * 5,
  ):
    super().__init__(timeout=timeout)
    self.language = language
    self.user_id = user_id
    self.update_callback = update_callback
    self.all_commands = commandss

    self.page = 0
    self.selected_value = selected_value
    self.current_commands = self._get_commands_for_value(selected_value)
    self.max_page = self._calc_max_page(self.current_commands)

    self._build_components()

  def _category_from_path(self, path: str) -> str:
    parts = path.split(".")
    return parts[-2] if len(parts) >= 2 else parts[-1]

  def _build_categories(self) -> list[str]:
    cogs: list[str] = []
    for _, keys in self.all_commands.items():
      category = self._category_from_path(keys["path"])
      if category not in cogs:
        cogs.append(category)
    return cogs

  def _get_commands_for_value(self, value: str) -> dict[str, dict[str, str]]:
    if value in SPECIAL_VALUES:
      return {}

    need_commands: dict[str, dict[str, str]] = {}
    for command, keys in self.all_commands.items():
      if self._category_from_path(keys["path"]) == value:
        need_commands[command] = keys
    return need_commands

  def _calc_max_page(self, commands: dict[str, dict[str, str]]) -> int:
    if not commands:
      return 0
    return max(0, (len(commands) - 1) // PER_PAGE)

  def _build_components(self):
    options: list[SelectOption] = []

    for cog in self._build_categories():
      options.append(SelectOption(label=cog, value=cog))

    options.append(
      SelectOption(
        label="📚" + translate_to_all_languages("command.about_cap", "message", self.language),
        value="about",
        description=translate_to_all_languages("about.bot_info", "message", self.language)[:100],
      )
    )
    options.append(
      SelectOption(
        label="📘" + translate_to_all_languages("legal.tos_and_privacy", "message", self.language),
        value="tospp",
        description=translate_to_all_languages("legal.rules_and_policies", "message", self.language)[:100],
      )
    )
    options.append(
      SelectOption(
        label="📖" + translate_to_all_languages("general.faq", "message", self.language),
        value="faq",
        description=translate_to_all_languages("faq.answers", "message", self.language)[:100],
      )
    )
    options.append(
      SelectOption(
        label="🧮" + translate_to_all_languages("general.formulas", "message", self.language),
        value="formules",
        description=translate_to_all_languages("economy.formulas", "message", self.language)[:100],
      )
    )

    select_menu = Select(
      row=0,
      placeholder="🌍" + translate_to_all_languages("general.select_category", "message", self.language),
      options=options,
    )
    select_menu.callback = self.select_callback
    self.add_item(select_menu)

    back_button = Button(
      style=ButtonStyle.primary,
      label="◀",
      row=1,
      disabled=self.page <= 0,
    )
    back_button.callback = self.button1_callback
    self.add_item(back_button)

    forward_button = Button(
      style=ButtonStyle.primary,
      label="▶",
      row=1,
      disabled=self.page >= self.max_page,
    )
    forward_button.callback = self.button2_callback
    self.add_item(forward_button)

    self._sync_buttons()

  def _sync_buttons(self):
    special = self.selected_value in SPECIAL_VALUES
    for item in self.children:
      if isinstance(item, Button):
        if item.label == "◀":
          item.disabled = special or self.page <= 0
        elif item.label == "▶":
          item.disabled = special or self.page >= self.max_page

  async def select_callback(self, interaction: Interaction):
    if interaction.user.id != self.user_id:
      return
    if not interaction.response.is_done():
      await interaction.response.defer()

    self.selected_value = interaction.data["values"][0]
    self.page = 0
    self.current_commands = self._get_commands_for_value(self.selected_value)
    self.max_page = self._calc_max_page(self.current_commands)
    self._sync_buttons()

    await self.update_callback(self.selected_value, self.page, self.max_page, self.current_commands)

  async def button1_callback(self, interaction: Interaction):
    if interaction.user.id != self.user_id:
      return
    if not interaction.response.is_done():
      await interaction.response.defer()

    if self.selected_value in SPECIAL_VALUES:
      return

    if self.page > 0:
      self.page -= 1
      self._sync_buttons()
      await self.update_callback(self.selected_value, self.page, self.max_page, self.current_commands)

  async def button2_callback(self, interaction: Interaction):
    if interaction.user.id != self.user_id:
      return
    if not interaction.response.is_done():
      await interaction.response.defer()

    if self.selected_value in SPECIAL_VALUES:
      return

    if self.page < self.max_page:
      self.page += 1
      self._sync_buttons()
      await self.update_callback(self.selected_value, self.page, self.max_page, self.current_commands)


class Help(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  async def build_help_embed(
    self,
    interaction: Interaction,
    language: str,
    selected_value: str,
    page: int,
    max_page: int,
    commands_data: dict[str, dict[str, str]],
  ) -> Embed:
    tm = self.bot.get_cog("TranslateMessage")

    help_embed = Embed(
      title=await tm.translate_message("general.help", language),
      description="### " + await tm.translate_message("general.all_info_here", language),
      color=Color.dark_teal(),
      timestamp=datetime.now(timezone.utc),
    )
    help_embed.set_author(
      name=interaction.user.name,
      icon_url=interaction.user.display_avatar.url,
    )

    if selected_value in SPECIAL_VALUES:
      if selected_value == "about":
        help_embed.description = await tm.translate_message(
          """
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
# **Другое**:
""",
          language,
        )
        help_embed.description += f"""
### **🔗[`{await tm.translate_message('general.bot_support_server', language)}`](https://discord.gg/DhtQr4PGYM)**  |  **🔗[`{await tm.translate_message('general.developer_server', language)}`](https://discord.gg/MXupeAApza)**  |  **🔗[`{await tm.translate_message('general.bot_website', language)}`](https://wolium.netlify.app/)**  |  **🔗[`{await tm.translate_message('general.support', language)}`](https://www.patreon.com/arturwol)**
"""
      elif selected_value == "tospp":
        help_embed.description = (
          f"### **[`{await tm.translate_message('legal.terms_of_service', language)}`](https://wolium.netlify.app/terms-of-service/), "
          f"[`{await tm.translate_message('legal.privacy_policy', language)}`](https://wolium.netlify.app/privacy-policy/) "
          f"{await tm.translate_message('general.and_for_bot_users', language)} "
          f"[`{await tm.translate_message('general.rules', language)}`](https://wolium.netlify.app/rules/)**"
        )
      elif selected_value == "faq":
        help_embed.description = await tm.translate_message(
          """
# **Часто Задаваемые Вопросы**:
## **1**. ***ИИ Не Отвечает Или Пишет None.***
### **Сервера Нейросети Выключены/Закончились Токены/Другая Ошибка, Если После 3-5 Раз Нейросеть Не Ответила/Написала None То Скорее Всего Закончились Токены, Нужно Будет Ждать Начала Следующего Месяца.**
## **2**. ***Где Узнать ID Канала?***
### > 1. **Перейдите В Настройки Дискорда.**
### > 2. **Во Вкладке `Настройки приложения` Нажмите `Расширенные`.**
### > 3. **Включите `Режим разработчика`.**
### > 4. **ПКМ По Каналу > `Скопировать ID канала`.**
""",
          language,
        )
      elif selected_value == "formules":
        help_embed.description = "### **" + await tm.translate_message("general.all_info_here", language) + f" | *{selected_value}***"

        help_embed.add_field(
          name="/" + await tm.translate_message("general.work", language),
          value=(
            "(" + await tm.translate_message("general.from", language) + " **`9.26`** "
            + await tm.translate_message("general.until", language) + " **`13.98`**) `*` "
            "(**`3.5`** `*` **`" + await tm.translate_message("economy.upgrade", language) + "`**) `*` "
            "(**`2`** " + await tm.translate_message("condition.boost_enabled_else", language) + " **`1`**) `*` "
            "(**`1.5`** " + await tm.translate_message("condition.voted_for_bot_else", language) + " **`1`**)\n"
            f"  **{await tm.translate_message('general.example', language)}**: `10.56 * 45.5 * 1 * 1.5`.\n"
            + await tm.translate_message("general.deprecated_recently", language)
          ),
          inline=False,
        )

      help_embed.set_footer(
        text=await tm.translate_message("general.help", language) + " | " + await tm.translate_message(selected_value, language, save=False)
      )
      return help_embed

    if commands_data:
      help_embed.description = "### **" + await tm.translate_message("general.all_info_here", language) + f" | *{selected_value}***"

      start_index = page * PER_PAGE
      end_index = min(start_index + PER_PAGE, len(commands_data))
      items = list(commands_data.items())[start_index:end_index]

      for rank, (command, keys) in enumerate(items, start=start_index + 1):
        description = keys.get("description") or "Нет Описания У Команды."
        try:
          help_embed.add_field(
            name=f"#{rank} " + await tm.translate_message(command, language),
            value=await tm.translate_message(description, language),
            inline=False,
          )
        except Exception:
          help_embed.add_field(
            name=f"#{rank} " + await tm.translate_message(str(command), language),
            value=await tm.translate_message("general.no_description", language),
            inline=False,
          )
    else:
      help_embed.add_field(
        name=await tm.translate_message("general.commands", language),
        value=await tm.translate_message("error.no_commands_for_category", language),
        inline=False,
      )

    help_embed.set_footer(
      text=await tm.translate_message("general.help", language)
      + " | "
      + await tm.translate_message(f"{page + 1}/{max_page + 1} | {selected_value}", language, save=False)
    )
    return help_embed

  @slash_command(
    description="Абсолютно всё обо мне.",
    name_localizations=translate_to_all_languages("command.help", "name"),
    description_localizations=translate_to_all_languages("about.all_about_me", "description"),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],
  )
  async def help(self, interaction: Interaction):
    invite = None

    try:
      user_id = interaction.user.id
      current_time = time()

      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]["time"]
        if current_time - last_command_time < 10:
          locale = locale_to_language(getattr(interaction, "locale", None))
          await interaction.response.send_message(
            await tm.translate_message("error.rate_limit_part1", locale)
            + f" **<t:{round(last_command_time + 10)}:R>** "
            + await tm.translate_message("error.rate_limit_part2", locale),
            ephemeral=True,
          )
          return
        slash_command_cooldown[user_id]["time"] = current_time
      else:
        slash_command_cooldown[user_id] = {"time": current_time}

      user_settings = await gd.get_data(
        user_id,
        ["language", "variation"],
        "users",
        "user_id",
        interaction.guild,
      )
      language = user_settings.get("language") or "en"

      if interaction.guild:
        invite = await gi.invite(interaction.guild)

      await interaction.response.defer(ephemeral=True)

      helper_message = None

      async def send_help_message(selected_value: str, page: int, max_page: int, commands: dict[str, dict[str, str]]):
        if helper_message is None:
          return
        help_embed = await self.build_help_embed(
          interaction=interaction,
          language=language,
          selected_value=selected_value,
          page=page,
          max_page=max_page,
          commands_data=commands,
        )
        await helper_message.edit(content=None, embed=help_embed, view=view)

      bot_commands: dict[str, dict[str, str]] = {}

      for bot_command in self.bot.get_application_commands(True):
        if not bot_command:
          continue

        parent_cog = getattr(bot_command, "parent_cog", None)
        module_path = getattr(parent_cog, "__module__", "") if parent_cog else ""
        if "owner" in module_path:
          continue

        extras = getattr(bot_command, "extras", None) or {}
        description = extras.get("description") or getattr(bot_command, "description", None) or "Нет Описания У Команды."

        bot_commands[bot_command.name] = {
          "path": module_path,
          "description": str(description),
        }

      need_commands: dict[str, dict[str, str]] = {}
      for command, keys in bot_commands.items():
        if "🎉fun" not in keys["path"]:
          continue
        need_commands[command] = keys

      max_page = max(0, (len(need_commands) - 1) // PER_PAGE) if need_commands else 0
      view = HelpMenu(
        interaction.user.id,
        language,
        send_help_message,
        "🎉fun",
        bot_commands,
      )

      helper_message = await interaction.followup.send(
        await tm.translate_message("data.loading_stage_2", language),
        view=view,
        wait=True,
        ephemeral=True,
      )

      await send_help_message("🎉fun", 0, max_page, need_commands)

    except Exception as e:
      traceback_msg = "".join(format_exception(type(e), e, e.__traceback__))[:5000]

      channel_value = "Неизвестно"
      if interaction.channel:
        channel_value = f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{getattr(interaction.channel, 'name', 'unknown')}`)"

      guild_value = "ЛС"
      if interaction.guild:
        guild_value = f"{interaction.guild.id} | {invite or 'нет инвайта'} | {interaction.guild.name}"

      fields = [
        {
          "name": "Пользователь",
          "value": f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          "inline": True,
        },
        {
          "name": "Сервер",
          "value": guild_value,
          "inline": True,
        },
        {
          "name": "Канал",
          "value": channel_value,
          "inline": True,
        },
        {
          "name": "Ошибка",
          "value": traceback_msg,
          "inline": False,
        },
      ]

      se = self.bot.get_cog("SendEmbed")
      await se.send_embed(
        title=f"Произошла ошибка при вводе команды /{interaction.application_command.name}",
        description=str(e)[:2048],
        color=Color.red(),
        fields=fields,
        footer_text="Ошибка в cogs.commands.🔧other.help",
        author_text="ЕРРОР",
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256,
      )

      tm = self.bot.get_cog("TranslateMessage")
      locale = locale_to_language(getattr(interaction, "locale", None))
      await interaction.followup.send(
        await tm.translate_message(
          "error.occurred_logs_saved_review",
          locale,
        ),
        ephemeral=True,
      )

  setattr(
    help,
    "extras",
    {
      "description": "Эта команда покажет вам всю информацию обо мне, а также список всех моих команд."
    },
  )


def setup(bot: commands.Bot):
  bot.add_cog(Help(bot))