import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

import httpx
import msal
import orjson
from fastapi import HTTPException

from server import settings
from .models import AccessResponse
from server.logging_config import get_logger

logger = get_logger(name=__name__)

# Thread pool for blocking MSAL operations
_msal_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="msal")
_GRAPH_TIMEOUT = httpx.Timeout(6.0, connect=3.0)
_ACCESS_CACHE_TTL_SECONDS = 120
_ACCESS_CACHE_STALE_GRACE_SECONDS = 600

# Per-token asyncio.Lock for thundering herd prevention (must stay in-process)
_fetch_locks_guard = asyncio.Lock()
_access_fetch_locks: Dict[str, asyncio.Lock] = {}

cca = msal.ConfidentialClientApplication(
    settings.CLIENT_ID,
    authority=settings.AUTHORITY,
    client_credential=settings.CLIENT_SECRET,
)


def _acquire_graph_token_sync(user_token: str) -> str:
    """Synchronous token acquisition - runs in thread pool."""
    result = cca.acquire_token_on_behalf_of(
        user_assertion=user_token,
        scopes=settings.GRAPH_SCOPES,
    )

    if not result or "error" in result:
        error_msg = result.get("error_description") if result else "Unknown error"
        logger.error("OBO Error: {}", error_msg)
        raise HTTPException(status_code=401, detail="Could not authenticate with backend")

    return result["access_token"]


async def _acquire_graph_token(user_token: str) -> str:
    """Acquire Graph token without blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_msal_executor, _acquire_graph_token_sync, user_token)


async def _fetch_user_groups(client: httpx.AsyncClient, graph_token: str) -> List[str]:
    try:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me/transitiveMemberOf?$select=id",
            headers={"Authorization": f"Bearer {graph_token}"},
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Timed out fetching user groups from Microsoft Graph") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Microsoft Graph is unavailable") from exc

    if response.status_code != 200:
        logger.error("Graph API Error (groups): {}", response.text)
        if response.status_code in {401, 403}:
            raise HTTPException(status_code=401, detail="Could not authorize with Microsoft Graph")
        raise HTTPException(status_code=502, detail="Failed to fetch user groups from Microsoft Graph")

    groups_data = response.json()
    return [g["id"] for g in groups_data.get("value", [])]


async def _fetch_user_profile(client: httpx.AsyncClient, graph_token: str) -> Tuple[str, str]:
    try:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {graph_token}"},
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Timed out fetching user profile from Microsoft Graph") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Microsoft Graph is unavailable") from exc

    if response.status_code != 200:
        logger.error("Graph API Error (profile): {}", response.text)
        if response.status_code in {401, 403}:
            raise HTTPException(status_code=401, detail="Could not authorize with Microsoft Graph")
        raise HTTPException(status_code=502, detail="Failed to fetch user profile from Microsoft Graph")

    profile = response.json()
    return profile.get("displayName", "User"), profile.get("id", "Unknown")


def _cache_key_for_token(user_token: str) -> str:
    return hashlib.sha256(user_token.encode("utf-8")).hexdigest()


def _build_access_response(*, group_ids: List[str], user_name: str) -> AccessResponse:
    has_chat = settings.GROUP_CHAT_ACCESS in group_ids
    has_explorer = settings.GROUP_EXPLORER_ACCESS in group_ids
    has_pipelines_ingestion = settings.GROUP_PIPELINES_INGESTION_ACCESS in group_ids
    has_pipelines_admin = settings.GROUP_PIPELINES_ADMIN_ACCESS in group_ids
    has_dev_data = settings.GROUP_DEV_DATA_ACCESS in group_ids

    return AccessResponse(
        hasChatAccess=has_chat,
        hasExplorerAccess=has_explorer,
        hasPipelinesIngestionAccess=has_pipelines_ingestion,
        hasPipelinesAdminAccess=has_pipelines_admin,
        hasDevDataAccess=has_dev_data,
        user=user_name,
    )


async def _get_cached_access(cache_key: str) -> AccessResponse | None:
    """Check Redis for a fresh (primary TTL) cached access response."""
    from server.config.redis import get_redis

    try:
        redis = get_redis()
        raw = await redis.get(f"auth:access:{cache_key}")
        if raw is not None:
            data = orjson.loads(raw)
            return AccessResponse.model_validate(data)
    except RuntimeError:
        pass  # Redis not initialized
    except Exception as e:
        logger.warning("Redis GET failed for auth cache: {}", e)
    return None


async def _get_stale_cached_access(cache_key: str) -> AccessResponse | None:
    """Check Redis for a stale (grace period) cached access response."""
    from server.config.redis import get_redis

    try:
        redis = get_redis()
        raw = await redis.get(f"auth:stale:{cache_key}")
        if raw is not None:
            data = orjson.loads(raw)
            return AccessResponse.model_validate(data)
    except RuntimeError:
        pass
    except Exception as e:
        logger.warning("Redis GET failed for auth stale cache: {}", e)
    return None


async def _store_cached_access(cache_key: str, access: AccessResponse) -> None:
    """Store access response in Redis with dual-key TTL pattern.

    Primary key (auth:access:) expires after _ACCESS_CACHE_TTL_SECONDS (120s).
    Stale key (auth:stale:) expires after TTL + grace (720s) for fallback
    during Graph API outages.
    """
    from server.config.redis import get_redis

    try:
        redis = get_redis()
        data = orjson.dumps(access.model_dump(mode="json")).decode("utf-8")
        await redis.set(
            f"auth:access:{cache_key}", data, ex=_ACCESS_CACHE_TTL_SECONDS
        )
        stale_ttl = _ACCESS_CACHE_TTL_SECONDS + _ACCESS_CACHE_STALE_GRACE_SECONDS
        await redis.set(
            f"auth:stale:{cache_key}", data, ex=stale_ttl
        )
    except RuntimeError:
        pass  # Redis not initialized
    except Exception as e:
        logger.warning("Redis SET failed for auth cache: {}", e)


async def _get_fetch_lock(cache_key: str) -> asyncio.Lock:
    """Get or create a per-token asyncio.Lock for thundering herd prevention."""
    async with _fetch_locks_guard:
        lock = _access_fetch_locks.get(cache_key)
        if lock is None:
            lock = asyncio.Lock()
            _access_fetch_locks[cache_key] = lock
        return lock


async def get_access_control(user_token: str) -> AccessResponse:
    cache_key = _cache_key_for_token(user_token)
    cached = await _get_cached_access(cache_key)
    if cached is not None:
        return cached

    fetch_lock = await _get_fetch_lock(cache_key)
    async with fetch_lock:
        # Another request may have populated the cache while we were waiting.
        cached_after_wait = await _get_cached_access(cache_key)
        if cached_after_wait is not None:
            return cached_after_wait

        graph_token = await _acquire_graph_token(user_token)

        try:
            async with httpx.AsyncClient(timeout=_GRAPH_TIMEOUT) as client:
                group_ids = await _fetch_user_groups(client, graph_token)
                user_name, user_id = await _fetch_user_profile(client, graph_token)
        except HTTPException as exc:
            # Degrade gracefully for transient IdP outages by using stale cache when available.
            if exc.status_code in {502, 503, 504}:
                stale = await _get_stale_cached_access(cache_key)
                if stale is not None:
                    logger.warning(
                        "Using stale access cache for token hash {} due to Graph error {}",
                        cache_key[:8],
                        exc.status_code,
                    )
                    return stale
            raise

        access = _build_access_response(group_ids=group_ids, user_name=user_name)

        logger.info("--- Access Check for User: {} ({}) ---", user_name, user_id)
        logger.info("User Groups ({}): {}", len(group_ids), group_ids)
        logger.info(
            "Checking Chat Access (Required: {}): {}",
            settings.GROUP_CHAT_ACCESS,
            "GRANTED" if access.hasChatAccess else "DENIED",
        )
        logger.info(
            "Checking Explorer Access (Required: {}): {}",
            settings.GROUP_EXPLORER_ACCESS,
            "GRANTED" if access.hasExplorerAccess else "DENIED",
        )
        logger.info(
            "Checking Pipelines Ingestion Access (Required: {}): {}",
            settings.GROUP_PIPELINES_INGESTION_ACCESS,
            "GRANTED" if access.hasPipelinesIngestionAccess else "DENIED",
        )
        logger.info(
            "Checking Pipelines Admin Access (Required: {}): {}",
            settings.GROUP_PIPELINES_ADMIN_ACCESS,
            "GRANTED" if access.hasPipelinesAdminAccess else "DENIED",
        )
        logger.info(
            "Checking Dev Data Access (Required: {}): {}",
            settings.GROUP_DEV_DATA_ACCESS,
            "GRANTED" if access.hasDevDataAccess else "DENIED",
        )
        logger.info("---------------------------------------------------")

        await _store_cached_access(cache_key, access)
        return access
