from nextcord import message_command, InteractionContextType, IntegrationType, Interaction, Message, Embed, Color
from nextcord.ext import commands
from datetime import datetime, timezone
import Utils.translate_to_all_languages

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class Translate(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  @message_command(name_localizations=translate_to_all_languages('other.translate_name', 'description'),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ])
  async def translate(self, interaction: Interaction, message: Message):
    try:
      user_id = interaction.user.id
      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")

      user_settings = await gd.get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']

      await interaction.response.defer(ephemeral=True)
      
      translate_embed = Embed(
        title=await tm.translate_message(f"command.translate.title",language)+f" {language}",
        description=message.content,
        color=Color.green(),
        timestamp=datetime.now(timezone.utc)
      )
      translate_embed.set_author(
        name=interaction.user.name,
        icon_url=interaction.user.display_avatar.url
      )
      translate_embed.add_field(
        name=await tm.translate_message(f"command.translate.name",language),
        value=await tm.translate_message(message.content,language,save=False),
        inline=True
      )
      translate_embed.set_footer(
        text=await tm.translate_message(f"command.translate.result",language)+f' {language}',
        icon_url="https://imgur.com/mvlC8XC"
      )
      await interaction.followup.send(embed=translate_embed,ephemeral=True)
    except Exception as e:
      await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

  setattr(translate,"extras",{"description": "commands.translate.description"})

def setup(bot: commands.Bot):
  bot.add_cog(Translate(bot))