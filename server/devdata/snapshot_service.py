"""PostgreSQL snapshot service — fully disk-based.

All snapshot metadata is read from and written to metadata.json files on disk.
No PostgreSQL snapshot tracking tables are used.  The only PG dependency is
for create (pg_dump against the live DB) and restore (pg_restore into the DB).
"""

import asyncio
import fcntl
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from server.devdata.disk_metadata import (
    DiskSnapshotMeta,
    find_snapshot,
    generate_snapshot_id,
    get_available_dates,
    scan_pg_snapshots,
    update_restore_tracking,
)
from server.devdata.snapshot_models import (
    DeleteSnapshotResponse,
    JobStatusResponse,
    SnapshotComparison,
    SnapshotDetail,
    SnapshotInfo,
    SnapshotListResponse,
)
from server.devdata.subprocess_handler import PostgresBackupHandler
from server.jobs import ProcessingJob
from server.logging_config import get_logger
from server.pipelines.api.job_tracker import JobTracker
from server.settings import get_settings

logger = get_logger(name=__name__)


class SnapshotJobTracker(JobTracker):
    """Snapshot-specific tracker with commit-on-progress semantics."""

    async def update_progress(self, job_id: str, **kwargs: Any) -> bool:
        if kwargs.get("status") in {"completed", "failed"} and "completed_at" not in kwargs:
            kwargs["completed_at"] = datetime.now(timezone.utc)

        updated = await self.update_job_status(job_id=job_id, **kwargs)
        if not updated:
            return False

        await self.db.commit()
        return True


class PostgresSnapshotService:
    """Service for managing PostgreSQL snapshots — disk-based metadata."""

    BACKUP_FILENAME = "backup.dump"
    ID_PREFIX = "SNAP"

    def __init__(self):
        self.settings = get_settings()
        self.backup_path = self.settings.postgres_backup_path
        self.handler = PostgresBackupHandler(self.settings.postgres_url)
        self.lock_file_path = self.backup_path / ".locks" / "snapshot_operation.lock"
        self.lock_file = None

    # ------------------------------------------------------------------ lock
    async def acquire_operation_lock(self, operation: str, timeout: int = 5) -> bool:
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
            logger.info(f"Acquired lock for {operation} operation")
            return True
        except BlockingIOError:
            logger.warning("Cannot acquire lock - another snapshot operation is running")
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
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
                logger.info("Released operation lock")
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")

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
            logger.error(f"Error checking operation status: {e}")
            return None

    # ----------------------------------------------------------- helpers
    async def get_alembic_version(self, db: AsyncSession) -> str:
        result = await db.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        )
        row = result.first()
        return row[0] if row else "unknown"

    async def get_database_stats(self, db: AsyncSession) -> Dict[str, Any]:
        table_count_result = await db.execute(
            text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                  AND table_name NOT LIKE 'alembic%'
            """)
        )
        table_count = table_count_result.scalar() or 0

        record_count_result = await db.execute(
            text("""
                SELECT SUM(n_live_tup)
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
            """)
        )
        total_records = record_count_result.scalar() or 0

        return {
            "table_count": table_count,
            "total_records": int(total_records),
        }

    # ----------------------------------------------------------- create
    async def create_snapshot(
        self,
        db: AsyncSession,
        job_id: str,
        name: str,
        description: Optional[str],
        user: str,
        is_scheduled: bool = False,
        schedule_id: Optional[str] = None,
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
                    current_step="Another snapshot operation is in progress",
                    error_message="Cannot create snapshot while another operation is running",
                )
                return

            await tracker.update_progress(
                job_id=job_id,
                status="running",
                progress_percent=5,
                current_step="Initializing snapshot...",
            )

            # Generate snapshot ID from disk scan
            snapshot_id = generate_snapshot_id(self.backup_path, self.ID_PREFIX)
            logger.info(f"Creating snapshot {snapshot_id} for user {user}")

            # Get Alembic version
            await tracker.update_progress(
                job_id=job_id, progress_percent=10,
                current_step="Checking database version...",
            )
            alembic_version = await self.get_alembic_version(db)

            # Get database statistics
            await tracker.update_progress(
                job_id=job_id, progress_percent=15,
                current_step="Gathering database statistics...",
            )
            stats = await self.get_database_stats(db)

            # Create snapshot directory
            snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            snapshot_dir = self.backup_path / snapshot_date / snapshot_id
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            backup_file = snapshot_dir / self.BACKUP_FILENAME

            # Execute pg_dump
            async def progress_callback(step: str, percent: int):
                overall_percent = 20 + int(percent * 0.7)
                await tracker.update_progress(
                    job_id=job_id,
                    progress_percent=overall_percent,
                    current_step=step,
                )

            parallel_jobs = getattr(self.settings, "postgres_backup_parallel_jobs", 4)

            result = await self.handler.execute_pg_dump(
                output_path=backup_file,
                compress=self.settings.postgres_backup_compression,
                parallel_jobs=parallel_jobs,
                progress_callback=progress_callback,
            )

            if result.success:
                await tracker.update_progress(
                    job_id=job_id, progress_percent=92,
                    current_step="Calculating checksum...",
                )
                checksum = await self.handler.calculate_checksum(result.output_file)

                # Write metadata.json — single source of truth
                metadata = {
                    "snapshot_id": snapshot_id,
                    "name": name,
                    "description": description,
                    "created_by": user,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "alembic_version": alembic_version,
                    "table_count": stats["table_count"],
                    "total_records": stats["total_records"],
                    "file_size": result.file_size,
                    "checksum": checksum,
                    "compressed": self.settings.postgres_backup_compression,
                    "status": "completed",
                    "is_scheduled": is_scheduled,
                    "schedule_id": schedule_id,
                    "restored_count": 0,
                    # Connection info for restore without live DB context
                    "postgres_host": self.handler.host,
                    "postgres_port": self.handler.port,
                    "postgres_database": self.handler.database,
                    "postgres_username": self.handler.username,
                }
                with open(snapshot_dir / "metadata.json", "w") as f:
                    json.dump(metadata, f, indent=2)

                # Checksum file
                with open(snapshot_dir / "checksum.sha256", "w") as f:
                    f.write(f"{checksum}  {result.output_file.name}\n")

                await tracker.update_progress(
                    job_id=job_id,
                    status="completed",
                    progress_percent=100,
                    current_step="Snapshot created successfully",
                )
                logger.info(
                    f"Snapshot {snapshot_id} created successfully "
                    f"({result.file_size / 1024 / 1024:.2f} MB)"
                )
            else:
                # Write failed metadata
                metadata = {
                    "snapshot_id": snapshot_id,
                    "name": name,
                    "description": description,
                    "created_by": user,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "failed",
                    "error_message": result.stderr,
                }
                with open(snapshot_dir / "metadata.json", "w") as f:
                    json.dump(metadata, f, indent=2)

                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Backup failed",
                    error_message=result.stderr,
                )
                logger.error(f"Failed to create snapshot {snapshot_id}: {result.stderr}")

        except Exception as e:
            logger.error(f"Error creating snapshot: {e}")
            await tracker.update_progress(
                job_id=job_id,
                status="failed",
                current_step="Unexpected error",
                error_message=str(e),
            )
        finally:
            if lock_acquired:
                self.release_operation_lock()

    # ----------------------------------------------------------- restore
    @staticmethod
    async def _ensure_job_record(
        db: AsyncSession,
        job_id: str,
        *,
        status: str = "running",
        progress_percent: int = 0,
        current_step: str = "Finalizing...",
        error_message: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Re-create job record if pg_restore replaced the DB contents,
        and set final status in a single commit so update_job_status is
        never called on a row that doesn't exist yet.
        """
        existing = await db.get(ProcessingJob, job_id)
        if existing:
            existing.status = status
            existing.progress_percent = progress_percent
            existing.current_step = current_step
            if error_message is not None:
                existing.error_message = error_message
            if completed_at is not None:
                existing.completed_at = completed_at
        else:
            job = ProcessingJob(
                id=job_id,
                job_type="snapshot_restore",
                batch_id=0,
                upload_id="restored",
                status=status,
                progress_percent=progress_percent,
                current_step=current_step,
                error_message=error_message,
                started_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                completed_at=completed_at,
            )
            db.add(job)
        await db.commit()

    async def restore_snapshot(
        self,
        db: AsyncSession,
        job_id: str,
        snapshot_id: str,
        user: str,
        date_str: Optional[str] = None,
        create_pre_restore_backup: bool = True,
        force: bool = False,
    ) -> Optional[str]:
        tracker = SnapshotJobTracker(db)
        pre_restore_snapshot_id = None
        lock_acquired = False

        try:
            lock_acquired = await self.acquire_operation_lock("restore")
            if not lock_acquired:
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Another snapshot operation is in progress",
                    error_message="Cannot restore while another operation is running",
                )
                return None

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
                return None

            backup_path = Path(snap.file_path)
            if not backup_path.exists():
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Backup file not found",
                    error_message=f"Backup file not found: {backup_path}",
                )
                return None

            # Check Alembic version compatibility
            current_version = await self.get_alembic_version(db)
            if snap.alembic_version and current_version != snap.alembic_version and not force:
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Version mismatch",
                    error_message=(
                        f"Alembic version mismatch: current={current_version}, "
                        f"snapshot={snap.alembic_version}"
                    ),
                )
                return None

            # Create pre-restore backup if requested
            if create_pre_restore_backup:
                await tracker.update_progress(
                    job_id=job_id,
                    progress_percent=10,
                    current_step="Creating pre-restore backup...",
                )
                pre_restore_job_id = str(uuid.uuid4())
                pre_restore_job = ProcessingJob(
                    id=pre_restore_job_id,
                    job_type="snapshot_creation",
                    batch_id=0,
                    upload_id="PRE-RESTORE",
                    status="pending",
                    progress_percent=0,
                    current_step="Initializing...",
                    started_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc),
                )
                db.add(pre_restore_job)
                await db.commit()

                await self.create_snapshot(
                    db=db,
                    job_id=pre_restore_job_id,
                    name=f"Pre-restore backup for {snapshot_id}",
                    description=f"Automatic backup before restoring {snap.name}",
                    user=user,
                    is_scheduled=False,
                )

                # Check result
                pre_job = await db.get(ProcessingJob, pre_restore_job_id)
                if pre_job and pre_job.status == "completed":
                    # Find the pre-restore snapshot ID from disk
                    all_snaps = scan_pg_snapshots(self.backup_path)
                    for s in all_snaps:
                        if s.name == f"Pre-restore backup for {snapshot_id}":
                            pre_restore_snapshot_id = s.snapshot_id
                            break
                elif pre_job and pre_job.status == "failed":
                    await tracker.update_progress(
                        job_id=job_id,
                        status="failed",
                        current_step="Pre-restore backup failed",
                        error_message=pre_job.error_message,
                    )
                    return None

            # Execute pg_restore
            await tracker.update_progress(
                job_id=job_id,
                progress_percent=30,
                current_step="Starting database restore...",
            )

            async def progress_callback(step: str, percent: int):
                overall_percent = 30 + int(percent * 0.65)
                logger.info("pg_restore progress: {}% - {}", overall_percent, step)

            parallel_jobs = getattr(self.settings, "postgres_backup_parallel_jobs", 4)

            result = await self.handler.execute_pg_restore(
                backup_path=backup_path,
                clean=True,
                parallel_jobs=parallel_jobs,
                progress_callback=progress_callback,
            )

            # pg_restore --clean drops/recreates tables, poisoning the session
            await db.rollback()

            if result.success:
                # Update restore tracking on disk
                update_restore_tracking(snap.metadata_path, user)

                # Ensure job record exists and set final status in one shot
                # (avoids "Job not found" warning from update_job_status)
                await self._ensure_job_record(
                    db, job_id,
                    status="completed",
                    progress_percent=100,
                    current_step="Restore completed successfully",
                    completed_at=datetime.now(timezone.utc),
                )
                logger.info(f"Successfully restored snapshot {snapshot_id} by {user}")
                return pre_restore_snapshot_id
            else:
                await self._ensure_job_record(
                    db, job_id,
                    status="failed",
                    current_step="Restore failed",
                    error_message=result.stderr,
                    completed_at=datetime.now(timezone.utc),
                )
                logger.error(f"Failed to restore snapshot {snapshot_id}: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Error restoring snapshot: {e}")
            try:
                await db.rollback()
                await self._ensure_job_record(
                    db, job_id,
                    status="failed",
                    current_step="Unexpected error",
                    error_message=str(e),
                    completed_at=datetime.now(timezone.utc),
                )
            except Exception as inner:
                logger.error(f"Failed to update job status after error: {inner}")
            return None
        finally:
            if lock_acquired:
                self.release_operation_lock()

    # ----------------------------------------------------------- list
    def list_snapshots(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> SnapshotListResponse:
        """List available snapshots from disk with pagination."""
        all_snapshots = scan_pg_snapshots(self.backup_path)
        total = len(all_snapshots)
        offset = (page - 1) * page_size
        page_items = all_snapshots[offset : offset + page_size]

        return SnapshotListResponse(
            snapshots=[
                SnapshotInfo(
                    id=s.snapshot_id,
                    name=s.name,
                    description=s.description,
                    file_size=s.file_size,
                    created_by=s.created_by,
                    created_at=s.created_at,
                    status=s.status,
                    is_scheduled=s.is_scheduled,
                    restored_count=s.restored_count,
                )
                for s in page_items
            ],
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + len(page_items) < total),
        )

    # ----------------------------------------------------------- detail
    def get_snapshot_detail(
        self,
        snapshot_id: str,
        date_str: Optional[str] = None,
    ) -> Optional[SnapshotDetail]:
        """Get detailed snapshot info from disk."""
        snap = find_snapshot(
            self.backup_path, snapshot_id, self.BACKUP_FILENAME, date_str=date_str
        )
        if not snap:
            return None

        return SnapshotDetail(
            id=snap.snapshot_id,
            name=snap.name,
            description=snap.description,
            file_path=snap.file_path,
            file_size=snap.file_size,
            checksum=snap.checksum,
            alembic_version=snap.alembic_version or "unknown",
            table_count=snap.table_count or 0,
            total_records=snap.total_records or 0,
            created_by=snap.created_by,
            created_at=snap.created_at,
            restored_count=snap.restored_count,
            last_restored_at=snap.last_restored_at,
            last_restored_by=snap.last_restored_by,
            is_scheduled=snap.is_scheduled,
            schedule_id=snap.schedule_id,
            status=snap.status,
            error_message=snap.error_message,
        )

    # ----------------------------------------------------------- delete
    def delete_snapshot(
        self,
        snapshot_id: str,
        user: str,
        date_str: Optional[str] = None,
    ) -> DeleteSnapshotResponse:
        """Delete a snapshot directory from disk."""
        try:
            snap = find_snapshot(
                self.backup_path, snapshot_id, self.BACKUP_FILENAME, date_str=date_str
            )
            if not snap:
                return DeleteSnapshotResponse(
                    success=False,
                    message=f"Snapshot {snapshot_id} not found",
                    deleted_file=False,
                )

            snapshot_dir = snap.metadata_path.parent
            shutil.rmtree(snapshot_dir)

            # Try to remove the parent date dir if empty
            try:
                snapshot_dir.parent.rmdir()
            except OSError:
                pass

            logger.info(f"Snapshot {snapshot_id} deleted by {user}")

            return DeleteSnapshotResponse(
                success=True,
                message=f"Snapshot {snapshot_id} deleted successfully",
                deleted_file=True,
            )

        except Exception as e:
            logger.error(f"Error deleting snapshot {snapshot_id}: {e}")
            return DeleteSnapshotResponse(
                success=False,
                message=f"Error deleting snapshot: {str(e)}",
                deleted_file=False,
            )

    # ----------------------------------------------------------- compare
    def compare_snapshots(
        self,
        snapshot_id_1: str,
        snapshot_id_2: str,
    ) -> Optional[SnapshotComparison]:
        snap1 = find_snapshot(self.backup_path, snapshot_id_1, self.BACKUP_FILENAME)
        snap2 = find_snapshot(self.backup_path, snapshot_id_2, self.BACKUP_FILENAME)

        if not snap1 or not snap2:
            return None

        size_diff = snap2.file_size - snap1.file_size
        record_diff = (snap2.total_records or 0) - (snap1.total_records or 0)
        table_diff = (snap2.table_count or 0) - (snap1.table_count or 0)
        time_diff = (snap2.created_at - snap1.created_at).total_seconds() / 3600

        def _to_info(s: DiskSnapshotMeta) -> SnapshotInfo:
            return SnapshotInfo(
                id=s.snapshot_id,
                name=s.name,
                description=s.description,
                file_size=s.file_size,
                created_by=s.created_by,
                created_at=s.created_at,
                status=s.status,
                is_scheduled=s.is_scheduled,
                restored_count=s.restored_count,
            )

        return SnapshotComparison(
            snapshot_1=_to_info(snap1),
            snapshot_2=_to_info(snap2),
            size_diff=size_diff,
            record_diff=record_diff,
            table_diff=table_diff,
            alembic_version_match=(snap1.alembic_version == snap2.alembic_version),
            created_time_diff_hours=time_diff,
        )

    # ----------------------------------------------------------- job status
    STALE_JOB_TIMEOUT_SECONDS = 300  # 5 minutes

    async def get_job_status(
        self,
        db: AsyncSession,
        job_id: str,
    ) -> Optional[JobStatusResponse]:
        job = await db.get(ProcessingJob, job_id)
        if not job:
            return None

        status = job.status
        error_message = job.error_message

        # Detect stale jobs: if pending/running for too long, the Celery task
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


# Create singleton instance
snapshot_service = PostgresSnapshotService()
