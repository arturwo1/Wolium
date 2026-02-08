import nextcord
from nextcord import SlashOption, IntegrationType, InteractionContextType
from nextcord.ext import commands
from cogs.utils.get_invite import GetInvite
from cogs.utils.translate_message import TranslateMessage
from cogs.utils.get_data import GetData
from cogs.utils.update_data import UpdateData
from datetime import datetime,timezone
from time import time
import traceback
import Utils.translate_to_all_languages
from Utils.config import DISCORD_LANGUAGES, slash_command_cooldown

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class Language(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
  
  @nextcord.slash_command(description="Выбрать Язык Бота.",
    name_localizations=translate_to_all_languages('язык', 'name'),
    description_localizations=translate_to_all_languages('Выбрать Язык Бота', 'description'),
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
  async def язык(self,
    interaction: nextcord.Interaction,
    язык: str=SlashOption(name="язык", description="Выбери Язык.",required=True, name_localizations=translate_to_all_languages('язык', 'name'), description_localizations=translate_to_all_languages('Выбери Язык.', 'description')),
    лично: bool=SlashOption(name="лично", description="Только Ты Увидешь Сообщение, Или Все.",required=False,default=False, name_localizations=translate_to_all_languages('лично', 'name'), description_localizations=translate_to_all_languages('Только Ты Увидешь Сообщение, Или Все.', 'description')),
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

      await interaction.response.defer(ephemeral=лично)

      invite = await (GetInvite(self.bot)).invite(interaction.guild)

      if язык in DISCORD_LANGUAGES:
        await interaction.followup.send("✔",ephemeral=лично)
        data = {
          'language': язык
        }
        await (UpdateData(self.bot)).update_data(user_id, data, 'users', 'user_id', interaction.guild)
      else:
        await interaction.followup.send("✖",ephemeral=лично)
    except Exception as e:
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/язык** `язык`  **{язык}**||",
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
        text=f"cogs.commands.🔧other.language",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      try:
        await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      except Exception:
        await interaction.followup.send(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

  @язык.on_autocomplete("язык")
  async def языки(self, interaction: nextcord.Interaction, язык: str):
    LANGUAGES = DISCORD_LANGUAGES
    filtered_language = [LANGUAGES for LANGUAGES in LANGUAGES if язык.lower() in LANGUAGES.lower()]
    filtered_language = filtered_language[:25]
    await interaction.response.send_autocomplete(filtered_language)

  setattr(язык, "extras",{"description": "С помощью этой команды вы можете выбрать язык, на котором я буду вам отвечать!"})

def setup(bot: commands.Bot):
  bot.add_cog(Language(bot))