"""Qdrant snapshot database models and Pydantic schemas.

Defines SQLAlchemy models for Qdrant snapshot tracking and related
Pydantic models for API requests/responses.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from server.devdata.snapshot_models import Base


class QdrantSnapshot(Base):
    """Track Qdrant backup snapshots."""

    __tablename__ = "qdrant_snapshots"

    # Primary key - QSNAP-YYYY-XXXX format
    id: Mapped[str] = mapped_column(String(24), primary_key=True)

    # User-friendly name and description
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Qdrant collection info
    collection_name: Mapped[str] = mapped_column(String(255), nullable=False)
    qdrant_snapshot_name: Mapped[Optional[str]] = mapped_column(String(255))

    # File information (local copy)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(64))  # SHA256

    # Collection state at snapshot time
    points_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vectors_count: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Metadata
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Restore tracking
    restored_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_restored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_restored_by: Mapped[Optional[str]] = mapped_column(String(255))

    # Status: pending, in_progress, completed, failed
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Indexes
    __table_args__ = (
        Index("idx_qdrant_snapshots_created_at", "created_at"),
        Index("idx_qdrant_snapshots_status", "status"),
        Index("idx_qdrant_snapshots_collection", "collection_name"),
    )


# ============================================================================
# Pydantic Models for API
# ============================================================================

class CreateQdrantSnapshotRequest(BaseModel):
    """Request to create a new Qdrant snapshot."""
    name: str = Field(..., max_length=255, description="Snapshot name")
    description: Optional[str] = Field(None, description="Optional description")
    collection_name: str = Field(..., description="Qdrant collection to snapshot")


class CreateQdrantSnapshotResponse(BaseModel):
    """Response for Qdrant snapshot creation."""
    success: bool
    message: str
    job_id: str = Field(..., description="Job ID to track progress")
    snapshot_id: str = Field(..., description="Generated snapshot ID")


class RestoreQdrantSnapshotRequest(BaseModel):
    """Request to restore a Qdrant collection from a snapshot."""
    force: bool = Field(False, description="Force restore even if collection has data")


class RestoreQdrantSnapshotResponse(BaseModel):
    """Response for Qdrant snapshot restoration."""
    success: bool
    message: str
    job_id: str = Field(..., description="Job ID to track progress")


class QdrantSnapshotInfo(BaseModel):
    """Basic Qdrant snapshot information."""
    id: str
    name: str
    description: Optional[str]
    collection_name: str
    file_size: int
    points_count: int
    created_by: str
    created_at: datetime
    status: str
    restored_count: int


class QdrantSnapshotDetail(BaseModel):
    """Detailed Qdrant snapshot information."""
    id: str
    name: str
    description: Optional[str]
    collection_name: str
    qdrant_snapshot_name: Optional[str]
    file_path: str
    file_size: int
    checksum: Optional[str]
    points_count: int
    vectors_count: int
    created_by: str
    created_at: datetime
    restored_count: int
    last_restored_at: Optional[datetime]
    last_restored_by: Optional[str]
    status: str
    error_message: Optional[str]


class QdrantSnapshotListResponse(BaseModel):
    """Paginated list of Qdrant snapshots."""
    snapshots: List[QdrantSnapshotInfo]
    total: int
    page: int
    page_size: int
    has_more: bool


class DeleteQdrantSnapshotResponse(BaseModel):
    """Response for Qdrant snapshot deletion."""
    success: bool
    message: str
    deleted_file: bool = Field(..., description="Whether file was deleted")
