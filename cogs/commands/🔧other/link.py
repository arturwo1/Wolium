from nextcord import slash_command, InteractionContextType, IntegrationType, Interaction, Embed, Colour
from nextcord import SlashOption, IntegrationType, InteractionContextType
from nextcord.ext import commands
from cogs.utils.get_invite import GetInvite
from cogs.utils.translate_message import TranslateMessage
from cogs.utils.get_data import GetData
from datetime import datetime,timezone
from time import time
from traceback import format_exception
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from aiohttp import ClientSession
from aiohttp.client_exceptions import (InvalidURL,TooManyRedirects,ClientConnectionError, InvalidUrlClientError, ClientPayloadError, ServerTimeoutError, ClientResponseError, ClientOSError)

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

headers = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
  "Accept-Language": "en;q=0.5,ru;q=0.5"
}
cookies = {
  "CONSENT": "YES+1"
}

def statuses(status: int):
  if status == 200:
    return "OK"
  elif status == 404:
    return "Not Found"
  elif status == 403:
    return "Forbidden"
  elif status == 500:
    return "Internal Server Error"
  elif status == 503:
    return "Service Unavailable"
  elif status == 301:
    return "Moved Permanently"
  elif status == 302:
    return "Moved Temporarily"
  else:
    return status

class Link(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
  
  @slash_command(description="Параметры Ссылки.",
    name_localizations=translate_to_all_languages('ссылка', 'name'),
    description_localizations=translate_to_all_languages('Параметры Ссылки.', 'description'),
    force_global=True,
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ])
  async def ссылка(self,
    interaction: Interaction,
    ссылка: str=SlashOption(name="ссылка", description="Выбери Ссылку.",required=True, name_localizations=translate_to_all_languages('ссылка', 'name'), description_localizations=translate_to_all_languages('Выбери Ссылку.', 'description')),
    лично: bool=SlashOption(name="лично", description="Только Ты Увидешь Сообщение, Или Все.",required=False,default=False, name_localizations=translate_to_all_languages('лично', 'name'), description_localizations=translate_to_all_languages('Только Ты Увидешь Сообщение, Или Все.', 'description')),
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
      
      user_settings = await (GetData(self.bot)).get_data(user_id,['language'],'users','user_id',interaction.guild)
      language = user_settings['language']

      if interaction.guild and interaction.permissions and interaction.permissions.send_messages:
        await interaction.response.defer(ephemeral=лично)
      else:
        лично=True
        await interaction.response.defer(ephemeral=лично)

      invite = await (GetInvite(self.bot)).invite(interaction.guild)

      text = None
      try:
        async with ClientSession(cookies=cookies) as session:
          async with session.get(ссылка, headers=headers, allow_redirects=True, max_redirects=5) as response:
            history = response.history
            final_url = str(response.url)
            urls = ""
            for url in history:
              urls += f"**{statuses(url.status)}** | **`{url.url}`**\n"
            text = f"""
**Got**: **`{ссылка}`**
**Final**: **`{final_url}`**
**Redirects**: {urls}
            """

            link_embed = Embed(
              title=await (TranslateMessage(self.bot)).translate_message("Перенаправления Этой Ссылки",language),
              description=text,
              color=Colour.og_blurple(),
              timestamp=datetime.now(timezone.utc)
            )
            link_embed.set_author(
              name=interaction.user.name,
              icon_url=interaction.user.display_avatar.url
            )
            link_embed.set_footer(
              text=await (TranslateMessage(self.bot)).translate_message("Ссылка",language),
              icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
            )

            await interaction.followup.send(embed=link_embed, ephemeral=лично)
      except (InvalidURL, InvalidUrlClientError):
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"### Неверная Ссылка:\n`{ссылка}`.",language), ephemeral=лично)
        return
      except ClientConnectionError:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"### Ошибка Подключения\nВозможно сайта не существует.",language), ephemeral=лично)
        return
      except ClientPayloadError:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"### Ошибка Пакета\nСервер передал поврежденные данные.",language), ephemeral=лично)
        return
      except ServerTimeoutError:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"### Ошибка Времени Ожидания\nСервер не ответил вовремя.",language), ephemeral=лично)
        return
      except ClientResponseError:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"### Ошибка Ответа\nСервер дал неожиданный ответ, возможно ошибку.",language), ephemeral=лично)
        return
      except ClientOSError:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"### Ошибка Клиента\nВозможно у моего хоста проблемы с интернетом.",language), ephemeral=лично)
        return
      except TooManyRedirects:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"### Слишком Много Перенаправлений, лимит `5`!\nСкорее всего это опасная ссылка!",language), ephemeral=лично)
        return
      
    except Exception as e:
      if "AutoMod" in str(e):
        try:
          await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"AutoMod На Этом Сервере Заблокировал Моё Сообщение.",language), ephemeral=True)
        except Exception:
          await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"AutoMod На Этом Сервере Заблокировал Моё Сообщение.",language), ephemeral=True)
        return
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/ссылка** `ссылка`  **{ссылка}**||",
        color=Colour.red(),
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
        text=f"cogs.commands.🔧other.link",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
      )
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
      try:
        await interaction.response.send_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      except Exception:
        await interaction.followup.send(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)

  setattr(ссылка, "extras",{"description": "Вы можете вставить сюда любую ссылку, а я вам покажу некоторые ее параметры!"})

def setup(bot: commands.Bot):
  bot.add_cog(Link(bot))