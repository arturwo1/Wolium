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
    user_id = interaction.user.id

    user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
    language = user_settings['language']

    await interaction.response.defer(ephemeral=True)
    
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

  setattr(перевести,"extras",{"description": "Позволяет перевести **абсолютно** любое сообщение на **ваш язык** с любого языка!"})

def setup(bot: commands.Bot):
  bot.add_cog(Translate(bot))