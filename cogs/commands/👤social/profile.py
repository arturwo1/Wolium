from string import ascii_letters, digits
from nextcord.ext import commands
from nextcord import File, IntegrationType, InteractionContextType, SlashOption, ButtonStyle, SelectOption, Interaction, slash_command, User, Embed, Color
from nextcord.ui import View, Button, Select, Modal, TextInput
from nextcord.errors import InteractionResponded
from nextcord.utils import find
from time import time
from datetime import datetime, timedelta, timezone
from traceback import format_exception
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from Utils.suffics import suffics
from cogs.utils.get_invite import GetInvite
from cogs.utils.translate_message import TranslateMessage
from cogs.utils.get_data import GetData
from random import choices
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops
from os import getenv, path, listdir
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from aiohttp import ClientSession
from copy import deepcopy
from babel.dates import format_datetime
from Utils.calculate_LvL import calculate_LvL

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages
executor = ThreadPoolExecutor()

class создать_дату_модал(Modal):
  def __init__(self, bot:commands.Bot):
    self.bot = bot
    super().__init__(title=translate_to_all_languages("ID Вашего Телеграм Аккаунта", 'message', 'en'))
    self.user_telegram_id = TextInput(
      label=translate_to_all_languages("Телеграм ID:", 'message', 'en'),
      min_length=2,
      max_length=int(str(datetime.now().year)[2:]),
      required=True,
      placeholder=translate_to_all_languages("Введите Здесь Ваш Телеграм ID.", 'message', 'en'))
    
    self.add_item(self.user_telegram_id)
      
  async def callback(self, interaction: Interaction):
    user_telegram_id = self.user_telegram_id.value
    if user_telegram_id==0:
      return await interaction.send(await (TranslateMessage(self.bot)).translate_message(f"Телеграм ID:",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **`{user_telegram_id}`** "+await (TranslateMessage(self.bot)).translate_message(f"Не Правильный!", interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'),ephemeral=True)
    user_settings = await (GetData(self.bot)).get_data(self.user_telegram_id.value,['language'],'users','user_id',interaction.guild)
    language = user_settings['language']
    if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
      async with self.bot.db_pool.acquire() as conn:
        try:
          await conn.execute(
            "UPDATE users SET discord_id = $1 WHERE telegram_id = $2",
            interaction.user.id, self.user_telegram_id.value
          )
        except Exception:
          return await interaction.send(await (TranslateMessage(self.bot)).translate_message(f"Телеграм ID:",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **`{user_telegram_id}`** "+await (TranslateMessage(self.bot)).translate_message(f"Не Правильный!", interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'),ephemeral=True)
        return await interaction.send(translate_to_all_languages(f"Теперь Вы Можете Спокойно Использовать Бота Одновременно В Телеграм И Дискорд Одновременно!\nА Также У Вас Теперь Есть Значок Дискорда В Профиле Бота. :D\nВам Нужно Ввести Команду Заново.", 'message', language),ephemeral=True)
    return await interaction.send('PostgreSQL not loaded in profile', ephemeral=True)

class привязать_телеграм(View):
  def __init__(self, user_id:int, language:str, update_callback, voted:bool, bot:commands.Bot, timeout=60*5):
    super().__init__(timeout=timeout)
    self.language = language
    self.user_id = user_id
    self.update_callback = update_callback
    self.bot = bot
    self.voted = voted

    if not self.voted:
      vote = Button(
        row=1,
        label=translate_to_all_languages("Голосовать Для +50% Зарплаты", 'message', self.language),
        style=ButtonStyle.url,
        url="https://top.gg/bot/1051105900116574250/vote"
      )
      self.add_item(vote)
    
    custom_button = Button(
      row=1,
      label=translate_to_all_languages("Привязать Телеграм Аккаунт", 'message', language),
      style=ButtonStyle.primary,
      custom_id=''.join(choices(ascii_letters + digits, k=100))
    )
    custom_button.callback = self.custom_button_callback
    self.add_item(custom_button)

    options = [
      {
        "label": '🔵'+translate_to_all_languages("Дискорд", 'message', language),
        "value": "discord",
        "description": translate_to_all_languages("Показывает Твою Информацию В Дискорде.", 'message', language)
      },
      {
        "label": '📘'+translate_to_all_languages("Сервер", 'message', language),
        "value": "server",
        "description": translate_to_all_languages("Показывает Твою Информацию На Сервере.", 'message', language)
      },
      {
        "label": '💹'+translate_to_all_languages("Экономика", 'message', language),
        "value": "economy",
        "description": translate_to_all_languages("Показывает Твою Экономическую Информацию.", 'message', language)
      },
      {
        "label": '🚨'+translate_to_all_languages("Нарушения", 'message', language),
        "value": "moderation",
        "description": translate_to_all_languages("Показывает Твои Нарушения.", 'message', language)
      },
      {
        "label": '🔄'+translate_to_all_languages("Перезарядки", 'message', language),
        "value": "cooldowns",
        "description": str(translate_to_all_languages("Показывает Когда Ты Сможешь Использовать Снова Команду У Которой Длинная Перезарядка.", 'message', language))[:100]
      },
      {
        "label": '🛒'+translate_to_all_languages("Другое", 'message', language),
        "value": "other",
        "description": translate_to_all_languages("Другое.", 'message', language)
      },
    ]

    select_menu = Select(
      row=0,
      placeholder='❓'+translate_to_all_languages("Выберите:", 'message', language),
      options=[
        SelectOption(label=opt['label'], description=opt.get('description', ''), value=opt['value'])
        for opt in options
      ]
    )
    select_menu.callback = self.select_callback
    self.add_item(select_menu)

  async def select_callback(self, interaction: Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    selected_value = interaction.data['values'][0]
    await self.update_callback(selected_value)
    
  async def custom_button_callback(self, interaction: Interaction):
    if interaction.user.id!=self.user_id:
      return
    if interaction.response.is_done():
      return
    await interaction.response.defer()
    await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Пока Эта Функция Недоступна.", self.language),ephemeral=True)
    self.stop()


class Profile(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  def draw_xp_bar(self, draw: ImageDraw, current_xp: int, need_xp: int, total_xp: int, LvL: int, pos: tuple[int, int], size: tuple[int, int], font: ImageFont, upscale: float = 1.0):
    x, y = pos[0], pos[1]
    width, height = size[0], size[1]
    bar_bg = (41, 48, 54)
    bar_fill = (83, 198, 226)
    text_color = (128, 224, 245)

    draw.rounded_rectangle([x, y, x + width, y + height], radius=8 * upscale, fill=bar_bg)
    progress = min((current_xp / need_xp) if need_xp > 0 else 0, 1.0)
    fill_width = int(width * progress)
    draw.rounded_rectangle([x, y, x + fill_width, y + height], radius=8 * upscale, fill=bar_fill)

    xp_text = f"{current_xp}/{need_xp} ({total_xp}) XP"
    xp_bbox = draw.textbbox((0, 0), xp_text, font=font)
    xp_text_x = x + width - xp_bbox[2]
    xp_text_y = y + height - xp_bbox[1] + 5 * upscale
    draw.text((xp_text_x, xp_text_y), xp_text, fill=text_color, font=font, stroke_width=0.4 * upscale)

    lvl_text = f"{LvL} LvL"
    lvl_bbox = draw.textbbox((0, 0), lvl_text, font=font)
    lvl_text_x = x + width - lvl_bbox[2]
    lvl_text_y = y - height + lvl_bbox[1] - 15 * upscale
    draw.text((lvl_text_x, lvl_text_y), lvl_text, fill=text_color, font=font, stroke_width=0.4)

  def mask_circle(self,im:Image, size:tuple[int,int]):
    if im.mode != "RGBA":
      im = im.convert("RGBA")

    # Маска круга
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)

    # Обрезаем изображение
    im = ImageOps.fit(im, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    
    # Объединяем альфа-канал изображения и круглую маску
    r, g, b, a = im.split()
    a = ImageChops.multiply(a, mask)
    im.putalpha(a)

    return im

  async def _draw_user_profile(
    self,
    type_: str,
    real_username: str,
    status: str,
    language: str,
    bot: commands.Bot,
    username: str,
    display_name: str,
    avatar: Image,
    badges: list[dict[str, bool]],
    member_in_guild: bool,
    voted: bool,
    **kwargs
  ):
    upscale = 2.0
    xp = kwargs.get("xp", 0)
    LvL, XP_need, XP_now = calculate_LvL(xp)

    if type_ in ['discord', 'server']:
      width, height = int(380 * upscale), int(290 * upscale)
    elif type_ == 'economy':
      width, height = int(380 * upscale), int(380 * upscale)
    elif type_ == 'moderation':
      height = int(185 * upscale)
      violation: dict[str, list[str | int]] = kwargs.get('violation', None)
      if violation:
        for v_name, v_value in violation.items():
          if v_name in ['ban','mute']:
            if isinstance(v_value, list):
              for _ in v_value:
                height += int(115 * upscale)
          else:
            if isinstance(v_value, list):
              for _ in v_value:
                height += int(90 * upscale)
          height += int(40 * upscale)
      width, height = int(380 * upscale), min(int(4000 * upscale), height)
    elif type_=='cooldowns':
      height = int(185 * upscale)
      cooldowns:dict[str,dict[str,str]]=kwargs.get('cooldowns',None)
      if cooldowns:
        for _ in cooldowns:
          height+=int(105*upscale)
      width, height = int(380*upscale), height
    else:
      width, height = int(380 * upscale), int(290 * upscale)
    bg_color = (35, 39, 42)
    text_color = (128, 224, 245)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rounded_bg = Image.new("RGBA", (width, height), bg_color)
    mask = Image.new("L", (width, height), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([0, 0, width, height], radius=int(20 * upscale), fill=255)
    img.paste(rounded_bg, (0, 0), mask)
    draw = ImageDraw.Draw(img)

    font_path = "NotoSans-Regular.ttf" if path.exists("NotoSans-Regular.ttf") else None
    font_large = ImageFont.truetype(font_path, int(24 * upscale)) if font_path else ImageFont.load_default()
    font_small = ImageFont.truetype(font_path, int(16 * upscale)) if font_path else ImageFont.load_default()
    font_verysmall = ImageFont.truetype(font_path, int(10 * upscale)) if font_path else ImageFont.load_default()

    avatar_size = int(96 * upscale)
    avatar = self.mask_circle(avatar, (avatar_size, avatar_size))
    img.paste(avatar, (int(20 * upscale), int(20 * upscale)), avatar)

    badge_size = int(32 * upscale)

    status_ico = Image.open(path.join('images', f'{status}.png')).resize((badge_size, badge_size), resample=Image.Resampling.LANCZOS).convert("RGBA")
    img.paste(status_ico, (avatar_size-badge_size+int(20 * upscale), avatar_size-badge_size+int(20 * upscale)), status_ico)

    draw.text((int(130 * upscale), int(25 * upscale)), display_name, font=font_large, fill=text_color, stroke_width=0.4 * upscale)
    draw.text((int(130 * upscale), int(55 * upscale)), f"@{username}", font=font_small, fill=(173, 176, 179), stroke_width=0.4 * upscale)

    self.draw_xp_bar(draw, XP_now, XP_need, xp, LvL, (int(130 * upscale), int(90 * upscale)), (int(230 * upscale), int(10 * upscale)), font_small, upscale)

    badge_y = int(125 * upscale)
    badge_x = int(25 * upscale)
    if path.exists('badges'):
      position = 0
      for badge_file in listdir('badges')[:8]:
        if badge_file.endswith((".png", ".gif")) and badge_file[:-4] in badges:
          badge_path = path.join('badges', badge_file)
          badge = Image.open(badge_path).resize((badge_size, badge_size), resample=Image.Resampling.LANCZOS).convert("RGBA")
          img.paste(badge, (badge_x + position * (badge_size + int(5 * upscale)), badge_y), badge)
          position += 1
    if member_in_guild and position <= 9:
      badge = Image.open(path.join('images', 'guild.png')).resize((badge_size, badge_size), resample=Image.Resampling.LANCZOS).convert("RGBA")
      img.paste(badge, (badge_x + position * (badge_size + int(5 * upscale)), badge_y), badge)
      position += 1
    if voted and position <= 9:
      badge = Image.open(path.join('badges', 'voted.png')).resize((badge_size, badge_size), resample=Image.Resampling.LANCZOS).convert("RGBA")
      img.paste(badge, (badge_x + position * (badge_size + int(5 * upscale)), badge_y), badge)
      position += 1

    draw.line((int(20 * upscale), int(160 * upscale), int(360 * upscale), int(160 * upscale)), fill=(43, 49, 55), width=int(3 * upscale))

    if type_ in ['discord', 'server']:
      badge1 = Image.open(path.join('images', 'messages.png')).resize((int(24 * upscale), int(32 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA")
      badge2 = Image.open(path.join('images', 'voice.png')).resize((int(24 * upscale), int(32 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA")
      badge3 = Image.open(path.join('images', 'calendar.png')).resize((int(24 * upscale), int(32 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA")

      img.paste(badge1, (int(24 * upscale), int(170 * upscale)), badge1)
      img.paste(badge2, (int(24 * upscale), int(200 * upscale)), badge2)
      img.paste(badge3, (int(24 * upscale), int(230 * upscale)), badge3)

      draw.text((int(50 * upscale), int(175 * upscale)), await (TranslateMessage(bot)).translate_message("Сообщения:", language) + f" {kwargs.get('messages', 0)}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
      draw.text((int(50 * upscale), int(205 * upscale)), await (TranslateMessage(bot)).translate_message("Время В Голосовом Канале:", language) + f" {kwargs.get('voice', 0)}.", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
      draw.text((int(50 * upscale), int(235 * upscale)), await (TranslateMessage(bot)).translate_message("Дата Регистрации:", language) + f" {kwargs.get('reg_data', 0)}.", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
    elif type_ == 'economy':
      badge1 = Image.open(path.join('images', 'economy.png')).resize((int(24 * upscale), int(24 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA")
      badge2 = Image.open(path.join('images', 'bank_balance.png')).resize((int(24 * upscale), int(24 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA")
      badge3 = Image.open(path.join('images', 'balance.png')).resize((int(24 * upscale), int(24 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA")
      badge4 = Image.open(path.join('images', 'upgrade.png')).resize((int(24 * upscale), int(24 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA")
      badge5 = Image.open(path.join('images', 'x2workamount.png')).resize((int(24 * upscale), int(24 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA")
      badge6 = Image.open(path.join('images', 'x2buyamount.png')).resize((int(24 * upscale), int(24 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA")

      img.paste(badge1, (int(24 * upscale), int(170 * upscale)), badge1)
      img.paste(badge2, (int(24 * upscale), int(200 * upscale)), badge2)
      img.paste(badge3, (int(24 * upscale), int(230 * upscale)), badge3)
      img.paste(badge4, (int(24 * upscale), int(260 * upscale)), badge4)
      img.paste(badge5, (int(24 * upscale), int(290 * upscale)), badge5)
      img.paste(badge6, (int(24 * upscale), int(320 * upscale)), badge6)

      draw.text((int(50 * upscale), int(175 * upscale)), await (TranslateMessage(bot)).translate_message("Всего Денег:", language) + f" €{kwargs.get('total_balance', 0)}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
      draw.text((int(50 * upscale), int(205 * upscale)), await (TranslateMessage(bot)).translate_message("В Банке Денег:", language) + f" €{kwargs.get('bank_balance', 0)}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
      draw.text((int(50 * upscale), int(235 * upscale)), await (TranslateMessage(bot)).translate_message("В Руках Денег:", language) + f" €{kwargs.get('balance', 0)}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
      draw.text((int(50 * upscale), int(265 * upscale)), await (TranslateMessage(bot)).translate_message("Улучшение:", language) + f" {kwargs.get('upgrade', 0)}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
      draw.text((int(50 * upscale), int(295 * upscale)), await (TranslateMessage(bot)).translate_message("x2 Заработок Количество:", language) + f" {kwargs.get('x2workamount', 0)}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
      draw.text((int(50 * upscale), int(325 * upscale)), await (TranslateMessage(bot)).translate_message("х2 Покупок Количество:", language) + f" {kwargs.get('x2buyamount', 0)}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
    elif type_ == 'moderation':
      str_reason = await (TranslateMessage(self.bot)).translate_message(f"Причина", language)
      str_mod = await (TranslateMessage(self.bot)).translate_message(f"Модератор", language)
      str_data = await (TranslateMessage(self.bot)).translate_message(f"Дата", language)
      str_time = await (TranslateMessage(self.bot)).translate_message(f"Длительность", language)
      if violation:
        text_height = int(165 * upscale)

        type_titles = {
          "warn": "Предупреждения",
          "mute": "Тайм-Ауты",
          "kick": "Изгнания",
          "ban": "Баны",
          "unwarn": "Снятие Предупреждений",
          "unmute": "Снятие Тайм-Аутов",
          "unban": "Снятие Банов"
        }
        extra_fields = {
          "ban": ["duration"],
          "mute": ["duration"]
        }
        for v_name, v_list in violation.items():
          if not v_list:
            continue

          # Заголовок
          translated_title = await TranslateMessage(self.bot).translate_message(type_titles.get(v_name, v_name), language)
          text_bbox = draw.textbbox((0, 0), translated_title, font=font_large)
          text_width = text_bbox[2] - text_bbox[0]
          center_x = (width - text_width) // 2
          draw.text((center_x, text_height), translated_title, font=font_large, fill=text_color, stroke_width=0.6 * upscale)
          text_height += int(40 * upscale)

          for entry in v_list:
            # Основная информация
            draw.text((int(24 * upscale), text_height), f"{str_reason}: {entry.get('reason', '-')}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
            text_height += int(25 * upscale)

            draw.text((int(24 * upscale), text_height), f"{str_mod}: {entry.get('mod', '-')}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
            text_height += int(25 * upscale)

            draw.text((int(24 * upscale), text_height), f"{str_data}: {entry.get('timestamp', '-')}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
            text_height += int(25 * upscale)

            # доп поля
            for extra in extra_fields.get(v_name, []):
              draw.text((int(24 * upscale), text_height), f"{str_time}: {entry.get(extra, '-')}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
              text_height += int(25 * upscale)

            text_height += int(15 * upscale)
      else:
        text = await TranslateMessage(self.bot).translate_message("Нет Данных", language)
        text_bbox = draw.textbbox((0, 0), text, font=font_large)
        text_width = text_bbox[2] - text_bbox[0]
        center_x = (width - text_width) // 2
        draw.text((center_x, int(165 * upscale)), text, font=font_large, fill=text_color, stroke_width=0.6 * upscale)
    elif type_=='cooldowns':
      text_height = int(165 * upscale)
      str_in = await (TranslateMessage(self.bot)).translate_message(f"Через", language)
      str_used = await (TranslateMessage(self.bot)).translate_message(f"Использовал", language)
      for cd_name, cd_value in cooldowns.items():
        str_cd_name = await (TranslateMessage(self.bot)).translate_message(cd_name, language)
        _in = cd_value.get('in',await (TranslateMessage(self.bot)).translate_message("Сейчас!", language))
        used = cd_value.get('used',await (TranslateMessage(self.bot)).translate_message("Никогда!", language))

        text_bbox = draw.textbbox((0, 0), str_cd_name, font=font_large)
        text_width = text_bbox[2] - text_bbox[0]
        center_x = (width - text_width) // 2
        draw.text((center_x, text_height), str_cd_name, font=font_large, fill=text_color, stroke_width=0.6 * upscale)
        text_height += int(40 * upscale)

        draw.text((int(24 * upscale), text_height), f"{str_used} {used}.", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
        text_height += int(25 * upscale)

        draw.text((int(24 * upscale), text_height), f"{str_in}: {_in if _in!="0:00:00" else await (TranslateMessage(self.bot)).translate_message("Сейчас!", language)}", font=font_small, fill=text_color, stroke_width=0.4 * upscale)
        text_height += int(40 * upscale)

    timeimage = Image.open(path.join('images', 'clock.png')).resize((int(15 * upscale), int(20 * upscale)), resample=Image.Resampling.LANCZOS).convert("RGBA")
    img.paste(timeimage, (int(25 * upscale), height - int(22 * upscale)), timeimage)
    draw.text((int(41.25 * upscale), height - int(20 * upscale)), f"{await (TranslateMessage(bot)).translate_message('Вызвал Команду:', language)} {real_username} | {datetime.now(timezone.utc).strftime('%d.%m.%y %H:%M:%S.%f')[:-3]}", font=font_verysmall, fill=(173, 176, 179), stroke_width=0.1 * upscale)

    return img 
  
  @slash_command(
    description="Просмотр Профиля",
    name_localizations=translate_to_all_languages('профиль', 'name'),
    description_localizations=translate_to_all_languages('Просмотр Профиля.', 'description'),
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
  async def профиль(self,
    interaction: Interaction,
    пользователь: User=SlashOption(name="пользователь", description="Ник Пользователя Для Просмотра/Создания Его Профиля.",required=False, name_localizations=translate_to_all_languages('пользователь', 'name'), description_localizations=translate_to_all_languages('Ник Пользователя Для Просмотра/Создания Его Профиля.', 'description')),
    лично: bool=SlashOption(name="лично", description="Будут Ли Другие Пользователи Видеть Это Сообщение?.",required=False, default=False, name_localizations=translate_to_all_languages('лично', 'name'), description_localizations=translate_to_all_languages('Будут Ли Другие Пользователи Видеть Это Сообщение?', 'description')),
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
      
      if пользователь!=None:
        try:
          member_id = пользователь.id
        except Exception:
          await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message('Пользователь Не Найден.',interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'),ephemeral=True)
          return
      else:
        member_id = None

      user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation','discord_id','telegram_id','reg_data','badges'],'users','user_id',interaction.guild)
      language = user_settings['language']
      variation = user_settings['variation']
      discord = user_settings['discord_id']
      telegram = user_settings['telegram_id']
      reg_data = user_settings['reg_data']
      badges = user_settings['badges']
      
      try:
        send_bank_message = await interaction.response.send_message(translate_to_all_languages("Загрузка Данных", 'message', language),ephemeral=лично)
      except InteractionResponded:
        send_bank_message = await interaction.followup.send(translate_to_all_languages("Загрузка Данных", 'message', language),ephemeral=лично)

      invite = await (GetInvite(self.bot)).invite(interaction.guild)

      if member_id:
        member_settings = await (GetData(self.bot)).get_data(member_id,['variation','discord_id','telegram_id','reg_data','badges'],'users','user_id',interaction.guild)
        variation = member_settings['variation']
        reg_data = member_settings['reg_data']
        badges = member_settings['badges']
        member_data = await (GetData(self.bot)).get_data(member_id,['bank_balance','balance','xp','x2workamount','x2buyamount','upgrade'],'user_data','user_id',interaction.guild)
        xp = member_data['xp']
        bank_balance = member_data['bank_balance']
        balance = member_data['balance']
        x2workamount = member_data['x2workamount']
        x2buyamount = member_data['x2buyamount']
        upgrade = member_data['upgrade']
      else:
        user_data = await (GetData(self.bot)).get_data(user_id,['bank_balance','balance','xp','x2workamount','x2buyamount','upgrade'],'user_data','user_id',interaction.guild)
        xp = user_data['xp']
        bank_balance = user_data['bank_balance']
        balance = user_data['balance']
        x2workamount = user_data['x2workamount']
        x2buyamount = user_data['x2buyamount']
        upgrade = user_data['upgrade']

      worka = 0
      rob = 0
      insert_data = 0
      
      if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
        async with self.bot.db_pool.acquire() as conn:
          query = f"SELECT command,timestamp FROM cooldowns where user_id = $1"
          data = await conn.fetch(query,member_id if member_id else user_id)
      else:
        await send_bank_message.edit('postgresql not loaded in profile')
        return
      for row in data:
        if row['command']=="work":
          worka = row['timestamp']
        if row['command']=="rob":
          rob = row['timestamp']
        if row['command']=="insert_data":
          insert_data=row['timestamp']
          
      violation = {}
      if interaction.guild:
        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          async with self.bot.db_pool.acquire() as conn:
            query = f"SELECT type,reason,duration,timestamp,mod_id FROM violations where user_id = $1 AND guild_id = $2"
            violations = await conn.fetch(query,member_id if member_id else user_id,interaction.guild.id)
        else:
          await send_bank_message.edit('postgresql not loaded in profile')
          return
        for row in violations:
          if row['type']=="warn":
            if 'warn' not in violation:
              violation['warn'] = []
            violation['warn'].append({
              "reason": row['reason'],
              "mod": f"{self.bot.get_user(int(row['mod_id'])).name if self.bot.get_user(int(row['mod_id'])) else 'Not Found'}({row['mod_id']})",
              "timestamp": datetime.fromtimestamp(row['timestamp']).strftime('%d.%m.%y %H:%M:%S')
            })
          elif row['type']=="mute":
            if 'mute' not in violation:
              violation['mute'] = []
            violation['mute'].append({
              "reason": row['reason'],
              "mod": f"{self.bot.get_user(int(row['mod_id'])).name if self.bot.get_user(int(row['mod_id'])) else 'Not Found'}({row['mod_id']})",
              "timestamp": datetime.fromtimestamp(row['timestamp']).strftime('%d.%m.%y %H:%M:%S'),
              "duration": timedelta(seconds=row['duration']) if row['duration'] else '∞'
            })
          elif row['type']=="kick":
            if 'kick' not in violation:
              violation['kick'] = []
            violation['kick'].append({
              "reason": row['reason'],
              "mod": f"{self.bot.get_user(int(row['mod_id'])).name if self.bot.get_user(int(row['mod_id'])) else 'Not Found'}({row['mod_id']})",
              "timestamp": datetime.fromtimestamp(row['timestamp']).strftime('%d.%m.%y %H:%M:%S')
            })
          elif row['type']=="ban":
            if 'ban' not in violation:
              violation['ban'] = []
            violation['ban'].append({
              "reason": row['reason'],
              "mod": f"{self.bot.get_user(int(row['mod_id'])).name if self.bot.get_user(int(row['mod_id'])) else 'Not Found'}({row['mod_id']})",
              "timestamp": datetime.fromtimestamp(row['timestamp']).strftime('%d.%m.%y %H:%M:%S'),
              "duration": timedelta(seconds=row['duration']) if row['duration'] else '∞'
            })
          elif row['type']=="unwarn":
            if 'unwarn' not in violation:
              violation['unwarn'] = []
            violation['unwarn'].append({
              "reason": row['reason'],
              "mod": f"{self.bot.get_user(int(row['mod_id'])).name if self.bot.get_user(int(row['mod_id'])) else 'Not Found'}({row['mod_id']})",
              "timestamp": datetime.fromtimestamp(row['timestamp']).strftime('%d.%m.%y %H:%M:%S')
            })
          elif row['type']=="unmute":
            if 'unmute' not in violation:
              violation['unmute'] = []
            violation['unmute'].append({
              "reason": row['reason'],
              "mod": f"{self.bot.get_user(int(row['mod_id'])).name if self.bot.get_user(int(row['mod_id'])) else 'Not Found'}({row['mod_id']})",
              "timestamp": datetime.fromtimestamp(row['timestamp']).strftime('%d.%m.%y %H:%M:%S'),
            })
          elif row['type']=="unban":
            if 'unban' not in violation:
              violation['unban'] = []
            violation['unban'].append({
              "reason": row['reason'],
              "mod": f"{self.bot.get_user(int(row['mod_id'])).name if self.bot.get_user(int(row['mod_id'])) else 'Not Found'}({row['mod_id']})",
              "timestamp": datetime.fromtimestamp(row['timestamp']).strftime('%d.%m.%y %H:%M:%S'),
            })
          else:
            if row['type'] not in violation:
              violation[row['type']] = []
            violation[row['type']].append({
              "reason": row['reason'],
              "mod": f"{self.bot.get_user(int(row['mod_id'])).name if self.bot.get_user(int(row['mod_id'])) else 'Not Found'}({row['mod_id']})",
              "timestamp": datetime.fromtimestamp(row['timestamp']).strftime('%d.%m.%y %H:%M:%S'),
            })

      sbank_balance = await suffics(number=bank_balance, variation=variation)
      sbalance = await suffics(number=balance, variation=variation)
      stotal_balance = await suffics(number=bank_balance+balance, variation=variation)
        
      headers = {
        "Authorization": getenv("TOPGG_DISCORDBOT_TOKEN_API"),
        'Content-Type': 'application/json'
      }
      async with ClientSession() as session:
        async with session.get(f"https://top.gg/api/bots/{self.bot.user.id}/check?userId={member_id if member_id else user_id}", headers=headers) as resp:
          if resp.status == 200:
            data = await resp.json()
            vote = data.get("voted") == 1
          else:
            vote = False

      async def update_callback(tipe:str=None):
        async with ClientSession() as session:
          async with session.get(getattr(пользователь, 'display_avatar', interaction.user.display_avatar).url) as response:
            image_data = await response.read()
        avatar = Image.open(BytesIO(image_data))
        file = None
        if tipe=="server":
          if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
            async with self.bot.db_pool.acquire() as conn:
              messages:int = await conn.fetchval("SELECT COUNT(*) FROM messages where user_id = $1 and guild_id = $2",member_id if member_id else user_id, interaction.guild.id if interaction.guild else 0)
              voicequery = f"SELECT COALESCE(SUM(time_spent), '0 seconds'::interval) AS total_time FROM voice WHERE user_id = $1 and guild_id = $2"
              voice = await conn.fetchrow(voicequery,member_id if member_id else user_id, interaction.guild.id if interaction.guild else 0)
          else:
            await send_bank_message.edit('postgresql not loaded in profile')
            return

          voice: timedelta = voice['total_time']

          img = await self._draw_user_profile(
            type_=tipe,
            real_username=interaction.user.name,
            status=getattr((find(lambda member:member==пользователь if member_id else interaction.user,(member for guild in self.bot.guilds for member in guild.members))or interaction.user),'status','offline'),
            language=language,
            bot=self.bot,
            username=getattr(пользователь, 'name', interaction.user.name),
            display_name=getattr(пользователь, 'display_name', interaction.user.display_name),
            avatar=avatar,
            badges=badges,
            member_in_guild=interaction.guild.get_member(member_id if member_id else user_id) if interaction.guild else False,
            voted=vote,
            reg_data=datetime.fromtimestamp(reg_data).strftime('%d.%m.%y'),
            xp=xp,
            messages=messages,
            voice=f"{voice.days}d {voice.seconds // 3600}h {(voice.seconds % 3600) // 60}m",
          )
          buffer = BytesIO()
          img.save(buffer, format="png")
          buffer.seek(0)
          file = File(buffer, filename="image.png")
        elif tipe=="discord":
          if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
            async with self.bot.db_pool.acquire() as conn:
              messages:int = await conn.fetchval("SELECT COUNT(*) FROM messages where user_id = $1",member_id if member_id else user_id)
              voicequery = f"SELECT COALESCE(SUM(time_spent), '0 seconds'::interval) AS total_time FROM voice WHERE user_id = $1"
              voice = await conn.fetchrow(voicequery,member_id if member_id else user_id)
          else:
            await send_bank_message.edit('postgresql not loaded in profile')
            return

          voice: timedelta = voice['total_time']
          
          img = await self._draw_user_profile(
            type_=tipe,
            real_username=interaction.user.name,
            status=getattr((find(lambda member:member==пользователь if member_id else interaction.user,(member for guild in self.bot.guilds for member in guild.members))or interaction.user),'status','offline'),
            language=language,
            bot=self.bot,
            username=getattr(пользователь, 'name', interaction.user.name),
            display_name=getattr(пользователь, 'display_name', interaction.user.display_name),
            avatar=avatar,
            badges=badges,
            member_in_guild=interaction.guild.get_member(member_id if member_id else user_id) if interaction.guild else False,
            voted=vote,
            reg_data=datetime.fromtimestamp(reg_data).strftime('%d.%m.%y'),
            xp=xp,
            messages=messages,
            voice=f"{voice.days}d {voice.seconds // 3600}h {(voice.seconds % 3600) // 60}m",
          )
          buffer = BytesIO()
          img.save(buffer, format="png")
          buffer.seek(0)
          file = File(buffer, filename="image.png")
        elif tipe=="economy":
          img = await self._draw_user_profile(
            type_=tipe,
            real_username=interaction.user.name,
            status=getattr((find(lambda member:member==пользователь if member_id else interaction.user,(member for guild in self.bot.guilds for member in guild.members))or interaction.user),'status','offline'),
            language=language,
            bot=self.bot,
            username=getattr(пользователь, 'name', interaction.user.name),
            display_name=getattr(пользователь, 'display_name', interaction.user.display_name),
            avatar=avatar,
            badges=badges,
            member_in_guild=interaction.guild.get_member(member_id if member_id else user_id) if interaction.guild else False,
            voted=vote,
            xp=xp,
            total_balance=stotal_balance,
            bank_balance=sbank_balance,
            balance=sbalance,
            upgrade=upgrade,
            x2workamount=x2workamount,
            x2buyamount=x2buyamount
          )
          buffer = BytesIO()
          img.save(buffer, format="png")
          buffer.seek(0)
          file = File(buffer, filename="image.png")
        elif tipe=="moderation":
          img = await self._draw_user_profile(
            type_=tipe,
            real_username=interaction.user.name,
            status=getattr((find(lambda member:member==пользователь if member_id else interaction.user,(member for guild in self.bot.guilds for member in guild.members))or interaction.user),'status','offline'),
            language=language,
            bot=self.bot,
            username=getattr(пользователь, 'name', interaction.user.name),
            display_name=getattr(пользователь, 'display_name', interaction.user.display_name),
            avatar=avatar,
            badges=badges,
            member_in_guild=interaction.guild.get_member(member_id if member_id else user_id) if interaction.guild else False,
            voted=vote,
            xp=xp,
            violation=deepcopy(violation) if violation else {}
          )
          buffer = BytesIO()
          img.save(buffer, format="png")
          buffer.seek(0)
          file = File(buffer, filename="image.png")
        elif tipe=='cooldowns':
          cooldowns={
            "Work": {
              "in":str(timedelta(seconds=max(0,(worka+60*39)-time()))).split('.')[0],
              "used":format_datetime(datetime.fromtimestamp(worka), "d MMMM, HH:mm:ss", locale=language)
            },
            "Rob": {
              "in":str(timedelta(seconds=max(0,(rob+60*60*6)-time()))).split('.')[0],
              "used":format_datetime(datetime.fromtimestamp(rob), "d MMMM, HH:mm:ss", locale=language)
            },
            "Вставить Дату": {
              "in":str(timedelta(seconds=max(0,(insert_data+31*24*60*60)-time()))).split('.')[0],
              "used":format_datetime(datetime.fromtimestamp(insert_data), "d MMMM, HH:mm:ss", locale=language)
            }
          }

          img = await self._draw_user_profile(
            type_=tipe,
            real_username=interaction.user.name,
            status=getattr((find(lambda member:member==пользователь if member_id else interaction.user,(member for guild in self.bot.guilds for member in guild.members))or interaction.user),'status','offline'),
            language=language,
            bot=self.bot,
            username=getattr(пользователь, 'name', interaction.user.name),
            display_name=getattr(пользователь, 'display_name', interaction.user.display_name),
            avatar=avatar,
            badges=badges,
            member_in_guild=interaction.guild.get_member(member_id if member_id else user_id) if interaction.guild else False,
            voted=vote,
            xp=xp,
            cooldowns=cooldowns
          )
          buffer = BytesIO()
          img.save(buffer, format="png")
          buffer.seek(0)
          file = File(buffer, filename="image.png")
        elif tipe=='other':
          file=None
        if file:
          try:
            await send_bank_message.edit("",file=file)
          except Exception:
            await interaction.followup.send("",file=file,ephemeral=True)
        else:
          try:
            await send_bank_message.edit("Еще Не Обновил С Эмбеда На Картинки")
          except Exception:
            await interaction.followup.send("Еще Не Обновил С Эмбеда На Картинки",ephemeral=True)
            
      view = привязать_телеграм(interaction.user.id, language, update_callback, vote, self.bot)
      try:
        await send_bank_message.edit(translate_to_all_languages("Второй Этап Загрузки Данных.", 'message', language),view=view)
      except Exception:
        await interaction.followup.send(translate_to_all_languages("Второй Этап Загрузки Данных.", 'message', language),ephemeral=True,view=view)
      await update_callback("discord")

    except Exception as e:
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"Пользователь Вписал Команду: ||**/профиль**  `пользователь`  **{пользователь}**||",
        color=Color.red(),
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
      await interaction.followup.send(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)

  setattr(профиль,"extras",{"description": "Показывает **Абсолютно** всю информацию о пользователе которую он *не скрывает*."},)

def setup(bot: commands.Bot):
  bot.add_cog(Profile(bot))