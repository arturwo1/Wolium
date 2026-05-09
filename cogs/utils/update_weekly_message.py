from nextcord import Embed, Colour, Object
from nextcord.errors import HTTPException
from nextcord.ext import commands, tasks
from datetime import datetime, timezone
from Utils.holiday_type_choose import holiday_type_choose
import Utils.config
from traceback import format_exception
from time import time

class UpdateWeeklyMessage(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.update_message.start()

  def cog_unload(self):
    self.update_message.cancel()

  @tasks.loop(hours=0.5)
  async def update_message(self):
    now = datetime.now(timezone.utc)
    is_weekend = now.weekday() in [5, 6]
    holiday = holiday_type_choose("current_holiday")

    ud = self.bot.get_cog("UpdateData")
    gd = self.bot.get_cog("GetData")
    tm = self.bot.get_cog("TranslateMessage")
    
    try:
      if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
        async with self.bot.db_pool.acquire() as conn:
          query = "SELECT user_id, voted_in FROM topgg"
          data = await conn.fetch(query)
        for row in data:
          user_id = row['user_id']
          voted_in = row['voted_in']
          if time()-voted_in>=36*3600:
            await ud.update_data(user_id, {'streak': 1}, 'topgg', 'user_id', None)
    except Exception:
      pass

    try:
      if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
        async with self.bot.db_pool.acquire() as conn:
          datetime_now = time()
          
          expired_bans = await conn.fetch("""
            SELECT * FROM violations 
            WHERE type = 'ban'
            AND duration IS NOT NULL
            AND (timestamp + duration) <= $1
          """, datetime_now)

          for row in expired_bans:
            user_id = row['user_id']
            guild_id = row['guild_id']

            last_ban = await conn.fetchrow("""
              SELECT * FROM violations 
              WHERE user_id = $1 AND guild_id = $2 AND type = 'ban'
              ORDER BY timestamp DESC LIMIT 1
            """, user_id, guild_id)

            if not last_ban or last_ban['timestamp'] != row['timestamp']:
              continue

            unban_after = await conn.fetchval("""
              SELECT 1 FROM violations 
              WHERE user_id = $1 AND guild_id = $2 AND type = 'unban' AND timestamp > $3
              LIMIT 1
            """, user_id, guild_id, row['timestamp'])

            if unban_after:
              continue
            
            guild = self.bot.get_guild(int(guild_id))
            if guild:
              try:
                member = await self.bot.fetch_user(user_id)
                dm = await member.create_dm()
                user_settings = await gd.get_data(user_id,['language'],'users','user_id',guild)
                language = user_settings['language']
                await dm.send(await tm.translate_message(f"Your Ban Expiration Has Passed.", language)+f"\n"+await tm.translate_message(f"On Server:", language)+f" `{guild.name}`\n"+await tm.translate_message(f"Unban Time:", language)+f" <t:{datetime_now}:F>")
              except Exception:
                pass
              await guild.unban(Object(id=int(user_id)))
              await (self.bot.get_cog("AddViolation")).add_violation(user_id, guild_id, "unban", await tm.translate_message("punishment.ban_expired",language), None, datetime_now, self.bot.user.id)
    except Exception as e:
      print("update weekly message unban exception:\n",''.join(format_exception(type(e), e, e.__traceback__)))

    try:
      if hasattr(self.bot, "db_pool") and self.bot.db_pool:
        servers = len(self.bot.guilds)

        async with self.bot.db_pool.acquire() as conn:
          await conn.execute(
            """
            INSERT INTO public_stats (key, value)
            VALUES
              ('servers', $1),
              ('users', (SELECT CAST(COUNT(DISTINCT user_id) AS TEXT) FROM user_commands))
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value
            """,
            str(servers)
          )
    except Exception as e:
      print(f"update weekly message stats update exception: {e}")

    try:
      try:
        week_message = await self.bot.get_guild(807304463449849938).get_channel(1166364621863661578).fetch_message(1166397100024664114)
      except HTTPException as e:
        print(f"Ошибка при получении еженедельного сообщения: {e}")
        return
  
      bp1 = f"@here\n`{now}`\n"
      if is_weekend:
        if holiday is None:
          message = f"# **Наступили Выходные!**\nВ Магазине Активированы Скидки(`х2`)!\nУспейте До Понедельника Купить Что Хотели :D"
        else:
          message = f"# **Наступили Выходные, А Также Щас Идет Праздник `{holiday['name']}`, Который Начался В `{holiday['start_date'].strftime('%d.%m.%Y')}` И Закончится В `{holiday['end_date'].strftime('%d.%m.%Y')}`(Длительность: *`{holiday['duration']} дней`*)!**\nВ Магазине Активированы Скидки(`х4`)!!!\nУспейте До Понедельника Купить Что Хотели :D"
      else:
        if holiday is None:
          message = f"# **К Сожелению Выходные Закончились Как И Скидки :(**\nВ Магазине Активированы Скидки(`х1`)\n Ждите Следующие Выходные Или Праздники :D"
        else:
          message = f"# **К Сожелению Выходные Закончились Но Щас Идет Праздник `{holiday['name']}`, Который Начался В `{holiday['start_date'].strftime('%d.%m.%Y')}` И Закончится В `{holiday['end_date'].strftime('%d.%m.%Y')}`(Длительность: *`{holiday['duration']} дней`*)!**\nВ Магазине Активированы Скидки(`х2`)\n Ждите Следующие Выходные Если Хотите Ещё Выше Скидки!(Главное Чтоб Праздник Не Прошел) :D"

      if week_message and message not in week_message.content:
        try:
          await week_message.edit(content=bp1+message)
        except HTTPException as e:
          print(f"Ошибка при обновлении еженедельного сообщения: {e}")
        Utils.config.WM_times_updated += 1

    except HTTPException as e:
      print(f"Ошибка HTTP: {e}")

    except Exception as e:
      traceback_msg = ''.join(format_exception(type(e), e, e.__traceback__))
      log = Embed(
        title="Ошибка в Боте",
        description="Ошибка произошла при обновлении в канале: <#1166364621863661578>",
        color=Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.set_author(name="Ошибка")
      log.add_field(name="Канал", value="<#1166364621863661578>", inline=False)
      log.add_field(name="Ошибка", value=f"```py\n{traceback_msg}```", inline=False)
      log.set_footer(text=str(datetime.now()), icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png")

      try:
        await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
      except Exception as ex:
        print(f"Не удалось отправить лог ошибки: {ex}")

  @update_message.before_loop
  async def before_update_message(self):
    await self.bot.wait_until_ready()

def setup(bot: commands.Bot):
  bot.add_cog(UpdateWeeklyMessage(bot))