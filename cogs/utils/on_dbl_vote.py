from asyncio import sleep
from datetime import datetime, timezone
from nextcord.ext import commands
from nextcord import Color, ButtonStyle
from nextcord.ui import View, Button
from aiohttp import web, ClientSession
from os import getenv
from time import time

class Vote(View):
  def __init__(self):
    super().__init__(timeout=1)
    vote = Button(
      row=1,
      label="Голосовать",
      style=ButtonStyle.url,
      url="https://top.gg/bot/1051105900116574250/vote",
      emoji="✅"
    )
    self.add_item(vote)

class OnDBLVote(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  async def topgg_vote(self,request):
    if request.headers.get("Authorization") != getenv("TOPGG_DISCORDBOT_TOKEN_API"):
      return web.Response(status=401,text="Unauthorized")
    data:dict[str,str] = await request.json()
    user_id = int(data.get("user"))
    user = self.bot.get_user(user_id)
    if not user: return web.Response(status=404, text="User not found")
    type_ = data.get('type')
    if type_ in ("upvote", "test"):
      voted_in = time()
      while True:
        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          async with self.bot.db_pool.acquire() as conn:
            await (self.bot.get_cog("EnsureUserExists")).ensure_user_exists(user_id, user.name)
            await conn.execute(
              "INSERT INTO topgg (user_id) VALUES ($1) "
              "ON CONFLICT (user_id) DO NOTHING",user_id)
          break
        else:
          await sleep(10)
      h12 = 12*60*60
      is_weekend = data.get("isWeekend", False)
      uti = await (self.bot.get_cog("GetData")).get_data(user_id,['votes','streak','voted_in'],'topgg','user_id',None)
      votes:int = uti['votes']+(1 if not is_weekend else 2)
      streak:int = uti['streak']
      voted_in_day_ago:float = uti['voted_in']
      voted_after:float = voted_in+h12
      query = data.get('query','')

      diff = time() - voted_in_day_ago
      days = (datetime.fromtimestamp(time(), timezone.utc) - datetime.fromtimestamp(voted_in_day_ago, timezone.utc)).days

      if diff < 12 * 3500:
        return web.Response(status=200,text="Already voted")

      if 12 * 3600 <= diff <= 36 * 3600 and days in [0, 1]:
        streak += 1
      else:
        streak = 1

      data = {
        'votes': votes,
        'streak': streak,
        'voted_in': voted_in
      }
      await (self.bot.get_cog("UpdateData")).update_data(user_id, data, 'topgg', 'user_id', None)

      url = f"https://top.gg/api/bots/{self.bot.user.id}"
      headers = {
        "Authorization": getenv("TOPGG_DISCORDBOT_TOKEN_API"),
        'Content-Type': 'application/json'
      }
      total_points = 0
      monthly_points = 0
      async with ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
          if resp.status == 200:
            data = await resp.json()
            total_points = data.get("points", 0)
            monthly_points = data.get("monthlyPoints", 0)
          else:
            print(f'TopGG on_dbl_vote: {resp.status} - {await resp.text()}')

      fields = [
        {
          'name':'**Пользователь**',
          'value':f'**Голосов За Меня**: ***`{votes}`***\n**Стрик**: ***`{streak}`***',
          'inline':True
        },
        {
          'name':'Бот',
          'value':f'**Голосов**: ***`{total_points}`***\n**Голосов За Месяц**: ***`{monthly_points}`***',
          'inline':True
        },
        {
          'name':'Время',
          'value':f'**В**: ***<t:{round(voted_in)}:R>***\n**Через**: ***<t:{round(voted_after)}:R>***',
          'inline':True
        },
        ({
          'name':'Запрос',
          'value':f'{query}',
          'inline':False
        } if not query in ['',None] else {})
      ]

      await self.bot.get_cog("SendEmbed").send_embed(
        title="Голос",
        description=f"### **<@{user_id}>** проголосовал За Меня!{'(**`2x`** выходные!)' if is_weekend else ''}",
        color=Color.brand_green(),
        fields=fields,
        footer_text="Спасибо За Голос!",
        author_text=user.display_name if user else None,
        author_icon=user.display_avatar.url if user and user.display_avatar else None,
        channel_id=1356663516538474596,
        view=Vote()
      )
    else:
      print(data)

    return web.Response(status=200,text="OK")

def setup(bot:commands.Bot):
  bot.add_cog(OnDBLVote(bot))