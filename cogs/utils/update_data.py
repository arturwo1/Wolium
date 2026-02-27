import nextcord
from nextcord.ext import commands
from datetime import datetime,timezone
from Utils.config import users
import traceback
from asyncio import sleep
from cogs.utils.get_invite import GetInvite
from json import dumps

class UpdateData(commands.Cog):
	def __init__(self, bot):
		self.bot:commands.Bot = bot

	def _adapt_value(self, v):
		if isinstance(v, (dict, list)):
			return dumps(v, ensure_ascii=False, separators=(",", ":"))
		return v
	
	async def update_data(self,user_id:str,data:dict,table:str,checker:str,guild:nextcord.Guild=None):
		ensure_guild = self.bot.get_cog("EnsureGuildExists")
		ensure_user = self.bot.get_cog("EnsureUserExists")
		try:
			data_str = ', '.join([f"{key} = ${i+2}" for i,key in enumerate(data.keys())])
			edit_data = 'None'
			values = 'None'
			try:
				user = self.bot.get_user(user_id)
			except Exception:
				user = None
			while True:
				if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
					if guild:
						await ensure_guild.ensure_guild_exists(guild.id)
						if user:
							if user_id not in users:
								language = guild.preferred_locale if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'en' if guild.preferred_locale=='en-US' or guild.preferred_locale=='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'es' if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale=='es-ES' and guild.preferred_locale!='sv-SE' else 'sv'
								await ensure_user.ensure_user_exists(user_id,user.name,language,guild) 
								users.add(user_id)
					elif not guild and user:
						await ensure_user.ensure_user_exists(user_id, user.name)

					async with self.bot.db_pool.acquire() as conn:
						async with conn.transaction():
							if len(data_str)>2000:
								await conn.execute(
									f"UPDATE {table} SET {data_str} = '' WHERE {checker} = $1",
									checker
								)
								for i in range(0, len(data_str), 2000):
									chunk = data_str[i:i+2000]
									await conn.execute(
										f"UPDATE {table} SET {data_str} = {data_str} || $1 WHERE {checker} = $2",
										chunk, checker
									)
							else:
								query = f"UPDATE {table} SET {data_str} WHERE {checker} = $1"
								adapted = [self._adapt_value(v) for v in data.values()]
								values = [user_id] + adapted
								edit_data = adapted
								await conn.execute(query,*values)
					break
				else:
					await sleep(10)
		except Exception as e:
			traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
			log = nextcord.Embed(
				title=f"Postgresql | Ошибка при изменении данных пользователя",
				description=(f"{e}")[:500],
				color=nextcord.Colour.red(),
				timestamp=datetime.now(timezone.utc)
			)
			if guild:
				invite = await (GetInvite(self.bot)).invite(guild)
				log.add_field(
					name="Сервер",
					value=f"{guild.id} | {invite} | {guild.name}" if guild else "ЛС",
					inline=False
				)
			if user:
				log.add_field(
					name="Пользователь",
					value=f"{user_id} | {user.mention} | {user.name}",
					inline=True
				)
			log.add_field(
				name="Данные",
				value=f"Изначально: ```json\n{data}```\nСделано: ```json\n{edit_data}```и```json\n{values}```\nТаблица: `{table}`\nЧекер: `{checker}`",
				inline=True
			)
			log.set_author(
				name=f"ЕРРОР",
			)
			for i in range(0, len(traceback_msg), 1000):
				log.add_field(
					name="Ошибка",
					value=f"```py\n{traceback_msg[i:i+1000]}```",
					inline=False
				)
			log.set_footer(
				text=f"{str(datetime.now())}",
				icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
			)
			await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
		return None

def setup(bot:commands.Bot):
	bot.add_cog(UpdateData(bot))