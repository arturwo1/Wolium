from time import time
from nextcord import slash_command, IntegrationType, InteractionContextType, Interaction, SlashOption, Colour, Embed
from nextcord.ext import commands
from datetime import datetime, timezone
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from cogs.utils.get_data import GetData
from cogs.utils.get_invite import GetInvite
from cogs.utils.send_embed import SendEmbed
from cogs.utils.translate_message import TranslateMessage
from traceback import format_exception
from Utils.suffics import suffics
from cogs.utils.update_data import UpdateData

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class FormatNumbers(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @slash_command(description="Позволяет Форматировать Числа.",
    name_localizations=translate_to_all_languages('форматирование_чисел', 'name'),
    description_localizations=translate_to_all_languages('Позволяет Форматировать Числа.', 'description'),
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
  async def форматирование_чисел(self,
    interaction: Interaction,
    вид: str=SlashOption(name="вид", description="Научная Нотация(1000=1e3), Обычная Нотация(1000=1.00K), Ничего(1000=1000)", choices={"scientific":"scientific","normal":"normal","None":"None"},required=True, name_localizations=translate_to_all_languages('вид', 'name'), description_localizations=translate_to_all_languages('Научная Нотация(1000=1e3), Обычная Нотация(1000=1.00K), Ничего(1000=1000)', 'description'), choice_localizations=translate_to_all_languages({"научная":"scientific","обычная":"normal","ничего":"None"}, 'choice')),
    пример: float=SlashOption(name="пример", description="Здесь Вы Можете Вписать Любое Число Чтоб Потом Увидеть Результат.", min_value=0, max_value=9.99e99,required=False, name_localizations=translate_to_all_languages('пример', 'name'), description_localizations=translate_to_all_languages('Здесь Вы Можете Вписать Любое Число Чтоб Потом Увидеть Результат.', 'description')),
  ):
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

      if пример is not None:
        число=пример
        sпример=await suffics(number=число,variation=вид)
      else:
        число=1234567890.1234567890
        sпример=await suffics(number=число,variation=вид)

      if вид=="scientific":
        data={"variation":"scientific"}
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Выбрали: `Научную Нотацию`.\nВот Пример Числа: `{число}={sпример}`.",language),ephemeral=True)
      elif вид=="normal":
        data={"variation":"normal"}
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Выбрали: `Обычную Нотацию`.\nВот Пример Числа: `{число}={sпример}`.",language),ephemeral=True)
      elif вид=="None":
        data={"variation":"None"}
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы `Ничего` Не Выбрали.\nВот Пример Числа: `{число}={sпример}`.",language),ephemeral=True)
      
      await (UpdateData(self.bot)).update_data(user_id,data,'users','user_id',interaction.guild)

    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь ввёл: ||**/{interaction.application_command.name}** {' '.join(f'`{option['name']}` **{option['value']}** ' for option in interaction.data.get('options',[]))}||",
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
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **<t:{round(last_command_time+10)}:R>** "+await (TranslateMessage(self.bot)).translate_message(f"you can write commands.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
      except Exception:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **<t:{round(last_command_time+10)}:R>** "+await (TranslateMessage(self.bot)).translate_message(f"you can write commands.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

def setup(bot:commands.Bot):
  bot.add_cog(FormatNumbers(bot))