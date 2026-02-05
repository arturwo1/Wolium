from nextcord.ext import commands
from nextcord import slash_command, SlashOption, Interaction, Member, Embed, Colour, Permissions
from nextcord.errors import Forbidden
from datetime import datetime, timezone
from time import time
import Utils.translate_to_all_languages
from cogs.utils.get_invite import GetInvite
from cogs.utils.translate_message import TranslateMessage
from Utils.config import servers_with_no_acces_for_bot, users_with_no_acces_for_bot, slash_command_cooldown
from traceback import format_exception
from cogs.utils.send_embed import SendEmbed
from cogs.utils.get_data import GetData
from asyncio import sleep

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class DeleteMessage(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot
  
  @slash_command(default_member_permissions=Permissions(send_messages=True, manage_messages=True),
  description="Команда Для Удаления Сообщений.",
  name_localizations=translate_to_all_languages('purge', 'name'),
  description_localizations=translate_to_all_languages('Command For Deleting Messages.', 'description'))
  async def удалить(self,
    interaction: Interaction,
    количество: int=SlashOption(name="количество", description="Количество Удаленных Сообщений.",required=True, name_localizations=translate_to_all_languages('amount', 'name'), description_localizations=translate_to_all_languages('Amount Of Deleted Messages.', 'description'), min_value=1, max_value=100),
    причина: str=SlashOption(name="причина", description="Причина Варна.",required=False, name_localizations=translate_to_all_languages('причина', 'name'), description_localizations=translate_to_all_languages('Reason for Deleting Messages.', 'description'), max_length=256),
    участник: Member=SlashOption(name="участник", description="Ник Участника Которого Хотите Заварнить.",required=False, name_localizations=translate_to_all_languages('участник', 'name'), description_localizations=translate_to_all_languages('Member\'s Nickname Whose Messages You Want to Delete.', 'description')),
    одновременно: bool=SlashOption(name="одновременно", description="Все Сообщения Будут Удалены Одновременно? Тогда Лимит 2 Недели.", name_localizations=translate_to_all_languages('simultaneously', 'name'), description_localizations=translate_to_all_languages('Will all messages be deleted at the same time? Then the Limit is 2 Weeks.', 'description'), default=True),
  ):
    try:
      if ((interaction.guild.id if interaction.guild else 0) in servers_with_no_acces_for_bot or interaction.user.id in users_with_no_acces_for_bot):
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://sites.google.com/view/arturwolium/main-page/rules) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv' ), ephemeral=True)
        return
      user_id = interaction.user.id
      current_time = time()

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"You write commands so fast,",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv')+f" **<t:{round(last_command_time+10)}:R>** "+await (TranslateMessage(self.bot)).translate_message(f"you can write commands.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}
      if interaction.guild:
        guild_settings = await (GetData(self.bot)).get_data(interaction.guild.id,['banned'],'guilds','guild_id',interaction.guild)
      user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation','banned'],'users','user_id',interaction.guild)
      language = user_settings['language']

      if user_settings['banned'] or (guild_settings['banned'] if interaction.guild else False):
        await interaction.response.send_message(await (TranslateMessage(self.bot)).translate_message(f"Вы Или Этот Сервер Были Заблокированы За Нарушение [**`Правил`**](https://sites.google.com/view/arturwolium/main-page/rules) Бота!\nОбсудите Это На Основном Сервере Бота(***`https://discord.gg/MXupeAApza`***).",language), ephemeral=True)
        servers_with_no_acces_for_bot.append(interaction.guild.id)
        users_with_no_acces_for_bot.append(user_id)
        return
      
      await interaction.response.defer(ephemeral=True)

      if not interaction.guild:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Эта команда работает только на серверах.",language), ephemeral=True)
        return
      if not interaction.guild.me.guild_permissions.manage_messages:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У меня нет прав на управление сообщениями.",language), ephemeral=True)
        return
      if not interaction.user.guild_permissions.manage_messages:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"У тебя нет прав на управление сообщениями.",language), ephemeral=True)
        return
      
      invite = await (GetInvite(self.bot)).invite(interaction.guild)
      
      try:
        if участник:
          messages = await interaction.channel.purge(limit=количество, check=lambda m: m.author.id == участник.id, bulk=одновременно)
        else:
          messages = await interaction.channel.purge(limit=количество, bulk=одновременно)
      except Forbidden:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Нет Прав.",language), ephemeral=True)
        return
      except Exception as e:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Ошибка:",language)+f" **```py\n{e}```**", ephemeral=True)
        return
      
      причина = str(причина)
      deleted_messages_embed = Embed(
        title=await (TranslateMessage(self.bot)).translate_message(f"Сообщения Удалены",language),
        description=await (TranslateMessage(self.bot)).translate_message("Было Успешно Удалено",language)+f" **`{len(messages)}`** "+((await (TranslateMessage(self.bot)).translate_message("Сообщений",language)+f" **{участник.mention}**.") if участник else "."),
        color=Colour.green(),
        timestamp=datetime.now(timezone.utc)
      )
      deleted_messages_embed.add_field(
        name=await (TranslateMessage(self.bot)).translate_message(f"Причина",language),
        value=причина,
      )
      deleted_messages_embed.add_field(
        name=await (TranslateMessage(self.bot)).translate_message(f"Удалено Сообщений",language),
        value=f"**`{len(messages)}`**",
      )
      if участник:
        deleted_messages_embed.add_field(
          name=await (TranslateMessage(self.bot)).translate_message(f"Участник",language),
          value=f"**{участник.mention}**",
        )
      deleted_messages_embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
      deleted_messages_embed.set_footer(text=await (TranslateMessage(self.bot)).translate_message(f"Удалено",language)+f" {len(messages)} "+await (TranslateMessage(self.bot)).translate_message(f"Cообщений",language))
      await interaction.followup.send(embed=deleted_messages_embed, ephemeral=True)

      fields = [
        {
          'name':'Модератор',
          'value':f"{interaction.user.id} | {interaction.user.mention} | {interaction.user.name}",
          'inline':True
        },
        ({
          'name':'Модератор удалил сообщения пользователя',
          'value':f"{участник.id} | {участник.mention} | {участник.name}",
          'inline':True
        } if участник else {}),
        {
          'name':'Причина',
          'value':причина,
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
        }
      ]
      await (SendEmbed(self.bot)).send_embed(
        title="Ввод команды",
        description=f"Пользователь ввёл: ||**/{interaction.application_command.name}** {' '.join(f'`{option['name']}` **{option['value']}** ' for option in interaction.data.get('options',[]))}||",
        color=Colour.yellow(),
        fields=fields,
        footer_text=interaction.application_command.name,
        author_text=interaction.user.name,
        author_icon=interaction.user.display_avatar.url,
        channel_id=1348577723097808977
      )

      guild_config = await (GetData(self.bot)).get_data(interaction.guild.id,['mod_log_channel'],'guild_settings','guild_id',interaction.guild)
      mod_log_channel = guild_config['mod_log_channel']
      if mod_log_channel and interaction.guild and interaction.guild.get_channel(mod_log_channel):
        mod_lang = interaction.guild_locale if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'en' if interaction.guild_locale =='en-US' or interaction.guild_locale =='en-GB' and interaction.guild_locale !='es-ES' and interaction.guild_locale !='sv-SE' else 'es' if interaction.guild_locale !='en-US' and interaction.guild_locale !='en-GB' and interaction.guild_locale =='es-ES' and interaction.guild_locale !='sv-SE' else 'sv'
        fields = [({
            'name':await (TranslateMessage(self.bot)).translate_message('Модератор удалил сообщения пользователя',mod_lang),
            'value':f"{участник.id} | {участник.mention} | {участник.name}",
            'inline':False
          } if участник else {}),
          {
            'name':await (TranslateMessage(self.bot)).translate_message('Причина',mod_lang),
            'value':причина,
            'inline':True
          },
          {
            'name':await (TranslateMessage(self.bot)).translate_message('Количество',mod_lang),
            'value':f"**`{len(messages)}`**",
            'inline':True
          },
        ]
        await (SendEmbed(self.bot)).send_embed(
          title=await (TranslateMessage(self.bot)).translate_message("Удаление сообщений",mod_lang),
          description=f"**{interaction.user.mention}** "+await (TranslateMessage(self.bot)).translate_message("Удалил",mod_lang)+f" **`{len(messages)}`** "+await (TranslateMessage(self.bot)).translate_message("сообщений",mod_lang)+(" "+await (TranslateMessage(self.bot)).translate_message("От",mod_lang)+f" **{участник.mention}**," if участник else ', ')+await (TranslateMessage(self.bot)).translate_message("По Причине",mod_lang)+f" {причина}",
          color=Colour.red(),
          fields=fields,
          footer_text=await (TranslateMessage(self.bot)).translate_message("Удаление сообщений",mod_lang),
          author_text=interaction.user.name,
          author_icon=interaction.user.display_avatar.url,
          guild_id=interaction.guild.id,
          channel_id=mod_log_channel
        )
    except Exception as e:
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
      await (SendEmbed(self.bot)).send_embed(
        title=f"Произошла ошибка при вводе команды /{interaction.application_command.name}",
        description=str(e)[:2048],
        color=Colour.red(),
        fields=fields,
        footer_text=f'Ошибка в cogs.commands.🔧other.help',
        author_text='ЕРРОР',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      await interaction.followup.send(await(TranslateMessage(self.bot)).translate_message(f"Произошла Ошибка, Логи Ошибки Сохранены, В Ближайшее Время Их Будут Рассматривать.",interaction.locale if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'en' if interaction.locale=='en-US' or interaction.locale=='en-GB' and interaction.locale!='es-ES' and interaction.locale!='sv-SE' else 'es' if interaction.locale!='en-US' and interaction.locale!='en-GB' and interaction.locale=='es-ES' and interaction.locale!='sv-SE' else 'sv'), ephemeral=True)

  setattr(удалить,"extras",{"description": "Эта Команда Позволяет Удалять Сообщения Пользователей."})

def setup(bot:commands.Bot):
  bot.add_cog(DeleteMessage(bot))