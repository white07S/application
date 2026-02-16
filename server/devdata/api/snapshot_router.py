"""API endpoints for PostgreSQL snapshot management."""

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.config.postgres import get_db_session, get_db_session_context
from server.devdata.snapshot_models import (
    CreateSnapshotRequest,
    CreateSnapshotResponse,
    RestoreSnapshotRequest,
    RestoreSnapshotResponse,
    SnapshotDetail,
    SnapshotListResponse,
    CompareSnapshotsRequest,
    SnapshotComparison,
    DeleteSnapshotResponse,
    JobStatusResponse,
)
from server.devdata.snapshot_service import snapshot_service
from server.jobs import ProcessingJob
from server.logging_config import get_logger

logger = get_logger(name=__name__)

router = APIRouter(prefix="/snapshots", tags=["Snapshots"])


async def _require_dev_data_access(token: str = Depends(get_token_from_header)):
    """Dependency that verifies the user has dev data access."""
    access = await get_access_control(token)
    if not access.hasDevDataAccess:
        raise HTTPException(status_code=403, detail="Dev data access required")
    return access


async def _require_dev_data_write_access(token: str = Depends(get_token_from_header)):
    """Dependency that verifies the user has dev data write access.

    For now, we'll use the pipelines admin access as a proxy for write access.
    In the future, this could be a separate permission.
    """
    access = await get_access_control(token)
    if not access.hasPipelinesAdminAccess:
        raise HTTPException(
            status_code=403,
            detail="Admin access required for snapshot operations"
        )
    return access


@router.post("/create", response_model=CreateSnapshotResponse)
async def create_snapshot(
    request: CreateSnapshotRequest,
    background_tasks: BackgroundTasks,
    access=Depends(_require_dev_data_write_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new PostgreSQL snapshot.

    This endpoint starts a background job to create the snapshot.
    Use the returned job_id to track progress.
    """
    try:
        # Create job for tracking
        job_id = str(uuid.uuid4())
        job = ProcessingJob(
            id=job_id,
            job_type="snapshot_creation",
            batch_id=0,
            upload_id="SNAPSHOT",
            status="pending",
            progress_percent=0,
            current_step="Initializing...",
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()

        # Generate snapshot ID for response
        snapshot_id = await snapshot_service.generate_snapshot_id(db)

        # Launch background task
        background_tasks.add_task(
            _run_snapshot_creation,
            job_id=job_id,
            snapshot_id=snapshot_id,
            name=request.name,
            description=request.description,
            user=access.user,
        )

        logger.info(f"Snapshot creation job {job_id} started by {access.user}")

        return CreateSnapshotResponse(
            success=True,
            message="Snapshot creation started",
            job_id=job_id,
            snapshot_id=snapshot_id,
        )

    except Exception as e:
        logger.error(f"Error starting snapshot creation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start snapshot creation: {str(e)}"
        )


async def _run_snapshot_creation(
    job_id: str,
    snapshot_id: str,
    name: str,
    description: str,
    user: str,
):
    """Background task to create a snapshot."""
    async with get_db_session_context() as db:
        await snapshot_service.create_snapshot(
            db=db,
            job_id=job_id,
            name=name,
            description=description,
            user=user,
            is_scheduled=False,
        )


@router.get("/list", response_model=SnapshotListResponse)
async def list_snapshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    filter_scheduled: bool = Query(None),
    _=Depends(_require_dev_data_access),
    db: AsyncSession = Depends(get_db_session),
):
    """List available snapshots with pagination."""
    return await snapshot_service.list_snapshots(
        db=db,
        page=page,
        page_size=page_size,
        filter_scheduled=filter_scheduled,
    )


@router.get("/{snapshot_id}", response_model=SnapshotDetail)
async def get_snapshot(
    snapshot_id: str,
    _=Depends(_require_dev_data_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Get detailed information about a specific snapshot."""
    snapshot = await snapshot_service.get_snapshot_detail(db, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return snapshot


@router.post("/{snapshot_id}/restore", response_model=RestoreSnapshotResponse)
async def restore_snapshot(
    snapshot_id: str,
    request: RestoreSnapshotRequest,
    background_tasks: BackgroundTasks,
    access=Depends(_require_dev_data_write_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Restore database from a snapshot.

    This endpoint starts a background job to restore the database.
    Use the returned job_id to track progress.

    WARNING: This will replace the current database with the snapshot!
    Consider creating a pre-restore backup (enabled by default).
    """
    try:
        # Verify snapshot exists
        snapshot = await snapshot_service.get_snapshot_detail(db, snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")

        # Check if snapshot is in a valid state
        if snapshot.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Snapshot is in {snapshot.status} state, cannot restore"
            )

        # Create job for tracking
        job_id = str(uuid.uuid4())
        job = ProcessingJob(
            id=job_id,
            job_type="snapshot_restore",
            batch_id=0,
            upload_id=snapshot_id,
            status="pending",
            progress_percent=0,
            current_step="Initializing restore...",
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()

        # Launch background task
        background_tasks.add_task(
            _run_snapshot_restore,
            job_id=job_id,
            snapshot_id=snapshot_id,
            user=access.user,
            create_pre_restore_backup=request.create_pre_restore_backup,
            force=request.force,
        )

        logger.info(f"Snapshot restore job {job_id} started by {access.user}")

        return RestoreSnapshotResponse(
            success=True,
            message="Snapshot restore started",
            job_id=job_id,
            pre_restore_snapshot_id=None,  # Will be available in job status if created
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting snapshot restore: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start snapshot restore: {str(e)}"
        )


async def _run_snapshot_restore(
    job_id: str,
    snapshot_id: str,
    user: str,
    create_pre_restore_backup: bool,
    force: bool,
):
    """Background task to restore a snapshot."""
    async with get_db_session_context() as db:
        pre_restore_id = await snapshot_service.restore_snapshot(
            db=db,
            job_id=job_id,
            snapshot_id=snapshot_id,
            user=user,
            create_pre_restore_backup=create_pre_restore_backup,
            force=force,
        )

        # Store pre-restore snapshot ID in job result if created
        if pre_restore_id:
            job = await db.get(ProcessingJob, job_id)
            if job:
                # Store in a JSON field or as part of the message
                # For now, we'll add it to the current_step
                job.current_step = f"Restore completed. Pre-restore backup: {pre_restore_id}"
                await db.commit()


@router.delete("/{snapshot_id}", response_model=DeleteSnapshotResponse)
async def delete_snapshot(
    snapshot_id: str,
    access=Depends(_require_dev_data_write_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a snapshot and its backup file.

    This permanently removes the snapshot and its associated backup file.
    This action cannot be undone.
    """
    return await snapshot_service.delete_snapshot(
        db=db,
        snapshot_id=snapshot_id,
        user=access.user,
    )


@router.post("/compare", response_model=SnapshotComparison)
async def compare_snapshots(
    request: CompareSnapshotsRequest,
    _=Depends(_require_dev_data_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Compare two snapshots to see differences."""
    comparison = await snapshot_service.compare_snapshots(
        db=db,
        snapshot_id_1=request.snapshot_id_1,
        snapshot_id_2=request.snapshot_id_2,
    )

    if not comparison:
        raise HTTPException(
            status_code=404,
            detail="One or both snapshots not found"
        )

    return comparison


@router.get("/job/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    _=Depends(_require_dev_data_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Get the status of a snapshot-related job."""
    status = await snapshot_service.get_job_status(db, job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return status


@router.get("/tools/verify")
async def verify_backup_tools(
    _=Depends(_require_dev_data_access),
):
    """Verify that pg_dump and pg_restore tools are available.

    This endpoint checks if the required PostgreSQL tools are installed
    and accessible on the server.
    """
    handler = snapshot_service.handler
    available, message = await handler.verify_pg_tools()

    return {
        "tools_available": available,
        "details": message,
        "backup_path": str(snapshot_service.backup_path),
        "backup_path_exists": snapshot_service.backup_path.exists(),
    }
