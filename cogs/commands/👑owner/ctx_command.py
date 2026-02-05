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

  @commands.command(name="ctx_команда",
    hidden=True,
    aliases=["command","команда","ввод","input","_"])
  async def команда(self,ctx: commands.Context, *, команда: str):
    try:
      if ctx.author.id != self.bot.owner_id:
        await ctx.send(f"Ты не <@{self.bot.owner_id}>!", delete_after=15)
        return

      embeds = []
      основной_embed = nextcord.Embed(
        title="Результат выполнения команды:",
        description=f"Количество символов в **команде**: `{len(команда)}`\n## **Команда:**\n```py\n{команда[:4000]}```",
        color=nextcord.Colour.yellow(),
        timestamp=datetime.now(timezone.utc)
      )
      send_message = await ctx.reply(embed=основной_embed,delete_after=60)
      await ctx.message.delete(delay=30)
      try:
        buf = io.StringIO()
        err_buf = io.StringIO()
        globals_ = {"bot": self.bot, "ctx": ctx}
        locals_ = {}
        
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
          if "async def" in команда or "await" in команда:
            await asyncio.get_running_loop().run_in_executor(None, exec, f"async def __aexec():\n  " + "\n  ".join(команда.split("\n")), globals_)
            результат = await asyncio.wait_for(globals_["__aexec"](), timeout=60)
          else:
            await asyncio.get_running_loop().run_in_executor(None, exec, команда, globals_, locals_)
            результат = buf.getvalue()

        ошибка = err_buf.getvalue().strip()
        результат = (str(результат) if результат is not None else buf.getvalue().strip() if buf else "None").strip()

        if ошибка:
          raise Exception(f"Результат:\n{результат}\n\nОшибка:\n{ошибка}")

        основной_embed.description = (
          f"Количество символов в **команде**: `{len(команда)}`\n"
          f"Количество символов в **результате**: `{len(результат)}`\n## **Команда:**\n```py\n{команда[:4000]}```"
        )
        await send_message.edit(embed=основной_embed)
        
        части = [результат[i:i + 4000] for i in range(0, len(результат), 4000)]
        for idx, часть in enumerate(части, start=1):
          embed = nextcord.Embed(
            title=f"Результат выполнения (часть {idx}):",
            description=f"```py\n{часть}```",
            color=nextcord.Colour.brand_green(),
            timestamp=datetime.now(timezone.utc),
          )
          embeds.append(embed)
      except Exception as e:
        traceback_msg = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        части = [traceback_msg[i:i + 4000] for i in range(0, len(traceback_msg), 4000)]
        for idx, часть in enumerate(части, start=1):
          embed = nextcord.Embed(
            title=f"Ошибка (часть {idx}):",
            description=f"```py\n{часть}```",
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
        await ctx.send(content=f"Ошибка при отправке сообщения: **```py\n{str(e)}```**", delete_after=60)
    except nextcord.errors.HTTPException:
      pass

def setup(bot: commands.Bot):
  bot.add_cog(ctx_Command(bot))