from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, BigInteger, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class TusUpload(Base):
    """Track TUS resumable upload state.

    This model stores the state of in-progress TUS uploads, allowing
    uploads to be resumed after interruption.
    """
    __tablename__ = "tus_uploads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    batch_session_id: Mapped[str] = mapped_column(String(36), nullable=False)  # Groups files for same upload
    upload_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # UPL-YYYY-XXXX (set after complete)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # issues, controls, actions
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    offset: Mapped[int] = mapped_column(BigInteger, default=0)
    is_complete: Mapped[bool] = mapped_column(default=False)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    temp_path: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Original Upload-Metadata as JSON
    expected_files: Mapped[int] = mapped_column(default=1)  # How many files expected in this batch
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # For TUS Expiration extension

    __table_args__ = (
        CheckConstraint("data_type IN ('issues', 'controls', 'actions')"),
        Index('idx_tus_uploads_is_complete', 'is_complete'),
        Index('idx_tus_uploads_created', 'created_at'),
        Index('idx_tus_uploads_uploaded_by', 'uploaded_by'),
        Index('idx_tus_uploads_batch_session', 'batch_session_id'),
    )

class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # UPL-YYYY-XXXX
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, validating, processing, success, failed
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # User who uploaded
    file_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    total_records: Mapped[Optional[int]] = mapped_column(nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'validating', 'validated', 'processing', 'success', 'failed')"),
        Index('idx_upload_batches_status', 'status'),
        Index('idx_upload_batches_created', 'created_at'),
    )

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    pipeline_type: Mapped[str] = mapped_column(String(50), nullable=False)  # validation, ingestion, nfr_taxonomy, enrichment, embeddings, fts
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, paused, success, failed
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_processed_record_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_checkpoint_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    records_total: Mapped[int] = mapped_column(default=0)
    records_processed: Mapped[int] = mapped_column(default=0)
    records_inserted: Mapped[int] = mapped_column(default=0)
    records_updated: Mapped[int] = mapped_column(default=0)
    records_skipped: Mapped[int] = mapped_column(default=0)
    records_failed: Mapped[int] = mapped_column(default=0)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'paused', 'success', 'failed')"),
        Index('idx_pipeline_runs_batch', 'upload_batch_id'),
        Index('idx_pipeline_runs_status', 'status'),
    )

class RecordProcessingLog(Base):
    __tablename__ = "record_processing_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # ingestion, taxonomy, enrichment, embeddings
    record_business_id: Mapped[str] = mapped_column(String(50), nullable=False)  # issue_id, control_id, etc.
    operation: Mapped[str] = mapped_column(String(20), nullable=False)  # insert, update, skip, fail
    version_created: Mapped[Optional[int]] = mapped_column(nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    processed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        Index('idx_record_log_pipeline', 'pipeline_run_id'),
        Index('idx_record_log_business_id', 'record_business_id'),
        Index('idx_record_log_stage', 'stage'),
    )


class ProcessingJob(Base):
    """Track processing jobs (ingestion and model runs) with persistence.

    Unlike the in-memory JobStatus, this persists to database for:
    - Surviving server restarts
    - Historical job tracking
    - Progress recovery
    """
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "ingestion" or "model_run"
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    upload_id: Mapped[str] = mapped_column(String(20), nullable=False)  # UPL-YYYY-XXXX
    pipeline_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed
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
    db_total_records: Mapped[int] = mapped_column(default=0)  # Total in DB after job

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Step details (JSON array)
    steps_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')"),
        CheckConstraint("job_type IN ('ingestion', 'model_run')"),
        Index('idx_processing_jobs_batch', 'batch_id'),
        Index('idx_processing_jobs_status', 'status'),
        Index('idx_processing_jobs_created', 'created_at'),
    )
