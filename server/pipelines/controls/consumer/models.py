"""Data models for consumer module responses.

This module defines Pydantic models and dataclasses for structuring
consumer query responses.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ControlRecord:
    """A complete control record with all model outputs at a specific date.

    Used for temporal queries (get_record_as_of_date).
    """
    control_id: str
    as_of_date: str
    actual_date: str
    fallback_used: str  # "exact", "before", "current"

    controls_main: Optional[Dict[str, Any]] = None
    taxonomy: Optional[Dict[str, Any]] = None
    enrichment: Optional[Dict[str, Any]] = None
    clean_text: Optional[Dict[str, Any]] = None
    embeddings: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "control_id": self.control_id,
            "as_of_date": self.as_of_date,
            "actual_date": self.actual_date,
            "fallback_used": self.fallback_used,
            "controls_main": self.controls_main,
            "taxonomy": self.taxonomy,
            "enrichment": self.enrichment,
            "clean_text": self.clean_text,
            "embeddings": self.embeddings,
        }


@dataclass
class ControlWithRelationships:
    """A control record with all graph-linked relationships.

    Used for graph traversal queries (get_control_with_relationships).
    """
    control_id: str
    controls_main: Optional[Dict[str, Any]] = None

    # Graph-linked relationships
    risk_themes: List[Dict[str, Any]] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    locations: List[Dict[str, Any]] = field(default_factory=list)
    sox_assertions: List[Dict[str, Any]] = field(default_factory=list)
    category_flags: List[Dict[str, Any]] = field(default_factory=list)

    # Model outputs (linked via graph edges)
    taxonomy: Optional[Dict[str, Any]] = None
    enrichment: Optional[Dict[str, Any]] = None
    clean_text: Optional[Dict[str, Any]] = None
    embeddings: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "control_id": self.control_id,
            "controls_main": self.controls_main,
            "risk_themes": self.risk_themes,
            "functions": self.functions,
            "locations": self.locations,
            "sox_assertions": self.sox_assertions,
            "category_flags": self.category_flags,
            "taxonomy": self.taxonomy,
            "enrichment": self.enrichment,
            "clean_text": self.clean_text,
            "embeddings": self.embeddings,
        }

    def summary(self) -> Dict[str, int]:
        """Get summary counts of relationships and model outputs."""
        return {
            "risk_themes": len(self.risk_themes),
            "functions": len(self.functions),
            "locations": len(self.locations),
            "sox_assertions": len(self.sox_assertions),
            "category_flags": len(self.category_flags),
            "has_taxonomy": 1 if self.taxonomy else 0,
            "has_enrichment": 1 if self.enrichment else 0,
            "has_clean_text": 1 if self.clean_text else 0,
            "has_embeddings": 1 if self.embeddings else 0,
        }


@dataclass
class ControlHistory:
    """Complete version history for a control.

    Used for temporal history queries (get_record_history).
    """
    control_id: str
    controls_main_versions: List[Dict[str, Any]]
    taxonomy_versions: List[Dict[str, Any]]
    enrichment_versions: List[Dict[str, Any]]
    clean_text_versions: List[Dict[str, Any]]
    embeddings_versions: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "control_id": self.control_id,
            "controls_main_versions": self.controls_main_versions,
            "taxonomy_versions": self.taxonomy_versions,
            "enrichment_versions": self.enrichment_versions,
            "clean_text_versions": self.clean_text_versions,
            "embeddings_versions": self.embeddings_versions,
        }

    def version_counts(self) -> Dict[str, int]:
        """Get counts of versions for each table."""
        return {
            "controls_main": len(self.controls_main_versions),
            "taxonomy": len(self.taxonomy_versions),
            "enrichment": len(self.enrichment_versions),
            "clean_text": len(self.clean_text_versions),
            "embeddings": len(self.embeddings_versions),
        }


@dataclass
class CurrentSnapshot:
    """Snapshot of all current tables.

    Used for snapshot queries (get_current_snapshot).
    Note: This uses dicts instead of DataFrames for better API compatibility.
    """
    controls_main: List[Dict[str, Any]] = field(default_factory=list)
    taxonomy: List[Dict[str, Any]] = field(default_factory=list)
    enrichment: List[Dict[str, Any]] = field(default_factory=list)
    clean_text: List[Dict[str, Any]] = field(default_factory=list)
    embeddings: List[Dict[str, Any]] = field(default_factory=list)

    # Lookup tables
    risk_themes: List[Dict[str, Any]] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    locations: List[Dict[str, Any]] = field(default_factory=list)
    sox_assertions: List[Dict[str, Any]] = field(default_factory=list)
    category_flags: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "controls_main": self.controls_main,
            "taxonomy": self.taxonomy,
            "enrichment": self.enrichment,
            "clean_text": self.clean_text,
            "embeddings": self.embeddings,
            "risk_themes": self.risk_themes,
            "functions": self.functions,
            "locations": self.locations,
            "sox_assertions": self.sox_assertions,
            "category_flags": self.category_flags,
        }

    def summary(self) -> Dict[str, int]:
        """Get summary counts of all tables."""
        return {
            "controls_main": len(self.controls_main),
            "taxonomy": len(self.taxonomy),
            "enrichment": len(self.enrichment),
            "clean_text": len(self.clean_text),
            "embeddings": len(self.embeddings),
            "risk_themes": len(self.risk_themes),
            "functions": len(self.functions),
            "locations": len(self.locations),
            "sox_assertions": len(self.sox_assertions),
            "category_flags": len(self.category_flags),
        }
