from random import randint
def random_color():
  return f"\033[{randint(30,37)};{randint(40,47) if randint(1,2)==1 else randint(90,97)};{randint(0,9)}m\033[5m"