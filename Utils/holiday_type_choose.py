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

def create_holidays(year:int):
  catholic_easter = catholic_easter_date(year)
  orthodox_easter = orthodox_easter_date(year)

  # catholic_easter_week = [catholic_easter + timedelta(days=i) for i in range(7)]
  # orthodox_easter_week = [orthodox_easter + timedelta(days=i) for i in range(7)]

  tc = datetime(year, 11, 1)
  while tc.weekday() != 3:
    tc += timedelta(days=1)
  tgd = (tc + timedelta(weeks=4)).day

  holidays:list[dict[str,datetime|str]] = [
    # Зима
    create_holiday(datetime(year, 12, 1), datetime(year, 12, 1), 'Всемирный день борьбы со СПИДом', 'зима'),  # 1 Декабря
    create_holiday(datetime(year, 12, 3), datetime(year, 12, 3), 'Международный день инвалидов', 'зима'),  # 3 Декабря
    create_holiday(datetime(year, 12, 10), datetime(year, 12, 10), 'День Рождения Wolium\'а', 'зима'),  # 10 Декабря
    create_holiday(datetime(year, 12, 21), datetime(year, 12, 22), 'Зимнее солнцестояние', 'зима'),  # 21-22 Декабря
    create_holiday(datetime(year, 12, 24), datetime(year, 12, 26), 'Рождество', 'зима'),  # 24-26 Декабря
    create_holiday(datetime(year, 12, 29), datetime(year, 12, 29), 'День Рождения создателя бота(arturwol\'a)', 'зима'),  # 29 Декабря
    create_holiday((datetime(year, 12, 31) if datetime.now().month!=1 else datetime(year-1, 12, 31)), (datetime(year+1, 1, 1) if datetime.now().month!=1 else datetime(year, 1, 1)), 'Новый Год', 'зима'),  # 31 Декабря - 1 Января
    create_holiday(datetime(year, 1, 13), datetime(year, 1, 13), 'Старый Новый Год и день защитников свободы Литвы', 'зима'),  # 13 Января
    create_holiday(datetime(year, 1, 21), datetime(year, 1, 24), 'Лунный Новый Год', 'зима'),  # 21-24 Января
    create_holiday(datetime(year, 2, 14), datetime(year, 2, 14), 'День святого Валентина', 'зима'),  # 14 Февраля
    create_holiday(datetime(year, 2, 16), datetime(year, 2, 16), 'День восстановления Литовского государства', 'зима'),  # 16 Февраля
    create_holiday(datetime(year, 2, 23), datetime(year, 2, 23), 'День защитника Отечества', 'зима'),  # 23 Февраля

    # Весна
    create_holiday(catholic_easter, catholic_easter + timedelta(days=6), 'Пасха (католическая)', 'весна'),  # Неделя Пасхи
    create_holiday(orthodox_easter, orthodox_easter + timedelta(days=6), 'Пасха (православная)', 'весна'),  # Неделя Пасхи
    create_holiday(datetime(year, 3, 8), datetime(year, 3, 8), 'Международный женский день', 'весна'),  # 8 Марта
    create_holiday(datetime(year, 3, 11), datetime(year, 3, 11), 'День восстановления независимости Литвы', 'весна'),  # 11 Марта
    create_holiday(datetime(year, 3, 17), datetime(year, 3, 17), 'День святого Патрика', 'весна'),  # 17 Марта
    create_holiday(datetime(year, 3, 20), datetime(year, 3, 20), 'Международный день счастья', 'весна'),  # 20 Марта
    create_holiday(datetime(year, 4, 1), datetime(year, 4, 1), 'День Дурака', 'весна'),  # 1 Апреля
    create_holiday(datetime(year, 4, 22), datetime(year, 4, 22), 'День Земли', 'весна'),  # 22 Апреля
    create_holiday(datetime(year, 5, 1), datetime(year, 5, 1), 'День Труда', 'весна'),  # 1 Мая
    create_holiday(datetime(year, 5, 8), datetime(year, 5, 8), 'День победы над нацизмом', 'весна'),  # 8 Мая
    create_holiday(datetime(year, 5, 8), datetime(year, 5, 9), 'День Победы', 'весна'),  # 8-9 Мая
    create_holiday(datetime(year, 5, 15), datetime(year, 5, 15), 'День семьи', 'весна'),  # 15 Мая

    # Лето
    create_holiday(datetime(year, 6, 1), datetime(year, 6, 1), 'День королевы и Международный день защиты детей', 'лето'),  # 1 Июня
    create_holiday(datetime(year, 6, 5), datetime(year, 6, 5), 'День охраны окружающей среды', 'лето'),  # 5 Июня
    create_holiday(datetime(year, 6, 12), datetime(year, 6, 12), 'День России', 'лето'),  # 12 Июня
    create_holiday(datetime(year, 6, 16), datetime(year, 6, 16), 'День отца', 'лето'),  # 16 Июня
    create_holiday(datetime(year, 6, 21), datetime(year, 6, 22), 'Летнее солцестояние', 'лето'),  # 21-22 Июня
    create_holiday(datetime(year, 6, 29), datetime(year, 6, 29), 'Праздник Петра и Павла', 'лето'),  # 29 Июня
    create_holiday(datetime(year, 7, 1), datetime(year, 7, 4), 'День независимости США', 'лето'),  # 1-4 Июля
    create_holiday(datetime(year, 7, 6), datetime(year, 7, 6), 'День независимости Литвы', 'лето'),  # 6 Июля
    create_holiday(datetime(year, 7, 30), datetime(year, 7, 30), 'Международный день дружбы', 'лето'),  # 30 Июля
    create_holiday(datetime(year, 8, 7), datetime(year, 8, 7), 'День борьбы с терроризмом', 'лето'),  # 7 Августа
    create_holiday(datetime(year, 8, 12), datetime(year, 8, 12), 'Международный день молодёжи', 'лето'),  # 12 Августа
    create_holiday(datetime(year, 8, 15), datetime(year, 8, 15), 'Успение Пресвятой Богородицы', 'лето'),  # 15 Августа

    # Осень
    create_holiday(datetime(year, 9, 1), datetime(year, 9, 1), 'День знаний', 'осень'),  # 1 Сентября
    create_holiday(datetime(year, 10, 21), datetime(year, 10, 21), 'День Литовской культуры и языка', 'осень'),  # 21 Октября
    create_holiday(datetime(year, 10, 31), datetime(year, 11, 1), 'Хеллоуин', 'осень'),  # 31 Октября - 1 Ноября
    create_holiday(datetime(year, 10, 24), datetime(year, 10, 24), 'День наций', 'осень'),  # 24 Октября
    create_holiday(datetime(year, 11, 1), datetime(year, 11, 2), 'День всех святых', 'осень'),  # 1-2 Ноября
    create_holiday(datetime(year, 11, 11), datetime(year, 11, 11), 'День памяти', 'осень'),  # 11 Ноября
    create_holiday(datetime(year, 11, 20), datetime(year, 11, 20), 'Всемирный день ребёнка', 'осень'),  # 20 Ноября
    create_holiday(datetime(year, 11, tgd), datetime(year, 11, tgd), 'День Благодарения', 'осень'),  # четертвый четверг Ноября
  ]

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