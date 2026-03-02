"""Redis connection management for async and sync operations.

Provides Redis clients for:
- Caching (DB 0) - async
- Celery broker (DB 1) - sync
- Celery results (DB 2) - sync
- Worker coordination (DB 3) - async
"""

from typing import Optional
import redis
from redis.asyncio import Redis

from server.logging_config import get_logger

logger = get_logger(name=__name__)

# Async clients (for FastAPI)
_cache_client: Optional[Redis] = None  # DB 0
_coord_client: Optional[Redis] = None  # DB 3

# Sync clients (for Celery and worker sync)
_sync_cache_client: Optional[redis.Redis] = None
_sync_coord_client: Optional[redis.Redis] = None


async def init_redis(url: str) -> None:
    """Initialize Redis clients for different purposes.

    Args:
        url: Base Redis connection URL (e.g., redis://localhost:6379)
    """
    global _cache_client, _coord_client

    # Parse base URL to remove any existing database number
    base_url = url.rstrip('/')
    if '/' in base_url.split('://')[-1]:
        base_url = '/'.join(base_url.split('/')[:-1])

    # Cache client (DB 0)
    _cache_client = Redis.from_url(
        f"{base_url}/0",
        decode_responses=True,
        protocol=3,
    )
    await _cache_client.ping()
    logger.info("Redis cache client initialized (DB 0)")

    # Coordination client (DB 3)
    _coord_client = Redis.from_url(
        f"{base_url}/3",
        decode_responses=True,
        protocol=3,
    )
    await _coord_client.ping()
    logger.info("Redis coordination client initialized (DB 3)")


def get_redis() -> Redis:
    """Get the global async Redis cache client (DB 0)."""
    if _cache_client is None:
        raise RuntimeError(
            "Redis client not initialized. Call init_redis() first."
        )
    return _cache_client


def get_redis_coordination() -> Redis:
    """Get the global async Redis coordination client (DB 3)."""
    if _coord_client is None:
        raise RuntimeError(
            "Redis coordination client not initialized. Call init_redis() first."
        )
    return _coord_client


def get_redis_sync_client() -> redis.Redis:
    """Get a sync Redis client for Celery tasks (DB 3).

    This creates a new sync client if needed. Used in Celery workers
    which run in separate processes.
    """
    global _sync_coord_client

    if _sync_coord_client is None:
        from server.settings import get_settings
        settings = get_settings()

        # Parse base URL
        base_url = settings.redis_url.rstrip('/')
        if '/' in base_url.split('://')[-1]:
            base_url = '/'.join(base_url.split('/')[:-1])

        _sync_coord_client = redis.Redis.from_url(
            f"{base_url}/3",
            decode_responses=True,
        )
        _sync_coord_client.ping()
        logger.info("Redis sync coordination client initialized (DB 3)")

    return _sync_coord_client


async def close_redis() -> None:
    """Close all Redis client connections."""
    global _cache_client, _coord_client, _sync_cache_client, _sync_coord_client

    if _cache_client is not None:
        await _cache_client.aclose()
        logger.info("Redis cache client closed")
        _cache_client = None

    if _coord_client is not None:
        await _coord_client.aclose()
        logger.info("Redis coordination client closed")
        _coord_client = None

    if _sync_cache_client is not None:
        _sync_cache_client.close()
        logger.info("Redis sync cache client closed")
        _sync_cache_client = None

    if _sync_coord_client is not None:
        _sync_coord_client.close()
        logger.info("Redis sync coordination client closed")
        _sync_coord_client = None