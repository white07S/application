"""Upload batch tracking and ID generation."""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from server.database import UploadBatch, DataSource
from server.logging_config import get_logger
from .storage import get_upload_sequence_path

logger = get_logger(name=__name__)


def _load_sequence() -> dict:
    """Load the upload ID sequence data from file."""
    seq_path = get_upload_sequence_path()
    if seq_path.exists():
        with open(seq_path, "r") as f:
            return json.load(f)
    return {"year": None, "sequence": 0}


def _save_sequence(data: dict) -> None:
    """Save the upload ID sequence data to file."""
    seq_path = get_upload_sequence_path()
    seq_path.parent.mkdir(parents=True, exist_ok=True)
    with open(seq_path, "w") as f:
        json.dump(data, f)


def generate_upload_id() -> str:
    """
    Generate a sequential upload ID in format UPL-YYYY-XXXX.
    Resets sequence at the start of each year.

    Returns:
        str: Upload ID like UPL-2026-0001
    """
    current_year = datetime.now().year
    seq_data = _load_sequence()

    if seq_data["year"] != current_year:
        # New year, reset sequence
        sequence = 1
    else:
        sequence = seq_data["sequence"] + 1

    # Update sequence file
    seq_data["year"] = current_year
    seq_data["sequence"] = sequence
    _save_sequence(seq_data)

    upload_id = f"UPL-{current_year}-{sequence:04d}"
    logger.info("Generated upload ID: {}", upload_id)
    return upload_id


def get_data_source_id(db: Session, source_code: str) -> int:
    """Get the data_source_id for a given source code."""
    source = db.query(DataSource).filter_by(source_code=source_code).first()
    if not source:
        raise ValueError(f"Unknown data source: {source_code}")
    return source.id


def create_upload_batch(
    db: Session,
    data_type: str,
    source_path: str,
    file_count: int,
) -> UploadBatch:
    """
    Create a new upload batch record in the database.

    Args:
        db: Database session
        data_type: Type of data (issues, controls, actions)
        source_path: Path where files are stored
        file_count: Number of files uploaded

    Returns:
        UploadBatch: The created batch record
    """
    upload_id = generate_upload_id()
    data_source_id = get_data_source_id(db, data_type)

    batch = UploadBatch(
        upload_id=upload_id,
        data_source_id=data_source_id,
        status="pending",
        source_path=source_path,
        file_count=file_count,
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
