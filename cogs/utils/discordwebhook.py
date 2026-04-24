from nextcord.ext import commands
from traceback import format_exception
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from json import loads
from aiohttp import web
from nextcord import Color
from os import getenv

class DiscordWebhook(commands.Cog):
  def __init__(self,bot):
    self.bot:commands.Bot=bot
  
  async def discord_info(self,request):
    try:
      signature = request.headers["X-Signature-Ed25519"]
      timestamp = request.headers["X-Signature-Timestamp"]
      body = await request.read()
      
      verify_key = VerifyKey(bytes.fromhex(getenv('DISCORD_WEB_API_WEBHOOK_CLIENT_SECRET')))
      verify_key.verify(f"{timestamp}".encode() + body, bytes.fromhex(signature))
    except BadSignatureError:
      return web.Response(status=401, text="invalid request signature")
    
    data = loads(body)

    if data["type"] == 1:
      return web.json_response({"type": 1})

    fields = [{
        'name':'Request',
        'value':f"**```py\n{str(await request.json())}```**",
        'inline':False
      }]
    try:
      await self.bot.get_cog("SendEmbed").send_embed(
        title="Discord webhook",
        description=f"### Discord received a message",
        color=Color.brand_green(),
        fields=fields,
        footer_text="Discord webhook!"
      )
    except Exception as e:
      print('Error in on_dbl_vote\n',''.join(format_exception(type(e), e, e.__traceback__)))
      return web.Response(status=400,text=str(e))

    return web.Response(status=200,text="OK")
  
def setup(bot:commands.Bot):
  bot.add_cog(DiscordWebhook(bot))