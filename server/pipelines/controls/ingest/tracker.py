"""Ingestion Progress Tracker.

This module provides real-time tracking of ingestion progress for UI updates.
Tracks records processed in batches of 10 as requested by the user.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class IngestionStatus(str, Enum):
    """Ingestion status values."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IngestionStats:
    """Summary statistics for ingestion operation."""
    # Total counts
    total_records: int = 0
    processed_records: int = 0
    new_records: int = 0
    updated_records: int = 0
    unchanged_records: int = 0
    failed_records: int = 0

    # Model pipeline stats
    model_pipeline_runs: int = 0

    # Reference table additions (for delta)
    risk_themes_added: int = 0
    functions_added: int = 0
    locations_added: int = 0
    sox_assertions_added: int = 0
    category_flags_added: int = 0

    # Edge counts
    edges_created: int = 0
    edges_deleted: int = 0

    # Errors
    errors: List[str] = field(default_factory=list)

    # Control IDs for reporting
    new_control_ids: List[str] = field(default_factory=list)
    changed_control_ids: List[str] = field(default_factory=list)
    failed_control_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert stats to dictionary for API responses."""
        return {
            "total_records": self.total_records,
            "processed_records": self.processed_records,
            "new_records": self.new_records,
            "updated_records": self.updated_records,
            "unchanged_records": self.unchanged_records,
            "failed_records": self.failed_records,
            "model_pipeline_runs": self.model_pipeline_runs,
            "reference_tables": {
                "risk_themes_added": self.risk_themes_added,
                "functions_added": self.functions_added,
                "locations_added": self.locations_added,
                "sox_assertions_added": self.sox_assertions_added,
                "category_flags_added": self.category_flags_added,
            },
            "edges": {
                "created": self.edges_created,
                "deleted": self.edges_deleted,
            },
            "errors_count": len(self.errors),
            "control_ids": {
                "new": self.new_control_ids[:100],  # Limit to first 100
                "changed": self.changed_control_ids[:100],
                "failed": self.failed_control_ids[:100],
            },
        }


@dataclass
class BatchProgress:
    """Progress for current batch."""
    batch_number: int
    batch_size: int
    current_index: int
    start_time: datetime

    def percentage(self) -> float:
        """Calculate batch completion percentage."""
        if self.batch_size == 0:
            return 0.0
        return (self.current_index / self.batch_size) * 100


class IngestionTracker:
    """Track ingestion progress for real-time UI updates.

    This tracker supports batch processing with configurable batch size
    (default 10 records per batch as requested by user).
    """

    def __init__(self, batch_size: int = 10):
        """Initialize tracker.

        Args:
            batch_size: Number of records per batch (default 10)
        """
        self.batch_size = batch_size
        self.status = IngestionStatus.PENDING
        self.stats = IngestionStats()

        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        self.current_batch: Optional[BatchProgress] = None
        self.current_phase: str = "initializing"
        self.current_message: str = ""

        # For tracking current control being processed
        self.current_control_id: Optional[str] = None

    def start(self, total_records: int, phase: str = "ingestion"):
        """Start ingestion tracking.

        Args:
            total_records: Total number of records to process
            phase: Current phase name
        """
        self.status = IngestionStatus.RUNNING
        self.stats.total_records = total_records
        self.start_time = datetime.now()
        self.current_phase = phase
        self.current_message = f"Starting {phase} for {total_records} records"

    def start_batch(self, batch_number: int, batch_size: int):
        """Start processing a new batch.

        Args:
            batch_number: Batch number (1-indexed)
            batch_size: Number of records in this batch
        """
        self.current_batch = BatchProgress(
            batch_number=batch_number,
            batch_size=batch_size,
            current_index=0,
            start_time=datetime.now()
        )
        self.current_message = f"Processing batch {batch_number} ({batch_size} records)"

    def complete_record(
        self,
        control_id: str,
        operation: str = "processed",
        is_new: bool = False,
        is_updated: bool = False,
        is_unchanged: bool = False
    ):
        """Mark a record as successfully processed.

        Args:
            control_id: Control ID that was processed
            operation: Type of operation performed
            is_new: True if this is a new record
            is_updated: True if this is an updated record
            is_unchanged: True if record was unchanged
        """
        self.current_control_id = control_id
        self.stats.processed_records += 1

        if is_new:
            self.stats.new_records += 1
            self.stats.new_control_ids.append(control_id)
        elif is_updated:
            self.stats.updated_records += 1
            self.stats.changed_control_ids.append(control_id)
        elif is_unchanged:
            self.stats.unchanged_records += 1

        if self.current_batch:
            self.current_batch.current_index += 1
            self.current_message = f"Processed {control_id} ({operation})"

    def fail_record(self, control_id: str, error: str):
        """Mark a record as failed.

        Args:
            control_id: Control ID that failed
            error: Error message
        """
        self.current_control_id = control_id
        self.stats.failed_records += 1
        self.stats.failed_control_ids.append(control_id)
        self.stats.errors.append(f"{control_id}: {error}")

        if self.current_batch:
            self.current_batch.current_index += 1
            self.current_message = f"Failed {control_id}: {error}"

    def add_error(self, error: str):
        """Add a general error message.

        Args:
            error: Error message
        """
        self.stats.errors.append(error)

    def increment_model_runs(self):
        """Increment model pipeline run count."""
        self.stats.model_pipeline_runs += 1

    def increment_edges_created(self, count: int = 1):
        """Increment edges created count.

        Args:
            count: Number of edges created
        """
        self.stats.edges_created += count

    def increment_edges_deleted(self, count: int = 1):
        """Increment edges deleted count.

        Args:
            count: Number of edges deleted
        """
        self.stats.edges_deleted += count

    def set_phase(self, phase: str, message: str = ""):
        """Set current processing phase.

        Args:
            phase: Phase name
            message: Optional message
        """
        self.current_phase = phase
        if message:
            self.current_message = message
        else:
            self.current_message = f"Phase: {phase}"

    def complete(self, status: IngestionStatus = IngestionStatus.COMPLETED):
        """Mark ingestion as complete.

        Args:
            status: Final status (COMPLETED or FAILED)
        """
        self.status = status
        self.end_time = datetime.now()
        self.current_batch = None

        if status == IngestionStatus.COMPLETED:
            self.current_message = "Ingestion completed successfully"
        else:
            self.current_message = "Ingestion failed"

    def get_progress(self) -> Dict:
        """Get current progress for UI polling.

        Returns:
            Dict with progress information suitable for API response
        """
        progress_data = {
            "status": self.status.value,
            "phase": self.current_phase,
            "message": self.current_message,
            "current_control_id": self.current_control_id,
            "stats": self.stats.to_dict(),
            "timing": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "elapsed_seconds": (
                    (self.end_time or datetime.now()) - self.start_time
                ).total_seconds() if self.start_time else 0,
            },
        }

        # Add batch progress if currently processing a batch
        if self.current_batch:
            progress_data["batch"] = {
                "number": self.current_batch.batch_number,
                "size": self.current_batch.batch_size,
                "current_index": self.current_batch.current_index,
                "percentage": self.current_batch.percentage(),
            }

        # Calculate overall percentage
        if self.stats.total_records > 0:
            progress_data["overall_percentage"] = (
                self.stats.processed_records / self.stats.total_records
            ) * 100
        else:
            progress_data["overall_percentage"] = 0.0

        return progress_data

    def get_summary(self) -> Dict:
        """Get final summary statistics.

        Returns:
            Dict with summary statistics
        """
        return {
            "status": self.status.value,
            "stats": self.stats.to_dict(),
            "timing": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "total_seconds": (
                    (self.end_time or datetime.now()) - self.start_time
                ).total_seconds() if self.start_time else 0,
            },
            "errors": self.stats.errors[:100],  # Limit to first 100 errors
        }
