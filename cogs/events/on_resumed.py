from nextcord.ext import commands
from datetime import datetime

class OnResumed(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_resumed(self):
    print(f'🔄\033[38;5;51m{self.bot.user if self.bot.user else "Бот"}\033[0m \033[38;5;82mвосстановил соединение в\033[0m \033[38;5;226m{datetime.now()}\033[0m')

def setup(bot:commands.Bot):
  bot.add_cog(OnResumed(bot))