from time import time
from nextcord import slash_command, Interaction, IntegrationType, InteractionContextType, Color
from nextcord.ext.commands import Cog, Bot
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from Utils.discord_locale import locale
from traceback import format_exception

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class DeleteData(Cog):
  def __init__(self,bot:Bot):
    self.bot:Bot=bot

  @slash_command(
    description="Delete your stored data",
    name_localizations=translate_to_all_languages('privacy.delete_name', 'name'),
    description_localizations=translate_to_all_languages('privacy.delete_desc', 'description'),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ])
  async def delete_data(self,
    interaction:Interaction,
  ):
    try:
      await interaction.response.defer(ephemeral=True)

      user_id = interaction.user.id
      current_time = time()

      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")
      se = self.bot.get_cog("SendEmbed")
      lang = locale(interaction.locale)

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.followup.send(await tm.translate_message("error.rate_limit", lang, variables={"time": f"<t:{round(last_command_time + 10)}:R>"}), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      user_settings = await gd.get_data(user_id,['language'],'users','user_id',interaction.guild)
      language = user_settings['language']

      async with self.bot.db_pool.acquire() as conn:
        async with conn.transaction():
          deleted_messages = await conn.execute(
            "DELETE FROM messages WHERE user_id = $1",
            user_id
          )
          deleted_voice = await conn.execute(
            "DELETE FROM voice WHERE user_id = $1",
            user_id
          )

      msg_count = deleted_messages.split()[-1]
      voice_count = deleted_voice.split()[-1]
      await interaction.followup.send(await tm.translate_message("privacy.data_deleted_success", language, variables={"messages": msg_count, "voice": voice_count}), ephemeral=True)

    except Exception as e:
      invite = await gi.invite(interaction.guild)
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      fields = [
        {
          'name':'User',
          'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline':True
        },
        {
          'name':'Server',
          'value':f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
          'inline':True
        },
        {
          'name':'Channel',
          'value':f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else f'[<@{interaction.user.id}>({interaction.user.id} | {interaction.user.name}({interaction.user.display_name})]'}`)",
          'inline':True
        },
        {
          'name':'Error',
          'value':traceback_msg,
          'inline':False
        }
      ]
      await se.send_embed(
        title=f"Error executing /{interaction.application_command.name}",
        description=str(e)[:2048],
        color=Color.red(),
        fields=fields,
        footer_text=f'Error in cogs.commands.🛡️privacy.delete_data',
        author_text='ERROR',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      await interaction.followup.send(await tm.translate_message("error.occurred_logs_saved_review", lang), ephemeral=True)

  setattr(delete_data,"extras",{"description": "commands.delete_data.description"})

def setup(bot:Bot):
  bot.add_cog(DeleteData(bot))
