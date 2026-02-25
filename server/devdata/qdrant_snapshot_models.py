"""Qdrant snapshot Pydantic schemas for API requests/responses.

SQLAlchemy model (QdrantSnapshot) has been removed.
Snapshot metadata is now stored entirely on disk in metadata.json files.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


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
