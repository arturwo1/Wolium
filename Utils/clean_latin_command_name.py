from re import sub
from unidecode import unidecode
def clean_latin_command_name(name: str):
  return sub(r'[^a-zA-Z0-9_]', '', unidecode(name).replace(' ', '_')).lower()[:32]