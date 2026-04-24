from datetime import timedelta
from traceback import format_exception
from nextcord import Member, Embed, Interaction, user_command, User, TextInputStyle, ButtonStyle, Colour, Message
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
  elif locale == 'es-ES':
    return 'es'
  elif locale == 'sv-SE':
    return 'sv'
  return 'en'

class ReportModal(Modal):
  def __init__(self, interaction:Interaction, user:User, language:str, mod_channel_id: int, bot:commands.Bot,timeout=60*5):
    super().__init__(title=translate_to_all_languages("report.user", 'message', language),timeout=timeout)
    self.interaction = interaction
    self.user = user
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
        'name': 'Server',
        'value': f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
        'inline': True
      },
      {
        'name': await tm.translate_message('general.channel', self.language),
        'value': f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else f'[<@{interaction.user.id}>({interaction.user.id} | {interaction.user.name}({interaction.user.display_name})]'}`)",
        'inline': True
      },
      {
        'name': await tm.translate_message('report.reporting_user', self.language),
        'value': f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
        'inline': True
      },
      {
        'name': await tm.translate_message('report.reported_user', self.language),
        'value': f"{self.user.id} | {self.user.mention} | {self.user.name}",
        'inline': True
      },
      {
        'name': await tm.translate_message('general.reason', self.language),
        'value': f"**`{self.reason.value}`**",
        'inline': True
      }
    ]
    await se.send_embed(
      title="Report",
      description=f"### **{interaction.user.mention}** reported for: **`{self.reason.value}`**",
      color=Colour.yellow(),
      fields=fields,
      footer_text='User Report',
      author_text=interaction.user.name,
      author_icon=interaction.user.display_avatar.url,
      channel_id=1356660605364469951
    )
    messagemod, modembed = await se.send_embed(
      title=await tm.translate_message("moderation.report_title", self.language),
      description=f"### **{interaction.user.mention}** {await tm.translate_message('report.reported_for_reason', self.language)} **`{self.reason.value}`**",
      color=Colour.yellow(),
      fields=fields[1:],
      footer_text=await tm.translate_message('report.user_title', self.language),
      author_text=interaction.user.name,
      author_icon=interaction.user.display_avatar.url,
      channel_id=self.mod_channel_id,
      guild_id=interaction.guild.id
    )
    await messagemod.edit(embed=modembed, view=ViolationsView(self.user, self.language, self.reason.value, self.mod_channel_id, messagemod, modembed, self.bot))

class ReportView(View):
  def __init__(self, interaction:Interaction, user:User, language:str, mod_channel_id:int, bot:commands.Bot,timeout=60*5):
    super().__init__(timeout=timeout)
    self.interaction = interaction
    self.user = user
    self.language = language
    self.mod_channel_id = mod_channel_id
    self.bot = bot

    report_button = Button(
      style=ButtonStyle.red,
      emoji='❌',
      label='Report'
    )
    report_button.callback = self.report_callback
    self.add_item(report_button)

  async def report_callback(self,interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.send_modal(ReportModal(self.interaction, self.user, self.language, self.mod_channel_id, self.bot))
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
      await interaction.followup.send(await tm.translate_message("error.invalid_time_format", self.language), ephemeral=True)
      return
    if duration > 60*60*24*7*2:
      await interaction.followup.send(await tm.translate_message("error.timeout_max_duration", self.language), ephemeral=True)
      return
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await tm.translate_message("error.user_does_not_exist", self.language), ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await tm.translate_message("error.not_on_server", self.language), ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'moderate_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.bot_no_mute_perms", self.language), ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'moderate_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.no_mute_perms", self.language), ephemeral=True)
      return
    if interaction.user != interaction.guild.owner and interaction.user.guild_permissions.value < self.member.guild_permissions.value:
      await interaction.followup.send(await tm.translate_message("moderation.lower_perms", self.language) + f" **{self.member.mention}**.", ephemeral=True)
      return
    try:
      await self.member.timeout(timeout=timedelta(seconds=duration if duration else 0), reason=self.reason)
      await av.add_violation(self.member.id, interaction.guild.id, 'mute', self.reason, duration, round(time()), interaction.user.id)
      try:
        await self.member.send(await tm.translate_message("moderation.user_muted_dm", self.language, variables={'user': interaction.user.mention, 'reason': self.reason, 'duration': str(timedelta(seconds=duration)) if duration else 'permanent'}))
      except Exception:
        pass
      self.embed.add_field(
        name=await tm.translate_message("moderation.verdict", self.language),
        value=f'**{self.member.mention}** ' + await tm.translate_message("punishment.timeout_success_until", self.language) + f' **<t:{duration}:R>**, ' + await tm.translate_message("punishment.by_reason", self.language) + f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await tm.translate_message("error.timeout_failed", self.language), ephemeral=True)
    
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
      await interaction.followup.send(await tm.translate_message("error.user_does_not_exist", self.language), ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await tm.translate_message("error.not_on_server", self.language), ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'ban_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.bot_no_ban_perms", self.language), ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'ban_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.no_ban_perms", self.language), ephemeral=True)
      return
    if interaction.user != interaction.guild.owner and interaction.user.guild_permissions.value < self.member.guild_permissions.value:
      await interaction.followup.send(await tm.translate_message("moderation.lower_perms", self.language) + f" **{self.member.mention}**.", ephemeral=True)
      return
    try:
      await self.member.ban(reason=self.reason)
      await av.add_violation(self.member.id, interaction.guild.id, 'ban', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await tm.translate_message("moderation.user_banned_dm", self.language, variables={'user': interaction.user.mention, 'reason': self.reason}))
      except Exception:
        pass
      self.embed.add_field(
        name=await tm.translate_message("moderation.verdict", self.language),
        value=f'**{self.member.mention}** ' + await tm.translate_message("punishment.ban_success_reason", self.language) + f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await tm.translate_message("error.ban_failed", self.language), ephemeral=True)
  
  async def kick_callback(self, interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    tm = self.bot.get_cog("TranslateMessage")
    av = self.bot.get_cog("AddViolation")
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await tm.translate_message("error.user_does_not_exist", self.language), ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await tm.translate_message("error.not_on_server", self.language), ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'kick_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.bot_no_kick_perms", self.language), ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'kick_members', False) == False:
      await interaction.followup.send(await tm.translate_message("moderation.no_kick_perms", self.language), ephemeral=True)
      return
    if interaction.user != interaction.guild.owner and interaction.user.guild_permissions.value < self.member.guild_permissions.value:
      await interaction.followup.send(await tm.translate_message("moderation.lower_perms", self.language) + f" **{self.member.mention}**.", ephemeral=True)
      return
    try:
      await self.member.kick(reason=self.reason)
      await av.add_violation(self.member.id, interaction.guild.id, 'kick', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await tm.translate_message("moderation.user_kicked_dm", self.language, variables={'user': interaction.user.mention, 'reason': self.reason}))
      except Exception:
        pass
      self.embed.add_field(
        name=await tm.translate_message("moderation.verdict", self.language),
        value=f'**{self.member.mention}** ' + await tm.translate_message("punishment.kick_success_reason", self.language) + f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await tm.translate_message("error.kick_failed", self.language), ephemeral=True)
    
    
  
  async def mute_callback(self, interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.send_modal(MuteModal(self.member, self.language, self.reason, self.message, self.embed, self.bot))
    

  async def warn_callback(self, interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    tm = self.bot.get_cog("TranslateMessage")
    av = self.bot.get_cog("AddViolation")
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await tm.translate_message("error.user_does_not_exist", self.language), ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await tm.translate_message("error.not_on_server", self.language), ephemeral=True)
      return
    if interaction.user != interaction.guild.owner and interaction.user.guild_permissions.value < self.member.guild_permissions.value:
      await interaction.followup.send(await tm.translate_message("moderation.lower_perms", self.language) + f" **{self.member.mention}**.", ephemeral=True)
      return
    try:
      await av.add_violation(self.member.id, interaction.guild.id, 'warn', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await tm.translate_message("moderation.user_warned_dm", self.language, variables={'user': interaction.user.mention, 'reason': self.reason}))
      except Exception:
        pass
      self.embed.add_field(
        name=await tm.translate_message("moderation.verdict", self.language),
        value=f'**{self.member.mention}** ' + await tm.translate_message("punishment.warn_success_reason", self.language) + f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await tm.translate_message("error.warn_failed", self.language), ephemeral=True)

class UserReport(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  @user_command(default_member_permissions=8,
  name_localizations=translate_to_all_languages('report.user_title', 'description'))
  async def user_report(self, interaction: Interaction, user: User):
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
          await interaction.response.send_message(await tm.translate_message("moderation.report_cooldown", lang) + f" **<t:{round(last_command_time+5*60)}:R>**", ephemeral=True)
          return
        else:
          report_cooldown[user_id]['time'] = current_time
      else:
        report_cooldown[user_id] = {'time': current_time}
      
      user_settings = await gd.get_data(user_id, ['language', 'variation'], 'users', 'user_id', interaction.guild)
      language = user_settings['language']
      
      await interaction.response.defer(ephemeral=True)
      
      invite = await gi.invite(interaction.guild)
      
      guild_config = await gd.get_data(interaction.guild.id, ['mod_log_channel'], 'guild_settings', 'guild_id', interaction.guild)
      mod_channel_id = int(guild_config['mod_log_channel'])
      if not mod_channel_id:
        await interaction.followup.send(await tm.translate_message("moderation.no_report_channel", language), ephemeral=True)
        return
      mod_channel = interaction.guild.get_channel(mod_channel_id)
      if not mod_channel:
        await interaction.followup.send(await tm.translate_message("moderation.no_report_channel", language), ephemeral=True)
        return

      view = ReportView(interaction, user, language, mod_channel_id, self.bot)
      await interaction.followup.send('### ' + await tm.translate_message("moderation.report_confirm", language) + f' **{user.mention}**, ' + await tm.translate_message("moderation.report_button", language), view=view, ephemeral=True)

    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      fields = [
        {
          'name': 'User',
          'value': f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline': True
        },
        {
          'name': 'Server',
          'value': f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
          'inline': True
        },
        {
          'name': 'Channel',
          'value': f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else f'[<@{interaction.user.id}>({interaction.user.id} | {interaction.user.name}({interaction.user.display_name})]'}`)",
          'inline': True
        },
        {
          'name': 'Error',
          'value': traceback_msg,
          'inline': False
        }
      ]
      await se.send_embed(
        title=f"Error in command /{interaction.application_command.name}",
        description=str(e)[:2048],
        color=Colour.red(),
        fields=fields,
        footer_text='Error in cogs.commands.🔨moderation.user_report',
        author_text='ERROR',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      await interaction.followup.send(await tm.translate_message("moderation.error_message", lang), ephemeral=True)

  setattr(user_report,"extras",{"description": "С Помощью Этой Команды Вы Можете Репортнуть Пользователя(за его аватарку/имя/ник/поведение)!"})


def setup(bot:commands.Bot):
  bot.add_cog(UserReport(bot))