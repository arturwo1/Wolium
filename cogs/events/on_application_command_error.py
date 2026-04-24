import nextcord
from nextcord.ext import commands
from datetime import datetime, timezone
import traceback

class OnApplicationCommandError(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_application_command_error(self, interaction: nextcord.Interaction, exception: Exception):
    traceback_msg = ((''.join(traceback.format_exception(type(exception), exception, exception.__traceback__)))[:4000])
    invite = await self.bot.get_cog("GetInvite").invite(interaction.guild)
    try:
      log = nextcord.Embed(
        title=f"Application Command Error",
        description=str(exception)[:2048],
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      log.add_field(
        name="User",
        value=f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
        inline=True
      )
      if interaction.guild:
        log.add_field(
          name="Server",
          value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
          inline=False
        )
      log.add_field(
        name="Channel",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else f'[<@{interaction.author.id}>({interaction.author.id} | {interaction.author.name}({interaction.author.display_name})]'}`)",
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
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
    except Exception as a:
      print(f"⚠ Application command error:\n  Interaction: {{\n    \"name\": \"{interaction.application_command.name}\",\n    \"id\": \"{interaction.id}\",\n    \"user\": \"{interaction.user}\"\n    \"user_id\": \"{interaction.user.id}\"\n}}\n  Error: {exception},\n  Exception: [{traceback_msg}]\n\n⚠ Error while sending error log: {a}")
    

def setup(bot:commands.Bot):
  bot.add_cog(OnApplicationCommandError(bot))