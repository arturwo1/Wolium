import nextcord
from nextcord import SlashOption
from nextcord.ext import commands
from datetime import datetime, timezone
import traceback
import io
import contextlib

class slash_Command(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  @nextcord.slash_command(
    guild_ids=[807304463449849938, 1297240282806620193],
    default_member_permissions=8,
    description="Execute a command or script"
  )
  async def execute_command(self, interaction: nextcord.Interaction, command: str = SlashOption(name="command", description="Command/script to execute", required=True)):
    if interaction.user.id != self.bot.owner_id:
      await interaction.response.send_message(f"Ты не <@{self.bot.owner_id}>!", ephemeral=True)
      return

    embeds = []
    main_embed = nextcord.Embed(
      title="Command execution result:",
      description=f"Character count in **command**: `{len(command)}`\n## **Command:**\n```py\n{command[:4000]}```",
      color=nextcord.Colour.yellow(),
      timestamp=datetime.now(timezone.utc)
    )
    await interaction.response.send_message(embed=main_embed, ephemeral=True)

    try:
      buf = io.StringIO()
      err_buf = io.StringIO()
      globals_ = {"bot": self.bot, "interaction": interaction}
      locals_ = {}
      
      with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
        if "async def" in command or "await" in command:
          exec(f"async def __aexec():\n  " + "\n  ".join(command.split("\n")), globals_)
          result = await globals_["__aexec"]()
        else:
          exec(command, globals_, locals_)
          result = buf.getvalue()

      error = err_buf.getvalue().strip()
      result = (str(result) if result is not None else buf.getvalue().strip() if buf else "None").strip()

      if error:
        raise Exception(f"Result:\n{result}\n\nError:\n{error}")

      main_embed.description = (
        f"Character count in **command**: `{len(command)}`\n"
        f"Character count in **result**: `{len(result)}`\n## **Command:**\n```py\n{command[:4000]}```"
      )
      await interaction.followup.edit_message(message_id=(await interaction.original_message()).id, embed=main_embed)
      
      parts = [result[i:i + 4000] for i in range(0, len(result), 4000)]
      for idx, part in enumerate(parts, start=1):
        embed = nextcord.Embed(
          title=f"Execution result (part {idx}):",
          description=f"```py\n{part}```",
          color=nextcord.Colour.brand_green(),
          timestamp=datetime.now(timezone.utc),
        )
        embeds.append(embed)
    except Exception as e:
      traceback_msg = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
      parts = [traceback_msg[i:i + 4000] for i in range(0, len(traceback_msg), 4000)]
      for idx, part in enumerate(parts, start=1):
        embed = nextcord.Embed(
          title=f"Error (part {idx}):",
          description=f"```py\n{part}```",
          color=nextcord.Colour.dark_red(),
          timestamp=datetime.now(timezone.utc),
        )
        embeds.append(embed)

    try:
      if embeds:
        await interaction.followup.send(embed=embeds.pop(0), ephemeral=True)
        for embed in embeds:
          await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
      await interaction.followup.send(
        content=f"Error sending message: ```py\n{str(e)}```",
        ephemeral=True
      )

def setup(bot: commands.Bot):
  bot.add_cog(slash_Command(bot))