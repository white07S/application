"""Service-level caching decorator.

Usage:
    from server.cache import cached

    @cached(namespace="explorer", ttl=3600)
    async def get_function_tree(as_of: date, parent_id: str | None = None, ...):
        ...
"""

from __future__ import annotations

import functools
from typing import Callable, Optional

from server.logging_config import get_logger

from .keys import build_cache_key
from .serialization import deserialize, serialize

logger = get_logger(name=__name__)

DEFAULT_TTL_SECONDS = 3600


def cached(
    namespace: str,
    ttl: int = DEFAULT_TTL_SECONDS,
    key_builder: Optional[Callable[..., str]] = None,
) -> Callable:
    """Decorator that caches async function results in Redis.

    Args:
        namespace: Cache namespace for grouped invalidation (e.g., "explorer", "auth")
        ttl: Time-to-live in seconds (safety net; primary invalidation is explicit)
        key_builder: Optional custom key builder function(func, args, kwargs) -> str.

    Notes:
        - Only works with async functions.
        - If Redis is unavailable, falls through to the original function
          (cache miss behavior, logged as warning).
        - The function return value must be serializable (Pydantic models,
          dicts, lists, tuples of those, or primitives).
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from server.config.redis import get_redis

            try:
                redis = get_redis()
            except RuntimeError:
                logger.warning(
                    "Redis not initialized, skipping cache for {}",
                    func.__name__,
                )
                return await func(*args, **kwargs)

            if key_builder:
                cache_key = key_builder(func, args, kwargs)
            else:
                cache_key = build_cache_key(namespace, func.__name__, args, kwargs)

            # Try cache GET
            try:
                cached_raw = await redis.get(cache_key)
                if cached_raw is not None:
                    logger.debug("Cache HIT: {}", cache_key)
                    return deserialize(cached_raw)
            except Exception as e:
                logger.warning("Redis GET failed for {}: {}", cache_key, e)

            # Cache MISS — call original function
            logger.debug("Cache MISS: {}", cache_key)
            result = await func(*args, **kwargs)

            # Store in cache
            try:
                serialized = serialize(result)
                await redis.set(cache_key, serialized, ex=ttl)
            except Exception as e:
                logger.warning("Redis SET failed for {}: {}", cache_key, e)

            return result

        wrapper._cache_namespace = namespace
        wrapper._cache_ttl = ttl
        wrapper._is_cached = True

        return wrapper
    return decorator
