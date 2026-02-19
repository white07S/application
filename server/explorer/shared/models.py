"""Shared Pydantic response models for the explorer module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TreeNodeResponse(BaseModel):
    id: str
    label: str
    level: int
    has_children: bool
    children: list[TreeNodeResponse] = []
    node_type: str | None = None
    status: str | None = None
    path: str | None = None


class TreeNodesResponse(BaseModel):
    nodes: list[TreeNodeResponse]


class FlatItemResponse(BaseModel):
    id: str
    label: str
    description: str | None = None
    function_node_id: str | None = None
    location_node_id: str | None = None
    location_type: str | None = None


class FlatItemsResponse(BaseModel):
    items: list[FlatItemResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class RiskThemeResponse(BaseModel):
    id: str
    name: str
    status: str = "active"
    children: list[RiskThemeResponse] = []


class RiskTaxonomyResponse(BaseModel):
    id: str
    name: str
    themes: list[RiskThemeResponse]


class RiskTaxonomiesResponse(BaseModel):
    taxonomies: list[RiskTaxonomyResponse]


# ──────────────────────────────────────────────────────────────────────
# Controls search request / response models
# ──────────────────────────────────────────────────────────────────────

# The 6 searchable fields (FTS columns in clean_text + Qdrant named vectors)
SEARCH_FIELD_NAMES = [
    "control_title",
    "control_description",
    "evidence_description",
    "local_functional_information",
    "control_as_event",
    "control_as_issues",
]


class SidebarFilters(BaseModel):
    """Sidebar filter selections sent to the server."""
    functions: list[str] = Field(default_factory=list, description="Function node_ids")
    locations: list[str] = Field(default_factory=list, description="Location node_ids")
    consolidated_entities: list[str] = Field(default_factory=list, description="CE node_ids")
    assessment_units: list[str] = Field(default_factory=list, description="AU unit_ids")
    risk_themes: list[str] = Field(default_factory=list, description="Risk theme_ids")

    @property
    def has_any(self) -> bool:
        return bool(
            self.functions or self.locations or self.consolidated_entities
            or self.assessment_units or self.risk_themes
        )


class ToolbarFilters(BaseModel):
    """Quick-filter toggles from the controls toolbar."""
    active_only: bool = False
    key_control: bool | None = None
    level1: bool = False
    level2: bool = False
    ai_score_max: int | None = Field(default=None, ge=0, le=14)
    # Date range filter
    date_from: datetime | None = Field(default=None, description="Start of date range (inclusive)")
    date_to: datetime | None = Field(default=None, description="End of date range (inclusive)")
    date_field: Literal["created_on", "last_modified_on"] = Field(
        default="created_on", description="Which date column to filter on",
    )


class ControlsSearchParams(BaseModel):
    """POST body for /v2/explorer/controls/search."""
    # Sidebar filters
    sidebar: SidebarFilters = Field(default_factory=SidebarFilters)
    filter_logic: Literal["and", "or"] = "and"
    relationship_scope: Literal["owns", "related", "both"] = "both"

    # Search
    search_query: str | None = None
    search_mode: Literal["keyword", "semantic", "hybrid", "id"] | None = None
    search_fields: list[str] = Field(
        default_factory=lambda: list(SEARCH_FIELD_NAMES),
        description="Which clean_text / Qdrant fields to search",
    )

    # Toolbar filters
    toolbar: ToolbarFilters = Field(default_factory=ToolbarFilters)

    # Pagination
    cursor: str | None = None
    page_size: int = Field(default=50, ge=1, le=200)


# --- Response models ---


class NamedItem(BaseModel):
    """A generic id+name pair for relationships."""
    id: str
    name: str | None = None


class ControlResponse(BaseModel):
    """Core control fields from ver_control."""
    control_id: str
    control_title: str | None = None
    control_description: str | None = None
    key_control: bool | None = None
    hierarchy_level: str | None = None
    preventative_detective: str | None = None
    manual_automated: str | None = None
    execution_frequency: str | None = None
    four_eyes_check: bool | None = None
    control_status: str | None = None
    evidence_description: str | None = None
    local_functional_information: str | None = None
    last_modified_on: datetime | None = None
    control_created_on: datetime | None = None
    control_owner: str | None = None
    control_owner_gpn: str | None = None
    sox_relevant: bool | None = None


class ControlRelationshipsResponse(BaseModel):
    """Resolved relationships for a control."""
    parent: NamedItem | None = None
    children: list[NamedItem] = Field(default_factory=list)
    owns_functions: list[NamedItem] = Field(default_factory=list)
    owns_locations: list[NamedItem] = Field(default_factory=list)
    related_functions: list[NamedItem] = Field(default_factory=list)
    related_locations: list[NamedItem] = Field(default_factory=list)
    risk_themes: list[NamedItem] = Field(default_factory=list)


class AIEnrichmentResponse(BaseModel):
    """AI enrichment + taxonomy output for a control."""
    # W-criteria (L1)
    what_yes_no: str | None = None
    where_yes_no: str | None = None
    who_yes_no: str | None = None
    when_yes_no: str | None = None
    why_yes_no: str | None = None
    what_why_yes_no: str | None = None
    risk_theme_yes_no: str | None = None
    # Operational criteria (L2)
    frequency_yes_no: str | None = None
    preventative_detective_yes_no: str | None = None
    automation_level_yes_no: str | None = None
    followup_yes_no: str | None = None
    escalation_yes_no: str | None = None
    evidence_yes_no: str | None = None
    abbreviations_yes_no: str | None = None
    # Summary + narratives
    summary: str | None = None
    control_as_event: str | None = None
    control_as_issues: str | None = None
    # Taxonomy
    primary_risk_theme_id: str | None = None
    secondary_risk_theme_id: str | None = None


class SimilarControlResponse(BaseModel):
    """A precomputed similar control with its hybrid score."""
    control_id: str
    score: float
    rank: int


class ParentL1ScoreResponse(BaseModel):
    """Parent L1 W-criteria score, included on L2 controls."""
    control_id: str
    criteria: list[dict] = Field(default_factory=list, description="[{key, yes_no}, ...]")
    yes_count: int = 0
    total: int = 0


class ControlWithDetailsResponse(BaseModel):
    """A single control with all its details, returned in search results."""
    control: ControlResponse
    relationships: ControlRelationshipsResponse = Field(default_factory=ControlRelationshipsResponse)
    ai: AIEnrichmentResponse | None = None
    parent_l1_score: ParentL1ScoreResponse | None = None
    similar_controls: list[SimilarControlResponse] = Field(default_factory=list)
    search_score: float | None = None


class ControlsSearchResponse(BaseModel):
    """Response for POST /v2/explorer/controls/search."""
    items: list[ControlWithDetailsResponse]
    cursor: str | None = None
    total_estimate: int
    has_more: bool
