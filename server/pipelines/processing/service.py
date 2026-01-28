"""Processing service for ingestion and model runs.

This module provides functions to execute ingestion and model runs
with progress tracking and database persistence.
"""
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from server.database import (
    DataSource, UploadBatch, PipelineRun, IngestionConfig, SessionLocal,
    DLControl, DLIssue, DLIssueAction, DLControlModelOutput, DLIssueModelOutput,
    ProcessingJob,
)
from server.database.models.pipeline import RecordProcessingLog
from server.logging_config import get_logger
from server.auth import token_manager

from .. import storage
from ..config import service as config_service
from . import ingestion
from . import models as model_runner
from . import graph as graph_runner

logger = get_logger(name=__name__)

# In-memory cache for active jobs (backed by database)
_active_jobs: Dict[str, "JobStatus"] = {}
_job_lock = threading.Lock()


@dataclass
class JobStatus:
    """Status of a processing job."""
    job_id: str
    job_type: str  # "ingestion" or "model_run"
    batch_id: int
    upload_id: str
    status: str  # "pending", "running", "completed", "failed"
    progress_percent: int = 0
    current_step: str = ""
    records_total: int = 0
    records_processed: int = 0
    records_new: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    # Summary fields (populated on completion)
    data_type: str = ""
    duration_seconds: float = 0.0
    db_total_records: int = 0  # Total records in DB after job
    # Batch tracking
    batches_total: int = 0
    batches_completed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        # Calculate duration if both timestamps exist
        duration = 0.0
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()

        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "batch_id": self.batch_id,
            "upload_id": self.upload_id,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "current_step": self.current_step,
            "records_total": self.records_total,
            "records_processed": self.records_processed,
            "records_new": self.records_new,
            "records_updated": self.records_updated,
            "records_skipped": self.records_skipped,
            "records_failed": self.records_failed,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "steps": self.steps,
            "data_type": self.data_type,
            "duration_seconds": duration or self.duration_seconds,
            "db_total_records": self.db_total_records,
            "batches_total": self.batches_total,
            "batches_completed": self.batches_completed,
        }


def _create_job_record(db: Session, job: JobStatus) -> ProcessingJob:
    """Create a new ProcessingJob record in database."""
    job_record = ProcessingJob(
        id=job.job_id,
        job_type=job.job_type,
        batch_id=job.batch_id,
        upload_id=job.upload_id,
        status=job.status,
        progress_percent=job.progress_percent,
        current_step=job.current_step,
        records_total=job.records_total,
        records_processed=job.records_processed,
        records_new=job.records_new,
        records_updated=job.records_updated,
        records_skipped=job.records_skipped,
        records_failed=job.records_failed,
        data_type=job.data_type,
        db_total_records=job.db_total_records,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        steps_json=json.dumps(job.steps) if job.steps else None,
        batches_total=job.batches_total,
        batches_completed=job.batches_completed,
        created_at=datetime.utcnow(),
    )
    db.add(job_record)
    return job_record


def _update_job_record(db: Session, job: JobStatus) -> None:
    """Update existing ProcessingJob record in database."""
    job_record = db.query(ProcessingJob).filter_by(id=job.job_id).first()
    if job_record:
        job_record.status = job.status
        job_record.progress_percent = job.progress_percent
        job_record.current_step = job.current_step
        job_record.records_total = job.records_total
        job_record.records_processed = job.records_processed
        job_record.records_new = job.records_new
        job_record.records_updated = job.records_updated
        job_record.records_skipped = job.records_skipped
        job_record.records_failed = job.records_failed
        job_record.data_type = job.data_type
        job_record.db_total_records = job.db_total_records
        job_record.started_at = job.started_at
        job_record.completed_at = job.completed_at
        job_record.error_message = job.error_message
        job_record.steps_json = json.dumps(job.steps) if job.steps else None
        job_record.batches_total = job.batches_total
        job_record.batches_completed = job.batches_completed


def _load_job_from_db(db: Session, job_id: str) -> Optional[JobStatus]:
    """Load a job from database."""
    job_record = db.query(ProcessingJob).filter_by(id=job_id).first()
    if not job_record:
        return None

    return JobStatus(
        job_id=job_record.id,
        job_type=job_record.job_type,
        batch_id=job_record.batch_id,
        upload_id=job_record.upload_id,
        status=job_record.status,
        progress_percent=job_record.progress_percent,
        current_step=job_record.current_step or "",
        records_total=job_record.records_total,
        records_processed=job_record.records_processed,
        records_new=job_record.records_new,
        records_updated=job_record.records_updated,
        records_skipped=job_record.records_skipped,
        records_failed=job_record.records_failed,
        data_type=job_record.data_type or "",
        db_total_records=job_record.db_total_records,
        started_at=job_record.started_at,
        completed_at=job_record.completed_at,
        error_message=job_record.error_message,
        steps=json.loads(job_record.steps_json) if job_record.steps_json else [],
        batches_total=job_record.batches_total,
        batches_completed=job_record.batches_completed,
    )


def get_validated_batches(db: Session) -> List[Dict]:
    """Get all batches that have been validated and are ready for processing.

    Returns batches with status 'validated' along with their parquet files info.
    """
    batches = db.query(UploadBatch).filter(
        UploadBatch.status.in_(["validated", "processing", "success"])
    ).order_by(UploadBatch.created_at.desc()).all()

    result = []
    for batch in batches:
        # Get data source
        source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
        data_type = source.source_code if source else "unknown"

        # Get parquet files
        parquet_files = config_service.get_parquet_files_for_batch(db, batch.id)
        # Estimate PK count by reading main parquet unique PK
        pk_records = None
        try:
            configs = config_service.get_ingestion_configs_by_source(db, data_type)
            main_config = next((c for c in configs if c.target_table_name in ("dl_issues", "dl_controls", "dl_issues_actions")), None)
            if main_config:
                preprocessed_path = storage.get_preprocessed_batch_path(batch.upload_id, data_type)
                parquet_file = preprocessed_path / main_config.source_parquet_name
                if parquet_file.exists():
                    import pandas as pd
                    pk_cols = json.loads(main_config.primary_key_columns)
                    df = pd.read_parquet(parquet_file, columns=pk_cols)
                    pk_records = df.drop_duplicates().shape[0]
        except Exception as e:
            logger.warning("Failed to compute pk_records for batch {}: {}", batch.upload_id, e)

        # Check if ingestion has been run
        ingestion_run = db.query(PipelineRun).filter_by(
            upload_batch_id=batch.id,
            pipeline_type="ingestion"
        ).order_by(PipelineRun.created_at.desc()).first()

        # Check if model run has been done
        model_run = db.query(PipelineRun).filter_by(
            upload_batch_id=batch.id,
            pipeline_type="model_run"
        ).order_by(PipelineRun.created_at.desc()).first()

        result.append({
            "batch_id": batch.id,
            "upload_id": batch.upload_id,
            "data_type": data_type,
            "status": batch.status,
            "file_count": batch.file_count,
            "total_records": batch.total_records,
            "uploaded_by": batch.uploaded_by,
            "created_at": batch.created_at.isoformat(),
            "parquet_files": parquet_files,
            "parquet_count": len(parquet_files),
            "pk_records": pk_records,
            "ingestion_status": ingestion_run.status if ingestion_run else None,
            "ingestion_run_id": ingestion_run.id if ingestion_run else None,
            "model_run_status": model_run.status if model_run else None,
            "model_run_id": model_run.id if model_run else None,
            "can_ingest": batch.status == "validated" and (not ingestion_run or ingestion_run.status == "failed"),
            "can_run_model": bool(ingestion_run and ingestion_run.status == "success" and (not model_run or model_run.status == "failed")),
        })

    return result


def start_ingestion_job(db: Session, batch_id: int, user_token: Optional[str] = None) -> JobStatus:
    """Start an ingestion job for a batch.

    This creates a job record and returns immediately.
    The actual processing runs in a background thread.

    Args:
        db: Database session
        batch_id: ID of the batch to process
        user_token: User's access token for acquiring Graph API token
    """
    # Prevent concurrent pipeline runs
    if storage.is_processing_locked():
        raise ValueError("Another pipeline is currently running. Please wait for it to complete.")

    batch = db.query(UploadBatch).filter_by(id=batch_id).first()
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")

    if batch.status != "validated":
        raise ValueError(f"Batch {batch_id} is not in validated state (status: {batch.status})")

    # Create job
    job_id = str(uuid.uuid4())
    job = JobStatus(
        job_id=job_id,
        job_type="ingestion",
        batch_id=batch_id,
        upload_id=batch.upload_id,
        status="pending",
        started_at=datetime.utcnow(),
    )

    # Store in memory (thread-safe)
    with _job_lock:
        _active_jobs[job_id] = job

    # Create pipeline run record
    run = PipelineRun(
        upload_batch_id=batch_id,
        pipeline_type="ingestion",
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(run)

    # Create processing job record in database
    _create_job_record(db, job)

    # Update batch status
    batch.status = "processing"
    db.commit()  # Commit so background thread can see the records

    # Acquire lock for this batch
    storage.acquire_processing_lock(batch.upload_id, owner="ingestion")

    # Get IDs for background thread
    run_id = run.id
    upload_id = batch.upload_id
    data_source_id = batch.data_source_id

    logger.info("Started ingestion job: job_id={}, batch_id={}", job_id, batch_id)

    # Acquire Graph token before starting background thread
    # This ensures token is acquired while we still have the user's token
    graph_token = None
    if user_token:
        graph_token = token_manager.acquire_graph_token_sync(user_token)
        if graph_token:
            logger.info("Acquired Graph token for ingestion job: {}", token_manager.get_trimmed_token(graph_token))
        else:
            logger.warning("Failed to acquire Graph token, proceeding without it")

    # Run the actual ingestion in background thread
    def run_in_background():
        bg_db = SessionLocal()
        try:
            bg_batch = bg_db.query(UploadBatch).filter_by(id=batch_id).first()
            bg_run = bg_db.query(PipelineRun).filter_by(id=run_id).first()
            _run_ingestion(bg_db, job, bg_run, bg_batch, graph_token=graph_token)
        except Exception as e:
            logger.exception("Background ingestion failed: {}", str(e))
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            _update_job_record(bg_db, job)
            bg_db.commit()
        finally:
            storage.release_processing_lock()
            bg_db.close()

    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()

    return job


def start_model_run_job(db: Session, batch_id: int, user_token: Optional[str] = None) -> JobStatus:
    """Start a model run job for a batch.

    Requires ingestion to be completed first.
    The actual processing runs in a background thread.

    Args:
        db: Database session
        batch_id: ID of the batch to process
        user_token: User's access token for acquiring Graph API token
    """
    if storage.is_processing_locked():
        raise ValueError("Another pipeline is currently running. Please wait for it to complete.")

    batch = db.query(UploadBatch).filter_by(id=batch_id).first()
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")

    # Check if ingestion is complete
    ingestion_run = db.query(PipelineRun).filter_by(
        upload_batch_id=batch_id,
        pipeline_type="ingestion",
        status="success"
    ).first()

    if not ingestion_run:
        raise ValueError(f"Batch {batch_id} has not been ingested yet")

    # Create job
    job_id = str(uuid.uuid4())
    job = JobStatus(
        job_id=job_id,
        job_type="model_run",
        batch_id=batch_id,
        upload_id=batch.upload_id,
        status="pending",
        started_at=datetime.utcnow(),
    )

    # Store in memory (thread-safe)
    with _job_lock:
        _active_jobs[job_id] = job

    # Create pipeline run record
    run = PipelineRun(
        upload_batch_id=batch_id,
        pipeline_type="model_run",
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(run)

    # Create processing job record in database
    _create_job_record(db, job)
    db.commit()  # Commit so background thread can see the records

    # Acquire lock for this batch
    storage.acquire_processing_lock(batch.upload_id, owner="model_run")

    # Get IDs for background thread
    run_id = run.id

    logger.info("Started model run job: job_id={}, batch_id={}", job_id, batch_id)

    # Acquire Graph token before starting background thread
    graph_token = None
    if user_token:
        graph_token = token_manager.acquire_graph_token_sync(user_token)
        if graph_token:
            logger.info("Acquired Graph token for model run job: {}", token_manager.get_trimmed_token(graph_token))
        else:
            logger.warning("Failed to acquire Graph token, proceeding without it")

    # Run actual model processing in background thread
    def run_in_background():
        bg_db = SessionLocal()
        try:
            bg_batch = bg_db.query(UploadBatch).filter_by(id=batch_id).first()
            bg_run = bg_db.query(PipelineRun).filter_by(id=run_id).first()
            _run_model_processing(bg_db, job, bg_run, bg_batch, graph_token=graph_token)
        except Exception as e:
            logger.exception("Background model run failed: {}", str(e))
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            _update_job_record(bg_db, job)
            bg_db.commit()
        finally:
            storage.release_processing_lock()
            bg_db.close()

    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()

    return job


def get_job_status(job_id: str) -> Optional[JobStatus]:
    """Get the status of a job.

    First checks in-memory cache, then falls back to database.
    """
    # Check in-memory cache first
    with _job_lock:
        if job_id in _active_jobs:
            return _active_jobs[job_id]

    # Fall back to database
    db = SessionLocal()
    try:
        return _load_job_from_db(db, job_id)
    finally:
        db.close()


def get_batch_jobs(batch_id: int) -> List[JobStatus]:
    """Get all jobs for a batch."""
    jobs = []

    # Check in-memory cache
    with _job_lock:
        jobs.extend([job for job in _active_jobs.values() if job.batch_id == batch_id])

    # Also check database for completed jobs not in cache
    db = SessionLocal()
    try:
        db_jobs = db.query(ProcessingJob).filter_by(batch_id=batch_id).all()
        cached_ids = {j.job_id for j in jobs}
        for job_record in db_jobs:
            if job_record.id not in cached_ids:
                job = _load_job_from_db(db, job_record.id)
                if job:
                    jobs.append(job)
    finally:
        db.close()

    return jobs


def get_batch_pipeline_status(db: Session, batch_id: int) -> Dict[str, Any]:
    """Return pipeline status and per-step summaries for a batch."""
    batch = db.query(UploadBatch).filter_by(id=batch_id).first()
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")

    source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
    data_type = source.source_code if source else "unknown"

    steps: List[Dict[str, Any]] = []

    # Ingestion summary
    ingestion_run = db.query(PipelineRun).filter_by(
        upload_batch_id=batch_id,
        pipeline_type="ingestion"
    ).order_by(PipelineRun.created_at.desc()).first()

    ingestion = None
    if ingestion_run:
        ingestion = {
            "status": ingestion_run.status,
            "records_total": ingestion_run.records_total,
            "records_processed": ingestion_run.records_processed,
            "records_inserted": ingestion_run.records_inserted,
            "records_updated": ingestion_run.records_updated,
            "records_skipped": ingestion_run.records_skipped,
            "records_failed": ingestion_run.records_failed,
            "pipeline_run_id": ingestion_run.id,
        }

    # Aggregate per-step progress from record_processing_log
    log_counts = (
        db.query(
            RecordProcessingLog.stage,
            RecordProcessingLog.operation,
        )
        .filter(RecordProcessingLog.pipeline_run_id == (ingestion_run.id if ingestion_run else -1))
        .all()
    )

    # Model steps: nfr_taxonomy, enrichment, embeddings
    for step_type in ["nfr_taxonomy", "enrichment", "embeddings"]:
        run = db.query(PipelineRun).filter_by(
            upload_batch_id=batch_id,
            pipeline_type=step_type
        ).order_by(PipelineRun.created_at.desc()).first()
        if run:
            steps.append({
                "name": step_type.replace("_", " ").title(),
                "type": step_type,
                "status": run.status,
                "records_processed": run.records_processed,
                "records_failed": run.records_failed,
                "records_skipped": run.records_skipped,
                "pipeline_run_id": run.id,
            })

    return {
        "batch_id": batch.id,
        "upload_id": batch.upload_id,
        "data_type": data_type,
        "ingestion": ingestion,
        "records_total": ingestion_run.records_total if ingestion_run else None,
        "records_processed": ingestion_run.records_processed if ingestion_run else None,
        "records_failed": ingestion_run.records_failed if ingestion_run else None,
        "steps": steps,
    }


def _run_ingestion(db: Session, job: JobStatus, run: PipelineRun, batch: UploadBatch, graph_token: Optional[str] = None):
    """Run real ingestion processing.

    Processes parquet files through the graph runner with batch processing.
    Note: Uses serial processing for SQLite compatibility.

    Args:
        db: Database session
        job: Job status tracker
        run: Pipeline run record
        batch: Upload batch to process
        graph_token: Microsoft Graph API token for model calls
    """
    import time as time_module  # Local import to avoid conflict with time fields

    source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
    data_type = source.source_code if source else "unknown"

    job.status = "running"
    job.current_step = "Initializing..."
    job.data_type = data_type
    run.status = "running"
    run.started_at = datetime.utcnow()
    _update_job_record(db, job)
    db.flush()

    # Throttled progress updates (serial processing, no threading needed)
    last_db_update = [time_module.time()]
    update_interval = 1.0  # Update DB at most once per second

    def progress_cb(step_name: str, percent: int, stats: Dict[str, Any]):
        # Update in-memory job state
        job.current_step = step_name
        job.progress_percent = percent
        job.records_total = stats.get("records_total", job.records_total)
        job.records_processed = stats.get("records_processed", job.records_processed)
        job.records_new = stats.get("records_inserted", job.records_new)
        job.records_updated = stats.get("records_updated", job.records_updated)
        job.records_failed = stats.get("records_failed", job.records_failed)
        job.batches_total = stats.get("batches_total", job.batches_total)
        job.batches_completed = stats.get("batches_completed", job.batches_completed)

        # Throttled DB update to avoid excessive writes
        current_time = time_module.time()
        if current_time - last_db_update[0] >= update_interval:
            try:
                _update_job_record(db, job)
                db.flush()
                last_db_update[0] = current_time
            except Exception as e:
                logger.warning("Progress DB update failed (will retry): {}", e)
                # Rollback if flush failed, then continue
                try:
                    db.rollback()
                except Exception:
                    pass

    try:
        stats = graph_runner.run_graph_for_batch(
            db=db,
            batch=batch,
            pipeline_run=run,
            progress_callback=progress_cb,
            graph_token=graph_token,
        )

        job.status = "completed"
        job.progress_percent = 100
        job.current_step = "Completed"
        job.completed_at = datetime.utcnow()
        job.data_type = data_type
        job.records_total = stats.get("records_total", job.records_total)
        job.records_processed = stats.get("records_processed", job.records_processed)
        job.records_new = stats.get("records_inserted", job.records_new)
        job.records_updated = stats.get("records_updated", job.records_updated)
        job.records_skipped = stats.get("records_skipped", 0)
        job.records_failed = stats.get("records_failed", job.records_failed)
        job.batches_total = stats.get("batches_total", 0)
        job.batches_completed = stats.get("batches_completed", 0)

        db_total = 0
        if data_type == "controls":
            db_total = db.query(DLControl).filter(DLControl.is_current == True).count()
        elif data_type == "issues":
            db_total = db.query(DLIssue).filter(DLIssue.is_current == True).count()
        elif data_type == "actions":
            db_total = db.query(DLIssueAction).filter(DLIssueAction.is_current == True).count()
        job.db_total_records = db_total

        run.status = "success"
        run.completed_at = datetime.utcnow()
        run.records_total = job.records_total
        run.records_processed = job.records_processed

        batch.status = "success"
        batch.total_records = job.records_new + job.records_updated

        _update_job_record(db, job)
        db.commit()

        try:
            storage.cleanup_upload_batch(batch.upload_id, data_type)
        except Exception as cleanup_err:
            logger.warning("Failed to cleanup batch files for {}: {}", batch.upload_id, cleanup_err)

        logger.info(
            "Graph ingestion completed: job_id={}, processed={}, new={}, updated={}",
            job.job_id, job.records_processed, job.records_new, job.records_updated
        )
    except Exception as e:
        logger.exception("Graph ingestion failed: {}", e)
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        run.status = "failed"
        run.error_details = str(e)
        batch.status = "failed"
        _update_job_record(db, job)
        db.commit()


def _run_model_processing(db: Session, job: JobStatus, run: PipelineRun, batch: UploadBatch, graph_token: Optional[str] = None):
    """Run actual model processing on ingested data.

    Executes NFR taxonomy classification, enrichment, and embeddings
    on records that were ingested in this batch.

    Args:
        db: Database session
        job: Job status tracker
        run: Pipeline run record
        batch: Upload batch to process
        graph_token: Microsoft Graph API token for model calls
    """
    # Log token availability for debugging
    logger.info("Model processing starting with token: {}", token_manager.get_trimmed_token(graph_token))
    job.status = "running"
    job.current_step = "Initializing models..."
    run.status = "running"
    run.started_at = datetime.utcnow()
    _update_job_record(db, job)
    db.flush()

    def progress_callback(step_name: str, percent: int, stats: model_runner.ModelRunStats):
        """Update job progress during model run."""
        job.current_step = f"Running {step_name}..."
        job.progress_percent = percent
        job.records_processed = stats.records_processed
        _update_job_record(db, job)
        db.flush()

    try:
        # Run all model functions
        stats, step_details = model_runner.run_models_for_batch(
            db=db,
            batch=batch,
            pipeline_run=run,
            progress_callback=progress_callback,
        )

        # Update job with results
        job.records_total = stats.records_total
        job.records_processed = stats.records_processed
        job.records_new = stats.records_processed  # All model outputs are "new"
        job.records_skipped = stats.records_skipped
        job.records_failed = stats.records_failed
        job.steps = step_details

        if stats.records_failed > 0:
            job.status = "failed"
            run.status = "failed"
            run.error_details = "One or more model steps failed"
        else:
            # Complete the job
            job.status = "completed"
            job.progress_percent = 100
            job.current_step = "Completed"
        job.completed_at = datetime.utcnow()

        # Get data type and total model outputs
        source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
        data_type = source.source_code if source else "unknown"
        job.data_type = data_type

        # Get total current model outputs for this data type
        db_total = 0
        if data_type == "controls":
            db_total = db.query(DLControlModelOutput).filter(DLControlModelOutput.is_current == True).count()
        elif data_type == "issues":
            db_total = db.query(DLIssueModelOutput).filter(DLIssueModelOutput.is_current == True).count()
        job.db_total_records = db_total

        if run.status != "failed":
            run.status = "success"
        run.completed_at = datetime.utcnow()
        run.records_total = stats.records_total
        run.records_processed = stats.records_processed

        _update_job_record(db, job)
        db.commit()

        logger.info(
            "Model run completed: job_id={}, records={}, processed={}, skipped={}, db_total={}",
            job.job_id, stats.records_total, stats.records_processed,
            stats.records_skipped, db_total
        )

    except Exception as e:
        logger.exception("Model run failed: job_id={}", job.job_id)
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()

        run.status = "failed"
        run.completed_at = datetime.utcnow()
        run.error_details = str(e)

        _update_job_record(db, job)
        db.commit()
