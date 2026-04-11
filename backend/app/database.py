import re
from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    settings.database_url, echo=settings.sql_echo, connect_args=connect_args
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Synchronous engine for Celery workers
def _to_sync_url(async_url: str) -> str:
    """Convert async DB URL to sync: remove +aiosqlite / +asyncpg drivers."""
    url = re.sub(r"\+aiosqlite", "", async_url)
    url = re.sub(r"postgresql\+asyncpg", "postgresql", url)
    return url


_sync_url = _to_sync_url(settings.database_url)
_sync_connect_args = {}
if _sync_url.startswith("sqlite"):
    _sync_connect_args["check_same_thread"] = False

sync_engine = create_engine(_sync_url, echo=settings.sql_echo, connect_args=_sync_connect_args)
SyncSession = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
