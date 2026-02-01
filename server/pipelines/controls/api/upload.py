"""V2 Pipeline API endpoints - Ingestion History."""
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.jobs import get_jobs_db, UploadBatch
from server.logging_config import get_logger

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/pipelines", tags=["Pipelines V2"])


# ============== Response Models ==============

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


# ============== Endpoints ==============

@router.get("/history", response_model=IngestionHistoryResponse)
async def get_ingestion_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
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
        # Get data type directly from batch
        data_type = batch.data_type

        # Get file names and sizes from the source path
        file_names = []
        total_size_bytes = 0
        source_path = Path(batch.source_path)

        if source_path.exists():
            for file_path in source_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() == ".csv":
                    file_names.append(file_path.name)
                    total_size_bytes += file_path.stat().st_size

        records.append(IngestionRecord(
            ingestionId=batch.upload_id,
            dataType=data_type,
            filesCount=batch.file_count or len(file_names),
            fileNames=file_names,
            totalSizeBytes=total_size_bytes,
            uploadedBy=batch.uploaded_by or "system",
            uploadedAt=batch.created_at.isoformat() + "Z",  # UTC indicator
            status=batch.status,
        ))

    return IngestionHistoryResponse(records=records, total=total)
