from nextcord import message_command, InteractionContextType, IntegrationType, Interaction, Message, Embed, Color
from nextcord.ext import commands
from datetime import datetime, timezone
from cogs.utils.get_invite import GetInvite
from cogs.utils.translate_message import TranslateMessage
import Utils.translate_to_all_languages
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot
from cogs.utils.get_data import GetData

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class Translate(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  @message_command(name_localizations=translate_to_all_languages('перевести', 'name'),
    force_global=True,
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ])
  async def перевести(self, interaction: Interaction, message: Message):
    if ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
      await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://sites.google.com/view/arturwolium/main-page/rules) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
      return
    user_id = interaction.user.id

    if interaction.guild:
      guild_settings = await (GetData(self.bot)).get_data(interaction.guild.id,['banned'],'guilds','guild_id',interaction.guild)
    user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation','banned'],'users','user_id',interaction.guild)
    language = user_settings['language']

    if user_settings['banned'] or (guild_settings['banned'] if interaction.guild else False):
      await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://sites.google.com/view/arturwolium/main-page/rules) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",language), ephemeral=True)
      servers_with_no_acces_for_bot.append(interaction.guild.id)
      users_with_no_acces_for_bot.append(user_id)
      return
    await interaction.response.defer(ephemeral=True)
    invite = await (GetInvite(self.bot)).invite(interaction.guild)
    translate = Embed(
      title=await (TranslateMessage(self.bot)).translate_message(f"Перевод текста на",language)+f" {language}",
      description=message.content,
      color=Color.green(),
      timestamp=datetime.now(timezone.utc)
    )
    translate.set_author(
      name=interaction.user.name,
      icon_url=interaction.user.display_avatar.url
    )
    translate.add_field(
      name=await (TranslateMessage(self.bot)).translate_message(f"Перевод",language),
      value=await (TranslateMessage(self.bot)).translate_message(message.content,language,save=False),
      inline=True
    )
    translate.set_footer(
      text=await (TranslateMessage(self.bot)).translate_message(f"Переведено На",language)+f' {language}',
      icon_url="https://imgur.com/mvlC8XC"
    )
    await interaction.followup.send(embed=translate,ephemeral=True)

    mod_guild = self.bot.get_guild(807304463449849938)
    mod_chan = mod_guild.get_channel(1348577723097808977)
    embe = Embed(
      title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
      description=f"Пользователь ввёл: ||**/{interaction.application_command.name}** {' '.join(f'`{option['name']}` **{option['value']}** ' for option in interaction.data.get('options',[]))}||",
      color=Color.og_blurple(),
      timestamp=datetime.now(timezone.utc)
    )
    embe.set_author(
      name=f"Сервер ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
      icon_url=f"{interaction.user.display_avatar.url}"
    )
    if interaction.guild:
      embe.add_field(
        name="Сервер",
        value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "ЛС",
        inline=False
      )
    embe.add_field(
      name="Канал",
      value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
      inline=True
    )
    embe.add_field(
      name="Сообщение",
      value=f"{message.content}",
      inline=False
    )
    embe.set_footer(
      text=f"Перевод сообщения",
      icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
    )
    await mod_chan.send(embed=embe)

  setattr(перевести,"extras",{"description": "Позволяет перевести **абсолютно** любое сообщение на **ваш язык** с любого языка!"})

def setup(bot: commands.Bot):
  bot.add_cog(Translate(bot))