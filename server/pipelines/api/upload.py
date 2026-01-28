"""V2 Pipeline API endpoints with database tracking."""
import datetime
import json
import shutil
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.database import get_db, UploadBatch, DataSource
from server.logging_config import get_logger

from .. import upload_tracker
from .. import storage
from ..validation import service as validation_service

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/pipelines", tags=["Pipelines V2"])


# ============== Response Models ==============

class UploadResponse(BaseModel):
    """Response for upload endpoint."""
    success: bool
    upload_id: str
    batch_id: int
    status: str
    data_type: str
    files_received: int
    source_path: str

class BatchStatusResponse(BaseModel):
    """Response for batch status endpoint."""
    upload_id: str
    batch_id: int
    data_type: str
    status: str
    file_count: Optional[int]
    total_records: Optional[int]
    started_at: Optional[str]
    completed_at: Optional[str]
    error_code: Optional[str]
    error_details: Optional[str]
    created_at: str

class BatchListResponse(BaseModel):
    """Response for batch list endpoint."""
    batches: List[BatchStatusResponse]
    total: int


class IngestionRecord(BaseModel):
    """Record format for ingestion history (compatible with v1 API)."""
    ingestionId: str
    dataType: str
    filesCount: int
    fileNames: List[str]
    totalSizeBytes: int
    uploadedBy: str
    uploadedAt: str
    status: str


class IngestionHistoryResponse(BaseModel):
    """Response for ingestion history endpoint (compatible with v1 API)."""
    records: List[IngestionRecord]
    total: int


class ValidationStatusResponse(BaseModel):
    """Response for validation status endpoint."""
    run_id: int
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    records_total: int
    records_processed: int
    records_failed: int
    error_details: Optional[dict]


# ============== Endpoints ==============

@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    data_type: Literal["issues", "controls", "actions"] = Form(...),
    files: List[UploadFile] = File(...),
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    Upload data files for processing.

    This endpoint:
    1. Validates basic file requirements (count, extension, size)
    2. Creates an upload batch record in the database
    3. Stores files in the uploads directory
    4. Returns the batch ID for tracking

    Processing is done separately (either automatically or via process endpoint).

    - **data_type**: Type of data being uploaded (issues, controls, or actions)
    - **files**: Excel files to upload
        - issues: exactly 4 xlsx files
        - controls: exactly 1 xlsx file
        - actions: exactly 1 xlsx file
    """
    # Check authentication and authorization
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        logger.warning("User {} denied access to pipelines upload", access.user)
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to upload pipeline data",
        )

    logger.info(
        "Upload request from user %s: data_type=%s, files=%d",
        access.user, data_type, len(files),
    )

    # Basic validation
    expected_counts = {"issues": 4, "controls": 1, "actions": 1}
    expected_count = expected_counts.get(data_type)

    if len(files) != expected_count:
        raise HTTPException(
            status_code=400,
            detail=f"Expected {expected_count} file(s) for {data_type}, got {len(files)}"
        )

    min_size_bytes = 5 * 1024  # 5KB minimum

    for file in files:
        if not file.filename or not file.filename.lower().endswith(".xlsx"):
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' must be an .xlsx file"
            )

        # Check size
        content = await file.read()
        await file.seek(0)

        if len(content) < min_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' is too small. Minimum size is 5KB"
            )

    # Create upload batch in database
    # First generate the upload_id to create the path
    upload_id = upload_tracker.generate_upload_id()
    batch_path = storage.get_upload_batch_path(upload_id, data_type)

    # Create batch record (we need to create it manually since we already have upload_id)
    data_source_id = upload_tracker.get_data_source_id(db, data_type)

    batch = UploadBatch(
        upload_id=upload_id,
        data_source_id=data_source_id,
        status="pending",
        source_path=str(batch_path),
        uploaded_by=access.user,
        file_count=len(files),
        created_at=datetime.datetime.utcnow(),
    )
    db.add(batch)
    db.flush()

    # Create upload directory and save files
    batch_path.mkdir(parents=True, exist_ok=True)

    try:
        for file in files:
            content = await file.read()
            file_path = batch_path / file.filename
            file_path.write_bytes(content)
            logger.info("Saved file: {}", file_path)
    except Exception as e:
        # Cleanup on failure
        if batch_path.exists():
            shutil.rmtree(batch_path)
        db.rollback()
        logger.exception("Failed to save uploaded files")
        raise HTTPException(status_code=500, detail="Failed to save uploaded files")

    db.commit()

    logger.info(
        "Upload batch created: upload_id=%s, batch_id=%d, data_type=%s, files=%d",
        batch.upload_id, batch.id, data_type, len(files)
    )

    # Run validation with tracking
    success, parquet_tables, validation_run = validation_service.run_validation(
        db=db,
        batch=batch,
        data_type=data_type,
        batch_path=batch_path,
    )

    db.commit()

    if not success:
        # Get validation details from the run
        validation_status = validation_service.get_validation_status(db, batch.id)
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Validation failed",
                "upload_id": batch.upload_id,
                "batch_id": batch.id,
                "validation_run_id": validation_run.id,
                "errors": validation_status.get("error_details") if validation_status else None,
            }
        )

    logger.info(
        "Validation successful for batch %s (run_id=%d)",
        batch.upload_id, validation_run.id
    )

    return UploadResponse(
        success=True,
        upload_id=batch.upload_id,
        batch_id=batch.id,
        status=batch.status,
        data_type=data_type,
        files_received=len(files),
        source_path=str(batch_path),
    )


@router.get("/upload/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: int,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    Get the status of an upload batch.

    - **batch_id**: The batch ID returned from upload
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    batch = upload_tracker.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    # Get data type from data source
    source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
    data_type = source.source_code if source else "unknown"

    return BatchStatusResponse(
        upload_id=batch.upload_id,
        batch_id=batch.id,
        data_type=data_type,
        status=batch.status,
        file_count=batch.file_count,
        total_records=batch.total_records,
        started_at=batch.started_at.isoformat() if batch.started_at else None,
        completed_at=batch.completed_at.isoformat() if batch.completed_at else None,
        error_code=batch.error_code,
        error_details=batch.error_details,
        created_at=batch.created_at.isoformat(),
    )


@router.get("/batches", response_model=BatchListResponse)
async def list_batches(
    status: Optional[str] = Query(None, description="Filter by status"),
    data_type: Optional[str] = Query(None, description="Filter by data type"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    List upload batches with optional filtering.

    - **status**: Filter by status (pending, validating, processing, success, failed)
    - **data_type**: Filter by data type (issues, controls, actions)
    - **limit**: Maximum records to return (1-100)
    - **offset**: Records to skip for pagination
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(UploadBatch)

    if status:
        query = query.filter(UploadBatch.status == status)

    if data_type:
        source = db.query(DataSource).filter_by(source_code=data_type).first()
        if source:
            query = query.filter(UploadBatch.data_source_id == source.id)

    total = query.count()
    batches = query.order_by(UploadBatch.created_at.desc()).offset(offset).limit(limit).all()

    result = []
    for batch in batches:
        source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
        result.append(BatchStatusResponse(
            upload_id=batch.upload_id,
            batch_id=batch.id,
            data_type=source.source_code if source else "unknown",
            status=batch.status,
            file_count=batch.file_count,
            total_records=batch.total_records,
            started_at=batch.started_at.isoformat() if batch.started_at else None,
            completed_at=batch.completed_at.isoformat() if batch.completed_at else None,
            error_code=batch.error_code,
            error_details=batch.error_details,
            created_at=batch.created_at.isoformat(),
        ))

    return BatchListResponse(batches=result, total=total)


@router.get("/history", response_model=IngestionHistoryResponse)
async def get_ingestion_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    Get ingestion history records in a format compatible with the v1 API.

    This endpoint returns batch records in the same format as the old /pipelines/history
    endpoint for backward compatibility with existing clients.

    - **limit**: Maximum number of records to return (1-100, default 50)
    - **offset**: Number of records to skip (default 0)
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        logger.warning("User {} denied access to pipelines ingestion history", access.user)
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access pipelines ingestion",
        )

    # Query batches ordered by creation time (newest first)
    query = db.query(UploadBatch).order_by(UploadBatch.created_at.desc())
    total = query.count()
    batches = query.offset(offset).limit(limit).all()

    records = []
    for batch in batches:
        # Get data type from data source
        source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
        data_type = source.source_code if source else "unknown"

        # Get file names and sizes from the source path
        file_names = []
        total_size_bytes = 0
        source_path = Path(batch.source_path)

        if source_path.exists():
            for file_path in source_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() == ".xlsx":
                    file_names.append(file_path.name)
                    total_size_bytes += file_path.stat().st_size

        records.append(IngestionRecord(
            ingestionId=batch.upload_id,
            dataType=data_type,
            filesCount=batch.file_count or len(file_names),
            fileNames=file_names,
            totalSizeBytes=total_size_bytes,
            uploadedBy=batch.uploaded_by or "system",
            uploadedAt=batch.created_at.isoformat(),
            status=batch.status,
        ))

    return IngestionHistoryResponse(records=records, total=total)


@router.get("/validation/{batch_id}", response_model=ValidationStatusResponse)
async def get_validation_status(
    batch_id: int,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    Get the validation status for an upload batch.

    Returns details about the validation pipeline run, including:
    - Status (pending, running, success, failed)
    - Record counts (total, processed, failed)
    - Error details if validation failed

    - **batch_id**: The batch ID to get validation status for
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    status = validation_service.get_validation_status(db, batch_id)

    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"No validation run found for batch {batch_id}"
        )

    return ValidationStatusResponse(
        run_id=status["run_id"],
        status=status["status"],
        started_at=status["started_at"],
        completed_at=status["completed_at"],
        records_total=status["records_total"],
        records_processed=status["records_processed"],
        records_failed=status["records_failed"],
        error_details=status["error_details"],
    )
