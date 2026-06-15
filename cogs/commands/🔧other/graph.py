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

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

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
    name="graph",
    name_localizations=translate_to_all_languages('command.graph', 'name'),
    description="Show activity graph",
    description_localizations=translate_to_all_languages('stats.show_activity_graph', 'description'),
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
  async def graph(
    self,
    interaction: Interaction,
    data_type: str = SlashOption(
      name="data_type",
      name_localizations=translate_to_all_languages('general.type_lower', 'name'),
      description="Type of data",
      description_localizations=translate_to_all_languages('data.data_type', 'description'),
      choices={"Messages": "messages", "Voice": "voice"},
      choice_localizations=translate_to_all_languages({"Messages": "messages", "Voice": "voice"}, 'choice'),
      required=True
    ),
    period: str = SlashOption(
      name="period",
      name_localizations=translate_to_all_languages('general.period', 'name'),
      description="Time period",
      description_localizations=translate_to_all_languages('general.time_period', 'description'),
      choices={"1 Day": "day", "1 Week": "week", "1 Month": "month", "1 Year": "year", "For All Time": "all"},
      choice_localizations=translate_to_all_languages({"1 Day": "day", "1 Week": "week", "1 Month": "month", "1 Year": "year", "For All Time": "all"}, 'choice'),
      required=True
    ),
    on_server: bool = SlashOption(
      name="on_server",
      name_localizations=translate_to_all_languages('general.server_lower', 'name'),
      description="On server or global.",
      description_localizations=translate_to_all_languages('general.on_server_or_global', 'description'),
      default=False
    )
  ):
    try:
      user_id = interaction.user.id
      current_time = time()

      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      lang = _get_locale(interaction.locale)
      
      if user_id in graph_command_cooldown:
        last_command_time = graph_command_cooldown[user_id]['time']
        if current_time - last_command_time < 120:
          await interaction.response.send_message(await tm.translate_message("error.rate_limit", lang, variables={"time": f"<t:{round(last_command_time+120)}:R>"}), ephemeral=True)
          return
        else:
          graph_command_cooldown[user_id]['time'] = current_time
      else:
        graph_command_cooldown[user_id] = {'time': current_time}

      user_settings = await gd.get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']
      
      await interaction.response.defer()

      user_id = interaction.user.id
      guild_id = interaction.guild.id if interaction.guild else None
      if on_server and not guild_id:
        return await interaction.followup.send(await tm.translate_message("error.server_info_only_on_server", language))

      # Rest of function continues...
    except Exception as e:
      await interaction.followup.send(f"Error: {str(e)[:500]}", ephemeral=True)

    now = datetime.now(timezone.utc)
    if period == "day":
      since = now - timedelta(days=1)
    elif period == "week":
      since = now - timedelta(weeks=1)
    elif period == "month":
      since = now - timedelta(days=30)
    elif period == "year":
      since = now - timedelta(days=365)
    else:
      since = None

    if not hasattr(self.bot, 'db_pool') or not self.bot.db_pool:
      return await interaction.followup.send(await tm.translate_message("error.no_db_connection",language))
    
    bucket, date_fmt = self._get_period_settings(period)

    async with self.bot.db_pool.acquire() as conn:
      if data_type == "messages":
          query = f"""
            SELECT date_trunc('{bucket}', date_time) AS bucket_time, COUNT(*)::int AS count
            FROM messages
            WHERE{" guild_id = $1 AND" if on_server else ""} user_id = ${"2" if on_server else "1"}
            {f"AND date_time >= ${'3' if on_server else '2'}" if since else ""}
            GROUP BY bucket_time
            ORDER BY bucket_time
          """
          if since:
            if since.tzinfo is not None and since.tzinfo.utcoffset(since) is not None:
              since = since.replace(tzinfo=None)
          params = [guild_id, user_id, since] if on_server and since else \
            [guild_id, user_id] if on_server else \
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
            f"{await tm.translate_message('general.messages',language)} — "
            f"{await tm.translate_message(period,language)} — "
            f"{await tm.translate_message('general.server' if on_server else 'general',language)}",
            color=COLORS['primary']
          )
          ax.set_xlabel(await tm.translate_message("general.date",language), color=COLORS['secondary'])
          ax.set_ylabel(await tm.translate_message("stats.message_count_label",language), color=COLORS['secondary'])

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

          message = await tm.translate_message("stats.messages_label",language) + " " + str(sum(values))
      elif data_type=="voice":
        query = f"""
          SELECT
            date_trunc('{bucket}', enter_time) AS bucket_time,
            COUNT(*)::int AS sessions,
            COALESCE(SUM(EXTRACT(EPOCH FROM time_spent)) / 3600.0, 0) AS hours
          FROM voice
          WHERE{" guild_id = $1 AND" if on_server else ""} user_id = ${"2" if on_server else "1"}
          {f"AND enter_time >= ${"3" if on_server else "2"}" if since else ""}
          GROUP BY bucket_time
          ORDER BY bucket_time
        """
        if since:
          if since.tzinfo is not None and since.tzinfo.utcoffset(since) is not None:
            since = since.replace(tzinfo=None)
        params = [guild_id, user_id, since] if on_server and since else \
          [guild_id, user_id] if on_server else \
          [user_id, since] if since else \
          [user_id]
        rows = await conn.fetch(query, *params)

        if not rows:
          return await interaction.followup.send(await tm.translate_message("error.no_data_for_period",language))

        dates = [r["bucket_time"] for r in rows]
        sessions = [r["sessions"] for r in rows]
        hours = [round(float(r["hours"]), 2) for r in rows]

        fig = Figure(figsize=(10, 4), dpi=120, facecolor=COLORS['bg'])
        FigureCanvasAgg(fig)

        ax1 = fig.add_subplot(111)
        ax1.set_facecolor(COLORS['bg'])

        ax1.bar(dates, sessions, color=COLORS['primary'], label=await tm.translate_message('stats.sessions',language))
        ax1.set_ylabel(await tm.translate_message("stats.sessions_count",language), color=COLORS['primary'])
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
        ax2.plot(dates, hours, color=COLORS['secondary'], marker='o', linewidth=1.8, label=await tm.translate_message('time.hours',language))
        ax2.set_ylabel(await tm.translate_message("stats.hours_in_voice",language), color=COLORS['secondary'])
        ax2.tick_params(axis='y', labelcolor=COLORS['secondary'])

        ax1.set_title(
          f"{await tm.translate_message('stats.voice_activity',language)} — "
          f"{await tm.translate_message(period,language)} — "
          f"{await tm.translate_message('general.server' if on_server else 'general',language)}",
          color=COLORS['primary']
        )
        ax1.set_xlabel(await tm.translate_message("general.date",language), color=COLORS['secondary'])

        for spine in ax1.spines.values():
          spine.set_color(COLORS['secondary'])
        for spine in ax2.spines.values():
          spine.set_color(COLORS['secondary'])

        fig.subplots_adjust(left=0.08, right=0.92, top=0.88, bottom=0.24)

        message = await tm.translate_message("stats.sessions_label",language)+" "+str(sum(sessions))+"\n"+await tm.translate_message("stats.hours_in_voice_label",language)+" "+str(sum(hours))+"\n\n## "+await tm.translate_message("general.website_more_info", language)+"\n**https://wolium.netlify.app/**"
      else:
        return await interaction.followup.send(await tm.translate_message("error.unknown_data_type",language))

    buf = BytesIO()
    fig.savefig(buf, format='png', facecolor=fig.get_facecolor())
    buf.seek(0)
    fig.clear()

    file = File(buf, filename="graph.png")
    await interaction.followup.send(content=message,file=file)

  setattr(graph,"extras",{"description": "commands.graph.description"})

def setup(bot: commands.Bot):
  bot.add_cog(Graph(bot))
