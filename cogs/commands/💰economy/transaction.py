import nextcord
from nextcord import SlashOption, IntegrationType, InteractionContextType
from nextcord.ext import commands
from Utils.suffics import suffics
from datetime import datetime,timezone
from time import time
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

class Transaction(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
  
  @nextcord.slash_command(description="Transfer money to/from bank",
    name_localizations=translate_to_all_languages('economy.transaction_name', 'name'),
    description_localizations=translate_to_all_languages('economy.transaction_desc', 'description'),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ],)
  async def transaction(self,
    interaction: nextcord.Interaction,
    amount: float=SlashOption(name="amount", description="Amount of money to transfer", min_value=100, max_value=1000000, required=True, name_localizations=translate_to_all_languages('economy.amount_name', 'name'), description_localizations=translate_to_all_languages('economy.amount_desc', 'description')),
    destination: str=SlashOption(name="destination", description="Transfer to bank or hand", required=True, name_localizations=translate_to_all_languages('economy.destination_name', 'name'), description_localizations=translate_to_all_languages('economy.transfer_desc', 'description'), choice_localizations=translate_to_all_languages({"In the Bank": "bank_balance", "In the hands": "balance"}, 'choice'), choices={"In the Bank": "bank_balance", "In the hands": "balance"}),
  ):
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

    user_settings = await gd.get_data(user_id, ['language','variation'], 'users', 'user_id', interaction.guild)
    language = user_settings['language']
    user_data = await gd.get_data(user_id, ['bank_balance','balance'], 'user_data', 'user_id', interaction.guild)

    bank_balance = user_data['bank_balance']
    balance = user_data['balance']
    variation = user_settings['variation']

    await interaction.response.defer(ephemeral=True)

    invite = await gi.invite(interaction.guild)

    sbank_balance = await suffics(number=bank_balance, variation=variation)
    sbalance = await suffics(number=balance, variation=variation)
    s_amount = await suffics(number=amount, variation=variation)

    if destination == "bank_balance":
      if amount >= balance:
        await interaction.followup.send(await tm.translate_message("economy.insufficient_hand_balance", language, variables={"amount": s_amount, "balance": sbalance}), ephemeral=True)
        return
      bank_balance += amount
      balance -= amount
      data = {
        'bank_balance': bank_balance,
        'balance': balance,
      }
      await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
      sbank_balance = await suffics(number=bank_balance, variation=variation)
      sbalance = await suffics(number=balance, variation=variation)
      await interaction.followup.send(await tm.translate_message("economy.transfer_to_bank_success", language, variables={"amount": s_amount, "hand": sbalance, "bank": sbank_balance}), ephemeral=True)
    else:
      if amount >= bank_balance:
        await interaction.followup.send(await tm.translate_message("economy.insufficient_bank_balance", language, variables={"amount": s_amount, "balance": sbalance}), ephemeral=True)
        return
      bank_balance -= amount
      balance += amount
      data = {
        'bank_balance': bank_balance,
        'balance': balance,
      }
      await ud.update_data(user_id, data, 'user_data', 'user_id', interaction.guild)
      sbank_balance = await suffics(number=bank_balance, variation=variation)
      sbalance = await suffics(number=balance, variation=variation)
      await interaction.followup.send(await tm.translate_message("economy.transfer_to_hand_success", language, variables={"amount": s_amount, "bank": sbalance, "hand": sbank_balance}), ephemeral=True)

  setattr(transaction,"extras",{"description": "commands.transaction.description"})

def setup(bot: commands.Bot):
  bot.add_cog(Transaction(bot))


