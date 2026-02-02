"""Health check and system status endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.jobs import get_jobs_db, JOBS_DATABASE_PATH, UploadBatch, ProcessingJob, TusUpload
from server.config.surrealdb import get_surrealdb_connection

router = APIRouter(prefix="/v2/health", tags=["Health"])


class TableCount(BaseModel):
    table_name: str
    count: int


class DatabaseStatus(BaseModel):
    connected: bool
    path: str
    tables: list[TableCount]


class SurrealDBStatus(BaseModel):
    connected: bool
    url: str


class HealthResponse(BaseModel):
    status: str  # "healthy" or "unhealthy"
    jobs_database: DatabaseStatus
    surrealdb: SurrealDBStatus


@router.get("", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_jobs_db)):
    """
    Health check endpoint that verifies database connectivity
    and returns table counts.
    """
    jobs_db_status = DatabaseStatus(
        connected=False,
        path=str(JOBS_DATABASE_PATH),
        tables=[]
    )

    surreal_status = SurrealDBStatus(
        connected=False,
        url=""
    )

    try:
        # Test jobs database connection
        db.execute(text("SELECT 1"))

        # Get table counts
        tables = [
            TableCount(table_name="tus_uploads", count=db.query(TusUpload).count()),
            TableCount(table_name="upload_batches", count=db.query(UploadBatch).count()),
            TableCount(table_name="processing_jobs", count=db.query(ProcessingJob).count()),
        ]

        jobs_db_status = DatabaseStatus(
            connected=True,
            path=str(JOBS_DATABASE_PATH),
            tables=tables
        )
    except Exception as e:
        # Log the error for debugging purposes
        import logging
        logging.warning("Failed to connect to jobs database: %s", e)

    # Test SurrealDB connection
    try:
        from server.settings import get_settings
        settings = get_settings()

        async with get_surrealdb_connection() as surreal_db:
            # Simple query to test connection
            await surreal_db.query("SELECT * FROM src_controls_main LIMIT 1")
            surreal_status = SurrealDBStatus(
                connected=True,
                url=settings.surrealdb_url
            )
    except Exception as e:
        # Log the error for debugging purposes
        import logging
        logging.warning("Failed to connect to SurrealDB: %s", e)
        surreal_status = SurrealDBStatus(
            connected=False,
            url=settings.surrealdb_url
        )

    overall_status = "healthy" if jobs_db_status.connected else "unhealthy"

    return HealthResponse(
        status=overall_status,
        jobs_database=jobs_db_status,
        surrealdb=surreal_status
    )
