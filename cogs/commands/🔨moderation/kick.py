from time import time
from nextcord.ext.commands import Cog, Bot
from nextcord import slash_command, SlashOption, Interaction, Member, Embed, Colour
from Utils.parse_time import parse_time
from Utils.config import slash_command_cooldown
import Utils.translate_to_all_languages
from cogs.utils.add_violation import AddViolation
from cogs.utils.get_data import GetData
from cogs.utils.translate_message import TranslateMessage
from datetime import datetime, timezone
from traceback import format_exception
from cogs.utils.send_embed import SendEmbed
from cogs.utils.get_invite import GetInvite

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class Kick(Cog):
  def __init__(self, bot:Bot):
    self.bot:Bot=bot

  @slash_command(default_member_permissions=2,
  description="Команда Что-Бы Кикнуть Пользователя",
  name_localizations=translate_to_all_languages('kick', 'name'),
  description_localizations=translate_to_all_languages('Command To Kick a User.', 'description'))
  async def кик(self,
    interaction: Interaction,
    участник: Member=SlashOption(name="участник", description="Ник Участника Которого Хотите Кикнуть.",required=True, name_localizations=translate_to_all_languages('участник', 'name'), description_localizations=translate_to_all_languages('The Nick of the Member You Want to Kick.', 'description')),
    причина: str=SlashOption(name="причина", description="Причина Кика.",required=True, name_localizations=translate_to_all_languages('причина', 'name'), description_localizations=translate_to_all_languages('Kick\'s Reason.', 'description')),
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

      send_kick_message = await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Loading...", language),ephemeral=True)
      if str(member_id)==str(user_id):
        await send_kick_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Зачем Кикать Самого Себя...", language))
        return
      if interaction.guild.me.guild_permissions.ban_members==False:
        await send_kick_message.edit(await (TranslateMessage(self.bot)).translate_message(f"Недостаточно Прав(Кикать/Отправлять Сообщения) У Бота.", language))
        return
      if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<interaction.guild.get_member(member_id).guild_permissions.value:
        await send_kick_message.edit(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У", language)+f" **{участник.mention}**.")
        return

      try:
        member = await self.bot.fetch_user(member_id)
        dm = await member.create_dm()
        await dm.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Кикнуты По Причине: `{причина}`",language))
      except Exception:
        pass
      try:
        await interaction.guild.kick(user=участник,reason=причина)
        timestamp = int(interaction.created_at.timestamp())
        await (AddViolation(self.bot)).add_violation(member_id, interaction.guild.id, "kick", причина, None, timestamp, user_id)
        success_kick = Embed(
          title=await (TranslateMessage(self.bot)).translate_message(f"Изгнание", language),
          description=f"""
**{await (TranslateMessage(self.bot)).translate_message("Участник",language)}**: **`{участник}`**(**{участник.mention}**)
**{await (TranslateMessage(self.bot)).translate_message("Причина",language)}**: **`{причина}`**
          """,
          color=Colour.green(),
          timestamp=datetime.now(timezone.utc)
        )
        success_kick.set_footer(
          text=f"Kick",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )
        await send_kick_message.edit('',embed=success_kick)
      except Exception as e:
        await interaction.response.send_message(f"Нет Прав У Бота.\n||**Ошибка: `{e}`**||",ephemeral=True)
    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = Embed(
                title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
                description=f"Пользователь Вписал Команду: ||**/кик** `участник`  **{участник}** `причина`  **{причина}**||",
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
  bot.add_cog(Kick(bot))