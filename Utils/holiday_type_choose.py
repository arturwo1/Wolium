from datetime import datetime, timedelta

year:int = datetime.now().year

def create_holiday(start_date:datetime, end_date:datetime, name:str, season:str)->dict[str,datetime|str]:
  return {
    'start_date': start_date,
    'end_date': end_date,
    'name': name,
    'duration': (end_date - start_date).days + 1,
    'season': season
  }

def catholic_easter_date(year:int):
  a = year % 19
  b = year // 100
  c = year % 100
  d = b // 4
  e = b % 4
  f = (b + 8) // 25
  g = (b - f + 1) // 3
  h = (19 * a + b - d - g + 15) % 30
  i = c // 4
  k = c % 4
  l = (32 + 2 * e + 2 * i - h - k) % 7
  m = (a + 11 * h + 22 * l) // 451
  month = (h + l - 7 * m + 114) // 31
  day = ((h + l - 7 * m + 114) % 31) + 1
  return datetime(year, month, day)

def orthodox_easter_date(year:int):
  a = year % 19
  b = year // 100
  c = year % 100
  d = b // 4
  e = b % 4
  g = (8 * b + 13) // 25
  h = (19 * a + b - d - g + 15) % 30
  i = c // 4
  k = c % 4
  m = (a + 11 * h) // 319
  month = (h + m - 7 * (a + 11 * h + 22 * m) % 30 + 114) // 31
  day = ((h + m - 7 * (a + 11 * h + 22 * m) % 30 + 114) % 31) + 1
  return datetime(year, month, day)

def h(key: str, start: datetime, end: datetime, season: str)->list[dict[str,datetime|str]]:
  return [create_holiday(start, end, key, season)]

def create_holidays(year: int)->list[dict[str,datetime|str]]:
  catholic_easter = catholic_easter_date(year)
  orthodox_easter = orthodox_easter_date(year)

  tc = datetime(year, 11, 1)
  while tc.weekday() != 3:
    tc += timedelta(days=1)
  tgd = (tc + timedelta(weeks=4)).day

  holidays = []

  # Winter
  holidays += h("world_aids_day", datetime(year, 12, 1), datetime(year, 12, 1), "winter")
  holidays += h("international_day_of_persons_with_disabilities", datetime(year, 12, 3), datetime(year, 12, 3), "winter")
  holidays += h("wolium_birthday", datetime(year, 12, 10), datetime(year, 12, 10), "winter")
  holidays += h("winter_solstice", datetime(year, 12, 21), datetime(year, 12, 22), "winter")
  holidays += h("christmas", datetime(year, 12, 24), datetime(year, 12, 26), "winter")
  holidays += h("bot_creator_birthday", datetime(year, 12, 29), datetime(year, 12, 29), "winter")
  holidays += h("new_year", datetime(year, 12, 31), datetime(year + 1, 1, 1), "winter")
  holidays += h("old_new_year", datetime(year, 1, 13), datetime(year, 1, 13), "winter")
  holidays += h("lunar_new_year", datetime(year, 1, 21), datetime(year, 1, 24), "winter")
  holidays += h("valentines_day", datetime(year, 2, 14), datetime(year, 2, 14), "winter")
  holidays += h("restoration_of_lithuanian_state", datetime(year, 2, 16), datetime(year, 2, 16), "winter")
  holidays += h("defender_of_fatherland_day", datetime(year, 2, 23), datetime(year, 2, 23), "winter")

  # Spring
  holidays += h("catholic_easter_week", catholic_easter, catholic_easter + timedelta(days=6), "spring")
  holidays += h("orthodox_easter_week", orthodox_easter, orthodox_easter + timedelta(days=6), "spring")
  holidays += h("international_womens_day", datetime(year, 3, 8), datetime(year, 3, 8), "spring")
  holidays += h("lithuanian_independence_day", datetime(year, 3, 11), datetime(year, 3, 11), "spring")
  holidays += h("st_patricks_day", datetime(year, 3, 17), datetime(year, 3, 17), "spring")
  holidays += h("international_day_of_happiness", datetime(year, 3, 20), datetime(year, 3, 20), "spring")
  holidays += h("april_fools_day", datetime(year, 4, 1), datetime(year, 4, 1), "spring")
  holidays += h("earth_day", datetime(year, 4, 22), datetime(year, 4, 22), "spring")
  holidays += h("labour_day", datetime(year, 5, 1), datetime(year, 5, 1), "spring")
  holidays += h("victory_over_nazism_day", datetime(year, 5, 8), datetime(year, 5, 8), "spring")
  holidays += h("victory_day", datetime(year, 5, 8), datetime(year, 5, 9), "spring")
  holidays += h("family_day", datetime(year, 5, 15), datetime(year, 5, 15), "spring")

  # Summer
  holidays += h("childrens_day", datetime(year, 6, 1), datetime(year, 6, 1), "summer")
  holidays += h("environment_day", datetime(year, 6, 5), datetime(year, 6, 5), "summer")
  holidays += h("russia_day", datetime(year, 6, 12), datetime(year, 6, 12), "summer")
  holidays += h("fathers_day", datetime(year, 6, 16), datetime(year, 6, 16), "summer")
  holidays += h("summer_solstice", datetime(year, 6, 21), datetime(year, 6, 22), "summer")
  holidays += h("st_peter_and_paul_day", datetime(year, 6, 29), datetime(year, 6, 29), "summer")
  holidays += h("us_independence_day", datetime(year, 7, 1), datetime(year, 7, 4), "summer")
  holidays += h("lithuania_state_day", datetime(year, 7, 6), datetime(year, 7, 6), "summer")
  holidays += h("friendship_day", datetime(year, 7, 30), datetime(year, 7, 30), "summer")
  holidays += h("anti_terrorism_day", datetime(year, 8, 7), datetime(year, 8, 7), "summer")
  holidays += h("international_youth_day", datetime(year, 8, 12), datetime(year, 8, 12), "summer")
  holidays += h("assumption_of_mary", datetime(year, 8, 15), datetime(year, 8, 15), "summer")

  # Autumn
  holidays += h("knowledge_day", datetime(year, 9, 1), datetime(year, 9, 1), "autumn")
  holidays += h("lithuanian_language_day", datetime(year, 10, 21), datetime(year, 10, 21), "autumn")
  holidays += h("halloween", datetime(year, 10, 31), datetime(year, 11, 1), "autumn")
  holidays += h("nations_day", datetime(year, 10, 24), datetime(year, 10, 24), "autumn")
  holidays += h("all_saints_day", datetime(year, 11, 1), datetime(year, 11, 2), "autumn")
  holidays += h("remembrance_day", datetime(year, 11, 11), datetime(year, 11, 11), "autumn")
  holidays += h("world_childrens_day", datetime(year, 11, 20), datetime(year, 11, 20), "autumn")
  holidays += h("thanksgiving_day", datetime(year, 11, tgd), datetime(year, 11, tgd), "autumn")

  return holidays
holidays:list[dict[str,datetime|str]] = create_holidays(year)

def holiday_type_choose(type_of_holiday:str):
  def print_holidays(holidays:list[dict[str,datetime|str]]):
    holiday1s = []

    def hghd():
      for holiday in holidays:
        holiday1 = [
          holiday['name'],
          holiday['start_date'].strftime('%d.%m.%Y'),
          holiday['end_date'].strftime('%d.%m.%Y'),
          holiday['duration'],
          holiday['season']
        ]
        holiday1s.append(holiday1)
      return holiday1s[:25]

    return hghd()

  def current_holiday(holidays:list[dict[str,datetime|str]]):
    today = datetime.now().date()
    for holiday in holidays:
      if holiday['start_date'].date() <= today <= holiday['end_date'].date():
        return holiday
    return None

  if type_of_holiday == "print_holidays":
    return print_holidays(holidays)
  elif type_of_holiday == "current_holiday":
    return current_holiday(holidays)