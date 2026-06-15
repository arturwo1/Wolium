from nextcord import slash_command, InteractionContextType, IntegrationType, Interaction, Embed, Colour, SlashOption
from nextcord.ext import commands
from datetime import datetime, timezone
from time import time
from traceback import format_exception
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from aiohttp import ClientSession, ClientTimeout
from aiohttp.client_exceptions import InvalidURL, TooManyRedirects, ClientConnectionError, InvalidUrlClientError, ClientPayloadError, ServerTimeoutError, ClientResponseError, ClientOSError

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

HEADERS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
  "Accept-Language": "en;q=0.5,ru;q=0.5",
}
COOKIES = {"CONSENT": "YES+1"}

REQUEST_TIMEOUT = ClientTimeout(total=15)
MAX_REDIRECTS = 5
COMMAND_COOLDOWN = 10

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

def statuses(status: int) -> str:
  statuses_map = {
    200: "OK",
    301: "Moved Permanently",
    302: "Moved Temporarily",
    303: "See Other",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    408: "Request Timeout",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
  }
  return statuses_map.get(status, str(status))

async def _safe_error_reply(interaction: Interaction, message: str, ephemeral: bool = True):
  try:
    if interaction.response.is_done():
      await interaction.followup.send(message, ephemeral=ephemeral)
    else:
      await interaction.response.send_message(message, ephemeral=ephemeral)
  except Exception:
    pass

class Link(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot

  @slash_command(
    description="Link parameters.",
    name_localizations=translate_to_all_languages("commands.link.name", "name"),
    description_localizations=translate_to_all_languages("commands.link.description", "description"),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],
  )
  async def link(
    self,
    interaction: Interaction,
    url: str = SlashOption(
      name="url",
      description="Choose a link.",
      required=True,
      name_localizations=translate_to_all_languages("commands.link.options.url.name", "name"),
      description_localizations=translate_to_all_languages("commands.link.options.url.description", "description"),
    ),
    ephemeral: bool = SlashOption(
      name="ephemeral",
      description="Only you see the message or everyone.",
      required=False,
      default=False,
      name_localizations=translate_to_all_languages("commands.link.options.ephemeral.name", "name"),
      description_localizations=translate_to_all_languages("commands.link.options.ephemeral.description", "description"),
    ),
  ):
    tm = self.bot.get_cog("TranslateMessage")
    gd = self.bot.get_cog("GetData")
    gi = self.bot.get_cog("GetInvite")

    language = _get_locale(interaction.locale)
    invite = None

    try:
      user_id = interaction.user.id
      current_time = time()

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]["time"]

        if current_time - last_command_time < COMMAND_COOLDOWN:
          await interaction.response.send_message(await tm.translate_message("errors.rate_limit", language, variables={"time": f"<t:{round(last_command_time + COMMAND_COOLDOWN)}:R>"}), ephemeral=True)
          return

        slash_command_cooldown[user_id]["time"] = current_time
      else:
        slash_command_cooldown[user_id] = {"time": current_time}

      user_settings = await gd.get_data(user_id, ["language"], "users", "user_id", interaction.guild)
      language = user_settings.get("language") or language

      if not (interaction.guild and interaction.permissions and interaction.permissions.send_messages):
        ephemeral = True

      await interaction.response.defer(ephemeral=ephemeral)

      if interaction.guild:
        invite = await gi.invite(interaction.guild)

      try:
        async with ClientSession(cookies=COOKIES, timeout=REQUEST_TIMEOUT) as session:
          async with session.get(url, headers=HEADERS, allow_redirects=True, max_redirects=MAX_REDIRECTS) as response:
            redirect_lines = []

            for redirect_response in response.history:
              redirect_lines.append(f"**{statuses(redirect_response.status)}** | **`{redirect_response.url}`**")

            redirects = "\n".join(redirect_lines)

            if not redirects:
              redirects = await tm.translate_message("commands.link.no_redirects", language)

            description = await tm.translate_message("commands.link.result", language, variables={"got_url": url, "final_url": str(response.url), "redirects": redirects})

            link_embed = Embed(
              title=await tm.translate_message("commands.link.embed.title", language),
              description=description,
              color=Colour.og_blurple(),
              timestamp=datetime.now(timezone.utc),
            )
            link_embed.set_author(
              name=interaction.user.name,
              icon_url=interaction.user.display_avatar.url,
            )
            link_embed.set_footer(
              text=await tm.translate_message("commands.link.embed.footer", language),
              icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png",
            )

            await interaction.followup.send(embed=link_embed, ephemeral=ephemeral)

      except (InvalidURL, InvalidUrlClientError):
        await interaction.followup.send(await tm.translate_message("commands.link.errors.invalid_url", language, variables={"url": url}), ephemeral=ephemeral)
        return

      except ClientConnectionError:
        await interaction.followup.send(await tm.translate_message("commands.link.errors.connection", language), ephemeral=ephemeral)
        return

      except ClientPayloadError:
        await interaction.followup.send(await tm.translate_message("commands.link.errors.payload", language), ephemeral=ephemeral)
        return

      except ServerTimeoutError:
        await interaction.followup.send(await tm.translate_message("commands.link.errors.timeout", language), ephemeral=ephemeral)
        return

      except ClientResponseError:
        await interaction.followup.send(await tm.translate_message("commands.link.errors.response", language), ephemeral=ephemeral)
        return

      except ClientOSError:
        await interaction.followup.send(await tm.translate_message("commands.link.errors.client", language), ephemeral=ephemeral)
        return

      except TooManyRedirects:
        await interaction.followup.send(await tm.translate_message("commands.link.errors.too_many_redirects", language, variables={"limit": str(MAX_REDIRECTS)}), ephemeral=ephemeral)
        return

    except Exception as e:
      if "AutoMod" in str(e):
        await _safe_error_reply(interaction, await tm.translate_message("commands.link.errors.automod_blocked", language), ephemeral=True)
        return

      traceback_msg = ("".join(format_exception(type(e), e, e.__traceback__)))[:5000]

      log = Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/link** `url`  **{url}**||",
        color=Colour.red(),
        timestamp=datetime.now(timezone.utc),
      )

      log.set_author(
        name=f"Сервер ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=f"{interaction.user.display_avatar.url}",
      )

      if interaction.guild:
        log.add_field(
          name="Сервер",
          value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}",
          inline=False,
        )

      log.add_field(
        name="Канал",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
        inline=False,
      )

      for i in range(0, len(traceback_msg), 1000):
        log.add_field(
          name="Ошибка",
          value=f"```py\n{traceback_msg[i:i + 1000]}```",
          inline=False,
        )

      log.set_footer(
        text="cogs.commands.🔧other.link",
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png",
      )

      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
      await _safe_error_reply(interaction, await tm.translate_message("errors.unknown", language), ephemeral=True)

  setattr(link, "extras", {"description": "commands.link.description"})

def setup(bot: commands.Bot):
  bot.add_cog(Link(bot))