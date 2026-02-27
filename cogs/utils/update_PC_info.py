from __future__ import annotations

import asyncio
from asyncio import Lock, to_thread
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from json import load, dump
from os import getenv, getpid, replace, getcwd, path, walk
from random import randint
from traceback import format_exception, print_exc
from typing import Any, Optional
from re import compile, I

from nextcord import Embed, Colour, Message, NotFound
from nextcord.ext import commands, tasks
from nextcord.errors import HTTPException

from aiohttp import ClientSession
from cpuinfo import get_cpu_info
from dotenv import load_dotenv
from psutil import (
  cpu_count as psutil_cpu_count,
  cpu_percent,
  swap_memory,
  net_io_counters,
  disk_usage,
  Process,
)
from wmi import WMI
import pynvml

from main import time_when_bot_run_firts
from Utils.suffics import suffics
from Utils.config import PC_times_updated as PC_times_updated_initial
from Utils.LHM import LHM

load_dotenv()

json_lock: Lock = Lock()

SMT_PAIRING = "offset" # adjacent | offset

# ----------------------------
# helpers
# ----------------------------

def embed_size(e: Embed) -> int:
  total = 0
  total += len(e.title or "")
  total += len(e.description or "")
  try:
    if e.footer and e.footer.text:
      total += len(e.footer.text)
  except Exception:
    pass
  try:
    if e.author and e.author.name:
      total += len(e.author.name)
  except Exception:
    pass
  for f in e.fields:
    total += len(f.name or "")
    total += len(f.value or "")
  return total

def clip(s: str, limit: int) -> str:
  s = s or ""
  if len(s) <= limit:
    return s
  return s[: max(0, limit - 3)] + "..."

def fnum(x: Any, default: float = 0.0) -> float:
  try:
    if x is None:
      return default
    return float(x)
  except Exception:
    return default

def fmt_c(x: float) -> str:   return f"{x:.2f}°C"
def fmt_v(x: float) -> str:   return f"{x:.3f}V"
def fmt_w(x: float) -> str:   return f"{x:.1f}W"
def fmt_mhz(x: float) -> str: return f"{x:.0f}MHz"
def fmt_pct(x: float) -> str: return f"{x:.2f}%"

def _iter_items(group: Any) -> list[tuple[str, Any]]:
  if group is None:
    return []
  try:
    it = group.items()
    return list(it)
  except Exception:
    return []

def _pick_sensor(group: Any, *, name_eq: str | None = None, name_contains: str | None = None, name_starts: str | None = None) -> Any | None:
  for _, n in _iter_items(group):
    nm = str(getattr(n, "name", "") or "")
    if name_eq is not None and nm == name_eq:
      return n
    if name_contains is not None and name_contains in nm:
      return n
    if name_starts is not None and nm.startswith(name_starts):
      return n
  return None

CORE_RE = compile(r"#\s*(\d+)", I)

def _core_idx(name: str) -> int | None:
  m = CORE_RE.search(str(name))
  return int(m.group(1)) if m else None

def classify(name: str) -> str:
  n = str(name).lower()
  if "effective" in n: return "effective"
  if "vid" in n:       return "vid"
  if "smu" in n:       return "smu"
  return "plain"

def by_idx(nodes: list, want: str | None = None):
  out = {}
  for n in nodes:
    nm = getattr(n, "name", "")
    idx = _core_idx(nm)
    if idx is None:
      continue
    if want is not None and classify(nm) != want:
      continue
    out[idx] = n
  return out

def _pick_many(
  group: Any,
  *,
  name_eq: str | None = None,
  name_contains: str | None = None,
  name_starts: str | None = None,
) -> list[Any]:
  out: list[Any] = []
  for _, n in _iter_items(group):
    nm = str(getattr(n, "name", "") or "")

    if name_eq is not None and nm == name_eq:
      out.append(n)
      continue

    if name_starts is not None and nm.lower().startswith(name_starts.lower()):
      out.append(n)
      continue

    if name_contains is not None and name_contains.lower() in nm.lower():
      out.append(n)
      continue

  return out

def _node_val(n: Any) -> float | None:
  v = getattr(n, "value", None)
  if v is None:
    return None
  try:
    return float(v)
  except Exception:
    return None

def build_cpu_rows(cpu_node: Any) -> list[CpuCoreRow]:
  loads_nodes = _pick_many(getattr(cpu_node, "load", None), name_starts="CPU Core #")
  loads = by_idx(loads_nodes)  # ключ = индекс из "#n"

  clocks_nodes = _pick_many(getattr(cpu_node, "clock", None), name_starts="Core #")
  clocks_plain = by_idx(clocks_nodes, "plain")
  clocks_eff   = by_idx(clocks_nodes, "effective")

  factors_nodes = _pick_many(getattr(cpu_node, "factor", None), name_starts="Core #")
  powers_nodes  = _pick_many(getattr(cpu_node, "power", None),  name_starts="Core #")
  volts_nodes   = _pick_many(getattr(cpu_node, "voltage", None),name_starts="Core #")

  factors = by_idx(factors_nodes, "plain")
  powers  = by_idx(powers_nodes,  "smu")
  volts   = by_idx(volts_nodes,   "vid")

  load_cnt = len(loads)
  core_cnt = len(clocks_plain) or len(factors) or len(powers) or len(volts)

  rows: list[CpuCoreRow] = []

  # SMT если есть per-core метрики (core_cnt) и load'ов в 2 раза больше
  if core_cnt and load_cnt >= core_cnt * 2:
    smt_off = core_cnt
    for i in range(1, core_cnt + 1):
      if SMT_PAIRING == "offset":
        t0, t1 = i, i + core_cnt
      else:
        t0, t1 = 2*i - 1, 2*i

      l0 = _node_val(loads.get(t0))
      l1 = _node_val(loads.get(t1))

      agg = None
      if l0 is not None or l1 is not None:
        agg = max(x for x in (l0, l1) if x is not None)

      rows.append(CpuCoreRow(
        i=i,
        load=agg,
        load0=l0,
        load1=l1,
        clk=_node_val(clocks_plain.get(i)),
        eff=_node_val(clocks_eff.get(i)),
        fac=_node_val(factors.get(i)),
        pwr=_node_val(powers.get(i)),
        vid=_node_val(volts.get(i)),
      ))
    return rows

  if core_cnt:
    for i in range(1, core_cnt + 1):
      l0 = _node_val(loads.get(i))
      rows.append(CpuCoreRow(
        i=i,
        load=l0,
        load0=l0,
        load1=None,
        clk=_node_val(clocks_plain.get(i)),
        eff=_node_val(clocks_eff.get(i)),
        fac=_node_val(factors.get(i)),
        pwr=_node_val(powers.get(i)),
        vid=_node_val(volts.get(i)),
      ))
    return rows

  for i in sorted(loads.keys()):
    l0 = _node_val(loads.get(i))
    rows.append(CpuCoreRow(i=i, load=l0, load0=l0, load1=None, clk=None, eff=None, fac=None, pwr=None, vid=None))
  return rows

def _fmt_rate(x: float) -> str:
  if x >= 1024**3: return f"{x/(1024**3):.2f}GB/s"
  if x >= 1024**2: return f"{x/(1024**2):.2f}MB/s"
  if x >= 1024:    return f"{x/1024:.2f}KB/s"
  return f"{x:.0f}B/s"

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

# ----------------------------
# static CPU + WMI RAM info
# ----------------------------

cpu_info = get_cpu_info()
cpu_model: str = cpu_info.get("brand_raw", "Unknown CPU")
cpu_cores_str = f"{psutil_cpu_count(logical=False)}`/`{psutil_cpu_count(logical=True)}"

proc = Process(getpid())
proc.cpu_percent(interval=None)

c_wmi = WMI()

TYPE_DETAIL_FLAGS = {
  1: "Reserved",
  2: "Other",
  4: "Unknown",
  8: "Fast-paged",
  16: "Static column",
  32: "Pseudo-static",
  64: "RAMBUS",
  128: "Synchronous",
  256: "CMOS",
  512: "EDO",
  1024: "Window DRAM",
  2048: "Cache DRAM",
  4096: "Non-volatile",
  8192: "Registered (Buffered)",
  16384: "Unbuffered (Unregistered)",
  32768: "Reserved for future use",
}

def _build_ram_info() -> list[dict[str, str]]:
  fields: list[dict[str, str]] = []
  try:
    for ram in c_wmi.Win32_PhysicalMemory():
      type_detail = ", ".join(
        f"[**{name}** - `{code}`]" for code, name in TYPE_DETAIL_FLAGS.items() if ram.TypeDetail & code
      )

      if isinstance(ram.SMBIOSMemoryType, str):
        mem_type = ram.SMBIOSMemoryType
      else:
        mem_type_map = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 30: "DDR5"}
        mem_type = mem_type_map.get(ram.SMBIOSMemoryType, str(ram.SMBIOSMemoryType))

      form_factor = "DIMM" if ram.FormFactor == 8 else "SODIMM" if ram.FormFactor == 12 else "Unknown"

      fields.append({
        "name": f"{ram.Manufacturer} | {ram.PartNumber}",
        "value": (
          f"**Объём**: `{int(ram.Capacity) / (1024 ** 3):.2f}GB`\n"
          f"**Скорость**: `{int(ram.Speed):.0f}MHz`\n"
          f"**Разрядность(общ/итог)**: `{ram.DataWidth}bit`/`{ram.TotalWidth}bit`\n"
          f"**Форм-Фактор**: `{ram.FormFactor}`(`{form_factor}`)\n"
          f"**Тип**: `{ram.MemoryType}`(`{mem_type}`)\n"
          f"**Локация**: `{ram.DeviceLocator}`\n"
          f"**Частота(конф)**: `{ram.ConfiguredClockSpeed}MHz`\n"
          f"**Напряжение(конф)**: `{int(ram.ConfiguredVoltage)/1000}V`\n"
          f"**TypeDetail**: `{ram.TypeDetail}`({type_detail})"
        )
      })
  except Exception:
    pass
  return fields

RAM_INFO = _build_ram_info()

# ----------------------------
# NVML fallback (если LHM не дал GPU)
# ----------------------------

@dataclass
class CpuCoreRow:
  i: int
  load: float | None
  load0: float | None
  load1: float | None
  clk: float | None
  eff: float | None
  fac: float | None
  pwr: float | None
  vid: float | None

class NvmlMini:
  def __init__(self) -> None:
    self.ok = False
    try:
      pynvml.nvmlInit()
      self.ok = True
    except Exception:
      self.ok = False

  def close(self) -> None:
    if self.ok:
      try:
        pynvml.nvmlShutdown()
      except Exception:
        pass
    self.ok = False

  def snapshot(self) -> dict[str, Any] | None:
    if not self.ok:
      return None
    try:
      count = pynvml.nvmlDeviceGetCount()
      if count <= 0:
        return None
      h = pynvml.nvmlDeviceGetHandleByIndex(0)
      name = pynvml.nvmlDeviceGetName(h)
      driver = pynvml.nvmlSystemGetDriverVersion()
      mem = pynvml.nvmlDeviceGetMemoryInfo(h)
      util = pynvml.nvmlDeviceGetUtilizationRates(h)
      temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
      try:
        fan = pynvml.nvmlDeviceGetFanSpeed(h)
      except Exception:
        fan = None
      try:
        power = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0
      except Exception:
        power = None
      core = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_GRAPHICS)
      memc = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_MEM)
      return {
        "name": str(name),
        "driver": str(driver),
        "temp": float(temp),
        "fan": None if fan is None else float(fan),
        "power": power,
        "core_mhz": float(core),
        "mem_mhz": float(memc),
        "gpu_util": float(util.gpu),
        "mem_util": float(util.memory),
        "mem_used_gb": mem.used / (1024 ** 3),
        "mem_total_gb": mem.total / (1024 ** 3),
      }
    except Exception:
      return None

# ----------------------------
# LHM cache (узлы + сенсоры)
# ----------------------------

@dataclass
class CpuRef:
  name: str = "CPU"
  tctl: Any = None
  ccd: Any = None
  total: Any = None
  max_core: Any = None
  pkg_power: Any = None
  bus: Any = None
  clk_avg: Any = None
  clk_eff: Any = None
  core_loads: list[Any] = None
  core_clocks: list[Any] = None
  core_factors: list[Any] = None
  core_powers: list[Any] = None
  core_voltages: list[Any] = None
  core_rows: list[CpuCoreRow] = None

@dataclass
class GpuRef:
  name: str = "GPU"
  temp_core: Any = None
  temp_memj: Any = None
  clk_core: Any = None
  clk_mem: Any = None
  power_pkg: Any = None
  mem_used: Any = None
  mem_free: Any = None
  mem_total: Any = None
  fans: list[Any] = None
  controls: list[Any] = None
  throughput_rx: Any = None
  throughput_tx: Any = None
  loads: dict[str, Any] = None
  smalldata: dict[str, Any] = None

@dataclass
class StorageRef:
  name: str
  temp1: Any = None
  temp2: Any = None
  warn: Any = None
  crit: Any = None
  life: Any = None
  spare: Any = None
  spare_thr: Any = None
  pct_used: Any = None
  used: Any = None
  free: Any = None
  total: Any = None
  read_total: Any = None
  write_total: Any = None
  pwr_cnt: Any = None
  pwr_hrs: Any = None
  read_act: Any = None
  write_act: Any = None
  total_act: Any = None

@dataclass
class NicRef:
  name: str
  up_total: Any = None
  down_total: Any = None
  up_speed: Any = None
  down_speed: Any = None
  util: Any = None

@dataclass
class SuperIORef:
  name: str
  volt: list[Any]
  temps: list[Any]
  fans: list[Any]
  controls: list[Any]

@dataclass
class MemRef:
  ram_used: Any = None
  ram_avail: Any = None
  ram_load: Any = None
  vram_used: Any = None # Virtual Memory
  vram_avail: Any = None
  vram_load: Any = None

@dataclass
class DimmRef:
  name: str
  cap: Any = None
  timings: dict[str, Any] = None

class LhmCache:
  def __init__(self, lhm: LHM):
    self.lhm = lhm
    self.ready = False
    self.built_at = datetime.min

    self.cpu: CpuRef | None = None
    self.gpu: GpuRef | None = None
    self.mem: MemRef | None = None
    self.dimms: list[DimmRef] = []
    self.storages: list[StorageRef] = []
    self.nics: list[NicRef] = []
    self.superios: list[SuperIORef] = []
    self.motherboard_name: str | None = None

  def refresh_refs(self) -> None:
    # Motherboard name
    mb = getattr(self.lhm, "motherboard", None)
    self.motherboard_name = str(getattr(mb, "name", "Unknown")) if mb else None

    # ---- CPU ----
    cpu = getattr(self.lhm, "cpu", None)
    if cpu:
      loads = _pick_many(getattr(cpu, "load", None), name_starts="CPU Core #")
      loads = sorted(loads, key=lambda n: _core_idx(getattr(n, "name", "")))
      clocks = _pick_many(getattr(cpu, "clock", None), name_starts="Core #")
      clocks = sorted(clocks, key=lambda n: _core_idx(getattr(n, "name", "")))
      factors = _pick_many(getattr(cpu, "factor", None), name_starts="Core #")
      factors = sorted(factors, key=lambda n: _core_idx(getattr(n, "name", "")))
      powers = _pick_many(getattr(cpu, "power", None), name_starts="Core #")
      powers = sorted(powers, key=lambda n: _core_idx(getattr(n, "name", "")))
      voltages = _pick_many(getattr(cpu, "voltage", None), name_starts="Core #")
      voltages = sorted(voltages, key=lambda n: _core_idx(getattr(n, "name", "")))
      rows = build_cpu_rows(cpu)
      self.cpu = CpuRef(
        core_rows=rows,
        name=str(getattr(cpu, "name", "CPU")),
        tctl=_pick_sensor(getattr(cpu, "temperature", None), name_contains="Tctl/Tdie"),
        ccd=_pick_sensor(getattr(cpu, "temperature", None), name_contains="CCD"),
        total=_pick_sensor(getattr(cpu, "load", None), name_eq="CPU Total"),
        max_core=_pick_sensor(getattr(cpu, "load", None), name_contains="CPU Core Max"),
        pkg_power=_pick_sensor(getattr(cpu, "power", None), name_eq="Package"),
        bus=_pick_sensor(getattr(cpu, "clock", None), name_eq="Bus Speed"),
        clk_avg=_pick_sensor(getattr(cpu, "clock", None), name_eq="Cores (Average)"),
        clk_eff=_pick_sensor(getattr(cpu, "clock", None), name_contains="Average Effective"),
        core_loads=loads,
        core_clocks=clocks,
        core_factors=factors,
        core_powers=powers,
        core_voltages=voltages,
      )
    else:
      self.cpu = None

    # ---- GPU ----
    gpu = getattr(self.lhm, "gpu", None)
    if gpu:
      loads_map = {}
      for label in [
        "GPU Core",
        "GPU Memory Controller",
        "GPU Video Engine",
        "GPU Bus",
        "D3D 3D",
        "D3D Video Decode",
        "D3D Video Encode",
        "D3D Copy",
      ]:
        loads_map[label] = _pick_sensor(getattr(gpu, "load", None), name_eq=label) or _pick_sensor(getattr(gpu, "load", None), name_contains=label)

      sd_map = {}
      for label in [
        "GPU Memory Total",
        "GPU Memory Free",
        "GPU Memory Used",
        "D3D Dedicated Memory Used",
        "D3D Shared Memory Used",
      ]:
        sd_map[label] = _pick_sensor(getattr(gpu, "smalldata", None), name_eq=label) or _pick_sensor(getattr(gpu, "smalldata", None), name_contains=label)

      fans = []
      for n in _pick_many(getattr(gpu, "fan", None), name_starts="GPU Fan"):
        fans.append(n)

      ctrls = []
      for n in _pick_many(getattr(gpu, "control", None), name_starts="GPU Fan"):
        ctrls.append(n)

      self.gpu = GpuRef(
        name=str(getattr(gpu, "name", "GPU")),
        temp_core=_pick_sensor(getattr(gpu, "temperature", None), name_eq="GPU Core") or _pick_sensor(getattr(gpu, "temperature", None), name_contains="GPU Core"),
        temp_memj=_pick_sensor(getattr(gpu, "temperature", None), name_contains="Memory Junction"),
        clk_core=_pick_sensor(getattr(gpu, "clock", None), name_eq="GPU Core"),
        clk_mem=_pick_sensor(getattr(gpu, "clock", None), name_eq="GPU Memory"),
        power_pkg=_pick_sensor(getattr(gpu, "power", None), name_contains="Package"),
        mem_total=sd_map.get("GPU Memory Total"),
        mem_free=sd_map.get("GPU Memory Free"),
        mem_used=sd_map.get("GPU Memory Used"),
        fans=fans,
        controls=ctrls,
        throughput_rx=_pick_sensor(getattr(gpu, "throughput", None), name_contains="PCIe Rx"),
        throughput_tx=_pick_sensor(getattr(gpu, "throughput", None), name_contains="PCIe Tx"),
        loads=loads_map,
        smalldata=sd_map,
      )
    else:
      self.gpu = None

    # ---- Storage ----
    self.storages = []
    for st in self.lhm.type_get("Storage"):
      temp1 = _pick_sensor(getattr(st, "temperature", None), name_eq="Temperature")
      temp2 = _pick_sensor(getattr(st, "temperature", None), name_eq="Temperature 2")
      warn = _pick_sensor(getattr(st, "temperature", None), name_contains="warning")
      crit = _pick_sensor(getattr(st, "temperature", None), name_contains="critical")

      def p_lvl(eq: str): return _pick_sensor(getattr(st, "level", None), name_eq=eq)
      def p_data(eq: str): return _pick_sensor(getattr(st, "data", None), name_eq=eq)
      def p_fac(eq: str): return _pick_sensor(getattr(st, "factor", None), name_eq=eq)
      def p_load(eq: str): return _pick_sensor(getattr(st, "load", None), name_eq=eq)

      self.storages.append(StorageRef(
        name=str(getattr(st, "name", "Storage")),
        temp1=temp1, temp2=temp2, warn=warn, crit=crit,
        life=p_lvl("Life"),
        spare=p_lvl("Available Spare"),
        spare_thr=p_lvl("Available Spare Threshold"),
        pct_used=p_lvl("Percentage Used"),
        used=p_load("Used Space"),
        read_act=p_load("Read Activity"),
        write_act=p_load("Write Activity"),
        total_act=p_load("Total Activity"),
        free=p_data("Free Space"),
        total=p_data("Total Space"),
        read_total=p_data("Data read"),
        write_total=p_data("Data written"),
        pwr_cnt=p_fac("Power on count"),
        pwr_hrs=p_fac("Power on hours"),
      ))

    # ---- Network ----
    self.nics = []
    for nic in self.lhm.type_get("Network"):
      def p_data_contains(substr: str) -> Any | None:
        for _, n in _iter_items(getattr(nic, "data", None)):
          nm = str(getattr(n, "name", "")).lower()
          if substr in nm:
            return n
        return None

      def p_thr_contains(substr: str) -> Any | None:
        for _, n in _iter_items(getattr(nic, "throughput", None)):
          nm = str(getattr(n, "name", "")).lower()
          if substr in nm:
            return n
        return None

      util = _pick_sensor(getattr(nic, "load", None), name_contains="Utilization")
      self.nics.append(NicRef(
        name=str(getattr(nic, "name", "NIC")),
        up_total=p_data_contains("uploaded"),
        down_total=p_data_contains("downloaded"),
        up_speed=p_thr_contains("upload speed"),
        down_speed=p_thr_contains("download speed"),
        util=util,
      ))

    # ---- SuperIO ----
    self.superios = []
    for chip in self.lhm.type_get("SuperIO"):
      self.superios.append(SuperIORef(
        name=str(getattr(chip, "name", "SuperIO")),
        volt=[n for _, n in _iter_items(getattr(chip, "voltage", None))],
        temps=[n for _, n in _iter_items(getattr(chip, "temperature", None))],
        fans=[n for _, n in _iter_items(getattr(chip, "fan", None))],
        controls=[n for _, n in _iter_items(getattr(chip, "control", None))],
      ))

    # ---- Memory (/ram + /vram + DIMMs) ----
    ram_node = None
    vram_node = None
    dimms: list[Any] = []

    for m in self.lhm.type_get("Memory"):
      nm = str(getattr(m, "name", "") or "")
      low = nm.lower()

      if "total memory" in low:
        ram_node = m
        continue

      if "virtual memory" in low:
        vram_node = m
        continue

      has_timing = bool(_iter_items(getattr(m, "timing", None)))
      has_capacity = _pick_sensor(getattr(m, "data", None), name_eq="Capacity") is not None

      if has_timing or has_capacity or ("dimm" in low) or ("module" in low) or ("(#" in nm):
        dimms.append(m)

    def pick_mem(mnode: Any) -> tuple[Any, Any, Any]:
      used = _pick_sensor(getattr(mnode, "data", None), name_contains="Used") or _pick_sensor(getattr(mnode, "data", None), name_contains="Memory Used")
      avail = _pick_sensor(getattr(mnode, "data", None), name_contains="Available") or _pick_sensor(getattr(mnode, "data", None), name_contains="Memory Available")
      loadn = _pick_sensor(getattr(mnode, "load", None), name_contains="Memory")
      return used, avail, loadn

    memref = MemRef()
    if ram_node:
      memref.ram_used, memref.ram_avail, memref.ram_load = pick_mem(ram_node)
    if vram_node:
      memref.vram_used, memref.vram_avail, memref.vram_load = pick_mem(vram_node)
    self.mem = memref

    self.dimms = []
    wanted_timings = {
      "tAA (CAS Latency Time)": "tCL",
      "tRCD (RAS to CAS Delay Time)": "tRCD",
      "tRP (Row Precharge Delay Time)": "tRP",
      "tRAS (Active to Precharge Delay Time)": "tRAS",
      "tRC (Active to Active/Refresh Delay Time)": "tRC",
      "tRFC1 (Refresh Recovery Delay Time)": "tRFC1",
    }

    for d in dimms:
      cap = _pick_sensor(getattr(d, "data", None), name_eq="Capacity")
      tmap: dict[str, Any] = {}
      for full, short in wanted_timings.items():
        tmap[short] = _pick_sensor(getattr(d, "timing", None), name_eq=full)
      self.dimms.append(DimmRef(
        name=str(getattr(d, "name", "DIMM")),
        cap=cap,
        timings=tmap,
      ))

    self.ready = True
    self.built_at = datetime.now()

  def build(self) -> None:
    self.refresh_refs()

# ----------------------------
# globals counters
# ----------------------------

start_updating_time: datetime = datetime.now()
end_updating_time: datetime = datetime.now()
PC_times_updated: int = PC_times_updated_initial

# ----------------------------
# Cog
# ----------------------------

class UpdatePCInfo(commands.Cog):
  GUILD_ID: int = 807304463449849938
  STATUS_CHANNEL_ID: int = 1163483706137247887
  STATUS_MESSAGE_ID: int = 1163484167682658324
  LOG_CHANNEL_ID: int = 1159138280651104256

  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    self.session: Optional[ClientSession] = None

    self.prev_net = net_io_counters()
    self.prev_time = datetime.now()
    self.prev_proc_io = proc.io_counters()

    self.lhm = LHM(refresh_sec=10)
    self.cache = LhmCache(self.lhm)
    self._last_cache_try = datetime.min

    self.nvml = NvmlMini()
    self.update_PC_info.start()

  def cog_unload(self) -> None:
    self.update_PC_info.cancel()
    try:
      self.lhm.close()
    except Exception:
      pass
    try:
      self.nvml.close()
    except Exception:
      pass
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

  async def _load_economy_data_count(self) -> int:
    try:
      async with json_lock:
        with open("economy_data.json", "r", encoding="utf-8") as f:
          data = load(f)
      return len(data)
    except Exception:
      return 0

  async def _get_economy_users_in_db(self) -> int:
    if not hasattr(self.bot, "db_pool") or not self.bot.db_pool:
      return 0
    try:
      async with self.bot.db_pool.acquire() as conn:
        val = await conn.fetchval("SELECT COUNT(*) FROM user_data WHERE upgrade > 1")
        return int(val or 0)
    except Exception:
      return 0

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

    c = self.cache.cpu
    if not c:
      per = cpu_percent(percpu=True)
      e.description = clip(
        f"**{cpu_model}** | `{cpu_cores_str}`\n" +
        " | ".join([f"`{i:02d}` {v:.1f}%" for i, v in enumerate(per, start=1)])[:4000],
        4096,
      )
      return e

    tctl = fnum(getattr(c.tctl, "value", None), 0.0)
    ccd = fnum(getattr(c.ccd, "value", None), 0.0)
    total = fnum(getattr(c.total, "value", None), 0.0)
    mx = fnum(getattr(c.max_core, "value", None), 0.0)
    pkg = fnum(getattr(c.pkg_power, "value", None), 0.0)
    bus = fnum(getattr(c.bus, "value", None), 0.0)
    avg = fnum(getattr(c.clk_avg, "value", None), 0.0)
    eff = fnum(getattr(c.clk_eff, "value", None), 0.0)

    rows = c.core_rows or []
    parts = []

    has_clk = any(r.clk is not None for r in rows)
    has_fac = any(r.fac is not None for r in rows)
    has_pwr = any(r.pwr is not None for r in rows)
    has_vid = any(r.vid is not None for r in rows)
    has_smt = any(r.load1 is not None for r in rows)

    for r in rows:
      if has_smt:
        t0 = f"{r.load0:4.1f}" if r.load0 is not None else "  — "
        t1 = f"{r.load1:4.1f}" if r.load1 is not None else "  — "
        load_s = f"{t0}%|{t1}%"
      else:
        load_s = f"{r.load:5.1f}%" if r.load is not None else "  —  "

      col = [load_s]

      if has_clk:
        col.append(f"{r.clk:5.0f}MHz" if r.clk is not None else "  —  ")
      if has_fac:
        col.append(f"{r.fac:4.2f}x" if r.fac is not None else " — ")
      if has_pwr:
        col.append(f"{r.pwr:4.1f}W" if r.pwr is not None else " — ")
      if has_vid:
        col.append(f"{r.vid:1.3f}V" if r.vid is not None else " — ")

      parts.append(f"`{r.i:02d}`" + " | ".join(col) + "\n")

    hdr_cols = ["Нагрузка(T0/T1)" if has_smt else "Нагрузка"]
    if has_clk: hdr_cols.append("Частота")
    if has_fac: hdr_cols.append("Множитель")
    if has_pwr: hdr_cols.append("Мощность")
    if has_vid: hdr_cols.append("Напряжение")
    hdr = " | ".join(hdr_cols)

    lines = ["  ".join(parts[i:i+4]) for i in range(0, len(parts), 4)]
    cores_block = clip("\n".join(lines), 1024)

    e.add_field(
      name=clip(c.name, 256),
      value=clip(
        f"**Температуры**: `Tctl {fmt_c(tctl)}` **|** `CCD {fmt_c(ccd)}`\n"
        f"**Нагрузка**: `Total {fmt_pct(total)}` **|** `MaxCore {fmt_pct(mx)}`\n"
        f"**Мощность**: `Pkg {fmt_w(pkg)}`\n"
        f"**Частота**: `Avg {fmt_mhz(avg)}` **|** `Eff {fmt_mhz(eff)}` **|** `Bus {bus:.3f}MHz`\n"
        f"**Ядра** N {hdr}:\n{cores_block}",
        1024
      ),
      inline=False,
    )
    return e

  def _embed_gpu(self) -> Embed:
    e = Embed(title="GPU", color=Colour.dark_purple())

    g = self.cache.gpu
    snap = self.nvml.snapshot()
    if g:
      temp = fnum(getattr(g.temp_core, "value", None), 0.0)
      memj = fnum(getattr(g.temp_memj, "value", None), 0.0)
      clk_c = fnum(getattr(g.clk_core, "value", None), 0.0)
      clk_m = fnum(getattr(g.clk_mem, "value", None), 0.0)
      pwr = fnum(getattr(g.power_pkg, "value", None), 0.0)

      mem_total_mb = fnum(getattr(g.mem_total, "value", None), 0.0)
      mem_used_mb = fnum(getattr(g.mem_used, "value", None), 0.0)
      mem_free_mb = fnum(getattr(g.mem_free, "value", None), 0.0)

      def ld(label: str) -> float:
        n = (g.loads or {}).get(label)
        return fnum(getattr(n, "value", None), 0.0)

      d3d_ded = fnum(getattr((g.smalldata or {}).get("D3D Dedicated Memory Used"), "value", None), 0.0)
      d3d_sha = fnum(getattr((g.smalldata or {}).get("D3D Shared Memory Used"), "value", None), 0.0)

      fan_line = ""
      if g.fans:
        fan_line = " **|** ".join([f"**{getattr(n,'name','Fan')}**: `{fnum(getattr(n,'value',None),0.0):.0f}RPM`" for n in g.fans[:3]])
      ctrl_line = ""
      if g.controls:
        ctrl_line = " **|** ".join([f"**{getattr(n,'name','Ctrl')}**: `{fnum(getattr(n,'value',None),0.0):.0f}%`" for n in g.controls[:3]])

      rx = fnum(getattr(g.throughput_rx, "value", None), 0.0)
      tx = fnum(getattr(g.throughput_tx, "value", None), 0.0)

      if not snap.get("driver"):
        snap['driver'] = "N/A"

      value = (
        f"**Драйвер**: `{snap['driver']}`\n"
        f"**Температуры**: `Ядро {fmt_c(temp)}` **|** `MemJ {fmt_c(memj)}`\n"
        f"**Частота**: `Ядро {fmt_mhz(clk_c)}` **|** `Память {fmt_mhz(clk_m)}`\n"
        f"**Мощность**: `{fmt_w(pwr)}`\n"
        f"**Нагрузка**: `Ядро {fmt_pct(ld('GPU Core'))}` **|** `Контроллер Памяти {fmt_pct(ld('GPU Memory Controller'))}` **|** `Видео {fmt_pct(ld('GPU Video Engine'))}` **|** `Шина {fmt_pct(ld('GPU Bus'))}`\n"
        f"**Direct3D Нагрузка**: `3D {fmt_pct(ld('D3D 3D'))}` **|** `Декодирование {fmt_pct(ld('D3D Video Decode'))}` **|** `Кодирование {fmt_pct(ld('D3D Video Encode'))}` **|** `Копирование {fmt_pct(ld('D3D Copy'))}`\n"
        f"**VRAM**: `{mem_used_mb/1024:.2f}GB`**/**`{mem_total_mb/1024:.2f}GB` (`Свободно {mem_free_mb/1024:.2f}GB`)\n"
        f"**Direct3D Память**: `Выделено {d3d_ded:.0f}MB` **|** `Общая {d3d_sha:.0f}MB`\n"
        f"**PCIe**: `Приходит {_fmt_rate(rx)}` **|** `Уходит {_fmt_rate(tx)}`\n"
        + (f"***Вентиляторы***:\n{fan_line}\n" if fan_line else "")
        + (f"***Контроллер***:\n{ctrl_line}\n" if ctrl_line else "")
      )

      e.add_field(name=clip(g.name, 256), value=clip(value, 1024), inline=False)
      return e

    if snap:
      e.add_field(
        name=clip(str(snap["name"]), 256),
        value=clip(
          f"**Драйвер**: `{snap['driver']}`\n"
          f"**Температура**: `{fmt_c(snap['temp'])}`\n"
          f"**Нагрузка**: `GPU {fmt_pct(snap['gpu_util'])}` **|** `VRAM {fmt_pct(snap['mem_util'])}`\n"
          f"**VRAM**: `{snap['mem_used_gb']:.2f}GB`**/**`{snap['mem_total_gb']:.2f}GB`\n"
          f"**Частоты**: `Ядро {fmt_mhz(snap['core_mhz'])}` **|** `Память {fmt_mhz(snap['mem_mhz'])}`\n"
          f"**Мощность**: `{fmt_w(snap['power'])}`\n"
          + (f"**Вентиляторы**: `{snap['fan']:.0f}%`" if snap["fan"] is not None else "**Вентиляторы**: `N/A`"),
          1024,
        ),
        inline=False,
      )
      return e

    try:
      ctrls = c_wmi.Win32_VideoController()
      if ctrls:
        g0 = ctrls[0]
        name = getattr(g0, "Name", "Неизвестно")
        driver = getattr(g0, "DriverVersion", "Неизвестно")
        ram = (getattr(g0, "AdapterRAM", 0) or 0) / (1024 ** 3)
        e.add_field(name=clip(name, 256), value=clip(f"**Драйвер**: `{driver}`\n**VRAM**: `{ram:.2f}GB`", 1024), inline=False)
        return e
    except Exception:
      pass

    e.description = "Не удалось получить информацию о GPU."
    return e

  def _embed_memory(self) -> Embed:
    e = Embed(title="Память", color=Colour.green())

    m = self.cache.mem
    if m:
      ram_used = fnum(getattr(m.ram_used, "value", None), 0.0)
      ram_av = fnum(getattr(m.ram_avail, "value", None), 0.0)
      ram_ld = fnum(getattr(m.ram_load, "value", None), 0.0)

      vm_used = fnum(getattr(m.vram_used, "value", None), 0.0)
      vm_av = fnum(getattr(m.vram_avail, "value", None), 0.0)
      vm_ld = fnum(getattr(m.vram_load, "value", None), 0.0)

      sw = swap_memory()

      e.add_field(
        name="Оперативная Память",
        value=clip(
          f"**RAM**: `Нагрузка {fmt_pct(ram_ld)}` **|** `Всего {ram_used+ram_av:.2f}GB` **|** `Использовано {ram_used:.2f}GB` **|** `Свободно {ram_av:.2f}GB`\n"
          f"**Virtual**: `Нагрузка {fmt_pct(vm_ld)}` **|** `Всего {vm_used+vm_av:.2f}GB` **|** `Использовано {vm_used:.2f}GB` **|** `Свободно {vm_av:.2f}GB`\n"
          f"**Swap**: `Нагрузка {sw.percent:.2f}%` **|** `Всего {sw.total/(1024**3)}GB` **|** `Использовано {sw.used/(1024**3):.2f}GB` **|** `Свободно {sw.free/(1024**3):.2f}GB`",
          1024
        ),
        inline=False
      )
    return e

  def _embed_ram_timings(self) -> Embed:
    e = Embed(title="DIMM (тайминги)", color=Colour.dark_green())
    if not self.cache.dimms:
      e.description = "Нет DIMM данных в LHM."
      return e

    dimms_count = len(self.cache.dimms)
    for d in self.cache.dimms:
      cap = fnum(getattr(d.cap, "value", None), 0.0)
      t = d.timings or {}
      def tval(k: str) -> str:
        n = t.get(k)
        return f"{fnum(getattr(n,'value',None),0.0):.2f}" if n else "N/A"

      value = (
        f"**Объём**: `{cap:.0f}GB`\n"
        f"**tCL/tRCD/tRP**: `{tval('tCL')}` / `{tval('tRCD')}` / `{tval('tRP')}`\n"
        f"**tRAS/tRC**: `{tval('tRAS')}` / `{tval('tRC')}`\n"
        f"**tRFC1**: `{tval('tRFC1')}`"
      )
      e.add_field(name=clip(str(d.name)+(f"  X{dimms_count}" if dimms_count>1 else ""), 256), value=clip(value, 1024), inline=False)
      break

    return e

  def _embed_motherboard(self) -> Embed:
    e = Embed(title="Материнка / SuperIO", color=Colour.dark_teal())
    if self.cache.motherboard_name:
      e.description = clip(f"**Motherboard**: `{self.cache.motherboard_name}`", 4096)

    if not self.cache.superios:
      e.add_field(name="SuperIO", value="Нет данных.", inline=False)
      return e

    for chip in self.cache.superios[:6]:
      def pack_list(nodes: list[Any], fmt_fn, take: int = 9) -> str:
        out = []
        for n in nodes[:take]:
          nm = str(getattr(n, "name", ""))
          vv = fnum(getattr(n, "value", None), None)
          if vv is None:
            continue
          out.append(f"**{nm}**: `{fmt_fn(vv)}`")
        more = ""
        if len(nodes) > take:
          more = f"\n… +{len(nodes)-take}"
        return " **|** ".join(out) + more if out else "`N/A`"

      vline = pack_list(chip.volt, fmt_v)
      tline = pack_list(chip.temps, fmt_c)
      fline = pack_list(chip.fans, lambda x: f"{x:.0f}RPM", take=6)
      cline = pack_list(chip.controls, lambda x: f"{x:.0f}%", take=6)

      e.add_field(
        name=clip(f"Чипсет: {chip.name}", 256),
        value=clip(
          f"***Напряжение***:\n{vline}\n"
          f"***Температура***:\n{tline}\n"
          f"***Вентилятор***:\n{fline}\n"
          f"***Контроллер***:\n{cline}",
          1024
        ),
        inline=False
      )
    return e

  def _embed_storage(self) -> Embed:
    e = Embed(title="Диски", color=Colour.dark_gold())
    if not self.cache.storages:
      du = disk_usage(getcwd())
      e.description = clip(
        f"**Вместимость**: `Всего {du.total/(1024**3):.2f}GB` **|** `Использовано {du.used/(1024**3):.2f}GB ({du.percent:.2f}%)`",
        4096
      )
      return e

    for st in self.cache.storages[:8]:
      temp1 = fnum(getattr(st.temp1, "value", None), 0.0)
      temp2 = fnum(getattr(st.temp2, "value", None), 0.0)
      warn = fnum(getattr(st.warn, "value", None), 0.0)
      crit = fnum(getattr(st.crit, "value", None), 0.0)

      life = fnum(getattr(st.life, "value", None), 0.0)
      spare = fnum(getattr(st.spare, "value", None), 0.0)
      spare_thr = fnum(getattr(st.spare_thr, "value", None), 0.0)
      pct_used = fnum(getattr(st.pct_used, "value", None), 0.0)

      usage = fnum(getattr(st.used, "value", None), 0.0)
      free = fnum(getattr(st.free, "value", None), 0.0)
      total = fnum(getattr(st.total, "value", None), 0.0)

      read_total = fnum(getattr(st.read_total, "value", None), 0.0)
      write_total = fnum(getattr(st.write_total, "value", None), 0.0)

      pwr_cnt = fnum(getattr(st.pwr_cnt, "value", None), 0.0)
      pwr_hrs = fnum(getattr(st.pwr_hrs, "value", None), 0.0)

      r_act = fnum(getattr(st.read_act, "value", None), 0.0)
      w_act = fnum(getattr(st.write_act, "value", None), 0.0)
      tot_act = fnum(getattr(st.total_act, "value", None), 0.0)

      used = total-free
      avail = 100-usage

      value = (
        f"**Температуры**: `T1 {fmt_c(temp1)}` **|** `T2 {fmt_c(temp2)}` **|** `Warn {fmt_c(warn)}` **|** `Crit {fmt_c(crit)}`\n"
        f"**Активность**: `W {w_act:.6f}%`**/**`R {r_act:.6f}%` **|** `Всего {tot_act:.6f}%`\n"
        f"**Вместимость**: `Всего {total:.2f}GB` **|** `Использовано {used:.2f}GB`(`{usage:.2f}%`) **|** `Свободно {free:.2f}GB`(`{avail:.2f}%`)\n"
        f"**Зп/Чт Всего**: `Зп {write_total:.0f}GB`**/**`Чт {read_total:.0f}GB`\n"
        f"**Включен**: `{pwr_hrs:.0f}ч`(`Включений: {pwr_cnt:.0f}`)\n"
        f"**NAND**: `Ресурс {life:.0f}%` **|** `резерв {spare:.0f}%`(`Использовано {pct_used:.0f}%`, `Порог {spare_thr:.0f}%`)"
      )
      e.add_field(name=clip(st.name, 256), value=clip(value, 1024), inline=False)

    return e

  async def _embed_network(self) -> Embed:
    e = Embed(title="Сеть", color=Colour.blue())

    if self.cache.nics:
      for nic in self.cache.nics[:8]:
        up_total = fnum(getattr(nic.up_total, "value", None), 0.0)
        down_total = fnum(getattr(nic.down_total, "value", None), 0.0)
        up_speed = fnum(getattr(nic.up_speed, "value", None), 0.0)
        down_speed = fnum(getattr(nic.down_speed, "value", None), 0.0)
        util = fnum(getattr(nic.util, "value", None), 0.0)

        val = (
          f"**Всего**: `Отд {up_total:.3f}GB`**/**`Скч {down_total:.3f}GB`\n"
          f"**Скорость**: `Отд {_fmt_rate(up_speed)}`**/**`Скч {_fmt_rate(down_speed)}`\n"
          f"**Нагрузка**: `{util:.6f}%`"
        )
        e.add_field(name=clip(nic.name, 256), value=clip(val, 1024), inline=False)

    e.add_field(name="Другое", value=clip(await self._collect_net_block_psutil(), 1024), inline=False)
    return e

  async def _embed_bot(self) -> Embed:
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

    saved_users = await self._load_economy_data_count()
    economy_users = await self._get_economy_users_in_db()
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
    e.add_field(name="Пользователи Сохранено/Всего", value=f"`{saved_users}`/`{len(self.bot.users)}` (economy: `{economy_users}`)", inline=False)
    e.add_field(name="top.gg Голосов Всего", value=f"`{total_points}`", inline=True)
    e.add_field(name="top.gg Голосов За месяц", value=f"`{monthly_points}`", inline=True)
    e.add_field(name="Задержка", value=f"`{self.bot.latency*1000:.2f}ms`", inline=False)

    e.set_footer(text=str(datetime.now()), icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png")

    self.prev_proc_io = botio_now
    return e

  async def _ensure_lhm_ready(self) -> None:
    now = datetime.now()

    try:
      await to_thread(self.lhm.update, force=True)
    except Exception as e:
      await self._send_error_embed("LHM update failed", "Не удалось обновить ссылки на сенсоры.", e)
      return

    try:
      await to_thread(self.cache.refresh_refs)
    except Exception as e:
      if (now - self._last_cache_try) >= timedelta(seconds=30):
        self._last_cache_try = now
        try:
          await to_thread(self.cache.build)
        except Exception:
          pass

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

    await self._ensure_lhm_ready()

    embeds: list[Embed] = []

    try:
      embeds.append(await self._embed_overview(message_to_edit))
      embeds.append(self._embed_cpu())
      embeds.append(self._embed_gpu())
      embeds.append(self._embed_memory())
      embeds.append(self._embed_ram_timings())
      embeds.append(self._embed_motherboard())
      embeds.append(self._embed_storage())
      embeds.append(await self._embed_network())

      if RAM_INFO:
        e_ram = Embed(title="RAM Инфо", color=Colour.dark_grey())
        items = len(RAM_INFO)
        for f in RAM_INFO:
          title = str(f["name"])+("  X"+str(items) if items>1 else "")
          e_ram.add_field(
            name=clip(title, 256),
            value=clip(f["value"], 900),
            inline=False
          )
          break
        embeds.append(e_ram)

      embeds.append(await self._embed_bot())
    except Exception as e:
      print(f"{datetime.now()} | UpdatePCInfo | {e}")
      print_exc()

    embeds = embeds[:10]

    # for e in embeds:
    #   print(f"[EMBED] {e.title!r} fields={len(e.fields)} size={embed_size(e)}")

    try:
      await message_to_edit.edit(embeds=embeds, content=None)
    except HTTPException as err:
      print(f"{datetime.now()} | UpdatePCInfo | {err}")
      print_exc()
      await asyncio.sleep(15)

    end_updating_time = datetime.now()
    self.prev_net = net_io_counters()
    self.prev_time = end_updating_time

  @update_PC_info.before_loop
  async def before_update_message(self) -> None:
    await self.bot.wait_until_ready()
    try:
      await to_thread(self.lhm.open)
    except Exception:
      pass
    await self._ensure_lhm_ready()

def setup(bot: commands.Bot) -> None:
  bot.add_cog(UpdatePCInfo(bot))
