"""Shared Pydantic response models for the explorer module."""

from __future__ import annotations

from pydantic import BaseModel


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
    effective_date: str | None = None
    date_warning: str | None = None


class FlatItemResponse(BaseModel):
    id: str
    label: str
    description: str | None = None


class FlatItemsResponse(BaseModel):
    items: list[FlatItemResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
    effective_date: str | None = None
    date_warning: str | None = None


class RiskThemeResponse(BaseModel):
    id: str
    name: str


class RiskTaxonomyResponse(BaseModel):
    id: str
    name: str
    themes: list[RiskThemeResponse]


class RiskTaxonomiesResponse(BaseModel):
    taxonomies: list[RiskTaxonomyResponse]
    effective_date: str | None = None
    date_warning: str | None = None
