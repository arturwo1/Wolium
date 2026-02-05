from nextcord.ext import commands
from datetime import datetime

class OnDisconnect(commands.Cog):
  def __init__(self,bot):
    self.bot:commands.Bot=bot
  
  @commands.Cog.listener()
  async def on_disconnect(self):
    print(f'❌ \033[38;5;51m{self.bot.user if self.bot.user else "Бот"}\033[0m \033[38;5;196mотключился от Discord в\033[0m \033[38;5;226m{datetime.now()}\033[0m')

def setup(bot:commands.Bot):
  bot.add_cog(OnDisconnect(bot))