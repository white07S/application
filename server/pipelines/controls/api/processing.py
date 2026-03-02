"""API endpoints for controls ingestion using Celery.

Provides endpoints for listing validated batches with readiness status,
triggering ingestion via Celery, and polling job progress.

Uses Celery for background processing instead of asyncio.create_task,
ensuring non-blocking operation across multiple workers.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.jobs import get_jobs_db, UploadBatch
from server.logging_config import get_logger
from server.workers.celery_app import celery_app

from ..readiness import check_ingestion_readiness
from ...processing import service as processing_service

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/ingestion", tags=["Ingestion"])


# ============== Response Models ==============

class ReadinessInfo(BaseModel):
    ready: bool
    source_jsonl: bool
    taxonomy: bool
    enrichment: bool
    feature_prep: bool
    embeddings: bool
    missing_models: List[str] = []
    missing_control_ids: Dict[str, List[str]] = {}
    message: Optional[str] = None


class ValidatedBatchResponse(BaseModel):
    batch_id: int
    upload_id: str
    data_type: str
    status: str
    file_count: Optional[int]
    total_records: Optional[int]
    uploaded_by: Optional[str]
    created_at: str
    readiness: ReadinessInfo
    can_ingest: bool
    ingestion_status: Optional[str]
    message: Optional[str]


class ValidatedBatchesListResponse(BaseModel):
    batches: List[ValidatedBatchResponse]
    total: int


class JobStatusResponse(BaseModel):
    job_id: str
    batch_id: Optional[int]  # Need this for UI to match job with batch
    status: str
    progress_percent: int
    current_step: str
    records_total: int
    records_processed: int
    records_new: int
    records_changed: int
    records_unchanged: int
    records_failed: int
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    duration_seconds: float = 0.0


class StartInsertRequest(BaseModel):
    batch_id: int


class StartInsertResponse(BaseModel):
    success: bool
    message: str
    job_id: str
    batch_id: int
    upload_id: str


# ============== Endpoints ==============

@router.get("/batches", response_model=ValidatedBatchesListResponse)
async def get_validated_batches(
    token: str = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_jobs_db),
):
    """Get all validated batches with ingestion readiness status."""
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    batches = await processing_service.get_validated_batches(db)

    return ValidatedBatchesListResponse(
        batches=[ValidatedBatchResponse(**b) for b in batches],
        total=len(batches)
    )


@router.post("/insert", response_model=StartInsertResponse)
async def start_ingestion(
    request: StartInsertRequest,
    token: str = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_jobs_db),
):
    """Start ingestion job via Celery for a validated batch.

    Submits ingestion task to Celery queue for background processing.
    Only one ingestion can run at a time (enforced by Celery task).

    Requires pipelines-admin access.
    """
    access = await get_access_control(token)

    if not access.hasPipelinesAdminAccess:
        raise HTTPException(
            status_code=403,
            detail="Pipelines admin access required to start ingestion"
        )

    # Get batch
    result = await db.execute(
        select(UploadBatch).where(UploadBatch.id == request.batch_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {request.batch_id} not found")

    if batch.status not in ("validated", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Batch {request.batch_id} is not in a re-runnable state (status: {batch.status})"
        )

    # Check predecessor upload was successfully ingested
    predecessor = await db.execute(
        select(UploadBatch)
        .where(UploadBatch.upload_id < batch.upload_id)
        .where(UploadBatch.data_type == batch.data_type)
        .order_by(UploadBatch.upload_id.desc())
        .limit(1)
    )
    prev_batch = predecessor.scalar_one_or_none()

    if prev_batch and prev_batch.status != "success":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot ingest {batch.upload_id}: predecessor {prev_batch.upload_id} "
                f"has status '{prev_batch.status}' (must be 'success'). "
                f"Please ingest {prev_batch.upload_id} first."
            ),
        )

    # Check readiness
    readiness = check_ingestion_readiness(batch.upload_id)
    if not readiness.ready:
        raise HTTPException(
            status_code=400,
            detail=readiness.message or "Model outputs are not ready for ingestion"
        )

    # Check if an ingestion is already running (via Celery)
    from server.config.redis import get_redis_sync_client
    redis_client = get_redis_sync_client()

    if redis_client.get("ingestion:lock"):
        # Get the running job ID
        running_job = redis_client.get("ingestion:lock")
        if running_job:
            # Check if the job is actually still running
            result = AsyncResult(running_job, app=celery_app)
            if result.state in ['PENDING', 'PROGRESS']:
                raise HTTPException(
                    status_code=409,
                    detail=f"Another ingestion is currently running (job: {running_job})"
                )
            else:
                # Job is done but lock wasn't cleaned up, remove it
                redis_client.delete("ingestion:lock")

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Submit to Celery
    from server.workers.tasks.ingestion import run_controls_ingestion_task

    task = run_controls_ingestion_task.apply_async(
        args=[request.batch_id, batch.upload_id],
        task_id=job_id,  # Use our job ID as the Celery task ID
        queue='ingestion'  # Ensure it goes to the ingestion queue
    )

    logger.info(
        "Submitted ingestion job to Celery: job_id={}, batch_id={}, upload_id={}",
        job_id, request.batch_id, batch.upload_id
    )

    return StartInsertResponse(
        success=True,
        message="Ingestion job queued successfully",
        job_id=job_id,
        batch_id=request.batch_id,
        upload_id=batch.upload_id,
    )


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    token: str = Depends(get_token_from_header),
):
    """Get the status of an ingestion job from Celery.

    Polls Celery for task status and returns progress information.
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get task result from Celery
    result = AsyncResult(job_id, app=celery_app)

    # Try to get state, but handle corrupted results
    try:
        task_state = result.state
    except (ValueError, KeyError, TypeError) as e:
        # Handle corrupted task result in Redis
        logger.warning(f"Corrupted task result for job {job_id}: {e}")

        # Try to clean up the bad result
        try:
            result.forget()  # Remove from backend
        except Exception:
            pass

        # Return a failed status
        return JobStatusResponse(
            job_id=job_id,
            batch_id=None,  # Can't determine batch_id from corrupted result
            status='failed',
            progress_percent=0,
            current_step='Task result corrupted',
            records_total=0,
            records_processed=0,
            records_new=0,
            records_changed=0,
            records_unchanged=0,
            records_failed=0,
            started_at=None,
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message='Task result was corrupted. Please retry the ingestion.',
        )

    # Map Celery states to our response format
    if task_state == 'PENDING':
        # Task not started yet - try to get batch_id from args
        batch_id = None
        try:
            # Try to get batch_id from task args (if available)
            if hasattr(result, 'args') and result.args:
                batch_id = result.args[0]
        except:
            pass

        return JobStatusResponse(
            job_id=job_id,
            batch_id=batch_id,
            status='queued',
            progress_percent=0,
            current_step='Waiting to start...',
            records_total=0,
            records_processed=0,
            records_new=0,
            records_changed=0,
            records_unchanged=0,
            records_failed=0,
            started_at=None,
            completed_at=None,
            error_message=None,
        )

    elif task_state == 'PROGRESS':
        # Task is running, get progress info
        info = result.info or {}

        # Calculate elapsed duration while running
        duration = 0.0
        if 'started_at' in info:
            try:
                started = datetime.fromisoformat(info['started_at'])
                now = datetime.now(timezone.utc)
                duration = (now - started).total_seconds()
            except Exception:
                pass

        return JobStatusResponse(
            job_id=job_id,
            batch_id=info.get('batch_id'),  # Get batch_id from progress metadata
            status='running',
            progress_percent=info.get('progress_percent', 0),
            current_step=info.get('current_step', 'Processing...'),
            records_total=info.get('records_total', 0),
            records_processed=info.get('records_processed', 0),
            records_new=0,  # Will be updated on completion
            records_changed=0,
            records_unchanged=0,
            records_failed=0,
            started_at=info.get('started_at'),  # Use the actual start time
            completed_at=None,  # Not completed yet
            error_message=None,  # No error
            duration_seconds=duration,
        )

    elif task_state == 'SUCCESS':
        # Task completed - check if it actually succeeded or failed
        info = result.info or {}

        # Check if the task returned an error (we return errors as success with error flag)
        if not info.get('success', True):
            # Task completed but with an error
            return JobStatusResponse(
                job_id=job_id,
                batch_id=info.get('batch_id'),
                status='failed',
                progress_percent=100,
                current_step='Failed',
                records_total=0,
                records_processed=0,
                records_new=0,
                records_changed=0,
                records_unchanged=0,
                records_failed=0,
                started_at=None,
                completed_at=info.get('failed_at', datetime.now(timezone.utc).isoformat()),
                error_message=info.get('message', 'Unknown error'),
            )

        # Task actually succeeded
        counts = info.get('counts', {})

        # Calculate duration if we have timestamps
        duration = 0.0
        if 'completed_at' in info and 'started_at' in info:
            try:
                completed = datetime.fromisoformat(info['completed_at'])
                started = datetime.fromisoformat(info.get('started_at', info['completed_at']))
                duration = (completed - started).total_seconds()
            except Exception:
                pass

        return JobStatusResponse(
            job_id=job_id,
            batch_id=info.get('batch_id'),
            status='completed',
            progress_percent=100,
            current_step='Completed',
            records_total=counts.get('total', 0),
            records_processed=counts.get('processed', 0),
            records_new=counts.get('new', 0),
            records_changed=counts.get('changed', 0),
            records_unchanged=counts.get('unchanged', 0),
            records_failed=counts.get('failed', 0),
            started_at=info.get('started_at'),  # May be None if not tracked
            completed_at=info.get('completed_at'),
            error_message=None,  # No error on success
            duration_seconds=duration,
        )

    elif task_state == 'FAILURE':
        # Task failed
        info = result.info or {}

        # Handle exception info
        error_message = 'Unknown error'
        batch_id = None
        if isinstance(info, dict):
            error_message = info.get('message', str(info))
            batch_id = info.get('batch_id')
        else:
            error_message = str(info)

        return JobStatusResponse(
            job_id=job_id,
            batch_id=batch_id,
            status='failed',
            progress_percent=100,
            current_step='Failed',
            records_total=0,
            records_processed=0,
            records_new=0,
            records_changed=0,
            records_unchanged=0,
            records_failed=0,
            started_at=None,  # May not have started properly
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=error_message,
        )

    else:
        # Other states (RETRY, REVOKED, etc.)
        # Try to get batch_id from result info if available
        batch_id = None
        if hasattr(result, 'info') and isinstance(result.info, dict):
            batch_id = result.info.get('batch_id')

        return JobStatusResponse(
            job_id=job_id,
            batch_id=batch_id,
            status=task_state.lower(),
            progress_percent=0,
            current_step=f"Status: {task_state}",
            records_total=0,
            records_processed=0,
            records_new=0,
            records_changed=0,
            records_unchanged=0,
            records_failed=0,
            started_at=None,
            completed_at=None,
            error_message=None,
        )


@router.delete("/job/{job_id}")
async def cancel_job(
    job_id: str,
    token: str = Depends(get_token_from_header),
):
    """Cancel a running ingestion job.

    Revokes the Celery task if it's still pending or running.
    """
    access = await get_access_control(token)

    if not access.hasPipelinesAdminAccess:
        raise HTTPException(
            status_code=403,
            detail="Pipelines admin access required to cancel jobs"
        )

    # Get task and check state
    result = AsyncResult(job_id, app=celery_app)

    if result.state in ['PENDING', 'PROGRESS']:
        # Revoke the task
        result.revoke(terminate=True)
        logger.info(f"Cancelled ingestion job: {job_id}")

        # Clean up the lock if this job holds it
        from server.config.redis import get_redis_sync_client
        redis_client = get_redis_sync_client()
        lock_value = redis_client.get("ingestion:lock")
        if lock_value and lock_value == job_id:
            redis_client.delete("ingestion:lock")

        return {"success": True, "message": f"Job {job_id} cancelled"}
    else:
        return {"success": False, "message": f"Job {job_id} is not running (state: {result.state})"}


@router.get("/jobs/active")
async def get_active_jobs(
    token: str = Depends(get_token_from_header),
):
    """Get list of active ingestion jobs.

    Returns all jobs that are currently queued or running.
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get active tasks from Celery
    inspect = celery_app.control.inspect()

    active_jobs = []

    # Get active tasks
    active = inspect.active()
    if active:
        for worker, tasks in active.items():
            for task in tasks:
                if task['name'] == 'server.workers.tasks.ingestion.run_controls_ingestion':
                    active_jobs.append({
                        'job_id': task['id'],
                        'status': 'running',
                        'worker': worker,
                        'args': task.get('args', []),
                    })

    # Get scheduled tasks
    scheduled = inspect.scheduled()
    if scheduled:
        for worker, tasks in scheduled.items():
            for task in tasks:
                if task['name'] == 'server.workers.tasks.ingestion.run_controls_ingestion':
                    active_jobs.append({
                        'job_id': task['id'],
                        'status': 'queued',
                        'worker': worker,
                        'args': task.get('args', []),
                    })

    return {"active_jobs": active_jobs, "total": len(active_jobs)}