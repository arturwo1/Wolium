import nextcord
from nextcord.ext import commands, tasks
import traceback
import json
from random import choice
from google import genai
from google.genai import types
from datetime import datetime, timezone
from asyncio import sleep
from Utils.config import gemini_api_keys, EMBED_MODEL

class EmojiCollector(commands.Cog):
  def __init__(self, bot):
    self.bot: commands.Bot = bot
    self.index_emojis.start()

  def cog_unload(self):
    self.index_emojis.cancel()

  def _make_client(self) -> genai.Client:
    return genai.Client(api_key=choice(gemini_api_keys))

  async def get_embedding(self, text: str) -> list[float] | None:
    try:
      client = self._make_client()
      result = await client.aio.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=768),
      )
      if result.embeddings:
        return result.embeddings[0].values
    except Exception as e:
      print(f"[EmojiCollector] Gemini embedding error: {type(e).__name__}: {e or 'no details'}")
    return None

  @tasks.loop(hours=1.0)
  async def index_emojis(self):
    while True:
      if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
        try:
          async with self.bot.db_pool.acquire() as conn:
            for guild in self.bot.guilds:
              for emoji in guild.emojis:
                await conn.execute(
                  """
                  INSERT INTO emojis (emoji_id, name, is_animated, guild_id)
                  VALUES ($1, $2, $3, $4)
                  ON CONFLICT (emoji_id) DO UPDATE
                  SET name = EXCLUDED.name,
                      is_animated = EXCLUDED.is_animated,
                      guild_id = EXCLUDED.guild_id
                  """,
                  emoji.id, emoji.name, emoji.animated, guild.id
                )

            rows = await conn.fetch(
              "SELECT emoji_id, name FROM emojis WHERE embedding IS NULL"
            )

          for row in rows:
            embedding = await self.get_embedding(row['name'])
            if embedding is None:
              continue
            if hasattr(self.bot, 'db_pool') and self.bot.db_pool:
              async with self.bot.db_pool.acquire() as conn:
                await conn.execute(
                  "UPDATE emojis SET embedding = $1::vector WHERE emoji_id = $2",
                  json.dumps(embedding), row['emoji_id']
                )

        except Exception as e:
          await self.log_error(f"index_emojis: {e}", traceback.format_exc())
          await sleep(60)
          continue
        break
      else:
        await sleep(10)

  @index_emojis.before_loop
  async def before_index(self):
    await self.bot.wait_until_ready()

  async def get_relevant_emojis(self, message_text: str, limit: int = 20) -> list[str]:
    if not (hasattr(self.bot, 'db_pool') and self.bot.db_pool):
      return []

    embedding = await self.get_embedding(message_text)
    if embedding is None:
      return await self.get_top_emojis(limit)

    try:
      async with self.bot.db_pool.acquire() as conn:
        rows = await conn.fetch(
          """
          SELECT name, emoji_id, is_animated
          FROM emojis
          WHERE embedding IS NOT NULL
          ORDER BY
            (1 - (embedding <=> $1::vector)) * 0.8
            + (usage_count::float / GREATEST((SELECT MAX(usage_count) FROM emojis), 1)) * 0.2
            DESC
          LIMIT $2
          """,
          json.dumps(embedding), limit
        )
        return [f"{int(row['is_animated'])}:{row['name']}:{row['emoji_id']}" for row in rows]
    except Exception as e:
      print(f"[EmojiCollector] get_relevant_emojis error: {e}")
      return []

  async def increment_emoji_usage(self, emoji_id: int):
    if not (hasattr(self.bot, 'db_pool') and self.bot.db_pool):
      return
    try:
      async with self.bot.db_pool.acquire() as conn:
        await conn.execute(
          "UPDATE emojis SET usage_count = usage_count + 1 WHERE emoji_id = $1",
          emoji_id
        )
    except Exception as e:
      print(f"[EmojiCollector] Failed to increment usage for {emoji_id}: {e}")

  async def get_top_emojis(self, limit: int = 50) -> list[str]:
    if not (hasattr(self.bot, 'db_pool') and self.bot.db_pool):
      return []
    try:
      async with self.bot.db_pool.acquire() as conn:
        rows = await conn.fetch(
          "SELECT name, emoji_id, is_animated FROM emojis ORDER BY usage_count DESC LIMIT $1",
          limit
        )
        return [f"{int(row['is_animated'])}:{row['name']}:{row['emoji_id']}" for row in rows]
    except Exception as e:
      print(f"[EmojiCollector] get_top_emojis error: {e}")
      return []

  async def log_error(self, error_msg: str, tb_data: str):
    try:
      log_channel = self.bot.get_channel(1159138280651104256)
      if not log_channel:
        return

      tb_trimmed = tb_data[:5000]
      embed = nextcord.Embed(
        title="EmojiCollector | Error",
        description=str(error_msg)[:500],
        color=nextcord.Colour.red(),
        timestamp=datetime.now(timezone.utc)
      )
      embed.set_author(name="ERROR")

      for i in range(0, len(tb_trimmed), 1000):
        embed.add_field(
          name="Traceback",
          value=f"```py\n{tb_trimmed[i:i+1000]}```",
          inline=False
        )

      await log_channel.send(embed=embed)
    except Exception as e:
      print(f"[EmojiCollector] Failed to log error: {e}")

def setup(bot: commands.Bot):
  bot.add_cog(EmojiCollector(bot))