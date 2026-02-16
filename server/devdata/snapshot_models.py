"""PostgreSQL snapshot database models and Pydantic schemas.

Defines SQLAlchemy models for snapshot tracking and related
Pydantic models for API requests/responses.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    BigInteger,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase

from server.pipelines.schema.base import metadata


class Base(DeclarativeBase):
    """Base class for snapshot models, using shared metadata."""
    metadata = metadata


class PostgresSnapshot(Base):
    """Track PostgreSQL backup snapshots."""

    __tablename__ = "postgres_snapshots"

    # Primary key - SNAP-YYYY-XXXX format
    id: Mapped[str] = mapped_column(String(20), primary_key=True)

    # User-friendly name and description
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # File information
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(64))  # SHA256

    # Database state at snapshot time
    alembic_version: Mapped[str] = mapped_column(String(32), nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_records: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Metadata
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Restore tracking
    restored_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_restored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_restored_by: Mapped[Optional[str]] = mapped_column(String(255))

    # Schedule relationship
    is_scheduled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schedule_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("snapshot_schedules.id", ondelete="SET NULL")
    )

    # Status
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    # Status values: pending, in_progress, completed, failed

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    schedule: Mapped[Optional["SnapshotSchedule"]] = relationship(
        "SnapshotSchedule", back_populates="snapshots"
    )

    # Indexes
    __table_args__ = (
        Index("idx_snapshots_created_at", "created_at"),
        Index("idx_snapshots_status", "status"),
        Index("idx_snapshots_schedule_id", "schedule_id"),
    )


class SnapshotSchedule(Base):
    """Snapshot scheduling configuration."""

    __tablename__ = "snapshot_schedules"

    # UUID primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Schedule configuration
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Retention policy
    max_snapshots: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    # Metadata
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Execution tracking
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_snapshot_id: Mapped[Optional[str]] = mapped_column(String(20))

    # Relationships
    snapshots: Mapped[List["PostgresSnapshot"]] = relationship(
        "PostgresSnapshot", back_populates="schedule"
    )

    # Indexes
    __table_args__ = (
        Index("idx_schedules_is_active", "is_active"),
        Index("idx_schedules_next_run_at", "next_run_at"),
    )


# ============================================================================
# Pydantic Models for API
# ============================================================================

class CreateSnapshotRequest(BaseModel):
    """Request to create a new snapshot."""
    name: str = Field(..., max_length=255, description="Snapshot name")
    description: Optional[str] = Field(None, description="Optional description")


class CreateSnapshotResponse(BaseModel):
    """Response for snapshot creation."""
    success: bool
    message: str
    job_id: str = Field(..., description="Job ID to track progress")
    snapshot_id: str = Field(..., description="Generated snapshot ID")


class RestoreSnapshotRequest(BaseModel):
    """Request to restore from a snapshot."""
    create_pre_restore_backup: bool = Field(
        True, description="Create backup before restoring"
    )
    force: bool = Field(
        False, description="Force restore even with version mismatch"
    )


class RestoreSnapshotResponse(BaseModel):
    """Response for snapshot restoration."""
    success: bool
    message: str
    job_id: str = Field(..., description="Job ID to track progress")
    pre_restore_snapshot_id: Optional[str] = Field(
        None, description="ID of pre-restore backup if created"
    )


class SnapshotInfo(BaseModel):
    """Basic snapshot information."""
    id: str
    name: str
    description: Optional[str]
    file_size: int
    created_by: str
    created_at: datetime
    status: str
    is_scheduled: bool
    restored_count: int


class SnapshotDetail(BaseModel):
    """Detailed snapshot information."""
    id: str
    name: str
    description: Optional[str]
    file_path: str
    file_size: int
    checksum: Optional[str]
    alembic_version: str
    table_count: int
    total_records: int
    created_by: str
    created_at: datetime
    restored_count: int
    last_restored_at: Optional[datetime]
    last_restored_by: Optional[str]
    is_scheduled: bool
    schedule_id: Optional[str]
    status: str
    error_message: Optional[str]


class SnapshotListResponse(BaseModel):
    """Paginated list of snapshots."""
    snapshots: List[SnapshotInfo]
    total: int
    page: int
    page_size: int
    has_more: bool


class CompareSnapshotsRequest(BaseModel):
    """Request to compare two snapshots."""
    snapshot_id_1: str
    snapshot_id_2: str
    include_schema: bool = Field(True, description="Include schema comparison")
    include_data: bool = Field(True, description="Include data volume comparison")


class SnapshotComparison(BaseModel):
    """Snapshot comparison result."""
    snapshot_1: SnapshotInfo
    snapshot_2: SnapshotInfo
    size_diff: int
    record_diff: int
    table_diff: int
    alembic_version_match: bool
    created_time_diff_hours: float
    schema_changes: Optional[List[str]] = None
    data_changes: Optional[dict] = None


class DeleteSnapshotResponse(BaseModel):
    """Response for snapshot deletion."""
    success: bool
    message: str
    deleted_file: bool = Field(..., description="Whether file was deleted")


class JobStatusResponse(BaseModel):
    """Job status for async operations."""
    job_id: str
    status: str  # pending, running, completed, failed
    progress_percent: int
    current_step: str
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    result: Optional[dict] = None


class CreateScheduleRequest(BaseModel):
    """Request to create a snapshot schedule."""
    name: str = Field(..., max_length=255, description="Schedule name")
    cron_expression: str = Field(..., description="Cron expression (e.g., '0 2 * * *')")
    max_snapshots: int = Field(7, ge=1, le=365, description="Max snapshots to retain")
    retention_days: int = Field(30, ge=1, le=365, description="Days to retain snapshots")
    is_active: bool = Field(True, description="Whether schedule is active")


class ScheduleInfo(BaseModel):
    """Schedule information."""
    id: str
    name: str
    cron_expression: str
    is_active: bool
    max_snapshots: int
    retention_days: int
    created_by: str
    created_at: datetime
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    snapshot_count: int


class ScheduleListResponse(BaseModel):
    """List of schedules."""
    schedules: List[ScheduleInfo]
    total: int