import nextcord
from nextcord import SlashOption
from nextcord.ext import commands
from Utils.suffics import suffics
from datetime import datetime,timezone
from time import time
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown
from traceback import format_exception

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class Text(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
  
  @nextcord.slash_command(
    description="Send message as bot (costs 50₩)",
    name_localizations=translate_to_all_languages('fun.text_name', 'name'),
    description_localizations=translate_to_all_languages('fun.text_desc', 'description'),
  )
  async def text(self,
    interaction: nextcord.Interaction,
    text_content: str=SlashOption(name="message", description="Message text to send",max_length=2000,required=True, name_localizations=translate_to_all_languages('fun.text_content_name', 'name'), description_localizations=translate_to_all_languages('fun.text_content_desc', 'description')),
    channel: nextcord.TextChannel=SlashOption(name="channel", description="Target channel for message",required=False, name_localizations=translate_to_all_languages('fun.channel_name', 'name'), description_localizations=translate_to_all_languages('fun.channel_desc', 'description')),
    message_reply_id: str=SlashOption(name="reply_to_id", description="Message ID to reply to",required=False, name_localizations=translate_to_all_languages('fun.message_id_name', 'name'), description_localizations=translate_to_all_languages('fun.message_id_desc', 'description')),
  ):
    try:
      user_id = interaction.user.id
      current_time = time()
      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      ud = self.bot.get_cog("UpdateData")
      gi = self.bot.get_cog("GetInvite")
      lang = _get_locale(interaction.locale)

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 10:
          await interaction.response.send_message(await tm.translate_message("error.rate_limit", lang, variables={"time": f"<t:{round(last_command_time + 10)}:R>"}), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      user_settings = await gd.get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']
      
      await interaction.response.defer(ephemeral=True)

      user_data = await gd.get_data(user_id,['bank_balance','balance'],'user_data','user_id',interaction.guild)
      
      bank_balance = user_data['bank_balance']
      balance = user_data['balance']
      variation = user_settings['variation']

      if bank_balance<50 or balance<50:
        await interaction.followup.send(await tm.translate_message("fun.insufficient_balance", language), ephemeral=True)
        return
      for ban_word in {"@here","@everyone"}:
        if ban_word in text_content:
          await interaction.followup.send(await tm.translate_message("fun.abuse_attempt_penalty", language), ephemeral=True)
          data = {
            'bank_balance': bank_balance-125,
            'balance': balance-125,
          }
          await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
          return
      if not interaction.guild:
        await interaction.followup.send(await tm.translate_message("fun.guild_only", language), ephemeral=True)
        return
      if not (channel.permissions_for(interaction.user).send_messages) if channel else False:
        await interaction.followup.send(await tm.translate_message("fun.no_write_permission", language), ephemeral=True)
        return
      
      invite = await gi.invite(interaction.guild)

      if channel and message_reply_id:
        try:
          target_message = await channel.fetch_message(message_reply_id)
        except nextcord.NotFound:
          await interaction.followup.send(await tm.translate_message("fun.message_not_found", language, variables={"message_id": message_reply_id}), ephemeral=True)
          return
        except nextcord.Forbidden:
          await interaction.followup.send(await tm.translate_message("fun.no_reply_permission", language), ephemeral=True)
          return
        except nextcord.HTTPException as e:
          await interaction.followup.send(await tm.translate_message("fun.unknown_error", language, variables={"error": str(e)}), ephemeral=True)
          return
        try:
          await target_message.reply(text_content)
        except nextcord.InvalidArgument:
          await interaction.followup.send(await tm.translate_message("fun.invalid_characters", language), ephemeral=True)
          return
        except nextcord.Forbidden:
          await interaction.followup.send(await tm.translate_message("fun.no_write_permission", language), ephemeral=True)
          return
        except nextcord.HTTPException as e:
          await interaction.followup.send(await tm.translate_message("fun.unknown_error", language, variables={"error": str(e)}), ephemeral=True)
          return
        if bank_balance>50:
          sbank_balance = await suffics(number=bank_balance-50, variation=variation)
          await interaction.followup.send(await tm.translate_message("fun.text_sent_reply_bank", language, variables={"message": text_content, "channel": channel.mention, "message_id": message_reply_id, "balance": sbank_balance}), ephemeral=True)
          data = {
            'bank_balance': bank_balance-50
          }
          await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
        else:
          sbalance = await suffics(number=balance-50, variation=variation)
          await interaction.followup.send(await tm.translate_message("fun.text_sent_reply_hand", language, variables={"message": text_content, "channel": channel.mention, "message_id": message_reply_id, "balance": sbalance}), ephemeral=True)
          data = {
            'balance': balance-50
          }
          await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
      elif channel and not message_reply_id:
        try:
          await channel.send(text_content)
        except nextcord.InvalidArgument:
          await interaction.followup.send(await tm.translate_message("fun.invalid_characters", language), ephemeral=True)
          return
        except nextcord.Forbidden:
          await interaction.followup.send(await tm.translate_message("fun.no_write_permission", language), ephemeral=True)
          return
        except nextcord.HTTPException as e:
          await interaction.followup.send(await tm.translate_message("fun.unknown_error", language, variables={"error": str(e)}), ephemeral=True)
          return
        if bank_balance>50:
          sbank_balance = await suffics(number=bank_balance-50, variation=variation)
          await interaction.followup.send(await tm.translate_message("fun.text_sent_channel_bank", language, variables={"message": text_content, "channel": channel.mention, "balance": sbank_balance}), ephemeral=True)
          data = {
            'bank_balance': bank_balance-50
          }
          await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
        else:
          sbalance = await suffics(number=balance-50, variation=variation)
          await interaction.followup.send(await tm.translate_message("fun.text_sent_channel_hand", language, variables={"message": text_content, "channel": channel.mention, "balance": sbalance}), ephemeral=True)
          data = {
            'balance': balance-50
          }
          await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
      else:
        try:
          await interaction.channel.send(text_content)
        except nextcord.InvalidArgument:
          await interaction.followup.send(await tm.translate_message("fun.invalid_characters", language), ephemeral=True)
          return
        except nextcord.Forbidden:
          await interaction.followup.send(await tm.translate_message("fun.no_write_permission", language), ephemeral=True)
          return
        except nextcord.HTTPException as e:
          await interaction.followup.send(await tm.translate_message("fun.unknown_error", language, variables={"error": str(e)}), ephemeral=True)
          return
        if bank_balance>50:
          sbank_balance = await suffics(number=bank_balance-50, variation=variation)
          await interaction.followup.send(await tm.translate_message("fun.text_sent_current_bank", language, variables={"message": text_content, "channel": interaction.channel.mention, "balance": sbank_balance}), ephemeral=True)
          data = {
            'bank_balance': bank_balance-50
          }
          await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
        else:
          sbalance = await suffics(number=balance-50, variation=variation)
          await interaction.followup.send(await tm.translate_message("fun.text_sent_current_hand", language, variables={"message": text_content, "channel": interaction.channel.mention, "balance": sbalance}), ephemeral=True)
          data = {
            'balance': balance-50
          }
          await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
    except Exception as e:
      if "AutoMod" in str(e):
        try:
          await interaction.response.send_message(await tm.translate_message("fun.automod_blocked", language), ephemeral=True)
        except Exception:
          await interaction.followup.send(await tm.translate_message("fun.automod_blocked", language), ephemeral=True)
        return
      traceback_msg = ((''.join(format_exception(type(e), e, e.__traceback__)))[:5000])
      log = nextcord.Embed(
        title=f"ник: {interaction.user.name}#{interaction.user.discriminator}, ID: {interaction.user.id}",
        description=f"User entered command: ||**/text** `text_content`  **{text_content}** `channel`  **{channel}** `message_reply_id`  **{message_reply_id}**||",
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )

      log.set_author(
        name=f"Server ID: {interaction.guild_id if interaction.guild else self.bot.user.name}",
        icon_url=f"{interaction.user.display_avatar.url}"
      )
      if interaction.guild:
        log.add_field(
          name="Server",
          value=f"{interaction.guild.id} | {invite} | {interaction.guild.name}" if interaction.guild else "DM",
          inline=False
        )
      log.add_field(
        name="Channel",
        value=f"<#{interaction.channel.id}>(`{interaction.channel.id}` | `{interaction.channel.name if interaction.guild else 'None'}`)",
        inline=False
      )
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
      try:
        await interaction.response.send_message(await tm.translate_message("error.occurred_logs_saved_review", lang), ephemeral=True)
      except Exception:
        await interaction.followup.send(await tm.translate_message("error.occurred_logs_saved_review", lang), ephemeral=True)
      await self.bot.get_guild(807304463449849938).get_channel(1159138280651104256).send(embed=log)
    
  setattr(text,"extras",{"description": "commands.text.description"})

def setup(bot: commands.Bot):
  bot.add_cog(Text(bot))