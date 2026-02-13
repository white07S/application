"""Controls ingestion into PostgreSQL + Qdrant.

Reads controls JSONL + AI model outputs and inserts/updates records
using the ref/ver/rel temporal schema, with embeddings upserted to Qdrant.

Usage:
    from server.pipelines.controls.ingest.service import (
        run_controls_ingestion,
        IngestionResult,
        IngestionCounts,
    )
"""

from .service import (
    run_controls_ingestion,
    IngestionResult,
    IngestionCounts,
)

__all__ = [
    "run_controls_ingestion",
    "IngestionResult",
    "IngestionCounts",
]
