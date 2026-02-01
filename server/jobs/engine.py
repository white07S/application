"""SQLAlchemy engine configuration for jobs SQLite database.

This is a separate database from the main data (SurrealDB) used for:
- TUS upload tracking
- Upload batch tracking
- Processing job tracking
"""

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from server.config.settings import get_settings
from server.logging_config import get_logger

from .models import Base

logger = get_logger(name=__name__)


def _get_database_path():
    """Get the jobs database path from settings."""
    settings = get_settings()
    return settings.job_tracking_db_path


JOBS_DATABASE_PATH = _get_database_path()


def _ensure_database_directory() -> None:
    """Create the database directory if it doesn't exist."""
    settings = get_settings()
    settings.ensure_job_tracking_dir()


def _set_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
    """Set SQLite pragmas on each new connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.execute("PRAGMA cache_size = -65536")  # 64MB
    cursor.execute("PRAGMA busy_timeout = 30000")
    cursor.close()


def create_jobs_engine() -> Engine:
    """Create and configure the SQLAlchemy engine for jobs database."""
    _ensure_database_directory()

    db_path = _get_database_path()
    database_url = f"sqlite:///{db_path}"

    logger.info("Creating jobs database engine at: {}", db_path)

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    event.listen(engine, "connect", _set_sqlite_pragmas)

    return engine


# Create the engine instance
_engine = None


def get_engine() -> Engine:
    """Get or create the jobs database engine."""
    global _engine
    if _engine is None:
        _engine = create_jobs_engine()
    return _engine


# Session factory
_session_local = None


def get_session_local() -> sessionmaker:
    """Get or create the session factory."""
    global _session_local
    if _session_local is None:
        _session_local = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_local


def get_jobs_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a jobs database session.

    Yields:
        SQLAlchemy Session instance for jobs database.
    """
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_jobs_database() -> None:
    """Initialize the jobs database by creating all tables."""
    _ensure_database_directory()
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Jobs database initialized at: {}", _get_database_path())
