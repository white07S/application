"""Shared dependencies for DevData Qdrant APIs."""

from fastapi import Depends, HTTPException

from server.auth.dependencies import get_token_from_header
from server.auth.models import AccessResponse
from server.auth.service import get_access_control


async def require_dev_data_access(token: str = Depends(get_token_from_header)) -> AccessResponse:
    """Require DevData ABAC access and return resolved access context."""
    access = await get_access_control(token)
    if not access.hasDevDataAccess:
        raise HTTPException(status_code=403, detail="Dev data access required")
    return access

