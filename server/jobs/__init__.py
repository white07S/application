"""Jobs module for tracking uploads and processing jobs.

This module provides PostgreSQL-based tracking for:
- TUS resumable uploads
- Upload batches
- Processing jobs (ingestion, model runs)

Tables are managed by Alembic alongside domain tables in the shared database.
"""

from server.jobs.engine import (
    get_jobs_db,
    get_session_factory_for_background,
    init_jobs_database,
    shutdown_jobs_engine,
)
from server.jobs.models import (
    TusUpload,
    UploadBatch,
    ProcessingJob,
)

__all__ = [
    # Engine
    "get_jobs_db",
    "get_session_factory_for_background",
    "init_jobs_database",
    "shutdown_jobs_engine",
    # Models
    "TusUpload",
    "UploadBatch",
    "ProcessingJob",
]
