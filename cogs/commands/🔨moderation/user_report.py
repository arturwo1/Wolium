from datetime import timedelta
from traceback import format_exception
from nextcord import Member, Embed, Interaction, user_command, User, TextInputStyle, ButtonStyle, Colour, Message
from nextcord.ext import commands
from nextcord.ui import Modal, View, Button, TextInput
from time import time

from Utils import parse_time
import Utils.translate_to_all_languages
from cogs.utils.add_violation import AddViolation
from cogs.utils.get_data import GetData
from cogs.utils.get_invite import GetInvite
from cogs.utils.send_embed import SendEmbed
from cogs.utils.translate_message import TranslateMessage
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages
report_cooldown = {}

class reportmodal(Modal):
  def __init__(self, interaction:Interaction, user:User, language:str, mod_channel_id: int, bot:commands.Bot,timeout=60*5):
    super().__init__(title=translate_to_all_languages("Жалоба На Пользователя", 'message', language),timeout=timeout)
    self.interaction = interaction
    self.user = user
    self.language = language
    self.mod_channel_id = mod_channel_id
    self.bot = bot

    self.reason = TextInput(
      label=translate_to_all_languages("Причина:", 'message', language),
      style=TextInputStyle.short,
      max_length=28,
      required=True,
      default_value=None,
      placeholder=translate_to_all_languages("Причина Жалобы.", 'message', language)
    )
    self.add_item(self.reason)
      
  async def callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Успешно Пожаловались На Пользователя! Ваша Жалоба Была Отправлена.",self.language),ephemeral=True)
    invite = await (GetInvite(self.bot)).invite(interaction.guild)
    fields = [
      {
        'name':'Сервер',
        'value':f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "ЛС",
        'inline':True
      },
      {
        'name':await (TranslateMessage(self.bot)).translate_message('Канал',self.language),
        'value':f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else f'[<@{interaction.user.id}>({interaction.user.id} | {interaction.user.name}({interaction.user.display_name})]'}`)",
        'inline':True
      },
      {
        'name':await (TranslateMessage(self.bot)).translate_message('Репортящий Пользователь',self.language),
        'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
        'inline':True
      },
      {
        'name':await (TranslateMessage(self.bot)).translate_message('Пользователь Которого Репортят',self.language),
        'value':f"{self.user.id} | {self.user.mention} | {self.user.name}",
        'inline':True
      },
      {
        'name':await (TranslateMessage(self.bot)).translate_message('Причина',self.language),
        'value':f"**`{self.reason.value}`**",
        'inline':True
      }
    ]
    await (SendEmbed(self.bot)).send_embed(
      title="Репорт",
      description=f"### **{interaction.user.mention}** Репортнул По Причине: **`{self.reason.value}`**",
      color=Colour.yellow(),
      fields=fields,
      footer_text='Жалоба На Пользователя',
      author_text=interaction.user.name,
      author_icon=interaction.user.display_avatar.url,
      channel_id=1356660605364469951
    )
    messagemod, modembed = await (SendEmbed(self.bot)).send_embed(
      title=await (TranslateMessage(self.bot)).translate_message("Репорт",self.language),
      description=f"### **{interaction.user.mention}** {await (TranslateMessage(self.bot)).translate_message('Репортнул По Причине:',self.language)} **`{self.reason.value}`**",
      color=Colour.yellow(),
      fields=fields[1:],
      footer_text=await (TranslateMessage(self.bot)).translate_message('Жалоба На Пользователя',self.language),
      author_text=interaction.user.name,
      author_icon=interaction.user.display_avatar.url,
      channel_id=self.mod_channel_id,
      guild_id=interaction.guild.id
    )
    await messagemod.edit(embed=modembed,view=violationsview(self.user,self.language,self.reason.value,self.mod_channel_id,messagemod,modembed,self.bot))

class reportview(View):
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
      label=translate_to_all_languages("Репорт", 'message', self.language)
    )
    report_button.callback = self.report_callback
    self.add_item(report_button)

  async def report_callback(self,interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.send_modal(reportmodal(self.interaction, self.user, self.language, self.mod_channel_id, self.bot))
    self.children[0].disabled = True
    await interaction.edit_original_message(view=self)

class mutemodal(Modal):
  def __init__(self, member:Member, language:str,reason:str, message:Message, embed:Embed, bot:commands.Bot,timeout=60*5):
    super().__init__(title=translate_to_all_languages("Enter The Duration Of The Time-Out", 'message', language),timeout=timeout)
    self.bot = bot
    self.member = member
    self.language = language
    self.reason = reason
    self.message = message
    self.embed = embed
    self.duration = TextInput(
      label=translate_to_all_languages("Длительность:", 'message', language),
      style=TextInputStyle.short,
      max_length=28,
      required=True,
      default_value=None,
      placeholder=translate_to_all_languages("Используйте Формат: 1d 1w 1h 1m 1s. 2 Недели - Макс. Длительность Тайм-Аута.", 'message', language)
    )
    self.add_item(self.duration)
      
  async def callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    duration = parse_time(self.duration.value)
    if duration==None:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Неверный Формат Времени.",self.language),ephemeral=True)
      return
    if duration>60*60*24*7*2:
      await interaction.send(await (TranslateMessage(self.bot)).translate_message("Максимальная Длительность Тайм-Аута 2 Недели.",self.language),ephemeral=True)
      return
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Такого Пользователя Не Существует.",self.language),ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Мы не на сервере.",self.language),ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'moderate_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Меня Недостаточно Прав.",self.language),ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'moderate_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Недостаточно Прав.",self.language),ephemeral=True)
      return
    if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<self.member.guild_permissions.value:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У",self.language)+f" **{self.member.mention}**.",ephemeral=True)
      return
    try:
      await self.member.timeout(timeout=timedelta(seconds=duration if duration else 0),reason=self.reason)
      await (AddViolation(self.bot)).add_violation(self.member.id, interaction.guild.id, 'mute', self.reason, duration, round(time()), interaction.user.id)
      try:
        await self.member.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Тайм-Аутнуты По Причине: `{self.reason}`, на{' '+str(timedelta(seconds=duration)) if duration else 'всегда'}, {interaction.user.mention}-ом", 'en',save=False))
      except Exception:
        pass
      self.embed.add_field(
        name=await (TranslateMessage(self.bot)).translate_message(f"Приговор",self.language),
        value=f'**{self.member.mention}** '+await (TranslateMessage(self.bot)).translate_message("Был Успешно Тайм-Аутнут До",self.language)+f' **<t:{duration}:R>**, '+await (TranslateMessage(self.bot)).translate_message("По Причине",self.language)+f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Не Удалось Тайм-Аутнуть Пользователя.",self.language),ephemeral=True)
    
class violationsview(View):
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
      label=translate_to_all_languages("Ban", 'message', self.language)
    )
    ban_button.callback = self.ban_callback
    self.add_item(ban_button)

    kick_button = Button(
      custom_id="kick",
      style=ButtonStyle.primary,
      emoji='👢',
      label=translate_to_all_languages("Выгнать", 'message', self.language)
    )
    kick_button.callback = self.kick_callback
    self.add_item(kick_button)

    mute_button = Button(
      custom_id="mute",
      style=ButtonStyle.primary,
      emoji='🔇',
      label=translate_to_all_languages("Mute", 'message', self.language)
    )
    mute_button.callback = self.mute_callback
    self.add_item(mute_button)

    warn_button = Button(
      custom_id="warn",
      style=ButtonStyle.primary,
      emoji='⚠️',
      label=translate_to_all_languages("Warn", 'message', self.language)
    )
    warn_button.callback = self.warn_callback
    self.add_item(warn_button)

  async def ban_callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Такого Пользователя Не Существует.",self.language),ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Мы не на сервере.",self.language),ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'ban_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Меня Недостаточно Прав.",self.language),ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'ban_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Недостаточно Прав.",self.language),ephemeral=True)
      return
    if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<self.member.guild_permissions.value:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У",self.language)+f" **{self.member.mention}**.",ephemeral=True)
      return
    try:
      await self.member.ban(reason=self.reason)
      await (AddViolation(self.bot)).add_violation(self.member.id, interaction.guild.id, 'ban', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Забанены По Причине: `{self.reason}`, {interaction.user.mention}-ом", 'en',save=False))
      except Exception:
        pass
      self.embed.add_field(
        name=await (TranslateMessage(self.bot)).translate_message(f"Приговор",self.language),
        value=f'**{self.member.mention}** '+await (TranslateMessage(self.bot)).translate_message("Был Успешно Забанен По Причине",self.language)+f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Не Удалось Забанить Пользователя.",self.language),ephemeral=True)
  
  async def kick_callback(self, interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Такого Пользователя Не Существует.",self.language),ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Мы не на сервере.",self.language),ephemeral=True)
      return
    if getattr(interaction.guild.me.guild_permissions, 'kick_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Меня Недостаточно Прав.",self.language),ephemeral=True)
      return
    if getattr(interaction.user.guild_permissions, 'kick_members', False)==False:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Недостаточно Прав.",self.language),ephemeral=True)
      return
    if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<self.member.guild_permissions.value:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У",self.language)+f" **{self.member.mention}**.",ephemeral=True)
      return
    try:
      await self.member.kick(reason=self.reason)
      await (AddViolation(self.bot)).add_violation(self.member.id, interaction.guild.id, 'kick', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Выгнаны По Причине: `{self.reason}` {interaction.user.mention}-ом", 'en',save=False))
      except Exception:
        pass
      self.embed.add_field(
        name=await (TranslateMessage(self.bot)).translate_message(f"Приговор",self.language),
        value=f'**{self.member.mention}** '+await (TranslateMessage(self.bot)).translate_message("Был Успешно Выгнан По Причине",self.language)+f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Не Удалось Выгнать Пользователя.",self.language),ephemeral=True)
    
    
  
  async def mute_callback(self, interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.send_modal(mutemodal(self.member, self.language, self.reason, self.message, self.embed, self.bot))
    

  async def warn_callback(self,interaction:Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    if not interaction.guild.get_member(self.member.id):
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Такого Пользователя Не Существует.",self.language),ephemeral=True)
      return
    if not interaction.guild:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Мы не на сервере.",self.language),ephemeral=True)
      return
    if interaction.user!=interaction.guild.owner and interaction.user.guild_permissions.value<self.member.guild_permissions.value:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Меньше Прав Чем У",self.language)+f" **{self.member.mention}**.",ephemeral=True)
      return
    try:
      await (AddViolation(self.bot)).add_violation(self.member.id, interaction.guild.id, 'warn', self.reason, None, round(time()), interaction.user.id)
      try:
        await self.member.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Были Предупреждены По Причине: `{self.reason}` {interaction.user.mention}-ом", 'en',save=False))
      except Exception:
        pass
      self.embed.add_field(
        name=await (TranslateMessage(self.bot)).translate_message(f"Приговор",self.language),
        value=f'**{self.member.mention}** '+await (TranslateMessage(self.bot)).translate_message("Был Успешно Предупрежден По Причине",self.language)+f' **`{self.reason}`**.'
      )
      await self.message.edit(embed=self.embed)
    except Exception:
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message("Не Удалось Предупредить Пользователя.",self.language),ephemeral=True)

class UserReport(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  @user_command(default_member_permissions=8,
  name_localizations=translate_to_all_languages('Репорт Пользователя', 'description'))
  async def репорт_пользователя(self,interaction: Interaction, user: User):
    try:
      user_id = interaction.user.id
      current_time = time()

      if not interaction.guild:
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Команда Доступна Только На Серверах.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
        return
      if user_id in report_cooldown:
        last_command_time = report_cooldown[user_id]['time']
        if current_time - last_command_time < 5*60:
          await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"You write commands so fast,",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **<t:{round(last_command_time+5*60)}:R>** "+await (TranslateMessage(self.bot)).translate_message(f"you can report.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
          return
        else:
          report_cooldown[user_id]['time'] = current_time
      else:
        report_cooldown[user_id] = {'time': current_time}
      
      user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']
      
      await interaction.response.defer(ephemeral=True)
      
      invite = await (GetInvite(self.bot)).invite(interaction.guild)
      
      guild_config = await (GetData(self.bot)).get_data(interaction.guild.id,['mod_log_channel'],'guild_settings','guild_id',interaction.guild)
      mod_channel_id = int(guild_config['mod_log_channel'])
      if not mod_channel_id:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"На Сервере Нету Канала Логов.",language), ephemeral=True)
        return
      mod_channel = interaction.guild.get_channel(mod_channel_id)
      if not mod_channel:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"На Сервере Нету Канала Логов.",language), ephemeral=True)
        return

      view=reportview(interaction,user,language,mod_channel_id,self.bot)
      await interaction.followup.send('### '+await (TranslateMessage(self.bot)).translate_message(f"Если Вы Уверены Что Хотите Репортнуть",language)+f' **{user.mention}**, '+await (TranslateMessage(self.bot)).translate_message(f"То Жмите Кнопку Ниже.",language),view=view,ephemeral=True)

    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      fields = [
        {
          'name':'Пользователь',
          'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline':True
        },
        {
          'name':'Сервер',
          'value':f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "ЛС",
          'inline':True
        },
        {
          'name':'Канал',
          'value':f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else f'[<@{interaction.user.id}>({interaction.user.id} | {interaction.user.name}({interaction.user.display_name})]'}`)",
          'inline':True
        },
        {
          'name':'Ошибка',
          'value':traceback_msg,
          'inline':False
        }
      ]
      await (SendEmbed(self.bot)).send_embed(
        title=f"Произошла ошибка при вводе команды /{interaction.application_command.name}",
        description=str(e)[:2048],
        color=Colour.red(),
        fields=fields,
        footer_text=f'Ошибка в cogs.commands.🔨moderation.report',
        author_text='ЕРРОР',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      await interaction.followup.send(await(TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)

  setattr(репорт_пользователя,"extras",{"description": "С Помощью Этой Команды Вы Можете Репортнуть Пользователя(за его аватарку/имя/ник/поведение)!"})


def setup(bot:commands.Bot):
  bot.add_cog(UserReport(bot))