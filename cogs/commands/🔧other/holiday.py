from datetime import datetime, timedelta, timezone
from time import time
from nextcord.ext import commands
from nextcord.ui import View, Button, button
from nextcord import slash_command, IntegrationType, InteractionContextType, Interaction, SlashOption, ButtonStyle, Embed, Colour
from Utils.holiday_type_choose import holiday_type_choose
import Utils.translate_to_all_languages
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot, slash_command_cooldown
from cogs.utils.get_data import GetData
from cogs.utils.get_invite import GetInvite
from cogs.utils.send_embed import SendEmbed
from cogs.utils.translate_message import TranslateMessage

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class список_праздников(View):
  def __init__(self, interaction_user_id, max_page, update_callback, timeout=60*60):
    super().__init__(timeout=timeout)
    self.interaction_user_id = interaction_user_id
    self.page = 0
    self.max_page = max_page
    self.update_callback = update_callback

  @button(label="◀", style=ButtonStyle.primary)
  async def button1_callback(self, button: Button, interaction: Interaction):
    user_id = interaction.user.id
    if user_id != self.interaction_user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    if self.page > 0:
      self.page -= 1
      await self.update_callback(self.page)
      #await interaction.response.edit_message(view=self)

  @button(label="▶", style=ButtonStyle.primary)
  async def button2_callback(self, button: Button, interaction: Interaction):
    user_id = interaction.user.id
    if user_id != self.interaction_user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    if self.page < self.max_page:
      self.page += 1
      await self.update_callback(self.page)
      #await interaction.response.edit_message(view=self)


class Holiday(commands.Cog):
  def __init__(self,bot):
    self.bot:commands.Bot=bot

  @slash_command(description="Узнать Праздники Которые Бот Использует.",
    name_localizations=translate_to_all_languages('праздник', 'name'),
    description_localizations=translate_to_all_languages('Узнать Праздники Которые Бот Использует.', 'description'),
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
  async def праздник(self,
    interaction: Interaction,
    праздник: str=SlashOption(name="праздник", description="Выбери Что Хочешь Узнать.",choices={"Current holiday": "current_holiday", "All holidays": "print_holidays"},required=True, name_localizations=translate_to_all_languages('праздник', 'name'), description_localizations=translate_to_all_languages('Выбери Что Хочешь Узнать.', 'description'), choice_localizations=translate_to_all_languages({"праздник сегодня": "current_holiday", "все праздники": "print_holidays"}, 'choice')),
    лично: bool=SlashOption(name="лично", description="Только Ты Увидешь Сообщение, Или Все.",required=False,default=False, name_localizations=translate_to_all_languages('лично', 'name'), description_localizations=translate_to_all_languages('Только Ты Увидешь Сообщение, Или Все.', 'description')),
  ):
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
    await interaction.response.defer(ephemeral=лично if interaction.guild else True)

    if праздник=="current_holiday":
      current_holiday = holiday_type_choose("current_holiday")
      if current_holiday:
        holiday_embed = Embed(
          title=f"{await (TranslateMessage(self.bot)).translate_message('Сезон Года Этого Праздника:',language)} {await (TranslateMessage(self.bot)).translate_message(current_holiday['season'],language)}",
          description=f"{await (TranslateMessage(self.bot)).translate_message('Название Праздника:',language)} **`{await (TranslateMessage(self.bot)).translate_message(current_holiday['name'],language)}`**",
          color=(Colour.from_rgb(255,0,0) if current_holiday['season']=="весна" else Colour.from_rgb(0,255,255) if current_holiday['season']=="лето" else Colour.from_rgb(255,0,0) if current_holiday['season']=="осень" else Colour.from_rgb(0,0,255)),
          timestamp=datetime.now(timezone.utc)
        )
        holiday_embed.set_author(
          name=f"{interaction.user.name}",
          icon_url=f"{interaction.user.display_avatar.url}",
        )
        holiday_embed.add_field(
          name=await (TranslateMessage(self.bot)).translate_message(f"Время Праздника",language),
          value=f"{await (TranslateMessage(self.bot)).translate_message('Начало Праздника В:',language)} {current_holiday['start_date']}\n{await (TranslateMessage(self.bot)).translate_message('Конец Праздника В:',language)} {current_holiday['end_date']}\n{await (TranslateMessage(self.bot)).translate_message('Длительность Праздника:',language)} {current_holiday['duration']} {await (TranslateMessage(self.bot)).translate_message('дней',language)}",
          inline=False,
        )
        holiday_embed.set_footer(
          text=f"{str(datetime.now())}",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png",
        )
        await interaction.followup.send(embed=holiday_embed,ephemeral=лично)
      else:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("В Данный Момент Праздников Нет",language),ephemeral=лично)
    elif праздник=="print_holidays":
      holidaysers:list = sorted(holiday_type_choose("print_holidays"), key=lambda x: datetime.strptime(x[1], '%d.%m.%Y'))
      max_page = (len(holidaysers) - 1) // 5
      async def update_holidays(page):
        holiday_embed = Embed(
          title=await (TranslateMessage(self.bot)).translate_message(f"Все Праздники Которые Бот Использует",language),
          description=await (TranslateMessage(self.bot)).translate_message(f"Если здесь нету праздников которые вы отмечаете, вы можете предложить их добавить разработчику бота.",language),
          color=(Colour.from_rgb(255,0,0) or Colour.from_rgb(0,255,255) or Colour.from_rgb(255,0,0) or Colour.from_rgb(0,0,255)),
          timestamp=datetime.now(timezone.utc)
        )
        holiday_embed.set_author(
          name=f"{interaction.user.name}",
          icon_url=f"{interaction.user.display_avatar.url}",
        )

        start_index = page * 5
        end_index = min(start_index + 5, len(holidaysers))

        for number, (name, start_date, end_date, duration, season) in enumerate(holidaysers[start_index:end_index], start=start_index + 1):
          # name, start_date, end_date, duration, season = current_holiday
          start_date_obj = datetime.strptime(start_date, '%d.%m.%Y')
          remaining_time = start_date_obj - datetime.now()

          if remaining_time.total_seconds() <= 0:
            remaining_time += timedelta(days=365)
          remaining_time_str = str(remaining_time).split('.')[0]
          
          holiday_embed.add_field(
            name=await (TranslateMessage(self.bot)).translate_message(f"Название Праздника: {name}",language),
            value=(
              f"{await (TranslateMessage(self.bot)).translate_message('До праздника:',language)} {remaining_time_str}\n"
              f"{await (TranslateMessage(self.bot)).translate_message('Сезон праздника:',language)} {await (TranslateMessage(self.bot)).translate_message(season,language)}\n"
              f"{await (TranslateMessage(self.bot)).translate_message('Начало праздника:',language)} {start_date}\n"
              f"{await (TranslateMessage(self.bot)).translate_message('Конец праздника:',language)} {end_date}\n"
              f"{await (TranslateMessage(self.bot)).translate_message('Длительность праздника:',language)} {duration} {await (TranslateMessage(self.bot)).translate_message('дней',language)}"
            ),
            inline=False)
          holiday_embed.set_footer(
            text=await (TranslateMessage(self.bot)).translate_message("Страница", language)+f" {page + 1}/{max_page + 1}",
            icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png",
          )
          try:
            await handler.edit(None, embed=holiday_embed)
          except Exception:
            await interaction.followup.send(embed=holiday_embed,ephemeral=True)

      view = список_праздников(interaction.user.id, max_page, update_holidays)
      try:
        handler = await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message("Подождите.", language), view=view)
      except Exception:
        handler = await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message("Подождите.", language), view=view,ephemeral=True)
      await update_holidays(0)

    invite = await (GetInvite(self.bot)).invite(interaction.guild)

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

def setup(bot:commands.Bot):
  bot.add_cog(Holiday(bot))