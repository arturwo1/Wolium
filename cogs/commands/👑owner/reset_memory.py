import nextcord
from nextcord.ext import commands
from Utils.config import message_for_wolium, history

class ResetMemory(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.command(name="reset_memory",
    hidden=True,
    aliases=["ресет_памяти","memory_reset","break_memory","reset_memory","memory_break"])
  async def reset_memory(self,ctx: commands.Context,):
    if not await self.bot.is_owner(ctx.author):
      return
    
    global history
    try:
      await ctx.reply(f"AI memory has been successfully reset.\nDuring this session, `{len(history)}` **messages** and `{len(str(history))}` **characters** were saved.",delete_after=15)
      await ctx.message.delete(delay=15)
    except nextcord.errors.HTTPException:
      pass
    history = [
      {
        "role": "system",
        "content": message_for_wolium
      }
    ]

def setup(bot:commands.Bot):
  bot.add_cog(ResetMemory(bot))