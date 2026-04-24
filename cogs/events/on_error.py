from nextcord.ext import commands
from nextcord.errors import ConnectionClosed

class OnError(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_error(self, event, *args, **kwargs):
    import sys
    exc_type, exc_value, _ = sys.exc_info()

    if isinstance(exc_value, ConnectionClosed):
      if exc_value.code == 1000:
        print(f"\033[38;5;226m🔁Connection closed normally (code 1000) —\033[0m \033[38;5;226mshard {exc_value.shard_id}\033[0m")
        return
    return await super(type(self.bot), self.bot).on_error(event, *args, **kwargs)
  
def setup(bot:commands.Bot):
  bot.add_cog(OnError(bot))