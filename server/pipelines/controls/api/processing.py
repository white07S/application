"""API endpoints for data processing (ingestion and model runs)."""
import asyncio
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.jobs import get_jobs_db, UploadBatch
from server.jobs.engine import get_session_local
from server.logging_config import get_logger
from server.config.surrealdb import get_surrealdb_connection
from server.config.settings import get_settings

from ..ingest.service import run_ingestion, IngestionResult
from ..ingest.tracker import IngestionTracker
from ..models.runner import run_model_pipeline_batch, get_pipeline_stats
from ..models.cache import ModelCache
from ..consumer.service import ControlsConsumer
from ... import storage
from ...api.job_tracker import JobTracker
from ...processing import service as processing_service

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/processing", tags=["Processing"])


# ============== Response Models ==============

class ParquetFileInfo(BaseModel):
    filename: str
    path: str
    size_bytes: int
    modified_at: float


class ValidatedBatchResponse(BaseModel):
    batch_id: int
    upload_id: str
    data_type: str
    status: str
    file_count: Optional[int]
    total_records: Optional[int]
    pk_records: Optional[int] = None
    uploaded_by: Optional[str]
    created_at: str
    parquet_files: List[ParquetFileInfo]
    parquet_count: int
    ingestion_status: Optional[str]
    ingestion_run_id: Optional[int]
    model_run_status: Optional[str]
    model_run_id: Optional[int]
    can_ingest: bool
    can_run_model: bool


class ValidatedBatchesListResponse(BaseModel):
    batches: List[ValidatedBatchResponse]
    total: int


class JobStepInfo(BaseModel):
    step: int
    name: str
    target_table: Optional[str] = None
    type: Optional[str] = None
    records_processed: int
    records_new: Optional[int] = None
    records_updated: Optional[int] = None
    completed_at: str


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
    records_updated: int
    records_skipped: int = 0
    records_failed: int
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    steps: List[Dict[str, Any]]
    # Summary fields
    data_type: str = ""
    duration_seconds: float = 0.0
    db_total_records: int = 0
    pk_records: Optional[int] = None
    # Batch tracking
    batches_total: int = 0
    batches_completed: int = 0


class StartJobRequest(BaseModel):
    batch_id: int


class StartJobResponse(BaseModel):
    success: bool
    message: str
    job_id: str
    batch_id: int
    upload_id: str


class PipelineStepStatus(BaseModel):
    name: str
    type: str
    status: str
    records_processed: int = 0
    records_failed: int = 0
    records_skipped: int = 0
    pipeline_run_id: Optional[int] = None
    records_total: Optional[int] = None


class PipelineStatusResponse(BaseModel):
    batch_id: int
    upload_id: str
    data_type: str
    ingestion: Optional[dict]
    steps: List[PipelineStepStatus]
    records_total: Optional[int] = None
    records_processed: Optional[int] = None
    records_failed: Optional[int] = None


# ============== Endpoints ==============

@router.get("/batches", response_model=ValidatedBatchesListResponse)
async def get_validated_batches(
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
):
    """
    Get all validated batches ready for processing.

    Returns batches that have passed validation and have parquet files,
    along with their ingestion and model run status.
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    batches = processing_service.get_validated_batches(db)

    return ValidatedBatchesListResponse(
        batches=[ValidatedBatchResponse(**b) for b in batches],
        total=len(batches)
    )


@router.post("/ingest", response_model=StartJobResponse)
async def start_ingestion(
    request: StartJobRequest,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
):
    """
    Start ingestion job for a validated batch.

    This triggers the new SurrealDB ingestion pipeline that:
    1. Loads split CSV files into SurrealDB (src_controls_* tables)
    2. Runs model pipeline for new/changed controls
    3. Cleans up parquet files after success

    Requires pipelines-admin access.
    """
    access = await get_access_control(token)

    if not access.hasPipelinesAdminAccess:
        raise HTTPException(
            status_code=403,
            detail="Pipelines admin access required to start ingestion"
        )

    try:
        # Prevent concurrent pipeline runs
        if storage.is_processing_locked():
            raise HTTPException(
                status_code=409,
                detail="Another pipeline is currently running. Please wait for it to complete."
            )

        # Get batch
        batch = db.query(UploadBatch).filter_by(id=request.batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail=f"Batch {request.batch_id} not found")

        if batch.status != "validated":
            raise HTTPException(
                status_code=400,
                detail=f"Batch {request.batch_id} is not in validated state (status: {batch.status})"
            )

        # Get data type from batch
        data_type = batch.data_type

        # Create job tracker
        job_id = str(uuid.uuid4())
        tracker = JobTracker(db)
        job = tracker.create_job(
            job_id=job_id,
            batch_id=request.batch_id,
            upload_id=batch.upload_id,
            job_type="ingestion",
            data_type=data_type,
        )

        # Update batch status
        batch.status = "processing"
        db.commit()

        # Acquire lock
        storage.acquire_processing_lock(batch.upload_id, owner="ingestion")

        logger.info(
            "Started SurrealDB ingestion job: job_id={}, batch_id={}, upload_id={}",
            job_id, request.batch_id, batch.upload_id
        )

        # Get paths
        split_dir = storage.get_split_batch_path(batch.upload_id, data_type)
        preprocessed_dir = storage.get_preprocessed_batch_path(batch.upload_id, data_type)

        # Run ingestion in background thread
        def run_in_background():
            """Background thread that runs ingestion + model pipeline."""
            bg_db = get_session_local()()
            bg_tracker = JobTracker(bg_db)

            try:
                # Update job to running
                bg_tracker.update_job_status(
                    job_id=job_id,
                    status="running",
                    current_step="Starting SurrealDB ingestion...",
                    progress_percent=5,
                )
                bg_db.commit()

                # Run ingestion (async in sync context)
                ingestion_result: IngestionResult = asyncio.run(
                    run_ingestion(
                        batch_id=batch.upload_id,
                        split_dir=split_dir,
                        is_base=False,  # Always delta ingestion
                        graph_token=token,
                    )
                )

                if not ingestion_result.success:
                    # Ingestion failed
                    bg_tracker.update_job_status(
                        job_id=job_id,
                        status="failed",
                        current_step="Ingestion failed",
                        error_message=ingestion_result.message,
                        progress_percent=50,
                        completed_at=datetime.utcnow(),
                    )

                    bg_batch = bg_db.query(UploadBatch).filter_by(id=request.batch_id).first()
                    if bg_batch:
                        bg_batch.status = "failed"

                    bg_db.commit()
                    return

                # Ingestion succeeded - update job progress
                stats = ingestion_result.stats
                bg_tracker.update_job_status(
                    job_id=job_id,
                    status="running",
                    current_step="Running model pipeline...",
                    progress_percent=60,
                    records_total=stats.get("total_records", 0),
                    records_processed=stats.get("processed_records", 0),
                    records_new=stats.get("new_records", 0),
                    records_updated=stats.get("updated_records", 0),
                )
                bg_db.commit()

                # Run model pipeline for new and changed controls
                controls_to_process = ingestion_result.new_control_ids + ingestion_result.changed_control_ids

                if controls_to_process:
                    logger.info(
                        "Running model pipeline for {} controls (new={}, changed={})",
                        len(controls_to_process),
                        len(ingestion_result.new_control_ids),
                        len(ingestion_result.changed_control_ids)
                    )

                    # Initialize model cache using configured path
                    settings = get_settings()
                    settings.ensure_model_cache_dir()
                    cache = ModelCache(cache_dir=settings.model_output_cache_path)

                    # Load split CSV tables for model pipeline (need control data)
                    # Model pipeline expects pandas DataFrames
                    import pandas as pd
                    from ..ingest.base import CSV_FILES

                    tables = {}
                    for table_name, csv_file in CSV_FILES.items():
                        csv_path = split_dir / csv_file
                        if csv_path.exists():
                            tables[table_name] = pd.read_csv(csv_path)

                    # Prepare controls list with record IDs
                    from ..consumer.queries import normalize_control_id_for_record
                    controls_list = [
                        {
                            "control_id": cid,
                            "record_id": normalize_control_id_for_record(cid),
                        }
                        for cid in controls_to_process
                    ]

                    # Run model pipeline batch
                    async def run_models():
                        async with get_surrealdb_connection() as db_conn:
                            return await run_model_pipeline_batch(
                                db=db_conn,
                                controls=controls_list,
                                tables=tables,
                                cache=cache,
                                graph_token=token,
                            )

                    model_results = asyncio.run(run_models())
                    pipeline_stats = get_pipeline_stats(model_results)

                    logger.info(
                        "Model pipeline completed: total={}, successful={}, failed={}",
                        pipeline_stats["total"],
                        pipeline_stats["successful"],
                        pipeline_stats["failed"]
                    )

                    # Update job with model results
                    bg_tracker.update_job_status(
                        job_id=job_id,
                        current_step="Cleaning up...",
                        progress_percent=90,
                        batches_total=len(controls_to_process),
                        batches_completed=pipeline_stats["successful"],
                    )
                    bg_db.commit()

                # Job completed successfully
                bg_tracker.update_job_status(
                    job_id=job_id,
                    status="completed",
                    current_step="Completed",
                    progress_percent=100,
                    completed_at=datetime.utcnow(),
                )

                bg_batch = bg_db.query(UploadBatch).filter_by(id=request.batch_id).first()
                if bg_batch:
                    bg_batch.status = "success"

                bg_db.commit()

                # Clean up parquet files after success
                try:
                    storage.cleanup_upload_batch(batch.upload_id, data_type)
                    logger.info("Cleaned up parquet files for batch {}", batch.upload_id)
                except Exception as cleanup_err:
                    logger.warning("Failed to cleanup batch files: {}", cleanup_err)

                logger.info("Ingestion job completed successfully: job_id={}", job_id)

            except Exception as e:
                logger.exception("Background ingestion failed: {}", str(e))
                bg_tracker.update_job_status(
                    job_id=job_id,
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.utcnow(),
                )

                bg_batch = bg_db.query(UploadBatch).filter_by(id=request.batch_id).first()
                if bg_batch:
                    bg_batch.status = "failed"

                bg_db.commit()

            finally:
                storage.release_processing_lock()
                bg_db.close()

        # Start background thread
        thread = threading.Thread(target=run_in_background, daemon=True)
        thread.start()

        return StartJobResponse(
            success=True,
            message="Ingestion job started successfully",
            job_id=job_id,
            batch_id=request.batch_id,
            upload_id=batch.upload_id,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to start ingestion job")
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion job: {str(e)}")


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
):
    """
    Get the status of a processing job.

    Returns progress information including:
    - Current step and progress percentage
    - Records processed, new, updated
    - Detailed step-by-step progress
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    # Use JobTracker to get job status
    tracker = JobTracker(db)
    job_data = tracker.get_job(job_id)

    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Return job data with proper format
    return JobStatusResponse(
        job_id=job_data["job_id"],
        job_type=job_data["job_type"],
        batch_id=job_data["batch_id"],
        upload_id=job_data["upload_id"],
        status=job_data["status"],
        progress_percent=job_data["progress_percent"],
        current_step=job_data["current_step"],
        records_total=job_data["records_total"],
        records_processed=job_data["records_processed"],
        records_new=job_data["records_new"],
        records_updated=job_data["records_updated"],
        records_skipped=job_data["records_skipped"],
        records_failed=job_data["records_failed"],
        started_at=job_data["started_at"],
        completed_at=job_data["completed_at"],
        error_message=job_data["error_message"],
        steps=[],  # Not tracked in new system yet
        data_type=job_data["data_type"],
        duration_seconds=job_data["duration_seconds"],
        db_total_records=job_data["db_total_records"],
        batches_total=job_data["batches_total"],
        batches_completed=job_data["batches_completed"],
    )


@router.get("/batch/{batch_id}/jobs", response_model=List[JobStatusResponse])
async def get_batch_jobs(
    batch_id: int,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
):
    """
    Get all jobs for a specific batch.

    Returns both ingestion and model run jobs for the batch.
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    # Use JobTracker to get all jobs for this batch
    tracker = JobTracker(db)
    jobs_data = tracker.get_batch_jobs(batch_id)

    return [
        JobStatusResponse(
            job_id=job["job_id"],
            job_type=job["job_type"],
            batch_id=job["batch_id"],
            upload_id=job["upload_id"],
            status=job["status"],
            progress_percent=job["progress_percent"],
            current_step=job["current_step"],
            records_total=job["records_total"],
            records_processed=job["records_processed"],
            records_new=job["records_new"],
            records_updated=job["records_updated"],
            records_skipped=job["records_skipped"],
            records_failed=job["records_failed"],
            started_at=job["started_at"],
            completed_at=job["completed_at"],
            error_message=job["error_message"],
            steps=[],
            data_type=job["data_type"],
            duration_seconds=job["duration_seconds"],
            db_total_records=job["db_total_records"],
            batches_total=job["batches_total"],
            batches_completed=job["batches_completed"],
        )
        for job in jobs_data
    ]


@router.get("/batch/{batch_id}/status", response_model=PipelineStatusResponse)
async def get_batch_status(
    batch_id: int,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
):
    """Get pipeline status (ingestion + model steps) for a batch from SurrealDB.

    This queries SurrealDB to get the current state of:
    - Ingestion (controls loaded into src_controls_main)
    - Model pipeline steps (taxonomy, enrichment, clean_text, embeddings)
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        # Get batch info
        batch = db.query(UploadBatch).filter_by(id=batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

        data_type = batch.data_type

        # Query SurrealDB for pipeline status
        async def get_surreal_status():
            async with get_surrealdb_connection() as db_conn:
                consumer = ControlsConsumer()
                consumer.db = db_conn

                # Get table counts to determine what's been processed
                counts = await consumer.get_table_counts()

                # Build status response
                from ..schema import (
                    SRC_CONTROLS_MAIN,
                    AI_CONTROLS_MODEL_TAXONOMY_CURRENT,
                    AI_CONTROLS_MODEL_ENRICHMENT_CURRENT,
                    AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT,
                    AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT,
                )

                ingestion_count = counts.get(SRC_CONTROLS_MAIN, 0)
                taxonomy_count = counts.get(AI_CONTROLS_MODEL_TAXONOMY_CURRENT, 0)
                enrichment_count = counts.get(AI_CONTROLS_MODEL_ENRICHMENT_CURRENT, 0)
                clean_text_count = counts.get(AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT, 0)
                embeddings_count = counts.get(AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT, 0)

                # Determine status based on counts
                ingestion_status = {
                    "status": "completed" if ingestion_count > 0 else "pending",
                    "records_total": ingestion_count,
                    "records_processed": ingestion_count,
                }

                steps = []

                if taxonomy_count > 0:
                    steps.append({
                        "name": "Taxonomy Classification",
                        "type": "taxonomy",
                        "status": "completed",
                        "records_processed": taxonomy_count,
                        "records_total": ingestion_count,
                        "records_failed": 0,
                        "records_skipped": 0,
                    })

                if enrichment_count > 0:
                    steps.append({
                        "name": "Enrichment Analysis",
                        "type": "enrichment",
                        "status": "completed",
                        "records_processed": enrichment_count,
                        "records_total": ingestion_count,
                        "records_failed": 0,
                        "records_skipped": 0,
                    })

                if clean_text_count > 0:
                    steps.append({
                        "name": "Text Cleaning",
                        "type": "clean_text",
                        "status": "completed",
                        "records_processed": clean_text_count,
                        "records_total": ingestion_count,
                        "records_failed": 0,
                        "records_skipped": 0,
                    })

                if embeddings_count > 0:
                    steps.append({
                        "name": "Embeddings Generation",
                        "type": "embeddings",
                        "status": "completed",
                        "records_processed": embeddings_count,
                        "records_total": ingestion_count,
                        "records_failed": 0,
                        "records_skipped": 0,
                    })

                return {
                    "batch_id": batch_id,
                    "upload_id": batch.upload_id,
                    "data_type": data_type,
                    "ingestion": ingestion_status,
                    "steps": steps,
                    "records_total": ingestion_count,
                    "records_processed": ingestion_count,
                    "records_failed": 0,
                }

        status = await get_surreal_status()
        return PipelineStatusResponse(**status)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch batch status from SurrealDB")
        raise HTTPException(status_code=500, detail=f"Failed to fetch batch status: {str(e)}")


