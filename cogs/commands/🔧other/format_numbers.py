from time import time
from nextcord import slash_command, IntegrationType, InteractionContextType, Interaction, SlashOption, Colour, Embed
from nextcord.ext import commands
from datetime import datetime, timezone
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from traceback import format_exception
from Utils.suffics import suffics

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class FormatNumbers(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @slash_command(description="Format numbers for display.",
    name_localizations=translate_to_all_languages('settings.number_formatting_snake', 'name'),
    description_localizations=translate_to_all_languages('settings.number_formatting_desc', 'description'),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
      ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],)
  async def format_numbers(self,
    interaction: Interaction,
    format_type: str=SlashOption(name="format_type", description="Scientific notation, normal notation, or no formatting", choices={"scientific":"scientific","normal":"normal","none":"none"},required=True, name_localizations=translate_to_all_languages('general.view_lower', 'name'), description_localizations=translate_to_all_languages('settings.number_format_options', 'description'), choice_localizations=translate_to_all_languages({"научная":"scientific","обычная":"normal","ничего":"none"}, 'choice')),
    example_number: float=SlashOption(name="example_number", description="Any number to see formatted result.", min_value=0, max_value=9.99e99,required=False, name_localizations=translate_to_all_languages('general.example_lower', 'name'), description_localizations=translate_to_all_languages('math.enter_number_desc', 'description')),
  ):
    try:
      user_id = interaction.user.id
      current_time = time()
      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      ud = self.bot.get_cog("UpdateData")
      lang = _get_locale(interaction.locale)

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(await tm.translate_message("error.rate_limit", lang, variables={"time": f"<t:{round(last_command_time+10)}:R>"}), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      user_settings = await gd.get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']

      if example_number is not None:
        number = example_number
        sformatted_number = await suffics(number=number, variation=format_type)
      else:
        number = 1234567890.1234567890
        sformatted_number = await suffics(number=number, variation=format_type)

      if format_type == "scientific":
        data = {"variation": "scientific"}
        await interaction.response.send_message(await tm.translate_message("settings.scientific_notation_selected", language, variables={"number": number, "formatted": sformatted_number}), ephemeral=True)
      elif format_type == "normal":
        data = {"variation": "normal"}
        await interaction.response.send_message(await tm.translate_message("settings.normal_notation_selected", language, variables={"number": number, "formatted": sformatted_number}), ephemeral=True)
      elif format_type == "none":
        data = {"variation": "none"}
        await interaction.response.send_message(await tm.translate_message("settings.no_notation_selected", language, variables={"number": number, "formatted": sformatted_number}), ephemeral=True)
      
      await ud.update_data(user_id, data, 'users', 'user_id', interaction.guild)

    except Exception as e:
      try:
        tm = self.bot.get_cog("TranslateMessage")
        gi = self.bot.get_cog("GetInvite")
        lang = _get_locale(interaction.locale)
      except:
        pass
      
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      invite = await gi.invite(interaction.guild) if interaction.guild else "No guild"
      
      log = Embed(
        title=f"User: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Command: ||**/format_numbers** `format_type` **{format_type}** `example_number` **{example_number}**||",
        color=Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.set_author(
        name=f"Server ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=f"{interaction.user.display_avatar.url}"
      )
      log.add_field(
        name="Server",
        value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
        inline=False
      )
      log.add_field(
        name="Channel",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
        inline=False
      )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
          name="Error",
          value=f"```py\n{traceback_msg[i:i+1000]}```",
          inline=False
        )
      log.set_footer(
        text=f"{str(datetime.now())}",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      try:
        await interaction.response.send_message(await tm.translate_message("error.occurred_logs_saved_review", lang), ephemeral=True)
      except Exception:
        await interaction.followup.send(await tm.translate_message("error.occurred_logs_saved_review", lang), ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

  setattr(format_numbers, "extras", {"description": "commands.format_numbers.description"})

def setup(bot:commands.Bot):
  bot.add_cog(FormatNumbers(bot))