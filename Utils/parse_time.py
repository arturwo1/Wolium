from re import findall, IGNORECASE

timeUNITS = {
  "qs": 1e-30,
  "rs": 1e-27,
  "ys": 1e-24,
  "zs": 1e-21,
  "as": 1e-18,
  "fs": 1e-15,
  "ps": 1e-12,
  "ns": 1e-9,
  "us": 1e-6,
  "ms": 1e-3,
  "s": 1,
  "m": 60,
  "h": 3600,
  "d": 86400,
  "w": 604800,
  "mo": 2629746,
  "y": 31557600,
  "dec": 315576000,
  "c": 3155760000,
  "ky": 3.15576e10,
  "my": 3.15576e13,
  "gy": 3.15576e16,
  "ty": 3.15576e19,
  "py": 3.15576e22,
  "ey": 3.15576e25,
  "zy": 3.15576e28,
  "yy": 3.15576e31,
  "ry": 3.15576e34,
  "qy": 3.15576e37,
}

def parse_time(value):
  if not value:
    return 0

  value = str(value).lower().strip().replace(",", ".")

  unit_keys = sorted(timeUNITS.keys(), key=len, reverse=True)
  pattern = rf"(\d+(?:\.\d+)?)\s*({'|'.join(unit_keys)})\b"

  sec = 0.0
  for num, unit in findall(pattern, value, flags=IGNORECASE):
    try:
      n = float(num)
    except ValueError:
      continue

    factor = timeUNITS.get(unit.lower())
    if factor:
      sec += n * factor

  return sec