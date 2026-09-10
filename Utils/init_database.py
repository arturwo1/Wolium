from asyncpg import create_pool
from Utils.config import DATABASE_CONFIG

async def init_database():
  return await create_pool(**DATABASE_CONFIG)