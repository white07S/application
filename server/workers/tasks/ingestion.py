"""Celery tasks for controls ingestion pipeline.

This module provides Celery tasks for running long-running
ingestion operations in the background without blocking the API.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import traceback

from celery import Task
from celery.signals import task_prerun, task_postrun, worker_process_init
from sqlalchemy.ext.asyncio import AsyncSession

from server.workers.celery_app import celery_app
from server.logging_config import get_logger
from server.pipelines import storage
from server.config.redis import get_redis_sync_client

logger = get_logger(name=__name__)


# Initialize database engine when worker process starts
@worker_process_init.connect
def init_worker_process(**kwargs):
    """Initialize database engine and other resources when worker process starts."""
    logger.info("Initializing worker process...")

    # Initialize PostgreSQL engine for this worker
    from server.config.postgres import init_engine
    from server.settings import get_settings

    settings = get_settings()
    # Use smaller pool for Celery workers
    pool_size = 3
    max_overflow = 5

    init_engine(
        settings.postgres_url,
        pool_size,
        max_overflow
    )
    logger.info("Worker process initialized with PostgreSQL engine")

    # Note: Redis will be initialized per-task in the async context
    # to avoid event loop issues


class IngestionTask(Task):
    """Base class for ingestion tasks with progress tracking."""

    def __init__(self):
        super().__init__()
        self.start_time = None

    def update_progress(self, step: str, current: int, total: int, start_time=None):
        """Update task progress for UI polling.

        Progress updates at ~10% increments.
        """
        if total > 0:
            percent = int((current / total) * 100)
            # Round to nearest 10%
            percent = (percent // 10) * 10
        else:
            percent = 0

        # Store start time on first update if provided
        if start_time and not self.start_time:
            self.start_time = start_time

        self.update_state(
            state='PROGRESS',
            meta={
                'batch_id': self.request.args[0] if self.request.args else None,  # First arg is batch_id
                'current_step': step,
                'records_processed': current,
                'records_total': total,
                'progress_percent': percent,
                'started_at': self.start_time.isoformat() if self.start_time else None,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
        )


@celery_app.task(
    bind=True,
    base=IngestionTask,
    name='server.workers.tasks.ingestion.run_controls_ingestion',
    queue='ingestion',
    time_limit=3600,  # 1 hour hard limit
    soft_time_limit=3000  # 50 min soft limit
)
def run_controls_ingestion_task(
    self,
    batch_id: int,
    upload_id: str,
    job_id: Optional[str] = None
) -> Dict[str, Any]:
    """Run controls ingestion as a Celery task.

    This task runs the full ingestion pipeline including:
    - Reading source JSONL and AI model outputs
    - Inserting/updating PostgreSQL records
    - Upserting embeddings to Qdrant
    - Computing similar controls

    Args:
        batch_id: The batch ID to ingest
        upload_id: The upload ID for the batch
        job_id: Optional job ID for tracking (defaults to task ID)

    Returns:
        Dict with ingestion results including counts and status
    """
    if job_id is None:
        job_id = self.request.id

    redis_client = None
    lock_acquired = False
    start_time = datetime.now(timezone.utc)

    try:
        # Acquire global ingestion lock (only one ingestion at a time)
        redis_client = get_redis_sync_client()
        lock_key = "ingestion:lock"

        # Try to acquire lock with 2-hour expiry (safety against stuck jobs)
        lock_acquired = redis_client.set(
            lock_key,
            job_id,
            nx=True,  # Only set if not exists
            ex=7200  # 2 hour expiry
        )

        if not lock_acquired:
            current_job = redis_client.get(lock_key)
            return {
                'batch_id': batch_id,
                'success': False,
                'message': f"Another ingestion is already running (job: {current_job})",
                'counts': {
                    'total': 0,
                    'processed': 0,
                    'new': 0,
                    'changed': 0,
                    'unchanged': 0,
                    'failed': 0
                }
            }

        logger.info(
            "Starting ingestion task: job_id={}, batch_id={}, upload_id={}",
            job_id, batch_id, upload_id
        )

        # Update initial progress with start time
        self.update_progress("Initializing ingestion...", 0, 100, start_time=start_time)

        # Create new event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run the async ingestion
            result = loop.run_until_complete(
                _run_async_ingestion(self, batch_id, upload_id)
            )

            # Success - update final state
            self.update_progress("Completed", result['counts']['total'], result['counts']['total'])

            logger.info(
                "Ingestion completed successfully: total={}, new={}, changed={}, unchanged={}",
                result['counts']['total'],
                result['counts']['new'],
                result['counts']['changed'],
                result['counts']['unchanged']
            )

            # Add start time to result for duration calculation
            result['started_at'] = start_time.isoformat()

            return result

        finally:
            loop.close()

    except Exception as e:
        logger.exception("Ingestion task failed: {}", str(e))

        # Return a proper error response instead of re-raising
        # This avoids Celery's exception serialization issues
        return {
            'batch_id': batch_id,
            'success': False,
            'message': f"Ingestion failed: {str(e)}",
            'counts': {
                'total': 0,
                'processed': 0,
                'new': 0,
                'changed': 0,
                'unchanged': 0,
                'failed': 0
            },
            'error': str(e),
            'traceback': traceback.format_exc(),
            'started_at': start_time.isoformat() if start_time else None,
            'failed_at': datetime.now(timezone.utc).isoformat()
        }

    finally:
        # Always release locks
        if redis_client and lock_acquired:
            redis_client.delete("ingestion:lock")

        # Release storage processing lock if held
        try:
            storage.release_processing_lock()
        except Exception:
            pass  # Ignore errors during cleanup


async def _run_async_ingestion(task: IngestionTask, batch_id: int, upload_id: str) -> Dict[str, Any]:
    """Run the async ingestion logic.

    This wraps the existing ingestion service and provides progress updates.
    """
    from server.pipelines.controls.ingest.service import run_controls_ingestion
    from server.jobs import get_session_factory_for_background, UploadBatch
    from sqlalchemy import select

    # Initialize Redis for this task's event loop
    from server.config.redis import init_redis
    from server.settings import get_settings
    settings = get_settings()

    try:
        await init_redis(settings.redis_url)
        logger.info("Redis initialized for ingestion task")
    except Exception as e:
        logger.warning("Redis initialization in task: {}", e)
        # Continue anyway - cache invalidation is non-fatal

    # Acquire storage processing lock
    try:
        storage.acquire_processing_lock(upload_id, owner="celery-ingestion")
    except RuntimeError as e:
        return {
            'batch_id': batch_id,
            'success': False,
            'message': f"Could not acquire processing lock: {str(e)}",
            'counts': {
                'total': 0,
                'processed': 0,
                'new': 0,
                'changed': 0,
                'unchanged': 0,
                'failed': 0
            }
        }

    # Create database session
    session_factory = get_session_factory_for_background()

    async with session_factory() as db:
        # Update batch status to processing
        result = await db.execute(
            select(UploadBatch).where(UploadBatch.id == batch_id)
        )
        batch = result.scalar_one_or_none()

        if not batch:
            return {
                'batch_id': batch_id,
                'success': False,
                'message': f"Batch {batch_id} not found",
                'counts': {
                    'total': 0,
                    'processed': 0,
                    'new': 0,
                    'changed': 0,
                    'unchanged': 0,
                    'failed': 0
                }
            }

        batch.status = "processing"
        await db.commit()

        # Create progress callback that updates Celery task state
        async def progress_callback(step: str, processed: int, total: int, percent: int):
            """Update task progress at ~10% increments."""
            # Round to nearest 10%
            rounded_percent = (percent // 10) * 10
            task.update_progress(step, processed, total)

        try:
            # Run the actual ingestion
            ingestion_result = await run_controls_ingestion(
                batch_id=batch_id,
                upload_id=upload_id,
                progress_callback=progress_callback
            )

            # Update batch status based on result
            batch.status = "success" if ingestion_result.success else "failed"
            await db.commit()

            # Invalidate caches after successful ingestion
            if ingestion_result.success:
                try:
                    from server.cache import invalidate_namespace
                    await invalidate_namespace("explorer")
                    await invalidate_namespace("stats")
                    await invalidate_namespace("dashboard")
                    logger.info("Caches invalidated after successful ingestion")
                except Exception as e:
                    logger.warning("Cache invalidation failed (non-fatal): {}", e)

                # Capture dashboard snapshot
                try:
                    from server.explorer.dashboard.snapshot_builder import capture_dashboard_snapshot
                    snapshot_id = await capture_dashboard_snapshot(upload_id=upload_id)
                    logger.info("Dashboard snapshot captured: snapshot_id={}", snapshot_id)
                except Exception as e:
                    logger.warning("Dashboard snapshot failed (non-fatal): {}", e)

            return {
                'batch_id': batch_id,
                'success': ingestion_result.success,
                'message': ingestion_result.message,
                'counts': {
                    'total': ingestion_result.counts.total,
                    'processed': ingestion_result.counts.processed,
                    'new': ingestion_result.counts.new,
                    'changed': ingestion_result.counts.changed,
                    'unchanged': ingestion_result.counts.unchanged,
                    'failed': ingestion_result.counts.failed
                },
                'completed_at': datetime.now(timezone.utc).isoformat()
                # Note: started_at is added by the parent function
            }

        except Exception as e:
            # Update batch status to failed
            batch.status = "failed"
            await db.commit()
            raise


# Signal handlers for logging
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, **kwargs):
    """Log when a task starts."""
    if task and task.name and task.name.startswith('server.workers.tasks.ingestion'):
        logger.info(f"Task {task.name} started with ID {task_id}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, state=None, **kwargs):
    """Log when a task completes."""
    if task and task.name and task.name.startswith('server.workers.tasks.ingestion'):
        logger.info(f"Task {task.name} completed with ID {task_id}, state: {state}")