#!/usr/bin/env python3
"""
Snapshot Management CLI — PostgreSQL & Qdrant

Usage:
    python snapshot_cli.py list                                          # List Postgres snapshots
    python snapshot_cli.py create --name "Backup Name"                   # Create Postgres snapshot
    python snapshot_cli.py restore --id SNAP-2024-0001                   # Restore Postgres snapshot
    python snapshot_cli.py delete --id SNAP-2024-0001                    # Delete Postgres snapshot
    python snapshot_cli.py status                                        # Check Postgres operation status

    python snapshot_cli.py --type qdrant list                            # List Qdrant snapshots
    python snapshot_cli.py --type qdrant create --name "Backup" --collection nfr_connect_controls
    python snapshot_cli.py --type qdrant restore --id QSNAP-2026-0001    # Restore Qdrant snapshot
    python snapshot_cli.py --type qdrant delete --id QSNAP-2026-0001     # Delete Qdrant snapshot
    python snapshot_cli.py --type qdrant status                          # Check Qdrant operation status
    python snapshot_cli.py --type qdrant collections                     # List Qdrant collections
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


# ======================================================================
# PostgreSQL commands
# ======================================================================

async def pg_list_snapshots(args):
    """List all available Postgres snapshots."""
    async with get_db_session_context() as db:
        response = await snapshot_service.list_snapshots(
            db, page=1, page_size=100
        )

        if not response.snapshots:
            print("No PostgreSQL snapshots found.")
            return

        print(f"\nFound {response.total} PostgreSQL snapshot(s):\n")
        print("-" * 100)
        print(f"{'ID':<20} {'Name':<30} {'Size':<12} {'Created':<20} {'Status':<10} {'Restored'}")
        print("-" * 100)

        for snap in response.snapshots:
            size_mb = snap.file_size / (1024 * 1024)
            created = datetime.fromisoformat(snap.created_at.isoformat()).strftime('%Y-%m-%d %H:%M')
            print(f"{snap.id:<20} {snap.name[:29]:<30} {size_mb:>10.2f}MB {created:<20} {snap.status:<10} {snap.restored_count}x")

        print("-" * 100)


async def pg_create_snapshot(args):
    """Create a new Postgres snapshot."""
    status = await snapshot_service.check_operation_status()
    if status:
        print(f"Cannot create snapshot: {status['operation']} operation already running")
        print(f"   Started at: {status['started_at']}")
        return

    print(f"Creating PostgreSQL snapshot: {args.name}")
    if args.description:
        print(f"Description: {args.description}")

    import uuid
    job_id = str(uuid.uuid4())

    async with get_db_session_context() as db:
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

        print("Starting snapshot creation...")

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

        prev_percent = 0
        while not task.done():
            await asyncio.sleep(2)
            job = await db.get(ProcessingJob, job_id)
            if job:
                if job.progress_percent != prev_percent:
                    print(f"Progress: {job.progress_percent}% - {job.current_step}")
                    prev_percent = job.progress_percent
                if job.status == "completed":
                    print("Snapshot created successfully!")
                    break
                elif job.status == "failed":
                    print(f"Snapshot creation failed: {job.error_message}")
                    break

        await task


async def pg_restore_snapshot(args):
    """Restore database from a Postgres snapshot."""
    status = await snapshot_service.check_operation_status()
    if status:
        print(f"Cannot restore snapshot: {status['operation']} operation already running")
        print(f"   Started at: {status['started_at']}")
        return

    async with get_db_session_context() as db:
        snapshot = await snapshot_service.get_snapshot_detail(db, args.id)
        if not snapshot:
            print(f"Snapshot {args.id} not found")
            return

        print(f"Restoring from snapshot: {snapshot.name}")
        print(f"Created: {snapshot.created_at}")
        print(f"Size: {snapshot.file_size / (1024 * 1024):.2f} MB")

        if not args.skip_confirm:
            response = input("\nWARNING: This will replace the current database! Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Restore cancelled.")
                return

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

        prev_percent = 0
        while not task.done():
            await asyncio.sleep(2)
            job = await db.get(ProcessingJob, job_id)
            if job:
                if job.progress_percent != prev_percent:
                    print(f"Progress: {job.progress_percent}% - {job.current_step}")
                    prev_percent = job.progress_percent
                if job.status == "completed":
                    print("Database restored successfully!")
                    print("\nIMPORTANT: You may need to restart the application and re-run data ingestion:")
                    print("   1. Restart the server to reconnect to the restored database")
                    print("   2. Run context provider ingestion if needed")
                    print("   3. Run control ingestion if needed")
                    print("   4. Re-index Qdrant collections if needed")
                    break
                elif job.status == "failed":
                    print(f"Restore failed: {job.error_message}")
                    break

        await task


async def pg_delete_snapshot(args):
    """Delete a Postgres snapshot."""
    async with get_db_session_context() as db:
        snapshot = await snapshot_service.get_snapshot_detail(db, args.id)
        if not snapshot:
            print(f"Snapshot {args.id} not found")
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
            print(f"{result.message}")
            if result.deleted_file:
                print("   Backup file deleted.")
        else:
            print(f"Error: {result.message}")


async def pg_check_status(args):
    """Check if a Postgres snapshot operation is running."""
    status = await snapshot_service.check_operation_status()

    if status:
        print(f"PostgreSQL operation in progress: {status['operation']}")
        print(f"   Started at: {status['started_at']}")
        print(f"   Process ID: {status.get('pid', 'unknown')}")
    else:
        print("No PostgreSQL snapshot operations are currently running.")

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
            print("\nActive PostgreSQL jobs:")
            for job in jobs:
                print(f"  - {job.id}: {job.job_type} - {job.status} ({job.progress_percent}%)")
                print(f"    {job.current_step}")


# ======================================================================
# Qdrant commands
# ======================================================================

async def qdrant_list_snapshots(args):
    """List all available Qdrant snapshots."""
    from server.devdata.qdrant_snapshot_service import qdrant_snapshot_service

    async with get_db_session_context() as db:
        response = await qdrant_snapshot_service.list_snapshots(
            db, page=1, page_size=100,
            collection_name=getattr(args, 'collection', None),
        )

        if not response.snapshots:
            print("No Qdrant snapshots found.")
            return

        print(f"\nFound {response.total} Qdrant snapshot(s):\n")
        print("-" * 120)
        print(f"{'ID':<22} {'Name':<25} {'Collection':<25} {'Points':<10} {'Size':<12} {'Created':<20} {'Status':<10} {'Restored'}")
        print("-" * 120)

        for snap in response.snapshots:
            size_mb = snap.file_size / (1024 * 1024)
            created = datetime.fromisoformat(snap.created_at.isoformat()).strftime('%Y-%m-%d %H:%M')
            print(
                f"{snap.id:<22} {snap.name[:24]:<25} {snap.collection_name[:24]:<25} "
                f"{snap.points_count:<10} {size_mb:>10.2f}MB {created:<20} {snap.status:<10} {snap.restored_count}x"
            )

        print("-" * 120)


async def qdrant_create_snapshot(args):
    """Create a new Qdrant snapshot."""
    from server.devdata.qdrant_snapshot_service import qdrant_snapshot_service

    status = await qdrant_snapshot_service.check_operation_status()
    if status:
        print(f"Cannot create snapshot: {status['operation']} operation already running")
        print(f"   Started at: {status['started_at']}")
        return

    collection = args.collection or get_settings().qdrant_collection

    print(f"Creating Qdrant snapshot: {args.name}")
    print(f"Collection: {collection}")
    if args.description:
        print(f"Description: {args.description}")

    import uuid
    job_id = str(uuid.uuid4())

    async with get_db_session_context() as db:
        from server.jobs import ProcessingJob
        job = ProcessingJob(
            id=job_id,
            job_type="qdrant_snapshot_creation",
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

        print("Starting Qdrant snapshot creation...")

        task = asyncio.create_task(
            qdrant_snapshot_service.create_snapshot(
                db=db,
                job_id=job_id,
                name=args.name,
                description=args.description,
                user=args.user or "cli_user",
                collection_name=collection,
            )
        )

        prev_percent = 0
        while not task.done():
            await asyncio.sleep(2)
            job = await db.get(ProcessingJob, job_id)
            if job:
                if job.progress_percent != prev_percent:
                    print(f"Progress: {job.progress_percent}% - {job.current_step}")
                    prev_percent = job.progress_percent
                if job.status == "completed":
                    print("Qdrant snapshot created successfully!")
                    break
                elif job.status == "failed":
                    print(f"Qdrant snapshot creation failed: {job.error_message}")
                    break

        await task


async def qdrant_restore_snapshot(args):
    """Restore Qdrant collection from a snapshot."""
    from server.devdata.qdrant_snapshot_service import qdrant_snapshot_service

    status = await qdrant_snapshot_service.check_operation_status()
    if status:
        print(f"Cannot restore snapshot: {status['operation']} operation already running")
        print(f"   Started at: {status['started_at']}")
        return

    async with get_db_session_context() as db:
        snapshot = await qdrant_snapshot_service.get_snapshot_detail(db, args.id)
        if not snapshot:
            print(f"Snapshot {args.id} not found")
            return

        print(f"Restoring from Qdrant snapshot: {snapshot.name}")
        print(f"Collection: {snapshot.collection_name}")
        print(f"Points: {snapshot.points_count}")
        print(f"Size: {snapshot.file_size / (1024 * 1024):.2f} MB")

        if not args.skip_confirm:
            response = input("\nWARNING: This will replace the Qdrant collection data! Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Restore cancelled.")
                return

        import uuid
        job_id = str(uuid.uuid4())

        from server.jobs import ProcessingJob
        job = ProcessingJob(
            id=job_id,
            job_type="qdrant_snapshot_restore",
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

        print("Starting Qdrant restore...")

        task = asyncio.create_task(
            qdrant_snapshot_service.restore_snapshot(
                db=db,
                job_id=job_id,
                snapshot_id=args.id,
                user=args.user or "cli_user",
                force=args.force,
            )
        )

        prev_percent = 0
        while not task.done():
            await asyncio.sleep(2)
            job = await db.get(ProcessingJob, job_id)
            if job:
                if job.progress_percent != prev_percent:
                    print(f"Progress: {job.progress_percent}% - {job.current_step}")
                    prev_percent = job.progress_percent
                if job.status == "completed":
                    print("Qdrant collection restored successfully!")
                    break
                elif job.status == "failed":
                    print(f"Qdrant restore failed: {job.error_message}")
                    break

        await task


async def qdrant_delete_snapshot(args):
    """Delete a Qdrant snapshot."""
    from server.devdata.qdrant_snapshot_service import qdrant_snapshot_service

    async with get_db_session_context() as db:
        snapshot = await qdrant_snapshot_service.get_snapshot_detail(db, args.id)
        if not snapshot:
            print(f"Snapshot {args.id} not found")
            return

        print(f"Deleting Qdrant snapshot: {snapshot.name}")
        print(f"Collection: {snapshot.collection_name}")

        if not args.skip_confirm:
            response = input("Are you sure? (yes/no): ")
            if response.lower() != 'yes':
                print("Delete cancelled.")
                return

        result = await qdrant_snapshot_service.delete_snapshot(
            db, args.id, args.user or "cli_user"
        )

        if result.success:
            print(f"{result.message}")
            if result.deleted_file:
                print("   Backup file deleted.")
        else:
            print(f"Error: {result.message}")


async def qdrant_check_status(args):
    """Check if a Qdrant snapshot operation is running."""
    from server.devdata.qdrant_snapshot_service import qdrant_snapshot_service

    status = await qdrant_snapshot_service.check_operation_status()

    if status:
        print(f"Qdrant operation in progress: {status['operation']}")
        print(f"   Started at: {status['started_at']}")
        print(f"   Process ID: {status.get('pid', 'unknown')}")
    else:
        print("No Qdrant snapshot operations are currently running.")

    async with get_db_session_context() as db:
        from sqlalchemy import select
        from server.jobs import ProcessingJob

        result = await db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.job_type.in_(["qdrant_snapshot_creation", "qdrant_snapshot_restore"]))
            .where(ProcessingJob.status.in_(["pending", "running"]))
        )
        jobs = result.scalars().all()

        if jobs:
            print("\nActive Qdrant jobs:")
            for job in jobs:
                print(f"  - {job.id}: {job.job_type} - {job.status} ({job.progress_percent}%)")
                print(f"    {job.current_step}")


async def qdrant_list_collections(args):
    """List available Qdrant collections."""
    from server.devdata.qdrant_snapshot_service import qdrant_snapshot_service

    try:
        collections = await qdrant_snapshot_service.list_collections()
        if not collections:
            print("No Qdrant collections found.")
            return

        print(f"\nAvailable Qdrant collections ({len(collections)}):\n")
        for name in collections:
            print(f"  - {name}")
        print()
    except Exception as e:
        print(f"Error listing collections: {e}")


# ======================================================================
# Main
# ======================================================================

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Snapshot Management CLI (PostgreSQL & Qdrant)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--type', choices=['postgres', 'qdrant'], default='postgres',
        help='Snapshot type: postgres (default) or qdrant'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # List command
    list_parser = subparsers.add_parser('list', help='List all snapshots')
    list_parser.add_argument('--collection', help='(Qdrant only) Filter by collection name')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new snapshot')
    create_parser.add_argument('--name', required=True, help='Snapshot name')
    create_parser.add_argument('--description', help='Snapshot description')
    create_parser.add_argument('--user', default='cli_user', help='User creating the snapshot')
    create_parser.add_argument('--collection', help='(Qdrant only) Collection name to snapshot')

    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from a snapshot')
    restore_parser.add_argument('--id', required=True, help='Snapshot ID')
    restore_parser.add_argument('--skip-backup', action='store_true', help='(Postgres only) Skip pre-restore backup')
    restore_parser.add_argument('--skip-confirm', action='store_true', help='Skip confirmation prompt')
    restore_parser.add_argument('--force', action='store_true', help='Force restore')
    restore_parser.add_argument('--user', default='cli_user', help='User performing the restore')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a snapshot')
    delete_parser.add_argument('--id', required=True, help='Snapshot ID')
    delete_parser.add_argument('--skip-confirm', action='store_true', help='Skip confirmation prompt')
    delete_parser.add_argument('--user', default='cli_user', help='User deleting the snapshot')

    # Status command
    status_parser = subparsers.add_parser('status', help='Check operation status')

    # Collections command (Qdrant only)
    collections_parser = subparsers.add_parser('collections', help='(Qdrant only) List available collections')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to the correct handler based on --type
    if args.type == 'qdrant':
        dispatch = {
            'list': qdrant_list_snapshots,
            'create': qdrant_create_snapshot,
            'restore': qdrant_restore_snapshot,
            'delete': qdrant_delete_snapshot,
            'status': qdrant_check_status,
            'collections': qdrant_list_collections,
        }
    else:
        dispatch = {
            'list': pg_list_snapshots,
            'create': pg_create_snapshot,
            'restore': pg_restore_snapshot,
            'delete': pg_delete_snapshot,
            'status': pg_check_status,
        }

    handler = dispatch.get(args.command)
    if not handler:
        if args.command == 'collections' and args.type == 'postgres':
            print("The 'collections' command is only available for --type qdrant")
            sys.exit(1)
        parser.print_help()
        sys.exit(1)

    asyncio.run(handler(args))


if __name__ == '__main__':
    main()
