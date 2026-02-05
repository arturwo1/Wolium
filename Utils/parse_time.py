from re import findall
def parse_time(put: str) -> (int|None):
  put = put.replace(' ', '')
  time_regex = findall(r'(\d+)([smhdw])', put.lower())
  if not time_regex:
    return None
  time_dict = {'s':1,'m':60,'h':3600,'d':86400,'w':604800}
  total_seconds = sum(int(value)*time_dict[unit] for value, unit in time_regex)
  return total_seconds