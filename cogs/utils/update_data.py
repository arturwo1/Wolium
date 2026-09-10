import nextcord
from nextcord.ext import commands
from datetime import datetime, timezone
import traceback
from json import dumps

class UpdateData(commands.Cog):
	def __init__(self, bot):
		self.bot: commands.Bot = bot

	def _adapt_value(self, v):
		if isinstance(v, (dict, list)):
			return dumps(v, ensure_ascii=False, separators=(",", ":"))
		return v
	
	async def update_data(self, user_id: str, data: dict, table: str, checker: str, guild: nextcord.Guild = None):
		try:
			dm = self.bot.get_cog("DataManager")
			user_id_int = int(user_id)
			user = self.bot.get_user(user_id_int)
			
			adapted = [self._adapt_value(v) for v in data.values()]
			values = [user_id_int] + adapted
			edit_data = adapted

			await dm.set_fields(table, {checker: user_id_int}, data, ttl_seconds=650, guild=guild, user=user)
			
			return True

		except Exception as e:
			traceback_msg = ((''.join(traceback.format_exception(type(e), e, e.__traceback__)))[:5000])
			log = nextcord.Embed(
				title=f"PostgreSQL | Error updating user data",
				description=(f"{e}")[:500],
				color=nextcord.Colour.red(),
				timestamp=datetime.now(timezone.utc)
			)
			if guild:
				invite = await self.bot.get_cog("GetInvite").invite(guild)
				log.add_field(
					name="Server",
					value=f"{guild.id} | {invite} | {guild.name}" if guild else "DM",
					inline=False
				)
			if user:
				log.add_field(
					name="User",
					value=f"{user_id} | {user.mention} | {user.name}",
					inline=True
				)
			log.add_field(
				name="Data",
				value=f"Expected: ```json\n{data}```\nDone: ```json\n{edit_data}```and```json\n{values}```\nTable: `{table}`\nChecker: `{checker}`",
				inline=True
			)
			log.set_author(name=f"ERROR")
			for i in range(0, len(traceback_msg), 1000):
				log.add_field(
					name="Error",
					value=f"```py\n{traceback_msg[i:i+1000]}```",
					inline=False
				)
			log.set_footer(
				text=f"{str(datetime.now())}",
				icon_url="https://cdn.discordapp.com/attachments/886241481118068906/1145385898637271060/2088617.png"
			)
			await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
			
			return False

def setup(bot: commands.Bot):
	bot.add_cog(UpdateData(bot))