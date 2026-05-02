from nextcord import Guild, Interaction, Colour
from nextcord.ext import commands
from asyncio import sleep
from json import dumps

class OnApplicationCommandCompletion(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  def _flatten_options(self, opts):
    out = []
    if not opts:
      return out
    for opt in opts:
      name = opt.get("name")
      if "value" in opt:
        out.append((name, opt.get("value")))
      if "options" in opt:
        out.extend(self._flatten_options(opt.get("options")))
    return out
  
  def _mentionify(self, guild:Guild, value):
    if isinstance(value, int) or isinstance(value, str):
      try:
        value = int(value)
      except Exception:
        return str(value)
      try:
        user = guild.get_member(value) if guild else self.bot.get_user(value)
        if user:
          return f"<@{value}>"
      except Exception:
        pass
      try:
        role = guild.get_role(value) if guild else None
        if role:
          return f"<@&{value}>"
      except Exception:
        pass
      try:
        channel = guild.get_channel(value) if guild else self.bot.get_channel(value)
        if channel:
          return f"<#{value}>"
      except Exception:
        pass
      try:
        guild = self.bot.get_guild(value)
        if guild:
          return f"{guild.name}"
      except Exception:
        pass
    return value
  
  @commands.Cog.listener()
  async def on_application_command_completion(self, interaction: Interaction):
    user = interaction.user
    guild = interaction.guild
    channel = interaction.channel
    gd = None
    gi = None
    se = None
    while not (gd and gi and se):
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")
      se = self.bot.get_cog("SendEmbed")
      await sleep(1)

    user_privacy = await gd.get_data(user.id, ['track_activity'], 'user_privacy', 'user_id', guild)
    if not user_privacy['track_activity']: return

    command_name = interaction.application_command.name if interaction.application_command and interaction.application_command.name else "Unknown"
    options = interaction.data.get("options", [])
    flat = self._flatten_options(options)
    options_str = f"**/{command_name}**"
    if options and flat:
      for name, value in flat:
        options_str += f" `{name}`  **{self._mentionify(guild, value)}**"

    invite = await gi.invite(guild)
    fields = [
      {
        'name':'Server',
        'value':f"{guild.id} | {invite} | {guild.name}" if guild else "DM",
        'inline':True
      },
      {
        'name':'Channel',
        'value':f"<#{channel.id}>(`{channel.id}` | `{channel.name if guild else f'[<@{user.id}>({user.id} | {user.name}({user.display_name})]'}`)" if channel else "Not Found",
        'inline':True
      }
    ]

    await se.send_embed(
      title="Command Input",
      description=f"User Input: ||{options_str}||",
      color=Colour.yellow(),
      fields=fields,
      footer_text=command_name,
      author_text=user.name,
      author_icon=f"{user.display_avatar.url}",
      channel_id=1348577723097808977
    )

    if getattr(self.bot, "db_pool") and self.bot.db_pool:
      user_id = user.id
      guild_id = guild.id if guild else None
      channel_id = channel.id if channel else None
      args = dumps(dict(flat))

      async with self.bot.db_pool.acquire() as conn:
        async with conn.transaction():
          await conn.execute("WITH cmd AS (INSERT INTO public.commands (name) VALUES ($5) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id ) INSERT INTO public.user_commands (user_id, guild_id, channel_id, command_id, args) VALUES ($1, $2, $3, (SELECT id FROM cmd), $4)", user_id, guild_id, channel_id, args, command_name)

def setup(bot:commands.Bot):
  bot.add_cog(OnApplicationCommandCompletion(bot))