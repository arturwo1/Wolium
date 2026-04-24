from nextcord import SlashOption, slash_command, Interaction, Color
from nextcord.ext import commands
from os import walk, sep
from sys import modules
from traceback import format_exception

class CogsEditor(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  async def resync(self):
    await self.bot.wait_until_ready()
    await self.bot.sync_application_commands()

  try:
    @slash_command(description="Позволяет выключать, перезагружать, удалять коги", 
      default_member_permissions=8, 
      guild_ids=[807304463449849938, 1297240282806620193])
    async def manage_cogs(self,
      interaction: Interaction,
      cog: str = SlashOption(name="cog", description="Выбор cog'а.", required=False),
      action: str = SlashOption(name="действие", description="Что делать с cog'ом.", choices={"загрузить": "load_extension", "перезагрузить": "reload_extension", "отключить": "unload_extension"}, required=False),
    ):
      if not await self.bot.is_owner(interaction.user):
        await interaction.response.send_message("Ты не создатель бота.", ephemeral=True)
        return
      
      se = self.bot.get_cog("SendEmbed")
      await interaction.response.defer(ephemeral=True)
      try:
        if cog and action:
          if cog in modules:
            del modules[cog]
          cog_name = self.bot.get_cog(cog)
          self.bot.remove_cog(cog_name)
          getattr(self.bot, action)(cog)
        elif cog and not action:
          await interaction.followup.send(f"Ты забыл выбрать `действие`.",ephemeral=True)
          return
        elif not cog and action:
          await interaction.followup.send(f"Ты забыл выбрать `cog`.",ephemeral=True)
          return
        else:
          for root, _, files in walk("cogs"):
            for file in files:
              if file.endswith(".py"):
                cog_path = f"{root.replace(sep, '.')}.{file[:-3]}"
                if cog_path in modules:
                  del modules[cog_path]
                cog_name = self.bot.get_cog(cog_path)
                self.bot.remove_cog(cog_name)
                try:
                  if cog_path in self.bot.extensions:
                    self.bot.unload_extension(cog_path)
                  self.bot.load_extension(cog_path)
                except Exception as e:
                  traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
                  fields = [
                    {
                      'name':'Ошибка',
                      'value':f"**```py\n{traceback_msg}```**",
                      'inline':False
                    }
                  ]
                  await se.send_embed(
                    title='Ошибка при перезагрузке/загрузке когов с помощью команды /управление_cogами',
                    description=(
                      "### **Загрузка cog'а**\n"+
                      f"**{cog_path}**\n"+
                      "### **Ошибка**\n"+
                      f"**{str(e)[:512]}**"
                    ),
                    color=Color.red(),
                    fields=fields,
                    footer_text='manage_cogs',
                    channel_id=1159138280651104256
                  )
      except commands.ExtensionNotFound as e:
        await interaction.followup.send(f"Cog не был найден, ошибка: **```py\n{e}```**", ephemeral=True)
        return
      except commands.ExtensionAlreadyLoaded as e:
        await interaction.followup.send(f"Cog уже был загружен, ошибка: **```py\n{e}```**", ephemeral=True)
        return
      except commands.ExtensionNotLoaded as e:
        await interaction.followup.send(f"Cog не загружен, ошибка: **```py\n{e}```**", ephemeral=True)
        return
      except commands.NoEntryPointError as e:
        await interaction.followup.send(f"Cog не имеет способа загрузки, ошибка: **```py\n{e}```**", ephemeral=True)
        return
      except commands.InvalidSetupArguments as e:
        await interaction.followup.send(f"Неправильные параметры для загрузки cog'а, ошибка: **```py\n{e}```**", ephemeral=True)
        return
      except commands.ExtensionFailed as e:
        await interaction.followup.send(f"Cog не смог загрузиться, ошибка: **```py\n{e}```**", ephemeral=True)
        return
      except Exception as e:
        await interaction.followup.send(f"Неизвестная ошибка: **```py\n{repr(e)}```**,**```py\n{((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])}```**", ephemeral=True)
        return
      await self.resync()
      await interaction.followup.send(f"✅Команда выполнена успешно.",ephemeral=True)

    try:
      @manage_cogs.on_autocomplete("cog")
      async def cogs_autocomplete(self, interaction: Interaction, cog: str):
        try:
          cogs: list[str] = []
          for root, _, files in walk("cogs"):
            for file in files:
              if file.endswith(".py"):
                cog_path = f"{root.replace(sep, '.')}.{file[:-3]}"
                cogs.append(cog_path)

          filtered_cogs = [c for c in cogs if cog.lower() in c.lower()]
          filtered_cogs = filtered_cogs[:25]
          await interaction.response.send_autocomplete(filtered_cogs)
        except ValueError:
          pass
    except ValueError:
      pass

    @manage_cogs.error
    async def command_error(self, interaction:Interaction, error: Exception):
      if isinstance(error, commands.CommandError):
        await interaction.followup.send(f"❌ Произошла ошибка: {str(error)}",ephemeral=True)
      else:
        await interaction.followup.send(f"❌ Произошла неизвестная ошибка: {str(error)}",ephemeral=True)
  except Exception:
    pass

def setup(bot: commands.Bot):
  bot.add_cog(CogsEditor(bot))
