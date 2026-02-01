"""Consumer module for querying controls data from SurrealDB with graph traversal.

This module provides the ControlsConsumer service for querying controls data
using graph traversal and temporal access patterns.

Naming Convention: {layer}_{domain}_{kind}_{name}
- layer: src | ai
- domain: controls (always plural)
- kind: ref | main | ver | rel | model
- name: descriptive name

Provides temporal data access patterns:
1. get_record_as_of_date(control_id, date) - Get record at specific date with fallback
2. get_record_history(control_id) - Get complete version history
3. get_current_snapshot() - Get all current tables
4. get_table_counts() - Get record counts for all tables

Graph-aware queries:
5. get_control_with_relationships(control_id) - Get control with all related entities via graph
6. get_controls_by_risk_theme(risk_theme_id) - Find controls linked to a risk theme
7. get_controls_by_function(function_id) - Find controls linked to a function
8. get_controls_by_location(location_id) - Find controls linked to a location
9. get_control_graph(control_id) - Get complete graph of control relationships

Complete Record Assembly:
10. get_complete_control_record(control_id) - Assembled dict with all data

Usage:
    from server.pipelines.controls.consumer import ControlsConsumer

    async with ControlsConsumer() as consumer:
        # Get control with all relationships
        record = await consumer.get_control_with_relationships("CTRL-001")

        # Get record as of specific date
        historical = await consumer.get_record_as_of_date("CTRL-001", "2026-01-15")

        # Get complete assembled record
        complete = await consumer.get_complete_control_record("CTRL-001")
"""

from .service import ControlsConsumer
from .models import (
    ControlRecord,
    ControlWithRelationships,
    ControlHistory,
    CurrentSnapshot,
)

__all__ = [
    "ControlsConsumer",
    "ControlRecord",
    "ControlWithRelationships",
    "ControlHistory",
    "CurrentSnapshot",
]
