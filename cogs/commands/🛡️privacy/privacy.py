from datetime import datetime, timezone
from nextcord import Embed, IntegrationType, InteractionContextType, slash_command, Interaction, Color, ButtonStyle
from nextcord.ui import View, Button
from nextcord.ext import commands
import Utils.translate_to_all_languages
from time import time
from Utils.config import slash_command_cooldown
from traceback import format_exception

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _return_emoji(value:bool):
  if value==False:
    return "✅"
  else:
    return "❌"

class конф_меню(View):
  def __init__(self, user_id:int, language:str, update_callback, privacy:dict, bot:commands.Bot, timeout=60*5):
    super().__init__(timeout=timeout)
    self.language = language
    self.user_id = user_id
    self.update_callback = update_callback
    self.privacy = privacy
    self.bot = bot
    self.get_data = self.bot.get_cog("GetData")
    self.update_data = self.bot.get_cog("UpdateData")
    if not (self.get_data and self.update_data):
      raise RuntimeError("Cogs not loaded")
    self.add_privacy()

  def add_privacy(self):
    self.clear_items()
    save_messages = Button(
      style=ButtonStyle.green if not self.privacy['save_messages'] else ButtonStyle.red,
      label=translate_to_all_languages("Сообщения", 'message', self.language),
      row=0,
      emoji=_return_emoji(self.privacy['save_messages'])
    )
    save_messages.callback = lambda i: self.save_flags(i, 'save_messages')
    self.add_item(save_messages)

    save_message_data = Button(
      style=ButtonStyle.green if not self.privacy['save_message_data'] else ButtonStyle.red,
      label=translate_to_all_languages("Контент Сообщений", 'message', self.language),
      row=1,
      emoji=_return_emoji(self.privacy['save_message_data'])
    )
    save_message_data.callback = lambda i: self.save_flags(i, 'save_message_data')
    self.add_item(save_message_data)

    save_voice = Button(
      style=ButtonStyle.green if not self.privacy['save_voice'] else ButtonStyle.red,
      label=translate_to_all_languages("Войс-Активность", 'message', self.language),
      row=0,
      emoji=_return_emoji(self.privacy['save_voice'])
    )
    save_voice.callback = lambda i: self.save_flags(i, 'save_voice')
    self.add_item(save_voice)

    save_activity = Button(
      style=ButtonStyle.green if not self.privacy['save_activity'] else ButtonStyle.red,
      label=translate_to_all_languages("Активность", 'message', self.language),
      row=1,
      emoji=_return_emoji(self.privacy['save_activity'])
    )
    save_activity.callback = lambda i: self.save_flags(i, 'save_activity')
    self.add_item(save_activity)

    save_activity_data = Button(
      style=ButtonStyle.green if not self.privacy['save_activity_data'] else ButtonStyle.red,
      label=translate_to_all_languages("Контент Активности", 'message', self.language),
      row=0,
      emoji=_return_emoji(self.privacy['save_activity_data'])
    )
    save_activity_data.callback = lambda i: self.save_flags(i, 'save_activity_data')
    self.add_item(save_activity_data)

    track_activity = Button(
      style=ButtonStyle.green if not self.privacy['track_activity'] else ButtonStyle.red,
      label=translate_to_all_languages("Слежка", 'message', self.language),
      row=1,
      emoji=_return_emoji(self.privacy['track_activity'])
    )
    track_activity.callback = lambda i: self.save_flags(i, 'track_activity')
    self.add_item(track_activity)
 
  async def save_flags(self, interaction:Interaction, name:str):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    value = self.privacy[name]
    data = {
      name: not value
    }
    await self.update_data.update_data(interaction.user.id, data, 'user_privacy', 'user_id', interaction.guild)
    self.privacy[name] = not value
    self.add_privacy()
    await interaction.edit_original_message(view=self)
    await self.update_callback(self.privacy)

class Privacy(commands.Cog):
  def __init__(self,bot):
    self.bot:commands.Bot = bot
  
  @slash_command(
    description="Управление сбором данных.",
    name_localizations=translate_to_all_languages('конфиденциальность', 'name'),
    description_localizations=translate_to_all_languages('Управление сбором данных.', 'description'),
    force_global=True,
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],)
  async def конфиденциальность(self,interaction: Interaction):
    try:
      user_id = interaction.user.id
      current_time = time()

      translate_message = self.bot.get_cog("TranslateMessage")
      get_data = self.bot.get_cog("GetData")
      get_invite = self.bot.get_cog("GetInvite")
      send_embed = self.bot.get_cog("SendEmbed")
      if not (translate_message and get_data and get_invite and send_embed):
        return

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(await translate_message.translate_message(f"You write commands so fast,",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **<t:{round(last_command_time+10)}:R>** "+await translate_message.translate_message(f"you can write commands.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      user_settings = await get_data.get_data(user_id,['language'],'users','user_id',interaction.guild)
      language = user_settings['language']

      user_privacy = await get_data.get_data(user_id,['save_messages', 'save_message_data', 'save_voice', 'save_activity', 'save_activity_data', 'track_activity'],'user_privacy','user_id',interaction.guild)
      
      await interaction.response.defer(ephemeral=True)

      async def build_desc(data: dict) -> str:
        parts = [
          await translate_message.translate_message("🛡️ **Конфиденциальность и данные**", language), "\n\n",
          await translate_message.translate_message("Я стараюсь быть максимально прозрачным: **что сохраняю** и **зачем**.", language), "\n\n",
          await translate_message.translate_message("По умолчанию я сохраняю только технические данные для стабильной работы:", language), "\n",
          await translate_message.translate_message("• 🧪 ошибки при использовании команд", language), "\n",
          await translate_message.translate_message("• ⚙️ вводимые команды (для поиска багов и улучшения функций)", language), "\n\n",
          await translate_message.translate_message("📦 **Срок хранения:** данные хранятся **без ограничения по времени**, пока вы сами не удалите их.", language), "\n\n",
          await translate_message.translate_message("🔐 **Настройки ниже:**", language), "\n",

          f"{_return_emoji(not data['save_messages'])} " + await translate_message.translate_message("**Сообщения (метаданные)** — `UserId`, `GuildId`, `ChannelId`, ссылка, время отправки. Нужны для графика активности.", language), "\n",
          f"{_return_emoji(not data['save_message_data'])} " + await translate_message.translate_message("**Контент сообщений** — текст сообщений и вложения. Работает только если включены **Сообщения**.", language), "\n",
          f"{_return_emoji(not data['save_voice'])} " + await translate_message.translate_message("**Войс-активность** — вход/выход/переход между войс-каналами (без записи голоса/экрана).", language), "\n",
          f"{_return_emoji(not data['save_activity'])} " + await translate_message.translate_message("**Активность Discord** — игры/стрим/музыка/статус/часть изменений профиля.", language), "\n",
          f"{_return_emoji(not data['save_activity_data'])} " + await translate_message.translate_message("**Контент активности** — расширенные данные активности. Работает только если включена **Активность**.", language), "\n",
          f"{_return_emoji(not data['track_activity'])} " + await translate_message.translate_message("**Диагностика команд** — где и когда использовалась команда (помогает мне находить ошибки и улучшать команды).", language), "\n\n",

          await translate_message.translate_message("🧹 **Управление:** вы всегда можете отключить категории и удалить данные.", language),
        ]
        return "".join(parts)

      privacy_embed = Embed(
        title=await translate_message.translate_message("Конфиденциальность", language),
        description=(await build_desc(user_privacy)),
        color=Color.blurple(),
        timestamp=datetime.now(timezone.utc)
      )
      privacy_embed.set_author(
        name=interaction.user.name,
        icon_url=interaction.user.display_avatar.url
      )
      privacy_embed.set_footer(
        text=await translate_message.translate_message("Конфиденциальность",language)
      )

      async def send_privacy_message(data:dict):
        privacy_embed.description = (await build_desc(data))
        await helper.edit(embed=privacy_embed, view=view)
      
      view = конф_меню(interaction.user.id, language, send_privacy_message, user_privacy, self.bot)
      helper = await interaction.followup.send(embed=privacy_embed,view=view,wait=True, ephemeral=True)
      await send_privacy_message(user_privacy)

    except Exception as e:
      invite = await get_invite.invite(interaction.guild)
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
      await send_embed.send_embed(
        title=f"Произошла ошибка при вводе команды /{interaction.application_command.name}",
        description=str(e)[:2048],
        color=Color.red(),
        fields=fields,
        footer_text=f'Ошибка в cogs.commands.🔧other.help',
        author_text='ЕРРОР',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      await interaction.followup.send(await translate_message.translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)

  setattr(конфиденциальность,"extras",{"description": "Эта команда позволяет вам выбрать, что именно вы разрешаете боту сохранять связанное с вашей активностью в Discord."})

def setup(bot:commands.Bot):
  bot.add_cog(Privacy(bot))