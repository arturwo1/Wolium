from nextcord.ext import commands
from datetime import datetime
from asyncio import sleep

class OnConnect(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  async def cleanup_duplicate_commands(self, guild_id: int = None):
    app_id = self.bot.application_id or (await self.bot.application_info()).id
    
    if guild_id:
      raw_commands = await self.bot.http.get_guild_commands(app_id, guild_id)
    else:
      raw_commands = await self.bot.http.get_global_commands(app_id)

    seen_commands = {}
    to_delete = []

    for cmd in raw_commands:
      name = cmd['name']
      cmd_type = cmd.get('type', 1)
      identifier = (name, cmd_type)

      if identifier in seen_commands:
        to_delete.append(cmd['id'])
      else:
        seen_commands[identifier] = cmd['id']

    for cmd_id in to_delete:
      try:
        if guild_id:
          await self.bot.http.delete_guild_command(app_id, guild_id, cmd_id)
        else:
          await self.bot.http.delete_global_command(app_id, cmd_id)
        print(f"🗑️ Deleted command duplicate. ID: {cmd_id}")
        await sleep(0.5) 
      except Exception as e:
        print(f"❌ Failed to delete command duplicate. ID: {cmd_id}; {e}")
  
  @commands.Cog.listener()
  async def on_connect(self):
    await self.cleanup_duplicate_commands()
    for guild in self.bot.guilds:
      await self.cleanup_duplicate_commands(guild.id)
    self.bot.add_all_application_commands()
    await self.bot.sync_application_commands()
    print(f'🔗\033[38;5;51m{self.bot.user if self.bot.user else "Bot"}\033[0m \033[38;5;82mconnected to Discord at\033[0m \033[38;5;226m{datetime.now()}\033[0m')

def setup(bot: commands.Bot):
  bot.add_cog(OnConnect(bot))