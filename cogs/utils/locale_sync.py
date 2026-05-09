import logging
from nextcord.ext import commands, tasks
from json import load, dump, loads, JSONDecodeError
from subprocess import run
from pathlib import Path
from asyncio import Lock, to_thread

log = logging.getLogger("LocaleSync")

LOCALES_DIR = Path("locales")
CACHE_FILE = LOCALES_DIR / ".sync_cache.json"
BASE_LANG = "en"
json_lock = Lock()

def load_json(path):
  if not path.exists():
    return {}
  try:
    with open(path, "r", encoding="utf-8") as f:
      return load(f)
  except JSONDecodeError as e:
    log.error("Ошибка синтаксиса в %s: %s", path, e)
    return None

def save_json(path, data):
  with open(path, "w", encoding="utf-8") as f:
    dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

def get_git_baseline(rel_path):
  try:
    git_path = (LOCALES_DIR / rel_path).as_posix()
    result = run(
      ["git", "show", f"HEAD:{git_path}"],
      capture_output=True,
      check=True
    )
    return loads(result.stdout.decode("utf-8"))
  except Exception as e:
    log.debug("Не удалось получить git baseline для %s: %s", rel_path, e)
    return None

class LocaleSync(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.sync.start()

  def cog_unload(self):
    self.sync.cancel()

  def main(self):
    full_cache = load_json(CACHE_FILE) or {}
    new_cache = {}
    
    for en_file in LOCALES_DIR.rglob(f"{BASE_LANG}.json"):
      current_dir = en_file.parent
      rel_path = str(en_file.relative_to(LOCALES_DIR))
      
      current_en = load_json(en_file)
      
      if current_en is None:
        log.warning("Пропуск синхронизации для %s из-за ошибки чтения базового файла.", current_dir.name)
        if rel_path in full_cache:
          new_cache[rel_path] = full_cache[rel_path]
        continue
      
      previous_en = full_cache.get(rel_path)
      if previous_en is None:
        previous_en = get_git_baseline(rel_path)
      
      if previous_en is None:
        new_cache[rel_path] = current_en
        continue

      new_cache[rel_path] = current_en

      added = current_en.keys() - previous_en.keys()
      removed = previous_en.keys() - current_en.keys()
      changed = {
        key for key in current_en.keys() & previous_en.keys()
        if current_en[key] != previous_en[key]
      }

      if not added and not removed and not changed:
        continue

      affected = added | changed

      for lang_file in current_dir.glob("*.json"):
        if lang_file.stem == BASE_LANG or lang_file.name.startswith('.'):
          continue

        lang_data = load_json(lang_file)
        if lang_data is None:
          continue

        needs_save = False

        for key in removed:
          if key in lang_data:
            lang_data.pop(key)
            needs_save = True

        for key in affected:
          if key not in lang_data:
            lang_data[key] = ""
            needs_save = True

        if needs_save:
          save_json(lang_file, lang_data)
          log.info("Обновлен языковой файл: %s", lang_file.relative_to(LOCALES_DIR))

    save_json(CACHE_FILE, new_cache)

  @tasks.loop(minutes=5)
  async def sync(self):
    async with json_lock:
      await to_thread(self.main)

  @sync.before_loop
  async def before_sync(self):
    await self.bot.wait_until_ready()

def setup(bot: commands.Bot):
  bot.add_cog(LocaleSync(bot))