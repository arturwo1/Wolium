from nextcord.ext import commands
from asyncio import sleep

class OnHttpRatelimit(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_http_ratelimit(self,limit:int,remaining:int,reset_after:float,bucket:str,scope:str):
    print(f"⚠ HTTP Rate Limit:\n  {limit=},\n  {remaining=},\n  {reset_after=},\n  {bucket=},\n  {scope=}")
    await sleep(reset_after)
  
def setup(bot:commands.Bot):
  bot.add_cog(OnHttpRatelimit(bot))