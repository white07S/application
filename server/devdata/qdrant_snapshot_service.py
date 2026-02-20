"""Qdrant snapshot service.

Provides core snapshot operations: create, restore, list, delete.
Uses Qdrant REST API for snapshot creation/download/upload, stores
snapshots locally, and tracks metadata in PostgreSQL.
"""

import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from server.config.postgres import get_db_session_context
from server.devdata.qdrant_snapshot_models import (
    QdrantSnapshot,
    CreateQdrantSnapshotResponse,
    RestoreQdrantSnapshotResponse,
    QdrantSnapshotInfo,
    QdrantSnapshotDetail,
    QdrantSnapshotListResponse,
    DeleteQdrantSnapshotResponse,
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
    """Service for managing Qdrant snapshots."""

    def __init__(self):
        self.settings = get_settings()
        self.backup_path = self.settings.qdrant_backup_path
        self.qdrant_url = self.settings.qdrant_url.rstrip("/")
        self.lock_file_path = self.backup_path / ".locks" / "qdrant_snapshot_operation.lock"
        self.lock_file = None

    # ------------------------------------------------------------------ lock
    async def acquire_operation_lock(self, operation: str) -> bool:
        """Acquire exclusive lock for snapshot operations."""
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
        """Release the operation lock."""
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
        """Check if a Qdrant snapshot operation is currently running."""
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

    # ----------------------------------------------------------- ID gen
    async def generate_snapshot_id(self, db: AsyncSession) -> str:
        """Generate a unique snapshot ID in QSNAP-YYYY-XXXX format."""
        current_year = datetime.now(timezone.utc).year
        result = await db.execute(
            select(func.max(QdrantSnapshot.id))
            .where(QdrantSnapshot.id.like(f"QSNAP-{current_year}-%"))
        )
        max_id = result.scalar()

        if max_id:
            sequence = int(max_id.split("-")[-1]) + 1
        else:
            sequence = 1

        return f"QSNAP-{current_year}-{sequence:04d}"

    # -------------------------------------------------------- Qdrant HTTP helpers
    async def _get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get collection info from Qdrant REST API."""
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
        """Tell Qdrant to create a snapshot. Returns the snapshot name."""
        async with httpx.AsyncClient(timeout=SNAPSHOT_TIMEOUT) as client:
            resp = await client.post(
                f"{self.qdrant_url}/collections/{collection_name}/snapshots",
            )
            resp.raise_for_status()
            data = resp.json()
            # Qdrant returns {"result": {"name": "...", ...}}
            return data["result"]["name"]

    async def _qdrant_download_snapshot(
        self, collection_name: str, snapshot_name: str, dest_path: Path
    ) -> int:
        """Stream-download a Qdrant snapshot file. Returns file size in bytes."""
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
        """Upload a local snapshot file to Qdrant for restore."""
        file_size = file_path.stat().st_size

        async with httpx.AsyncClient(timeout=SNAPSHOT_TIMEOUT) as client:
            with open(file_path, "rb") as f:
                resp = await client.post(
                    f"{self.qdrant_url}/collections/{collection_name}/snapshots/upload",
                    content=f,
                    headers={
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(file_size),
                    },
                )
                resp.raise_for_status()

    async def _qdrant_delete_snapshot(
        self, collection_name: str, snapshot_name: str
    ) -> None:
        """Delete a snapshot from Qdrant's internal storage."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(
                    f"{self.qdrant_url}/collections/{collection_name}/snapshots/{snapshot_name}",
                )
                resp.raise_for_status()
        except Exception as e:
            # Non-fatal: the local copy is what matters
            logger.warning(f"Failed to delete Qdrant-side snapshot {snapshot_name}: {e}")

    async def list_collections(self) -> List[str]:
        """List available Qdrant collections."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.qdrant_url}/collections")
            resp.raise_for_status()
            data = resp.json()
            collections = data.get("result", {}).get("collections", [])
            return [c["name"] for c in collections]

    # ---------------------------------------------------------- checksum
    @staticmethod
    def _calculate_sha256(file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
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
        """Create a new Qdrant snapshot (runs in background)."""
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

            # Generate snapshot ID
            snapshot_id = await self.generate_snapshot_id(db)
            logger.info(f"Creating Qdrant snapshot {snapshot_id} for collection {collection_name}")

            # Get collection stats
            await tracker.update_progress(
                job_id=job_id,
                progress_percent=10,
                current_step="Fetching collection statistics...",
            )
            stats = await self._get_collection_stats(collection_name)

            # Prepare local path
            snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            snapshot_dir = self.backup_path / snapshot_date / snapshot_id
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            local_file = snapshot_dir / "snapshot.snapshot"

            # Create DB record with in_progress status
            snapshot = QdrantSnapshot(
                id=snapshot_id,
                name=name,
                description=description,
                collection_name=collection_name,
                file_path=str(local_file),
                file_size=0,
                points_count=stats["points_count"],
                vectors_count=stats["vectors_count"],
                created_by=user,
                created_at=datetime.now(timezone.utc),
                restored_count=0,
                status="in_progress",
            )
            db.add(snapshot)
            await db.commit()

            # Ask Qdrant to create snapshot
            await tracker.update_progress(
                job_id=job_id,
                progress_percent=20,
                current_step="Creating snapshot in Qdrant...",
            )
            qdrant_snapshot_name = await self._qdrant_create_snapshot(collection_name)

            # Download snapshot file
            await tracker.update_progress(
                job_id=job_id,
                progress_percent=40,
                current_step="Downloading snapshot file...",
            )
            file_size = await self._qdrant_download_snapshot(
                collection_name, qdrant_snapshot_name, local_file
            )

            # Calculate checksum
            await tracker.update_progress(
                job_id=job_id,
                progress_percent=85,
                current_step="Calculating checksum...",
            )
            checksum = self._calculate_sha256(local_file)

            # Save metadata.json
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
            }
            with open(snapshot_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            # Update DB record
            snapshot.qdrant_snapshot_name = qdrant_snapshot_name
            snapshot.file_size = file_size
            snapshot.checksum = checksum
            snapshot.status = "completed"
            await db.commit()

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

            if snapshot_id:
                record = await db.get(QdrantSnapshot, snapshot_id)
                if record:
                    record.status = "failed"
                    record.error_message = str(e)
                    await db.commit()

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
        force: bool = False,
    ) -> None:
        """Restore a Qdrant collection from a local snapshot (runs in background)."""
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

            snapshot = await db.get(QdrantSnapshot, snapshot_id)
            if not snapshot:
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Snapshot not found",
                    error_message=f"Snapshot {snapshot_id} not found",
                )
                return

            local_file = Path(snapshot.file_path)
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
            await self._qdrant_upload_snapshot(snapshot.collection_name, local_file)

            # Update restore tracking
            snapshot.restored_count += 1
            snapshot.last_restored_at = datetime.now(timezone.utc)
            snapshot.last_restored_by = user
            await db.commit()

            await tracker.update_progress(
                job_id=job_id,
                status="completed",
                progress_percent=100,
                current_step="Restore completed successfully",
            )

            logger.info(f"Qdrant snapshot {snapshot_id} restored by {user}")

        except Exception as e:
            logger.error(f"Error restoring Qdrant snapshot: {e}")
            await tracker.update_progress(
                job_id=job_id,
                status="failed",
                current_step="Unexpected error",
                error_message=str(e),
            )
        finally:
            if lock_acquired:
                self.release_operation_lock()

    # ---------------------------------------------------------- list
    async def list_snapshots(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        collection_name: Optional[str] = None,
    ) -> QdrantSnapshotListResponse:
        """List Qdrant snapshots with pagination."""
        query = select(QdrantSnapshot).order_by(desc(QdrantSnapshot.created_at))

        if collection_name:
            query = query.where(QdrantSnapshot.collection_name == collection_name)

        count_query = select(func.count()).select_from(QdrantSnapshot)
        if collection_name:
            count_query = count_query.where(QdrantSnapshot.collection_name == collection_name)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.limit(page_size).offset(offset)

        result = await db.execute(query)
        snapshots = result.scalars().all()

        return QdrantSnapshotListResponse(
            snapshots=[
                QdrantSnapshotInfo(
                    id=s.id,
                    name=s.name,
                    description=s.description,
                    collection_name=s.collection_name,
                    file_size=s.file_size,
                    points_count=s.points_count,
                    created_by=s.created_by,
                    created_at=s.created_at,
                    status=s.status,
                    restored_count=s.restored_count,
                )
                for s in snapshots
            ],
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + len(snapshots) < total),
        )

    # ---------------------------------------------------------- detail
    async def get_snapshot_detail(
        self, db: AsyncSession, snapshot_id: str
    ) -> Optional[QdrantSnapshotDetail]:
        """Get detailed info about a Qdrant snapshot."""
        snapshot = await db.get(QdrantSnapshot, snapshot_id)
        if not snapshot:
            return None

        return QdrantSnapshotDetail(
            id=snapshot.id,
            name=snapshot.name,
            description=snapshot.description,
            collection_name=snapshot.collection_name,
            qdrant_snapshot_name=snapshot.qdrant_snapshot_name,
            file_path=snapshot.file_path,
            file_size=snapshot.file_size,
            checksum=snapshot.checksum,
            points_count=snapshot.points_count,
            vectors_count=snapshot.vectors_count,
            created_by=snapshot.created_by,
            created_at=snapshot.created_at,
            restored_count=snapshot.restored_count,
            last_restored_at=snapshot.last_restored_at,
            last_restored_by=snapshot.last_restored_by,
            status=snapshot.status,
            error_message=snapshot.error_message,
        )

    # ---------------------------------------------------------- delete
    async def delete_snapshot(
        self, db: AsyncSession, snapshot_id: str, user: str
    ) -> DeleteQdrantSnapshotResponse:
        """Delete a Qdrant snapshot (local file + DB record)."""
        try:
            snapshot = await db.get(QdrantSnapshot, snapshot_id)
            if not snapshot:
                return DeleteQdrantSnapshotResponse(
                    success=False,
                    message=f"Snapshot {snapshot_id} not found",
                    deleted_file=False,
                )

            # Delete local file
            local_file = Path(snapshot.file_path)
            deleted_file = False

            if local_file.exists():
                local_file.unlink()
                deleted_file = True

                # Delete metadata if present
                snapshot_dir = local_file.parent
                metadata_file = snapshot_dir / "metadata.json"
                if metadata_file.exists():
                    metadata_file.unlink()

                # Remove dir if empty
                try:
                    snapshot_dir.rmdir()
                except OSError:
                    pass

            # Delete DB record
            await db.delete(snapshot)
            await db.commit()

            logger.info(f"Qdrant snapshot {snapshot_id} deleted by {user}")

            return DeleteQdrantSnapshotResponse(
                success=True,
                message=f"Snapshot {snapshot_id} deleted successfully",
                deleted_file=deleted_file,
            )

        except Exception as e:
            logger.error(f"Error deleting Qdrant snapshot {snapshot_id}: {e}")
            return DeleteQdrantSnapshotResponse(
                success=False,
                message=f"Error deleting snapshot: {str(e)}",
                deleted_file=False,
            )

    # ---------------------------------------------------------- job status
    async def get_job_status(
        self, db: AsyncSession, job_id: str
    ) -> Optional[JobStatusResponse]:
        """Get status of a Qdrant snapshot job."""
        job = await db.get(ProcessingJob, job_id)
        if not job:
            return None

        return JobStatusResponse(
            job_id=job.id,
            status=job.status,
            progress_percent=job.progress_percent,
            current_step=job.current_step,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
        )


# Singleton
qdrant_snapshot_service = QdrantSnapshotService()
