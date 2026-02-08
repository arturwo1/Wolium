from nextcord import Interaction
from nextcord.ext import commands
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot

class ApplicationCommandCheck(commands.Cog):
  def __init__(self, bot:commands.Bot):
    self.bot = bot

    bot.add_application_command_check(self.application_command_check)

  def cog_unload(self):
    self.bot.remove_application_command_check(self.application_command_check)

  async def application_command_check(self, interaction: Interaction) -> bool:
    language = interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'
    get_data = self.bot.get_cog("GetData")
    translate_message = self.bot.get_cog("TranslateMessage")

    if not (get_data and translate_message):
      from cogs.utils.translate_message import TranslateMessage
      await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Не Удалось Загрузить Важные Модули, Повторите Команду Снова.", language), ephemeral=True)
      return False

    if ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
      await interaction.response.send_message(await translate_message.translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",language), ephemeral=True)
      return False
    user_id = interaction.user.id

    if interaction.guild:
      guild_settings = await get_data.get_data(interaction.guild.id,['banned'],'guilds','guild_id',interaction.guild)
    user_settings = await get_data.get_data(user_id,['language','variation','banned'],'users','user_id',interaction.guild)
    language = user_settings['language']

    if user_settings['banned'] or (guild_settings['banned'] if interaction.guild else False):
      await interaction.response.send_message(await translate_message.translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://wolium.netlify.app/rules/) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",language), ephemeral=True)
      servers_with_no_acces_for_bot.append(interaction.guild.id)
      users_with_no_acces_for_bot.append(user_id)
      return False
    
    return True
def setup(bot:commands.Bot):
  bot.add_cog(ApplicationCommandCheck(bot))