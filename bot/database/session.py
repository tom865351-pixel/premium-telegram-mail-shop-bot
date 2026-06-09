from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import get_settings
from bot.database.base import Base

settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_restricted BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_note TEXT"))
        await conn.execute(text("ALTER TABLE deposits ADD COLUMN IF NOT EXISTS proof_file_id VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE deposits ADD COLUMN IF NOT EXISTS ocr_status VARCHAR(64)"))
        await conn.execute(text("ALTER TABLE deposits ADD COLUMN IF NOT EXISTS ocr_details TEXT"))
        await conn.execute(text("ALTER TABLE auto_stock_sources ADD COLUMN IF NOT EXISTS last_added_count INTEGER NOT NULL DEFAULT 0"))
        await conn.execute(text("ALTER TABLE auto_stock_sources ADD COLUMN IF NOT EXISTS last_error TEXT"))
        await conn.execute(text("ALTER TABLE auto_stock_sources ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMP WITH TIME ZONE"))


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
