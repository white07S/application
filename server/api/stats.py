"""Explorer statistics endpoints (public, no auth required)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from server.jobs import get_jobs_db, UploadBatch
from server.logging_config import get_logger

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/stats", tags=["Stats"])


class ControlsStats(BaseModel):
    total_controls: int
    ingested_today: int
    last_sync: str | None  # ISO datetime or null


@router.get("/controls", response_model=ControlsStats)
async def get_controls_stats(db: AsyncSession = Depends(get_jobs_db)):
    """Return real-time controls statistics for the explorer."""
    total_controls = 0
    ingested_today = 0
    last_sync: str | None = None

    try:
        # Total controls from src_controls_ref_control
        result = await db.execute(
            text("SELECT COUNT(*) FROM src_controls_ref_control")
        )
        total_controls = result.scalar_one()
    except Exception as e:
        logger.warning("Failed to count controls: {}", e)

    try:
        # Today's ingested: sum total_records from successful batches completed today
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result = await db.execute(
            select(func.coalesce(func.sum(UploadBatch.total_records), 0)).where(
                UploadBatch.data_type == "controls",
                UploadBatch.status == "success",
                UploadBatch.completed_at >= today_start,
            )
        )
        ingested_today = result.scalar_one()
    except Exception as e:
        logger.warning("Failed to get today's ingested count: {}", e)

    try:
        # Last sync: most recent completed_at from successful controls batches
        result = await db.execute(
            select(UploadBatch.completed_at)
            .where(
                UploadBatch.data_type == "controls",
                UploadBatch.status == "success",
            )
            .order_by(UploadBatch.completed_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            last_sync = row.isoformat()
    except Exception as e:
        logger.warning("Failed to get last sync: {}", e)

    return ControlsStats(
        total_controls=total_controls,
        ingested_today=ingested_today,
        last_sync=last_sync,
    )
