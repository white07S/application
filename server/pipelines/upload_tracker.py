"""Upload batch tracking and ID generation (async PostgreSQL)."""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from server.logging_config import get_logger

logger = get_logger(name=__name__)


async def generate_upload_id(db: AsyncSession) -> str:
    """Generate a sequential upload ID in format UPL-YYYY-XXXX.

    Resets sequence at the start of each year.
    Uses INSERT ... ON CONFLICT DO NOTHING for PostgreSQL.

    Returns:
        str: Upload ID like UPL-2026-0001
    """
    current_year = datetime.now().year

    # Ensure the sequence row exists for this year
    await db.execute(
        text(
            "INSERT INTO upload_id_sequence (year, sequence) "
            "VALUES (:year, 0) "
            "ON CONFLICT (year) DO NOTHING"
        ),
        {"year": current_year},
    )

    # Atomically increment and return
    result = await db.execute(
        text(
            "UPDATE upload_id_sequence "
            "SET sequence = sequence + 1 "
            "WHERE year = :year "
            "RETURNING sequence"
        ),
        {"year": current_year},
    )
    sequence = result.scalar_one()

    upload_id = f"UPL-{current_year}-{sequence:04d}"
    logger.info("Generated upload ID: {}", upload_id)
    return upload_id
