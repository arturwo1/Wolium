from asyncio import sleep
from datetime import datetime, timezone
from nextcord.ext import commands
from nextcord import Color, ButtonStyle
from nextcord.ui import View, Button
from aiohttp import web, ClientSession
from os import getenv
from cogs.utils.ensure_user_exists import EnsureUserExists
from cogs.utils.get_data import GetData
from cogs.utils.send_embed import SendEmbed
from time import time
from cogs.utils.update_data import UpdateData

class WebMain(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  async def index(self,request):
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Discord Embedded App</title></head>
    <body>
      <h1>Добро пожаловать в мое Discord Embedded App!</h1>
      <p>Это главная страница вашего приложения.</p>
    </body>
    </html>
    """
    return web.Response(text=html_content,content_type='text/html',headers={'Content-Security-Policy': "default-src * 'unsafe-inline';",'X-Frame-Options': 'ALLOWALL'})

def setup(bot:commands.Bot):
  bot.add_cog(WebMain(bot))