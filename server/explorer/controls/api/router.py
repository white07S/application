"""API endpoints for Explorer controls search and detail."""

from fastapi import APIRouter, Depends, HTTPException

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.explorer.shared.models import (
    ControlDescriptionsRequest,
    ControlDescriptionsResponse,
    ControlDetailResponse,
    ControlDiffRequest,
    ControlDiffResponse,
    ControlsSearchParams,
    ControlsSearchResponse,
    ControlVersionListResponse,
)
from server.explorer.controls.service import (
    get_control_descriptions,
    get_control_detail,
    get_control_diff,
    get_control_versions,
    search_controls,
)
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


@router.get("/{control_id}/detail", response_model=ControlDetailResponse)
async def control_detail(
    control_id: str,
    _token: str = Depends(_require_explorer_access),
):
    """Get extended detail for a single control (overlay view)."""
    try:
        return await get_control_detail(control_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{control_id}/versions", response_model=ControlVersionListResponse)
async def control_versions(
    control_id: str,
    _token: str = Depends(_require_explorer_access),
):
    """Get all version timestamps for a control."""
    return await get_control_versions(control_id)


@router.post("/{control_id}/diff", response_model=ControlDiffResponse)
async def control_diff(
    control_id: str,
    body: ControlDiffRequest,
    _token: str = Depends(_require_explorer_access),
):
    """Compare two versions of a control."""
    try:
        return await get_control_diff(control_id, body.from_tx, body.to_tx)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/descriptions", response_model=ControlDescriptionsResponse)
async def control_descriptions(
    body: ControlDescriptionsRequest,
    _token: str = Depends(_require_explorer_access),
):
    """Fetch brief descriptions for a list of control IDs."""
    return await get_control_descriptions(body.control_ids)
