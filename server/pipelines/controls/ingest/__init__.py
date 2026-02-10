"""Ingestion Module for SurrealDB.

This module provides base and delta ingestion capabilities with real-time
progress tracking for UI updates.

Main Functions:
- run_ingestion: Orchestrate base or delta ingestion process

Components:
- tracker: Progress tracking with batch processing (10 records per batch)
- base: Base ingestion (clear + load all controls)
- delta: Delta ingestion (detect changes + update/insert)
- service: Orchestration and coordination

Usage:
    from server.pipelines.controls.ingest import run_ingestion

    result = await run_ingestion(
        batch_id="batch_123",
        split_dir=Path("/path/to/split/files"),
        is_base=True,  # or False for delta
    )

    if result.success:
        print(f"Ingested {len(result.new_control_ids)} new controls")
"""

from .tracker import (
    IngestionTracker,
    IngestionStats,
    IngestionStatus,
    BatchProgress,
)
from .service import (
    run_ingestion,
    IngestionResult,
)
from .base import ingest_base
from .delta import ingest_delta

__all__ = [
    # Main service functions
    "run_ingestion",
    "IngestionResult",
    # Core ingestion functions
    "ingest_base",
    "ingest_delta",
    # Tracker components
    "IngestionTracker",
    "IngestionStats",
    "IngestionStatus",
    "BatchProgress",
]
