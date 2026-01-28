"""Transaction tracker for per-record pipeline processing.

Tracks the global transaction state for each record being processed,
including sub-transactions for each pipeline stage (insert, models, etc.).
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from server.logging_config import get_logger

logger = get_logger(name=__name__)


class TransactionStatus(str, Enum):
    """Status of a transaction or sub-transaction."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class SubTransaction:
    """Tracks a single stage within a record's processing."""
    name: str  # "insert_main", "insert_children", "nfr_taxonomy", etc.
    status: TransactionStatus = TransactionStatus.PENDING
    attempt: int = 0  # Current retry attempt (0 = not started, 1 = first attempt)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None

    def start(self) -> None:
        """Mark sub-transaction as started."""
        self.status = TransactionStatus.RUNNING
        self.attempt += 1
        self.started_at = datetime.utcnow()
        self.error = None

    def complete(self, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark sub-transaction as completed successfully."""
        self.status = TransactionStatus.SUCCESS
        self.completed_at = datetime.utcnow()
        self.result = result

    def fail(self, error: str) -> None:
        """Mark sub-transaction as failed."""
        self.status = TransactionStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error = error

    def retry(self) -> None:
        """Mark sub-transaction for retry."""
        self.status = TransactionStatus.RETRYING
        self.error = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "attempt": self.attempt,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class RecordTransaction:
    """Tracks the complete processing state for a single record (PK)."""
    pk: str  # Business key (e.g., ISSUE-0000000001)
    status: TransactionStatus = TransactionStatus.PENDING
    sub_transactions: Dict[str, SubTransaction] = field(default_factory=dict)
    retry_count: int = 0
    last_error: Optional[str] = None
    last_failed_stage: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    record_data: Optional[Dict[str, Any]] = None  # Original record data for failure file

    def start(self) -> None:
        """Mark record transaction as started."""
        self.status = TransactionStatus.RUNNING
        self.started_at = datetime.utcnow()

    def add_stage(self, stage_name: str) -> SubTransaction:
        """Add a new sub-transaction stage."""
        sub = SubTransaction(name=stage_name)
        self.sub_transactions[stage_name] = sub
        return sub

    def get_stage(self, stage_name: str) -> Optional[SubTransaction]:
        """Get a sub-transaction by name."""
        return self.sub_transactions.get(stage_name)

    def complete(self) -> None:
        """Mark record transaction as completed successfully."""
        self.status = TransactionStatus.SUCCESS
        self.completed_at = datetime.utcnow()

    def fail(self, error: str, stage: str) -> None:
        """Mark record transaction as failed."""
        self.status = TransactionStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.last_error = error
        self.last_failed_stage = stage

    def is_complete(self) -> bool:
        """Check if all sub-transactions completed successfully."""
        return all(
            sub.status == TransactionStatus.SUCCESS
            for sub in self.sub_transactions.values()
        )

    def has_failed(self) -> bool:
        """Check if any sub-transaction has permanently failed."""
        return self.status == TransactionStatus.FAILED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pk": self.pk,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "last_failed_stage": self.last_failed_stage,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "sub_transactions": {
                name: sub.to_dict() for name, sub in self.sub_transactions.items()
            },
        }


@dataclass
class BatchTransaction:
    """Tracks a batch of records being processed together."""
    batch_id: str  # UUID for this batch
    records: Dict[str, RecordTransaction] = field(default_factory=dict)  # pk -> transaction
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def add_record(self, pk: str, record_data: Optional[Dict[str, Any]] = None) -> RecordTransaction:
        """Add a record to the batch."""
        record = RecordTransaction(pk=pk, record_data=record_data)
        self.records[pk] = record
        return record

    def start(self) -> None:
        """Mark batch as started."""
        self.started_at = datetime.utcnow()

    def complete(self) -> None:
        """Mark batch as completed."""
        self.completed_at = datetime.utcnow()

    def get_successful_records(self) -> List[RecordTransaction]:
        """Get all successfully completed records."""
        return [r for r in self.records.values() if r.status == TransactionStatus.SUCCESS]

    def get_failed_records(self) -> List[RecordTransaction]:
        """Get all failed records."""
        return [r for r in self.records.values() if r.status == TransactionStatus.FAILED]

    def get_progress(self) -> Dict[str, int]:
        """Get batch progress statistics."""
        total = len(self.records)
        completed = sum(1 for r in self.records.values() if r.status == TransactionStatus.SUCCESS)
        failed = sum(1 for r in self.records.values() if r.status == TransactionStatus.FAILED)
        in_progress = sum(1 for r in self.records.values() if r.status == TransactionStatus.RUNNING)

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "pending": total - completed - failed - in_progress,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.get_progress(),
            "records": {pk: r.to_dict() for pk, r in self.records.items()},
        }


class TransactionTracker:
    """Manages transaction tracking across batch processing.

    Handles:
    - Batch creation and tracking
    - Per-record sub-transaction tracking
    - Retry logic with configurable max retries
    - Progress calculation
    - Failure file generation
    """

    def __init__(self, batch_size: int = 10, max_retries: int = 3):
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.current_batch: Optional[BatchTransaction] = None
        self.completed_batches: List[BatchTransaction] = []
        self.failed_records: List[Dict[str, Any]] = []
        self._progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_progress_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback to receive progress updates."""
        self._progress_callback = callback

    def start_batch(self, pks: List[str], records_data: Optional[Dict[str, Dict[str, Any]]] = None) -> BatchTransaction:
        """Start a new batch with the given primary keys.

        Args:
            pks: List of primary key values for records in this batch
            records_data: Optional dict mapping pk to record data (for failure file)

        Returns:
            The created BatchTransaction
        """
        batch = BatchTransaction(batch_id=str(uuid.uuid4()))
        batch.start()

        for pk in pks:
            record_data = records_data.get(pk) if records_data else None
            batch.add_record(pk, record_data)

        self.current_batch = batch
        logger.debug("Started batch {} with {} records", batch.batch_id, len(pks))
        return batch

    def start_record(self, pk: str) -> RecordTransaction:
        """Mark a record as started."""
        if not self.current_batch:
            raise ValueError("No active batch")

        record = self.current_batch.records.get(pk)
        if not record:
            raise ValueError(f"Record {pk} not in current batch")

        record.start()
        self._notify_progress()
        return record

    def start_sub_transaction(self, pk: str, stage: str) -> SubTransaction:
        """Start a sub-transaction for a stage."""
        if not self.current_batch:
            raise ValueError("No active batch")

        record = self.current_batch.records.get(pk)
        if not record:
            raise ValueError(f"Record {pk} not in current batch")

        sub = record.get_stage(stage)
        if not sub:
            sub = record.add_stage(stage)

        sub.start()
        return sub

    def complete_sub_transaction(
        self,
        pk: str,
        stage: str,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark a sub-transaction as completed successfully."""
        if not self.current_batch:
            raise ValueError("No active batch")

        record = self.current_batch.records.get(pk)
        if not record:
            raise ValueError(f"Record {pk} not in current batch")

        sub = record.get_stage(stage)
        if not sub:
            raise ValueError(f"Stage {stage} not found for record {pk}")

        sub.complete(result)
        logger.debug("Completed stage {} for record {}", stage, pk)

    def fail_sub_transaction(self, pk: str, stage: str, error: str) -> bool:
        """Mark a sub-transaction as failed.

        Returns:
            True if should retry, False if max retries exceeded
        """
        if not self.current_batch:
            raise ValueError("No active batch")

        record = self.current_batch.records.get(pk)
        if not record:
            raise ValueError(f"Record {pk} not in current batch")

        sub = record.get_stage(stage)
        if not sub:
            raise ValueError(f"Stage {stage} not found for record {pk}")

        if sub.attempt < self.max_retries:
            sub.retry()
            record.retry_count += 1
            logger.warning(
                "Stage {} failed for record {} (attempt {}/{}): {}",
                stage, pk, sub.attempt, self.max_retries, error
            )
            return True  # Should retry
        else:
            sub.fail(error)
            record.fail(error, stage)
            self._add_failed_record(record)
            logger.error(
                "Stage {} permanently failed for record {} after {} retries: {}",
                stage, pk, self.max_retries, error
            )
            self._notify_progress()
            return False  # Max retries exceeded

    def complete_record(self, pk: str) -> None:
        """Mark a record as completed successfully."""
        if not self.current_batch:
            raise ValueError("No active batch")

        record = self.current_batch.records.get(pk)
        if not record:
            raise ValueError(f"Record {pk} not in current batch")

        record.complete()
        logger.debug("Completed record {}", pk)
        self._notify_progress()

    def fail_record(self, pk: str, error: str, stage: str = "unknown") -> None:
        """Mark a record as permanently failed."""
        if not self.current_batch:
            raise ValueError("No active batch")

        record = self.current_batch.records.get(pk)
        if not record:
            raise ValueError(f"Record {pk} not in current batch")

        record.fail(error, stage)
        self._add_failed_record(record)
        self._notify_progress()

    def complete_batch(self) -> BatchTransaction:
        """Complete the current batch and return it."""
        if not self.current_batch:
            raise ValueError("No active batch")

        self.current_batch.complete()
        batch = self.current_batch
        self.completed_batches.append(batch)
        self.current_batch = None

        logger.info(
            "Completed batch {}: {} successful, {} failed",
            batch.batch_id,
            len(batch.get_successful_records()),
            len(batch.get_failed_records())
        )

        return batch

    def get_progress(self) -> Dict[str, Any]:
        """Get overall processing progress.

        Returns dict with:
        - batches_total: Total batches processed
        - batches_completed: Number of completed batches
        - records_total: Total records across all batches
        - records_processed: Successfully processed records
        - records_failed: Failed records
        - current_batch_progress: Progress within current batch (0-100)
        - percent_complete: Overall completion percentage
        """
        completed_records = sum(
            len(b.get_successful_records()) for b in self.completed_batches
        )
        failed_records = len(self.failed_records)
        total_records = completed_records + failed_records

        current_batch_progress = 0
        if self.current_batch:
            batch_progress = self.current_batch.get_progress()
            total_records += batch_progress["total"]
            completed_records += batch_progress["completed"]
            failed_records += batch_progress["failed"]

            batch_done = batch_progress["completed"] + batch_progress["failed"]
            current_batch_progress = int((batch_done / batch_progress["total"]) * 100) if batch_progress["total"] > 0 else 0

        percent_complete = int((completed_records + failed_records) / total_records * 100) if total_records > 0 else 0

        return {
            "batches_total": len(self.completed_batches) + (1 if self.current_batch else 0),
            "batches_completed": len(self.completed_batches),
            "records_total": total_records,
            "records_processed": completed_records,
            "records_failed": failed_records,
            "current_batch_progress": current_batch_progress,
            "percent_complete": percent_complete,
        }

    def get_failed_records(self) -> List[Dict[str, Any]]:
        """Get list of failed records with error details."""
        return self.failed_records

    def write_failure_file(self, upload_id: str, output_path: Path) -> Optional[Path]:
        """Write failed records to a JSON file.

        Args:
            upload_id: The upload batch ID
            output_path: Directory to write the failure file

        Returns:
            Path to the failure file, or None if no failures
        """
        if not self.failed_records:
            return None

        output_path.mkdir(parents=True, exist_ok=True)
        failure_file = output_path / f"{upload_id}_failed_records.json"

        failure_data = {
            "upload_id": upload_id,
            "generated_at": datetime.utcnow().isoformat(),
            "total_failed": len(self.failed_records),
            "records": self.failed_records,
        }

        failure_file.write_text(json.dumps(failure_data, indent=2, default=str))
        logger.info("Written {} failed records to {}", len(self.failed_records), failure_file)

        return failure_file

    def _add_failed_record(self, record: RecordTransaction) -> None:
        """Add a record to the failed records list."""
        self.failed_records.append({
            "pk": record.pk,
            "failed_at_stage": record.last_failed_stage,
            "retry_count": record.retry_count,
            "last_error": record.last_error,
            "record_data": record.record_data,
            "failed_at": datetime.utcnow().isoformat(),
        })

    def _notify_progress(self) -> None:
        """Notify progress callback if set."""
        if self._progress_callback:
            try:
                self._progress_callback(self.get_progress())
            except Exception as e:
                logger.warning("Progress callback failed: {}", e)

    def reset(self) -> None:
        """Reset tracker state for a new processing run."""
        self.current_batch = None
        self.completed_batches = []
        self.failed_records = []
