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
    description="Ввести команду/скрипт"
  )
  async def команда(self, interaction: nextcord.Interaction, команда: str = SlashOption(name="команда", description="Ввод команды/скрипта", required=True)):
    if interaction.user.id != self.bot.owner_id:
      await interaction.response.send_message(f"Ты не <@{self.bot.owner_id}>!", ephemeral=True)
      return

    embeds = []
    основной_embed = nextcord.Embed(
      title="Результат выполнения команды:",
      description=f"Количество символов в **команде**: `{len(команда)}`\n## **Команда:**\n```py\n{команда[:4000]}```",
      color=nextcord.Colour.yellow(),
      timestamp=datetime.now(timezone.utc)
    )
    await interaction.response.send_message(embed=основной_embed, ephemeral=True)

    try:
      buf = io.StringIO()
      err_buf = io.StringIO()
      globals_ = {"bot": self.bot, "interaction": interaction}
      locals_ = {}
      
      with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
        if "async def" in команда or "await" in команда:
          exec(f"async def __aexec():\n  " + "\n  ".join(команда.split("\n")), globals_)
          результат = await globals_["__aexec"]()
        else:
          exec(команда, globals_, locals_)
          результат = buf.getvalue()

      ошибка = err_buf.getvalue().strip()
      результат = (str(результат) if результат is not None else buf.getvalue().strip() if buf else "None").strip()

      if ошибка:
        raise Exception(f"Результат:\n{результат}\n\nОшибка:\n{ошибка}")

      основной_embed.description = (
        f"Количество символов в **команде**: `{len(команда)}`\n"
        f"Количество символов в **результате**: `{len(результат)}`\n## **Команда:**\n```py\n{команда[:4000]}```"
      )
      await interaction.followup.edit_message(message_id=(await interaction.original_message()).id, embed=основной_embed)
      
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
        await interaction.followup.send(embed=embeds.pop(0), ephemeral=True)
        for embed in embeds:
          await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
      await interaction.followup.send(
        content=f"Ошибка при отправке сообщения: ```py\n{str(e)}```",
        ephemeral=True
      )

def setup(bot: commands.Bot):
  bot.add_cog(slash_Command(bot))