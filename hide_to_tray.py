import threading
import os
import ctypes
from ctypes import wintypes
from pystray import Icon, MenuItem, Menu
from PIL import Image
import sys
from datetime import datetime
from pathlib import Path

script_directory = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_directory)

ICON_PATH = r"images\Wolium.gif"
TRAY_NAME = "Wolium"
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

log_buffer = []

class Tee:
  def __init__(self, original):
    self.original = original

  def write(self, text):
    if text.strip():
      log_buffer.append(text)
    self.original.write(text)

  def flush(self):
    self.original.flush()

sys.stdout = Tee(sys.stdout)
sys.stderr = Tee(sys.stderr)

GetConsoleWindow = ctypes.windll.kernel32.GetConsoleWindow
ShowWindow = ctypes.windll.user32.ShowWindow
Kernel32 = ctypes.windll.kernel32

SW_HIDE = 0
SW_SHOW = 5

hwnd = GetConsoleWindow()

tray_icon = None

def save_log(icon, item):
  if not log_buffer:
    return

  timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
  log_file = LOG_DIR / f"log_{timestamp}.log"

  with open(log_file, "w", encoding="utf-8") as f:
    f.writelines(log_buffer)

  print(f"[LOG] Лог сохранён в {log_file}")

def hide_console():
  if hwnd:
    ShowWindow(hwnd, SW_HIDE)

def show_console():
  if hwnd:
    ShowWindow(hwnd, SW_SHOW)

def on_open(icon, item):
  show_console()

def on_hide(icon, item):
  hide_console()

def on_quit(icon, item):
  try:
    icon.stop()
  except Exception:
    pass
  os._exit(0)

def create_tray():
  global tray_icon

  try:
    image = Image.open(ICON_PATH)
  except Exception:
    image = Image.new("RGBA", (64, 64), (255, 255, 255, 0))

  menu = Menu(
    MenuItem("Консоль", Menu(
      MenuItem("Открыть", on_open),
      MenuItem("Скрыть", on_hide),
    )),
    MenuItem("Сохранить лог", save_log),
    MenuItem("Выход", on_quit),
  )

  tray_icon = Icon(TRAY_NAME, image, TRAY_NAME, menu)
  tray_icon.run()

PHANDLER = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

@PHANDLER
def console_handler(event):
  """
  dwCtrlType:
  0 = CTRL_C_EVENT
  1 = CTRL_BREAK_EVENT
  2 = CTRL_CLOSE_EVENT
  5 = CTRL_SHUTDOWN_EVENT
  """
  if event == 2:
    hide_console()
    return True
  return False

Kernel32.SetConsoleCtrlHandler(console_handler, True)

tray_thread = threading.Thread(target=create_tray, daemon=True)
tray_thread.start()

hide_console()