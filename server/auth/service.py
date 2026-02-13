import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

import httpx
import msal
from fastapi import HTTPException

from server import settings
from .models import AccessResponse
from server.logging_config import get_logger

logger = get_logger(name=__name__)

# Thread pool for blocking MSAL operations
_msal_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="msal")

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
    response = await client.get(
        "https://graph.microsoft.com/v1.0/me/transitiveMemberOf?$select=id",
        headers={"Authorization": f"Bearer {graph_token}"},
    )

    if response.status_code != 200:
        logger.error("Graph API Error (groups): %s", response.text)
        raise HTTPException(status_code=500, detail="Failed to fetch user groups")

    groups_data = response.json()
    return [g["id"] for g in groups_data.get("value", [])]


async def _fetch_user_profile(client: httpx.AsyncClient, graph_token: str) -> Tuple[str, str]:
    response = await client.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {graph_token}"},
    )

    if response.status_code != 200:
        logger.error("Graph API Error (profile): %s", response.text)
        raise HTTPException(status_code=500, detail="Failed to fetch user profile")

    profile = response.json()
    return profile.get("displayName", "User"), profile.get("id", "Unknown")


async def get_access_control(user_token: str) -> AccessResponse:
    graph_token = await _acquire_graph_token(user_token)

    async with httpx.AsyncClient() as client:
        group_ids = await _fetch_user_groups(client, graph_token)
        user_name, user_id = await _fetch_user_profile(client, graph_token)

    has_chat = settings.GROUP_CHAT_ACCESS in group_ids
    has_dashboard = settings.GROUP_DASHBOARD_ACCESS in group_ids
    has_pipelines_ingestion = settings.GROUP_PIPELINES_INGESTION_ACCESS in group_ids
    has_pipelines_admin = settings.GROUP_PIPELINES_ADMIN_ACCESS in group_ids
    has_dev_data = settings.GROUP_DEV_DATA_ACCESS in group_ids

    logger.info("--- Access Check for User: {} ({}) ---", user_name, user_id)
    logger.info("User Groups ({}): {}", len(group_ids), group_ids)
    logger.info(
        "Checking Chat Access (Required: {}): {}",
        settings.GROUP_CHAT_ACCESS,
        "GRANTED" if has_chat else "DENIED",
    )
    logger.info(
        "Checking Dashboard Access (Required: {}): {}",
        settings.GROUP_DASHBOARD_ACCESS,
        "GRANTED" if has_dashboard else "DENIED",
    )
    logger.info(
        "Checking Pipelines Ingestion Access (Required: {}): {}",
        settings.GROUP_PIPELINES_INGESTION_ACCESS,
        "GRANTED" if has_pipelines_ingestion else "DENIED",
    )
    logger.info(
        "Checking Pipelines Admin Access (Required: {}): {}",
        settings.GROUP_PIPELINES_ADMIN_ACCESS,
        "GRANTED" if has_pipelines_admin else "DENIED",
    )
    logger.info(
        "Checking Dev Data Access (Required: {}): {}",
        settings.GROUP_DEV_DATA_ACCESS,
        "GRANTED" if has_dev_data else "DENIED",
    )
    logger.info("---------------------------------------------------")

    return AccessResponse(
        hasChatAccess=has_chat,
        hasDashboardAccess=has_dashboard,
        hasPipelinesIngestionAccess=has_pipelines_ingestion,
        hasPipelinesAdminAccess=has_pipelines_admin,
        hasDevDataAccess=has_dev_data,
        user=user_name,
    )
