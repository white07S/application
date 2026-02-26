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
    l1_score_dist: ScoreDistribution
    l2_score_dist: ScoreDistribution
    criterion_pass_rates: list[CriterionPassRate]
    worst_criteria: list[CriterionPassRate]  # sorted ascending by pass_rate
    score_by_function: list[FunctionBreakdown]


class PortfolioAnalyticsResponse(BaseModel):
    attribute_distributions: list[AttributeDistribution]
    function_breakdown: list[FunctionBreakdown]
    risk_theme_breakdown: list[RiskThemeBreakdown]
    controls_created_by_month: dict[str, int]  # {"2024-01": 15, ...}
    controls_modified_by_month: dict[str, int]


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
