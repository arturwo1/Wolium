from datetime import timedelta
from traceback import format_exception
from nextcord import Member, Embed, Interaction, message_command, Message, TextInputStyle, ButtonStyle, Colour
from nextcord.ext import commands
from nextcord.ui import Modal, View, Button, TextInput
from time import time
from Utils import parse_time
import Utils.translate_to_all_languages

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages
report_cooldown = {}

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class ReportModal(Modal):
  def __init__(self, interaction:Interaction, message:Message, language:str, mod_channel_id: int, bot:commands.Bot,timeout=60*5):
    super().__init__(title=translate_to_all_languages("report.message", 'message', language),timeout=timeout)
    self.interaction = interaction
    self.message = message
    self.language = language
    self.mod_channel_id = mod_channel_id
    self.bot = bot

    self.reason = TextInput(
      label=translate_to_all_languages("general.reason_label", 'message', language),
      style=TextInputStyle.short,
      max_length=28,
      required=True,
      default_value=None,
      placeholder=translate_to_all_languages("report.reason_desc", 'message', language)
    )
    self.add_item(self.reason)
      
  async def callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    tm = self.bot.get_cog("TranslateMessage")
    gi = self.bot.get_cog("GetInvite")
    se = self.bot.get_cog("SendEmbed")
    
    await interaction.followup.send(await tm.translate_message("moderation.report_success", self.language), ephemeral=True)
    invite = await gi.invite(interaction.guild)
    fields = [
      {
        'name':'Server',
        'value':f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
        'inline':True
      },
      {
        'name':await tm.translate_message('general.channel', self.language),
        'value':f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'DM'}`)",
        'inline':True
      },
      {
        'name':await tm.translate_message('moderation.report_reporting_user', self.language),
        'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
        'inline':True
      },
      {
        'name':await tm.translate_message('moderation.report_reported_user', self.language),
        'value':f"{self.message.author.id} | {self.message.author.mention} | {self.message.author.name}",
        'inline':True
      },
      {
        'name':await tm.translate_message('general.message', self.language),
        'value':str(self.message.content)[:256],
        'inline':True
      },
      {
        'name':await tm.translate_message('general.reason', self.language),
        'value':f"**`{self.reason.value}`**",
        'inline':True
      }
    ]
    await se.send_embed(
      title=await tm.translate_message("moderation.report_title", self.language),
      description=f"**{interaction.user.mention}** reported message from **{self.message.author.mention}**\nReason: **`{self.reason.value}`**",
      color=Colour.yellow(),
      fields=fields,
      footer_text=await tm.translate_message("moderation.report_message_title", self.language),
      author_text=interaction.user.name,
      author_icon=interaction.user.display_avatar.url,
      channel_id=1356660605364469951
    )
    messagemod, modembed = await se.send_embed(
      title=await tm.translate_message("moderation.report_title", self.language),
      description=f"**{interaction.user.mention}** reported message from **{self.message.author.mention}**\n{self.message.content}\nReason: **`{self.reason.value}`**",
      color=Colour.yellow(),
      fields=fields[1:],
      footer_text=await tm.translate_message("moderation.report_message_title", self.language),
      author_text=interaction.user.name,
      author_icon=interaction.user.display_avatar.url,
      channel_id=self.mod_channel_id,
      guild_id=interaction.guild.id
    )
    await messagemod.edit(embed=modembed, view=ViolationsView(self.message.author, self.language, self.reason.value, self.mod_channel_id, self.message, modembed, self.bot))

class ReportView(View):
  def __init__(self, interaction:Interaction, message:Message, language:str, mod_channel_id:int, bot:commands.Bot, timeout=60*5):
    super().__init__(timeout=timeout)
    self.interaction = interaction
    self.message = message
    self.language = language
    self.mod_channel_id = mod_channel_id
    self.bot = bot

    report_button = Button(
      style=ButtonStyle.red,
      emoji='❌',
      label=translate_to_all_languages("moderation.report_button", 'message', self.language)
    )
    report_button.callback = self.report_callback
    self.add_item(report_button)

  async def report_callback(self, interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.send_modal(ReportModal(self.interaction, self.message, self.language, self.mod_channel_id, self.bot))
    self.children[0].disabled = True
    await interaction.edit_original_message(view=self)

class MuteModal(Modal):
  def __init__(self, member:Member, language:str,reason:str, message:Message, embed:Embed, bot:commands.Bot,timeout=60*5):
    super().__init__(title=translate_to_all_languages("moderation.enter_timeout_duration", 'message', language),timeout=timeout)
    self.bot = bot
    self.member = member
    self.language = language
    self.reason = reason
    self.message = message
    self.embed = embed
    self.duration = TextInput(
      label=translate_to_all_languages("general.duration_label", 'message', language),
      style=TextInputStyle.short,
      max_length=28,
      required=True,
      default_value=None,
      placeholder=translate_to_all_languages("moderation.timeout_format_hint", 'message', language)
    )
    self.add_item(self.duration)
      
  async def callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    tm = self.bot.get_cog("TranslateMessage")
    av = self.bot.get_cog("AddViolation")
    
    duration = parse_time(self.duration.value)
    if duration == None:
      await interaction.followup.send(await tm.translate_message("moderation.invalid_mute_duration", self.language), ephemeral=True)
      return
    if duration > 60*60*24*7*2:
      await interaction.followup.send(await tm.translate_message("moderation.mute_max_duration", self.language, variables={"duration": f"`{timedelta(seconds=duration)}`"}), ephemeral=True)
      return
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await tm.translate_message("moderation.user_not_found", self.language), ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await tm.translate_message("moderation.guild_only", self.language), ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'moderate_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.bot_no_mute_perms", self.language), ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'moderate_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.insufficient_mute_perms", self.language), ephemeral=True)
      return
    if interaction.user != interaction.guild.owner and interaction.user.guild_permissions.value < self.member.guild_permissions.value:
      await interaction.followup.send(await tm.translate_message("moderation.insufficient_perms", self.language, variables={"user": self.member.mention}), ephemeral=True)
      return
    try:
      await self.member.timeout(timeout=timedelta(seconds=duration if duration else 0), reason=self.reason)
      await av.add_violation(self.member.id, interaction.guild.id, 'mute', self.reason, duration, round(time()), interaction.user.id)
      try:
        await self.member.send(await tm.translate_message("moderation.mute_dm_notification", self.language, variables={"reason": self.reason, "duration": f"`{timedelta(seconds=duration)}`"}))
      except Exception:
        pass
      self.embed.add_field(
        name=await tm.translate_message("moderation.verdict", self.language),
        value=f'**{self.member.mention}** ' + await tm.translate_message("moderation.mute_success", self.language, variables={"duration": f"`{timedelta(seconds=duration)}`", "reason": self.reason})
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await tm.translate_message("moderation.mute_failed", self.language), ephemeral=True)
    
class ViolationsView(View):
  def __init__(self, member:Member, language:str,reason:str, mod_log_channel:int, message:Message, embed:Embed, bot:commands.Bot):
    super().__init__(timeout=None)
    self.language = language
    self.reason = reason
    self.member = member
    self.message = message
    self.embed = embed
    self.bot = bot
    self.mod_log_channel = mod_log_channel
    self.add_violations()

  def add_violations(self):
    ban_button = Button(
      custom_id="ban",
      style=ButtonStyle.primary,
      emoji="🔨",
      label=translate_to_all_languages("moderation.ban_cap", 'message', self.language)
    )
    ban_button.callback = self.ban_callback
    self.add_item(ban_button)

    kick_button = Button(
      custom_id="kick",
      style=ButtonStyle.primary,
      emoji='👢',
      label=translate_to_all_languages("moderation.kick", 'message', self.language)
    )
    kick_button.callback = self.kick_callback
    self.add_item(kick_button)

    mute_button = Button(
      custom_id="mute",
      style=ButtonStyle.primary,
      emoji='🔇',
      label=translate_to_all_languages("moderation.mute", 'message', self.language)
    )
    mute_button.callback = self.mute_callback
    self.add_item(mute_button)

    warn_button = Button(
      custom_id="warn",
      style=ButtonStyle.primary,
      emoji='⚠️',
      label=translate_to_all_languages("moderation.warn", 'message', self.language)
    )
    warn_button.callback = self.warn_callback
    self.add_item(warn_button)

  async def ban_callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    tm = self.bot.get_cog("TranslateMessage")
    av = self.bot.get_cog("AddViolation")
    
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await tm.translate_message("moderation.user_not_found", self.language), ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await tm.translate_message("moderation.guild_only", self.language), ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'ban_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.bot_no_ban_perms", self.language), ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'ban_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.insufficient_perms", self.language, variables={"user": self.member.mention}), ephemeral=True)
      return
    if interaction.user != interaction.guild.owner and interaction.user.guild_permissions.value < self.member.guild_permissions.value:
      await interaction.followup.send(await tm.translate_message("moderation.insufficient_perms", self.language, variables={"user": self.member.mention}), ephemeral=True)
      return
    try:
      await self.member.ban(reason=self.reason)
      await av.add_violation(self.member.id, interaction.guild.id, 'ban', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await tm.translate_message("moderation.ban_dm_notification", self.language, variables={"reason": self.reason}))
      except Exception:
        pass
      self.embed.add_field(
        name=await tm.translate_message("moderation.verdict", self.language),
        value=f'**{self.member.mention}** ' + await tm.translate_message("moderation.ban_success", self.language, variables={"reason": self.reason})
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await tm.translate_message("moderation.ban_failed", self.language), ephemeral=True)
  
  async def kick_callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    tm = self.bot.get_cog("TranslateMessage")
    av = self.bot.get_cog("AddViolation")
    
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await tm.translate_message("moderation.user_not_found", self.language), ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await tm.translate_message("moderation.guild_only", self.language), ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'kick_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.bot_no_kick_perms", self.language), ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'kick_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.insufficient_perms", self.language, variables={"user": self.member.mention}), ephemeral=True)
      return
    if interaction.user != interaction.guild.owner and interaction.user.guild_permissions.value < self.member.guild_permissions.value:
      await interaction.followup.send(await tm.translate_message("moderation.insufficient_perms", self.language, variables={"user": self.member.mention}), ephemeral=True)
      return
    try:
      await self.member.kick(reason=self.reason)
      await av.add_violation(self.member.id, interaction.guild.id, 'kick', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await tm.translate_message("moderation.kick_dm_notification", self.language, variables={"reason": self.reason}))
      except Exception:
        pass
      self.embed.add_field(
        name=await tm.translate_message("moderation.verdict", self.language),
        value=f'**{self.member.mention}** ' + await tm.translate_message("moderation.kick_success", self.language, variables={"reason": self.reason})
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await tm.translate_message("moderation.kick_failed", self.language), ephemeral=True)
    
    
  
  async def mute_callback(self, interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.send_modal(MuteModal(self.member, self.language, self.reason, self.message, self.embed, self.bot))
    

  async def warn_callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    tm = self.bot.get_cog("TranslateMessage")
    av = self.bot.get_cog("AddViolation")
    
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await tm.translate_message("moderation.user_not_found", self.language), ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await tm.translate_message("moderation.guild_only", self.language), ephemeral=True)
      return
    if interaction.user != interaction.guild.owner and interaction.user.guild_permissions.value < self.member.guild_permissions.value:
      await interaction.followup.send(await tm.translate_message("moderation.insufficient_perms", self.language, variables={"user": self.member.mention}), ephemeral=True)
      return
    try:
      await av.add_violation(self.member.id, interaction.guild.id, 'warn', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await tm.translate_message("moderation.warn_dm_notification", self.language, variables={"reason": self.reason}))
      except Exception:
        pass
      self.embed.add_field(
        name=await tm.translate_message("moderation.verdict", self.language),
        value=f'**{self.member.mention}** ' + await tm.translate_message("moderation.warn_success", self.language, variables={"reason": self.reason})
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await tm.translate_message("moderation.warn_failed", self.language), ephemeral=True)

class MessageReport(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  @message_command(default_member_permissions=8,
  name_localizations=translate_to_all_languages('moderation.report_message_name', 'description'))
  async def message_report(self, interaction: Interaction, message: Message):
    try:
      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")
      se = self.bot.get_cog("SendEmbed")
      lang = _get_locale(interaction.locale)
      user_id = interaction.user.id
      current_time = time()

      if not interaction.guild:
        await interaction.response.send_message(await tm.translate_message("moderation.guild_only", lang), ephemeral=True)
        return
      if user_id in report_cooldown:
        last_command_time = report_cooldown[user_id]['time']
        if current_time - last_command_time < 5*60:
          await interaction.response.send_message(await tm.translate_message("moderation.report_cooldown", lang, variables={"time": f"<t:{round(last_command_time+5*60)}:R>"}), ephemeral=True)
          return
        else:
          report_cooldown[user_id]['time'] = current_time
      else:
        report_cooldown[user_id] = {'time': current_time}
      
      user_settings = await gd.get_data(user_id, ['language','variation'], 'users', 'user_id', interaction.guild)
      language = user_settings['language']
      
      await interaction.response.defer(ephemeral=True)
      
      guild_config = await gd.get_data(interaction.guild.id, ['mod_log_channel'], 'guild_settings', 'guild_id', interaction.guild)
      mod_channel_id = int(guild_config['mod_log_channel'])
      if not mod_channel_id:
        await interaction.followup.send(await tm.translate_message("moderation.no_report_channel", language), ephemeral=True)
        return
      mod_channel = interaction.guild.get_channel(mod_channel_id)
      if not mod_channel:
        await interaction.followup.send(await tm.translate_message("moderation.no_report_channel", language), ephemeral=True)
        return

      view = ReportView(interaction, message, language, mod_channel_id, self.bot)
      await interaction.followup.send(await tm.translate_message("moderation.report_confirm", language, variables={"user": message.author.mention, "message": message.content[:100]}), view=view, ephemeral=True)

    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      
      invite = await gi.invite(interaction.guild) if interaction.guild else "DM"
      fields = [
        {
          'name':'User',
          'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline':True
        },
        {
          'name':'Server',
          'value':f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
          'inline':True
        },
        {
          'name':'Channel',
          'value':f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'DM'}`)",
          'inline':True
        },
        {
          'name':'Error',
          'value':traceback_msg,
          'inline':False
        }
      ]
      await se.send_embed(
        title=f"Error executing /{interaction.application_command.name}",
        description=str(e)[:2048],
        color=Colour.red(),
        fields=fields,
        footer_text='Error in moderation.message_report',
        author_text='ERROR',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      try:
        await interaction.response.send_message(await tm.translate_message("error.logs_saved", lang), ephemeral=True)
      except Exception:
        try:
          await interaction.followup.send(await tm.translate_message("error.logs_saved", lang), ephemeral=True)
        except Exception:
          pass

  setattr(message_report, "extras", {"description": "Report a message to moderators"})

def setup(bot:commands.Bot):
  bot.add_cog(MessageReport(bot))