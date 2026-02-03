"""Upload batch tracking and ID generation."""
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from server.jobs import UploadBatch
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


def create_upload_batch(
    db: Session,
    data_type: str,
    source_path: str,
    file_count: int,
    uploaded_by: Optional[str] = None,
) -> UploadBatch:
    """
    Create a new upload batch record in the database.

    Args:
        db: Database session
        data_type: Type of data (issues, controls, actions)
        source_path: Path where files are stored
        file_count: Number of files uploaded
        uploaded_by: User who uploaded

    Returns:
        UploadBatch: The created batch record
    """
    upload_id = generate_upload_id(db)

    batch = UploadBatch(
        upload_id=upload_id,
        data_type=data_type,
        status="pending",
        source_path=source_path,
        file_count=file_count,
        uploaded_by=uploaded_by,
        created_at=datetime.utcnow(),
    )

    db.add(batch)
    db.flush()  # Get the ID without committing

    logger.info(
        "Created upload batch: id={}, upload_id={}, data_type={}",
        batch.id, batch.upload_id, data_type
    )

    return batch


def update_batch_status(
    db: Session,
    batch_id: int,
    status: str,
    error_code: Optional[str] = None,
    error_details: Optional[str] = None,
    total_records: Optional[int] = None,
) -> UploadBatch:
    """
    Update an upload batch status.

    Args:
        db: Database session
        batch_id: Batch ID to update
        status: New status (pending, validating, processing, success, failed)
        error_code: Error code if failed
        error_details: JSON error details if failed
        total_records: Total records count if known

    Returns:
        UploadBatch: Updated batch record
    """
    batch = db.query(UploadBatch).filter_by(id=batch_id).first()
    if not batch:
        raise ValueError(f"Upload batch not found: {batch_id}")

    batch.status = status

    if status == "validating":
        batch.started_at = datetime.utcnow()
    elif status in ("success", "failed"):
        batch.completed_at = datetime.utcnow()

    if error_code:
        batch.error_code = error_code
    if error_details:
        batch.error_details = error_details
    if total_records is not None:
        batch.total_records = total_records

    db.flush()

    logger.info("Updated batch {} status to {}", batch.upload_id, status)
    return batch


def get_batch_by_id(db: Session, batch_id: int) -> Optional[UploadBatch]:
    """Get an upload batch by its internal ID."""
    return db.query(UploadBatch).filter_by(id=batch_id).first()


def get_batch_by_upload_id(db: Session, upload_id: str) -> Optional[UploadBatch]:
    """Get an upload batch by its upload ID (UPL-YYYY-XXXX)."""
    return db.query(UploadBatch).filter_by(upload_id=upload_id).first()


def get_pending_batches(db: Session) -> list[UploadBatch]:
    """Get all pending upload batches in FIFO order."""
    return (
        db.query(UploadBatch)
        .filter_by(status="pending")
        .order_by(UploadBatch.created_at.asc())
        .all()
    )
