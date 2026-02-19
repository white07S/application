"""API endpoint for Explorer controls search."""

from fastapi import APIRouter, Depends, HTTPException

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.explorer.shared.models import ControlsSearchParams, ControlsSearchResponse
from server.explorer.controls.service import search_controls
from server.logging_config import get_logger

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/explorer/controls", tags=["Explorer Controls"])


async def _require_explorer_access(token: str = Depends(get_token_from_header)):
    """Verify the user has explorer access and return the token."""
    access = await get_access_control(token)
    if not access.hasExplorerAccess:
        raise HTTPException(status_code=403, detail="Explorer access required")
    return token


@router.post("/search", response_model=ControlsSearchResponse)
async def controls_search(
    params: ControlsSearchParams,
    token: str = Depends(_require_explorer_access),
):
    """Search controls with sidebar filters, FTS, semantic search, and toolbar filters."""
    return await search_controls(params, graph_token=token)
