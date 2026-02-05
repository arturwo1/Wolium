import nextcord
from nextcord.ext import commands
from cogs.utils.translate_message import TranslateMessage

class OnCommandError(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_command_error(self, ctx: commands.Context,error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
      try:
        if ctx.guild:
          language = ctx.guild.preferred_locale if ctx.guild.preferred_locale!='en-US' and ctx.guild.preferred_locale!='en-GB' and ctx.guild.preferred_locale!='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'en' if ctx.guild.preferred_locale=='en-US' or ctx.guild.preferred_locale=='en-GB' and ctx.guild.preferred_locale!='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'es' if ctx.guild.preferred_locale!='en-US' and ctx.guild.preferred_locale!='en-GB' and ctx.guild.preferred_locale=='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'sv'
        else:
          language = "en"
        await ctx.reply(await (TranslateMessage(self.bot)).translate_message("Command not found.",language), delete_after=15)
        await ctx.message.delete(delay=15)
      except nextcord.errors.HTTPException:
        pass
    elif isinstance(error, commands.MissingRequiredArgument):
      try:
        if ctx.guild:
          language = ctx.guild.preferred_locale if ctx.guild.preferred_locale!='en-US' and ctx.guild.preferred_locale!='en-GB' and ctx.guild.preferred_locale!='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'en' if ctx.guild.preferred_locale=='en-US' or ctx.guild.preferred_locale=='en-GB' and ctx.guild.preferred_locale!='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'es' if ctx.guild.preferred_locale!='en-US' and ctx.guild.preferred_locale!='en-GB' and ctx.guild.preferred_locale=='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'sv'
        else:
          language = "en"
        await ctx.reply(await (TranslateMessage(self.bot)).translate_message("Ошибка: отсутствует аргумент",language)+f" **`{error.param.name}`**.", delete_after=15)
        await ctx.message.delete(delay=15)
      except nextcord.errors.HTTPException:
        pass
    else:
      raise error

def setup(bot:commands.Bot):
  bot.add_cog(OnCommandError(bot))