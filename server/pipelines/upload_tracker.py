"""Upload batch tracking and ID generation."""
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from server.logging_config import get_logger

logger = get_logger(name=__name__)


def generate_upload_id(db: Session) -> str:
    """
    Generate a sequential upload ID in format UPL-YYYY-XXXX.
    Resets sequence at the start of each year.

    Returns:
        str: Upload ID like UPL-2026-0001
    """
    current_year = datetime.now().year

    # Ensure the sequence row exists for this year, then atomically increment.
    db.execute(
        text(
            "INSERT OR IGNORE INTO upload_id_sequence (year, sequence) "
            "VALUES (:year, 0)"
        ),
        {"year": current_year},
    )
    db.execute(
        text(
            "UPDATE upload_id_sequence "
            "SET sequence = sequence + 1 "
            "WHERE year = :year"
        ),
        {"year": current_year},
    )
    sequence = db.execute(
        text("SELECT sequence FROM upload_id_sequence WHERE year = :year"),
        {"year": current_year},
    ).scalar_one()

    upload_id = f"UPL-{current_year}-{sequence:04d}"
    logger.info("Generated upload ID: {}", upload_id)
    return upload_id
