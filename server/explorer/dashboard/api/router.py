"""API endpoints for the Controls Portfolio Dashboard."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.explorer.dashboard.models import (
    ConcentrationResponse,
    DashboardFilters,
    DocQualityResponse,
    ExecutiveOverviewResponse,
    FilteredTrendRequest,
    HistoryChangeResponse,
    LifecycleHeatmapResponse,
    RedundancyResponse,
    RegulatoryComplianceResponse,
    ScoreTrendResponse,
    SnapshotRebuildResponse,
    TrendResponse,
)
from server.explorer.dashboard.service import (
    compute_concentration,
    compute_doc_quality,
    compute_executive_overview,
    compute_lifecycle_heatmap,
    compute_regulatory_compliance,
    compute_similarity_redundancy,
    get_score_trends,
    get_snapshot_trends,
)
from server.explorer.dashboard.snapshot_builder import capture_dashboard_snapshot
from server.logging_config import get_logger

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/explorer/dashboard", tags=["Explorer Dashboard"])


async def _require_explorer_access(token: str = Depends(get_token_from_header)):
    access = await get_access_control(token)
    if not access.hasExplorerAccess:
        raise HTTPException(status_code=403, detail="Explorer access required")
    return token


# ── Tab endpoints (live computation, filterable) ──────────────────────────


@router.post("/executive-overview", response_model=ExecutiveOverviewResponse)
async def get_executive_overview(
    filters: DashboardFilters = DashboardFilters(),
    token: str = Depends(_require_explorer_access),
):
    """Executive overview: KPIs, score distributions, criterion pass rates, breakdowns."""
    return await compute_executive_overview(filters)


@router.post("/doc-quality", response_model=DocQualityResponse)
async def get_doc_quality(
    filters: DashboardFilters = DashboardFilters(),
    token: str = Depends(_require_explorer_access),
):
    """Documentation quality: score histograms, worst criteria, score by function."""
    return await compute_doc_quality(filters)


@router.post("/regulatory-compliance", response_model=RegulatoryComplianceResponse)
async def get_regulatory_compliance(
    filters: DashboardFilters = DashboardFilters(),
    token: str = Depends(_require_explorer_access),
):
    """Regulatory compliance: SOX/CCAR/BCBS239 coverage and scores."""
    return await compute_regulatory_compliance(filters)


@router.post("/lifecycle-heatmap", response_model=LifecycleHeatmapResponse)
async def get_lifecycle_heatmap(
    filters: DashboardFilters = DashboardFilters(),
    token: str = Depends(_require_explorer_access),
):
    """Monthly created vs retired controls heatmap (last 12 months, filterable)."""
    return await compute_lifecycle_heatmap(filters)


@router.post("/concentration/{dimension}", response_model=ConcentrationResponse)
async def get_concentration(
    dimension: str,
    filters: DashboardFilters = DashboardFilters(),
    token: str = Depends(_require_explorer_access),
):
    """Month-over-month concentration of Roles/Process/Product/Service from AI enrichment (L1 Active Key)."""
    if dimension not in ("roles", "process", "product", "service"):
        raise HTTPException(status_code=400, detail="dimension must be 'roles', 'process', 'product', or 'service'")
    return await compute_concentration(filters, dimension)


@router.post("/similarity-redundancy", response_model=RedundancyResponse)
async def get_similarity_redundancy(
    filters: DashboardFilters = DashboardFilters(),
    token: str = Depends(_require_explorer_access),
):
    """Month-over-month: new controls that already have a prior-created similar control."""
    return await compute_similarity_redundancy(filters)


# ── Trend endpoints (from pre-computed snapshots) ─────────────────────────


@router.get("/trends", response_model=TrendResponse)
async def get_trends(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    token: str = Depends(_require_explorer_access),
):
    """Time-series trend data from dashboard snapshots (control counts, avg scores)."""
    return await get_snapshot_trends(from_date, to_date, limit)


@router.get("/trends/scores", response_model=ScoreTrendResponse)
async def get_trends_scores(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    token: str = Depends(_require_explorer_access),
):
    """Time-series score distribution histograms from dashboard snapshots."""
    return await get_score_trends(from_date, to_date, limit)


@router.post("/trends/filtered", response_model=TrendResponse)
async def get_trends_filtered(
    request: FilteredTrendRequest,
    token: str = Depends(_require_explorer_access),
):
    """Filtered trend data using live temporal reconstruction."""
    # For now, return global trends. Filtered temporal reconstruction
    # will be implemented when multiple ingestion runs are available.
    return await get_snapshot_trends(request.from_date, request.to_date, request.limit)


# ── Admin endpoints ───────────────────────────────────────────────────────


@router.post("/snapshot/rebuild", response_model=SnapshotRebuildResponse)
async def rebuild_snapshot(
    token: str = Depends(_require_explorer_access),
):
    """Force rebuild the current dashboard snapshot (admin utility)."""
    import time as _time

    start = _time.monotonic()
    snapshot_id = await capture_dashboard_snapshot(snapshot_type="manual")
    elapsed = int((_time.monotonic() - start) * 1000)

    from server.explorer.dashboard.schema import dashboard_snapshots
    from sqlalchemy import select
    from server.config.postgres import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                select(dashboard_snapshots.c.snapshot_at)
                .where(dashboard_snapshots.c.snapshot_id == snapshot_id)
            )
        ).one()

    return SnapshotRebuildResponse(
        snapshot_id=snapshot_id,
        snapshot_at=row[0],
        computation_ms=elapsed,
    )
