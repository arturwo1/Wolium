from json import dumps, loads
from decimal import Decimal
from typing import Any, Dict, Tuple

def build_key(table: str, keys: Dict[str, Any]) -> str:
  key_json = dumps({k: keys[k] for k in sorted(keys)}, ensure_ascii=False, default=str)
  return f"{table}:{key_json}"

def parse_key(ident: str) -> Tuple[str, Dict[str, Any]]:
  table, _, key_json = ident.partition(":")
  return table, loads(key_json)

def serialize_row(data: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, str]]:
  values, types = {}, {}
  for k, v in data.items():
    if v is None:
      continue
    elif isinstance(v, bool):
      values[k], types[k] = str(v), "b"
    elif isinstance(v, (dict, list)):
      values[k], types[k] = dumps(v, ensure_ascii=False), "j"
    elif isinstance(v, Decimal):
      values[k], types[k] = str(v), "d"
    elif isinstance(v, int):
      values[k], types[k] = str(v), "i"
    elif isinstance(v, float):
      values[k], types[k] = str(v), "f"
    else:
      values[k], types[k] = str(v), "s"

  return values, types

def deserialize_row(values: Dict[str, str], types: Dict[str, str]) -> Dict[str, Any]:
  res = {}
  for k, v in values.items():
    tag = types.get(k)
    if tag == "b": res[k] = v == "True"
    elif tag == "i": res[k] = int(float(v))
    elif tag == "f": res[k] = float(v)
    elif tag == "d": res[k] = Decimal(v)
    elif tag == "j": res[k] = loads(v)
    elif tag == "s": res[k] = v
    else:
      if v.lstrip("-").isdigit():
        res[k] = int(v)
      else:
        try: res[k] = float(v)
        except ValueError: res[k] = v
  return res