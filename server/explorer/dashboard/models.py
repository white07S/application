"""Pydantic request/response models for the dashboard API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ── Request Models ────────────────────────────────────────────────────────


class DashboardFilters(BaseModel):
    """Sidebar filters applied to dashboard aggregate queries."""

    functions: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    consolidated_entities: list[str] = Field(default_factory=list)
    assessment_units: list[str] = Field(default_factory=list)
    risk_themes: list[str] = Field(default_factory=list)
    filter_logic: str = "and"
    relationship_scope: str = "both"

    @property
    def has_any(self) -> bool:
        return bool(
            self.functions
            or self.locations
            or self.consolidated_entities
            or self.assessment_units
            or self.risk_themes
        )


class FilteredTrendRequest(BaseModel):
    """Request for filtered trend data with time range."""

    filters: DashboardFilters = Field(default_factory=DashboardFilters)
    from_date: datetime | None = None
    to_date: datetime | None = None
    limit: int = Field(default=50, ge=1, le=200)


# ── Response Building Blocks ──────────────────────────────────────────────


class PortfolioSummary(BaseModel):
    total_controls: int
    total_l1: int
    total_l2: int
    active_controls: int
    inactive_controls: int
    key_controls: int
    sox_relevant: int
    ccar_relevant: int
    bcbs239_relevant: int


class ScoreDistribution(BaseModel):
    distribution: dict[str, int]  # {"0": 150, "1": 200, ...}
    avg_score: float | None
    median_score: float | None
    total_assessed: int


class CriterionPassRate(BaseModel):
    criterion: str
    label: str
    pass_rate: float  # 0.0 to 1.0
    pass_count: int
    total_count: int


class AttributeDistribution(BaseModel):
    field: str
    values: dict[str, int]  # {"Preventative": 1200, "Detective": 800}


class FunctionBreakdown(BaseModel):
    node_id: str
    name: str
    control_count: int
    avg_score: float | None = None
    active_count: int = 0


class RiskThemeBreakdown(BaseModel):
    theme_id: str
    name: str
    control_count: int


# ── Endpoint Response Models ──────────────────────────────────────────────


class ExecutiveOverviewResponse(BaseModel):
    summary: PortfolioSummary
    total_all_controls: int  # unfiltered count across all statuses for awareness
    l1_score_dist: ScoreDistribution
    l2_score_dist: ScoreDistribution
    criterion_pass_rates: list[CriterionPassRate]
    attribute_distributions: list[AttributeDistribution]
    top_functions: list[FunctionBreakdown]
    top_risk_themes: list[RiskThemeBreakdown]
    snapshot_at: datetime | None = None


class DocQualityResponse(BaseModel):
    l1_avg_score: float | None
    l1_total_assessed: int
    l2_avg_score: float | None
    l2_total_assessed: int


class RegulatoryComplianceResponse(BaseModel):
    summary: PortfolioSummary
    sox_controls: int
    ccar_controls: int
    bcbs239_controls: int
    sox_by_function: list[FunctionBreakdown]
    sox_score_dist: ScoreDistribution


# ── Time-Series Models ────────────────────────────────────────────────────


class SnapshotTrendPoint(BaseModel):
    snapshot_at: datetime
    upload_id: str | None
    total_controls: int
    active_controls: int
    avg_l1_score: float | None
    avg_l2_score: float | None
    controls_scoring_full_marks: int | None
    controls_scoring_zero: int | None
    criterion_pass_rates: dict[str, float] = Field(default_factory=dict)


class TrendResponse(BaseModel):
    points: list[SnapshotTrendPoint]
    total_snapshots: int


class ScoreTrendPoint(BaseModel):
    snapshot_at: datetime
    distribution: dict[str, int]
    avg_score: float | None


class ScoreTrendResponse(BaseModel):
    l1_trend: list[ScoreTrendPoint]
    l2_trend: list[ScoreTrendPoint]


class HistoryChangeResponse(BaseModel):
    trends: TrendResponse
    score_trends: ScoreTrendResponse


class SnapshotRebuildResponse(BaseModel):
    snapshot_id: int
    snapshot_at: datetime
    computation_ms: int


# ── Lifecycle Heatmap ────────────────────────────────────────────────────


class LifecycleMonthPoint(BaseModel):
    month: str  # "2025-01"
    created: int
    retired: int


class LifecycleHeatmapResponse(BaseModel):
    months: list[LifecycleMonthPoint]


# ── Concentration (Who / Where Month-over-Month) ─────────────────────


class ConcentrationEntry(BaseModel):
    value: str   # display name (most common original form)
    count: int


class ConcentrationMonthPoint(BaseModel):
    month: str                        # "2025-01"
    top: list[ConcentrationEntry]
    others_count: int                 # sum of values outside top N


class ConcentrationResponse(BaseModel):
    dimension: str                                    # "who" or "where"
    top_values: list[str]                             # global top N, sorted by total desc
    months: list[ConcentrationMonthPoint]
    grid: dict[str, dict[str, int]]                   # value -> {month -> count} for heatmap


# ── Similarity Redundancy Month-over-Month ───────────────────────────


class RedundancyMonthPoint(BaseModel):
    month: str                      # "2025-01"
    total_created: int
    with_prior_near_duplicate: int  # similar score >= 0.90 created earlier
    with_prior_weak_similar: int    # similar score 0.60–0.90 created earlier
    with_prior_similar: int         # union count (each control counted once)
    redundancy_pct: float           # with_prior_similar / total_created * 100


class RedundancyResponse(BaseModel):
    months: list[RedundancyMonthPoint]
