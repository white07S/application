"""Database engine for job tracking — delegates to shared PostgreSQL engine.

All job tables (TusUpload, UploadBatch, UploadIdSequence, ProcessingJob)
now live alongside domain tables in PostgreSQL. Alembic manages the schema.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from server.config.postgres import get_db_session, get_session_factory
from server.logging_config import get_logger

logger = get_logger(name=__name__)


async def get_jobs_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session.

    This is a thin wrapper around the shared Postgres session factory.
    """
    async for session in get_db_session():
        yield session


def get_session_factory_for_background():
    """Return the async session factory for background tasks.

    Background tasks (e.g. ingestion) create their own sessions
    outside the request lifecycle.
    """
    return get_session_factory()


async def init_jobs_database() -> None:
    """No-op — Alembic manages all table creation."""
    logger.debug("init_jobs_database is a no-op; Alembic manages schema")


async def shutdown_jobs_engine() -> None:
    """No-op — engine lifecycle is managed by config/postgres.py."""
    logger.debug("shutdown_jobs_engine is a no-op; engine lifecycle in config/postgres.py")
