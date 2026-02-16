"""PostgreSQL snapshot service.

Provides core snapshot operations including create, restore, list, delete, and compare.
"""

import asyncio
import json
import os
import uuid
import fcntl
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from sqlalchemy import select, func, text, desc
from sqlalchemy.ext.asyncio import AsyncSession

from server.config.postgres import get_db_session_context
from server.devdata.snapshot_models import (
    PostgresSnapshot,
    SnapshotSchedule,
    CreateSnapshotResponse,
    RestoreSnapshotResponse,
    SnapshotInfo,
    SnapshotDetail,
    SnapshotListResponse,
    SnapshotComparison,
    DeleteSnapshotResponse,
    JobStatusResponse,
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
    """Service for managing PostgreSQL snapshots."""

    def __init__(self):
        """Initialize the snapshot service."""
        self.settings = get_settings()
        self.backup_path = self.settings.postgres_backup_path
        self.handler = PostgresBackupHandler(self.settings.postgres_url)
        self.lock_file_path = self.backup_path / ".locks" / "snapshot_operation.lock"
        self.lock_file = None

    async def acquire_operation_lock(self, operation: str, timeout: int = 5) -> bool:
        """Acquire a lock for snapshot operations to prevent concurrent execution.

        Args:
            operation: Type of operation ('create' or 'restore')
            timeout: Maximum seconds to wait for lock

        Returns:
            True if lock acquired, False if another operation is running
        """
        try:
            # Ensure lock directory exists
            self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Open or create lock file
            self.lock_file = open(self.lock_file_path, 'w')

            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Write lock information
            lock_info = {
                "operation": operation,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid()
            }
            json.dump(lock_info, self.lock_file)
            self.lock_file.flush()

            logger.info(f"Acquired lock for {operation} operation")
            return True

        except BlockingIOError:
            # Lock is held by another process
            logger.warning(f"Cannot acquire lock - another snapshot operation is running")
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
        """Release the operation lock."""
        try:
            if self.lock_file:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                self.lock_file = None

                # Try to remove the lock file
                try:
                    self.lock_file_path.unlink()
                except:
                    pass

                logger.info("Released operation lock")
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")

    async def check_operation_status(self) -> Optional[Dict[str, Any]]:
        """Check if a snapshot operation is currently running.

        Returns:
            Lock information if an operation is running, None otherwise
        """
        try:
            if not self.lock_file_path.exists():
                return None

            # Try to read the lock file
            with open(self.lock_file_path, 'r') as f:
                # Try to acquire shared lock (to check if file is locked)
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    # If we can get the lock, no operation is running
                    return None
                except BlockingIOError:
                    # File is locked, operation is running
                    f.seek(0)
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error checking operation status: {e}")
            return None

    async def generate_snapshot_id(self, db: AsyncSession) -> str:
        """Generate a unique snapshot ID in SNAP-YYYY-XXXX format.

        Args:
            db: Database session

        Returns:
            Generated snapshot ID
        """
        current_year = datetime.now(timezone.utc).year

        # Get the highest sequence number for the current year
        result = await db.execute(
            select(func.max(PostgresSnapshot.id))
            .where(PostgresSnapshot.id.like(f"SNAP-{current_year}-%"))
        )
        max_id = result.scalar()

        if max_id:
            # Extract sequence number and increment
            sequence = int(max_id.split('-')[-1]) + 1
        else:
            sequence = 1

        return f"SNAP-{current_year}-{sequence:04d}"

    async def get_alembic_version(self, db: AsyncSession) -> str:
        """Get the current Alembic migration version.

        Args:
            db: Database session

        Returns:
            Current Alembic revision ID
        """
        result = await db.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        )
        row = result.first()
        return row[0] if row else "unknown"

    async def get_database_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get database statistics for the snapshot.

        Args:
            db: Database session

        Returns:
            Dictionary with table_count and total_records
        """
        # Count tables (excluding system tables and alembic)
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

        # Get total record count across all tables
        # This is an approximation using pg_stat_user_tables
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
            "total_records": int(total_records)
        }

    async def create_snapshot(
        self,
        db: AsyncSession,
        job_id: str,
        name: str,
        description: Optional[str],
        user: str,
        is_scheduled: bool = False,
        schedule_id: Optional[str] = None
    ) -> None:
        """Create a new PostgreSQL backup snapshot (runs in background).

        Args:
            db: Database session
            job_id: Job ID for tracking
            name: Snapshot name
            description: Optional description
            user: User creating the snapshot
            is_scheduled: Whether this is a scheduled snapshot
            schedule_id: Schedule ID if scheduled
        """
        tracker = SnapshotJobTracker(db)
        snapshot_id = None
        lock_acquired = False

        try:
            # Try to acquire operation lock
            lock_acquired = await self.acquire_operation_lock("create")
            if not lock_acquired:
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Another snapshot operation is in progress",
                    error_message="Cannot create snapshot while another operation is running"
                )
                return
            # Update job status
            await tracker.update_progress(
                job_id=job_id,
                status="running",
                progress_percent=5,
                current_step="Initializing snapshot..."
            )

            # Generate snapshot ID
            snapshot_id = await self.generate_snapshot_id(db)
            logger.info(f"Creating snapshot {snapshot_id} for user {user}")

            # Get Alembic version
            await tracker.update_progress(
                job_id=job_id,
                progress_percent=10,
                current_step="Checking database version..."
            )
            alembic_version = await self.get_alembic_version(db)

            # Get database statistics
            await tracker.update_progress(
                job_id=job_id,
                progress_percent=15,
                current_step="Gathering database statistics..."
            )
            stats = await self.get_database_stats(db)

            # Create snapshot directory
            snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            snapshot_dir = self.backup_path / snapshot_date / snapshot_id
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            # Define backup file path
            backup_file = snapshot_dir / "backup.dump"

            # Create snapshot record with pending status
            snapshot = PostgresSnapshot(
                id=snapshot_id,
                name=name,
                description=description,
                file_path=str(backup_file),
                file_size=0,  # Will be updated after backup
                alembic_version=alembic_version,
                table_count=stats["table_count"],
                total_records=stats["total_records"],
                created_by=user,
                created_at=datetime.now(timezone.utc),
                restored_count=0,
                is_scheduled=is_scheduled,
                schedule_id=schedule_id,
                status="in_progress"
            )
            db.add(snapshot)
            await db.commit()

            # Execute pg_dump
            async def progress_callback(step: str, percent: int):
                # Map pg_dump progress to overall progress (20-90%)
                overall_percent = 20 + int(percent * 0.7)
                await tracker.update_progress(
                    job_id=job_id,
                    progress_percent=overall_percent,
                    current_step=step
                )

            # Use parallel jobs for better performance
            parallel_jobs = getattr(self.settings, 'postgres_backup_parallel_jobs', 4)

            result = await self.handler.execute_pg_dump(
                output_path=backup_file,
                compress=self.settings.postgres_backup_compression,
                parallel_jobs=parallel_jobs,
                progress_callback=progress_callback
            )

            if result.success:
                # Calculate checksum
                await tracker.update_progress(
                    job_id=job_id,
                    progress_percent=92,
                    current_step="Calculating checksum..."
                )
                checksum = await self.handler.calculate_checksum(result.output_file)

                # Save metadata
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
                    "compressed": self.settings.postgres_backup_compression
                }
                metadata_file = snapshot_dir / "metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)

                # Save checksum file
                checksum_file = snapshot_dir / "checksum.sha256"
                with open(checksum_file, 'w') as f:
                    f.write(f"{checksum}  {result.output_file.name}\n")

                # Update snapshot record
                snapshot.file_path = str(result.output_file)
                snapshot.file_size = result.file_size
                snapshot.checksum = checksum
                snapshot.status = "completed"
                await db.commit()

                # Update job as completed
                await tracker.update_progress(
                    job_id=job_id,
                    status="completed",
                    progress_percent=100,
                    current_step="Snapshot created successfully"
                )

                logger.info(f"Snapshot {snapshot_id} created successfully ({result.file_size / 1024 / 1024:.2f} MB)")
            else:
                # Update snapshot as failed
                snapshot.status = "failed"
                snapshot.error_message = result.stderr
                await db.commit()

                # Update job as failed
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Backup failed",
                    error_message=result.stderr
                )

                logger.error(f"Failed to create snapshot {snapshot_id}: {result.stderr}")

        except Exception as e:
            logger.error(f"Error creating snapshot: {e}")

            # Update snapshot as failed if it exists
            if snapshot_id:
                snapshot_record = await db.get(PostgresSnapshot, snapshot_id)
                if snapshot_record:
                    snapshot_record.status = "failed"
                    snapshot_record.error_message = str(e)
                    await db.commit()

            # Update job as failed
            await tracker.update_progress(
                job_id=job_id,
                status="failed",
                current_step="Unexpected error",
                error_message=str(e)
            )
        finally:
            # Release lock if acquired
            if lock_acquired:
                self.release_operation_lock()

    async def restore_snapshot(
        self,
        db: AsyncSession,
        job_id: str,
        snapshot_id: str,
        user: str,
        create_pre_restore_backup: bool = True,
        force: bool = False
    ) -> Optional[str]:
        """Restore database from a snapshot (runs in background).

        Args:
            db: Database session
            job_id: Job ID for tracking
            snapshot_id: Snapshot to restore
            user: User performing restore
            create_pre_restore_backup: Whether to create a backup before restoring
            force: Force restore even with version mismatch

        Returns:
            Pre-restore snapshot ID if created, None otherwise
        """
        tracker = SnapshotJobTracker(db)
        pre_restore_snapshot_id = None
        lock_acquired = False

        try:
            # Try to acquire operation lock
            lock_acquired = await self.acquire_operation_lock("restore")
            if not lock_acquired:
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Another snapshot operation is in progress",
                    error_message="Cannot restore while another operation is running"
                )
                return None
            # Update job status
            await tracker.update_progress(
                job_id=job_id,
                status="running",
                progress_percent=5,
                current_step="Loading snapshot information..."
            )

            # Get snapshot
            snapshot = await db.get(PostgresSnapshot, snapshot_id)
            if not snapshot:
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Snapshot not found",
                    error_message=f"Snapshot {snapshot_id} not found"
                )
                return None

            # Check if backup file exists
            backup_path = Path(snapshot.file_path)
            if not backup_path.exists():
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Backup file not found",
                    error_message=f"Backup file not found: {backup_path}"
                )
                return None

            # Check Alembic version compatibility
            current_version = await self.get_alembic_version(db)
            if current_version != snapshot.alembic_version and not force:
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Version mismatch",
                    error_message=f"Alembic version mismatch: current={current_version}, snapshot={snapshot.alembic_version}"
                )
                return None

            # Create pre-restore backup if requested
            if create_pre_restore_backup:
                await tracker.update_progress(
                    job_id=job_id,
                    progress_percent=10,
                    current_step="Creating pre-restore backup..."
                )

                # Create a new job for the pre-restore backup
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

                # Create the pre-restore backup
                await self.create_snapshot(
                    db=db,
                    job_id=pre_restore_job_id,
                    name=f"Pre-restore backup for {snapshot_id}",
                    description=f"Automatic backup before restoring {snapshot.name}",
                    user=user,
                    is_scheduled=False
                )

                # Wait for pre-restore backup to complete
                while True:
                    await asyncio.sleep(2)
                    pre_restore_job = await db.get(ProcessingJob, pre_restore_job_id)
                    if pre_restore_job.status == "completed":
                        # Get the created snapshot ID
                        pre_restore_snapshot = await db.execute(
                            select(PostgresSnapshot)
                            .where(PostgresSnapshot.created_by == user)
                            .where(PostgresSnapshot.name.like("Pre-restore backup%"))
                            .order_by(desc(PostgresSnapshot.created_at))
                            .limit(1)
                        )
                        pre_restore_record = pre_restore_snapshot.scalar_one_or_none()
                        if pre_restore_record:
                            pre_restore_snapshot_id = pre_restore_record.id
                        break
                    elif pre_restore_job.status == "failed":
                        await tracker.update_progress(
                            job_id=job_id,
                            status="failed",
                            current_step="Pre-restore backup failed",
                            error_message=pre_restore_job.error_message
                        )
                        return None

            # Execute pg_restore
            await tracker.update_progress(
                job_id=job_id,
                progress_percent=30,
                current_step="Starting database restore..."
            )

            async def progress_callback(step: str, percent: int):
                # Map pg_restore progress to overall progress (30-95%)
                overall_percent = 30 + int(percent * 0.65)
                await tracker.update_progress(
                    job_id=job_id,
                    progress_percent=overall_percent,
                    current_step=step
                )

            # Use parallel jobs for better performance
            parallel_jobs = getattr(self.settings, 'postgres_backup_parallel_jobs', 4)

            result = await self.handler.execute_pg_restore(
                backup_path=backup_path,
                clean=True,
                parallel_jobs=parallel_jobs,
                progress_callback=progress_callback
            )

            if result.success:
                # Update snapshot restore tracking
                snapshot.restored_count += 1
                snapshot.last_restored_at = datetime.now(timezone.utc)
                snapshot.last_restored_by = user
                await db.commit()

                # Update job as completed
                await tracker.update_progress(
                    job_id=job_id,
                    status="completed",
                    progress_percent=100,
                    current_step="Restore completed successfully"
                )

                logger.info(f"Successfully restored snapshot {snapshot_id} by {user}")
                return pre_restore_snapshot_id
            else:
                # Update job as failed
                await tracker.update_progress(
                    job_id=job_id,
                    status="failed",
                    current_step="Restore failed",
                    error_message=result.stderr
                )

                logger.error(f"Failed to restore snapshot {snapshot_id}: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Error restoring snapshot: {e}")

            # Update job as failed
            await tracker.update_progress(
                job_id=job_id,
                status="failed",
                current_step="Unexpected error",
                error_message=str(e)
            )
            return None
        finally:
            # Release lock if acquired
            if lock_acquired:
                self.release_operation_lock()

    async def list_snapshots(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        filter_scheduled: Optional[bool] = None
    ) -> SnapshotListResponse:
        """List available snapshots with pagination.

        Args:
            db: Database session
            page: Page number (1-based)
            page_size: Number of items per page
            filter_scheduled: Optional filter for scheduled snapshots

        Returns:
            Paginated snapshot list
        """
        # Build query
        query = select(PostgresSnapshot).order_by(desc(PostgresSnapshot.created_at))

        if filter_scheduled is not None:
            query = query.where(PostgresSnapshot.is_scheduled == filter_scheduled)

        # Get total count
        count_query = select(func.count()).select_from(PostgresSnapshot)
        if filter_scheduled is not None:
            count_query = count_query.where(PostgresSnapshot.is_scheduled == filter_scheduled)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.limit(page_size).offset(offset)

        # Execute query
        result = await db.execute(query)
        snapshots = result.scalars().all()

        # Convert to response models
        snapshot_infos = [
            SnapshotInfo(
                id=s.id,
                name=s.name,
                description=s.description,
                file_size=s.file_size,
                created_by=s.created_by,
                created_at=s.created_at,
                status=s.status,
                is_scheduled=s.is_scheduled,
                restored_count=s.restored_count
            )
            for s in snapshots
        ]

        return SnapshotListResponse(
            snapshots=snapshot_infos,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + len(snapshots) < total)
        )

    async def get_snapshot_detail(
        self,
        db: AsyncSession,
        snapshot_id: str
    ) -> Optional[SnapshotDetail]:
        """Get detailed information about a snapshot.

        Args:
            db: Database session
            snapshot_id: Snapshot ID

        Returns:
            Snapshot details or None if not found
        """
        snapshot = await db.get(PostgresSnapshot, snapshot_id)
        if not snapshot:
            return None

        return SnapshotDetail(
            id=snapshot.id,
            name=snapshot.name,
            description=snapshot.description,
            file_path=snapshot.file_path,
            file_size=snapshot.file_size,
            checksum=snapshot.checksum,
            alembic_version=snapshot.alembic_version,
            table_count=snapshot.table_count,
            total_records=snapshot.total_records,
            created_by=snapshot.created_by,
            created_at=snapshot.created_at,
            restored_count=snapshot.restored_count,
            last_restored_at=snapshot.last_restored_at,
            last_restored_by=snapshot.last_restored_by,
            is_scheduled=snapshot.is_scheduled,
            schedule_id=snapshot.schedule_id,
            status=snapshot.status,
            error_message=snapshot.error_message
        )

    async def delete_snapshot(
        self,
        db: AsyncSession,
        snapshot_id: str,
        user: str
    ) -> DeleteSnapshotResponse:
        """Delete a snapshot and its backup file.

        Args:
            db: Database session
            snapshot_id: Snapshot to delete
            user: User performing deletion

        Returns:
            Deletion result
        """
        try:
            # Get snapshot
            snapshot = await db.get(PostgresSnapshot, snapshot_id)
            if not snapshot:
                return DeleteSnapshotResponse(
                    success=False,
                    message=f"Snapshot {snapshot_id} not found",
                    deleted_file=False
                )

            # Delete backup file and directory
            backup_path = Path(snapshot.file_path)
            deleted_file = False

            if backup_path.exists():
                # Backup can be a single file or a pg_dump directory format archive.
                if backup_path.is_dir():
                    shutil.rmtree(backup_path)
                else:
                    backup_path.unlink()
                deleted_file = True

                # Delete metadata and checksum files if they exist
                snapshot_dir = backup_path.parent
                metadata_file = snapshot_dir / "metadata.json"
                checksum_file = snapshot_dir / "checksum.sha256"

                if metadata_file.exists():
                    metadata_file.unlink()
                if checksum_file.exists():
                    checksum_file.unlink()

                # Try to remove the directory if empty
                try:
                    snapshot_dir.rmdir()
                except OSError:
                    pass  # Directory not empty, that's fine

            # Delete database record
            await db.delete(snapshot)
            await db.commit()

            logger.info(f"Snapshot {snapshot_id} deleted by {user}")

            return DeleteSnapshotResponse(
                success=True,
                message=f"Snapshot {snapshot_id} deleted successfully",
                deleted_file=deleted_file
            )

        except Exception as e:
            logger.error(f"Error deleting snapshot {snapshot_id}: {e}")
            return DeleteSnapshotResponse(
                success=False,
                message=f"Error deleting snapshot: {str(e)}",
                deleted_file=False
            )

    async def compare_snapshots(
        self,
        db: AsyncSession,
        snapshot_id_1: str,
        snapshot_id_2: str
    ) -> Optional[SnapshotComparison]:
        """Compare two snapshots.

        Args:
            db: Database session
            snapshot_id_1: First snapshot ID
            snapshot_id_2: Second snapshot ID

        Returns:
            Comparison result or None if snapshots not found
        """
        # Get both snapshots
        snapshot1 = await db.get(PostgresSnapshot, snapshot_id_1)
        snapshot2 = await db.get(PostgresSnapshot, snapshot_id_2)

        if not snapshot1 or not snapshot2:
            return None

        # Calculate differences
        size_diff = snapshot2.file_size - snapshot1.file_size
        record_diff = snapshot2.total_records - snapshot1.total_records
        table_diff = snapshot2.table_count - snapshot1.table_count
        time_diff = (snapshot2.created_at - snapshot1.created_at).total_seconds() / 3600

        return SnapshotComparison(
            snapshot_1=SnapshotInfo(
                id=snapshot1.id,
                name=snapshot1.name,
                description=snapshot1.description,
                file_size=snapshot1.file_size,
                created_by=snapshot1.created_by,
                created_at=snapshot1.created_at,
                status=snapshot1.status,
                is_scheduled=snapshot1.is_scheduled,
                restored_count=snapshot1.restored_count
            ),
            snapshot_2=SnapshotInfo(
                id=snapshot2.id,
                name=snapshot2.name,
                description=snapshot2.description,
                file_size=snapshot2.file_size,
                created_by=snapshot2.created_by,
                created_at=snapshot2.created_at,
                status=snapshot2.status,
                is_scheduled=snapshot2.is_scheduled,
                restored_count=snapshot2.restored_count
            ),
            size_diff=size_diff,
            record_diff=record_diff,
            table_diff=table_diff,
            alembic_version_match=(snapshot1.alembic_version == snapshot2.alembic_version),
            created_time_diff_hours=time_diff
        )

    async def get_job_status(
        self,
        db: AsyncSession,
        job_id: str
    ) -> Optional[JobStatusResponse]:
        """Get status of a snapshot-related job.

        Args:
            db: Database session
            job_id: Job ID

        Returns:
            Job status or None if not found
        """
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
            error_message=job.error_message
        )


# Create singleton instance
snapshot_service = PostgresSnapshotService()
