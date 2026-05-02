from nextcord import SlashOption, slash_command, Interaction, Color
from nextcord.ext import commands
from nextcord.errors import ApplicationCheckFailure
from os import walk, sep
from sys import modules
from traceback import format_exception

class CogsEditor(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  @commands.command(name="sync")
  @commands.is_owner()
  async def sync_commands(self, ctx: commands.Context):
    msg = await ctx.send("🔄 Начинаю синхронизацию слеш-команд с Discord...")
    try:
      await self.bot.sync_application_commands()
      await msg.edit(content="✅ Слеш-команды успешно синхронизированы! Автозаполнение починено.")
    except Exception as e:
      await msg.edit(content=f"❌ Ошибка при синхронизации: ```py\n{e}```")

  @slash_command(
    description="Позволяет выключать, перезагружать, удалять коги", 
    default_member_permissions=8, 
    guild_ids=[807304463449849938, 1297240282806620193]
  )
  async def manage_cogs(self,
    interaction: Interaction,
    cog: str = SlashOption(name="cog", description="Выбор cog'а.", required=False),
    action: str = SlashOption(name="действие", description="Что делать с cog'ом.", choices={"загрузить": "load_extension", "перезагрузить": "reload_extension", "отключить": "unload_extension"}, required=False),
  ):
    if not await self.bot.is_owner(interaction.user):
      await interaction.response.send_message("Ты не создатель бота.", ephemeral=True)
      return
    
    await interaction.response.defer(ephemeral=True)
    se = self.bot.get_cog("SendEmbed")

    try:
      if cog and action:
        if cog in modules and action != "unload_extension":
          del modules[cog]
        getattr(self.bot, action)(cog)

      elif (cog and not action) or (not cog and action):
        await interaction.followup.send("❌ Нужно выбрать и `cog`, и `действие` (либо оставить оба пустыми для полной перезагрузки).", ephemeral=True)
        return

      else:
        for root, _, files in walk("cogs"):
          for file in files:
            if file.endswith(".py"):
              cog_path = f"{root.replace(sep, '.')}.{file[:-3]}"
              
              if cog_path in modules:
                del modules[cog_path]
              
              try:
                if cog_path in self.bot.extensions:
                  self.bot.unload_extension(cog_path)
                self.bot.load_extension(cog_path)
              except Exception as e:
                traceback_msg = ''.join(format_exception(type(e), e, e.__traceback__))[:3000]
                fields = [
                  {
                    'name': 'Ошибка',
                    'value': f"**```py\n{traceback_msg}```**",
                    'inline': False
                  }
                ]
                if se:
                  await se.send_embed(
                    title='Ошибка при перезагрузке/загрузке когов',
                    description=f"### **Загрузка cog'а**\n**{cog_path}**\n### **Ошибка**\n**{str(e)[:512]}**",
                    color=Color.red(),
                    fields=fields,
                    footer_text='manage_cogs',
                    channel_id=1159138280651104256
                  )
      
      await interaction.followup.send("✅ Команда выполнена успешно.", ephemeral=True)

    except commands.ExtensionError as e:
      await interaction.followup.send(f"Ошибка работы с когом: **```py\n{e}```**", ephemeral=True)
    except Exception as e:
      await interaction.followup.send(f"Неизвестная ошибка: **```py\n{repr(e)}```**", ephemeral=True)

  @manage_cogs.on_autocomplete("cog")
  async def cogs_autocomplete(self, interaction: Interaction, cog: str):
    cogs: list[str] = []
    for root, _, files in walk("cogs"):
      for file in files:
        if file.endswith(".py"):
          cog_path = f"{root.replace(sep, '.')}.{file[:-3]}"
          cogs.append(cog_path)

    filtered_cogs = [c for c in cogs if cog.lower() in c.lower()][:25]
    await interaction.response.send_autocomplete(filtered_cogs)

  @manage_cogs.error
  async def command_error(self, interaction: Interaction, error: Exception):
    send_method = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
    
    if isinstance(error, ApplicationCheckFailure):
      await send_method("❌ У вас нет прав для использования этой команды.", ephemeral=True)
    elif isinstance(error, commands.CommandError):
      await send_method(f"❌ Произошла ошибка команды: {str(error)}", ephemeral=True)
    else:
      await send_method(f"❌ Произошла неизвестная ошибка: {str(error)}", ephemeral=True)

def setup(bot: commands.Bot):
  bot.add_cog(CogsEditor(bot))