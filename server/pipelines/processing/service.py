"""Processing service for listing batches with ingestion readiness (async).

Provides batch listing with readiness status for the ingestion API.
"""

from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.jobs import UploadBatch, ProcessingJob
from server.logging_config import get_logger
from server.pipelines.controls.readiness import check_ingestion_readiness

logger = get_logger(name=__name__)


async def get_validated_batches(db: AsyncSession) -> List[Dict]:
    """Get all batches that have been validated, with ingestion readiness status.

    Returns batches with status 'validated', 'processing', or 'success' along with
    their readiness information (whether all model outputs are available).
    """
    result = await db.execute(
        select(UploadBatch)
        .where(UploadBatch.status.in_(["validated", "processing", "success", "failed"]))
        .order_by(UploadBatch.created_at.desc())
    )
    batches = result.scalars().all()

    output = []
    for batch in batches:
        upload_id = batch.upload_id

        # Check ingestion readiness (model outputs available?)
        readiness = check_ingestion_readiness(upload_id)

        # Get the latest ingestion job for this batch
        job_result = await db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.batch_id == batch.id, ProcessingJob.job_type == "ingestion")
            .order_by(ProcessingJob.created_at.desc())
            .limit(1)
        )
        ingestion_job = job_result.scalar_one_or_none()

        # Can ingest only if: readiness is True, batch is validated,
        # and no successful ingestion job exists yet (or last one failed)
        can_ingest = (
            readiness.ready
            and batch.status in ("validated", "failed")
            and (not ingestion_job or ingestion_job.status == "failed")
        )

        output.append({
            "batch_id": batch.id,
            "upload_id": upload_id,
            "data_type": batch.data_type,
            "status": batch.status,
            "file_count": batch.file_count,
            "total_records": batch.total_records,
            "uploaded_by": batch.uploaded_by,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "readiness": readiness.to_dict(),
            "can_ingest": can_ingest,
            "ingestion_status": ingestion_job.status if ingestion_job else None,
            "message": readiness.message,
        })

    return output
