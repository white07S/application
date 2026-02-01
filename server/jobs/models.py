"""SQLAlchemy models for job tracking.

These models are stored in the jobs.db SQLite database, separate from
the main SurrealDB data storage.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, BigInteger, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all job tracking models."""
    pass


class TusUpload(Base):
    """Track TUS resumable upload state.

    This model stores the state of in-progress TUS uploads, allowing
    uploads to be resumed after interruption.
    """
    __tablename__ = "tus_uploads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    batch_session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    upload_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # UPL-YYYY-XXXX
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # issues, controls, actions
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    offset: Mapped[int] = mapped_column(BigInteger, default=0)
    is_complete: Mapped[bool] = mapped_column(default=False)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    temp_path: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_files: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint("data_type IN ('issues', 'controls', 'actions')"),
        Index('idx_tus_uploads_is_complete', 'is_complete'),
        Index('idx_tus_uploads_batch_session', 'batch_session_id'),
    )


class UploadBatch(Base):
    """Track upload batches and their processing status."""
    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # UPL-YYYY-XXXX
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # controls, issues, actions
    status: Mapped[str] = mapped_column(String(20), default="pending")
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    file_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    total_records: Mapped[Optional[int]] = mapped_column(nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'validating', 'validated', 'processing', 'success', 'failed')"),
        CheckConstraint("data_type IN ('issues', 'controls', 'actions')"),
        Index('idx_upload_batches_status', 'status'),
    )


class ProcessingJob(Base):
    """Track processing jobs (ingestion and model runs) with persistence."""
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)  # ingestion, model_run
    batch_id: Mapped[int] = mapped_column(nullable=False)
    upload_id: Mapped[str] = mapped_column(String(20), nullable=False)  # UPL-YYYY-XXXX
    status: Mapped[str] = mapped_column(String(20), default="pending")
    progress_percent: Mapped[int] = mapped_column(default=0)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Record counts
    records_total: Mapped[int] = mapped_column(default=0)
    records_processed: Mapped[int] = mapped_column(default=0)
    records_new: Mapped[int] = mapped_column(default=0)
    records_updated: Mapped[int] = mapped_column(default=0)
    records_skipped: Mapped[int] = mapped_column(default=0)
    records_failed: Mapped[int] = mapped_column(default=0)

    # Batch tracking
    batches_total: Mapped[int] = mapped_column(default=0)
    batches_completed: Mapped[int] = mapped_column(default=0)

    # Summary fields
    data_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    db_total_records: Mapped[int] = mapped_column(default=0)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')"),
        CheckConstraint("job_type IN ('ingestion', 'model_run')"),
        Index('idx_processing_jobs_batch', 'batch_id'),
        Index('idx_processing_jobs_status', 'status'),
    )
