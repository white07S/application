"""Token manager for Microsoft Graph API tokens with auto-refresh.

Provides thread-safe token acquisition and caching using MSAL's
built-in token cache with persistence to disk.
"""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import msal

from server import settings
from server.logging_config import get_logger

logger = get_logger(name=__name__)

# Thread pool for blocking MSAL operations
_token_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="token_mgr")

# Persistent cache file location - store alongside data ingestion path
CACHE_FILE = settings.DATA_INGESTION_PATH / ".msal_token_cache.bin"

# Thread lock for cache operations
_cache_lock = threading.Lock()

# Singleton cache instance
_token_cache: Optional[msal.SerializableTokenCache] = None


def _get_token_cache() -> msal.SerializableTokenCache:
    """Get or create the persistent token cache."""
    global _token_cache

    if _token_cache is not None:
        return _token_cache

    with _cache_lock:
        # Double-check after acquiring lock
        if _token_cache is not None:
            return _token_cache

        _token_cache = msal.SerializableTokenCache()

        # Load existing cache if available
        if CACHE_FILE.exists():
            try:
                _token_cache.deserialize(CACHE_FILE.read_text())
                logger.info("Loaded MSAL token cache from {}", CACHE_FILE)
            except Exception as e:
                logger.warning("Failed to load token cache: {}", e)

        return _token_cache


def _save_cache() -> None:
    """Save the token cache to disk if it has changed."""
    cache = _get_token_cache()

    if cache.has_state_changed:
        with _cache_lock:
            try:
                # Ensure parent directory exists
                CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                CACHE_FILE.write_text(cache.serialize())
                logger.debug("Saved MSAL token cache to {}", CACHE_FILE)
            except Exception as e:
                logger.warning("Failed to save token cache: {}", e)


def _get_cca() -> msal.ConfidentialClientApplication:
    """Get MSAL ConfidentialClientApplication with persistent cache."""
    cache = _get_token_cache()

    return msal.ConfidentialClientApplication(
        settings.CLIENT_ID,
        authority=settings.AUTHORITY,
        client_credential=settings.CLIENT_SECRET,
        token_cache=cache,
    )


def acquire_graph_token_sync(user_token: str) -> Optional[str]:
    """Synchronous token acquisition - may block on network I/O.

    Use acquire_graph_token() for async contexts.

    Args:
        user_token: The user's access token from the frontend

    Returns:
        Graph API access token, or None if acquisition failed
    """
    cca = _get_cca()

    try:
        result = cca.acquire_token_on_behalf_of(
            user_assertion=user_token,
            scopes=settings.GRAPH_SCOPES,
        )

        # Save cache after token operation
        _save_cache()

        if not result or "error" in result:
            error_desc = result.get("error_description", "Unknown error") if result else "No result"
            logger.error("OBO token acquisition failed: {}", error_desc)
            return None

        access_token = result.get("access_token")
        if access_token:
            # Log token info (not the full token for security)
            expires_in = result.get("expires_in", "unknown")
            logger.info(
                "Acquired Graph token: expires_in={}s, token_prefix={}...",
                expires_in,
                access_token[:20] if len(access_token) > 20 else access_token
            )

        return access_token

    except Exception as e:
        logger.exception("Failed to acquire Graph token: {}", e)
        return None


async def acquire_graph_token(user_token: str) -> Optional[str]:
    """Acquire a Microsoft Graph API token using OBO flow (async).

    Uses MSAL's built-in caching and auto-refresh:
    - If cached token is valid, returns it immediately
    - If cached token is expired but refresh token exists, refreshes automatically
    - If no cache, performs OBO exchange

    Args:
        user_token: The user's access token from the frontend

    Returns:
        Graph API access token, or None if acquisition failed
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_token_executor, acquire_graph_token_sync, user_token)


def get_trimmed_token(token: Optional[str], prefix_length: int = 10, suffix_length: int = 10) -> str:
    """Get a trimmed version of a token for logging.

    Args:
        token: The full token
        prefix_length: Number of characters to show at start
        suffix_length: Number of characters to show at end

    Returns:
        Trimmed token like "eyJ0eXAi...2nE" or "(none)" if token is None
    """
    if not token:
        return "(none)"

    if len(token) <= prefix_length + suffix_length + 3:
        return token

    return f"{token[:prefix_length]}...{token[-suffix_length:]}"


def clear_cache() -> None:
    """Clear the token cache (useful for testing or logout)."""
    global _token_cache

    with _cache_lock:
        _token_cache = None
        if CACHE_FILE.exists():
            try:
                CACHE_FILE.unlink()
                logger.info("Cleared MSAL token cache")
            except Exception as e:
                logger.warning("Failed to delete token cache file: {}", e)
