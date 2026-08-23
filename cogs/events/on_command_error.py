import nextcord
from nextcord.ext import commands

class OnCommandError(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @commands.Cog.listener()
  async def on_command_error(self, ctx: commands.Context,error: commands.CommandError):
    tm = self.bot.get_cog("TranslateMessage")
    if isinstance(error, commands.CommandNotFound):
      try:
        if ctx.guild:
          language = ctx.guild.preferred_locale if ctx.guild.preferred_locale!='en-US' and ctx.guild.preferred_locale!='en-GB' and ctx.guild.preferred_locale!='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'en' if ctx.guild.preferred_locale=='en-US' or ctx.guild.preferred_locale=='en-GB' and ctx.guild.preferred_locale!='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'es' if ctx.guild.preferred_locale!='en-US' and ctx.guild.preferred_locale!='en-GB' and ctx.guild.preferred_locale=='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'sv'
        else:
          language = "en"
        await ctx.reply(await tm.translate_message("error.command_not_found",language), delete_after=15)
        await ctx.message.delete(delay=15)
      except nextcord.errors.HTTPException:
        pass
    elif isinstance(error, commands.MissingRequiredArgument):
      try:
        if ctx.guild:
          language = ctx.guild.preferred_locale if ctx.guild.preferred_locale!='en-US' and ctx.guild.preferred_locale!='en-GB' and ctx.guild.preferred_locale!='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'en' if ctx.guild.preferred_locale=='en-US' or ctx.guild.preferred_locale=='en-GB' and ctx.guild.preferred_locale!='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'es' if ctx.guild.preferred_locale!='en-US' and ctx.guild.preferred_locale!='en-GB' and ctx.guild.preferred_locale=='es-ES' and ctx.guild.preferred_locale!='sv-SE' else 'sv'
        else:
          language = "en"
        error_msg = await tm.translate_message("error.missing_argument",language)
        await ctx.reply(f"{error_msg} **`{error.param.name}`**.", delete_after=15)
        await ctx.message.delete(delay=15)
      except nextcord.errors.HTTPException:
        pass
    else:
      raise error

def setup(bot:commands.Bot):
  bot.add_cog(OnCommandError(bot))