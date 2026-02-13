"""PostgreSQL async connection management.

Provides an async SQLAlchemy engine and session factory for PostgreSQL
via asyncpg.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from server.logging_config import get_logger

logger = get_logger(name=__name__)

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(
    database_url: str,
    pool_size: int = 5,
    max_overflow: int = 10,
) -> None:
    """Create the global async engine and session factory."""
    global _engine, _async_session_factory
    _engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=False,
    )
    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("PostgreSQL async engine initialized")


def get_engine() -> AsyncEngine:
    """Get the global async engine. Raises if not initialized."""
    if _engine is None:
        raise RuntimeError(
            "PostgreSQL engine not initialized. Call init_engine() first."
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the global async session factory."""
    if _async_session_factory is None:
        raise RuntimeError(
            "Session factory not initialized. Call init_engine() first."
        )
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session.

    Usage::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


@asynccontextmanager
async def get_db_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Standalone async context manager for DB sessions (non-FastAPI use).

    Usage::

        async with get_db_session_context() as session:
            await session.execute(...)
            await session.commit()
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the async engine and release all connections."""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        logger.info("PostgreSQL engine disposed")
    _engine = None
    _async_session_factory = None
