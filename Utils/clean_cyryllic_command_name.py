from re import sub
def clean_cyryllic_command_name(name: str):
  return sub(r'[^а-яА-ЯёЁ0-9_]', '', (name.translate(str.maketrans({
    ' ': '_',
    'Ґ': 'Г',
    'Є': 'Э',
    'Ї': 'Йи',
    'Ґ': 'Г',
    'є': 'э',
    'ї': 'йи',
    'Ѝ': 'И',
    'Ї': 'Йи',
    'ѝ': 'и',
    'ї': 'йи',
  })))).lower()[:32]
