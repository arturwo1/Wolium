from nextcord import message_command, Interaction, IntegrationType, InteractionContextType, Message
from nextcord.ui import Modal, TextInput
from nextcord.ext import commands
from Utils.sstv_encoder import SSTV_MODES
import Utils.translate_to_all_languages

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

OUTPUT_CHOICES = ("file", "voice", "vc")

class SSTVOptionsModal(Modal):
  def __init__(self, bot: commands.Bot, message: Message, language: str):
    super().__init__(title=translate_to_all_languages('sstv.modal.title', 'message', language))
    self.bot = bot
    self.message = message
    self.language = language

    mode_choices = ", ".join(SSTV_MODES.keys())
    self.mode_input = TextInput(
      label=translate_to_all_languages('sstv.option.mode.name', 'message', language),
      default_value="robot36",
      placeholder=mode_choices[:100],
      required=True,
      max_length=30,
    )
    self.add_item(self.mode_input)

    output_choices = ", ".join(OUTPUT_CHOICES)
    self.output_input = TextInput(
      label=translate_to_all_languages('sstv.option.output.name', 'message', language),
      default_value="file",
      placeholder=output_choices,
      required=True,
      max_length=10,
    )
    self.add_item(self.output_input)

  async def callback(self, interaction: Interaction):
    mode = self.mode_input.value.strip().lower()
    output = self.output_input.value.strip().lower()

    tm = self.bot.get_cog("TranslateMessage")

    if mode not in SSTV_MODES:
      await interaction.response.send_message(
        await tm.translate_message("sstv.error.invalid_mode", self.language),
        ephemeral=True,
      )
      return

    if output not in OUTPUT_CHOICES:
      await interaction.response.send_message(
        await tm.translate_message("sstv.error.invalid_output", self.language),
        ephemeral=True,
      )
      return

    await interaction.response.defer()

    SSTV = self.bot.get_cog("SSTV")
    await SSTV.sstv(interaction, self.message.attachments, mode, output)

class SSTVMessage(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  @message_command(
    name_localizations=translate_to_all_languages('sstv_command.command.name', 'description'),
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
  async def sstv(self, interaction: Interaction, message: Message):
    user_id = interaction.user.id
    tm = self.bot.get_cog("TranslateMessage")
    gd = self.bot.get_cog("GetData")

    user_settings = await gd.get_data(user_id, ['language'], 'users', 'user_id', interaction.guild)
    language = user_settings['language']

    if not message.attachments:
      await interaction.response.defer(ephemeral=True)
      await interaction.followup.send(await tm.translate_message("sstv.error.no_attachments", language), ephemeral=True)
      return

    await interaction.response.send_modal(SSTVOptionsModal(self.bot, message, language))

def setup(bot: commands.Bot):
  bot.add_cog(SSTVMessage(bot))