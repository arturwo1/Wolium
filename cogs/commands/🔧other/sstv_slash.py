from nextcord import slash_command, Attachment, Interaction, SlashOption, IntegrationType, InteractionContextType
from nextcord.ext import commands
from Utils.sstv_encoder import SSTV_MODES
import Utils.translate_to_all_languages

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class SSTVSlash(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  @slash_command(
    description="Convert image to SSTV",
    name_localizations=translate_to_all_languages('sstv.command.name', 'name'),
    description_localizations=translate_to_all_languages('sstv.command.description', 'description'),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],
  )
  async def sstv(
    self,
    interaction: Interaction,
    image: Attachment = SlashOption(
      name="image",
      description="Image to convert.",
      required=True,
      name_localizations=translate_to_all_languages('sstv.option.image.name', 'name'),
      description_localizations=translate_to_all_languages('sstv.option.image.description', 'description')
    ),
    mode: str = SlashOption(
      name="mode",
      description="SSTV mode.",
      choices=list(SSTV_MODES.keys()),
      default="robot36",
      name_localizations=translate_to_all_languages('sstv.option.mode.name', 'name'),
      description_localizations=translate_to_all_languages('sstv.option.mode.description', 'description')
    ),
    output: str = SlashOption(
      name="output",
      description="Where to send.",
      choices=["file", "voice", "vc"],
      default="file",
      name_localizations=translate_to_all_languages('sstv.option.output.name', 'name'),
      description_localizations=translate_to_all_languages('sstv.option.output.description', 'description')
    ),
  ):
    await interaction.response.defer()
    SSTV = self.bot.get_cog("SSTV")
    await SSTV.sstv(interaction, [image], mode, output)

def setup(bot:commands.Bot):
  bot.add_cog(SSTVSlash(bot))