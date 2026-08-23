from asyncio import sleep, to_thread
from subprocess import run
from PIL import UnidentifiedImageError
from nextcord import Attachment, File, FFmpegPCMAudio, Interaction
from nextcord.ext import commands
from Utils.sstv_encoder import encode_to_wav, build_waveform
from aiohttp import ClientSession, FormData
from json import dumps

class SSTV(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  async def sstv(self, interaction: Interaction, images: list[Attachment], mode: str, output: str):
    limit = interaction.guild.filesize_limit if interaction.guild else 10 * 1024 * 1024
    user_id = interaction.user.id

    tm = self.bot.get_cog("TranslateMessage")
    gd = self.bot.get_cog("GetData")

    user_settings = await gd.get_data(user_id, ['language'], 'users', 'user_id', interaction.guild)
    language = user_settings['language']

    if output == "vc":
      if interaction.guild is None:
        await interaction.followup.send(await tm.translate_message("sstv.error.guild_only", language))
        return

      member = interaction.guild.get_member(interaction.user.id)
      if not member or not member.voice or not member.voice.channel:
        await interaction.followup.send(await tm.translate_message("sstv.error.join_vc", language))
        return

      vc = interaction.guild.voice_client
      connected_now = vc is None
      if vc is None:
        try:
          vc = await member.voice.channel.connect()
        except Exception:
          await interaction.followup.send(await tm.translate_message("sstv.error.vc_connect_failed", language))
          return
      elif vc.channel != member.voice.channel:
        await interaction.followup.send(await tm.translate_message("sstv.error.already_in_vc", language))
        return

    for image in images:
      if image.size > limit:
        await interaction.followup.send(await tm.translate_message("sstv.error.image_too_big", language))
        return

      image_bytes = await image.read()

      try:
        wav = await to_thread( encode_to_wav, image_bytes, mode=mode)
      except UnidentifiedImageError:
        await interaction.followup.send(await tm.translate_message("sstv.error.invalid_image", language))
        return

      if len(wav.getbuffer()) > limit:
        await interaction.followup.send(await tm.translate_message("sstv.error.sstv_too_big", language))
        return

      file = File(wav, filename=f"{image.filename}.wav")

      if output == "file":
        try:
          await interaction.followup.send(file=file)
        except Exception:
          await interaction.followup.send(file=file, ephemeral=True)
        return

      if output == "voice":
        waveform, duration = await to_thread(build_waveform, wav)

        wav.seek(0)

        proc = await to_thread(
          run,
          [
            "ffmpeg", "-y",
            "-i", "pipe:0",
            "-ac", "1",
            "-ar", "48000",
            "-c:a", "libopus",
            "-b:a", "32k",
            "-f", "ogg",
            "pipe:1",
          ],
          input=wav.read(),
          stdout=-1,
          stderr=-1,
          check=True,
        )

        ogg_bytes = proc.stdout

        if len(ogg_bytes) > limit:
          await interaction.followup.send(await tm.translate_message("sstv.error.voice_too_big", language))
          return

        form = FormData()
        form.add_field(
          "payload_json",
          dumps({
            "flags": 8192,
            "attachments": [{
              "id": "0",
              "filename": f"{image.filename}.ogg",
              "duration_secs": duration,
              "waveform": waveform,
            }],
          }),
          content_type="application/json",
        )
        form.add_field("files[0]", ogg_bytes, filename=f"{image.filename}.ogg", content_type="audio/ogg")

        url = f"https://discord.com/api/v10/webhooks/{interaction.application_id}/{interaction.token}?wait=true"

        async with ClientSession() as session:
          async with session.post(url, data=form) as resp:
            if resp.status not in (200, 201):
              await interaction.followup.send((await tm.translate_message("sstv.error.voice_send_failed", language)).format(status=resp.status))

        return

      if output == "vc":
        if vc.is_playing():
          vc.stop()

        wav.seek(0)
        vc.play(FFmpegPCMAudio(wav, pipe=True))

        while vc.is_playing():
          await sleep(1)

        if connected_now:
          await vc.disconnect()

        await interaction.followup.send(await tm.translate_message("sstv.status.playback_finished", language))

        return

def setup(bot:commands.Bot):
  bot.add_cog(SSTV(bot))