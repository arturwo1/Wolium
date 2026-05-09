from nextcord.ext import commands, tasks
from nextcord.errors import HTTPException, NotFound, Forbidden
from asyncio import sleep
from time import time as now_time
from json import loads
from Utils.parse_time import parse_time
from Utils.config import pending

class TTLListener(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.check.start()

  def cog_unload(self):
    self.check.cancel()

  @tasks.loop(seconds=5)
  async def check(self):
    gd = self.bot.get_cog("GetData")
    ud = self.bot.get_cog("UpdateData")
    if not gd or not ud:
      return

    now_ts = int(now_time())

    for guild in self.bot.guilds:
      guild_id = guild.id

      cfg = await gd.get_data(
        guild_id,
        ["ttl_channel", "ttl_messages"],
        "guild_settings",
        "guild_id",
        guild
      )

      ttl_channels = loads(cfg.get("ttl_channel")) or {}
      ttl_messages = loads(cfg.get("ttl_messages")) or {}

      changed = False

      guild_pending = pending.pop(guild_id, None)
      if guild_pending:
        for ch_key, msgs in guild_pending.items():
          bucket = ttl_messages.get(ch_key) or {}
          bucket.update(msgs)
          ttl_messages[ch_key] = bucket
        changed = True

      if not ttl_messages:
        if changed:
          await ud.update_data(guild_id, {"ttl_messages": ttl_messages}, "guild_settings", "guild_id", guild)
        continue

      deleted_this_tick = 0
      MAX_DELETES_PER_TICK = 20

      for ch_key, msgs in list(ttl_messages.items()):
        ttl_str = ttl_channels.get(str(ch_key))
        ttl_sec = int(parse_time(ttl_str) or 0) if ttl_str else 0

        if ttl_sec <= 0:
          if msgs:
            ttl_messages.pop(ch_key, None)
            changed = True
          continue

        channel = guild.get_channel(int(ch_key))
        if not channel:
          continue

        for msg_id, created_ts in list(msgs.items()):
          if now_ts < int(created_ts) + ttl_sec:
            continue

          try:
            msg = await channel.fetch_message(int(msg_id))
            await msg.delete()
          except NotFound:
            pass
          except Forbidden:
            pass
          except HTTPException as e:
            retry_after = getattr(e, "retry_after", None)
            await sleep(float(retry_after) if retry_after else 1.0)
            break

          msgs.pop(msg_id, None)
          changed = True
          deleted_this_tick += 1
          if deleted_this_tick >= MAX_DELETES_PER_TICK:
            break

        if not msgs:
          ttl_messages.pop(ch_key, None)
          changed = True

        if deleted_this_tick >= MAX_DELETES_PER_TICK:
          break

      if changed:
        await ud.update_data(guild_id, {"ttl_messages": ttl_messages}, "guild_settings", "guild_id", guild)

  @check.before_loop
  async def before_check(self):
    await self.bot.wait_until_ready()

def setup(bot: commands.Bot):
  bot.add_cog(TTLListener(bot))