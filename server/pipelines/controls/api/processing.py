"""API endpoints for controls ingestion (async PostgreSQL).

Provides endpoints for listing validated batches with readiness status,
triggering ingestion, and polling job progress.

Background ingestion uses asyncio.create_task() instead of threading.Thread,
eliminating the sync/async boundary.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.jobs import get_jobs_db, get_session_factory_for_background, UploadBatch, ProcessingJob
from server.logging_config import get_logger

from ..ingest.service import run_controls_ingestion, IngestionResult
from ..readiness import check_ingestion_readiness
from ... import storage
from ...api.job_tracker import JobTracker
from ...processing import service as processing_service

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/ingestion", tags=["Ingestion"])


# ============== Response Models ==============

class ReadinessInfo(BaseModel):
    ready: bool
    source_jsonl: bool
    taxonomy: bool
    enrichment: bool
    clean_text: bool
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
    job_type: str
    batch_id: int
    upload_id: str
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
    created_at: Optional[str]
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
    """Start ingestion job for a validated batch.

    Checks readiness (all model outputs available), then runs
    controls ingestion into PostgreSQL + Qdrant as a background asyncio task.

    Requires pipelines-admin access.
    """
    access = await get_access_control(token)

    if not access.hasPipelinesAdminAccess:
        raise HTTPException(
            status_code=403,
            detail="Pipelines admin access required to start ingestion"
        )

    lock_acquired = False
    try:
        # Prevent concurrent pipeline runs
        if storage.is_processing_locked():
            raise HTTPException(
                status_code=409,
                detail="Another pipeline is currently running. Please wait for it to complete."
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

        # Check readiness
        readiness = check_ingestion_readiness(batch.upload_id)
        if not readiness.ready:
            raise HTTPException(
                status_code=400,
                detail=readiness.message or "Model outputs are not ready for ingestion"
            )

        # Create job
        job_id = str(uuid.uuid4())
        tracker = JobTracker(db)
        await tracker.create_job(
            job_id=job_id,
            batch_id=request.batch_id,
            upload_id=batch.upload_id,
            job_type="ingestion",
        )

        # Acquire lock
        try:
            storage.acquire_processing_lock(batch.upload_id, owner="ingestion")
            lock_acquired = True
        except RuntimeError as lock_err:
            raise HTTPException(status_code=409, detail=str(lock_err))

        # Update batch status
        batch.status = "processing"
        await db.commit()

        logger.info(
            "Started ingestion job: job_id={}, batch_id={}, upload_id={}",
            job_id, request.batch_id, batch.upload_id
        )

        # Launch background task (async, no thread needed)
        _batch_id = request.batch_id
        _upload_id = batch.upload_id
        asyncio.create_task(
            _run_ingestion_background(job_id, _batch_id, _upload_id)
        )

        return StartInsertResponse(
            success=True,
            message="Ingestion job started successfully",
            job_id=job_id,
            batch_id=request.batch_id,
            upload_id=batch.upload_id,
        )

    except HTTPException:
        if lock_acquired:
            storage.release_processing_lock()
        raise
    except ValueError as e:
        if lock_acquired:
            storage.release_processing_lock()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to start ingestion job")
        if lock_acquired:
            storage.release_processing_lock()
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion job: {str(e)}")


async def _run_ingestion_background(job_id: str, batch_id: int, upload_id: str) -> None:
    """Background async task that runs ingestion with its own DB session."""
    session_factory = get_session_factory_for_background()

    async with session_factory() as bg_db:
        bg_tracker = JobTracker(bg_db)

        try:
            # Update job to running
            await bg_tracker.update_job_status(
                job_id=job_id,
                status="running",
                current_step="Starting controls ingestion...",
                progress_percent=5,
            )
            await bg_db.commit()

            # Async progress callback
            async def on_progress(step: str, processed: int, total: int, percent: int):
                await bg_tracker.update_job_status(
                    job_id=job_id,
                    current_step=step,
                    records_processed=processed,
                    records_total=total,
                    progress_percent=max(5, min(95, percent)),
                )
                await bg_db.commit()

            # Run ingestion (already async, no thread boundary)
            result: IngestionResult = await run_controls_ingestion(
                batch_id=batch_id,
                upload_id=upload_id,
                progress_callback=on_progress,
            )

            now = datetime.now(timezone.utc)

            if not result.success:
                await bg_tracker.update_job_status(
                    job_id=job_id,
                    status="failed",
                    current_step="Ingestion failed",
                    error_message=result.message,
                    records_total=result.counts.total,
                    records_processed=result.counts.processed,
                    records_new=result.counts.new,
                    records_changed=result.counts.changed,
                    records_unchanged=result.counts.unchanged,
                    records_failed=result.counts.failed,
                    progress_percent=100,
                    completed_at=now,
                )

                bg_batch_result = await bg_db.execute(
                    select(UploadBatch).where(UploadBatch.id == batch_id)
                )
                bg_batch = bg_batch_result.scalar_one_or_none()
                if bg_batch:
                    bg_batch.status = "failed"

                await bg_db.commit()
                return

            # Ingestion succeeded
            await bg_tracker.update_job_status(
                job_id=job_id,
                status="completed",
                current_step="Completed",
                progress_percent=100,
                records_total=result.counts.total,
                records_processed=result.counts.processed,
                records_new=result.counts.new,
                records_changed=result.counts.changed,
                records_unchanged=result.counts.unchanged,
                records_failed=result.counts.failed,
                completed_at=now,
            )

            bg_batch_result = await bg_db.execute(
                select(UploadBatch).where(UploadBatch.id == batch_id)
            )
            bg_batch = bg_batch_result.scalar_one_or_none()
            if bg_batch:
                bg_batch.status = "success"

            await bg_db.commit()

            logger.info(
                "Ingestion job completed: job_id={}, total={}, new={}, changed={}, unchanged={}",
                job_id, result.counts.total, result.counts.new,
                result.counts.changed, result.counts.unchanged,
            )

        except Exception as e:
            logger.exception("Background ingestion failed: {}", str(e))
            await bg_tracker.update_job_status(
                job_id=job_id,
                status="failed",
                error_message=str(e),
                completed_at=datetime.now(timezone.utc),
            )

            bg_batch_result = await bg_db.execute(
                select(UploadBatch).where(UploadBatch.id == batch_id)
            )
            bg_batch = bg_batch_result.scalar_one_or_none()
            if bg_batch:
                bg_batch.status = "failed"

            await bg_db.commit()

        finally:
            storage.release_processing_lock()


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    token: str = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_jobs_db),
):
    """Get the status of an ingestion job."""
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    tracker = JobTracker(db)
    job_data = await tracker.get_job(job_id)

    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(**job_data)
