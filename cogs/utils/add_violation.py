import nextcord
from nextcord.ext import commands
from datetime import datetime, timedelta, timezone
import traceback
from cogs.utils.ensure_user_exists import EnsureUserExists
from cogs.utils.ensure_guild_exists import EnsureGuildExists
from cogs.utils.ensure_guild_user_exists import EnsureGuildUserExists
from cogs.utils.ensure_user_data_exists import EnsureUserDataExists
from cogs.utils.get_data import GetData
from cogs.utils.get_invite import GetInvite
from cogs.utils.send_embed import SendEmbed
from cogs.utils.translate_message import TranslateMessage
from Utils.config import users
from asyncio import sleep

class AddViolation(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  async def add_violation(self, user_id:int, guild_id:int, type_:str, reason:str, duration:int, timestamp:int, mod_id:int):
    try:
      duration = duration if isinstance(duration, (int,float)) else None
      guild = self.bot.get_guild(guild_id)
      user = self.bot.get_user(user_id)
      mod = guild.get_member(mod_id)
      language = guild.preferred_locale if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'en' if guild.preferred_locale=='en-US' or guild.preferred_locale=='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'es' if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale=='es-ES' and guild.preferred_locale!='sv-SE' else 'sv'
      if type_!='unban' and (mod!=guild.owner and mod.guild_permissions.value<guild.get_member(user_id).guild_permissions.value):
        try:
          await mod.send(await (TranslateMessage(self.bot)).translate_message(f"Вы не можете выдать наказание пользователю {user.mention}.",language))
          return
        except Exception:
          return
      if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
        while True:
          async with self.bot.db_pool.acquire() as conn:
            if user_id not in users:
              await (EnsureUserExists(self.bot)).ensure_user_exists(user_id,user.name,language,guild) 
              await (EnsureGuildExists(self.bot)).ensure_guild_exists(guild.id)
              await (EnsureGuildUserExists(self.bot)).ensure_guild_user_exists(guild.id, user_id)
              await (EnsureUserDataExists(self.bot)).ensure_user_data_exists(user_id, guild)
              users.add(user_id)

            await conn.execute(
              "INSERT INTO violations (user_id, guild_id, type, reason, duration, timestamp, mod_id) "
              "VALUES ($1, $2, $3, $4, $5, $6, $7)",
              user_id, guild_id, type_, reason, duration, timestamp, mod_id
            )
            break
      else:
        await sleep(10)
      guild_config = await (GetData(self.bot)).get_data(guild_id,['mod_log_channel'],'guild_settings','guild_id',guild)
      mod_log_channel = guild_config['mod_log_channel']
      if mod_log_channel and guild and guild.get_channel(mod_log_channel):
        guild_locale = guild.preferred_locale
        mod_lang = guild_locale if guild_locale !='en-US' and guild_locale !='en-GB' and guild_locale !='es-ES' and guild_locale !='sv-SE' else 'en' if guild_locale =='en-US' or guild_locale =='en-GB' and guild_locale !='es-ES' and guild_locale !='sv-SE' else 'es' if guild_locale !='en-US' and guild_locale !='en-GB' and guild_locale =='es-ES' and guild_locale !='sv-SE' else 'sv'
        fields = [({
            'name':await (TranslateMessage(self.bot)).translate_message('Пользователь',mod_lang),
            'value':f"{user.id} | {user.mention} | {user.name}",
            'inline':True
          } if user else {}),
          ({
            'name':await (TranslateMessage(self.bot)).translate_message('Модератор',mod_lang),
            'value':f"{mod.id} | {mod.mention} | {mod.name}",
            'inline':True
          } if mod else {}),
          {
            'name':await (TranslateMessage(self.bot)).translate_message('Тип',mod_lang),
            'value':f"**`{await (TranslateMessage(self.bot)).translate_message(type_,mod_lang)}`**",
            'inline':True
          },
          {
            'name':await (TranslateMessage(self.bot)).translate_message('Причина',mod_lang),
            'value':f"**`{reason}`**",
            'inline':True
          },
          ({
            'name':await (TranslateMessage(self.bot)).translate_message('Длительность',mod_lang),
            'value':f"**<t:{duration+timestamp}:R>**(**`{timedelta(seconds=duration)}`**)",
            'inline':True
          } if duration else {}),
        ]
        await (SendEmbed(self.bot)).send_embed(
          title=await (TranslateMessage(self.bot)).translate_message("Выдача Нарушения",mod_lang),
          description=f"**{mod.mention}** "+await (TranslateMessage(self.bot)).translate_message("Выдал",mod_lang)+f" **`{await (TranslateMessage(self.bot)).translate_message(type_,mod_lang)}`** "+f"**{user.mention}** "+await (TranslateMessage(self.bot)).translate_message("По Причине",mod_lang)+f" {reason}"+(' '+await (TranslateMessage(self.bot)).translate_message("На",mod_lang)+f" **<t:{duration+timestamp}:R>**." if duration else '.'),
          color=nextcord.Colour.red(),
          fields=fields,
          footer_text=await (TranslateMessage(self.bot)).translate_message("Выдача Нарушения",mod_lang),
          author_text=mod.name,
          author_icon=mod.display_avatar.url,
          guild_id=guild_id,
          channel_id=mod_log_channel
        )
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
        title=f"Postgresql | Ошибка для добавления нарушения",
        description=(f"{e}")[:500],
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      if guild:
        invite = await (GetInvite(self.bot)).invite(guild)
        log.add_field(
          name="Сервер",
          value=f"{guild.id} | {invite} | {guild.name}" if guild else "ЛС",
          inline=False
        )
      if user:
        log.add_field(
          name="Пользователь",
          value=f"{user_id} | {user.mention} | {user.name}",
          inline=True
        )
      log.add_field(
        name="Данные",
        value=f"user_id: {user_id}\nguild_id: {guild_id}\ntype_: {type_}\nreason: {reason}\nduration: {duration}\ntimestamp: {timestamp}\nmod_id: {mod_id}",
        inline=True
      )
      log.set_author(
        name=f"ЕРРОР",
      )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
          name="Ошибка",
          value=f"```py\n{traceback_msg[i:i+1000]}```",
          inline=False
        )
      log.set_footer(
        text=f"{str(datetime.now())}",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
    return

def setup(bot:commands.Bot):
  bot.add_cog(AddViolation(bot))