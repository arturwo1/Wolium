import nextcord
from nextcord import SlashOption, IntegrationType, InteractionContextType
from nextcord.ext import commands
from cogs.utils.get_invite import GetInvite
from cogs.utils.translate_message import TranslateMessage
from cogs.utils.get_data import GetData
from cogs.utils.update_data import UpdateData
from Utils.suffics import suffics
from datetime import datetime,timezone
from time import time
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

class Transaction(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
  
  @nextcord.slash_command(description="Вывод/Ввод Средств В Банк",
    name_localizations=translate_to_all_languages('transaction', 'name'),
    description_localizations=translate_to_all_languages('Withdrawal/Input of Funds to the Bank', 'description'),
    force_global=True,
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],)
  async def транзакция(self,
    interaction: nextcord.Interaction,
    количество: float=SlashOption(name="количество", description="количество Денег Которое Вы Хотите Вывести С Банка.",min_value=100,max_value=1000000,required=True, name_localizations=translate_to_all_languages('quantity', 'name'), description_localizations=translate_to_all_languages('The amount of money you want to withdraw from the Bank.', 'description')),
    куда: str=SlashOption(name="куда", description="Передача Денег В Банк Или В Руки.",required=True, name_localizations=translate_to_all_languages('where', 'name'), description_localizations=translate_to_all_languages('Transferring Money to Bank or Hands.', 'description'), choice_localizations=translate_to_all_languages({"In the Bank": "bank_balance", "In the hands": "balance"}, 'choice'), choices={"In the Bank": "bank_balance", "In the hands": "balance"}),
  ):
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

    user_settings = await (GetData(self.bot)).get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
    language = user_settings['language']
    user_data = await (GetData(self.bot)).get_data(user_id,['bank_balance','balance'],'user_data','user_id',interaction.guild)
    
    bank_balance = user_data['bank_balance']
    balance = user_data['balance']
    variation = user_settings['variation']

    await interaction.response.defer(ephemeral=True)

    invite = await (GetInvite(self.bot)).invite(interaction.guild)

    sbank_balance = await suffics(number=bank_balance, variation=variation)
    sbalance = await suffics(number=balance, variation=variation)
    sколичество = await suffics(number=количество, variation=variation)

    if куда=="bank_balance":
      if количество>=balance:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Указали:",language)+f" `€{sколичество}`, "+await (TranslateMessage(self.bot)).translate_message(f"Но У Вас В Руках Только:", language)+f" `€{sbalance}`.",ephemeral=True)
        return
      bank_balance += количество
      balance -= количество
      data = {
        'bank_balance': bank_balance,
        'balance': balance,
      }
      await (UpdateData(self.bot)).update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
      sbank_balance = await suffics(number=bank_balance, variation=variation)
      sbalance = await suffics(number=balance, variation=variation)
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Перевели В Банк:",language)+f" `€{sколичество}`, "+await (TranslateMessage(self.bot)).translate_message(f"Теперь В Руках Осталось:",language)+f" `€{sbalance}`, "+await (TranslateMessage(self.bot)).translate_message(f"И В Банке:", language)+f" `€{sbank_balance}`.",ephemeral=True)
    else:
      if количество>=bank_balance:
        await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Указали:",language)+f" `€{sколичество}`, "+await (TranslateMessage(self.bot)).translate_message(f"Но У Вас В Банке Только:", language)+f" `€{sbalance}`.",ephemeral=True)
        return
      bank_balance -= количество
      balance += количество
      data = {
        'bank_balance': bank_balance,
        'balance': balance,
      }
      await (UpdateData(self.bot)).update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
      sbank_balance = await suffics(number=bank_balance, variation=variation)
      sbalance = await suffics(number=balance, variation=variation)
      await interaction.followup.send(await (TranslateMessage(self.bot)).translate_message(f"Вы Перевели В Руки:",language)+f" `€{sколичество}`, "+await (TranslateMessage(self.bot)).translate_message(f"Теперь В Банке Осталось:",language)+f" `€{sbalance}`, "+await (TranslateMessage(self.bot)).translate_message(f"И В Руках:", language)+f" `€{sbank_balance}`.",ephemeral=True)

  setattr(транзакция,"extras",{"description": "Позволяет перекидывать деньги с банка в руки и обратно."})

def setup(bot: commands.Bot):
  bot.add_cog(Transaction(bot))