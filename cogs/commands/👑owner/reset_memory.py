import nextcord
from nextcord.ext import commands
from Utils.config import message_for_wolium, history

class ResetMemory(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.command(name="сброс_памяти",
    hidden=True,
    aliases=["ресет_памяти","memory_reset","break_memory","reset_memory","memory_break"])
  async def сброс_памяти(self,ctx: commands.Context,):
    if not await self.bot.is_owner(ctx.author):
      return
    
    global history
    try:
      await ctx.reply(f"Память Нейросети Была Успешно Сброшена,\nЗа Этот Момент Было Сохранено `{len(history)}` **Сообщений** и `{len(str(history))}` **Символов**.",delete_after=15)
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