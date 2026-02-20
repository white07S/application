"""SQLAlchemy models for job tracking.

These models are stored alongside the domain tables in PostgreSQL.
They share the same MetaData instance so Alembic manages all tables together.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String, Text, BigInteger, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase

from server.pipelines.schema.base import metadata


class Base(DeclarativeBase):
    """Base class for all job tracking models, using shared metadata."""
    metadata = metadata


class TusUpload(Base):
    """Track TUS resumable upload state."""
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

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
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'validating', 'validated', 'processing', 'success', 'failed')"),
        CheckConstraint("data_type IN ('issues', 'controls', 'actions')"),
        Index('idx_upload_batches_status', 'status'),
    )


class UploadIdSequence(Base):
    """Track upload ID sequences per year (UPL-YYYY-XXXX)."""
    __tablename__ = "upload_id_sequence"

    year: Mapped[int] = mapped_column(primary_key=True)
    sequence: Mapped[int] = mapped_column(default=0)


class ProcessingJob(Base):
    """Track processing jobs (ingestion and model runs) with persistence."""
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)  # ingestion, snapshot_creation, snapshot_restore
    batch_id: Mapped[int] = mapped_column(nullable=False)
    upload_id: Mapped[str] = mapped_column(String(20), nullable=False)  # UPL-YYYY-XXXX
    status: Mapped[str] = mapped_column(String(20), default="pending")
    progress_percent: Mapped[int] = mapped_column(default=0)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Record counts
    records_total: Mapped[int] = mapped_column(default=0)
    records_processed: Mapped[int] = mapped_column(default=0)
    records_new: Mapped[int] = mapped_column(default=0)
    records_changed: Mapped[int] = mapped_column(default=0)
    records_unchanged: Mapped[int] = mapped_column(default=0)
    records_failed: Mapped[int] = mapped_column(default=0)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')"),
        CheckConstraint("job_type IN ('ingestion', 'snapshot_creation', 'snapshot_restore', 'qdrant_snapshot_creation', 'qdrant_snapshot_restore')"),
        Index('idx_processing_jobs_batch', 'batch_id'),
        Index('idx_processing_jobs_status', 'status'),
    )
