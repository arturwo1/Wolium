import nextcord
from nextcord.ext import commands
from datetime import datetime,timezone
import traceback
import time
import json
from cogs.utils.get_invite import GetInvite
from asyncio import sleep

class EnsureUserExists(commands.Cog):
	def __init__(self, bot):
		self.bot:commands.Bot = bot

	async def ensure_user_exists(self,user_id:int,username:str|None=None,language:str|None=None,guild:nextcord.Guild=None):
		try:
			try:
				user = self.bot.get_user(user_id)
				name = user.name
			except Exception:
				return
			while True:
				if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
					async with self.bot.db_pool.acquire() as conn:
						async with conn.transaction():
							await conn.execute(
								"INSERT INTO users (user_id, username, reg_data, language, telegram_id, discord_id, badges) VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (user_id) DO NOTHING",
								user_id, username if username!=None else name, time.time(), language if language else 'en', None, user_id, json.dumps(["discord"])
							)

							await conn.execute(
								"INSERT INTO user_data (user_id) VALUES ($1) "
								"ON CONFLICT (user_id) DO NOTHING",
								user_id
							)

							await conn.execute(
								"INSERT INTO user_privacy (user_id) VALUES ($1) "
								"ON CONFLICT (user_id) DO NOTHING",
								user_id
							)

							await conn.execute(
								"INSERT INTO topgg (user_id) VALUES ($1) "
								"ON CONFLICT (user_id) DO NOTHING",
								user_id
							)

							if guild and guild.id:
								await conn.execute(
									"INSERT INTO guild_users (guild_id, user_id) VALUES ($1, $2) "
									"ON CONFLICT (guild_id, user_id) DO NOTHING",
									guild.id, user_id
								)
					break
				else:
					await sleep(10)
		except Exception as e:
			traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
			log = nextcord.Embed(
				title=f"Postgresql | Ошибка добавления пользователя в БД",
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
					value=f"{user_id} | {user.mention} | {name}",
					inline=True
				)
			log.add_field(
				name="Данные",
				value=f"user_id: {user_id}\nusername: {username}\nlanguage: {language}\nguild: {guild}",
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
		return

def setup(bot:commands.Bot):
	bot.add_cog(EnsureUserExists(bot))