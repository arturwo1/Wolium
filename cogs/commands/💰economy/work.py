from os import getenv
from aiohttp import ClientSession
from nextcord import SlashOption, IntegrationType, InteractionContextType, slash_command, Interaction, Embed, Color, ButtonStyle
from nextcord.ext import commands
from nextcord.ui import View, Button
from Utils.suffics import suffics
from datetime import datetime,timedelta,timezone
from time import time
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from random import uniform
from traceback import format_exception

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class VoteView(View):
  def __init__(self, user_id:int, language:str, voted:bool, bot, timeout=60*5):
    super().__init__(timeout=timeout)
    self.language = language
    self.user_id = user_id
    self.voted = voted
    self.bot = bot

    if not self.voted:
      vote = Button(
        row=1,
        label=translate_to_all_languages("economy.vote_button_label", 'message', self.language),
        style=ButtonStyle.url,
        url="https://top.gg/bot/1051105900116574250/vote"
      )
      self.add_item(vote)

class Work(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
  
  @slash_command(
    description="Earn coins by working",
    name_localizations=translate_to_all_languages('economy.work_name', 'name'),
    description_localizations=translate_to_all_languages('economy.work_desc', 'description'),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],)
  async def work(self,
    interaction: Interaction,
    boost: bool=SlashOption(name="boost", description="Activate double earnings if available", required=False, name_localizations=translate_to_all_languages('economy.boost_name', 'name'), description_localizations=translate_to_all_languages('economy.boost_desc', 'description')),
  ):
    try:
      user_id = interaction.user.id
      current_time = time()
      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")
      ud = self.bot.get_cog("UpdateData")
      lang = _get_locale(interaction.locale)

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(await tm.translate_message("error.rate_limit", lang, variables={"time": f"<t:{round(last_command_time + 10)}:R>"}), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      user_settings = await gd.get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']
      user_data = await gd.get_data(user_id,['bank_balance','balance','x2workamount','upgrade'],'user_data','user_id',interaction.guild)
      
      bank_balance = user_data['bank_balance']
      balance = user_data['balance']
      x2workamount = user_data['x2workamount']
      upgrade = user_data['upgrade']
      variation = user_settings['variation']

      sbank_balance = await suffics(number=bank_balance, variation=variation)
      sbalance = await suffics(number=balance, variation=variation)

      if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
        async with self.bot.db_pool.acquire() as conn:
          wquery = "SELECT timestamp FROM cooldowns WHERE user_id = $1 AND command = $2"
          equery = "INSERT INTO cooldowns (user_id, command, timestamp) VALUES ($1, $2, $3) ON CONFLICT (user_id, command) DO UPDATE SET timestamp = EXCLUDED.timestamp"
          worka = await conn.fetchval(wquery, user_id, 'work')
          if worka is None:
            await conn.execute(equery, user_id, 'work', int(time()-60*40))
            worka = await conn.fetchval(wquery, user_id, 'work')
      else:
        return

      time_since_last_usage=time()-worka
      if time_since_last_usage<(60*39):
        remaining = int((60*39) - time_since_last_usage)
        await interaction.response.send_message(await tm.translate_message("economy.cooldown_remaining", language, variables={"time": str(timedelta(seconds=remaining))[:-4]}), ephemeral=True)
        return
      else:
        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          async with self.bot.db_pool.acquire() as conn:
            await conn.execute(equery, user_id, 'work', int(time()))
        else:
          return

      try:
        work_send_message = await interaction.response.send_message(await tm.translate_message('common.loading', language))
      except Exception:
        work_send_message = await interaction.followup.send(await tm.translate_message('common.loading', language), ephemeral=True)

      invite = await gi.invite(interaction.guild)

      if boost==True and x2workamount>0:
        буст=2
        x2workamount = x2workamount-1
        data = {
          'x2workamount': x2workamount
        }
        await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
      else:
        boost=False
        буст=1
      
      headers = {
        "Authorization": getenv("TOPGG_DISCORDBOT_TOKEN_API"),
        'Content-Type': 'application/json'
      }
      async with ClientSession() as session:
        async with session.get(f"https://top.gg/api/bots/{self.bot.user.id}/check?userId={user_id}", headers=headers) as resp:
          if resp.status == 200:
            data = await resp.json()
            user_vote = data.get("voted") == 1
          else:
            user_vote = False
      if user_vote:
        vote=1.5
      else:
        vote=1
      
      uti = await gd.get_data(user_id,['votes','streak','voted_in'],'topgg','user_id',None)
      user_votes:int = uti['votes']+1
      streak:int = uti['streak']
      voted_in_day_ago:float = uti['voted_in']

      if 12*60*60<=time()-voted_in_day_ago<=12*60*60+12*60*60:
        streak = streak
      else:
        streak = 1
        await ud.update_data(user_id, {'streak': streak}, 'topgg', 'user_id', None)
      
      total_votes = 0
      monthly_votes = 0
      async with ClientSession() as session:
        async with session.get(f"https://top.gg/api/bots/{self.bot.user.id}", headers={"Authorization": getenv("TOPGG_DISCORDBOT_TOKEN_API"),'Content-Type': 'application/json'}) as resp:
          if resp.status == 200:
            data = await resp.json()
            total_votes = data.get("points", 0)
            monthly_votes = data.get("monthlyPoints", 0)
          else:
            pass

      work_amount = uniform(9.26, 13.98)*(3.5*(1.5*upgrade)**1.5)*(1+буст*(0.05*((int(monthly_votes)**0.5)+(int(total_votes)**0.1)+(0.5*int(streak))+(0.1*int(user_votes)))))*vote

      total_balance = bank_balance+balance
      bank_balance = bank_balance+work_amount
      data = {
        'bank_balance': bank_balance+work_amount
      }
      await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)

      sbank_balance = await suffics(number=bank_balance, variation=variation)
      sbalance = await suffics(number=balance, variation=variation)
      stotal_balance = await suffics(number=total_balance, variation=variation)
      swork_amount = await suffics(number=work_amount, variation=variation)

      view = VoteView(interaction.user.id, language, user_vote, self.bot)

      boost_status = await tm.translate_message("economy.boost_active", language) if boost else await tm.translate_message("economy.boost_inactive", language)
      vote_status = await tm.translate_message("economy.voted", language) if user_vote else await tm.translate_message("economy.not_voted", language)

      work = Embed(
        title=await tm.translate_message("economy.work_embed_title", language, variables={"amount": swork_amount, "boost": boost_status, "vote": vote_status}),
        description=await tm.translate_message("economy.work_embed_desc", language),
        color=Color.green(),
        timestamp=datetime.now(timezone.utc)
      )
      work.set_author(
        name=await tm.translate_message("economy.work_author", language, variables={"name": interaction.user.name}),
        icon_url=f"{interaction.user.display_avatar.url}"
      )
      work.add_field(
        name=await tm.translate_message("economy.total_balance_label", language),
        value=f"`€{stotal_balance}`",
        inline=False
      )
      work.add_field(
        name=await tm.translate_message("economy.bank_balance_label", language),
        value=f"`€{sbank_balance}`",
        inline=False
      )
      work.add_field(
        name=await tm.translate_message("economy.hand_balance_label", language),
        value=f"`€{sbalance}`",
        inline=False
      )
      work.add_field(
        name=await tm.translate_message("economy.double_earnings_boosts_left", language),
        value=f"`{x2workamount}`",
        inline=False
      )
      work.add_field(
        name=await tm.translate_message("economy.upgrade_label", language),
        value=f"`{upgrade}`",
        inline=False
      )
      work.set_footer(
        text=await tm.translate_message("economy.cooldown_footer", language, variables={"minutes": "minutes"}),
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      try:
        await work_send_message.edit("", embed=work, view=view)
      except Exception:
        await interaction.followup.send(embed=work,view=view,ephemeral=True)

    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/работать** `boost`  **{boost}**",
        color=Color.red(),
        timestamp=datetime.now(timezone.utc)
      )

      log.set_author(
        name=f"Сервер ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=f"{interaction.user.display_avatar.url}"
      )
      if interaction.guild:
        log.add_field(
          name="Сервер",
          value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "ЛС" if interaction.guild else "ЛС",
          inline=False
        )
      log.add_field(
        name="Канал",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
        inline=False
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
      try:
        await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      except Exception:
        await interaction.followup.send(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)

  setattr(work,"extras",{"description": "Самый простой способ получить экономическую валюту которая очень важна в моих командах, использование этой команды самый простой."})

def setup(bot: commands.Bot):
  bot.add_cog(Work(bot))
