from nextcord.ext import commands
from nextcord import RawMessageDeleteEvent

class OnRawMessageDelete(commands.Cog):
  def __init__(self, bot:commands.Bot):
    self.bot = bot
  
  @commands.Cog.listener()
  async def on_raw_message_delete(self, payload: RawMessageDeleteEvent):
    try:
      bunker_utils = self.bot.get_cog("BunkerUtils")
      if bunker_utils:
        await bunker_utils.handle_message_delete(payload)
    except Exception: pass
  
def setup(bot:commands.Bot):
  bot.add_cog(OnRawMessageDelete(bot))