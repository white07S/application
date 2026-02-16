#!/usr/bin/env python3
"""
PostgreSQL Snapshot Management CLI

Usage:
    python snapshot_cli.py list                          # List all snapshots
    python snapshot_cli.py create --name "Backup Name"   # Create a new snapshot
    python snapshot_cli.py restore --id SNAP-2024-0001  # Restore a snapshot
    python snapshot_cli.py delete --id SNAP-2024-0001   # Delete a snapshot
    python snapshot_cli.py status                        # Check if operation is running
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.config.postgres import get_db_session_context
from server.devdata.snapshot_service import snapshot_service
from server.settings import get_settings
from server.logging_config import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(name=__name__)


async def list_snapshots(args):
    """List all available snapshots."""
    async with get_db_session_context() as db:
        response = await snapshot_service.list_snapshots(
            db, page=1, page_size=100
        )

        if not response.snapshots:
            print("No snapshots found.")
            return

        print(f"\nFound {response.total} snapshot(s):\n")
        print("-" * 100)
        print(f"{'ID':<20} {'Name':<30} {'Size':<12} {'Created':<20} {'Status':<10} {'Restored'}")
        print("-" * 100)

        for snap in response.snapshots:
            size_mb = snap.file_size / (1024 * 1024)
            created = datetime.fromisoformat(snap.created_at.isoformat()).strftime('%Y-%m-%d %H:%M')
            print(f"{snap.id:<20} {snap.name[:29]:<30} {size_mb:>10.2f}MB {created:<20} {snap.status:<10} {snap.restored_count}x")

        print("-" * 100)


async def create_snapshot(args):
    """Create a new snapshot."""
    # Check if another operation is running
    status = await snapshot_service.check_operation_status()
    if status:
        print(f"❌ Cannot create snapshot: {status['operation']} operation already running")
        print(f"   Started at: {status['started_at']}")
        return

    print(f"Creating snapshot: {args.name}")
    if args.description:
        print(f"Description: {args.description}")

    # Create job ID for tracking
    import uuid
    job_id = str(uuid.uuid4())

    async with get_db_session_context() as db:
        # Add a simple job record for tracking
        from server.jobs import ProcessingJob
        job = ProcessingJob(
            id=job_id,
            job_type="snapshot_creation",
            batch_id=0,
            upload_id="CLI",
            status="pending",
            progress_percent=0,
            current_step="Initializing...",
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()

        # Start snapshot creation in background
        print("Starting snapshot creation...")

        # Create task for snapshot
        task = asyncio.create_task(
            snapshot_service.create_snapshot(
                db=db,
                job_id=job_id,
                name=args.name,
                description=args.description,
                user=args.user or "cli_user",
                is_scheduled=False
            )
        )

        # Monitor progress
        prev_percent = 0
        while not task.done():
            await asyncio.sleep(2)

            # Check job status
            job = await db.get(ProcessingJob, job_id)
            if job:
                if job.progress_percent != prev_percent:
                    print(f"Progress: {job.progress_percent}% - {job.current_step}")
                    prev_percent = job.progress_percent

                if job.status == "completed":
                    print("✅ Snapshot created successfully!")
                    break
                elif job.status == "failed":
                    print(f"❌ Snapshot creation failed: {job.error_message}")
                    break

        await task


async def restore_snapshot(args):
    """Restore database from a snapshot."""
    # Check if another operation is running
    status = await snapshot_service.check_operation_status()
    if status:
        print(f"❌ Cannot restore snapshot: {status['operation']} operation already running")
        print(f"   Started at: {status['started_at']}")
        return

    async with get_db_session_context() as db:
        # Get snapshot details
        snapshot = await snapshot_service.get_snapshot_detail(db, args.id)
        if not snapshot:
            print(f"❌ Snapshot {args.id} not found")
            return

        print(f"Restoring from snapshot: {snapshot.name}")
        print(f"Created: {snapshot.created_at}")
        print(f"Size: {snapshot.file_size / (1024 * 1024):.2f} MB")

        if not args.skip_confirm:
            response = input("\n⚠️  WARNING: This will replace the current database! Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Restore cancelled.")
                return

        # Create job for tracking
        import uuid
        job_id = str(uuid.uuid4())

        from server.jobs import ProcessingJob
        job = ProcessingJob(
            id=job_id,
            job_type="snapshot_restore",
            batch_id=0,
            upload_id=args.id,
            status="pending",
            progress_percent=0,
            current_step="Initializing restore...",
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()

        print("Starting restore...")

        # Start restore in background
        task = asyncio.create_task(
            snapshot_service.restore_snapshot(
                db=db,
                job_id=job_id,
                snapshot_id=args.id,
                user=args.user or "cli_user",
                create_pre_restore_backup=not args.skip_backup,
                force=args.force
            )
        )

        # Monitor progress
        prev_percent = 0
        while not task.done():
            await asyncio.sleep(2)

            job = await db.get(ProcessingJob, job_id)
            if job:
                if job.progress_percent != prev_percent:
                    print(f"Progress: {job.progress_percent}% - {job.current_step}")
                    prev_percent = job.progress_percent

                if job.status == "completed":
                    print("✅ Database restored successfully!")
                    print("\n⚠️  IMPORTANT: You may need to restart the application and re-run data ingestion:")
                    print("   1. Restart the server to reconnect to the restored database")
                    print("   2. Run context provider ingestion if needed")
                    print("   3. Run control ingestion if needed")
                    print("   4. Re-index Qdrant collections if needed")
                    break
                elif job.status == "failed":
                    print(f"❌ Restore failed: {job.error_message}")
                    break

        await task


async def delete_snapshot(args):
    """Delete a snapshot."""
    async with get_db_session_context() as db:
        snapshot = await snapshot_service.get_snapshot_detail(db, args.id)
        if not snapshot:
            print(f"❌ Snapshot {args.id} not found")
            return

        print(f"Deleting snapshot: {snapshot.name}")

        if not args.skip_confirm:
            response = input("Are you sure? (yes/no): ")
            if response.lower() != 'yes':
                print("Delete cancelled.")
                return

        result = await snapshot_service.delete_snapshot(
            db, args.id, args.user or "cli_user"
        )

        if result.success:
            print(f"✅ {result.message}")
            if result.deleted_file:
                print("   Backup file deleted.")
        else:
            print(f"❌ {result.message}")


async def check_status(args):
    """Check if a snapshot operation is currently running."""
    status = await snapshot_service.check_operation_status()

    if status:
        print(f"🔄 Operation in progress: {status['operation']}")
        print(f"   Started at: {status['started_at']}")
        print(f"   Process ID: {status.get('pid', 'unknown')}")
    else:
        print("✅ No snapshot operations are currently running.")

    # Also check for any pending/running jobs
    async with get_db_session_context() as db:
        from sqlalchemy import select
        from server.jobs import ProcessingJob

        result = await db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.job_type.in_(["snapshot_creation", "snapshot_restore"]))
            .where(ProcessingJob.status.in_(["pending", "running"]))
        )
        jobs = result.scalars().all()

        if jobs:
            print("\nActive jobs:")
            for job in jobs:
                print(f"  - {job.id}: {job.job_type} - {job.status} ({job.progress_percent}%)")
                print(f"    {job.current_step}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PostgreSQL Snapshot Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # List command
    list_parser = subparsers.add_parser('list', help='List all snapshots')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new snapshot')
    create_parser.add_argument('--name', required=True, help='Snapshot name')
    create_parser.add_argument('--description', help='Snapshot description')
    create_parser.add_argument('--user', default='cli_user', help='User creating the snapshot')

    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from a snapshot')
    restore_parser.add_argument('--id', required=True, help='Snapshot ID (e.g., SNAP-2024-0001)')
    restore_parser.add_argument('--skip-backup', action='store_true', help='Skip pre-restore backup')
    restore_parser.add_argument('--skip-confirm', action='store_true', help='Skip confirmation prompt')
    restore_parser.add_argument('--force', action='store_true', help='Force restore even with version mismatch')
    restore_parser.add_argument('--user', default='cli_user', help='User performing the restore')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a snapshot')
    delete_parser.add_argument('--id', required=True, help='Snapshot ID')
    delete_parser.add_argument('--skip-confirm', action='store_true', help='Skip confirmation prompt')
    delete_parser.add_argument('--user', default='cli_user', help='User deleting the snapshot')

    # Status command
    status_parser = subparsers.add_parser('status', help='Check operation status')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Run the appropriate command
    if args.command == 'list':
        asyncio.run(list_snapshots(args))
    elif args.command == 'create':
        asyncio.run(create_snapshot(args))
    elif args.command == 'restore':
        asyncio.run(restore_snapshot(args))
    elif args.command == 'delete':
        asyncio.run(delete_snapshot(args))
    elif args.command == 'status':
        asyncio.run(check_status(args))


if __name__ == '__main__':
    main()