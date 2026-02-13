"""Health check and system status endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from server.jobs import get_jobs_db, UploadBatch, ProcessingJob, TusUpload
from server.logging_config import get_logger

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/health", tags=["Health"])


class TableCount(BaseModel):
    table_name: str
    count: int


class DatabaseStatus(BaseModel):
    connected: bool
    tables: list[TableCount]


class QdrantStatus(BaseModel):
    connected: bool
    collection: str


class HealthResponse(BaseModel):
    status: str  # "healthy" or "unhealthy"
    database: DatabaseStatus
    qdrant: QdrantStatus


@router.get("", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_jobs_db)):
    """Health check endpoint that verifies database connectivity and returns table counts."""
    db_status = DatabaseStatus(connected=False, tables=[])
    qdrant_status = QdrantStatus(connected=False, collection="")

    try:
        # Test PostgreSQL connection
        await db.execute(text("SELECT 1"))

        # Get table counts
        tus_count = (await db.execute(select(func.count()).select_from(TusUpload))).scalar_one()
        batch_count = (await db.execute(select(func.count()).select_from(UploadBatch))).scalar_one()
        job_count = (await db.execute(select(func.count()).select_from(ProcessingJob))).scalar_one()

        tables = [
            TableCount(table_name="tus_uploads", count=tus_count),
            TableCount(table_name="upload_batches", count=batch_count),
            TableCount(table_name="processing_jobs", count=job_count),
        ]

        db_status = DatabaseStatus(connected=True, tables=tables)
    except Exception as e:
        logger.warning("Failed to connect to database: {}", e)

    # Test Qdrant connection
    try:
        from server.pipelines.controls.qdrant_service import get_collection_info
        info = await get_collection_info()
        if info:
            qdrant_status = QdrantStatus(
                connected=True,
                collection=info.get("collection_name", ""),
            )
    except Exception as e:
        logger.warning("Failed to connect to Qdrant: {}", e)

    overall_status = "healthy" if (db_status.connected and qdrant_status.connected) else "unhealthy"

    return HealthResponse(
        status=overall_status,
        database=db_status,
        qdrant=qdrant_status,
    )
