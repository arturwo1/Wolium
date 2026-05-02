import random
from datetime import datetime, timedelta, timezone
from time import time
from nextcord.ext import commands
from nextcord.ui import View, Button, button
from nextcord import slash_command, IntegrationType, InteractionContextType, Interaction, SlashOption, ButtonStyle, Embed, Colour
from Utils.holiday_type_choose import holiday_type_choose
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class HolidayPagination(View):
  def __init__(self, interaction_user_id, max_page, get_page_embed_coro, timeout=5*60):
    super().__init__(timeout=timeout)
    self.interaction_user_id = interaction_user_id
    self.page = 0
    self.max_page = max_page
    self.get_page_embed_coro = get_page_embed_coro
    self.update_buttons()

  def update_buttons(self):
    self.children[0].disabled = (self.page == 0)
    self.children[1].disabled = (self.page == self.max_page)

  @button(label="◀", style=ButtonStyle.primary)
  async def prev_button(self, button: Button, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    self.page -= 1
    if self.page < 0: self.page = 0
    if self.page > self.max_page: self.page = self.max_page

    self.update_buttons()
    embed = await self.get_page_embed_coro(self.page)
    await interaction.edit_original_message(embed=embed, view=self)

  @button(label="▶", style=ButtonStyle.primary)
  async def next_button(self, button: Button, interaction: Interaction):
    if interaction.response.is_done():
      return
    await interaction.response.defer()

    self.page += 1
    if self.page < 0: self.page = 0
    if self.page > self.max_page: self.page = self.max_page
    
    self.update_buttons()
    embed = await self.get_page_embed_coro(self.page)
    await interaction.edit_original_message(embed=embed, view=self)

class Holiday(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot

  def get_discord_locale(self, locale: str) -> str:
    if locale in ("en-US", "en-GB"):
      return "en"
    if locale == "es-ES":
      return "es"
    if locale == "sv-SE":
      return "sv"
    return "en"

  @slash_command(
    name="праздник",
    description="Узнать Праздники Которые Бот Использует.",
    name_localizations=translate_to_all_languages('holiday.holiday_lower', 'name'),
    description_localizations=translate_to_all_languages('holiday.learn_used_holidays', 'description'),
    integration_types=[IntegrationType.user_install, IntegrationType.guild_install],
    contexts=[InteractionContextType.guild, InteractionContextType.bot_dm, InteractionContextType.private_channel],
  )
  async def holiday(
    self,
    interaction: Interaction,
    праздник: str = SlashOption(
      name="праздник", 
      description="Выбери Что Хочешь Узнать.",
      choices={"Current holiday": "current_holiday", "All holidays": "print_holidays"},
      required=True, 
      name_localizations=translate_to_all_languages('holiday.holiday_lower', 'name'), 
      description_localizations=translate_to_all_languages('general.choose_info', 'description'), 
      choice_localizations=translate_to_all_languages({"праздник сегодня": "current_holiday", "все праздники": "print_holidays"}, 'choice')
    ),
    лично: bool = SlashOption(
      name="лично", 
      description="Только Ты Увидишь Сообщение, Или Все.",
      required=False,
      default=False, 
      name_localizations=translate_to_all_languages('general.personally', 'name'), 
      description_localizations=translate_to_all_languages('general.ephemeral_desc', 'description')
    )
  ):
    user_id = interaction.user.id
    current_time = time()
    tm = self.bot.get_cog("TranslateMessage")

    if user_id in slash_command_cooldown:
      last_command_time = slash_command_cooldown[user_id]['time']
      if current_time - last_command_time < 10:
        locale = self.get_discord_locale(interaction.locale)
        msg1 = await tm.translate_message("error.rate_limit_part1", locale)
        msg2 = await tm.translate_message("error.rate_limit_part2", locale)
        
        await interaction.response.send_message(f"{msg1} **<t:{round(last_command_time + 10)}:R>** {msg2}", ephemeral=True)
        return
      else:
        slash_command_cooldown[user_id]['time'] = current_time
    else:
      slash_command_cooldown[user_id] = {'time': current_time}

    await interaction.response.defer(ephemeral=лично if interaction.guild else True)

    user_settings = await self.bot.get_cog("GetData").get_data(user_id, ['language', 'variation'], 'users', 'user_id', interaction.guild)
    language = user_settings['language']

    if праздник == "current_holiday":
      current_holiday = holiday_type_choose("current_holiday")
      
      if current_holiday:
        season = current_holiday['season']
        colors_map = {
          "весна": Colour.from_rgb(0, 255, 0),
          "лето": Colour.from_rgb(255, 255, 0),
          "осень": Colour.from_rgb(255, 128, 0),
          "зима": Colour.from_rgb(0, 255, 255)
        }
        embed_color = colors_map.get(season, Colour.blurple())

        t_season_title = await tm.translate_message('holiday.season_label', language)
        t_season_val = await tm.translate_message(season, language)
        t_name_title = await tm.translate_message('holiday.name', language)
        t_name_val = await tm.translate_message(current_holiday['name'], language)

        holiday_embed = Embed(
          title=f"{t_season_title} {t_season_val}",
          description=f"{t_name_title} **`{t_name_val}`**",
          color=embed_color,
          timestamp=datetime.now(timezone.utc)
        )
        holiday_embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        
        val_start = f"{await tm.translate_message('holiday.start_at', language)} {current_holiday['start_date']}"
        val_end = f"{await tm.translate_message('holiday.end_at', language)} {current_holiday['end_date']}"
        val_dur = f"{await tm.translate_message('holiday.duration', language)} {current_holiday['duration']} {await tm.translate_message('time.days', language)}"
        
        holiday_embed.add_field(
          name=await tm.translate_message("holiday.time", language),
          value=f"{val_start}\n{val_end}\n{val_dur}",
          inline=False
        )
        holiday_embed.set_footer(
          text=datetime.now().strftime("%Y-%m-%d %H:%M"), 
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )
        
        await interaction.followup.send(embed=holiday_embed, ephemeral=лично)
      else:
        await interaction.followup.send(await tm.translate_message("holiday.none_currently", language), ephemeral=лично)

    elif праздник == "print_holidays":
      holidaysers = sorted(holiday_type_choose("print_holidays"), key=lambda x: datetime.strptime(x[1], '%d.%m.%Y'))
      if not holidaysers:
        await interaction.followup.send(await tm.translate_message("error.holidays_not_found", language), ephemeral=лично)
        return

      max_page = (len(holidaysers) - 1) // 5

      async def generate_page_embed(page: int) -> Embed:
        embed = Embed(
          title=await tm.translate_message("holiday.all_used", language),
          description=await tm.translate_message("holiday.suggest_new", language),
          color=random.choice([Colour.from_rgb(255, 0, 0), Colour.from_rgb(0, 255, 255), Colour.from_rgb(0, 0, 255)]),
          timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)

        start_index = page * 5
        end_index = min(start_index + 5, len(holidaysers))

        for name, start_date, end_date, duration, season in holidaysers[start_index:end_index]:
          start_date_obj = datetime.strptime(start_date, '%d.%m.%Y')
          end_date_obj = datetime.strptime(end_date, '%d.%m.%Y')
          remaining_time = start_date_obj - datetime.now()

          if remaining_time.total_seconds() <= 0:
            try:
              start_date_obj = start_date_obj.replace(year=datetime.now().year + 1)
              end_date_obj = end_date_obj.replace(year=datetime.now().year + 1)
            except ValueError:
              start_date_obj += timedelta(days=365)
              end_date_obj += timedelta(days=365)
              
            remaining_time = start_date_obj - datetime.now()
            
            start_date = start_date_obj.strftime('%d.%m.%Y')
            end_date = end_date_obj.strftime('%d.%m.%Y')
            
          remaining_time_str = str(remaining_time).split('.')[0]
          
          v_remain = f"{await tm.translate_message('holiday.time_until', language)} {remaining_time_str}"
          v_season = f"{await tm.translate_message('holiday.season', language)} {await tm.translate_message(season, language)}"
          v_start = f"{await tm.translate_message('holiday.start', language)} {start_date}"
          v_end = f"{await tm.translate_message('holiday.end', language)} {end_date}"
          v_dur = f"{await tm.translate_message('holiday.duration_label', language)} {duration} {await tm.translate_message('time.days', language)}"

          embed.add_field(
            name=await tm.translate_message(f"Название Праздника: {name}", language),
            value=f"{v_remain}\n{v_season}\n{v_start}\n{v_end}\n{v_dur}",
            inline=False
          )

        embed.set_footer(
          text=f"{await tm.translate_message('general.page', language)} {page + 1}/{max_page + 1}",
          icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
        )
        return embed

      view = HolidayPagination(interaction.user.id, max_page, generate_page_embed)
      first_embed = await generate_page_embed(0)
      await interaction.followup.send(embed=first_embed, view=view, ephemeral=лично)

  setattr(holiday, "extras", {"description": "commands.holiday.description"})

def setup(bot: commands.Bot):
  bot.add_cog(Holiday(bot))