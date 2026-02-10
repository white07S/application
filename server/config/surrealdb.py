"""SurrealDB connection management.

This module provides an async context manager for SurrealDB connections
with proper error handling and configuration.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from surrealdb import AsyncSurreal
from server.logging_config import get_logger
from server.settings import get_settings

logger = get_logger(name=__name__)


class SurrealDBConnectionError(Exception):
    """Raised when SurrealDB connection fails."""
    pass


@asynccontextmanager
async def get_surrealdb_connection() -> AsyncGenerator[AsyncSurreal, None]:
    """Async context manager for SurrealDB connections.

    Yields:
        AsyncSurreal: Connected and authenticated SurrealDB client.

    Raises:
        SurrealDBConnectionError: If connection or authentication fails.

    Example:
        async with get_surrealdb_connection() as db:
            result = await db.query("SELECT * FROM controls")
            print(result)
    """
    settings = get_settings()
    db = AsyncSurreal(settings.surrealdb_url)

    try:
        # Connect to SurrealDB
        logger.debug(f"Connecting to SurrealDB at {settings.surrealdb_url}")
        await db.connect()

        # Sign in with credentials
        logger.debug(f"Authenticating with user: {settings.surrealdb_user}")
        await db.signin({
            "username": settings.surrealdb_user,
            "password": settings.surrealdb_pass,
        })

        # Use namespace and database
        logger.debug(
            f"Using namespace '{settings.surrealdb_namespace}' "
            f"and database '{settings.surrealdb_database}'"
        )
        await db.use(settings.surrealdb_namespace, settings.surrealdb_database)

        logger.info("SurrealDB connection established successfully")
        yield db

    except Exception as e:
        error_msg = f"Failed to connect to SurrealDB: {str(e)}"
        logger.error(error_msg)
        raise SurrealDBConnectionError(error_msg) from e

    finally:
        # Close the connection
        try:
            await db.close()
            logger.debug("SurrealDB connection closed")
        except Exception as e:
            logger.warning(f"Error closing SurrealDB connection: {str(e)}")


