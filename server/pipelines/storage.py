"""Storage management for pipeline data."""
import os
from pathlib import Path
from server import settings
from server.logging_config import get_logger

logger = get_logger(name=__name__)

# Directory names under DATA_INGESTION_PATH
UPLOADS_DIR = "uploads"
PREPROCESSED_DIR = "preprocessed"
DATABASE_DIR = "database"
STATE_DIR = ".state"
TUS_UPLOADS_DIR = ".tus_uploads"
LOCK_FILE = "processing_lock.json"

def get_uploads_path() -> Path:
    """Get the uploads directory path."""
    return settings.DATA_INGESTION_PATH / UPLOADS_DIR

def get_preprocessed_path() -> Path:
    """Get the preprocessed parquet directory path."""
    return settings.DATA_INGESTION_PATH / PREPROCESSED_DIR

def get_database_path() -> Path:
    """Get the database directory path."""
    return settings.DATA_INGESTION_PATH / DATABASE_DIR

def get_state_path() -> Path:
    """Get the state directory path (for lock files, etc.)."""
    return settings.DATA_INGESTION_PATH / STATE_DIR


def get_tus_uploads_path() -> Path:
    """Get the TUS resumable uploads directory path."""
    return settings.DATA_INGESTION_PATH / TUS_UPLOADS_DIR

def get_upload_batch_path(upload_id: str, data_type: str) -> Path:
    """Get the path for a specific upload batch.

    Format: uploads/{upload_id}_{data_type}/
    Example: uploads/UPL-2026-0001_issues/
    """
    return get_uploads_path() / f"{upload_id}_{data_type}"

def get_preprocessed_batch_path(upload_id: str, data_type: str) -> Path:
    """Get the preprocessed parquet path for a batch.

    Format: preprocessed/{upload_id}_{data_type}/
    """
    return get_preprocessed_path() / f"{upload_id}_{data_type}"

def init_storage_directories() -> None:
    """Initialize all required storage directories."""
    directories = [
        get_uploads_path(),
        get_preprocessed_path(),
        get_database_path(),
        get_state_path(),
        get_tus_uploads_path(),
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured storage directory exists: {}", directory)

def cleanup_upload_batch(upload_id: str, data_type: str) -> None:
    """Clean up preprocessed files for a completed upload batch.

    Only removes the preprocessed (parquet) directory for the batch.
    The original uploads directory is preserved as the source of truth.
    Called after successful database ingestion.
    """
    import shutil

    # Only clean up preprocessed parquet files, keep original uploads
    preprocessed_path = get_preprocessed_batch_path(upload_id, data_type)

    if preprocessed_path.exists():
        shutil.rmtree(preprocessed_path)
        logger.info("Cleaned up preprocessed directory: {}", preprocessed_path)

def get_lock_file_path() -> Path:
    """Get path to the processing lock file."""
    return get_state_path() / LOCK_FILE


def acquire_processing_lock(upload_id: str, owner: str) -> None:
    """Acquire a global processing lock to ensure only one pipeline runs at a time.

    Raises:
        RuntimeError if a lock already exists and has not expired.
    """
    import json
    from datetime import datetime, timedelta

    lock_path = get_lock_file_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        try:
            existing = json.loads(lock_path.read_text())
        except Exception:
            existing = {}

        expires_at = existing.get("expires_at")
        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at)
            except Exception:
                expires_dt = None
        else:
            expires_dt = None

        # If not expired, prevent new lock
        if not expires_dt or expires_dt > datetime.utcnow():
            raise RuntimeError(f"Pipeline already running for upload '{existing.get('upload_id')}' by '{existing.get('owner')}'.")

    payload = {
        "upload_id": upload_id,
        "owner": owner,
        "pid": os.getpid(),
        "started_at": datetime.utcnow().isoformat(),
        # auto-expire after 2 hours in case of crash
        "expires_at": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
    }
    lock_path.write_text(json.dumps(payload, indent=2))
    logger.info("Acquired processing lock for upload {} by {}", upload_id, owner)


def release_processing_lock() -> None:
    """Release the global processing lock if held."""
    lock_path = get_lock_file_path()
    if lock_path.exists():
        lock_path.unlink()
        logger.info("Released processing lock")


def is_processing_locked() -> bool:
    """Check if a processing lock is active (non-expired)."""
    import json
    from datetime import datetime

    lock_path = get_lock_file_path()
    if not lock_path.exists():
        return False

    try:
        data = json.loads(lock_path.read_text())
        expires_at = data.get("expires_at")
        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at)
                if expires_dt < datetime.utcnow():
                    return False
            except Exception:
                return True
        return True
    except Exception:
        return True

def get_upload_sequence_path() -> Path:
    """Get path to the upload ID sequence file."""
    return get_state_path() / "upload_id_sequence.json"
