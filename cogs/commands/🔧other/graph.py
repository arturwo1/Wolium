from nextcord.ext import commands
from nextcord import IntegrationType, InteractionContextType, SlashOption, Interaction, slash_command, File
from datetime import timedelta, datetime, timezone
from io import BytesIO
from collections import defaultdict, Counter
from matplotlib.pyplot import rcParams, figure, plot, title, xlabel, ylabel, grid, tight_layout, subplots, savefig, close
from matplotlib.dates import DateFormatter
from time import time
from cogs.utils.get_data import GetData
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot
from cogs.utils.translate_message import TranslateMessage
import Utils.translate_to_all_languages

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages
graph_command_cooldown = {}

class Graph(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  @slash_command(
    name="график",
    name_localizations=translate_to_all_languages('график', 'name'),
    description="Показать График Активности",
    description_localizations=translate_to_all_languages('Показать График Активности.', 'description'),
    force_global=True,
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ]
  )
  async def график(
    self,
    interaction: Interaction,
    тип: str = SlashOption(
      name="тип",
      name_localizations=translate_to_all_languages('тип', 'name'),
      description="Тип Данных",
      description_localizations=translate_to_all_languages('Тип Данных', 'description'),
      choices={"Messages": "messages", "Voice": "voice"},
      choice_localizations=translate_to_all_languages({"Messages": "messages", "Voice": "voice"}, 'choice'),
      required=True
    ),
    период: str = SlashOption(
      name="период",
      name_localizations=translate_to_all_languages('период', 'name'),
      description="Период Времени",
      description_localizations=translate_to_all_languages('Период Времени', 'description'),
      choices={"1 Day": "day", "1 Week": "week", "1 Month": "month", "1 Year": "year", "For All Time": "all"},
      choice_localizations=translate_to_all_languages({"1 Day": "day", "1 Week": "week", "1 Month": "month", "1 Year": "year", "For All Time": "all"}, 'choice'),
      required=True
    ),
    сервер: bool = SlashOption(
      name="сервер",
      name_localizations=translate_to_all_languages('сервер', 'name'),
      description="На Сервере Или В Общем.",
      description_localizations=translate_to_all_languages('На Сервере Или В Общем.', 'description'),
      default=False
    )
  ):
    if ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
      await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://sites.google.com/view/arturwolium/main-page/rules) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
      return
    user_id = interaction.user.id
    current_time = time()

    if user_id in graph_command_cooldown:
      last_command_time = graph_command_cooldown[user_id]['time']
      if current_time - last_command_time < 120:
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"You write commands so fast,",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **<t:{round(last_command_time+120)}:R>** "+await (TranslateMessage(self.bot)).translate_message(f"you can write commands.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
        return
      else:
        graph_command_cooldown[user_id]['time'] = current_time
    else:
      graph_command_cooldown[user_id] = {'time': current_time}
    if interaction.guild:
      guild_settings = await (GetData(self.bot)).get_data(interaction.guild.id,['banned'],'guilds','guild_id',interaction.guild)
    user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation','banned'],'users','user_id',interaction.guild)
    language = user_settings['language']

    if user_settings['banned'] or (guild_settings['banned'] if interaction.guild else False):
      await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://sites.google.com/view/arturwolium/main-page/rules) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",language), ephemeral=True)
      servers_with_no_acces_for_bot.append(interaction.guild.id)
      users_with_no_acces_for_bot.append(user_id)
      return
    
    await interaction.response.defer()

    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else None
    if сервер and not guild_id:
      return await interaction.send(await (TranslateMessage(self.bot)).translate_message("Информация О Сервере Доступна Только На Сервере.",language))

    now = datetime.now(timezone.utc)
    if период == "day":
      since = now - timedelta(days=1)
    elif период == "week":
      since = now - timedelta(weeks=1)
    elif период == "month":
      since = now - timedelta(days=30)
    elif период == "year":
      since = now - timedelta(days=365)
    else:
      since = None

    if not hasattr(self.bot, 'db_pool') or not self.bot.db_pool:
      return await interaction.send(await (TranslateMessage(self.bot)).translate_message("Нет подключения к базе данных.",language))

    async with self.bot.db_pool.acquire() as conn:
      if тип == "messages":
          query = f"""
            SELECT date_time FROM messages
            WHERE{" guild_id = $1 AND" if сервер else ""} user_id = ${"2" if сервер else "1"}
            {f"AND date_time >= ${'3' if сервер else '2'}" if since else ""}
          """
          if since:
            # Удаляем таймзону, если она есть
            if since.tzinfo is not None and since.tzinfo.utcoffset(since) is not None:
              since = since.replace(tzinfo=None)
          params = [guild_id, user_id, since] if сервер and since else \
            [guild_id, user_id] if сервер else \
            [user_id, since] if since else \
            [user_id]
          rows = await conn.fetch(query, *params)
          data = [r["date_time"].date() for r in rows]

          counted = Counter(data)
          dates = sorted(counted.keys())
          values = [counted[day] for day in dates]

          # Настройки цветов
          rcParams['axes.facecolor'] = '#23272A'
          rcParams['figure.facecolor'] = '#23272A'
          rcParams['text.color'] = '#80E0F5'
          rcParams['axes.labelcolor'] = '#ADB0B3'
          rcParams['xtick.color'] = '#ADB0B3'
          rcParams['ytick.color'] = '#ADB0B3'

          figure(figsize=(10, 4))
          plot(dates, values, marker='o', color='cyan')
          title(f"{await (TranslateMessage(self.bot)).translate_message('Сообщения',language)} — {await (TranslateMessage(self.bot)).translate_message(период,language)} — {await (TranslateMessage(self.bot)).translate_message('Сервер' if сервер else 'Общее',language)}")
          xlabel(await (TranslateMessage(self.bot)).translate_message("Дата",language))
          ylabel(await (TranslateMessage(self.bot)).translate_message("Количество сообщений",language))
          grid(True)
          tight_layout()
          message = await (TranslateMessage(self.bot)).translate_message("Сообщений:",language)+" "+str(len(data))
      else:  # voice
        query = f"""
          SELECT enter_time, time_spent FROM voice
          WHERE{" guild_id = $1 AND" if сервер else ""} user_id = ${"2" if сервер else "1"}
          {f"AND enter_time >= ${'3' if сервер else '2'}" if since else ""}
        """
        if since:
          if since.tzinfo is not None and since.tzinfo.utcoffset(since) is not None:
            since = since.replace(tzinfo=None)
        params = [guild_id, user_id, since] if сервер and since else \
          [guild_id, user_id] if сервер else \
          [user_id, since] if since else \
          [user_id]
        rows = await conn.fetch(query, *params)

        session_data = defaultdict(int)
        time_data = defaultdict(float)

        for r in rows:
          day = r["enter_time"].date()
          session_data[day] += 1
          time_data[day] += r["time_spent"].total_seconds() / 3600  # в часах

        if not session_data:
          return await interaction.send(await (TranslateMessage(self.bot)).translate_message("Нет данных за указанный период.",language))

        dates = sorted(session_data.keys())
        sessions = [session_data[d] for d in dates]
        hours = [round(time_data[d], 2) for d in dates]

        # Настройки цветов
        rcParams['axes.facecolor'] = '#23272A'
        rcParams['figure.facecolor'] = '#23272A'
        rcParams['text.color'] = '#80E0F5'
        rcParams['axes.labelcolor'] = '#ADB0B3'
        rcParams['xtick.color'] = '#ADB0B3'
        rcParams['ytick.color'] = '#ADB0B3'

        fig, ax1 = subplots(figsize=(10, 4))

        ax1.bar(dates, sessions, color='skyblue', label=await (TranslateMessage(self.bot)).translate_message('Сессии',language))
        ax1.set_ylabel(await (TranslateMessage(self.bot)).translate_message("Количество сессий",language), color='skyblue')
        ax1.tick_params(axis='y', labelcolor='skyblue')

        ax2 = ax1.twinx()
        ax2.plot(dates, hours, color='lightcoral', marker='o', label=await (TranslateMessage(self.bot)).translate_message('Часы',language))
        ax2.set_ylabel(await (TranslateMessage(self.bot)).translate_message("Часы в войсе",language), color='lightcoral')
        ax2.tick_params(axis='y', labelcolor='lightcoral')

        title(f"{await (TranslateMessage(self.bot)).translate_message('Войс-активность',language)} — {await (TranslateMessage(self.bot)).translate_message(период,language)} — {await (TranslateMessage(self.bot)).translate_message('Сервер' if сервер else 'Общее',language)}")
        xlabel(await (TranslateMessage(self.bot)).translate_message("Дата",language))
        ax1.xaxis.set_major_formatter(DateFormatter('%d.%m'))

        fig.tight_layout()
        message = await (TranslateMessage(self.bot)).translate_message("Сессий:",language)+" "+str(sum(sessions))+"\n"+await (TranslateMessage(self.bot)).translate_message("Часов В Войсе:",language)+" "+str(sum(hours))

    buf = BytesIO()
    savefig(buf, format='png')
    buf.seek(0)
    close()

    file = File(buf, filename="graph.png")
    await interaction.send(content=message,file=file)

  setattr(график,"extras",{"description": "Ты Можешь Узнать Свою Активность За Любой Промежуток Времени С Момента Установки Меня."})

def setup(bot: commands.Bot):
  bot.add_cog(Graph(bot))