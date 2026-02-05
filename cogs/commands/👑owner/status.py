from nextcord import SlashOption, slash_command, Interaction, Game, Streaming, Activity, ActivityType, Status
from nextcord.ext.commands import Cog, Bot
from json import load, dump
from main import init_database

status_data = {}

class Status(Cog):
  def __init__(self, bot):
    self.bot: Bot = bot

  @slash_command(guild_ids=[807304463449849938,1297240282806620193],default_member_permissions=8, description="Изменить Статус Бота.")
  async def статус(self,
    interaction: Interaction,
    название: str=SlashOption(name="название", description="Надпись в Активносте.",required=True),
    активность: str=SlashOption(name="активность", description="Выбрать Активность У Бота.",choices={"играть": "play", "стримить": "stream", "слушать": "listening", "смотреть": "watching", "участие в соревновании": "competing"}, required=False),
    статус: str=SlashOption(name="статус", description="Выбрать Статус Бота.",choices={"онлайн": "online", "оффлайн": "offline", "неактивен": "idle", "не беспокоить": "dnd", "скрыт": "invisible"}, required=False),
    ссылка: str=SlashOption(name="ссылка", description="Ссылка На Стрим.",required=False),
    название_эмодзи: str=SlashOption(name="название_эмодзи", description="Название Эмодзи В Начале Статуса.",required=False,default=None),
    анимировано_эмодзи: bool=SlashOption(name="анимировано_эмодзи", description="Анимировано Ли Эмодзи В Начале Статуса?",required=False,default=None),
    id_эмодзи: str=SlashOption(name="id_эмодзи", description="ID Эмодзи В Начале Статуса.",required=False,default=None),
  ):
    if interaction.user.id!=self.bot.owner_id:
      await interaction.response.send_message(f"Только <@{self.bot.owner_id}> может менять статус мне.",ephemeral=True)
      return
    try:
      with open('economy_data.json', 'r', encoding='utf-8') as f:
        economy_data = load(f)
    except FileNotFoundError:
      economy_data: dict = {}
    
    try:
      answer = await interaction.response.send_message(f"# СООБЩЕНИЕ", ephemeral=True)
      name = eval(''.join(название))
    except Exception as e:
      await answer.edit(f"ошибка: **`{e}`**")
      return
    
    conn = await (await init_database()).acquire()

    if активность=="play":
      activity=Game(name)
    elif активность=="stream":
      activity=Streaming(name=name,url=ссылка)
    elif активность in ["listening","watching","competing"]:
      activity=Activity(
        type=ActivityType[активность],
        name=name,
        url=(ссылка if ссылка else None),
        emoji=(
          {
            'name': название_эмодзи,
            'id': int(id_эмодзи),
            'animated': анимировано_эмодзи
          } if (название_эмодзи!=None and id_эмодзи!=None and анимировано_эмодзи!=None) else None
        )
      )
    if статус:
      await self.bot.change_presence(status=Status[статус], activity=activity)

    status_data['status'] = {
      'название': название,
      'активность': активность,
      'статус': статус,
      'ссылка': ссылка,
      'название_эмодзи': название_эмодзи,
      'анимировано_эмодзи': анимировано_эмодзи,
      'id_эмодзи': int(id_эмодзи)
    }
    with open('status_data.json', 'w', encoding='utf-8') as f:
      dump(status_data, f, ensure_ascii=False, indent=4)

    await answer.edit(f"### Статус Успешно Установлен!\n**Введенные данные**:\nНазвание: `{название}`\nАктивность: `{активность}`\nСтатус: `{статус}`\nСсылка: `{ссылка}`\nКак выглядит название в сатусе бота: `{name}`")
    await conn.close()

def setup(bot: Bot):
  bot.add_cog(Status(bot))