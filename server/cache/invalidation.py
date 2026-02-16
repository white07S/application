"""Cache invalidation helpers.

Provides namespace-scoped invalidation using Redis SCAN
(safe for production, non-blocking, cursor-based).
"""

from server.logging_config import get_logger

from .keys import namespace_pattern

logger = get_logger(name=__name__)


async def invalidate_namespace(namespace: str) -> int:
    """Delete all cache keys in a namespace.

    Uses SCAN with cursor iteration (non-blocking, safe for production).

    Args:
        namespace: Cache namespace (e.g., "explorer", "stats")

    Returns:
        Number of keys deleted.
    """
    from server.config.redis import get_redis

    redis = get_redis()
    pattern = namespace_pattern(namespace)
    deleted = 0

    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
            deleted += len(keys)
        if cursor == 0:
            break

    if deleted > 0:
        logger.info("Invalidated {} cache keys in namespace '{}'", deleted, namespace)
    else:
        logger.debug("No cache keys found in namespace '{}' to invalidate", namespace)

    return deleted


async def invalidate_all() -> int:
    """Delete ALL cache keys (all namespaces).

    Only deletes keys with the ``cache:`` prefix, so auth keys
    (which use ``auth:``) are not affected.

    Returns:
        Number of keys deleted.
    """
    from server.config.redis import get_redis

    redis = get_redis()
    pattern = "cache:*"
    deleted = 0

    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
            deleted += len(keys)
        if cursor == 0:
            break

    logger.info("Invalidated ALL {} cache keys", deleted)
    return deleted
