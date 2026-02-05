from Utils.random_color import random_color
def lazylightshow(text: str):
  result=""
  for i in range(0, len(text), 3):
    chunk = text[i:i + 3]
    result += chunk
    result+=random_color()
  return result