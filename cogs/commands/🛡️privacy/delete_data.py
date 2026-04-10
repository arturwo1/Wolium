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
    description="Удаление Данных С Бота",
    name_localizations=translate_to_all_languages('удалить_дату', 'name'),
    description_localizations=translate_to_all_languages('Удаление Данных С Бота', 'description'),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ])
  async def удалить_дату(self,
    interaction:Interaction,
  ):
    try:
      await interaction.response.defer(ephemeral=True)

      user_id = interaction.user.id
      current_time = time()

      translate_message = self.bot.get_cog("TranslateMessage")
      get_data = self.bot.get_cog("GetData")
      get_invite = self.bot.get_cog("GetInvite")
      send_embed = self.bot.get_cog("SendEmbed")
      if not (translate_message and get_data and get_invite and send_embed):
        return

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.followup.send(await translate_message.translate_message("You write commands so fast,",locale(interaction.locale)), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}
        
      user_settings = await get_data.get_data(user_id,['language'],'users','user_id',interaction.guild)
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

      await interaction.followup.send(await translate_message.translate_message("Все Ваши Сообщения И Вся Ваша Войс Активность Была Удалена С Моей Базы Данных Успешно.", language)+f"\n  Messages: {deleted_messages.split()[-1]}\n  Voice: {deleted_voice.split()[-1]}", ephemeral=True)
              
    except Exception as e:
      invite = await get_invite.invite(interaction.guild)
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      fields = [
        {
          'name':'Пользователь',
          'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline':True
        },
        {
          'name':'Сервер',
          'value':f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "ЛС",
          'inline':True
        },
        {
          'name':'Канал',
          'value':f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else f'[<@{interaction.user.id}>({interaction.user.id} | {interaction.user.name}({interaction.user.display_name})]'}`)",
          'inline':True
        },
        {
          'name':'Ошибка',
          'value':traceback_msg,
          'inline':False
        }
      ]
      await send_embed.send_embed(
        title=f"Произошла ошибка при вводе команды ||**/{interaction.application_command.name}** {' '.join(f'`{option["name"]}` **{option["value"]}** ' for option in interaction.data.get('options',[]))}||",
        description=str(e)[:2048],
        color=Color.red(),
        fields=fields,
        footer_text=f'Ошибка в cogs.commands.🔧other.help',
        author_text='ЕРРОР',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      await interaction.followup.send(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.", ephemeral=True)

  
  setattr(удалить_дату,"extras",{"description": "Позволяет Вам Удалить Все Сохраненные Сообщения и Войс-Активность!"})

def setup(bot:Bot):
  bot.add_cog(DeleteData(bot))