from zipfile import ZipFile
from json import JSONDecodeError, loads, dumps
from datetime import datetime, timedelta
from time import time
from nextcord import slash_command, Interaction, SlashOption, IntegrationType, InteractionContextType, Color, Attachment, WebhookMessage
from nextcord.ext.commands import Cog, Bot
import Utils.translate_to_all_languages
from Utils.config import slash_command_cooldown, гласные, согласные
from traceback import format_exception
from io import BytesIO
from asyncio import to_thread, sleep, Semaphore, wait_for, TimeoutError
from re import compile
from pathlib import PurePosixPath

translate_to_all_languages = Utils.translate_to_all_languages.translate_to_all_languages

def _get_locale(locale: str) -> str:
  if locale in ('en-US', 'en-GB'):
    return 'en'
  if locale == 'es-ES':
    return 'es'
  if locale == 'sv-SE':
    return 'sv'
  return locale

ALLOWED_CHARS = set(" \t\n.,!?-()[]{}\"':;")

def parse_dt(ts):
  if not ts:
    return datetime.now()
  if isinstance(ts, datetime):
    return ts
  if isinstance(ts, str):
    ts = ts.strip().replace("Z", "+00:00")
    try:
      return datetime.fromisoformat(ts)
    except ValueError:
      return datetime.now()
  return datetime.now()

class InsertData(Cog):
  def __init__(self,bot:Bot):
    self.bot:Bot=bot
    self.semaphores_limit = 8
    self.semaphores: dict[tuple[int, int], Semaphore] = {}
    self.last_msg: dict[int, WebhookMessage] = {}

  async def give_cooldown(self, user_id: int, ts: int | None = None):
    if ts is None:
      ts = int(time() - 31*24*60*60)
    if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
      async with self.bot.db_pool.acquire() as conn:
        wquery = "SELECT timestamp FROM cooldowns WHERE user_id = $1 AND command = $2"
        equery = "INSERT INTO cooldowns (user_id, command, timestamp) VALUES ($1, $2, $3) ON CONFLICT (user_id, command) DO UPDATE SET timestamp = EXCLUDED.timestamp"
        insert_data = await conn.fetchval(wquery, user_id, 'insert_data')
        if insert_data is None:
          await conn.execute(equery, user_id, 'insert_data', ts)
          insert_data = await conn.fetchval(wquery, user_id, 'insert_data')
        return insert_data, equery
    else:
      return None, None

  async def import_zip_streaming(self, interaction:Interaction, file: Attachment, language: str):
    tm = self.bot.get_cog("TranslateMessage")

    zip_bytes = await wait_for(file.read(), timeout=120)

    total_uncompressed = 0
    file_count = 0
    channels_meta: dict[str, dict] = {}

    message_count = 0
    real_message_count = 0

    v_re = compile(f"[{гласные}]{3}")
    c_re = compile(f"[{согласные}]{3}")
    only_noise_re = compile(r"^[\W\d_]+$")

    BATCH_ROWS = 500
    rows: list[tuple] = []

    insert_query = """
      INSERT INTO messages
      (guild_id, channel_id, user_id, date_time, content, message_url, attachments)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
    """

    def is_gibberish(text: str) -> bool:
      s = text.strip()
      if len(s) < 3:
        return True

      letters = 0
      bad = 0
      nums = 0

      for ch in s:
        if ch.isalpha():
          letters += 1
        if ch.isdigit():
          nums += 1
        if (not ch.isalnum()) and (ch not in ALLOWED_CHARS):
          bad += 1

      if letters == 0:
        return True

      if bad / len(s) > 0.35:
        return True

      if nums / len(s) > 0.45:
        return True

      return False

    def should_skip_text(text: str) -> bool:
      if len(text) < 3:
        return True
      if v_re.search(text) or c_re.search(text):
        return True
      if only_noise_re.match(text):
        return True
      if is_gibberish(text):
        return True
      return False

    async def flush(conn):
      nonlocal rows
      if not rows:
        return
      await conn.executemany(insert_query, rows)
      rows = []

    async with self.bot.db_pool.acquire() as conn:
      async with conn.transaction():
        with ZipFile(BytesIO(zip_bytes), "r") as z:
          infos = z.infolist()

          for info in infos:
            file_count += 1
            total_uncompressed += info.file_size
            if total_uncompressed > 200 * 1024**2:
              await interaction.followup.send(
                await tm.translate_message("privacy.zip_too_large", language, variables={"size": f"{total_uncompressed/1024**2:.2f}MB"}),
                ephemeral=True
              )
              return 0, 0
            if file_count > 100000:
              await interaction.followup.send(
                await tm.translate_message("privacy.zip_too_many_files", language),
                ephemeral=True
              )
              return 0, 0

          if self.last_msg.get(interaction.user.id):
            await self.last_msg[interaction.user.id].edit(content=await tm.translate_message("privacy.extracting_channels", language))

          for info in infos:
            name = info.filename
            if not (name.startswith(("messages/", "Сообщения/", "Messages/")) and name.endswith("channel.json")):
              continue
            parts = PurePosixPath(name).parts
            if len(parts) < 3:
              continue
            dir_name = parts[1]
            with z.open(info) as f:
              raw = await to_thread(f.read)

            try:
              channels_meta[dir_name] = await to_thread(lambda: loads(raw.decode("utf-8")))
            except JSONDecodeError:
              channels_meta[dir_name] = {}

          has_messages = False
          deleted = False

          if self.last_msg.get(interaction.user.id):
            await self.last_msg[interaction.user.id].edit(content=await tm.translate_message("privacy.importing_messages", language))
          last_update_time = time()

          for info in infos:
            name = info.filename
            if not (name.startswith(("messages/", "Сообщения/", "Messages/")) and name.endswith("messages.json")):
              continue

            has_messages = True

            if not deleted:
              deleted = True
              await conn.execute("DELETE FROM messages WHERE user_id = $1;", interaction.user.id)

            parts = PurePosixPath(name).parts
            if len(parts) < 3:
              continue

            dir_name = parts[1]
            channel_data = channels_meta.get(dir_name, {}) or {}

            guild = channel_data.get("guild", {}) if isinstance(channel_data, dict) else {}
            guild_id = guild.get("id") if isinstance(guild, dict) else None
            channel_id = channel_data.get("id") if isinstance(channel_data, dict) else None

            with z.open(info) as f:
              raw = await to_thread(f.read)

            try:
              messages_content = await to_thread(lambda: loads(raw.decode("utf-8")))
            except JSONDecodeError:
              continue

            if not isinstance(messages_content, list):
              continue

            for msg in messages_content:
              message_count += 1
              if not isinstance(msg, dict):
                continue

              attachments: str = msg.get("Attachments", "")
              attachments = [
                url.strip()
                for url in attachments.split()
                if url.strip()
              ]
              content = msg.get("Contents", None)
              text = (content or "").strip()

              if not text and not attachments:
                continue
              if text and should_skip_text(text):
                continue

              timestamp = msg.get("Timestamp", None)
              message_id = msg.get("ID", None)

              row = (
                int(guild_id) if isinstance(guild_id, str) and guild_id.isdigit() else None,
                int(channel_id) if isinstance(channel_id, str) and channel_id.isdigit() else None,
                interaction.user.id,
                parse_dt(timestamp),
                text,
                (
                  f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
                  if all([guild_id, channel_id, message_id])
                  else f"https://discord.com/channels/@me/{channel_id}/{message_id}"
                  if all([channel_id, message_id])
                  else None
                ),
                dumps(attachments),
              )

              rows.append(row)
              real_message_count += 1

              if len(rows) >= BATCH_ROWS:
                await flush(conn)
                await sleep(0.05)

            if time() - last_update_time > 5:
              last_update_time = time()
              if self.last_msg.get(interaction.user.id):
                await self.last_msg[interaction.user.id].edit(content=await tm.translate_message("privacy.importing_progress", language, variables={"count": str(message_count)}))

          if self.last_msg.get(interaction.user.id):
            await self.last_msg[interaction.user.id].edit(content=await tm.translate_message("privacy.import_finalizing", language, variables={"count": str(message_count)}))
          await flush(conn)


          if not has_messages:
            await interaction.followup.send(
              await tm.translate_message("privacy.zip_missing_structure", language),
              ephemeral=True
            )
            return 0, 0

    return real_message_count, message_count

  @slash_command(
    description="Import messages from Discord archive",
    name_localizations=translate_to_all_languages('privacy.insert_name', 'name'),
    description_localizations=translate_to_all_languages('privacy.insert_desc', 'description'),
    integration_types=[
      IntegrationType.user_install,
      IntegrationType.guild_install,
    ],
    contexts=[
      InteractionContextType.guild,
      InteractionContextType.bot_dm,
      InteractionContextType.private_channel,
    ])
  async def insert_data(self,
    interaction:Interaction,
    file: Attachment=SlashOption(name="file", description="ZIP archive with your Discord data",required=True, name_localizations=translate_to_all_languages('privacy.file_param', 'name'), description_localizations=translate_to_all_languages('privacy.file_desc', 'description')),
  ):
    try:
      await interaction.response.defer(ephemeral=True)

      user_id = interaction.user.id
      current_time = time()

      tm = self.bot.get_cog("TranslateMessage")
      gd = self.bot.get_cog("GetData")
      gi = self.bot.get_cog("GetInvite")
      se = self.bot.get_cog("SendEmbed")

      lang = _get_locale(interaction.locale)

      if user_id in slash_command_cooldown:
        last_command_time = slash_command_cooldown[user_id]['time']
        if current_time - last_command_time < 120:
          await interaction.followup.send(await tm.translate_message("error.rate_limit", lang, variables={"time": f"<t:{round(last_command_time+120)}:R>"}), ephemeral=True)
          return
        else:
          slash_command_cooldown[user_id]['time'] = current_time
      else:
        slash_command_cooldown[user_id] = {'time': current_time}

      user_settings = await gd.get_data(user_id,['language','variation'],'users','user_id',interaction.guild)
      language = user_settings['language']

      try:
        insert_data, equery = await wait_for(self.give_cooldown(user_id), timeout=5)
      except TimeoutError:
        await interaction.followup.send(await tm.translate_message("privacy.database_timeout", lang), ephemeral=True)
        return
      if insert_data is None or equery is None:
        return

      if file.size > 50*1024**2:
        await interaction.followup.send(await tm.translate_message("privacy.zip_exceeds_50mb", language, variables={"size": f"{file.size/1024**2:.2f}MB"}), ephemeral=True)
        return

      time_since_last_usage=time()-insert_data
      if time_since_last_usage<(31*24*60*60):
        remaining = str(timedelta(seconds=((31*24*60*60)-time_since_last_usage)))[:-4]
        await interaction.followup.send(await tm.translate_message("privacy.cooldown_active", language, variables={"time": remaining}), ephemeral=True)
        return
      else:
        if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
          async with self.bot.db_pool.acquire() as conn:
            await conn.execute(equery, user_id, 'insert_data', int(time()))
        else:
          return

      invite = await gi.invite(interaction.guild)

      key = (interaction.guild.id if interaction.guild else 0, interaction.user.id)
      msg = await tm.translate_message("privacy.queue_wait_message", language)
      followup_sent = None
      attempts = 0

      self.last_msg[user_id] = await interaction.followup.send(await tm.translate_message("privacy.extraction_start", language), wait=True, ephemeral=True)

      while True:
        semaphore = self.semaphores.get(key)
        if semaphore is not None:
          break

        if len(self.semaphores) < self.semaphores_limit:
          semaphore = self.semaphores[key] = Semaphore(1)
          break

        if followup_sent is None:
          followup_sent = await interaction.followup.send(msg, wait=True, ephemeral=True)

        attempts += 1
        await followup_sent.edit(
          content=msg+"\n"+await tm.translate_message("privacy.queue_attempt", language, variables={"attempts": str(attempts), "limit": str(self.semaphores_limit), "occupied": str(len(self.semaphores))})
        )

        if attempts >= 10:
          await self.give_cooldown(user_id, ts=int(time()-60))
          await interaction.followup.send(
            await tm.translate_message("privacy.queue_too_long", language),
            ephemeral=True
          )
          return
        await sleep(5)

      try:
        async with semaphore:
          real_count, total_count = await self.import_zip_streaming(interaction, file, language)
          if total_count == 0:
            return

          await interaction.followup.send(
            await tm.translate_message("privacy.import_success", language, variables={"total": str(total_count), "real": str(real_count)}),
            ephemeral=True
          )
      finally:
        self.last_msg.pop(user_id, None)
        if self.semaphores.get(key) is semaphore:
          self.semaphores.pop(key, None)

    except Exception as e:
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
        title=f"Error occurred while executing command ||**/{interaction.application_command.name}** {' '.join(f'`{option['name']}` **{option['value']}** ' for option in interaction.data.get('options',[]))}||",
        description=str(e)[:2048],
        color=Color.red(),
        fields=fields,
        footer_text=f'Error in cogs.commands.🛡️privacy.insert_data',
        author_text='ERROR',
        author_icon=interaction.user.display_avatar.url,
        channel_id=1159138280651104256
      )
      lang = _get_locale(interaction.locale)
      await interaction.followup.send(await tm.translate_message("error.occurred_logs_saved_review", lang), ephemeral=True)
      await self.give_cooldown(user_id, ts=int(time()-60))

  setattr(insert_data,"extras",{"description": "commands.insert_data.description"})

def setup(bot:Bot):
  bot.add_cog(InsertData(bot))
