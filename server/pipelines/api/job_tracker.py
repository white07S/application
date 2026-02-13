"""Job tracking for processing pipelines (async PostgreSQL).

Provides a simple interface for tracking ingestion jobs
using the ProcessingJob table for atomic, persistent storage.

Job states: pending, running, completed, failed
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.jobs import ProcessingJob
from server.logging_config import get_logger

logger = get_logger(name=__name__)


class JobTracker:
    """PostgreSQL-based job tracker for processing jobs.

    Uses the ProcessingJob table for atomic, persistent storage.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(
        self,
        job_id: str,
        batch_id: int,
        upload_id: str,
        job_type: str = "ingestion",
    ) -> ProcessingJob:
        """Create a new job record."""
        now = datetime.now(timezone.utc)
        job = ProcessingJob(
            id=job_id,
            job_type=job_type,
            batch_id=batch_id,
            upload_id=upload_id,
            status="pending",
            progress_percent=0,
            current_step="Initializing...",
            started_at=now,
            created_at=now,
        )

        self.db.add(job)
        await self.db.flush()

        logger.info(
            "Created job: id={}, type={}, batch={}, upload={}",
            job_id, job_type, batch_id, upload_id,
        )

        return job

    async def update_job_status(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress_percent: Optional[int] = None,
        current_step: Optional[str] = None,
        records_total: Optional[int] = None,
        records_processed: Optional[int] = None,
        records_new: Optional[int] = None,
        records_changed: Optional[int] = None,
        records_unchanged: Optional[int] = None,
        records_failed: Optional[int] = None,
        error_message: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> bool:
        """Update job status and progress. Returns True if found."""
        result = await self.db.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            logger.warning("Job not found: {}", job_id)
            return False

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
        if records_changed is not None:
            job.records_changed = records_changed
        if records_unchanged is not None:
            job.records_unchanged = records_unchanged
        if records_failed is not None:
            job.records_failed = records_failed
        if error_message is not None:
            job.error_message = error_message
        if completed_at is not None:
            job.completed_at = completed_at

        await self.db.flush()

        logger.debug(
            "Updated job {}: status={}, progress={}%",
            job_id, job.status, job.progress_percent,
        )

        return True

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID as dictionary."""
        result = await self.db.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            return None

        return self._job_to_dict(job)

    async def get_batch_jobs(self, batch_id: int) -> List[Dict[str, Any]]:
        """Get all jobs for a specific batch."""
        result = await self.db.execute(
            select(ProcessingJob).where(ProcessingJob.batch_id == batch_id)
        )
        jobs = result.scalars().all()

        return [self._job_to_dict(job) for job in jobs]

    def _job_to_dict(self, job: ProcessingJob) -> Dict[str, Any]:
        """Convert ProcessingJob to dictionary."""
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
            "records_changed": job.records_changed,
            "records_unchanged": job.records_unchanged,
            "records_failed": job.records_failed,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "error_message": job.error_message,
            "duration_seconds": duration,
        }
