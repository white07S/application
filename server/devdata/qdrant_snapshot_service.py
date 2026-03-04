"""Qdrant snapshot service — fully disk-based.

All snapshot metadata is read from and written to metadata.json files on disk.
No PostgreSQL tracking tables are used.  The only PG dependency is for job
tracking (ProcessingJob) during create/restore operations.
"""

import fcntl
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from server.devdata.disk_metadata import (
    DiskSnapshotMeta,
    find_snapshot,
    generate_snapshot_id,
    get_available_dates,
    scan_qdrant_snapshots,
    update_restore_tracking,
)
from server.devdata.qdrant_snapshot_models import (
    DeleteQdrantSnapshotResponse,
    QdrantSnapshotDetail,
    QdrantSnapshotInfo,
    QdrantSnapshotListResponse,
)
from server.devdata.snapshot_models import JobStatusResponse
from server.devdata.snapshot_service import SnapshotJobTracker
from server.jobs import ProcessingJob
from server.logging_config import get_logger
from server.settings import get_settings

logger = get_logger(name=__name__)

# Generous timeout for large snapshot transfers
SNAPSHOT_TIMEOUT = 600.0
# Chunk size for streaming downloads (1 MB)
STREAM_CHUNK_SIZE = 1024 * 1024


class QdrantSnapshotService:
    """Service for managing Qdrant snapshots — disk-based metadata."""

    BACKUP_FILENAME = "snapshot.snapshot"
    ID_PREFIX = "QSNAP"

    def __init__(self):
        self.settings = get_settings()
        self.backup_path = self.settings.qdrant_backup_path
        self.qdrant_url = self.settings.qdrant_url.rstrip("/")
        self.lock_file_path = self.backup_path / ".locks" / "qdrant_snapshot_operation.lock"
        self.lock_file = None

    # ------------------------------------------------------------------ lock
    async def acquire_operation_lock(self, operation: str) -> bool:
        try:
            self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.lock_file = open(self.lock_file_path, "w")
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_info = {
                "operation": operation,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
            }
            json.dump(lock_info, self.lock_file)
            self.lock_file.flush()
            logger.info(f"Acquired Qdrant snapshot lock for {operation}")
            return True
        except BlockingIOError:
            logger.warning("Cannot acquire lock - another Qdrant snapshot operation is running")
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False
        except Exception as e:
            logger.error(f"Error acquiring Qdrant snapshot lock: {e}")
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False

    def release_operation_lock(self):
        try:
            if self.lock_file:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                self.lock_file = None
                try:
                    self.lock_file_path.unlink()
                except Exception:
                    pass
                logger.info("Released Qdrant snapshot lock")
        except Exception as e:
            logger.error(f"Error releasing Qdrant snapshot lock: {e}")

    async def check_operation_status(self) -> Optional[Dict[str, Any]]:
        try:
            if not self.lock_file_path.exists():
                return None
            with open(self.lock_file_path, "r") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    return None
                except BlockingIOError:
                    f.seek(0)
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error checking Qdrant operation status: {e}")
            return None

    # -------------------------------------------------------- Qdrant HTTP helpers
    async def _get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.qdrant_url}/collections/{collection_name}")
            resp.raise_for_status()
            data = resp.json()
            result_data = data.get("result", {})
            return {
                "points_count": result_data.get("points_count", 0),
                "vectors_count": result_data.get("vectors_count", 0),
            }

    async def _qdrant_create_snapshot(self, collection_name: str) -> str:
        async with httpx.AsyncClient(timeout=SNAPSHOT_TIMEOUT) as client:
            resp = await client.post(
                f"{self.qdrant_url}/collections/{collection_name}/snapshots",
            )
            resp.raise_for_status()
            data = resp.json()
            return data["result"]["name"]

    async def _qdrant_download_snapshot(
        self, collection_name: str, snapshot_name: str, dest_path: Path
    ) -> int:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        total_bytes = 0
        async with httpx.AsyncClient(timeout=SNAPSHOT_TIMEOUT) as client:
            url = f"{self.qdrant_url}/collections/{collection_name}/snapshots/{snapshot_name}"
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(STREAM_CHUNK_SIZE):
                        f.write(chunk)
                        total_bytes += len(chunk)
        return total_bytes

    async def _qdrant_upload_snapshot(
        self, collection_name: str, file_path: Path
    ) -> None:
        file_size = file_path.stat().st_size
        logger.info(
            "Uploading snapshot {} ({:.1f} MB) to collection {}",
            file_path.name, file_size / (1024 * 1024), collection_name,
        )
        timeout = httpx.Timeout(30.0, read=None, write=None)
        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(file_path, "rb") as f:
                resp = await client.post(
                    f"{self.qdrant_url}/collections/{collection_name}/snapshots/upload",
                    files={"snapshot": (file_path.name, f, "application/octet-stream")},
                )
            if resp.status_code >= 400:
                logger.error(
                    "Qdrant upload failed: status={} body={}",
                    resp.status_code, resp.text[:500],
                )
            resp.raise_for_status()

    async def _qdrant_delete_snapshot(
        self, collection_name: str, snapshot_name: str
    ) -> None:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(
                    f"{self.qdrant_url}/collections/{collection_name}/snapshots/{snapshot_name}",
                )
                resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to delete Qdrant-side snapshot {snapshot_name}: {e}")

    async def list_collections(self) -> List[str]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.qdrant_url}/collections")
            resp.raise_for_status()
            data = resp.json()
            collections = data.get("result", {}).get("collections", [])
            return [c["name"] for c in collections]

    # ---------------------------------------------------------- checksum
    @staticmethod
    def _calculate_sha256(file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    # ---------------------------------------------------------- create
    async def create_snapshot(
        self,
        db: AsyncSession,
        job_id: str,
        name: str,
        description: Optional[str],
        user: str,
        collection_name: str,
    ) -> None:
        tracker = SnapshotJobTracker(db)
        snapshot_id = None
        lock_acquired = False

        try:
            lock_acquired = await self.acquire_operation_lock("create")
            if not lock_acquired:
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Another Qdrant snapshot operation is in progress",
                    error_message="Cannot create snapshot while another operation is running",
                )
                return

            await tracker.update_progress(
                job_id=job_id,
                status="running",
                progress_percent=5,
                current_step="Initializing Qdrant snapshot...",
            )

            # Generate snapshot ID from disk scan
            snapshot_id = generate_snapshot_id(self.backup_path, self.ID_PREFIX)
            logger.info(f"Creating Qdrant snapshot {snapshot_id} for collection {collection_name}")

            # Get collection stats
            await tracker.update_progress(
                job_id=job_id, progress_percent=10,
                current_step="Fetching collection statistics...",
            )
            stats = await self._get_collection_stats(collection_name)

            # Prepare local path
            snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            snapshot_dir = self.backup_path / snapshot_date / snapshot_id
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            local_file = snapshot_dir / self.BACKUP_FILENAME

            # Ask Qdrant to create snapshot
            await tracker.update_progress(
                job_id=job_id, progress_percent=20,
                current_step="Creating snapshot in Qdrant...",
            )
            qdrant_snapshot_name = await self._qdrant_create_snapshot(collection_name)

            # Download snapshot file
            await tracker.update_progress(
                job_id=job_id, progress_percent=40,
                current_step="Downloading snapshot file...",
            )
            file_size = await self._qdrant_download_snapshot(
                collection_name, qdrant_snapshot_name, local_file
            )

            # Calculate checksum
            await tracker.update_progress(
                job_id=job_id, progress_percent=85,
                current_step="Calculating checksum...",
            )
            checksum = self._calculate_sha256(local_file)

            # Write metadata.json — single source of truth
            metadata = {
                "snapshot_id": snapshot_id,
                "name": name,
                "description": description,
                "collection_name": collection_name,
                "qdrant_snapshot_name": qdrant_snapshot_name,
                "created_by": user,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "points_count": stats["points_count"],
                "vectors_count": stats["vectors_count"],
                "file_size": file_size,
                "checksum": checksum,
                "status": "completed",
                "restored_count": 0,
                "qdrant_url": self.qdrant_url,
            }
            with open(snapshot_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            # Clean up Qdrant-side snapshot (we have the local copy)
            await self._qdrant_delete_snapshot(collection_name, qdrant_snapshot_name)

            await tracker.update_progress(
                job_id=job_id,
                status="completed",
                progress_percent=100,
                current_step="Snapshot created successfully",
            )
            logger.info(
                f"Qdrant snapshot {snapshot_id} created ({file_size / 1024 / 1024:.2f} MB)"
            )

        except Exception as e:
            logger.error(f"Error creating Qdrant snapshot: {e}")

            # Write failed metadata if we got an ID
            if snapshot_id:
                snapshot_dir = (
                    self.backup_path
                    / datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    / snapshot_id
                )
                if snapshot_dir.exists():
                    failed_meta = {
                        "snapshot_id": snapshot_id,
                        "name": name,
                        "description": description,
                        "collection_name": collection_name,
                        "created_by": user,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "status": "failed",
                        "error_message": str(e),
                    }
                    try:
                        with open(snapshot_dir / "metadata.json", "w") as f:
                            json.dump(failed_meta, f, indent=2)
                    except Exception:
                        pass

            await tracker.update_progress(
                job_id=job_id,
                status="failed",
                current_step="Unexpected error",
                error_message=str(e),
            )
        finally:
            if lock_acquired:
                self.release_operation_lock()

    # ---------------------------------------------------------- restore
    async def restore_snapshot(
        self,
        db: AsyncSession,
        job_id: str,
        snapshot_id: str,
        user: str,
        date_str: Optional[str] = None,
        force: bool = False,
    ) -> None:
        tracker = SnapshotJobTracker(db)
        lock_acquired = False

        try:
            lock_acquired = await self.acquire_operation_lock("restore")
            if not lock_acquired:
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Another Qdrant snapshot operation is in progress",
                    error_message="Cannot restore while another operation is running",
                )
                return

            await tracker.update_progress(
                job_id=job_id,
                status="running",
                progress_percent=5,
                current_step="Loading snapshot information...",
            )

            # Find snapshot on disk
            snap = find_snapshot(
                self.backup_path, snapshot_id, self.BACKUP_FILENAME, date_str=date_str
            )
            if not snap:
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Snapshot not found",
                    error_message=f"Snapshot {snapshot_id} not found on disk",
                )
                return

            local_file = Path(snap.file_path)
            if not local_file.exists():
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Snapshot file not found",
                    error_message=f"File not found: {local_file}",
                )
                return

            # Upload snapshot to Qdrant
            await tracker.update_progress(
                job_id=job_id,
                progress_percent=20,
                current_step="Uploading snapshot to Qdrant...",
            )
            await self._qdrant_upload_snapshot(snap.collection_name, local_file)

            # Update restore tracking on disk
            update_restore_tracking(snap.metadata_path, user)

            await tracker.update_progress(
                job_id=job_id,
                status="completed",
                progress_percent=100,
                current_step="Restore completed successfully",
            )
            logger.info(f"Qdrant snapshot {snapshot_id} restored by {user}")

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error("Error restoring Qdrant snapshot: {}", error_msg, exc_info=True)
            await tracker.update_progress(
                job_id=job_id,
                status="failed",
                current_step="Unexpected error",
                error_message=error_msg,
            )
        finally:
            if lock_acquired:
                self.release_operation_lock()

    # ---------------------------------------------------------- list
    def list_snapshots(
        self,
        page: int = 1,
        page_size: int = 20,
        collection_name: Optional[str] = None,
    ) -> QdrantSnapshotListResponse:
        """List Qdrant snapshots from disk with pagination."""
        all_snapshots = scan_qdrant_snapshots(
            self.backup_path, collection_filter=collection_name
        )
        total = len(all_snapshots)
        offset = (page - 1) * page_size
        page_items = all_snapshots[offset : offset + page_size]

        return QdrantSnapshotListResponse(
            snapshots=[
                QdrantSnapshotInfo(
                    id=s.snapshot_id,
                    name=s.name,
                    description=s.description,
                    collection_name=s.collection_name or "unknown",
                    file_size=s.file_size,
                    points_count=s.points_count or 0,
                    created_by=s.created_by,
                    created_at=s.created_at,
                    status=s.status,
                    restored_count=s.restored_count,
                )
                for s in page_items
            ],
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + len(page_items) < total),
        )

    # ---------------------------------------------------------- detail
    def get_snapshot_detail(
        self,
        snapshot_id: str,
        date_str: Optional[str] = None,
    ) -> Optional[QdrantSnapshotDetail]:
        """Get detailed info about a Qdrant snapshot from disk."""
        snap = find_snapshot(
            self.backup_path, snapshot_id, self.BACKUP_FILENAME, date_str=date_str
        )
        if not snap:
            return None

        return QdrantSnapshotDetail(
            id=snap.snapshot_id,
            name=snap.name,
            description=snap.description,
            collection_name=snap.collection_name or "unknown",
            qdrant_snapshot_name=snap.qdrant_snapshot_name,
            file_path=snap.file_path,
            file_size=snap.file_size,
            checksum=snap.checksum,
            points_count=snap.points_count or 0,
            vectors_count=snap.vectors_count or 0,
            created_by=snap.created_by,
            created_at=snap.created_at,
            restored_count=snap.restored_count,
            last_restored_at=snap.last_restored_at,
            last_restored_by=snap.last_restored_by,
            status=snap.status,
            error_message=snap.error_message,
        )

    # ---------------------------------------------------------- delete
    def delete_snapshot(
        self,
        snapshot_id: str,
        user: str,
        date_str: Optional[str] = None,
    ) -> DeleteQdrantSnapshotResponse:
        """Delete a Qdrant snapshot directory from disk."""
        try:
            snap = find_snapshot(
                self.backup_path, snapshot_id, self.BACKUP_FILENAME, date_str=date_str
            )
            if not snap:
                return DeleteQdrantSnapshotResponse(
                    success=False,
                    message=f"Snapshot {snapshot_id} not found",
                    deleted_file=False,
                )

            snapshot_dir = snap.metadata_path.parent
            shutil.rmtree(snapshot_dir)

            # Try to remove parent date dir if empty
            try:
                snapshot_dir.parent.rmdir()
            except OSError:
                pass

            logger.info(f"Qdrant snapshot {snapshot_id} deleted by {user}")

            return DeleteQdrantSnapshotResponse(
                success=True,
                message=f"Snapshot {snapshot_id} deleted successfully",
                deleted_file=True,
            )

        except Exception as e:
            logger.error(f"Error deleting Qdrant snapshot {snapshot_id}: {e}")
            return DeleteQdrantSnapshotResponse(
                success=False,
                message=f"Error deleting snapshot: {str(e)}",
                deleted_file=False,
            )

    # ---------------------------------------------------------- job status
    STALE_JOB_TIMEOUT_SECONDS = 300  # 5 minutes

    async def get_job_status(
        self, db: AsyncSession, job_id: str
    ) -> Optional[JobStatusResponse]:
        from datetime import datetime, timezone

        job = await db.get(ProcessingJob, job_id)
        if not job:
            return None

        status = job.status
        error_message = job.error_message

        # Detect stale jobs: if pending for too long, the Celery task
        # likely crashed without updating the DB.
        if status in ("pending", "running") and job.started_at:
            elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
            if status == "pending" and elapsed > self.STALE_JOB_TIMEOUT_SECONDS:
                status = "failed"
                error_message = "Job timed out — the background worker may have crashed. Please retry."
                job.status = status
                job.error_message = error_message
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

        return JobStatusResponse(
            job_id=job.id,
            status=status,
            progress_percent=job.progress_percent,
            current_step=job.current_step,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_message=error_message,
        )


# Singleton
qdrant_snapshot_service = QdrantSnapshotService()
