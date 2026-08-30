"""Bootstrap database tables."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import all models so they register with Base.metadata
import app.models  # noqa: F401

from sqlalchemy.ext.asyncio import create_async_engine
from app.core.database import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL_ASYNC",
    "postgresql+asyncpg://tokenguard:tokenguard_dev@host.docker.internal:5432/tokenguard",
)


async def init():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    tables = list(Base.metadata.tables.keys())
    print(f"Created {len(tables)} tables: {', '.join(tables)}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init())
