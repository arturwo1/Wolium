import nextcord
from nextcord.ext import commands
import asyncio
from datetime import datetime, timedelta
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot

time_of_join = {}

class OnVoiceStateUpdate(commands.Cog):
  def __init__(self, bot:commands.Bot):
    self.bot = bot
  
  @commands.Cog.listener()
  async def on_voice_state_update(self, member: nextcord.Member, before: nextcord.VoiceState, after: nextcord.VoiceState):
    if not member:
      return
    global time_of_join
    user_id = member.id
    guild_id = member.guild.id if member.guild else None

    if guild_id in servers_with_no_acces_for_bot or user_id in users_with_no_acces_for_bot:
      return
    if not self.bot.get_user(user_id):
      return
    
    get_data = self.bot.get_cog('GetData')
    update_data = self.bot.get_cog('UpdateData')

    if guild_id:
      guild_settings = await get_data.get_data(guild_id,['banned'],'guilds','guild_id',member.guild)
    user_settings = await get_data.get_data(user_id,['banned'],'users','user_id',member.guild)

    if user_settings['banned'] or (guild_settings['banned'] if member.guild else False):
      servers_with_no_acces_for_bot.append(guild_id)
      users_with_no_acces_for_bot.append(user_id)
      return
    
    user_privacy = await get_data.get_data(user_id,['save_voice'], 'user_privacy', 'user_id', member.guild)
    
    if not user_privacy['save_voice']:
      return

    sdeaf = member.voice.self_deaf if member.voice else None
    smute = member.voice.self_mute if member.voice else None
    deaf = member.voice.deaf if member.voice else None
    mute = member.voice.mute if member.voice else None

    before_channel_id = before.channel.id if before.channel else None
    after_channel_id = after.channel.id if after.channel else None
    user_id = member.id
    enter_time = None
    leave_time = None
    
    time_spent = None

    user_data = await get_data.get_data(user_id,['xp','bank_balance','balance','upgrade'],'user_data','user_id',member.guild)
    xp = user_data['xp']
    bank_balance = user_data['bank_balance']
    balance = user_data['balance']
    upgrade = user_data['upgrade']
    reward_per_voice = (0.001*upgrade)
        
    if before.channel is None and after.channel and sdeaf!=True and smute!=True and deaf!=True and mute!=True:
      joined_at_voice = datetime.now()
      await asyncio.sleep(20)
      if after.channel and len(after.channel.members) == 1:
        await asyncio.sleep(20)
        if len(member.guild.voice_channels) == 1 and member in member.guild.voice_channels:
          return
      time_of_join[member.id] = joined_at_voice
    
    elif before.channel and after.channel is None:
      if member.id in time_of_join and sdeaf!=True and smute!=True and deaf!=True and mute!=True:
        enter_time = time_of_join.pop(member.id)
        leave_time = datetime.now()
        
        time_spent: timedelta = leave_time-enter_time

        voice_reward = reward_per_voice*time_spent.total_seconds()

        data = {
          'xp': xp+round(time_spent.total_seconds()/60),
          'bank_balance': bank_balance+voice_reward,
          'balance': balance+voice_reward,
        }
        await update_data.update_data(user_id, data, 'user_data', 'user_id', member.guild)

        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          async with self.bot.db_pool.acquire() as connection:
            query = """
            INSERT INTO voice (guild_id, before_channel_id, after_channel_id, user_id, enter_time, leave_time, time_spent)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            await connection.execute(query, guild_id, before_channel_id, after_channel_id, user_id, enter_time, leave_time, time_spent)

    elif before.channel and after.channel and before.channel!=after.channel:
      if member.id in time_of_join and sdeaf!=True and smute!=True and deaf!=True and mute!=True:
        enter_time = time_of_join.pop(member.id)
        leave_time = datetime.now()
        time_of_join[member.id] = datetime.now()

        time_spent: timedelta = leave_time-enter_time

        voice_reward = reward_per_voice*time_spent.total_seconds()

        data = {
          'xp': xp+round(time_spent.total_seconds()/60),
          'bank_balance': bank_balance+voice_reward,
          'balance': balance+voice_reward,
        }
        await update_data.update_data(user_id, data, 'user_data', 'user_id', member.guild)

        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          async with self.bot.db_pool.acquire() as connection:
            query = """
            INSERT INTO voice (guild_id, before_channel_id, after_channel_id, user_id, enter_time, leave_time, time_spent)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            await connection.execute(query, guild_id, before_channel_id, after_channel_id, user_id, enter_time, leave_time, time_spent)

def setup(bot:commands.Bot):
  bot.add_cog(OnVoiceStateUpdate(bot))