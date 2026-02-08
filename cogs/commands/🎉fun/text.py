import nextcord
from nextcord import SlashOption
from nextcord.ext import commands
from cogs.utils.get_invite import GetInvite
from cogs.utils.translate_message import TranslateMessage
from cogs.utils.get_data import GetData
from cogs.utils.update_data import UpdateData
from Utils.suffics import suffics
from datetime import datetime,timezone
from time import time
import traceback
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class Text(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
  
  @nextcord.slash_command(
    description="Написать Сообщение От Имени Бота. Стоимость €50.",
    name_localizations=translate_to_all_languages('text', 'name'),
    description_localizations=translate_to_all_languages('Write a Message in the Bot\'s Name. Cost €50.', 'description'),
    force_global=True,)
  async def текст(self,
    interaction: nextcord.Interaction,
    текст: str=SlashOption(name="текст", description="Напишите Здесь То Что Отправит Бот.",max_length=2000,required=True, name_localizations=translate_to_all_languages('text', 'name'), description_localizations=translate_to_all_languages('Write Here What Bot Sends.', 'description')),
    канал: nextcord.TextChannel=SlashOption(name="канал", description="Канал В Который Бот Отправит Сообщение.",required=False, name_localizations=translate_to_all_languages('channel', 'name'), description_localizations=translate_to_all_languages('The channel to which the bot will send a message.', 'description')),
    id_сообщения_участника: str=SlashOption(name="идентификатор_сообщения", description="ID Сообщения Участника Сообщения На Которое Бот Должен Ответить.",required=False, name_localizations=translate_to_all_languages('идентификатор_сообщения', 'name'), description_localizations=translate_to_all_languages('Member Message ID of the Message to which the Bot should Reply.', 'description')),
  ):
    try:
      user_id = interaction.user.id
      current_time = time()

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"You write commands so fast,",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **<t:{round(last_command_time+10)}:R>** "+await (TranslateMessage(self.bot)).translate_message(f"you can write commands.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}
      
      user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']
      
      await interaction.response.defer(ephemeral=True)

      user_data = await (GetData(self.bot)).get_data(user_id,['bank_balance','balance'],'user_data','user_id',interaction.guild)
      
      bank_balance = user_data['bank_balance']
      balance = user_data['balance']
      variation = user_settings['variation']

      if bank_balance<50 or balance<50:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Вам Нужно `€50`, Но У Вас Нигде Столько Нет!",language), ephemeral=True)
        return
      for ban_word in {"@here","@everyone"}:
        if ban_word in текст:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"За Попытку Злоупотребления Этой Команды У Вас Штраф В `€250`!\nДаже Если У Вас Нет Таких Денег, Вы В Минусе Будете.",language), ephemeral=True)
          data = {
            'bank_balance': bank_balance-125,
            'balance': balance-125,
          }
          await (UpdateData(self.bot)).update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
          return
      if not interaction.guild:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Эта Команда Доступна Только На Серверах!",language), ephemeral=True)
        return
      if not (канал.permissions_for(interaction.user).send_messages) if канал else False:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Тебя Нет Прав Писать В Этом Канале!",language), ephemeral=True)
        return
      
      invite = await (GetInvite(self.bot)).invite(interaction.guild)

      if канал and id_сообщения_участника:
        try:
          target_message = await канал.fetch_message(id_сообщения_участника)
        except nextcord.NotFound:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Сообщение С ID",language)+f" `{id_сообщения_участника}`, "+await (TranslateMessage(self.bot)).translate_message(f"Не Найдено!",language), ephemeral=True)
          return
        except nextcord.Forbidden:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Меня Нет Прав Отвечать На Это Сообщение!",language), ephemeral=True)
          return
        except nextcord.HTTPException as e:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Неизвестная Ошибка, Отправьте Это Моему [**`Разработчику`**](https://discord.gg/MXupeAApza)!",language)+f"**```py\n{e}```**", ephemeral=True)
          return
        try:
          await target_message.reply(текст)
        except nextcord.InvalidArgument:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Текст Вашего Сообщения Мог Содержать Странные Символы, Ваше Сообщение Не Отправлено. Напишите Его Заново, Но Без Использования Спец. Символов.",language), ephemeral=True)
          return
        except nextcord.Forbidden:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Меня Нет Прав Писать В Этом Канале!",language), ephemeral=True)
          return
        except nextcord.HTTPException as e:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Неизвестная Ошибка, Отправьте Это Моему [**`Разработчику`**](https://discord.gg/MXupeAApza)!",language)+f"```py\n{e}```", ephemeral=True)
          return
        if bank_balance>50:
          sbank_balance = await suffics(number=bank_balance-50, variation=variation)
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"**Сообщение**: \"**`{текст}`**\", **Отправлено В**: **`{канал}`**, Как **Ответ На Сообщение** С **ID**: **`{id_сообщения_участника}`**.\nС Вашего Счета В Банке Снято `€50`. У Вас Осталось: `€{sbank_balance}`",language,save=False), ephemeral=True)
          data = {
            'bank_balance': bank_balance-50
          }
          await (UpdateData(self.bot)).update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
        else:
          sbalance = await suffics(number=balance-50, variation=variation)
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"**Сообщение**: \"**`{текст}`**\", **Отправлено В**: **`{канал}`**, Как **Ответ На Сообщение** С **ID**: **`{id_сообщения_участника}`**.\nС Вас Снято `€50`. У Вас Осталось: `€{sbalance}`",language,save=False), ephemeral=True)
          data = {
            'balance': balance-50
          }
          await (UpdateData(self.bot)).update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
      elif канал and not id_сообщения_участника:
        try:
          await канал.send(текст)
        except nextcord.InvalidArgument:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Текст Вашего Сообщения Мог Содержать Странные Символы, Ваше Сообщение Не Отправлено. Напишите Его Заново, Но Без Использования Спец. Символов.",language), ephemeral=True)
          return
        except nextcord.Forbidden:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Меня Нет Прав Писать В Этом Канале!",language), ephemeral=True)
          return
        except nextcord.HTTPException as e:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Неизвестная Ошибка, Отправьте Это Моему [**`Разработчику`**](https://discord.gg/MXupeAApza)!",language)+f"```py\n{e}```", ephemeral=True)
          return
        if bank_balance>50:
          sbank_balance = await suffics(number=bank_balance-50, variation=variation)
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"**Сообщение**: \"**`{текст}`**\", **Отправлено В**: **`{канал}`**.\nС Вашего Счета В Банке Снято `€50`. У Вас Осталось: `€{sbank_balance}`",language,save=False), ephemeral=True)
          data = {
            'bank_balance': bank_balance-50
          }
          await (UpdateData(self.bot)).update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
        else:
          sbalance = await suffics(number=balance-50, variation=variation)
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"**Сообщение**: \"**`{текст}`**\", **Отправлено В**: **`{канал}`**.\nС Вас Снято `€50`. У Вас Осталось: `€{sbalance}`",language,save=False), ephemeral=True)
          data = {
            'balance': balance-50
          }
          await (UpdateData(self.bot)).update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
      else:
        try:
          await interaction.channel.send(текст)
        except nextcord.InvalidArgument:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Текст Вашего Сообщения Мог Содержать Странные Символы, Ваше Сообщение Не Отправлено. Напишите Его Заново, Но Без Использования Спец. Символов.",language), ephemeral=True)
          return
        except nextcord.Forbidden:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У Меня Нет Прав Писать В Этом Канале!",language), ephemeral=True)
          return
        except nextcord.HTTPException as e:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Неизвестная Ошибка, Отправьте Это Моему [**`Разработчику`**](https://discord.gg/MXupeAApza)!",language)+f"```py\n{e}```", ephemeral=True)
          return
        if bank_balance>50:
          sbank_balance = await suffics(number=bank_balance-50, variation=variation)
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"**Сообщение**: \"**`{текст}`**\", **Отправлено В**: **`{interaction.channel.name}`**.\nС Вашего Счета В Банке Снято `€50`. У Вас Осталось: `€{sbank_balance}`",language,save=False), ephemeral=True)
          data = {
            'bank_balance': bank_balance-50
          }
          await (UpdateData(self.bot)).update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
        else:
          sbalance = await suffics(number=balance-50, variation=variation)
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"**Сообщение**: \"**`{текст}`**\", **Отправлено В**: **`{interaction.channel.name}`**.\nС Вас Снято `€50`. У Вас Осталось: `€{sbalance}`",language,save=False), ephemeral=True)
          data = {
            'balance': balance-50
          }
          await (UpdateData(self.bot)).update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
    except Exception as e:
      if "AutoMod" in str(e):
        try:
          await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"AutoMod На Этом Сервере Заблокировал Моё Сообщение.",language), ephemeral=True)
        except Exception:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"AutoMod На Этом Сервере Заблокировал Моё Сообщение.",language), ephemeral=True)
        return
      traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/текст** `текст`  **{текст}** `канал`  **{канал}** `id_сообщения_участника`  **{id_сообщения_участника}**||",
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )

      log.set_author(
        name=f"Сервер ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=f"{interaction.user.display_avatar.url}"
      )
      if interaction.guild:
        log.add_field(
          name="Сервер",
          value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "ЛС" if interaction.guild else "ЛС",
          inline=False
        )
      log.add_field(
        name="Канал",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
        inline=False
      )
      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
          name="Ошибка",
          value=f"```py\n{traceback_msg[i:i+1000]}```",
          inline=False
        )
      log.set_footer(
        text=f"{str(datetime.now())}",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      try:
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
      except Exception:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
    
  setattr(текст,"extras",{"description": "С помощью этой команды можно писать куда-угодно от моего имени!"},)

def setup(bot: commands.Bot):
  bot.add_cog(Text(bot))