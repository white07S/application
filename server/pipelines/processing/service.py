"""Processing service for listing batches and jobs.

Simplified service after migration to SurrealDB.
"""
from typing import Dict, List

from sqlalchemy.orm import Session

from server.jobs import UploadBatch, ProcessingJob
from server.logging_config import get_logger
from .. import storage

logger = get_logger(name=__name__)


def get_validated_batches(db: Session) -> List[Dict]:
    """Get all batches that have been validated and are ready for processing.

    Returns batches with status 'validated' along with their parquet files info.
    """
    batches = db.query(UploadBatch).filter(
        UploadBatch.status.in_(["validated", "processing", "success"])
    ).order_by(UploadBatch.created_at.desc()).all()

    result = []
    for batch in batches:
        data_type = batch.data_type

        # Get parquet files from preprocessed directory
        parquet_files = []
        preprocessed_path = storage.get_preprocessed_batch_path(batch.upload_id, data_type)

        if preprocessed_path.exists():
            for file_path in preprocessed_path.glob("*.parquet"):
                stat = file_path.stat()
                parquet_files.append({
                    "filename": file_path.name,
                    "path": str(file_path),
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime,
                })

        # Get the latest jobs for this batch
        ingestion_job = db.query(ProcessingJob).filter_by(
            batch_id=batch.id,
            job_type="ingestion"
        ).order_by(ProcessingJob.created_at.desc()).first()

        model_job = db.query(ProcessingJob).filter_by(
            batch_id=batch.id,
            job_type="model_run"
        ).order_by(ProcessingJob.created_at.desc()).first()

        result.append({
            "batch_id": batch.id,
            "upload_id": batch.upload_id,
            "data_type": data_type,
            "status": batch.status,
            "file_count": batch.file_count,
            "total_records": batch.total_records,
            "uploaded_by": batch.uploaded_by,
            "created_at": batch.created_at.isoformat() + "Z",  # UTC indicator
            "parquet_files": parquet_files,
            "parquet_count": len(parquet_files),
            "pk_records": None,  # No longer computed, SurrealDB handles this
            "ingestion_status": ingestion_job.status if ingestion_job else None,
            "ingestion_run_id": None,  # Deprecated - using job tracking now
            "model_run_status": model_job.status if model_job else None,
            "model_run_id": None,  # Deprecated - using job tracking now
            "can_ingest": batch.status == "validated" and (not ingestion_job or ingestion_job.status == "failed"),
            "can_run_model": bool(ingestion_job and ingestion_job.status == "completed" and (not model_job or model_job.status == "failed")),
        })

    return result
