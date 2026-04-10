import sys, ctypes, clr
from time import sleep, time
from re import sub
from typing import Any, Iterator
from threading import Thread

if __name__ == "__main__":
  def is_admin():
    try:
      return ctypes.windll.shell32.IsUserAnAdmin()
    except:
      return False

  if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
      None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit(0)

dll = r"C:\Users\artur\AppData\Local\Microsoft\WinGet\Packages\LibreHardwareMonitor.LibreHardwareMonitor_Microsoft.Winget.Source_8wekyb3d8bbwe\LibreHardwareMonitorLib.dll"
clr.AddReference(dll)

from LibreHardwareMonitor.Hardware import Computer, IHardware  # pyright: ignore[reportMissingModuleSource]

def slug_seg(s: str) -> str:
  s = str(s).lower()
  s = s.replace("#", "")
  s = s.replace("(", "").replace(")", "")
  s = sub(r"[^a-z0-9._ -]+", "", s)
  s = sub(r"\s+", "_", s.strip())
  s = sub(r"_+", "_", s)
  if s and s[0].isdigit():
    s = "_" + s
  return s or "_"

def ident_to_path(identifier: str) -> list[str]:
  identifier = str(identifier).strip().lstrip("/")
  if not identifier:
    return []
  return [slug_seg(p) for p in identifier.split("/") if p]

def insert_path(root: dict, path: list[str], payload: dict):
  cur = root
  for seg in path[:-1]:
    cur = cur.setdefault(seg, {})
  leaf = path[-1]
  if leaf in cur and isinstance(cur[leaf], dict) and isinstance(payload, dict):
    cur[leaf].update(payload)
  else:
    cur[leaf] = payload

def enum_name(x: Any) -> str:
  try:
    return x.ToString()               # .NET Enum
  except Exception:
    return str(x).split(".")[-1]      # "HardwareType.Cpu" -> "Cpu"
  
def init_lhm(self):
  thread = Thread(target=self.pc.Open)
  thread.start()

def update_hw(hw):
  thread = Thread(target=hw.Update)
  thread.start()

class Node:
  __slots__ = ("_data",)

  def __init__(self, data: Any = None):
    self._data = data if isinstance(data, dict) else {}

  @staticmethod
  def empty() -> "Node":
    return Node({})

  def __bool__(self) -> bool:
    return bool(self._data)

  @property
  def value(self) -> Any:
    return self._data.get("value", None)

  def __getattr__(self, name: str) -> Any:
    # node.xxx.yyy.value
    v = self._data.get(name, None)
    if isinstance(v, dict):
      return Node(v)
    if v is None:
      return Node.empty()
    return v

  def items(self) -> Iterator[tuple[str, "Node"]]:
    for k, v in self._data.items():
      if isinstance(v, dict):
        yield k, Node(v)

  def raw(self) -> Any:
    return self._data

  def __repr__(self) -> str:
    keys = list(self._data.keys())
    if len(keys) > 12:
      keys = keys[:12] + ["..."]
    return f"<Node {keys}>"

class LHM:
  def __init__(self, refresh_sec: int = 30):
    self.pc = Computer()
    self.refresh_sec = refresh_sec
    self._last = 0.0
    self._tree: dict = {}
    self._by_type: dict[str, list[list[str]]] = {}
    self.hw = Node.empty()

  def open(self):
    self.pc.IsCpuEnabled = True
    self.pc.IsGpuEnabled = True
    self.pc.IsMemoryEnabled = True
    self.pc.IsMotherboardEnabled = True
    self.pc.IsStorageEnabled = True
    self.pc.IsControllerEnabled = True
    self.pc.IsNetworkEnabled = True
    init_lhm(self)
    self.update(force=True)

  def close(self):
    self.pc.Close()

  def _scan_hw(self, hw: IHardware):
    update_hw(hw)

    hw_path = ident_to_path(hw.Identifier)
    if hw_path:
      ht = enum_name(hw.HardwareType)
      insert_path(self._tree, hw_path, {"type": ht, "name": str(hw.Name)})
      self._by_type.setdefault(ht, [])
      if hw_path not in self._by_type[ht]:
        self._by_type[ht].append(hw_path)

    for s in hw.Sensors:
      if s.Value is None:
        continue
      spath = ident_to_path(s.Identifier)
      if not spath:
        continue

      st = enum_name(s.SensorType)

      mn = None if s.Min is None else float(s.Min)
      mx = None if s.Max is None else float(s.Max)

      insert_path(self._tree, spath, {
        "type": st,
        "name": str(s.Name),
        "value": float(s.Value),
        "min": mn,
        "max": mx,
        "parameters": {}
        # "parameters": {
        #   slug_seg(p.Name): {
        #     "name": str(p.Name),
        #     "value": p.Value,
        #     "default": p.DefaultValue,
        #     "description": str(p.Description)
        #   } for p in s.Parameters
        # }
      })

    for shw in hw.SubHardware:
      self._scan_hw(shw)

  def update(self, force: bool = False):
    now = time()
    if not force and self._tree and (now - self._last) < self.refresh_sec:
      return

    self._tree = {}
    self._by_type = {}

    for hw in self.pc.Hardware:
      self._scan_hw(hw)

    self.hw = Node(self._tree)
    self._last = now

  def type_get(self, hw_type: str) -> list[Node]:
    self.update()
    found: list[Node] = []
    paths = self._by_type.get(hw_type, [])
    for pth in paths:
      cur: Any = self._tree
      ok = True
      for seg in pth:
        if not isinstance(cur, dict) or seg not in cur:
          ok = False
          break
        cur = cur[seg]
      if ok and isinstance(cur, dict):
        found.append(Node(cur))
    return found

  def _first_by_type(self, hw_type: str) -> Node:
    nodes = self.type_get(hw_type)
    return nodes[0] if nodes else Node.empty()

  @property
  def cpu(self) -> Node:
    return self._first_by_type("Cpu")

  @property
  def gpu(self) -> Node:
    g = self._first_by_type("GpuNvidia")
    if g:
      return g
    g = self._first_by_type("GpuAmd")
    if g:
      return g
    return self._first_by_type("GpuIntel")

  @property
  def motherboard(self) -> Node:
    return self._first_by_type("Motherboard")

  def find_in_subtree(
    self,
    root: Node,
    *,
    name_starts: str = "",
    name_contains: str = "",
    sensor_type: str = "",
  ) -> list[tuple[str, Node]]:
    out: list[tuple[str, Node]] = []
    for k, n in root.items():
      nm = getattr(n, "name", "") or ""
      tp = getattr(n, "type", "") or ""
      if sensor_type and tp != sensor_type:
        continue
      if name_starts and not str(nm).startswith(name_starts):
        continue
      if name_contains and name_contains not in str(nm):
        continue
      out.append((k, n))
    return out

# ---------------- test ----------------

if __name__ == "__main__":

  try:
    sys.path.insert(0, r"C:\Users\artur\OneDrive\projects\DiscordBot")
    from cogs.utils.update_PC_info import _iter_items
    lhm = LHM(refresh_sec=1)
    lhm.open()
    print("=== LHM Memory nodes ===")
    for m in lhm.type_get("Memory"):
      print(getattr(m, "name", None),
            "timing=", bool(_iter_items(getattr(m, "timing", None))),
            "data=", bool(_iter_items(getattr(m, "data", None))))
  except Exception as e:
    print("err:", e)

  while True:
    sleep(1)