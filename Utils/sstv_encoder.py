import io
import wave
import audioop
import base64
from PIL import Image
from pysstv.color import Robot36, MartinM1, MartinM2, ScottieS1, ScottieS2, ScottieDX, PasokonP3, PasokonP5, PasokonP7, PD90, PD120, PD160, PD180, PD240, PD290

SSTV_MODES = {
  'robot36': Robot36,
  'martinm1': MartinM1,
  'martinm2': MartinM2,
  'scottie1': ScottieS1,
  'scottie2': ScottieS2,
  'scottiedx': ScottieDX,
  'pasokonp3': PasokonP3,
  'pasokonp5': PasokonP5,
  'pasokonp7': PasokonP7,
  'pd90': PD90,
  'pd120': PD120,
  'pd160': PD160,
  'pd180': PD180,
  'pd240': PD240,
  'pd290': PD290,
}

SSTV_SIZES = {
  'robot36': (320, 240),
  'martinm1': (320, 256),
  'martinm2': (320, 256),
  'scottie1': (320, 256),
  'scottie2': (320, 256),
  'scottiedx': (320, 256),
  'pasokonp3': (640, 496),
  'pasokonp5': (640, 496),
  'pasokonp7': (640, 496),
  'pd90': (640, 496),
  'pd120': (640, 496),
  'pd160': (640, 496),
  'pd180': (640, 496),
  'pd240': (640, 496),
  'pd290': (640, 496),
}

def prepare_image(img, mode):
  width, height = SSTV_SIZES[mode]

  img = img.convert("RGB")
  img.thumbnail((width, height), Image.Resampling.LANCZOS)

  canvas = Image.new("RGB", (width, height), (0, 0, 0))
  x = (width - img.width) // 2
  y = (height - img.height) // 2
  canvas.paste(img, (x, y))

  return canvas

def encode_to_wav(image_bytes, mode='robot36', samples_per_sec=44100, bits=16):
  img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
  img = prepare_image(img, mode)

  wav = io.BytesIO()

  cls = SSTV_MODES.get(mode, Robot36)
  sstv = cls(img, samples_per_sec, bits)
  sstv.write_wav(wav)

  wav.seek(0)
  return wav

def build_waveform(wav, points=100):
  wav.seek(0)

  with wave.open(wav, "rb") as f:
    frames = f.readframes(f.getnframes())
    sampwidth = f.getsampwidth()
    channels = f.getnchannels()
    nframes = f.getnframes()
    duration = nframes / f.getframerate()

  block = max(1, nframes // points)
  block_bytes = block * sampwidth * channels

  amplitudes = []

  for start in range(0, len(frames), block_bytes):
    chunk = frames[start:start + block_bytes]
    if chunk:
      amplitudes.append(audioop.rms(chunk, sampwidth))

  if not amplitudes:
    return base64.b64encode(b"\0").decode(), 0.0

  peak = max(amplitudes) or 1
  scaled = bytes(min(255, int(a / peak * 255)) for a in amplitudes[:points])

  wav.seek(0)
  return base64.b64encode(scaled).decode(), duration