import nextcord
from nextcord.ext import commands
from nextcord.ui import View
from datetime import datetime,timezone

class SendEmbed(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  async def send_embed(self, title:str, description:str, color:nextcord.Color=nextcord.Color.yellow(), fields:list[dict[str,str|bool]]=None, footer_text:str=None, author_text:str=None, author_icon:str=None,guild_id:int=807304463449849938,channel_id:int=1159138280651104256, view:View=None):
    """### Example: 
```py
fields: [
  {
    'name':'',
    'value':'',
    'inline':False
  },
  {
    'name':'',
    'value':'',
    'inline':False
  }
]
```
    """
    channel = self.bot.get_guild(guild_id).get_channel(channel_id)
    embed = nextcord.Embed(
      title=title,
      description=description,
      color=color,
      timestamp=datetime.now(timezone.utc)
    )
    if author_text:
      embed.set_author(
        name=author_text,
        icon_url=author_icon
      )
    if fields:
      for field in fields:
        if 'name' not in field or 'value' not in field or 'inline' not in field:
          continue
        name = field['name']
        value = field['value']
        inline = field['inline']
        for i in range(0, len(value), 1000):
          if len(value)>=1000:
            embed.add_field(
              name=name,
              value=f"**```py\n{value[i:i+1000]}```**",
              inline=inline
            )
          else:
            embed.add_field(
              name=name,
              value=value[i:i+1000],
              inline=inline
            )
    if footer_text:
      embed.set_footer(
        text=footer_text,
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
    try:
      return await channel.send(embed=embed,view=view), embed
    except nextcord.Forbidden:
      pass

def setup(bot:commands.Bot):
  bot.add_cog(SendEmbed(bot))