"""Jobs module for tracking uploads and processing jobs.

This module provides SQLite-based tracking for:
- TUS resumable uploads
- Upload batches
- Processing jobs (ingestion, model runs)

Uses a separate jobs.db SQLite database for atomic, persistent storage.
"""

from server.jobs.engine import (
    get_jobs_db,
    init_jobs_database,
    JOBS_DATABASE_PATH,
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
    "init_jobs_database",
    "JOBS_DATABASE_PATH",
    "shutdown_jobs_engine",
    # Models
    "TusUpload",
    "UploadBatch",
    "ProcessingJob",
]
