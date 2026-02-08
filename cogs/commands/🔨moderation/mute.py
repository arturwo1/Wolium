from time import time
from nextcord.ext.commands import Cog, Bot
from nextcord import slash_command, SlashOption, Interaction, Member, Embed, Colour
from Utils.parse_time import parse_time
from Utils.config import slash_command_cooldown
import Utils.translate_to_all_languages
from cogs.utils.add_violation import AddViolation
from cogs.utils.get_data import GetData
from cogs.utils.translate_message import TranslateMessage
from datetime import datetime, timezone, timedelta
from traceback import format_exception
from cogs.utils.send_embed import SendEmbed
from cogs.utils.get_invite import GetInvite

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class Mute(Cog):
  def __init__(self, bot:Bot):
    self.bot:Bot=bot

  @slash_command(default_member_permissions=536870924,
  description="Команда Что-Бы Замутить Пользователя",
  name_localizations=translate_to_all_languages('mute', 'name'),
  description_localizations=translate_to_all_languages('Command To Mute User.', 'description'))
  async def мут(self,
    interaction: Interaction,
    участник: Member=SlashOption(name="участник", description="Ник Участника Которого Хотите Замутить.",required=True, name_localizations=translate_to_all_languages('участник', 'name'), description_localizations=translate_to_all_languages('Nickname Of User That You Want To Mute.', 'description')),
    длительность: str=SlashOption(name="длительность", description="Длительность Мута(s,m,h,d,w).",required=True, name_localizations=translate_to_all_languages('длительность', 'name'), description_localizations=translate_to_all_languages('Cooldown Of Mute(s,m,h,d,w).', 'description')),
    причина: str=SlashOption(name="причина", description="Причина Мута.",required=True, name_localizations=translate_to_all_languages('причина', 'name'), description_localizations=translate_to_all_languages('Mute Reason.', 'description')),
  ):
    try:
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

      user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']

      send_mute_message = await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Loading...", language),ephemeral=True)
      длительность = parse_time(длительность)
      if str(member_id)==str(user_id):
        await send_mute_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Зачем Тайм-Аутить Самого Себя...", language))
        return
      if interaction.guild.me.guild_permissions.ban_members==False:
        await send_mute_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Недостаточно Прав(Тайм-Аутить/Отправлять Сообщения) У Бота.", language))
        return
      if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<interaction.guild.get_member(member_id).guild_permissions.value:
        await send_mute_message.edit(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У", language)+f" **{участник.mention}**.")
        return
      if длительность==None:
        await send_mute_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Вы Используете Не Правильный Формат Времени!\nВы Можете Использовать только: `s`(секунды), `m`(минуты),`h`(часы),`d`(дни),`w`(недели).\nПример: `1w5d20h54m45s`", language))
        return
      if длительность>2419200:
        await send_mute_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Максимальное Время Мута: `28 дней`, Вы Вписали:", language)+f" `{timedelta(seconds=длительность)}`.")
        return

      try:
        member = interaction.guild.get_member(member_id)
        dm = await member.create_dm()
        await dm.send(await (TranslateMessage(self.bot)).translate_message("Вы Были Замучены.",language)+"\n"+await (TranslateMessage(self.bot)).translate_message("Причина:",language)+f" `{причина}`\n"+await (TranslateMessage(self.bot)).translate_message("Время:",language)+f" `{timedelta(seconds=длительность)}`")
      except Exception:
        pass
      try:
        await участник.timeout(timeout=timedelta(seconds=длительность),reason=причина)
        timestamp = int(interaction.created_at.timestamp())
        await (AddViolation(self.bot)).add_violation(member_id, interaction.guild.id, "mute", причина, длительность, timestamp, user_id)

        success_unban = Embed(
          title=await (TranslateMessage(self.bot)).translate_message(f"Тайм-Аутинг", language),
          description=f"""
**{await (TranslateMessage(self.bot)).translate_message("Участник", language)}**: **`{участник}`**(**{участник.mention}**)
**{await (TranslateMessage(self.bot)).translate_message("Причина", language)}**: **`{причина}`**
**{await (TranslateMessage(self.bot)).translate_message("Время", language)}**: **`{timedelta(seconds=длительность)}`**
          """,
          color=Colour.green(),
          timestamp=datetime.now(timezone.utc)
        )
        success_unban.set_footer(
          text=f"Mute",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )
        await send_mute_message.edit('',embed=success_unban)
      except Exception as e:
        await send_mute_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Нет Прав У Бота.",language)+f"\n```py{(''.join(format_exception(type(e), e, e.__traceback__)))[:2000]}```",ephemeral=True)
    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/мут** `участник`  **{участник}** `длительность`  **{длительность}** `причина`  **{причина}**||",
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
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
      except Exception:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)


def setup(bot:Bot):
  bot.add_cog(Mute(bot))