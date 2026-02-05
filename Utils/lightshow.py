from Utils.random_color import random_color
def lightshow(text: str):
  result=""
  for char in text:
    result+=char
    result+=random_color()
  return result