"""SQLAlchemy engine configuration for SQLite database."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from server.settings import DATA_INGESTION_PATH

# Database path configuration
DATABASE_DIR = DATA_INGESTION_PATH / "database"
DATABASE_PATH = DATABASE_DIR / "main.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# SQLite PRAGMA settings
# Cache size in pages (negative value = KB, so -65536 = 64MB)
SQLITE_CACHE_SIZE = -65536


def _ensure_database_directory() -> None:
    """Create the database directory if it doesn't exist."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)


def _set_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
    """Set SQLite pragmas on each new connection.

    Args:
        dbapi_connection: The raw DBAPI connection.
        connection_record: The connection record (unused but required by event signature).
    """
    cursor = dbapi_connection.cursor()
    # Enable foreign key constraint enforcement
    cursor.execute("PRAGMA foreign_keys = ON")
    # Use Write-Ahead Logging for better concurrency
    cursor.execute("PRAGMA journal_mode = WAL")
    # NORMAL synchronous mode - good balance of safety and performance
    cursor.execute("PRAGMA synchronous = NORMAL")
    # Set cache size to 64MB (negative value means KB)
    cursor.execute(f"PRAGMA cache_size = {SQLITE_CACHE_SIZE}")
    # Set busy timeout to 30 seconds to handle lock contention
    cursor.execute("PRAGMA busy_timeout = 30000")
    cursor.close()


def create_database_engine() -> Engine:
    """Create and configure the SQLAlchemy engine.

    Returns:
        Configured SQLAlchemy Engine instance.
    """
    _ensure_database_directory()

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Register event listener to set pragmas on connect
    event.listen(engine, "connect", _set_sqlite_pragmas)

    return engine


# Create the engine instance
engine = create_database_engine()

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session.

    Yields:
        SQLAlchemy Session instance.

    Example:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
