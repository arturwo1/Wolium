import nextcord
from nextcord import SlashOption, IntegrationType, InteractionContextType
from nextcord.ext import commands
from regex import B
from cogs.utils.get_invite import GetInvite
from cogs.utils.translate_message import TranslateMessage
from cogs.utils.get_data import GetData
from Utils.suffics import suffics
from datetime import datetime,timezone,timedelta
from time import time
import traceback
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown


translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class прокрутка_лидеров(nextcord.ui.View):
  def __init__(self, interaction_user_id, max_page, update_callback, timeout=60*60):
    super().__init__(timeout=timeout)
    self.interaction_user_id = interaction_user_id
    self.page = 0
    self.max_page = max_page
    self.update_callback = update_callback  # Callback для обновления эмбеда
    self.update_buttons()

  def update_buttons(self):
    self.clear_items()
    back_button = nextcord.ui.Button(
      style=nextcord.ButtonStyle.primary,
      label="◀",
      disabled=self.page <= 0
    )
    back_button.callback = self.button1_callback
    self.add_item(back_button)
    forward_button = nextcord.ui.Button(
      style=nextcord.ButtonStyle.primary,
      label="▶",
      disabled=self.page >= self.max_page
    )
    forward_button.callback = self.button2_callback
    self.add_item(forward_button)

  async def button1_callback(self, interaction: nextcord.Interaction):
    user_id = interaction.user.id
    if user_id != self.interaction_user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    if self.page > 0:
      self.page -= 1
      self.update_buttons()
      await self.update_callback(self.page)
      await interaction.edit_original_message(view=self)

  async def button2_callback(self, interaction: nextcord.Interaction):
    user_id = interaction.user.id
    if user_id != self.interaction_user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    if self.page < self.max_page:
      self.page += 1
      self.update_buttons()
      await self.update_callback(self.page)
      await interaction.edit_original_message(view=self)

class Leaders(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  @nextcord.slash_command(description="Просмотр ЛидерБордов",
    name_localizations=translate_to_all_languages('leaders', 'name'),
    description_localizations=translate_to_all_languages('View LeaderBoards', 'description'),
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
  async def лидеры(self,
    interaction: nextcord.Interaction,
    сортировка: str=SlashOption(name="sorting", description="Select List By Which to Sort LeaderBoard.",choices={"Total Money":"total_balance","Bank Balance":"bank_balance","Balance":"balance","Upgrade": "upgrade","Total XP":"xp", "LvL":"LvL", "Experience":"XP_now", "Message Count":"messages", "Time In Voice":"voice", "Votes":"votes", "Streak Votes":"streak"},required=True, name_localizations=translate_to_all_languages('sorting', 'name'), description_localizations=translate_to_all_languages('Select List By Which to Sort LeaderBoard.', 'description'), choice_localizations=translate_to_all_languages({"Total Money":"total_balance","Bank Balance":"bank_balance","Balance":"balance","Upgrade": "upgrade","Total XP":"xp", "LvL":"LvL", "Experience":"XP_now", "Message Count":"messages", "Time In Voice":"voice", "Votes":"votes", "Streak Votes":"streak"}, 'choice')),
    тип: str=SlashOption(name="type", description="Тип ЛидерБорда",choices={"World":"world","Server":"server","Top Servers":"tservers"},required=True, name_localizations=translate_to_all_languages('type', 'name'), description_localizations=translate_to_all_languages('LeaderBoard Type', 'description'), choice_localizations=translate_to_all_languages({"World":"world","Server":"server","Top Servers":"tservers"}, 'choice'),default='server'),
  ):
    global super_total_value
    try:
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
      
      user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']
      original_user_variation = user_settings['variation']
      
      if сортировка == "total_balance":
        sort_key = 'balance, user_data.bank_balance'
      elif сортировка == "bank_balance":
        sort_key = 'bank_balance'
      elif сортировка == "balance":
        sort_key = 'balance'
      elif сортировка == "upgrade":
        sort_key = 'upgrade'
      elif сортировка == "xp":
        sort_key = 'xp'
      elif сортировка == "LvL":
        sort_key = 'xp'
      elif сортировка == "XP_now":
        sort_key = 'xp'
      elif сортировка=="messages":
        sort_key = 'messages'
      elif сортировка=="voice":
        sort_key = 'voice'
      elif сортировка=='votes':
        sort_key = 'votes'
      elif сортировка=='streak':
        sort_key = 'streak'
      else:
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка И Кажется",language)+f" `{сортировка}` "+await (TranslateMessage(self.bot)).translate_message(f"Нет В Базе Данных, Отправьте Это На Сервере Поддержки [**`Меня`**](https://discord.gg/MXupeAApza).",language), ephemeral=True)
        return

      users_and_balances = []
      super_total_value = 0
      sort_value = 0

      handler = await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message("Подождите.", language))

      invite = await (GetInvite(self.bot)).invite(interaction.guild)

      if тип in ['server', 'world']:
        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          async with self.bot.db_pool.acquire() as conn:
            #  if sort_key in ['votes','streak']
            query = f"""
            SELECT user_data.user_id, 
              {f'user_data.{sort_key}' if sort_key not in ['messages','voice','votes','streak'] else 'COUNT(*) AS messages_count' if sort_key=='messages' else 'COALESCE(SUM(time_spent), \'0 seconds\'::interval) AS total_time' if sort_key=='voice' else f"topgg.{sort_key}"}, 
              users.telegram_id, 
              users.discord_id, 
              users.variation 
            FROM user_data 
            JOIN users ON user_data.user_id = users.user_id 
            {'LEFT JOIN messages ON user_data.user_id = messages.user_id' if sort_key == 'messages' else 'LEFT JOIN voice ON user_data.user_id = voice.user_id' if sort_key=='voice' else f'LEFT JOIN topgg ON user_data.user_id = topgg.user_id' if sort_key in ['votes','streak'] else ''}
            GROUP BY user_data.user_id, users.telegram_id, users.discord_id, users.variation{f', topgg.{sort_key}' if sort_key in ['votes','streak'] else ''}
            """
            data = await conn.fetch(query)
        else:
          return
        
        for row in data:
          user_id = row['user_id']
          telegram = True if row['telegram_id'] else False
          discord = True if row['discord_id'] else False
          variation = row['variation']
          if (тип=='server' and str(user_id) in [str(member.id) for member in (interaction.guild.members if interaction.guild else [interaction.user,self.bot.user])]) or тип=='world':
            if сортировка=="total_balance":
              sort_value = row['balance']+row['bank_balance']
            elif сортировка=="LvL" or сортировка=="XP_now":
              sort_value1 = row['xp']
              XP_now = sort_value1
              LvL = 0
              while XP_now>25*LvL:
                XP_now-=25*LvL
                LvL+=1
              sort_value = LvL if сортировка=="LvL" else XP_now
            elif сортировка=='messages':
              sort_value = row.get("messages_count", 0)
            elif сортировка=='voice':
              sort_value:timedelta = row.get("total_time", 0)
              if sort_value:
                sort_value = sort_value.total_seconds()
              else:
                sort_value = 0
            else:
              sort_value = row.get(sort_key, 0)
            if not sort_value:
              continue
            super_total_value += sort_value
            users_and_balances.append((int(user_id), sort_value, variation, discord, telegram))
      else:
        for guild in self.bot.guilds:
          users = [member.id for member in guild.members]
          sort_value = 0
          if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
            async with self.bot.db_pool.acquire() as conn:
              if сортировка == "total_balance":
                sort_key = 'balance, bank_balance'
              query = f"""
              SELECT user_data.user_id, 
                  {f'user_data.{sort_key}' if sort_key not in ['messages','voice','votes','streak'] else 'COUNT(*) AS messages_count' if sort_key=='messages' else 'COALESCE(SUM(time_spent), \'0 seconds\'::interval) AS total_time' if sort_key=='voice' else f"topgg.{sort_key}"}, 
                  users.telegram_id, 
                  users.discord_id, 
                  users.variation 
              FROM user_data 
              JOIN users ON user_data.user_id = users.user_id 
              {'LEFT JOIN messages ON user_data.user_id = messages.user_id' if сортировка == 'messages' else 'LEFT JOIN voice ON user_data.user_id = voice.user_id' if sort_key == 'voice' else f'LEFT JOIN topgg ON user_data.user_id = topgg.user_id' if sort_key in ['votes','streak'] else ''}
              WHERE user_data.user_id IN ({','.join(map(str, users))})
              GROUP BY user_data.user_id, users.telegram_id, users.discord_id, users.variation{f', topgg.{sort_key}' if sort_key in ['votes','streak'] else ''}
              """
              data = await conn.fetch(query)
          else:
            return

          for row in data:
            user_id = row['user_id']
            telegram = True if row['telegram_id'] else False
            discord = True if row['discord_id'] else False
            variation = row['variation']

            if сортировка == "total_balance":
              sort_value += row['balance'] + row['bank_balance']
            elif сортировка in ["LvL", "XP_now"]:
              XP_now = row['xp']
              LvL = XP_now // 25
              XP_now = XP_now % 25
              sort_value += LvL if сортировка == "LvL" else XP_now
            elif сортировка == 'messages':
              sort_value += row.get("messages_count", 0)
            elif сортировка == 'voice':
              sort_value1 = row.get("total_time", 0)
              if isinstance(sort_value1, timedelta):
                sort_value += sort_value1.total_seconds()
              else:
                sort_value += 0
            else:
              sort_value += row.get(sort_key, 0) if row.get(sort_key, 0) else 0

            super_total_value += sort_value
          users_and_balances.append((int(guild.id), sort_value, variation, discord, telegram))

      users_and_balances.sort(key=lambda x: x[1], reverse=True)

      max_page = (len(users_and_balances) - 1) // 10

      async def update_leaderboard(page:int):
        global super_total_value
        lead = nextcord.Embed(
          title=await (TranslateMessage(self.bot)).translate_message(('Топы Мира' if тип=='world' else 'Топы Сервера' if тип=='server' else 'Топ Серверов'), language),
          description=await (TranslateMessage(self.bot)).translate_message(f"Сортировка По:", language)+f" **{сортировка}**",
          color=nextcord.Color.yellow(),
          timestamp=datetime.now(timezone.utc)
        )
        super_total_value = 0 if not super_total_value else super_total_value if сортировка not in ['voice'] else (timedelta(seconds=super_total_value) if isinstance(super_total_value, (int, float)) else super_total_value)
        lead.set_author(
          name=await (TranslateMessage(self.bot)).translate_message(f"Всего", language)+f" {сортировка}: {await suffics(number=super_total_value, variation=original_user_variation) if сортировка not in ['voice'] and super_total_value!=0 else f'{super_total_value.days}d {super_total_value.seconds // 3600}h {(super_total_value.seconds % 3600) // 60}m' if super_total_value!=0 else super_total_value}",
          icon_url=interaction.user.display_avatar.url
        )

        start_index = page * 10
        end_index = min(start_index + 10, len(users_and_balances))

        for rank, (user_id, sort_value, variation, discord, telegram) in enumerate(users_and_balances[start_index:end_index], start=start_index + 1):
          if interaction.guild:
            str_badge_in_description = ''
            str_badge_in_description += '<:guild:1358530418940575976> ' if interaction.guild and interaction.guild.get_member(interaction.user.id) else ''
            str_badge_in_description += '<a:on_discord:1318709863999606817>' if (interaction.guild.get_member(user_id) or self.bot.get_user(user_id)) and discord else ''
            str_badge_in_description += '<a:on_telegram:1318946754661453834>' if (interaction.guild.get_member(user_id) or self.bot.get_user(user_id)) and telegram else ''
            euro = '€' if сортировка in ['balance','bank_balance','total_balance'] else ''
            sort_value = sort_value if сортировка not in ['voice'] else timedelta(seconds=sort_value)
            if interaction.guild.get_member(user_id):
              lead.add_field(
                name=f"**#{rank}**. {str_badge_in_description}{interaction.guild.get_member(user_id).mention}",
                value=f"{euro}{await suffics(number=sort_value, variation=variation) if сортировка not in ['voice'] else f'{sort_value.days}d {sort_value.seconds // 3600}h {(sort_value.seconds % 3600) // 60}m'}",
                inline=False
              )
            elif self.bot.get_guild(user_id):
              invite = await (GetInvite(self.bot)).invite(self.bot.get_guild(user_id),'leaders')
              lead.add_field(
                name=f"**#{rank}**. {(f'[**`{self.bot.get_guild(user_id).name}`**]({invite})') if invite not in ['Нет инвайтов','Нет прав для просмотра инвайтов','ошибка','ЛС'] else f'**`{self.bot.get_guild(user_id).name}`**'}",
                value=f"{euro}{await suffics(number=sort_value, variation=variation) if сортировка not in ['voice'] else f'{sort_value.days}d {sort_value.seconds // 3600}h {(sort_value.seconds % 3600) // 60}m'}",
                inline=False
              )
            else:
              lead.add_field(
                name=f"**#{rank}**. {str_badge_in_description}<@{user_id}>",
                value=f"{euro}{await suffics(number=sort_value, variation=variation) if сортировка not in ['voice'] else f'{sort_value.days}d {sort_value.seconds // 3600}h {(sort_value.seconds % 3600) // 60}m'}",
                inline=False
              )
          else:
            lead.add_field(
              name=f"**#{rank}**. ❓ {str_badge_in_description}<@{user_id}>",
              value=f"{{euro}}{round(sort_value, 2) if сортировка not in ['voice'] else f'{sort_value.days}d {sort_value.seconds // 3600}h {(sort_value.seconds % 3600) // 60}m'}",
              inline=False
            )

          lead.set_footer(
            text=await (TranslateMessage(self.bot)).translate_message(f"Страница", language)+f" {page + 1}/{max_page + 1}",
            icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
          )
          try:
            await handler.edit(None, embed=lead)
          except Exception:
            await interaction.followup.send(embed=lead,ephemeral=True)

      view = прокрутка_лидеров(interaction.user.id, max_page, update_leaderboard)
      try:
        await handler.edit(await (TranslateMessage(self.bot)).translate_message("Подождите.", language), view=view)
      except Exception:
        handler = await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Подождите.", language), view=view,ephemeral=True)
      await update_leaderboard(0)

    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/лидеры** `сортировка`  **{сортировка}** `тип` **{тип}**||",
        color=nextcord.Colour.red(),
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
      try:
        await interaction.response.send_message(await(TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
      except Exception:
        await interaction.followup.send(await(TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

  setattr(лидеры,"extras",{"description": "Показывает список лидеров в любом вам удобном формате."})

def setup(bot: commands.Bot):
  bot.add_cog(Leaders(bot))