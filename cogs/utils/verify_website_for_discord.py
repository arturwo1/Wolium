from nextcord.ext.commands import Cog, Bot
from aiohttp import web

class VerifyWebsiteForDiscord(Cog):
  def __init__(self,bot:Bot):
    self.bot=bot
  
  async def discord_verification(self, request):
    return web.Response(
      body=b'dh=8af7099341fbbff1fa2e346576c1b378153cf341',
      content_type='text/plain'
    )

def setup(bot:Bot):
  bot.add_cog(VerifyWebsiteForDiscord(bot))