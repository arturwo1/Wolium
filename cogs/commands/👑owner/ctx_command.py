import nextcord
from nextcord.ext import commands
from datetime import datetime, timezone
import traceback
import io
import asyncio
import contextlib

class ctx_Command(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  @commands.command(name="ctx_command",
    hidden=True,
    aliases=["command","execute","input","_"])
  async def execute(self,ctx: commands.Context, *, command: str):
    try:
      if ctx.author.id != self.bot.owner_id:
        await ctx.send(f"Ты не <@{self.bot.owner_id}>!", delete_after=15)
        return

      embeds = []
      main_embed = nextcord.Embed(
        title="Command execution result:",
        description=f"Character count in **command**: `{len(command)}`\n## **Command:**\n```py\n{command[:4000]}```",
        color=nextcord.Colour.yellow(),
        timestamp=datetime.now(timezone.utc)
      )
      send_message = await ctx.reply(embed=main_embed,delete_after=60)
      await ctx.message.delete(delay=30)
      try:
        buf = io.StringIO()
        err_buf = io.StringIO()
        globals_ = {"bot": self.bot, "ctx": ctx}
        locals_ = {}
        
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
          if "async def" in command or "await" in command:
            await asyncio.get_running_loop().run_in_executor(None, exec, f"async def __aexec():\n  " + "\n  ".join(command.split("\n")), globals_)
            result = await asyncio.wait_for(globals_["__aexec"](), timeout=60)
          else:
            await asyncio.get_running_loop().run_in_executor(None, exec, command, globals_, locals_)
            result = buf.getvalue()

        error = err_buf.getvalue().strip()
        result = (str(result) if result is not None else buf.getvalue().strip() if buf else "None").strip()

        if error:
          raise Exception(f"Result:\n{result}\n\nError:\n{error}")

        main_embed.description = (
          f"Character count in **command**: `{len(command)}`\n"
          f"Character count in **result**: `{len(result)}`\n## **Command:**\n```py\n{command[:4000]}```"
        )
        await send_message.edit(embed=main_embed)
        
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
          await ctx.send(embed=embeds.pop(0), delete_after=60)
          for embed in embeds:
            await ctx.send(embed=embed, delete_after=30)
      except Exception as e:
        await ctx.send(content=f"Error sending message: **```py\n{str(e)}```**", delete_after=60)
    except nextcord.errors.HTTPException:
      pass

def setup(bot: commands.Bot):
  bot.add_cog(ctx_Command(bot))