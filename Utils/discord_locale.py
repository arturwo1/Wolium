locales = {
  'en': ['en-US', 'en-GB'],
  'es': ['es-ES'],
  'sv': ['sv-SE'],
}

def locale(locale:str) -> str:
  if not locale:
    return 'en'
  
  for name, value in locales.items():
    for loc in value:
      if locale==loc:
        return name

  return locale.split('-', 1)[0]