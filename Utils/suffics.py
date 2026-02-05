async def suffics(number, variation):
  #print("Проверка: number =", number)
  #print("Проверка: variation =", variation)

  if variation == "scientific":
    result = '{:e}'.format(number)
    #print("Проверка: результат =", result)
    return result

  elif variation == "normal":
    suffixes = ['', 'K', 'M', 'B', 'T', 'Qa', 'Qi', 'Sx', 'Sp', 'Oс', 'No', 'Dc']
    magnitude = 0
    while number >= 1000:
      number /= 1000.0
      magnitude += 1
    result = '{:.2f}{}'.format(number, suffixes[magnitude])
    #print("Проверка: результат =", result)
    return result

  else:
    number = round(number, 2)
    #print("Проверка: результат =", number)
    return number