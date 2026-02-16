"""Redis async connection management.

Provides an async Redis client for caching via redis-py with hiredis parser.
Follows the same lifecycle pattern as postgres.py and qdrant.py.
"""

from redis.asyncio import Redis

from server.logging_config import get_logger

logger = get_logger(name=__name__)

_client: Redis | None = None


async def init_redis(url: str) -> None:
    """Initialize the global async Redis client and verify connectivity.

    Args:
        url: Redis connection URL (e.g., redis://localhost:6379)
    """
    global _client
    _client = Redis.from_url(
        url,
        decode_responses=True,
        protocol=3,
    )
    await _client.ping()
    logger.info("Redis client initialized and connected: {}", url)


def get_redis() -> Redis:
    """Get the global async Redis client. Raises if not initialized."""
    if _client is None:
        raise RuntimeError(
            "Redis client not initialized. Call init_redis() first."
        )
    return _client


async def close_redis() -> None:
    """Close the Redis client connection."""
    global _client
    if _client is not None:
        await _client.aclose()
        logger.info("Redis client closed")
    _client = None
