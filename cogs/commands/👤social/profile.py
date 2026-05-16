import asyncio
from functools import partial
from string import ascii_letters, digits
from time import time
from datetime import datetime, timedelta, timezone
from traceback import format_exception
from random import choices
from os import getenv, path, listdir
from io import BytesIO
from copy import deepcopy
from nextcord.ext import commands
from nextcord import File, IntegrationType, InteractionContextType, SlashOption, ButtonStyle, SelectOption, Interaction, slash_command, User, Embed, Color
from nextcord.ui import View, Button, Select, Modal, TextInput
from nextcord.errors import InteractionResponded
from nextcord.utils import find
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops
from aiohttp import ClientSession
from babel.dates import format_datetime
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from Utils.suffics import suffics
from Utils.calculate_LvL import calculate_LvL

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class CreateDateModal(Modal):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    super().__init__(
      title=translate_to_all_languages("profile.telegram_modal_title", 'message', 'en')
    )
    self.user_telegram_id = TextInput(
      label=translate_to_all_languages("profile.telegram_id_label", 'message', 'en'),
      min_length=2,
      max_length=int(str(datetime.now().year)[2:]),
      required=True,
      placeholder=translate_to_all_languages("profile.enter_telegram_id", 'message', 'en'),
    )
    self.add_item(self.user_telegram_id)

  async def callback(self, interaction: Interaction):
    tm = self.bot.get_cog("TranslateMessage")
    gd = self.bot.get_cog("GetData")
    lang = _get_locale(interaction.locale)

    tid = self.user_telegram_id.value
    if tid == 0:
      return await interaction.send(
        await tm.translate_message("profile.invalid_telegram_id", lang, variables={"id": tid}),ephemeral=True)

    user_settings = await gd.get_data(tid, ['language'], 'users', 'user_id', interaction.guild)
    language = user_settings['language']

    if not (hasattr(self.bot, 'db_pool') and self.bot.db_pool):
      return await interaction.send('PostgreSQL not loaded in profile', ephemeral=True)

    async with self.bot.db_pool.acquire() as conn:
      try:
        await conn.execute("UPDATE users SET discord_id = $1 WHERE telegram_id = $2",interaction.user.id, tid)
      except Exception:
        return await interaction.send(
          await tm.translate_message("profile.invalid_telegram_id", lang, variables={"id": tid}), ephemeral=True)

    return await interaction.send(await tm.translate_message("profile.telegram_linked_success", language), ephemeral=True)

class ProfileView(View):
  def __init__(
    self,
    user_id: int,
    language: str,
    update_callback,
    voted: bool,
    bot: commands.Bot,
    timeout: int = 60 * 5,
  ):
    super().__init__(timeout=timeout)
    self.language = language
    self.user_id = user_id
    self.update_callback = update_callback
    self.bot = bot
    self.voted = voted

    options = [
      SelectOption(
        label='🔵 ' + translate_to_all_languages("profile.section_discord", 'message', language),
        description=translate_to_all_languages("profile.section_discord_desc", 'message', language),
        value="discord",
      ),
      SelectOption(
        label='📘 ' + translate_to_all_languages("profile.section_server", 'message', language),
        description=translate_to_all_languages("profile.section_server_desc", 'message', language),
        value="server",
      ),
      SelectOption(
        label='💹 ' + translate_to_all_languages("profile.section_economy", 'message', language),
        description=translate_to_all_languages("profile.section_economy_desc", 'message', language),
        value="economy",
      ),
      SelectOption(
        label='🚨 ' + translate_to_all_languages("profile.section_moderation", 'message', language),
        description=translate_to_all_languages("profile.section_moderation_desc", 'message', language),
        value="moderation",
      ),
      SelectOption(
        label='🔄 ' + translate_to_all_languages("profile.section_cooldowns", 'message', language),
        description=str(translate_to_all_languages("profile.section_cooldowns_desc", 'message', language))[:100], value="cooldowns"),
      SelectOption(
        label='🛒 ' + translate_to_all_languages("profile.section_other", 'message', language),
        description=translate_to_all_languages("profile.section_other_desc", 'message', language),
        value="other",
      )
    ]
    select_menu = Select(
      row=0,
      placeholder='❓ ' + translate_to_all_languages("profile.choose_section", 'message', language),
      options=options,
    )
    select_menu.callback = self.select_callback
    self.add_item(select_menu)

    if not self.voted:
      self.add_item(Button(
        row=1,
        label=translate_to_all_languages("economy.vote_for_salary_boost", 'message', language),
        style=ButtonStyle.url,
        url="https://top.gg/bot/1051105900116574250/vote"
      ))

    tg_btn = Button(
      row=1,
      label=translate_to_all_languages("profile.link_telegram_button", 'message', language),
      style=ButtonStyle.primary,
      custom_id=''.join(choices(ascii_letters + digits, k=100))
    )
    tg_btn.callback = self.telegram_button_callback
    self.add_item(tg_btn)

    leaders_btn = Button(
      row=1,
      label='🏆 ' + translate_to_all_languages("economy.leaders_name", 'message', language),
      style=ButtonStyle.secondary,
      custom_id='leaders_' + ''.join(choices(ascii_letters + digits, k=20))
    )
    leaders_btn.callback = self.leaders_button_callback
    self.add_item(leaders_btn)

  async def select_callback(self, interaction: Interaction):
    if interaction.user.id != self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    await self.update_callback(interaction.data['values'][0])

  async def telegram_button_callback(self, interaction: Interaction):
    tm = self.bot.get_cog("TranslateMessage")
    if interaction.user.id != self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    await interaction.followup.send(await tm.translate_message("profile.feature_unavailable", self.language), ephemeral=True)
    self.stop()

  async def leaders_button_callback(self, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    tm = self.bot.get_cog("TranslateMessage")
    await interaction.followup.send(
      await tm.translate_message("profile.use_leaders_command", self.language), ephemeral=True)

class Profile(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  def _mask_circle(self, im: Image.Image, size: tuple[int, int]) -> Image.Image:
    if im.mode != "RGBA":
      im = im.convert("RGBA")
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size[0], size[1]), fill=255)
    im = ImageOps.fit(im, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    r, g, b, a = im.split()
    im.putalpha(ImageChops.multiply(a, mask))
    return im

  def _draw_xp_bar(
    self,
    draw: ImageDraw.ImageDraw,
    current_xp: int,
    need_xp: int,
    total_xp: int,
    lvl: int,
    pos: tuple[int, int],
    size: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    upscale: float = 1.0,
  ) -> None:
    x, y = pos
    w, h = size
    draw.rounded_rectangle([x, y, x + w, y + h], radius=int(8 * upscale), fill=(41, 48, 54))
    progress = min((current_xp / need_xp) if need_xp > 0 else 0, 1.0)
    fill_w = int(w * progress)
    if fill_w > 0:
      draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=int(8 * upscale), fill=(83, 198, 226))

    text_color = (128, 224, 245)
    xp_text = f"{current_xp}/{need_xp} ({total_xp}) XP"
    xp_bb = draw.textbbox((0, 0), xp_text, font=font)
    draw.text((x + w - (xp_bb[2] - xp_bb[0]), y + h - xp_bb[1] + int(5 * upscale)), xp_text, fill=text_color, font=font, stroke_width=int(0.4 * upscale))
    lvl_text = f"{lvl} LvL"
    lvl_bb = draw.textbbox((0, 0), lvl_text, font=font)
    draw.text((x + w - (lvl_bb[2] - lvl_bb[0]), y - h + lvl_bb[1] - int(15 * upscale)), lvl_text, fill=text_color, font=font, stroke_width=int(0.4 * upscale))

  def _draw_profile_sync(
    self,
    type_: str,
    real_username: str,
    status: str,
    username: str,
    display_name: str,
    avatar: Image.Image,
    badges: list,
    member_in_guild: bool,
    voted: bool,
    strings: dict,
    rank: int | None,
    total_users: int | None,
    **kwargs,
  ) -> Image.Image:
    upscale = 2.0
    xp = kwargs.get("xp", 0)
    LvL, XP_need, XP_now = calculate_LvL(xp)

    if type_ in ('discord', 'server'):
      width, height = int(380 * upscale), int(300 * upscale)
    elif type_ == 'economy':
      width, height = int(380 * upscale), int(380 * upscale)
    elif type_ == 'moderation':
      height = int(185 * upscale)
      violation = kwargs.get('violation') or {}
      for v_name, v_list in violation.items():
        for _ in (v_list or []):
          height += int(115 * upscale) if v_name in ('ban', 'mute') else int(90 * upscale)
        height += int(40 * upscale)
      width, height = int(380 * upscale), min(int(4000 * upscale), height)
    elif type_ == 'cooldowns':
      height = int(185 * upscale)
      cooldowns = kwargs.get('cooldowns') or {}
      height += int(105 * upscale) * len(cooldowns)
      width, height = int(380 * upscale), height
    else:
      width, height = int(380 * upscale), int(300 * upscale)

    bg_color = (35, 39, 42)
    text_color = (128, 224, 245)
    muted_color = (173, 176, 179)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rounded_bg = Image.new("RGBA", (width, height), bg_color)
    mask_bg = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask_bg).rounded_rectangle([0, 0, width, height], radius=int(20 * upscale), fill=255)
    img.paste(rounded_bg, (0, 0), mask_bg)
    draw = ImageDraw.Draw(img)

    font_path = "NotoSans-Regular.ttf" if path.exists("NotoSans-Regular.ttf") else None
    font_large = ImageFont.truetype(font_path, int(24 * upscale)) if font_path else ImageFont.load_default()
    font_small = ImageFont.truetype(font_path, int(16 * upscale)) if font_path else ImageFont.load_default()
    font_tiny  = ImageFont.truetype(font_path, int(10 * upscale)) if font_path else ImageFont.load_default()

    av_size = int(96 * upscale)
    avatar = self._mask_circle(avatar, (av_size, av_size))
    img.paste(avatar, (int(20 * upscale), int(20 * upscale)), avatar)

    badge_size = int(32 * upscale)
    status_ico = (Image.open(path.join('images', f'{status}.png')).resize((badge_size, badge_size), resample=Image.Resampling.LANCZOS).convert("RGBA"))
    img.paste(status_ico, (av_size - badge_size + int(20 * upscale), av_size - badge_size + int(20 * upscale)), status_ico)

    draw.text((int(130 * upscale), int(25 * upscale)), display_name, font=font_large, fill=text_color, stroke_width=int(0.4 * upscale))
    draw.text((int(130 * upscale), int(55 * upscale)), f"@{username}", font=font_small, fill=muted_color, stroke_width=int(0.4 * upscale))

    if rank is not None:
      rank_str = f"#{rank}"
      rank_bb = draw.textbbox((0, 0), rank_str, font=font_large)
      rank_w = rank_bb[2] - rank_bb[0]
      draw.text((width - int(20 * upscale) - rank_w, int(25 * upscale)), rank_str, font=font_large, fill=text_color, stroke_width=int(0.4 * upscale))
      if total_users and total_users > 0:
        pct = rank / total_users * 100
        pct_str = strings.get('top_label', 'Top') + f" {max(pct, 0.1):.1f}%"
        pct_bb = draw.textbbox((0, 0), pct_str, font=font_small)
        draw.text((width - int(20 * upscale) - (pct_bb[2] - pct_bb[0]), int(55 * upscale)), pct_str, font=font_small, fill=muted_color, stroke_width=int(0.4 * upscale))

    self._draw_xp_bar(draw, XP_now, XP_need, xp, LvL, (int(130 * upscale), int(90 * upscale)), (int(210 * upscale), int(10 * upscale)), font_small, upscale)

    badge_y = int(125 * upscale)
    badge_x = int(25 * upscale)
    position = 0
    if path.exists('badges'):
      for badge_file in listdir('badges')[:8]:
        if badge_file.endswith((".png", ".gif")) and badge_file[:-4] in badges:
          badge_img = (Image.open(path.join('badges', badge_file)).resize((badge_size, badge_size), resample=Image.Resampling.LANCZOS).convert("RGBA"))
          img.paste(badge_img, (badge_x + position * (badge_size + int(5 * upscale)), badge_y), badge_img)
          position += 1
    if member_in_guild and position <= 9:
      b = (Image.open(path.join('images', 'guild.png')).resize((badge_size, badge_size), resample=Image.Resampling.LANCZOS).convert("RGBA"))
      img.paste(b, (badge_x + position * (badge_size + int(5 * upscale)), badge_y), b)
      position += 1
    if voted and position <= 9:
      b = (Image.open(path.join('badges', 'voted.png')).resize((badge_size, badge_size), resample=Image.Resampling.LANCZOS).convert("RGBA"))
      img.paste(b, (badge_x + position * (badge_size + int(5 * upscale)), badge_y), b)
      position += 1

    draw.line((int(20 * upscale), int(163 * upscale), int(360 * upscale), int(163 * upscale)),fill=(43, 49, 55), width=int(3 * upscale))

    def paste_icon(name: str, w_px: int, h_px: int, y_px: int):
      ico = (Image.open(path.join('images', f'{name}.png')).resize((int(w_px * upscale), int(h_px * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA"))
      img.paste(ico, (int(24 * upscale), int(y_px * upscale)), ico)

    if type_ in ('discord', 'server'):
      paste_icon('messages', 24, 32, 172)
      paste_icon('voice',    24, 32, 202)
      paste_icon('calendar', 24, 32, 232)

      draw.text((int(54 * upscale), int(177 * upscale)), strings['messages_label'] + f" {kwargs.get('messages', 0)}", font=font_small, fill=text_color, stroke_width=int(0.4 * upscale))
      draw.text((int(54 * upscale), int(207 * upscale)), strings['voice_label'] + f" {kwargs.get('voice', '0d 0h 0m')}", font=font_small, fill=text_color, stroke_width=int(0.4 * upscale))
      draw.text((int(54 * upscale), int(237 * upscale)), strings['reg_label'] + f" {kwargs.get('reg_data', '—')}", font=font_small, fill=text_color, stroke_width=int(0.4 * upscale))

    elif type_ == 'economy':
      icons = ['economy','bank_balance','balance','upgrade','x2workamount','x2buyamount']
      ys = [170, 200, 230, 260, 290, 320]
      for ico_name, y_px in zip(icons, ys):
        paste_icon(ico_name, 24, 24, y_px)

      rows = [
        (strings['total_label'], f" {kwargs.get('total_balance', 0)}₩"),
        (strings['bank_label'], f" {kwargs.get('bank_balance', 0)}₩"),
        (strings['balance_label'], f" {kwargs.get('balance', 0)}₩"),
        (strings['upgrade_label'], f" {kwargs.get('upgrade', 0)}"),
        (strings['x2work_label'], f" {kwargs.get('x2workamount', 0)}"),
        (strings['x2buy_label'], f" {kwargs.get('x2buyamount', 0)}"),
      ]
      for (label, value), y_px in zip(rows, ys):
        draw.text((int(54 * upscale), int((y_px + 5) * upscale)), label + value, font=font_small, fill=text_color, stroke_width=int(0.4 * upscale))

    elif type_ == 'moderation':
      violation = kwargs.get('violation') or {}
      text_h = int(168 * upscale)
      type_order = ['warn','mute','kick','ban','unwarn','unmute','unban']
      violation_sorted = {k: violation[k] for k in type_order if k in violation}
      violation_sorted.update({k: v for k, v in violation.items() if k not in type_order})

      if violation_sorted:
        for v_name, v_list in violation_sorted.items():
          if not v_list:
            continue
          title = strings.get(f'vtype_{v_name}', v_name)
          tb = draw.textbbox((0, 0), title, font=font_large)
          draw.text(((width - (tb[2] - tb[0])) // 2, text_h), title, font=font_large, fill=text_color, stroke_width=int(0.6 * upscale))
          text_h += int(40 * upscale)

          for entry in v_list:
            lines = [
              (strings['reason_label'], entry.get('reason', '—')),
              (strings['mod_label'],    entry.get('mod', '—')),
              (strings['date_label'],   entry.get('timestamp', '—')),
            ]
            if v_name in ('ban', 'mute'):
              lines.append((strings['duration_label'], str(entry.get('duration', '—'))))
            for label, val in lines:
              draw.text((int(24 * upscale), text_h), f"{label}: {val}", font=font_small, fill=text_color, stroke_width=int(0.4 * upscale))
              text_h += int(25 * upscale)
            text_h += int(15 * upscale)
      else:
        no_data = strings.get('no_data', 'No Data')
        tb = draw.textbbox((0, 0), no_data, font=font_large)
        draw.text(((width - (tb[2] - tb[0])) // 2, int(168 * upscale)), no_data, font=font_large, fill=text_color, stroke_width=int(0.6 * upscale))

    elif type_ == 'cooldowns':
      cooldowns = kwargs.get('cooldowns') or {}
      text_h = int(168 * upscale)
      for cd_name, cd_val in cooldowns.items():
        tb = draw.textbbox((0, 0), cd_name, font=font_large)
        draw.text(((width - (tb[2] - tb[0])) // 2, text_h), cd_name, font=font_large, fill=text_color, stroke_width=int(0.6 * upscale))
        text_h += int(40 * upscale)

        _in = cd_val.get('in', strings.get('now', 'Now!'))
        _used = cd_val.get('used', strings.get('never', 'Never!'))
        draw.text((int(24 * upscale), text_h), strings['used_label'] + f" {_used}.", font=font_small, fill=text_color, stroke_width=int(0.4 * upscale))
        text_h += int(25 * upscale)
        draw.text((int(24 * upscale), text_h), strings['in_label'] + f": {_in if _in != '0:00:00' else strings.get('now', 'Now!')}",font=font_small, fill=text_color, stroke_width=int(0.4 * upscale))
        text_h += int(40 * upscale)

    clock = (Image.open(path.join('images', 'clock.png')).resize((int(15 * upscale), int(20 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA"))
    img.paste(clock, (int(25 * upscale), height - int(22 * upscale)), clock)
    draw.text((int(41 * upscale), height - int(20 * upscale)), f"{strings['called_label']} {real_username} | {datetime.now(timezone.utc).strftime('%d.%m.%y %H:%M:%S.%f')[:-3]}", font=font_tiny, fill=muted_color, stroke_width=int(0.1 * upscale))

    return img

  async def _build_profile_image(
    self,
    type_: str,
    real_username: str,
    status: str,
    language: str,
    username: str,
    display_name: str,
    avatar: Image.Image,
    badges: list,
    member_in_guild: bool,
    voted: bool,
    rank: int | None,
    total_users: int | None,
    **kwargs,
  ) -> Image.Image:
    tm = self.bot.get_cog("TranslateMessage")

    async def t(s: str) -> str:
      return await tm.translate_message(s, language)

    strings: dict = {
      'top_label': await t("profile.leaderboard_top"),
      'messages_label': await t("profile.messages_count"),
      'voice_label': await t("profile.voice_time"),
      'reg_label': await t("profile.register_date"),
      'total_label': await t("profile.total_money"),
      'bank_label': await t("profile.bank_money"),
      'balance_label': await t("profile.hand_money"),
      'upgrade_label': await t("economy.upgrade_label"),
      'x2work_label': await t("profile.x2_work_boosts"),
      'x2buy_label': await t("profile.x2_buy_boosts"),
      'reason_label': await t("profile.violation_reason"),
      'mod_label': await t("profile.moderator"),
      'date_label': await t("profile.violation_date"),
      'duration_label': await t("profile.violation_duration"),
      'no_data': await t("profile.no_violations"),
      'used_label': await t("profile.last_used"),
      'in_label': await t("profile.available_in"),
      'now': await t("profile.now"),
      'never': await t("profile.never_used"),
      'called_label': await t("profile.called_at"),
      'vtype_warn': await t("profile.warnings"),
      'vtype_mute': await t("profile.timeouts"),
      'vtype_kick': await t("profile.kicks"),
      'vtype_ban': await t("profile.bans"),
      'vtype_unwarn': await t("profile.remove_warns"),
      'vtype_unmute': await t("profile.remove_timeouts"),
      'vtype_unban': await t("profile.remove_bans"),
    }

    draw_fn = partial(
      self._draw_profile_sync,
      type_=type_,
      real_username=real_username,
      status=status,
      username=username,
      display_name=display_name,
      avatar=avatar,
      badges=badges,
      member_in_guild=member_in_guild,
      voted=voted,
      strings=strings,
      rank=rank,
      total_users=total_users,
      **kwargs,
    )
    return await asyncio.get_event_loop().run_in_executor(None, draw_fn)

  @slash_command(
    description="View user profile",
    name_localizations=translate_to_all_languages('social.profile_name', 'name'),
    description_localizations=translate_to_all_languages('social.profile_desc', 'description'),
    integration_types=[IntegrationType.user_install, IntegrationType.guild_install],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],
  )
  async def profile(
    self,
    interaction: Interaction,
    user: User = SlashOption(
      name="user",
      description="User profile to view",
      required=False,
      name_localizations=translate_to_all_languages('social.user_param', 'name'),
      description_localizations=translate_to_all_languages('social.user_param_desc', 'description'),
    ),
    ephemeral: bool = SlashOption(
      name="ephemeral",
      description="Should others see this message?",
      required=False,
      default=False,
      name_localizations=translate_to_all_languages('social.ephemeral_param', 'name'),
      description_localizations=translate_to_all_languages('social.ephemeral_param_desc', 'description'),
    ),
  ):
    try:
      caller_id = interaction.user.id
      current_time = time()

      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")
      lang_for_cooldown = _get_locale(interaction.locale)

      if caller_id in slash_command_cooldown:
        last_time = slash_command_cooldown[caller_id]['time']
        if current_time - last_time < 10:
          return await interaction.response.send_message(await tm.translate_message("error.rate_limit", lang_for_cooldown, variables={"time": f"<t:{round(last_time + 10)}:R>"}),ephemeral=True)
        slash_command_cooldown[caller_id]['time'] = current_time
      else:
        slash_command_cooldown[caller_id] = {'time': current_time}

      target_id: int | None = None
      if user is not None:
        try:
          target_id = user.id
        except Exception:
          return await interaction.response.send_message(await tm.translate_message('error.user_not_found', lang_for_cooldown),ephemeral=True)

      viewing_own = (target_id is None or target_id == caller_id)
      effective_target_id = target_id if target_id else caller_id

      caller_settings = await gd.get_data(caller_id, ['language', 'variation', 'discord_id', 'telegram_id', 'reg_data', 'badges'],'users', 'user_id', interaction.guild)
      caller_privacy = await gd.get_data(caller_id, ['publicity'], 'user_privacy', 'user_id', interaction.guild)
      language = caller_settings['language']
      variation = caller_settings['variation']
      caller_public = caller_privacy['publicity']

      if not viewing_own:
        if not caller_public:
          try:
            await interaction.response.send_message(
              await tm.translate_message("error.your_profile_hidden",language,),ephemeral=True)
          except InteractionResponded:
            await interaction.followup.send(
              await tm.translate_message("error.your_profile_hidden",language,),ephemeral=True)
          return

        target_privacy = await gd.get_data(effective_target_id, ['publicity'], 'user_privacy', 'user_id', interaction.guild)
        if not target_privacy['publicity']:
          try:
            await interaction.response.send_message(await tm.translate_message("profile.target_profile_hidden", language),ephemeral=True)
          except InteractionResponded:
            await interaction.followup.send(
              await tm.translate_message("profile.target_profile_hidden", language),ephemeral=True)
          return

      try:
        loading_msg = await interaction.response.send_message(await tm.translate_message("profile.loading", language), ephemeral=ephemeral)
      except InteractionResponded:
        loading_msg = await interaction.followup.send(await tm.translate_message("profile.loading", language), ephemeral=ephemeral)

      invite = await gi.invite(interaction.guild)

      if not viewing_own:
        tgt_settings = await gd.get_data(effective_target_id,['variation', 'discord_id', 'telegram_id', 'reg_data', 'badges'],'users', 'user_id', interaction.guild)
        variation = tgt_settings['variation']
        reg_data = tgt_settings['reg_data']
        badges = tgt_settings['badges']
      else:
        reg_data = caller_settings['reg_data']
        badges = caller_settings['badges']

      if not (hasattr(self.bot, 'db_pool') and self.bot.db_pool):
        await loading_msg.edit('postgresql not loaded in profile')
        return

      async with self.bot.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT bank_balance, balance, xp, x2workamount, x2buyamount, upgrade FROM user_data WHERE user_id = $1",effective_target_id)
        xp = row['xp'] if row else 0
        bank_balance = row['bank_balance'] if row else 0
        balance = row['balance'] if row else 0
        x2workamount = row['x2workamount'] if row else 0
        x2buyamount = row['x2buyamount'] if row else 0
        upgrade = row['upgrade'] if row else 0

        rank_row = await conn.fetchrow(
          """
          SELECT
            (SELECT COUNT(*) FROM user_data WHERE xp > $1) + 1 AS rank,
            (SELECT COUNT(*) FROM user_data) AS total
          """,
          xp
        )
        global_rank  = rank_row['rank']  if rank_row else None
        total_users  = rank_row['total'] if rank_row else None

        cd_rows = await conn.fetch("SELECT command, timestamp FROM cooldowns WHERE user_id = $1",effective_target_id)
      worka = rob = insert_data = 0
      for r in cd_rows:
        if r['command'] == 'work': worka = r['timestamp']
        elif r['command'] == 'rob': rob = r['timestamp']
        elif r['command'] == 'insert_data': insert_data = r['timestamp']

      violation: dict = {}
      if interaction.guild:
        async with self.bot.db_pool.acquire() as conn:
          v_rows = await conn.fetch("SELECT type, reason, duration, timestamp, mod_id FROM violations WHERE user_id = $1 AND guild_id = $2", effective_target_id, interaction.guild.id)
        for r in v_rows:
          vtype = r['type']
          entry = {
            "reason": r['reason'],
            "mod": f"{self.bot.get_user(int(r['mod_id'])).name if self.bot.get_user(int(r['mod_id'])) else 'Not Found'}({r['mod_id']})",
            "timestamp": datetime.fromtimestamp(r['timestamp']).strftime('%d.%m.%y %H:%M:%S'),
          }
          if vtype in ('ban', 'mute', 'unmute'):
            entry['duration'] = timedelta(seconds=r['duration']) if r['duration'] else '∞'
          violation.setdefault(vtype, []).append(entry)

      sbank_balance = await suffics(number=bank_balance, variation=variation)
      sbalance = await suffics(number=balance,      variation=variation)
      stotal = await suffics(number=bank_balance + balance, variation=variation)

      headers = {
        "Authorization": getenv("TOPGG_DISCORDBOT_TOKEN_API"),
        "Content-Type": "application/json",
      }
      async with ClientSession() as session:
        async with session.get(f"https://top.gg/api/bots/{self.bot.user.id}/check?userId={effective_target_id}",headers=headers) as resp:
          vote = (await resp.json()).get("voted") == 1 if resp.status == 200 else False

      def _get_status():
        member = find(
          lambda m: m == (user if not viewing_own else interaction.user),
          (mb for g in self.bot.guilds for mb in g.members),
        )
        return str(getattr(member or interaction.user, 'status', 'offline'))

      def _member_in_guild():
        return interaction.guild.get_member(effective_target_id) is not None if interaction.guild else False

      site_promo = ("## " + await tm.translate_message("profile.site_info",language) + "\n**https://wolium.netlify.app/**")

      async def update_callback(tipe: str):
        nonlocal loading_msg

        async with ClientSession() as session:
          av_url = getattr(user, 'display_avatar', interaction.user.display_avatar).url
          async with session.get(av_url) as r:
            avatar = Image.open(BytesIO(await r.read()))

        common = dict(
          type_=tipe,
          real_username=interaction.user.name,
          status=_get_status(),
          language=language,
          username=getattr(user, 'name', interaction.user.name),
          display_name=getattr(user, 'display_name', interaction.user.display_name),
          avatar=avatar,
          badges=badges,
          member_in_guild=_member_in_guild(),
          voted=vote,
          rank=global_rank,
          total_users=total_users,
          xp=xp,
        )

        if tipe in ('discord', 'server'):
          async with self.bot.db_pool.acquire() as conn:
            if tipe == 'discord':
              messages = await conn.fetchval("SELECT COUNT(*) FROM messages WHERE user_id = $1", effective_target_id)
              voice_row = await conn.fetchrow("SELECT COALESCE(SUM(time_spent), '0 seconds'::interval) AS t FROM voice WHERE user_id = $1",effective_target_id)
            else:
              messages = await conn.fetchval("SELECT COUNT(*) FROM messages WHERE user_id = $1 AND guild_id = $2",effective_target_id, interaction.guild.id if interaction.guild else 0)
              voice_row = await conn.fetchrow("SELECT COALESCE(SUM(time_spent), '0 seconds'::interval) AS t FROM voice WHERE user_id = $1 AND guild_id = $2",effective_target_id, interaction.guild.id if interaction.guild else 0)
          v: timedelta = voice_row['t']
          common.update(
            reg_data=datetime.fromtimestamp(reg_data).strftime('%d.%m.%y'),
            messages=messages,
            voice=f"{v.days}d {v.seconds // 3600}h {(v.seconds % 3600) // 60}m",
          )

        elif tipe == 'economy':
          common.update(
            total_balance=stotal,
            bank_balance=sbank_balance,
            balance=sbalance,
            upgrade=upgrade,
            x2workamount=x2workamount,
            x2buyamount=x2buyamount,
          )

        elif tipe == 'moderation':
          common['violation'] = deepcopy(violation)

        elif tipe == 'cooldowns':
          common['cooldowns'] = {
            await tm.translate_message("profile.command_work", language): {
              "in": str(timedelta(seconds=max(0, (worka + 60 * 39) - time()))).split('.')[0],
              "used": format_datetime(datetime.fromtimestamp(worka), "d MMMM, HH:mm:ss", locale=language),
            },
            await tm.translate_message("profile.command_rob", language): {
              "in": str(timedelta(seconds=max(0, (rob + 60 * 60 * 6) - time()))).split('.')[0],
              "used": format_datetime(datetime.fromtimestamp(rob), "d MMMM, HH:mm:ss", locale=language),
            },
            await tm.translate_message("profile.command_insert", language): {
              "in": str(timedelta(seconds=max(0, (insert_data + 31 * 24 * 60 * 60) - time()))).split('.')[0],
              "used": format_datetime(datetime.fromtimestamp(insert_data), "d MMMM, HH:mm:ss", locale=language),
            },
          }

        elif tipe == 'other':
          try:
            await loading_msg.edit(await tm.translate_message("profile.section_other_content", language) + site_promo)
          except Exception:
            await interaction.followup.send(await tm.translate_message("profile.section_other_content", language) + site_promo, ephemeral=True,)
          return

        img = await self._build_profile_image(**common)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        file = File(buf, filename="profile.png")

        try:
          await loading_msg.edit(site_promo, file=file)
        except Exception:
          await interaction.followup.send(site_promo, file=file, ephemeral=True)

      view = ProfileView(caller_id, language, update_callback, vote, self.bot)
      try:
        await loading_msg.edit(await tm.translate_message("profile.loading_step2", language), view=view)
      except Exception:
        await interaction.followup.send(await tm.translate_message("profile.loading_step2", language),ephemeral=True, view=view)

      await update_callback("discord")

    except Exception as e:
      tb = ''.join(format_exception(type(e), e, e.__traceback__))[:5000]
      log = Embed(
        title=f"User: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Command: ||**/profile** `user` **{user}**||",
        color=Color.red(),
        timestamp=datetime.now(timezone.utc),
      )
      log.set_author(
        name=f"Server ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=interaction.user.display_avatar.url,
      )
      if interaction.guild:
        invite = await self.bot.get_cog("GetInvite").invite(interaction.guild)
        log.add_field(
          name="Server",
          value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}",
          inline=False,
        )
      log.add_field(
        name="Channel",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
        inline=False,
      )
      for i in range(0, len(tb), 1000):
        log.add_field(name="Error", value=f"```py\n{tb[i:i+1000]}```", inline=False)
      log.set_footer(
        text=str(datetime.now()),
        icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png",
      )
      lang = _get_locale(interaction.locale)
      await interaction.followup.send(await tm.translate_message("error.occurred_logs_saved_review", lang), ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

  setattr(profile, "extras", {"description": "Shows comprehensive profile information for any user."})


def setup(bot: commands.Bot):
  bot.add_cog(Profile(bot))
