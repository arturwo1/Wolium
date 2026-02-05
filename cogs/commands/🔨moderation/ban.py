from time import time
from nextcord.ext.commands import Cog, Bot
from nextcord import slash_command, SlashOption, Interaction, Member, Embed, Colour
from Utils.parse_time import parse_time
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot, slash_command_cooldown
import Utils.translate_to_all_languages
from cogs.utils.add_violation import AddViolation
from cogs.utils.get_data import GetData
from cogs.utils.translate_message import TranslateMessage
from datetime import datetime, timedelta, timezone
from traceback import format_exception

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class Ban(Cog):
  def __init__(self, bot:Bot):
    self.bot:Bot=bot

  @slash_command(default_member_permissions=16,
  description="Команда Что-Бы Ban Пользователя",
  name_localizations=translate_to_all_languages('ban', 'name'),
  description_localizations=translate_to_all_languages('Command to Ban a User.', 'description'))
  async def бан(self,
    interaction: Interaction,
    участник: Member=SlashOption(name="участник", description="Ник Участника Которого Хотите Ban.",required=True, name_localizations=translate_to_all_languages('участник', 'name'), description_localizations=translate_to_all_languages('Nickname of the Member you want to ban.', 'description')),
    причина: str=SlashOption(name="причина", description="Причина Бана.",required=True, name_localizations=translate_to_all_languages('причина', 'name'), description_localizations=translate_to_all_languages('описание', 'description'),max_length=128),
    удалить_сообщения: str=SlashOption(name="удалить_сообщения", description="Сколько Хотите Удалить Сообщений Пользователя(s,m,h,d,w).",required=False, name_localizations=translate_to_all_languages('удалить_сообщения', 'name'), description_localizations=translate_to_all_languages('Сколько Хотите Удалить Сообщений Пользователя(s,m,h,d,w).', 'description'),default=0),
    длительность: str=SlashOption(name="длительность", description="Длительность Бана(s,m,h,d,w).",required=False, name_localizations=translate_to_all_languages('длительность', 'name'), description_localizations=translate_to_all_languages('Длительность Бана(s,m,h,d,w).', 'description'),default=None),
  ):
    try:
      if ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://sites.google.com/view/arturwolium/main-page/rules) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
        return
      user_id = interaction.user.id
      member_id = участник.id
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

      send_ban_message = await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message("Загрузка Данных", language),ephemeral=True)
      if str(member_id)==str(user_id):
        await send_ban_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Зачем Банить Самого Себя...", language))
        return
      if interaction.guild.me.guild_permissions.ban_members==False:
        await send_ban_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Недостаточно Прав(Банить/Отправлять Сообщения) У Меня.", language))
        return
      if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<interaction.guild.get_member(member_id).guild_permissions.value:
        await send_ban_message.edit(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У", language)+f" **{участник.mention}**.")
        return
      
      длительность = parse_time(длительность)
        
      mod_chan = self.bot.get_guild(807304463449849938).get_channel(839208959284871179)
      embe = Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/бан** `участник`  **{участник}** `причина`  **{причина}** `удалить_сообщения`  **{удалить_сообщения}** `длительность`  **{длительность}**||",
        color=Colour.dark_red(),
        timestamp=datetime.now(timezone.utc)
      )
      embe.set_author(
        name=f"Сервер ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=f"{interaction.user.display_avatar.url}"
      )
      embe.add_field(
        name="Сервер",
        value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
        inline=False
      )
      embe.add_field(
        name="Канал",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
        inline=False
      )
      embe.add_field(
        name="Модератор Забанил:",
        value=f"{участник}",
        inline=False
      )
      embe.add_field(
        name="Причина:",
        value=f"{причина}",
        inline=False
      )
      embe.add_field(
        name="Удалено Сообщений Время:",
        value=f"{удалить_сообщения}",
        inline=False
      )
      embe.add_field(
        name="Длитеьность:",
        value=f"{длительность}",
        inline=False
      )
      embe.set_footer(
        text=f"{str(datetime.now())}",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      await mod_chan.send(embed=embe)
    
      try:
        try:
          member = await self.bot.fetch_user(member_id)
          dm = await member.create_dm()
          await dm.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Забанены По Причине:", language))+f" `{причина}`"
        except Exception:
          pass
        success_ban = Embed(
          title=await (TranslateMessage(self.bot)).translate_message(f"Бан", language),
          description=f"""
          **{await (TranslateMessage(self.bot)).translate_message("Участник",language)}**: **`{участник}`**(**{участник.mention}**)
          **{await (TranslateMessage(self.bot)).translate_message("Причина",language)}**: **`{причина}`**
          **{await (TranslateMessage(self.bot)).translate_message("Длительность", language)}**: **`{timedelta(seconds=длительность)}`**
          """,
          color=Colour.green(),
          timestamp=datetime.now(timezone.utc)
        )
        success_ban.set_footer(
          text=f"Ban",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )

        await interaction.guild.ban(user=участник,reason=причина,delete_message_seconds=удалить_сообщения)
        timestamp = int(interaction.created_at.timestamp())
        await (AddViolation(self.bot)).add_violation(member_id, interaction.guild.id, "ban", причина, длительность, timestamp, user_id)
        
        await send_ban_message.edit('',embed=success_ban)
      except Exception as e:
        await send_ban_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Нет Прав У Бота(скорее всего его роль ниже по иерархии чем", language))+f" **{участник.mention}**).\n||**Ошибка: `{e}`**||"
    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/бан** `участник`  **{участник}** `причина`  **{причина}** `удалить_сообщения`  **{удалить_сообщения}** `длительность`  **{длительность}**||",
        color=Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.set_author(
        name=f"Сервер ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=f"{interaction.user.display_avatar.url}"
      )
      log.add_field(
        name="Сервер",
        value=f"{interaction.guild.id} | {(f'[**`инвайт`**]({invites[0].url if invites else 'Нет инвайтов'})' if (invites := await interaction.guild.invites()) else 'Нет инвайтов') if interaction.guild.me.guild_permissions.manage_guild else 'Нет прав для просмотра инвайтов'} | {interaction.guild.name}" if interaction.guild else "ЛС",
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
        await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      except Exception:
        await interaction.followup.send(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

def setup(bot:Bot):
  bot.add_cog(Ban(bot))