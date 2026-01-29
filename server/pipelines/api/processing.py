"""API endpoints for data processing (ingestion and model runs)."""
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.database import get_db, DataSource
from server.logging_config import get_logger

from ..processing import service as processing_service

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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
):
    """
    Start ingestion job for a validated batch.

    This triggers the ingestion pipeline that loads parquet files
    into the data layer tables.

    Requires pipelines-admin access.
    """
    access = await get_access_control(token)

    if not access.hasPipelinesAdminAccess:
        raise HTTPException(
            status_code=403,
            detail="Pipelines admin access required to start ingestion"
        )

    try:
        job = processing_service.start_ingestion_job(db, request.batch_id, user_token=token)

        return StartJobResponse(
            success=True,
            message="Ingestion job started successfully",
            job_id=job.job_id,
            batch_id=job.batch_id,
            upload_id=job.upload_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to start ingestion job")
        raise HTTPException(status_code=500, detail="Failed to start ingestion job")


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
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

    job = processing_service.get_job_status(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(**job.to_dict())


@router.get("/batch/{batch_id}/jobs", response_model=List[JobStatusResponse])
async def get_batch_jobs(
    batch_id: int,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    Get all jobs for a specific batch.

    Returns both ingestion and model run jobs for the batch.
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    jobs = processing_service.get_batch_jobs(batch_id)

    return [JobStatusResponse(**job.to_dict()) for job in jobs]


@router.get("/batch/{batch_id}/status", response_model=PipelineStatusResponse)
async def get_batch_status(
    batch_id: int,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """Get pipeline status (ingestion + model steps) for a batch, even after refresh."""
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        status = processing_service.get_batch_pipeline_status(db, batch_id)
        return PipelineStatusResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Failed to fetch batch status")
        raise HTTPException(status_code=500, detail="Failed to fetch batch status")


