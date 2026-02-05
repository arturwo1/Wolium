import nextcord
from nextcord.ext import commands
from datetime import datetime
import asyncio


class CountUserMessages(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  
  async def count_user_messages(self, user_id, tYpe, guild, channel, bank, user_user_id):
    start_time = datetime.now()
    total_messages_all = 0
    total_messages_guild = 0
    total_messages_channel = 0

    async def count_messages_in_channel(channel):
      """Подсчитывает сообщения пользователя в указанном канале."""
      count = 0
      try:
        async for message in channel.history(limit=None):
          if message.author.id == user_id:
            count += 1
      except nextcord.Forbidden:
        pass
      return count

    async def count_messages_in_guild(guild):
      """Подсчитывает сообщения пользователя на сервере."""
      tasks = [count_messages_in_channel(channel) for channel in guild.text_channels]
      results = await asyncio.gather(*tasks, return_exceptions=True)
      return sum(r for r in results if isinstance(r, int))

    if bank:
      user = await self.bot.fetch_user(user_user_id)
      dm = await user.create_dm()

      dm_message = await dm.send(
        "# Загруженные Данные\n"
        "**Всего Сообщений**: 0\n"
        "**Сообщений На Сервере**: 0\n"
        "**Сообщений В Канале**: 0\n"
        "Прогрузилось За: 0 секунд"
      )

      tasks_all_guilds = [count_messages_in_guild(g) for g in self.bot.guilds]
      total_messages_all = sum(await asyncio.gather(*tasks_all_guilds, return_exceptions=True))

      if guild:
        total_messages_guild = await count_messages_in_guild(guild)

      if channel:
        total_messages_channel = await count_messages_in_channel(channel)

      elapsed_time = str(datetime.now() - start_time)[:-4]
      await dm_message.edit(
        f"# Загруженные Данные\n"
        f"**Всего Сообщений**: {total_messages_all}\n"
        f"**Сообщений На Сервере**: {total_messages_guild}\n"
        f"**Сообщений В Канале**: {total_messages_channel}\n"
        f"Прогрузилось За: {elapsed_time}"
      )

      return total_messages_all, total_messages_guild, total_messages_channel, elapsed_time
    else:
      if tYpe == "all":
        tasks_all_guilds = [count_messages_in_guild(g) for g in self.bot.guilds]
        total_messages_all = sum(await asyncio.gather(*tasks_all_guilds, return_exceptions=True))

      elif tYpe == "guild":
        if guild:
          total_messages_guild = await count_messages_in_guild(guild)

      elif tYpe == "channel":
        if channel:
          total_messages_channel = await count_messages_in_channel(channel)

      elapsed_time = str(datetime.now() - start_time)[:-4]
      return total_messages_all, total_messages_guild, total_messages_channel, elapsed_time

def setup(bot:commands.Bot):
  bot.add_cog(CountUserMessages(bot))