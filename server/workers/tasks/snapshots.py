"""Celery tasks for PostgreSQL and Qdrant snapshot operations.

Wraps the existing async snapshot services so that long-running
pg_dump / pg_restore / Qdrant transfers survive API restarts.
"""

import asyncio
import traceback
from datetime import datetime, timezone
from typing import Any, Dict

from server.workers.celery_app import celery_app
from server.logging_config import get_logger

logger = get_logger(name=__name__)


def _run_in_loop(coro):
    """Run an async coroutine in a fresh event loop (Celery is sync)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _ensure_engine():
    """Ensure the PostgreSQL engine is initialized for this worker."""
    from server.config.postgres import init_engine
    from server.settings import get_settings

    settings = get_settings()
    init_engine(settings.postgres_url, pool_size=3, max_overflow=5)


# ── PostgreSQL snapshots ─────────────────────────────────────────

@celery_app.task(
    name='server.workers.tasks.snapshots.create_pg_snapshot',
    queue='snapshot',
    time_limit=7200,
    soft_time_limit=7000,
)
def create_pg_snapshot_task(
    job_id: str,
    name: str,
    description: str,
    user: str,
) -> Dict[str, Any]:
    """Create a PostgreSQL snapshot via pg_dump."""
    _ensure_engine()
    try:
        _run_in_loop(_create_pg_snapshot(job_id, name, description, user))
        return {'success': True, 'job_id': job_id}
    except Exception as e:
        logger.exception("PG snapshot creation task failed: {}", str(e))
        _fail_job_sync(job_id, str(e))
        return {'success': False, 'job_id': job_id, 'error': str(e)}


@celery_app.task(
    name='server.workers.tasks.snapshots.restore_pg_snapshot',
    queue='snapshot',
    time_limit=7200,
    soft_time_limit=7000,
)
def restore_pg_snapshot_task(
    job_id: str,
    snapshot_id: str,
    user: str,
    create_pre_restore_backup: bool,
    force: bool,
) -> Dict[str, Any]:
    """Restore a PostgreSQL snapshot via pg_restore."""
    _ensure_engine()
    try:
        _run_in_loop(
            _restore_pg_snapshot(job_id, snapshot_id, user, create_pre_restore_backup, force)
        )
        return {'success': True, 'job_id': job_id}
    except Exception as e:
        logger.exception("PG snapshot restore task failed: {}", str(e))
        _fail_job_sync(job_id, str(e))
        return {'success': False, 'job_id': job_id, 'error': str(e)}


async def _create_pg_snapshot(job_id: str, name: str, description: str, user: str):
    from server.config.postgres import get_db_session_context
    from server.devdata.snapshot_service import snapshot_service

    async with get_db_session_context() as db:
        await snapshot_service.create_snapshot(
            db=db,
            job_id=job_id,
            name=name,
            description=description,
            user=user,
            is_scheduled=False,
        )


async def _restore_pg_snapshot(
    job_id: str, snapshot_id: str, user: str,
    create_pre_restore_backup: bool, force: bool,
):
    from server.config.postgres import get_db_session_context
    from server.devdata.snapshot_service import snapshot_service
    from server.jobs import ProcessingJob

    async with get_db_session_context() as db:
        pre_restore_id = await snapshot_service.restore_snapshot(
            db=db,
            job_id=job_id,
            snapshot_id=snapshot_id,
            user=user,
            create_pre_restore_backup=create_pre_restore_backup,
            force=force,
        )

        if pre_restore_id:
            job = await db.get(ProcessingJob, job_id)
            if job:
                job.current_step = f"Restore completed. Pre-restore backup: {pre_restore_id}"
                await db.commit()


# ── Qdrant snapshots ─────────────────────────────────────────────

@celery_app.task(
    name='server.workers.tasks.snapshots.create_qdrant_snapshot',
    queue='snapshot',
    time_limit=3600,
    soft_time_limit=3400,
)
def create_qdrant_snapshot_task(
    job_id: str,
    name: str,
    description: str,
    user: str,
    collection_name: str,
) -> Dict[str, Any]:
    """Create a Qdrant snapshot."""
    _ensure_engine()
    try:
        _run_in_loop(
            _create_qdrant_snapshot(job_id, name, description, user, collection_name)
        )
        return {'success': True, 'job_id': job_id}
    except Exception as e:
        logger.exception("Qdrant snapshot creation task failed: {}", str(e))
        _fail_job_sync(job_id, str(e))
        return {'success': False, 'job_id': job_id, 'error': str(e)}


@celery_app.task(
    name='server.workers.tasks.snapshots.restore_qdrant_snapshot',
    queue='snapshot',
    time_limit=3600,
    soft_time_limit=3400,
)
def restore_qdrant_snapshot_task(
    job_id: str,
    snapshot_id: str,
    user: str,
    force: bool,
) -> Dict[str, Any]:
    """Restore a Qdrant collection from a snapshot."""
    _ensure_engine()
    try:
        _run_in_loop(_restore_qdrant_snapshot(job_id, snapshot_id, user, force))
        return {'success': True, 'job_id': job_id}
    except Exception as e:
        logger.exception("Qdrant snapshot restore task failed: {}", str(e))
        _fail_job_sync(job_id, str(e))
        return {'success': False, 'job_id': job_id, 'error': str(e)}


async def _create_qdrant_snapshot(
    job_id: str, name: str, description: str, user: str, collection_name: str,
):
    from server.config.postgres import get_db_session_context
    from server.devdata.qdrant_snapshot_service import qdrant_snapshot_service

    async with get_db_session_context() as db:
        await qdrant_snapshot_service.create_snapshot(
            db=db,
            job_id=job_id,
            name=name,
            description=description,
            user=user,
            collection_name=collection_name,
        )


async def _restore_qdrant_snapshot(job_id: str, snapshot_id: str, user: str, force: bool):
    from server.config.postgres import get_db_session_context
    from server.devdata.qdrant_snapshot_service import qdrant_snapshot_service

    async with get_db_session_context() as db:
        await qdrant_snapshot_service.restore_snapshot(
            db=db,
            job_id=job_id,
            snapshot_id=snapshot_id,
            user=user,
            force=force,
        )


# ── Shared helpers ───────────────────────────────────────────────

def _fail_job_sync(job_id: str, error: str):
    """Mark a job as failed using a synchronous DB connection.

    Uses a sync engine to avoid event loop conflicts — this runs in the
    except block after the async loop has already been closed.
    """
    try:
        from sqlalchemy import create_engine, text
        from server.settings import get_settings

        settings = get_settings()
        # Convert async URL to sync (asyncpg → psycopg2)
        sync_url = settings.postgres_url.replace(
            "postgresql+asyncpg", "postgresql"
        )
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE processing_jobs "
                    "SET status = :status, error_message = :error, "
                    "    current_step = 'Failed', completed_at = :completed_at "
                    "WHERE id = :job_id"
                ),
                {
                    "status": "failed",
                    "error": error[:2000],  # Truncate long errors
                    "job_id": job_id,
                    "completed_at": datetime.now(timezone.utc),
                },
            )
            conn.commit()
        engine.dispose()
    except Exception as e:
        logger.error("Failed to update job {} as failed: {}", job_id, e)
