from time import time
from nextcord.ext.commands import Cog, Bot
from nextcord import slash_command, SlashOption, Interaction, User, Embed, Colour
from Utils.parse_time import parse_time
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot, slash_command_cooldown
import Utils.translate_to_all_languages
from cogs.utils.add_violation import AddViolation
from cogs.utils.get_data import GetData
from cogs.utils.translate_message import TranslateMessage
from datetime import datetime, timezone
from traceback import format_exception
from cogs.utils.send_embed import SendEmbed
from cogs.utils.get_invite import GetInvite

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class UnBan(Cog):
  def __init__(self, bot:Bot):
    self.bot:Bot=bot

  @slash_command(default_member_permissions=16,
  description="Команда Что-Бы Разбанить Пользователя",
  name_localizations=translate_to_all_languages('unban', 'name'),
  description_localizations=translate_to_all_languages('Command To Unban a User.', 'description'))
  async def разбан(self,
    interaction: Interaction,
    пользователь: User=SlashOption(name="пользователь", description="Ник Пользователя Которого Хотите Разбанить.",required=True, name_localizations=translate_to_all_languages('пользователь', 'name'), description_localizations=translate_to_all_languages('Nickname of the User You Want to Unban.', 'description')),
    причина: str=SlashOption(name="причина", description="Причина Разбана.",required=True, name_localizations=translate_to_all_languages('причина', 'name'), description_localizations=translate_to_all_languages('Reason for Unbanning.', 'description')),
  ):
    try:
      if ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://sites.google.com/view/arturwolium/main-page/rules) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
        return
      user_id = interaction.user.id
      member_id = пользователь.id
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

      send_unban_message = await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message("Загрузка Данных", language),ephemeral=True)
      
      async with self.bot.db_pool.acquire() as conn:
        mod_id: int = await conn.fetchval(
          "SELECT mod_id FROM violations "
          "WHERE user_id = $1 AND guild_id = $2 AND type = 'ban' "
          "ORDER BY timestamp DESC LIMIT 1;",
          user_id, interaction.guild.id
        )
      
      if str(member_id)==str(user_id):
        await send_unban_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Зачем Пытаться Разбанить Самого Себя...", language))
        return
      if interaction.guild.me.guild_permissions.ban_members==False:
        await send_unban_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Недостаточно Прав(Банить/Отправлять Сообщения) У Меня.", language))
        return
      if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<(interaction.guild.get_member(mod_id).guild_permissions.value if mod_id else 0):
        await send_unban_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Был Выдан Бан от:",language)+f" **<@{mod_id}>**\n"+await (TranslateMessage(self.bot)).translate_message(f"У тебя Меньше Прав Чем У Него.", language)+f" **{пользователь.mention}**.")
        return
      try:
        await interaction.guild.fetch_ban(пользователь)
      except Exception:
        await send_unban_message.edit(await (TranslateMessage(self.bot)).translate_message(f"{пользователь.mention} Не Забанен.", language))
        return
      
      invite = await (GetInvite(self.bot)).invite(interaction.guild)

      fields = [
        {
          'name':'Модератор',
          'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline':True
        },
        {
          'name':'Сервер',
          'value':f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "ЛС",
          'inline':True
        },
        {
          'name':'Канал',
          'value':f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else f'[<@{interaction.user.id}>({interaction.user.id} | {interaction.user.name}({interaction.user.display_name})]'}`)",
          'inline':True
        },
        {
          'name':'Пользователь',
          'value':f"{пользователь.id} | {пользователь.mention} | {пользователь.name}",
          'inline':True
        },
        {
          'name':'Причина',
          'value':f"{причина}",
          'inline':True
        },
        {
          'name':'Время',
          'value':f"<t:{int(interaction.created_at.timestamp())}:F>",
          'inline':True
        }
      ]
      await (SendEmbed(self.bot)).send_embed(
        title="Ввод команды",
        description=f"Пользователь ввёл: ||**/{interaction.application_command.name}** {' '.join(f'`{option['name']}` **{option['value']}** ' for option in interaction.data.get('options',[]))}||",
        color=Colour.yellow(),
        fields=fields,
        footer_text=interaction.application_command.name,
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        channel_id=1348577723097808977
      )

      try:
        await interaction.guild.unban(user=пользователь,reason=причина)
        timestamp = int(interaction.created_at.timestamp())
        await (AddViolation(self.bot)).add_violation(member_id, interaction.guild.id, "unban", причина, None, timestamp, user_id)
        try:
          member = await self.bot.fetch_user(member_id)
          dm = await member.create_dm()
          await dm.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Разбанены По Причине:", language)+f" `{причина}`\n"+await (TranslateMessage(self.bot)).translate_message(f"На Сервере:", language)+f" `{interaction.guild.name}`\n"+await (TranslateMessage(self.bot)).translate_message(f"Разбанил:", language)+f" **{interaction.user.name}**(`{interaction.user.id}`) | **{interaction.user.mention}**\n"+await (TranslateMessage(self.bot)).translate_message(f"Время Разбана:", language)+f" <t:{timestamp}:F>")
        except Exception:
          pass

        success_unban = Embed(
          title=await (TranslateMessage(self.bot)).translate_message(f"Снятие Бана", language),
          description=f"""
**{await (TranslateMessage(self.bot)).translate_message("Участник", language)}**: **`{пользователь}`**(**{пользователь.mention}**)
**{await (TranslateMessage(self.bot)).translate_message("Причина", language)}**: **`{причина}`**
          """,
          color=Colour.green(),
          timestamp=datetime.now(timezone.utc)
        )
        success_unban.set_footer(
          text=f"UnBan",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )
        await send_unban_message.edit('',embed=success_unban)
      except Exception as e:
        await send_unban_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Нет Прав У Меня.", language)+f" ||**```py\n{e}```**||")
    except Exception as e:
        traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
        log = Embed(
          title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
          description=f"Пользователь Вписал Команду: ||**/разбан** `пользователь`  **{пользователь}** `причина`  **{причина}**||",
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
  bot.add_cog(UnBan(bot))