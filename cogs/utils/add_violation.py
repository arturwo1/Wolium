import nextcord
from nextcord.ext import commands
from datetime import datetime, timedelta, timezone
import traceback
from Utils.config import users
from asyncio import sleep

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class AddViolation(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  async def add_violation(self, user_id:int, guild_id:int, type_:str, reason:str, duration:int, timestamp:int, mod_id:int):
    try:
      duration = duration if isinstance(duration, (int,float)) else None
      guild = self.bot.get_guild(guild_id)
      user = self.bot.get_user(user_id)
      mod = guild.get_member(mod_id)
      language = _get_locale(guild.preferred_locale)

      tm = self.bot.get_cog("TranslateMessage")

      if type_!='unban' and (mod!=guild.owner and mod.guild_permissions.value<guild.get_member(user_id).guild_permissions.value):
        try:
          await mod.send(await tm.translate_message("punishment.insufficient_perms", language, variables={"user": user.mention}))
          return
        except Exception:
          return
      if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
        while True:
          async with self.bot.db_pool.acquire() as conn:
            if user_id not in users:
              await self.bot.get_cog("EnsureGuildExists").ensure_guild_exists(guild.id)
              await self.bot.get_cog("EnsureUserExists").ensure_user_exists(user_id,user.name,language,guild) 
              users.add(user_id)

            await conn.execute(
              "INSERT INTO violations (user_id, guild_id, type, reason, duration, timestamp, mod_id) "
              "VALUES ($1, $2, $3, $4, $5, $6, $7)",
              user_id, guild_id, type_, reason, duration, timestamp, mod_id
            )
            break
      else:
        await sleep(10)
      guild_config = await self.bot.get_cog("GetData").get_data(guild_id,['mod_log_channel'],'guild_settings','guild_id',guild)
      mod_log_channel = guild_config['mod_log_channel']
      if mod_log_channel and guild and guild.get_channel(mod_log_channel):
        guild_locale = guild.preferred_locale
        mod_lang = guild_locale if guild_locale !='en-US' and guild_locale !='en-GB' and guild_locale !='es-ES' and guild_locale !='sv-SE' else 'en' if guild_locale =='en-US' or guild_locale =='en-GB' and guild_locale !='es-ES' and guild_locale !='sv-SE' else 'es' if guild_locale !='en-US' and guild_locale !='en-GB' and guild_locale =='es-ES' and guild_locale !='sv-SE' else 'sv'
        fields = [({
            'name':await tm.translate_message('general.user',mod_lang),
            'value':f"{user.id} | {user.mention} | {user.name}",
            'inline':True
          } if user else {}),
          ({
            'name':await tm.translate_message('general.moderator',mod_lang),
            'value':f"{mod.id} | {mod.mention} | {mod.name}",
            'inline':True
          } if mod else {}),
          {
            'name':await tm.translate_message('general.type',mod_lang),
            'value':f"**`{await tm.translate_message(type_,mod_lang)}`**",
            'inline':True
          },
          {
            'name':await tm.translate_message('general.reason',mod_lang),
            'value':f"**`{reason}`**",
            'inline':True
          },
          ({
            'name':await tm.translate_message('general.duration_label',mod_lang),
            'value':f"**<t:{duration+timestamp}:R>**(**`{timedelta(seconds=duration)}`**)",
            'inline':True
          } if duration else {}),
        ]
        duration_text = ''
        if duration:
          on_text = await tm.translate_message("general.for", mod_lang)
          duration_text = f" {on_text} **<t:{duration+timestamp}:R>**."
        
        description = await tm.translate_message(
          "punishment.violation_description",
          mod_lang,
          variables={
            "moderator": mod.mention,
            "type": await tm.translate_message(type_, mod_lang),
            "user": user.mention,
            "reason": reason,
            "duration_text": duration_text
          }
        )
        
        await self.bot.get_cog("SendEmbed").send_embed(
          title=await tm.translate_message("punishment.issue_violation",mod_lang),
          description=description,
          color=nextcord.Colour.red(),
          fields=fields,
          footer_text=await tm.translate_message("punishment.issue_violation",mod_lang),
          author_text=mod.name,
          author_icon=mod.display_avatar.url,
          guild_id=guild_id,
          channel_id=mod_log_channel
        )
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
        title="PostgreSQL | Error adding violation",
        description=(f"{e}")[:500],
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      if guild:
        invite = await self.bot.get_cog("GetInvite").invite(guild)
        log.add_field(
          name="Server",
          value=f"{guild.id} | {invite} | {guild.name}" if guild else "DM",
          inline=False
        )
      if user:
        log.add_field(
          name="User",
          value=f"{user_id} | {user.mention} | {user.name}",
          inline=True
        )
      log.add_field(
        name="Data",
        value=f"user_id: {user_id}\nguild_id: {guild_id}\ntype_: {type_}\nreason: {reason}\nduration: {duration}\ntimestamp: {timestamp}\nmod_id: {mod_id}",
        inline=True
      )
      log.set_author(
        name=f"ERROR",
      )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
          name="Error",
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