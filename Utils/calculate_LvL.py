def calculate_LvL(xp):
  if not isinstance(xp, (int,float)):
    xp = 0
  XP_now = xp
  LvL = 0
  while XP_now > 25 * LvL:
    XP_now -= 25 * LvL
    LvL += 1
  XP_need = 25 * LvL
  return LvL, XP_need, XP_now