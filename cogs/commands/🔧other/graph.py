from nextcord.ext import commands
from nextcord import IntegrationType, InteractionContextType, SlashOption, Interaction, slash_command, File
from datetime import timedelta, datetime, timezone
from io import BytesIO
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter, AutoDateLocator
from time import time
import Utils.translate_to_all_languages

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages
graph_command_cooldown = {}
COLORS = {
  "primary": "#80E0F5",
  "secondary": "#ADB0B3",
  "bg": "#23272A",
  "grid_alpha": 0.25,
}

class Graph(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  def _get_period_settings(self, period: str):
    if period == "day":
      return "hour", "%H:%M"
    if period == "week":
      return "day", "%d.%m"
    if period == "month":
      return "day", "%d.%m"
    if period == "year":
      return "month", "%m.%Y"
    return "month", "%m.%Y"

  @slash_command(
    name="график",
    name_localizations=translate_to_all_languages('график', 'name'),
    description="Показать График Активности",
    description_localizations=translate_to_all_languages('Показать График Активности.', 'description'),
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
    user_id = interaction.user.id
    current_time = time()

    translate_message = self.bot.get_cog("TranslateMessage")
    get_data = self.bot.get_cog("GetData")
    
    if user_id in graph_command_cooldown:
      last_command_time = graph_command_cooldown[user_id]['time']
      if current_time - last_command_time < 120:
        await interaction.response.send_message(await translate_message.translate_message(f"You write commands so fast,",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **<t:{round(last_command_time+120)}:R>** "+await translate_message.translate_message(f"you can write commands.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
        return
      else:
        graph_command_cooldown[user_id]['time'] = current_time
    else:
      graph_command_cooldown[user_id] = {'time': current_time}

    user_settings = await get_data.get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
    language = user_settings['language']
    
    await interaction.response.defer()

    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else None
    if сервер and not guild_id:
      return await interaction.send(await translate_message.translate_message("Информация О Сервере Доступна Только На Сервере.",language))

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
      return await interaction.send(await translate_message.translate_message("Нет подключения к базе данных.",language))
    
    bucket, date_fmt = self._get_period_settings(период)

    async with self.bot.db_pool.acquire() as conn:
      if тип == "messages":
          query = f"""
            SELECT date_trunc('{bucket}', date_time) AS bucket_time, COUNT(*)::int AS count
            FROM messages
            WHERE{" guild_id = $1 AND" if сервер else ""} user_id = ${"2" if сервер else "1"}
            {f"AND date_time >= ${'3' if сервер else '2'}" if since else ""}
            GROUP BY bucket_time
            ORDER BY bucket_time
          """
          if since:
            if since.tzinfo is not None and since.tzinfo.utcoffset(since) is not None:
              since = since.replace(tzinfo=None)
          params = [guild_id, user_id, since] if сервер and since else \
            [guild_id, user_id] if сервер else \
            [user_id, since] if since else \
            [user_id]

          rows = await conn.fetch(query, *params)
          dates = [r["bucket_time"] for r in rows]
          values = [r["count"] for r in rows]

          fig = Figure(figsize=(10, 4), dpi=120, facecolor=COLORS['bg'])
          FigureCanvasAgg(fig)
          ax = fig.add_subplot(111)
          ax.set_facecolor(COLORS['bg'])

          ax.plot(dates, values, marker='o', linewidth=1.8, color=COLORS['primary'])

          ax.set_title(
            f"{await translate_message.translate_message('Сообщения',language)} — "
            f"{await translate_message.translate_message(период,language)} — "
            f"{await translate_message.translate_message('Сервер' if сервер else 'Общее',language)}",
            color=COLORS['primary']
          )
          ax.set_xlabel(await translate_message.translate_message("Дата",language), color=COLORS['secondary'])
          ax.set_ylabel(await translate_message.translate_message("Количество сообщений",language), color=COLORS['secondary'])

          ax.grid(True, alpha=COLORS['grid_alpha'])
          ax.tick_params(axis='x', colors=COLORS['secondary'], labelsize=9)
          ax.tick_params(axis='y', colors=COLORS['secondary'], labelsize=9)

          locator = AutoDateLocator(minticks=4, maxticks=8)
          ax.xaxis.set_major_locator(locator)
          ax.xaxis.set_major_formatter(DateFormatter(date_fmt))
          for label in ax.get_xticklabels():
            label.set_rotation(25)
            label.set_ha('right')

          for spine in ax.spines.values():
            spine.set_color(COLORS['secondary'])

          fig.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.24)

          message = await translate_message.translate_message("Сообщений:",language) + " " + str(sum(values))
      elif тип=="voice":
        query = f"""
          SELECT
            date_trunc('{bucket}', enter_time) AS bucket_time,
            COUNT(*)::int AS sessions,
            COALESCE(SUM(EXTRACT(EPOCH FROM time_spent)) / 3600.0, 0) AS hours
          FROM voice
          WHERE{" guild_id = $1 AND" if сервер else ""} user_id = ${"2" if сервер else "1"}
          {f"AND enter_time >= ${'3' if сервер else '2'}" if since else ""}
          GROUP BY bucket_time
          ORDER BY bucket_time
        """
        if since:
          if since.tzinfo is not None and since.tzinfo.utcoffset(since) is not None:
            since = since.replace(tzinfo=None)
        params = [guild_id, user_id, since] if сервер and since else \
          [guild_id, user_id] if сервер else \
          [user_id, since] if since else \
          [user_id]
        rows = await conn.fetch(query, *params)

        if not rows:
          return await interaction.send(await translate_message.translate_message("Нет данных за указанный период.",language))

        dates = [r["bucket_time"] for r in rows]
        sessions = [r["sessions"] for r in rows]
        hours = [round(float(r["hours"]), 2) for r in rows]

        fig = Figure(figsize=(10, 4), dpi=120, facecolor=COLORS['bg'])
        FigureCanvasAgg(fig)

        ax1 = fig.add_subplot(111)
        ax1.set_facecolor(COLORS['bg'])

        ax1.bar(dates, sessions, color=COLORS['primary'], label=await translate_message.translate_message('Сессии',language))
        ax1.set_ylabel(await translate_message.translate_message("Количество сессий",language), color=COLORS['primary'])
        ax1.tick_params(axis='y', labelcolor=COLORS['primary'])
        ax1.tick_params(axis='x', colors=COLORS['secondary'], labelsize=9)
        ax1.grid(True, alpha=COLORS['grid_alpha'])

        locator = AutoDateLocator(minticks=4, maxticks=8)
        ax1.xaxis.set_major_locator(locator)
        ax1.xaxis.set_major_formatter(DateFormatter(date_fmt))
        for label in ax1.get_xticklabels():
          label.set_rotation(25)
          label.set_ha('right')

        ax2 = ax1.twinx()
        ax2.plot(dates, hours, color=COLORS['secondary'], marker='o', linewidth=1.8, label=await translate_message.translate_message('Часы',language))
        ax2.set_ylabel(await translate_message.translate_message("Часы в войсе",language), color=COLORS['secondary'])
        ax2.tick_params(axis='y', labelcolor=COLORS['secondary'])

        ax1.set_title(
          f"{await translate_message.translate_message('Войс-активность',language)} — "
          f"{await translate_message.translate_message(период,language)} — "
          f"{await translate_message.translate_message('Сервер' if сервер else 'Общее',language)}",
          color=COLORS['primary']
        )
        ax1.set_xlabel(await translate_message.translate_message("Дата",language), color=COLORS['secondary'])

        for spine in ax1.spines.values():
          spine.set_color(COLORS['secondary'])
        for spine in ax2.spines.values():
          spine.set_color(COLORS['secondary'])

        fig.subplots_adjust(left=0.08, right=0.92, top=0.88, bottom=0.24)

        message = await translate_message.translate_message("Сессий:",language)+" "+str(sum(sessions))+"\n"+await translate_message.translate_message("Часов В Войсе:",language)+" "+str(sum(hours))+"\n\n## "+await translate_message.translate_message("На моём сайте вы уже можете посмотреть всё, что вас интересует, более подробно!", language)+"\n**https://wolium.netlify.app/**"
      else:
        return await interaction.send(await translate_message.translate_message("Неизвестный тип данных.",language))

    buf = BytesIO()
    fig.savefig(buf, format='png', facecolor=fig.get_facecolor())
    buf.seek(0)
    fig.clear()

    file = File(buf, filename="graph.png")
    await interaction.send(content=message,file=file)

  setattr(график,"extras",{"description": "Ты Можешь Узнать Свою Активность За Любой Промежуток Времени С Момента Установки Меня."})

def setup(bot: commands.Bot):
  bot.add_cog(Graph(bot))