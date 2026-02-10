"""Ingestion Service Module.

This module orchestrates the ingestion process, coordinating between
base and delta ingestion modes with progress tracking.
"""

from pathlib import Path
from typing import Dict
from dataclasses import dataclass

from surrealdb import AsyncSurreal
from server.logging_config import get_logger
from server.config.surrealdb import get_surrealdb_connection
from .tracker import IngestionTracker, IngestionStatus
from .base import ingest_base
from .delta import ingest_delta

logger = get_logger(name=__name__)


@dataclass
class IngestionResult:
    """Result of ingestion operation."""
    success: bool
    message: str
    stats: Dict
    new_control_ids: list
    changed_control_ids: list
    errors: list

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "success": self.success,
            "message": self.message,
            "stats": self.stats,
            "new_control_ids": self.new_control_ids,
            "changed_control_ids": self.changed_control_ids,
            "errors": self.errors,
        }


async def run_ingestion(
    batch_id: str,
    split_dir: Path,
    is_base: bool = False,
) -> IngestionResult:
    """Run ingestion process (base or delta).

    Args:
        batch_id: Unique identifier for this batch
        split_dir: Directory containing split CSV files
        is_base: True for base ingestion (clear + load all), False for delta

    Returns:
        IngestionResult with statistics and status
    """
    tracker = IngestionTracker(batch_size=10)
    logger.info(f"Starting {'base' if is_base else 'delta'} ingestion for batch {batch_id}")

    try:
        # Verify split directory exists
        if not split_dir.exists() or not split_dir.is_dir():
            error_msg = f"Split directory not found: {split_dir}"
            logger.error(error_msg)
            tracker.add_error(error_msg)
            tracker.complete(IngestionStatus.FAILED)
            return IngestionResult(
                success=False,
                message=error_msg,
                stats=tracker.stats.to_dict(),
                new_control_ids=[],
                changed_control_ids=[],
                errors=tracker.stats.errors,
            )

        # Connect to SurrealDB
        async with get_surrealdb_connection() as db:
            logger.info("Connected to SurrealDB")

            if is_base:
                # Base ingestion: clear all + load all controls
                control_record_ids = await ingest_base(db, split_dir, tracker)

                tracker.complete(IngestionStatus.COMPLETED)
                logger.info(f"Base ingestion completed: {len(control_record_ids)} controls ingested")

                return IngestionResult(
                    success=True,
                    message=f"Base ingestion completed successfully. Ingested {len(control_record_ids)} controls.",
                    stats=tracker.stats.to_dict(),
                    new_control_ids=list(control_record_ids.keys()),
                    changed_control_ids=[],
                    errors=tracker.stats.errors,
                )

            else:
                # Delta ingestion: detect changes + update/insert
                new_control_record_ids, changed_control_ids = await ingest_delta(
                    db, split_dir, tracker
                )

                tracker.complete(IngestionStatus.COMPLETED)
                logger.info(
                    f"Delta ingestion completed: new={len(new_control_record_ids)}, "
                    f"changed={len(changed_control_ids)}, unchanged={tracker.stats.unchanged_records}"
                )

                return IngestionResult(
                    success=True,
                    message=(
                        f"Delta ingestion completed successfully. "
                        f"New: {len(new_control_record_ids)}, "
                        f"Changed: {len(changed_control_ids)}, "
                        f"Unchanged: {tracker.stats.unchanged_records}"
                    ),
                    stats=tracker.stats.to_dict(),
                    new_control_ids=list(new_control_record_ids.keys()),
                    changed_control_ids=changed_control_ids,
                    errors=tracker.stats.errors,
                )

    except Exception as e:
        error_msg = f"Ingestion failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        tracker.add_error(error_msg)
        tracker.complete(IngestionStatus.FAILED)

        return IngestionResult(
            success=False,
            message=error_msg,
            stats=tracker.stats.to_dict(),
            new_control_ids=[],
            changed_control_ids=[],
            errors=tracker.stats.errors,
        )
