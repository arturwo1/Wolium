import nextcord
from nextcord.ext import commands
from datetime import datetime, timezone
import traceback
from Utils.config import users
import json
from asyncio import sleep

class LogMemberActivity(commands.Cog):
	def __init__(self, bot):
		self.bot:commands.Bot = bot
	
	async def log_member_activity(self, user_id:int, guild_id:int|None, activity_type:str, data:dict):
		try:
			while True:
				if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
					async with self.bot.db_pool.acquire() as conn:
						guild = self.bot.get_guild(guild_id)
						user = self.bot.get_user(user_id)
						if guild:
							if user_id not in users:
								language = guild.preferred_locale if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'en' if guild.preferred_locale=='en-US' or guild.preferred_locale=='en-GB' and guild.preferred_locale!='es-ES' and guild.preferred_locale!='sv-SE' else 'es' if guild.preferred_locale!='en-US' and guild.preferred_locale!='en-GB' and guild.preferred_locale=='es-ES' and guild.preferred_locale!='sv-SE' else 'sv'
								await self.bot.get_cog("EnsureGuildExists").ensure_guild_exists(guild.id)
								await self.bot.get_cog("EnsureUserExists").ensure_user_exists(user_id,user.name,language,guild)
								users.add(user_id)
						elif not guild and user:
							await self.bot.get_cog("EnsureUserExists").ensure_user_exists(user_id, user.name)
						query = """
						INSERT INTO users_members_activity (user_id, guild_id, type, data)
						VALUES ($1, $2, $3, $4)
						"""
						await conn.execute(query, user_id, guild_id, activity_type, json.dumps(data))
					break
				else:
					await sleep(10)
		except Exception as e:
			traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
			log = nextcord.Embed(
				title=f"Postgresql | Ошибка при добавлении лога юзера",
				description=(f"{e}")[:500],
				color=nextcord.Colour.red(),
				timestamp=datetime.now(timezone.utc)
			)
			if guild:
				invite = await self.bot.get_cog("GetInvite").invite(guild)
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
				value=f"user_id: {user_id}\nguild_id: {guild_id}\nactivity_type: {activity_type}\ndata: **```json\n{data}```**",
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
				text=f"log_member_activity",
				icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
			)
			await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
		return

def setup(bot:commands.Bot):
	bot.add_cog(LogMemberActivity(bot))