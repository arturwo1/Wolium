from asyncio import Lock, to_thread, sleep
from datetime import datetime, timedelta, timezone
from json import load, dump
from os import getenv, getpid, replace, getcwd, path, walk
from random import randint
from traceback import format_exception, print_exc
from nextcord import Embed, Colour, Message
from nextcord.ext import commands, tasks
from nextcord.errors import HTTPException, Forbidden, NotFound, DiscordServerError
from aiohttp import ClientSession
from cpuinfo import get_cpu_info
from dotenv import load_dotenv
from psutil import (
  cpu_count as psutil_cpu_count,
  cpu_percent,
  cpu_freq,
  virtual_memory,
  swap_memory,
  net_io_counters,
  disk_usage,
  Process,
)
from main import time_when_bot_run_firts
from Utils.suffics import suffics
from Utils.config import PC_times_updated as PC_times_updated_initial
load_dotenv()

json_lock: Lock = Lock()

def clip(s: str, limit: int) -> str:
  s = s or ""
  if len(s) <= limit:
    return s
  return s[: max(0, limit - 3)] + "..."

def fmt_c(x: float) -> str:   return f"{x:.2f}°C"
def fmt_pct(x: float) -> str: return f"{x:.2f}%"
def fmt_mhz(x: float) -> str: return f"{x:.0f}MHz"

async def _dir_disk_usage_async(dir_path: str) -> int:
  def _walk() -> int:
    total = 0
    for dirpath, _, filenames in walk(dir_path):
      for filename in filenames:
        fp = path.join(dirpath, filename)
        if path.isfile(fp):
          try:
            total += path.getsize(fp)
          except OSError:
            pass
    return total
  return await to_thread(_walk)

cpu_info = get_cpu_info()
cpu_model: str = cpu_info.get("brand_raw", "Unknown CPU")
cpu_cores_str = f"{psutil_cpu_count(logical=False)}`/`{psutil_cpu_count(logical=True)}"

proc = Process(getpid())
proc.cpu_percent(interval=None)

start_updating_time: datetime = datetime.now()
end_updating_time: datetime = datetime.now()
PC_times_updated: int = PC_times_updated_initial

class UpdatePCInfo(commands.Cog):
  GUILD_ID: int = 807304463449849938
  STATUS_CHANNEL_ID: int = 1163483706137247887
  STATUS_MESSAGE_ID: int = 1163484167682658324
  LOG_CHANNEL_ID: int = 1159138280651104256

  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    self.session: ClientSession|None = None

    self.prev_net = net_io_counters()
    self.prev_time = datetime.now()
    self.prev_proc_io = proc.io_counters()

    self.update_PC_info.start()

  def cog_unload(self) -> None:
    self.update_PC_info.cancel()
    if self.session and not self.session.closed:
      self.bot.loop.create_task(self.session.close())

  async def _get_session(self) -> ClientSession:
    if self.session is None or self.session.closed:
      self.session = ClientSession()
    return self.session

  async def _fetch_topgg_votes(self) -> tuple[int, int]:
    token = getenv("TOPGG_DISCORDBOT_TOKEN_API")
    if not token or not self.bot.user:
      return 0, 0
    url = f"https://top.gg/api/bots/{self.bot.user.id}"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    try:
      session = await self._get_session()
      async with session.get(url, headers=headers, timeout=5) as resp:
        if resp.status == 200:
          data = await resp.json()
          return int(data.get("points", 0) or 0), int(data.get("monthlyPoints", 0) or 0)
        return 0, 0
    except Exception:
      return 0, 0

  async def _send_error_embed(self, title: str, description: str, exc: Exception) -> None:
    traceback_msg = "".join(format_exception(type(exc), exc, exc.__traceback__))
    embed = Embed(title=title, description=description, color=Colour.red(), timestamp=datetime.now(timezone.utc))
    embed.set_author(name="ЕРРОР")
    for i in range(0, len(traceback_msg), 1000):
      embed.add_field(name="Ошибка", value=f"```py\n{traceback_msg[i:i+1000]}```", inline=False)

    guild = self.bot.get_guild(self.GUILD_ID)
    if not guild:
      return
    log_chan = guild.get_channel(self.LOG_CHANNEL_ID)
    if log_chan:
      await log_chan.send(embed=embed)

  async def _load_bot_data(self, raw_description: str) -> dict[str, int]:
    try:
      async with json_lock:
        with open("bot_data.json", "r", encoding="utf-8") as f:
          data = load(f)
      return {
        "total_times_updated": int(data.get("total_times_updated", 0) or 0),
        "best_times_updated": int(data.get("best_times_updated", 0) or 0),
        "best_time_ON": int(data.get("best_time_ON", 0) or 0),
        "total_time_ON": int(data.get("total_time_ON", 0) or 0),
      }
    except Exception:
      return {"total_times_updated": 0, "best_times_updated": 0, "best_time_ON": 0, "total_time_ON": 0}

  async def _get_used_users_in_db(self):
    try:
      async with self.bot.db_pool.acquire() as conn:
        val = await conn.fetchval("SELECT COUNT(DISTINCT user_id) FROM user_commands")
        return [{"amount":int(val or 0)}]
    except Exception:
      return [{"amount":0}]

  async def _get_economy_users_in_db(self):
    try:
      async with self.bot.db_pool.acquire() as conn:
        val = await conn.fetchval("SELECT COUNT(*) FROM user_data WHERE upgrade > 1")
        return [{"amount":int(val or 0)}]
    except Exception:
      return [{"amount":0}]

  async def _collect_net_block_psutil(self) -> str:
    net_now = net_io_counters()
    dt = max((datetime.now() - self.prev_time).total_seconds(), 1.0)

    bytes_sent_delta = net_now.bytes_sent - self.prev_net.bytes_sent
    bytes_recv_delta = net_now.bytes_recv - self.prev_net.bytes_recv
    packets_sent_delta = net_now.packets_sent - self.prev_net.packets_sent
    packets_recv_delta = net_now.packets_recv - self.prev_net.packets_recv
    errout_delta = net_now.errout - self.prev_net.errout
    errin_delta = net_now.errin - self.prev_net.errin
    dropin_delta = net_now.dropin - self.prev_net.dropin
    dropout_delta = net_now.dropout - self.prev_net.dropout

    total_packets = (
      f"`{await suffics(number=net_now.packets_sent, variation='normal')}`"
      f"**/**`{await suffics(number=net_now.packets_recv, variation='normal')}`"
    )
    packets_delta_str = (
      f"`{await suffics(number=packets_sent_delta, variation='normal')}`"
      f"**/**`{await suffics(number=packets_recv_delta, variation='normal')}`"
    )

    return (
      f"**ЗА ВСЕ ВРЕМЯ**\n"
      f"**Отд/Скч**: `{net_now.bytes_sent / (1024 ** 2):.2f}MB`**/**`{net_now.bytes_recv / (1024 ** 2):.2f}MB`\n"
      f"**Пакеты**: {total_packets}\n"
      f"**Ошибки**: `{net_now.errout}`**/**`{net_now.errin}` **|** **Дропы**: `{net_now.dropin}`**/**`{net_now.dropout}`\n\n"
      f"**ЗА {dt:.0f} СЕК**\n"
      f"**Отд/Скч**: `{bytes_sent_delta / (1024 ** 2):.2f}MB`**/**`{bytes_recv_delta / (1024 ** 2):.2f}MB`\n"
      f"**Пакеты**: {packets_delta_str}\n"
      f"**Ошибки**: `{errout_delta}`**/**`{errin_delta}` **|** **Дропы**: `{dropin_delta}`**/**`{dropout_delta}`"
    )

  async def _embed_overview(self, message_to_edit: Message) -> Embed:
    import Utils.config as cfg
    global PC_times_updated

    WM_times_updated = getattr(cfg, "WM_times_updated", 0)
    PGSQL_times_updated = getattr(cfg, "PGSQL_times_updated", 0)
    time_on_delta = datetime.now() - time_when_bot_run_firts

    raw_description = message_to_edit.embeds[0].description if message_to_edit.embeds else ""
    bot_data = await self._load_bot_data(raw_description)

    total_times_updated = bot_data["total_times_updated"]
    best_times_updated = bot_data["best_times_updated"]
    best_time_ON = bot_data["best_time_ON"]
    total_time_ON = bot_data["total_time_ON"]

    e = Embed(
      title=f"Обновление заняло {(start_updating_time - end_updating_time).total_seconds():.2f} сек",
      description=(
        f"### **Текущее**\n"
        f"PostgreSQL Забекапилась `{PGSQL_times_updated}` Раз\n"
        f"Сообщение В <#1166364621863661578> Обновилось `{WM_times_updated}` Раз\n"
        f"Это Сообщение Обновилось `{PC_times_updated}` Раз\n"
        f"Бот включен: `{time_on_delta}` Времени\n\n"
        f"### **Всего**\n"
        f"Это Сообщение Обновилось `{total_times_updated}` Раз\n"
        f"Бот включен: `{timedelta(seconds=total_time_ON)}` Времени\n\n"
        f"### **Рекорды**\n"
        f"Это Сообщение Обновилось `{best_times_updated}` Раз\n"
        f"Бот включен: `{timedelta(seconds=best_time_ON)}` Времени"
      ),
      color=Colour.from_rgb(randint(0, 255), randint(0, 255), randint(0, 255)),
      timestamp=datetime.now(timezone.utc),
    )

    PC_times_updated += 1
    bot_data["total_times_updated"] = total_times_updated + 1

    if PC_times_updated >= best_times_updated:
      bot_data["best_times_updated"] = PC_times_updated

    if time_on_delta.total_seconds() >= float(best_time_ON):
      bot_data["best_time_ON"] = int(time_on_delta.total_seconds())

    now = datetime.now()
    total_time_ON_td = timedelta(seconds=total_time_ON) + (now - self.prev_time)
    bot_data["total_time_ON"] = int(total_time_ON_td.total_seconds())

    async with json_lock:
      tmp = "temp_bot_data.json"
      try:
        with open(tmp, "w", encoding="utf-8") as f:
          dump(bot_data, f, ensure_ascii=False, indent=2)
        replace(tmp, "bot_data.json")
      except Exception:
        pass

    return e

  def _embed_cpu(self) -> Embed:
    e = Embed(title="CPU", color=Colour.blurple())

    per = cpu_percent(percpu=True)
    total = cpu_percent(percpu=False)
    freq = cpu_freq()
    cur_mhz = freq.current if freq else 0.0

    per_core_lines = " | ".join([f"`{i:02d}` {v:.1f}%" for i, v in enumerate(per, start=1)])

    e.add_field(
      name=clip(f"{cpu_model} | `{cpu_cores_str}`", 256),
      value=clip(
        f"**Нагрузка (Total)**: `{fmt_pct(total)}`\n"
        f"**Частота**: `{fmt_mhz(cur_mhz)}`\n"
        f"**Ядра**:\n{per_core_lines}",
        1024
      ),
      inline=False,
    )
    return e

  def _embed_memory(self) -> Embed:
    e = Embed(title="Память", color=Colour.green())

    vm = virtual_memory()
    sw = swap_memory()

    e.add_field(
      name="Оперативная Память",
      value=clip(
        f"**RAM**: `Нагрузка {vm.percent:.2f}%` **|** `Всего {vm.total/(1024**3):.2f}GB` **|** `Использовано {vm.used/(1024**3):.2f}GB` **|** `Свободно {vm.available/(1024**3):.2f}GB`\n"
        f"**Swap**: `Нагрузка {sw.percent:.2f}%` **|** `Всего {sw.total/(1024**3):.2f}GB` **|** `Использовано {sw.used/(1024**3):.2f}GB` **|** `Свободно {sw.free/(1024**3):.2f}GB`",
        1024
      ),
      inline=False
    )
    return e

  def _embed_storage(self) -> Embed:
    e = Embed(title="Диски", color=Colour.dark_gold())
    du = disk_usage(getcwd())
    e.description = clip(
      f"**Вместимость**: `Всего {du.total/(1024**3):.2f}GB` **|** `Использовано {du.used/(1024**3):.2f}GB ({du.percent:.2f}%)` **|** `Свободно {du.free/(1024**3):.2f}GB`",
      4096
    )
    return e

  async def _embed_network(self) -> Embed:
    e = Embed(title="Сеть", color=Colour.blue())
    e.add_field(name="Статистика", value=clip(await self._collect_net_block_psutil(), 1024), inline=False)
    return e

  async def _embed_bot(self) -> Embed:
    dm = self.bot.get_cog("DataManager")
    dir_size = await _dir_disk_usage_async(getcwd())
    disk_total = disk_usage(getcwd()).total

    botio_now = proc.io_counters()
    bot_read = botio_now.read_bytes
    bot_write = botio_now.write_bytes
    bot_read_delta = bot_read - self.prev_proc_io.read_bytes
    bot_write_delta = bot_write - self.prev_proc_io.write_bytes

    bot_cpu_p = proc.cpu_percent(interval=None)
    bot_mem_p = proc.memory_percent()
    bot_mem_i = proc.memory_info()

    used_users = (await dm.get_or_query("used_users", {}, 60*60, self._get_used_users_in_db))[0]["amount"] or 0
    economy_users = (await dm.get_or_query("economy_users", {}, 60*60, self._get_economy_users_in_db))[0]["amount"] or 0
    total_points, monthly_points = await self._fetch_topgg_votes()

    dt = max((datetime.now() - self.prev_time).total_seconds(), 1.0)

    e = Embed(title="Бот", color=Colour.orange(), timestamp=datetime.now(timezone.utc))
    e.add_field(
      name="Процесс",
      value=clip(
        f"**ЦП**: `{bot_cpu_p:.2f}%`\n"
        f"**RAM (RSS/VMS)**: `{bot_mem_p:.2f}%`(`{bot_mem_i.rss/(1024**2):.2f}MB`**/**`{bot_mem_i.vms/(1024**2):.2f}MB`)\n"
        f"**IO (R/W)**: `{bot_read/(1024**2):.2f}MB`**/**`{bot_write/1024:.2f}KB`\n"
        f"**IO За {dt:.0f} Сек**: `{bot_read_delta/1024:.2f}KB` / `{bot_write_delta}B`\n"
        f"**Диск**: `{dir_size/(1024**2):.2f}MB`(`{(dir_size/disk_total*100):.4f}%`)",
        1024
      ),
      inline=False
    )

    e.add_field(name="Сервера", value=f"`{len(self.bot.guilds)}`", inline=True)
    e.add_field(name="Шарды", value=f"`{self.bot.shard_count}`", inline=True)
    e.add_field(name="ID Шарда", value=f"`{self.bot.shard_id}`", inline=True)
    e.add_field(name="Пользователи Использовали Меня/Всего", value=f"`{used_users}`/`{len(self.bot.users)}` (economy: `{economy_users}`)", inline=False)
    e.add_field(name="top.gg Голосов Всего", value=f"`{total_points}`", inline=True)
    e.add_field(name="top.gg Голосов За месяц", value=f"`{monthly_points}`", inline=True)
    e.add_field(name="Задержка", value=f"`{self.bot.latency*1000:.2f}ms`", inline=False)

    e.set_footer(text=str(datetime.now()), icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png")

    self.prev_proc_io = botio_now
    return e

  @tasks.loop(seconds=30)
  async def update_PC_info(self) -> None:
    global start_updating_time, end_updating_time

    start_updating_time = datetime.now()

    guild = self.bot.get_guild(self.GUILD_ID)
    if not guild:
      return
    channel = guild.get_channel(self.STATUS_CHANNEL_ID)
    if not channel:
      return

    try:
      message_to_edit = await channel.fetch_message(self.STATUS_MESSAGE_ID)
    except (NotFound, HTTPException):
      print(f"{datetime.now()} | UpdatePCInfo | Status message not found / RateLimit.")
      return

    embeds: list[Embed] = []

    try:
      embeds.append(await self._embed_overview(message_to_edit))
      embeds.append(self._embed_cpu())
      embeds.append(self._embed_memory())
      embeds.append(self._embed_storage())
      embeds.append(await self._embed_network())
      embeds.append(await self._embed_bot())
    except Exception as e:
      print(f"{datetime.now()} | UpdatePCInfo | {e}")
      print_exc()

    embeds = embeds[:10]

    try:
      await message_to_edit.edit(embeds=embeds, content=None)
    except (NotFound, Forbidden, DiscordServerError):
      await sleep(15)
    except HTTPException as err:
      print(f"{datetime.now()} | UpdatePCInfo | {err}")
      print_exc()
      await sleep(15)

    end_updating_time = datetime.now()
    self.prev_net = net_io_counters()
    self.prev_time = end_updating_time

  @update_PC_info.before_loop
  async def before_update_message(self) -> None:
    await self.bot.wait_until_ready()

def setup(bot: commands.Bot) -> None:
  bot.add_cog(UpdatePCInfo(bot))