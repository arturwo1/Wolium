from nextcord import slash_command, InteractionContextType, IntegrationType, Interaction, Embed, Colour
from nextcord import SlashOption, IntegrationType, InteractionContextType
from nextcord.ext import commands
from datetime import datetime, timezone
from time import time
from traceback import format_exception
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from aiohttp import ClientSession
from aiohttp.client_exceptions import (InvalidURL, TooManyRedirects, ClientConnectionError, InvalidUrlClientError, ClientPayloadError, ServerTimeoutError, ClientResponseError, ClientOSError)

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

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
  
  @slash_command(description="Link parameters.",
    name_localizations=translate_to_all_languages('general.link_lower', 'name'),
    description_localizations=translate_to_all_languages('general.link_parameters', 'description'),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ])
  async def link(self,
    interaction: Interaction,
    url: str=SlashOption(name="url", description="Choose a link.",required=True, name_localizations=translate_to_all_languages('general.link_lower', 'name'), description_localizations=translate_to_all_languages('general.choose_link', 'description')),
    ephemeral: bool=SlashOption(name="ephemeral", description="Only you see the message or everyone.",required=False,default=False, name_localizations=translate_to_all_languages('general.personally', 'name'), description_localizations=translate_to_all_languages('general.ephemeral_desc', 'description')),
  ):
    try:
      user_id = interaction.user.id
      current_time = time()
      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")
      lang = _get_locale(interaction.locale)

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(await tm.translate_message("error.rate_limit", lang, variables={"time": f"<t:{round(last_command_time+10)}:R>"}), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}
      
      user_settings = await gd.get_data(user_id,['language'],'users','user_id',interaction.guild)
      language = user_settings['language']

      if interaction.guild and interaction.permissions and interaction.permissions.send_messages:
        await interaction.response.defer(ephemeral=ephemeral)
      else:
        ephemeral=True
        await interaction.response.defer(ephemeral=ephemeral)

      invite = await gi.invite(interaction.guild)

      text = None
      try:
        async with ClientSession(cookies=cookies) as session:
          async with session.get(url, headers=headers, allow_redirects=True, max_redirects=5) as response:
            history = response.history
            final_url = str(response.url)
            urls = ""
            for url in history:
              urls += f"**{statuses(url.status)}** | **`{url.url}`**\n"
            text = f"""
**Got**: **`{url}`**
**Final**: **`{final_url}`**
**Redirects**: {urls}
            """

            link_embed = Embed(
              title=await tm.translate_message("general.link_redirects",language),
              description=text,
              color=Colour.og_blurple(),
              timestamp=datetime.now(timezone.utc)
            )
            link_embed.set_author(
              name=interaction.user.name,
              icon_url=interaction.user.display_avatar.url
            )
            link_embed.set_footer(
              text=await tm.translate_message("general.link",language),
              icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
            )

            await interaction.followup.send(embed=link_embed, ephemeral=ephemeral)
      except (InvalidURL, InvalidUrlClientError):
        await interaction.followup.send(await tm.translate_message(f"### Неверная url:\n`{url}`.",language), ephemeral=ephemeral)
        return
      except ClientConnectionError:
        await interaction.followup.send(await tm.translate_message(f"### Ошибка Подключения\nВозможно сайта не существует.",language), ephemeral=ephemeral)
        return
      except ClientPayloadError:
        await interaction.followup.send(await tm.translate_message(f"### Ошибка Пакета\nСервер передал поврежденные данные.",language), ephemeral=ephemeral)
        return
      except ServerTimeoutError:
        await interaction.followup.send(await tm.translate_message(f"### Ошибка Времени Ожидания\nСервер не ответил вовремя.",language), ephemeral=ephemeral)
        return
      except ClientResponseError:
        await interaction.followup.send(await tm.translate_message(f"### Ошибка Ответа\nСервер дал неожиданный ответ, возможно ошибку.",language), ephemeral=ephemeral)
        return
      except ClientOSError:
        await interaction.followup.send(await tm.translate_message(f"### Ошибка Клиента\nВозможно у моего хоста проблемы с интернетом.",language), ephemeral=ephemeral)
        return
      except TooManyRedirects:
        await interaction.followup.send(await tm.translate_message(f"### Слишком Много Перенаправлений, лимит `5`!\nСкорее всего это опасная url!",language), ephemeral=ephemeral)
        return
      
    except Exception as e:
      if "AutoMod" in str(e):
        try:
          await interaction.response.send_message(await tm.translate_message(f"AutoMod На Этом Сервере Заблокировал Моё Сообщение.",language), ephemeral=True)
        except Exception:
          await interaction.followup.send(await tm.translate_message(f"AutoMod На Этом Сервере Заблокировал Моё Сообщение.",language), ephemeral=True)
        return
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/url** `url`  **{url}**||",
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

  setattr(link, "extras",{"description": "You can paste any link here and I will show you some of its parameters!"})

def setup(bot: commands.Bot):
  bot.add_cog(Link(bot))