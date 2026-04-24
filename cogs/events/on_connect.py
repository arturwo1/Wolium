from nextcord.ext import commands
from datetime import datetime

class OnConnect(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_connect(self):
    self.bot.add_all_application_commands()
    await self.bot.sync_application_commands()
    print(f'🔗\033[38;5;51m{self.bot.user if self.bot.user else "Bot"}\033[0m \033[38;5;82mconnected to Discord at\033[0m \033[38;5;226m{datetime.now()}\033[0m')

def setup(bot: commands.Bot):
  bot.add_cog(OnConnect(bot))