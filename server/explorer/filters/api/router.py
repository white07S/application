"""API endpoints for Explorer filter data."""

from fastapi import APIRouter, Depends, HTTPException, Query

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.logging_config import get_logger
from server.explorer.shared.models import (
    TreeNodesResponse,
    FlatItemsResponse,
    RiskTaxonomiesResponse,
)
from server.explorer.filters.service import (
    get_function_tree,
    get_location_tree,
    get_consolidated_entities,
    get_assessment_units,
    get_risk_taxonomies,
)

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/explorer/filters", tags=["Explorer Filters"])


async def _require_explorer_access(token: str = Depends(get_token_from_header)):
    """Verify the user has explorer access."""
    access = await get_access_control(token)
    if not access.hasExplorerAccess:
        raise HTTPException(status_code=403, detail="Explorer access required")
    return access


@router.get("/functions", response_model=TreeNodesResponse)
async def functions(
    parent_id: str = Query(None, description="Parent node ID for lazy loading"),
    search: str = Query(None, description="Search by name or node ID"),
    _=Depends(_require_explorer_access),
):
    """Get function hierarchy nodes."""
    nodes = await get_function_tree(parent_id, search)
    return TreeNodesResponse(nodes=nodes)


@router.get("/locations", response_model=TreeNodesResponse)
async def locations(
    parent_id: str = Query(None, description="Parent node ID for lazy loading"),
    search: str = Query(None, description="Search by name or node ID"),
    _=Depends(_require_explorer_access),
):
    """Get location hierarchy nodes."""
    nodes = await get_location_tree(parent_id, search)
    return TreeNodesResponse(nodes=nodes)


@router.get("/consolidated-entities", response_model=FlatItemsResponse)
async def consolidated_entities(
    search: str = Query(None, description="Case-insensitive search on name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _=Depends(_require_explorer_access),
):
    """Get consolidated entities with optional search and pagination."""
    result = await get_consolidated_entities(search, page, page_size)
    return FlatItemsResponse(**result)


@router.get("/assessment-units", response_model=FlatItemsResponse)
async def assessment_units(
    _=Depends(_require_explorer_access),
):
    """Get all assessment units."""
    result = await get_assessment_units()
    return FlatItemsResponse(**result)


@router.get("/risk-themes", response_model=RiskTaxonomiesResponse)
async def risk_themes(
    _=Depends(_require_explorer_access),
):
    """Get all risk taxonomies with their active themes."""
    taxonomies = await get_risk_taxonomies()
    return RiskTaxonomiesResponse(taxonomies=taxonomies)
