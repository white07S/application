"""PostgreSQL snapshot Pydantic schemas for API requests/responses.

SQLAlchemy models (PostgresSnapshot, SnapshotSchedule) have been removed.
Snapshot metadata is now stored entirely on disk in metadata.json files.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


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
