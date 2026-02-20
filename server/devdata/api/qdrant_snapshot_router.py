"""API endpoints for Qdrant snapshot management."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.config.postgres import get_db_session, get_db_session_context
from server.devdata.qdrant_snapshot_models import (
    CreateQdrantSnapshotRequest,
    CreateQdrantSnapshotResponse,
    RestoreQdrantSnapshotRequest,
    RestoreQdrantSnapshotResponse,
    QdrantSnapshotDetail,
    QdrantSnapshotListResponse,
    DeleteQdrantSnapshotResponse,
)
from server.devdata.snapshot_models import JobStatusResponse
from server.devdata.qdrant_snapshot_service import qdrant_snapshot_service
from server.jobs import ProcessingJob
from server.logging_config import get_logger

logger = get_logger(name=__name__)

router = APIRouter(prefix="/qdrant-snapshots", tags=["Qdrant Snapshots"])


async def _require_dev_data_access(token: str = Depends(get_token_from_header)):
    """Dependency that verifies the user has dev data access."""
    access = await get_access_control(token)
    if not access.hasDevDataAccess:
        raise HTTPException(status_code=403, detail="Dev data access required")
    return access


async def _require_dev_data_write_access(token: str = Depends(get_token_from_header)):
    """Dependency that verifies the user has dev data write (admin) access."""
    access = await get_access_control(token)
    if not access.hasPipelinesAdminAccess:
        raise HTTPException(
            status_code=403,
            detail="Admin access required for snapshot operations",
        )
    return access


@router.post("/create", response_model=CreateQdrantSnapshotResponse)
async def create_snapshot(
    request: CreateQdrantSnapshotRequest,
    background_tasks: BackgroundTasks,
    access=Depends(_require_dev_data_write_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new Qdrant snapshot (background job)."""
    try:
        job_id = str(uuid.uuid4())
        job = ProcessingJob(
            id=job_id,
            job_type="qdrant_snapshot_creation",
            batch_id=0,
            upload_id="QDRANT-SNAPSHOT",
            status="pending",
            progress_percent=0,
            current_step="Initializing...",
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()

        snapshot_id = await qdrant_snapshot_service.generate_snapshot_id(db)

        background_tasks.add_task(
            _run_qdrant_snapshot_creation,
            job_id=job_id,
            name=request.name,
            description=request.description,
            user=access.user,
            collection_name=request.collection_name,
        )

        logger.info(f"Qdrant snapshot creation job {job_id} started by {access.user}")

        return CreateQdrantSnapshotResponse(
            success=True,
            message="Qdrant snapshot creation started",
            job_id=job_id,
            snapshot_id=snapshot_id,
        )

    except Exception as e:
        logger.error(f"Error starting Qdrant snapshot creation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start Qdrant snapshot creation: {str(e)}",
        )


async def _run_qdrant_snapshot_creation(
    job_id: str,
    name: str,
    description: str,
    user: str,
    collection_name: str,
):
    """Background task to create a Qdrant snapshot."""
    async with get_db_session_context() as db:
        await qdrant_snapshot_service.create_snapshot(
            db=db,
            job_id=job_id,
            name=name,
            description=description,
            user=user,
            collection_name=collection_name,
        )


@router.get("/list", response_model=QdrantSnapshotListResponse)
async def list_snapshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    collection_name: str = Query(None),
    _=Depends(_require_dev_data_access),
    db: AsyncSession = Depends(get_db_session),
):
    """List Qdrant snapshots with pagination."""
    return await qdrant_snapshot_service.list_snapshots(
        db=db,
        page=page,
        page_size=page_size,
        collection_name=collection_name,
    )


@router.get("/collections")
async def list_collections(
    _=Depends(_require_dev_data_access),
):
    """List available Qdrant collections."""
    try:
        collections = await qdrant_snapshot_service.list_collections()
        return {"collections": collections}
    except Exception as e:
        logger.error(f"Error listing Qdrant collections: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to list Qdrant collections: {str(e)}",
        )


@router.get("/job/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    _=Depends(_require_dev_data_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Get the status of a Qdrant snapshot job."""
    status = await qdrant_snapshot_service.get_job_status(db, job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return status


@router.get("/{snapshot_id}", response_model=QdrantSnapshotDetail)
async def get_snapshot(
    snapshot_id: str,
    _=Depends(_require_dev_data_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Get detailed information about a Qdrant snapshot."""
    snapshot = await qdrant_snapshot_service.get_snapshot_detail(db, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return snapshot


@router.post("/{snapshot_id}/restore", response_model=RestoreQdrantSnapshotResponse)
async def restore_snapshot(
    snapshot_id: str,
    request: RestoreQdrantSnapshotRequest,
    background_tasks: BackgroundTasks,
    access=Depends(_require_dev_data_write_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Restore a Qdrant collection from a snapshot (background job).

    WARNING: This will replace the Qdrant collection data!
    """
    try:
        snapshot = await qdrant_snapshot_service.get_snapshot_detail(db, snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")

        if snapshot.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Snapshot is in {snapshot.status} state, cannot restore",
            )

        job_id = str(uuid.uuid4())
        job = ProcessingJob(
            id=job_id,
            job_type="qdrant_snapshot_restore",
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

        background_tasks.add_task(
            _run_qdrant_snapshot_restore,
            job_id=job_id,
            snapshot_id=snapshot_id,
            user=access.user,
            force=request.force,
        )

        logger.info(f"Qdrant snapshot restore job {job_id} started by {access.user}")

        return RestoreQdrantSnapshotResponse(
            success=True,
            message="Qdrant snapshot restore started",
            job_id=job_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting Qdrant snapshot restore: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start Qdrant snapshot restore: {str(e)}",
        )


async def _run_qdrant_snapshot_restore(
    job_id: str,
    snapshot_id: str,
    user: str,
    force: bool,
):
    """Background task to restore a Qdrant snapshot."""
    async with get_db_session_context() as db:
        await qdrant_snapshot_service.restore_snapshot(
            db=db,
            job_id=job_id,
            snapshot_id=snapshot_id,
            user=user,
            force=force,
        )


@router.delete("/{snapshot_id}", response_model=DeleteQdrantSnapshotResponse)
async def delete_snapshot(
    snapshot_id: str,
    access=Depends(_require_dev_data_write_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a Qdrant snapshot and its backup file."""
    return await qdrant_snapshot_service.delete_snapshot(
        db=db,
        snapshot_id=snapshot_id,
        user=access.user,
    )
