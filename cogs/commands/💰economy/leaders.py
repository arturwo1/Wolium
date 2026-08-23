from nextcord import SlashOption, IntegrationType, InteractionContextType, ButtonStyle, Interaction, Embed, Color, Colour, slash_command
from nextcord.ext import commands
from nextcord.ui import View, Button
from nextcord.errors import NotFound, Forbidden
from Utils.suffics import suffics
from datetime import datetime, timezone, timedelta
from time import time
from traceback import format_exception
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from Utils.calculate_LvL import calculate_LvL

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

_SORT_KEY_MAP = {
  "total_balance": "balance, user_data.bank_balance",
  "bank_balance": "bank_balance",
  "balance": "balance",
  "upgrade": "upgrade",
  "xp": "xp",
  "LvL": "xp",
  "XP_now": "xp",
  "messages": "messages",
  "voice": "voice",
  "votes": "votes",
  "streak": "streak",
}

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

def _fmt_voice(seconds) -> str:
  td = timedelta(seconds=int(seconds)) if isinstance(seconds, (int, float)) else seconds
  return f"{td.days}d {td.seconds // 3600}h {(td.seconds % 3600) // 60}m"

def _build_query(sort_key: str, where_clause: str = "") -> str:
  select_col = (
    f"user_data.{sort_key}" if sort_key not in ('messages', 'voice', 'votes', 'streak')
    else "COUNT(*) AS messages_count" if sort_key == 'messages'
    else "COALESCE(SUM(time_spent), '0 seconds'::interval) AS total_time" if sort_key == 'voice'
    else f"topgg.{sort_key}"
  )
  join_clause = (
    "LEFT JOIN messages ON user_data.user_id = messages.user_id" if sort_key == 'messages'
    else "LEFT JOIN voice ON user_data.user_id = voice.user_id" if sort_key == 'voice'
    else f"LEFT JOIN topgg ON user_data.user_id = topgg.user_id" if sort_key in ('votes', 'streak')
    else ""
  )
  group_extra = f", topgg.{sort_key}" if sort_key in ('votes', 'streak') else ""
  return f"""
    SELECT user_data.user_id, {select_col},
      users.telegram_id, users.discord_id, users.variation
    FROM user_data
    JOIN users ON user_data.user_id = users.user_id
    LEFT JOIN user_privacy ON user_data.user_id = user_privacy.user_id
    {join_clause}
    WHERE COALESCE(user_privacy.publicity, True) = True
    {where_clause}
    GROUP BY user_data.user_id, users.telegram_id, users.discord_id, users.variation{group_extra}
  """

def _extract_sort_value(row, sort_type: str, sort_key: str) -> float:
  if sort_type == "total_balance":
    return (row.get('balance') or 0) + (row.get('bank_balance') or 0)
  if sort_type in ("LvL", "XP_now"):
    lvl, _, xp_now = calculate_LvL(row['xp'])
    return lvl if sort_type == "LvL" else xp_now
  if sort_type == 'messages':
    return row.get("messages_count") or 0
  if sort_type == 'voice':
    td = row.get("total_time")
    return td.total_seconds() if isinstance(td, timedelta) else 0
  return row.get(sort_key) or 0

class LeaderboardPaginator(View):
  def __init__(self, interaction_user_id, max_page, update_callback, timeout=60 * 60):
    super().__init__(timeout=timeout)
    self.interaction_user_id = interaction_user_id
    self.page = 0
    self.max_page = max_page
    self.update_callback = update_callback
    self.update_buttons()

  def update_buttons(self):
    self.clear_items()
    back = Button(style=ButtonStyle.primary, label="◀", disabled=self.page <= 0)
    back.callback = lambda i: self._shift(i, -1)
    self.add_item(back)
    fwd = Button(style=ButtonStyle.primary, label="▶", disabled=self.page >= self.max_page)
    fwd.callback = lambda i: self._shift(i, 1)
    self.add_item(fwd)

  async def _shift(self, interaction: Interaction, delta: int):
    if interaction.user.id != self.interaction_user_id or interaction.response.is_done():
      return
    await interaction.response.defer()

    self.page = max(0, min(self.page + delta, self.max_page))
    self.update_buttons()
    await self.update_callback(self.page)
    await interaction.edit_original_message(view=self)

class Leaders(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  @slash_command(
    description="View leaderboards",
    name_localizations=translate_to_all_languages('economy.leaders_name', 'name'),
    description_localizations=translate_to_all_languages('economy.leaders_desc', 'description'),
    integration_types=[IntegrationType.user_install, IntegrationType.guild_install],
    contexts=[InteractionContextType.guild, InteractionContextType.bot_dm, InteractionContextType.private_channel],
  )
  async def leaders(self,
    interaction: Interaction,
    сортировка: str = SlashOption(
      name="sorting",
      description="Select List By Which to Sort LeaderBoard.",
      choices={"Total Money": "total_balance", "Bank Balance": "bank_balance", "Balance": "balance", "Upgrade": "upgrade", "Total XP": "xp", "LvL": "LvL", "Experience": "XP_now", "Message Count": "messages", "Time In Voice": "voice", "Votes": "votes", "Streak Votes": "streak"},
      required=True,
      name_localizations=translate_to_all_languages('general.sorting', 'name'),
      description_localizations=translate_to_all_languages('leaderboard.sort_desc', 'description'),
      choice_localizations=translate_to_all_languages({"Total Money": "total_balance", "Bank Balance": "bank_balance", "Balance": "balance", "Upgrade": "upgrade", "Total XP": "xp", "LvL": "LvL", "Experience": "XP_now", "Message Count": "messages", "Time In Voice": "voice", "Votes": "votes", "Streak Votes": "streak"}, 'choice'),
    ),
    тип: str = SlashOption(
      name="type",
      description="Тип ЛидерБорда",
      choices={"World": "world", "Server": "server", "Top Servers": "tservers"},
      required=True,
      name_localizations=translate_to_all_languages('general.type', 'name'),
      description_localizations=translate_to_all_languages('leaderboard.type', 'description'),
      choice_localizations=translate_to_all_languages({"World": "world", "Server": "server", "Top Servers": "tservers"}, 'choice'),
      default='server',
    ),
  ):
    invite = None
    try:
      user_id = interaction.user.id
      current_time = time()

      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")

      if user_id in slash_command_cooldown:
        last_time = slash_command_cooldown[user_id]['time']
        if current_time - last_time < 10:
          locale = _get_locale(interaction.locale)
          await interaction.response.send_message(await tm.translate_message("error.rate_limit_part1", locale) + f" **<t:{round(last_time + 10)}:R>** " + await tm.translate_message("error.rate_limit_part2", locale), ephemeral=True)
          return
        slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      user_settings = await gd.get_data(user_id, ['language', 'variation'], 'users', 'user_id', interaction.guild)
      user_privacy = await gd.get_data(user_id, ['publicity'], 'user_privacy', 'user_id', interaction.guild)
      language = user_settings['language']
      original_user_variation = user_settings['variation']

      if user_privacy["publicity"] is False:
        await interaction.response.send_message(await tm.translate_message("error.your_profile_hidden", language),ephemeral=True)
        return

      if сортировка not in _SORT_KEY_MAP:
        await interaction.response.send_message(await tm.translate_message("economy.sort_not_found", language, variables={"sort_type": сортировка}), ephemeral=True)
        return

      sort_key = _SORT_KEY_MAP[сортировка]

      users_and_balances = []
      super_total_value = 0

      await interaction.response.send_message(await tm.translate_message("general.wait", language))
      invite = await gi.invite(interaction.guild)

      if not (hasattr(self.bot, 'db_pool') and self.bot.db_pool):
        return

      if тип in ('server', 'world'):
        query = _build_query(sort_key)
        async with self.bot.db_pool.acquire() as conn:
          data = await conn.fetch(query)

        guild_member_ids = {str(m.id) for m in (interaction.guild.members if interaction.guild else [interaction.user, self.bot.user])}

        for row in data:
          uid = row['user_id']
          if тип == 'server' and str(uid) not in guild_member_ids:
            continue
          sv = _extract_sort_value(row, сортировка, sort_key)
          if not sv:
            continue
          super_total_value += sv
          users_and_balances.append((int(uid), sv, row['variation'], bool(row['discord_id']), bool(row['telegram_id'])))

      else:
        guild_member_map = {g.id: [m.id for m in g.members] for g in self.bot.guilds}
        all_ids = {mid for ids in guild_member_map.values() for mid in ids}
        if not all_ids:
          return

        sum_column = "balance + bank_balance" if сортировка == 'total_balance' else sort_key
        query = f"""
          SELECT m.guild_id, SUM(ud.{sum_column}) as server_sum
          FROM guild_users m
          JOIN user_data ud ON m.user_id = ud.user_id
          LEFT JOIN user_privacy up ON m.user_id = up.user_id
          WHERE COALESCE(up.publicity, True) = True
          GROUP BY m.guild_id
          ORDER BY server_sum DESC
          LIMIT 100;
        """
        
        async with self.bot.db_pool.acquire() as conn:
          data = await conn.fetch(query)

        for row in data:
          guild_id = row['guild_id']
          guild_sv = row['server_sum']
          if not guild_sv:
            continue
          super_total_value += guild_sv
          users_and_balances.append((int(guild_id), guild_sv, None, False, False))

      users_and_balances.sort(key=lambda x: x[1], reverse=True)
      max_page = max(0, (len(users_and_balances) - 1) // 10)

      async def update_leaderboard(page: int):
        lead = Embed(
          title=await tm.translate_message('economy.world_leaderboard' if тип == 'world' else 'economy.server_leaderboard' if тип == 'server' else 'economy.top_servers', language),
          description=await tm.translate_message("economy.sort_by", language) + f" **{сортировка}**",
          color=Color.yellow(),
          timestamp=datetime.now(timezone.utc)
        )

        total_display = (
          _fmt_voice(super_total_value) if сортировка == 'voice' and super_total_value
          else await suffics(number=super_total_value, variation=original_user_variation) if super_total_value
          else super_total_value
        )
        lead.set_author(
          name=await tm.translate_message("general.total", language) + f" {сортировка}: {total_display}",
          icon_url=interaction.user.display_avatar.url
        )

        start = page * 10
        wallet = '₩' if сортировка in ('balance', 'bank_balance', 'total_balance') else ''

        for rank, (uid, sv, variation, has_discord, has_telegram) in enumerate(users_and_balances[start:start + 10], start=start + 1):
          val_str = _fmt_voice(sv) if сортировка == 'voice' else f"{await suffics(number=sv, variation=variation)}{wallet}"

          member = interaction.guild.get_member(uid) if interaction.guild else None
          user_obj = self.bot.get_user(uid)
          guild_obj = self.bot.get_guild(uid)
          if not user_obj and not guild_obj:
            try:
              user_obj = await self.bot.fetch_user(uid)
            except NotFound:
              pass
          if not user_obj and not guild_obj:
            try:
              guild_obj = await self.bot.fetch_guild(uid)
            except (NotFound, Forbidden):
              pass

          badges = ''
          if member:
            badges += '<:guild:1358530418940575976> '
          if (member or user_obj) and has_discord:
            badges += '<a:on_discord:1318709863999606817>'
          if (member or user_obj) and has_telegram:
            badges += '<a:on_telegram:1318946754661453834>'

          if member:
            display = f"{badges}{member.display_name}"
          elif guild_obj:
            display = f"**`{guild_obj.name}`**"
          elif user_obj:
            display = f"{badges}{getattr(user_obj, 'display_name', f'{badges}ID: {uid}')}"
          else:
            display = f"{badges}UNKNOWN({uid})"

          lead.add_field(
            name=f"**#{rank}**.",
            value=f"{display} | {val_str}", inline=False)

        lead.set_footer(
          text=await tm.translate_message("general.page", language) + f" {page + 1}/{max_page + 1}",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )
        try:
          await interaction.edit_original_message(content=None, embed=lead)
        except Exception:
          return

      view = LeaderboardPaginator(interaction.user.id, max_page, update_leaderboard)
      try:
        await interaction.edit_original_message(content=await tm.translate_message("general.wait", language), view=view)
      except Exception:
        await interaction.followup.send(content=await tm.translate_message("general.wait", language), view=view, ephemeral=True)
      await update_leaderboard(0)

    except Exception as e:
      traceback_msg = ''.join(format_exception(type(e), e, e.__traceback__))[:5000]
      locale = _get_locale(interaction.locale)
      log = Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/лидеры** `сортировка` **{сортировка}** `тип` **{тип}**||",
        color=Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.set_author(
        name=f"Сервер ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=interaction.user.display_avatar.url
      )
      if interaction.guild:
        log.add_field(
          name="Сервер",
          value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}",
          inline=False
        )
      log.add_field(
        name="Канал",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
        inline=False
      )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(name="Ошибка", value=f"```py\n{traceback_msg[i:i + 1000]}```", inline=False)
      log.set_footer(
        text=str(datetime.now()),
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      error_msg = await tm.translate_message("error.occurred_logs_saved_review", locale)
      try:
        await interaction.response.send_message(error_msg, ephemeral=True)
      except Exception:
        await interaction.followup.send(error_msg, ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

  setattr(leaders, "extras", {"description": "commands.leaders.description"})

def setup(bot: commands.Bot):
  bot.add_cog(Leaders(bot))


