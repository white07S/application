"""Job tracking for processing pipelines.

This module provides a simple interface for tracking ingestion and model run jobs
using the ProcessingJob SQLite table for atomic, persistent storage.

Job states: pending, running, completed, failed
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from server.jobs import ProcessingJob
from server.logging_config import get_logger

logger = get_logger(name=__name__)


class JobTracker:
    """SQLite-based job tracker for processing jobs.

    Uses the ProcessingJob table for atomic, persistent storage.
    Provides a simple interface for creating, updating, and querying jobs.
    """

    def __init__(self, db: Session):
        """Initialize job tracker with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_job(
        self,
        job_id: str,
        batch_id: int,
        upload_id: str,
        job_type: str,
        data_type: str = "",
    ) -> ProcessingJob:
        """Create a new job record.

        Args:
            job_id: Unique job identifier (UUID)
            batch_id: Upload batch ID
            upload_id: Upload ID (UPL-YYYY-XXXX)
            job_type: Type of job ("ingestion" or "model_run")
            data_type: Type of data being processed (controls, issues, actions)

        Returns:
            The created ProcessingJob record
        """
        job = ProcessingJob(
            id=job_id,
            job_type=job_type,
            batch_id=batch_id,
            upload_id=upload_id,
            status="pending",
            progress_percent=0,
            current_step="Initializing...",
            data_type=data_type,
            started_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

        self.db.add(job)
        self.db.flush()

        logger.info(
            "Created job: id={}, type={}, batch={}, upload={}",
            job_id, job_type, batch_id, upload_id
        )

        return job

    def update_job_status(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress_percent: Optional[int] = None,
        current_step: Optional[str] = None,
        records_total: Optional[int] = None,
        records_processed: Optional[int] = None,
        records_new: Optional[int] = None,
        records_updated: Optional[int] = None,
        records_skipped: Optional[int] = None,
        records_failed: Optional[int] = None,
        batches_total: Optional[int] = None,
        batches_completed: Optional[int] = None,
        error_message: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> bool:
        """Update job status and progress.

        Args:
            job_id: Job identifier
            status: New status (pending, running, completed, failed)
            progress_percent: Progress percentage (0-100)
            current_step: Current step description
            records_total: Total records to process
            records_processed: Records processed so far
            records_new: New records inserted
            records_updated: Records updated
            records_skipped: Records skipped
            records_failed: Records that failed
            batches_total: Total batches
            batches_completed: Batches completed
            error_message: Error message if failed
            completed_at: Completion timestamp

        Returns:
            True if job was found and updated, False otherwise
        """
        job = self.db.query(ProcessingJob).filter_by(id=job_id).first()

        if not job:
            logger.warning("Job not found: {}", job_id)
            return False

        # Update fields that are provided (not None)
        if status is not None:
            job.status = status
        if progress_percent is not None:
            job.progress_percent = progress_percent
        if current_step is not None:
            job.current_step = current_step
        if records_total is not None:
            job.records_total = records_total
        if records_processed is not None:
            job.records_processed = records_processed
        if records_new is not None:
            job.records_new = records_new
        if records_updated is not None:
            job.records_updated = records_updated
        if records_skipped is not None:
            job.records_skipped = records_skipped
        if records_failed is not None:
            job.records_failed = records_failed
        if batches_total is not None:
            job.batches_total = batches_total
        if batches_completed is not None:
            job.batches_completed = batches_completed
        if error_message is not None:
            job.error_message = error_message
        if completed_at is not None:
            job.completed_at = completed_at

        self.db.flush()

        logger.debug(
            "Updated job {}: status={}, progress={}%",
            job_id, job.status, job.progress_percent
        )

        return True

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job data as dictionary, or None if not found
        """
        job = self.db.query(ProcessingJob).filter_by(id=job_id).first()

        if not job:
            return None

        return self._job_to_dict(job)

    def get_batch_jobs(self, batch_id: int) -> List[Dict[str, Any]]:
        """Get all jobs for a specific batch.

        Args:
            batch_id: Upload batch ID

        Returns:
            List of job data dictionaries
        """
        jobs = self.db.query(ProcessingJob).filter_by(batch_id=batch_id).all()

        return [self._job_to_dict(job) for job in jobs]

    def _job_to_dict(self, job: ProcessingJob) -> Dict[str, Any]:
        """Convert ProcessingJob to dictionary.

        Args:
            job: ProcessingJob record

        Returns:
            Job data as dictionary
        """
        # Calculate duration if both timestamps exist
        duration = 0.0
        if job.started_at and job.completed_at:
            duration = (job.completed_at - job.started_at).total_seconds()

        return {
            "job_id": job.id,
            "job_type": job.job_type,
            "batch_id": job.batch_id,
            "upload_id": job.upload_id,
            "status": job.status,
            "progress_percent": job.progress_percent,
            "current_step": job.current_step or "",
            "records_total": job.records_total,
            "records_processed": job.records_processed,
            "records_new": job.records_new,
            "records_updated": job.records_updated,
            "records_skipped": job.records_skipped,
            "records_failed": job.records_failed,
            "batches_total": job.batches_total,
            "batches_completed": job.batches_completed,
            "data_type": job.data_type or "",
            "db_total_records": job.db_total_records,
            "started_at": job.started_at.isoformat() + "Z" if job.started_at else None,
            "completed_at": job.completed_at.isoformat() + "Z" if job.completed_at else None,
            "created_at": job.created_at.isoformat() + "Z" if job.created_at else None,
            "error_message": job.error_message,
            "duration_seconds": duration,
        }
