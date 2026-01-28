"""Health check and system status endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.database import get_db, DATABASE_PATH
from server.database.models import DataSource, DatasetConfig, ModelConfig, UploadBatch, PipelineRun

router = APIRouter(prefix="/v2/health", tags=["Health"])

class TableCount(BaseModel):
    table_name: str
    count: int

class DatabaseStatus(BaseModel):
    connected: bool
    path: str
    tables: list[TableCount]

class HealthResponse(BaseModel):
    status: str  # "healthy" or "unhealthy"
    database: DatabaseStatus

@router.get("", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint that verifies database connectivity
    and returns table counts.
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))

        # Get table counts
        tables = [
            TableCount(table_name="data_sources", count=db.query(DataSource).count()),
            TableCount(table_name="dataset_config", count=db.query(DatasetConfig).count()),
            TableCount(table_name="model_config", count=db.query(ModelConfig).count()),
            TableCount(table_name="upload_batches", count=db.query(UploadBatch).count()),
            TableCount(table_name="pipeline_runs", count=db.query(PipelineRun).count()),
        ]

        return HealthResponse(
            status="healthy",
            database=DatabaseStatus(
                connected=True,
                path=str(DATABASE_PATH),
                tables=tables
            )
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            database=DatabaseStatus(
                connected=False,
                path=str(DATABASE_PATH),
                tables=[]
            )
        )
