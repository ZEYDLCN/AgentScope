"""SQLAlchemy async engine/session kurulumu (§17)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from agentguard.storage.models import Base


def create_engine(database_url: str) -> AsyncEngine:
    # In-memory SQLite: her yeni bağlantı ayrı bir boş DB açar; testlerde
    # tabloların kaybolmaması için tek bağlantıyı sabitleyen StaticPool
    # kullanılır.
    if ":memory:" in database_url:
        return create_async_engine(
            database_url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_async_engine(database_url, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    """Dev/test kolaylığı: `Base.metadata.create_all`.

    Prod'da bu fonksiyon kullanılmaz; şema değişiklikleri yalnızca Alembic
    ile yapılır (`alembic upgrade head`, §17.1).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
