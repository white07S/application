"""Explorer statistics endpoints (public, no auth required)."""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select, func, text

from server.cache import cached
from server.config.postgres import get_db_session_context
from server.jobs import UploadBatch
from server.logging_config import get_logger

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/stats", tags=["Stats"])


class ControlsStats(BaseModel):
    total_controls: int
    ingested_today: int
    last_sync: str | None  # ISO datetime or null


@cached(namespace="stats", ttl=300)
async def _fetch_controls_stats() -> dict:
    """Fetch controls stats from the database. Cached for 5 minutes."""
    total_controls = 0
    ingested_today = 0
    last_sync: str | None = None

    async with get_db_session_context() as db:
        try:
            result = await db.execute(
                text("SELECT COUNT(*) FROM src_controls_ref_control")
            )
            total_controls = result.scalar_one()
        except Exception as e:
            logger.warning("Failed to count controls: {}", e)

        try:
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

    return {
        "total_controls": total_controls,
        "ingested_today": ingested_today,
        "last_sync": last_sync,
    }


@router.get("/controls", response_model=ControlsStats)
async def get_controls_stats():
    """Return controls statistics for the explorer."""
    data = await _fetch_controls_stats()
    return ControlsStats(**data)
