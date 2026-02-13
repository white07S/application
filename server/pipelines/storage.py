"""Storage management for pipeline data.

Directory structure:

DATA_INGESTED_PATH/
├── controls/          Controls CSV + JSONL per upload
│   ├── UPL-2026-0001.csv
│   └── UPL-2026-0001.jsonl
├── model_runs/        AI model outputs per upload
│   ├── taxonomy/
│   ├── enrichment/
│   ├── clean_text/
│   └── embeddings/
├── jobs/              PostgreSQL job tracking (managed by Alembic)
├── .tus_temp/         TUS temporary uploads
└── .state/            Lock files

CONTEXT_PROVIDERS_PATH/
├── organization/      Org chart JSONL (date-partitioned)
│   └── YYYY-MM-DD/
└── risk_theme/        Risk theme JSONL (date-partitioned)
    └── YYYY-MM-DD/
"""

import os
from pathlib import Path

from server.settings import get_settings
from server.logging_config import get_logger

logger = get_logger(name=__name__)

# Directory names
TUS_TEMP_DIR = ".tus_temp"
STATE_DIR = ".state"
CONTROLS_DIR = "controls"
MODEL_RUNS_DIR = "model_runs"
LOCK_FILE = "processing_lock.json"


# ── TUS temp + state ─────────────────────────────────────────────────

def get_uploads_path() -> Path:
    """Get the TUS temporary uploads directory path."""
    return get_settings().data_ingested_path / TUS_TEMP_DIR


def get_state_path() -> Path:
    """Get the state directory path (for lock files)."""
    return get_settings().data_ingested_path / STATE_DIR


# ── Data ingested path (controls + model runs) ───────────────────────

def get_controls_path() -> Path:
    """Get the controls data directory."""
    return get_settings().data_ingested_path / CONTROLS_DIR


def get_model_runs_path() -> Path:
    """Get the model runs base directory."""
    return get_settings().data_ingested_path / MODEL_RUNS_DIR


def get_control_csv_path(upload_id: str) -> Path:
    """Get path for a control upload's CSV file."""
    return get_controls_path() / f"{upload_id}.csv"


def get_control_jsonl_path(upload_id: str) -> Path:
    """Get path for a control upload's JSONL file."""
    return get_controls_path() / f"{upload_id}.jsonl"


def get_model_output_path(model_name: str, upload_id: str, suffix: str = ".jsonl") -> Path:
    """Get path for a model run output file.

    Examples:
        get_model_output_path("taxonomy", "UPL-2026-0001") → .../model_runs/taxonomy/UPL-2026-0001.jsonl
        get_model_output_path("embeddings", "UPL-2026-0001", ".npz") → .../model_runs/embeddings/UPL-2026-0001.npz
    """
    return get_model_runs_path() / model_name / f"{upload_id}{suffix}"


def get_model_index_path(model_name: str, upload_id: str, suffix: str = ".jsonl") -> Path:
    """Get path for a model run index sidecar file.

    Examples:
        get_model_index_path("taxonomy", "UPL-2026-0001") → .../taxonomy/UPL-2026-0001.jsonl.index.json
        get_model_index_path("embeddings", "UPL-2026-0001", ".npz") → .../embeddings/UPL-2026-0001.npz.index.json
    """
    return get_model_runs_path() / model_name / f"{upload_id}{suffix}.index.json"


# ── Context providers path ────────────────────────────────────────────

def get_context_providers_path() -> Path:
    """Get the context providers base directory."""
    return get_settings().context_providers_path


def get_latest_context_date(domain: str) -> str | None:
    """Find the latest date folder under a context provider domain.

    Args:
        domain: "organization" or "risk_theme"

    Returns:
        Date string (YYYY-MM-DD) of the latest folder, or None if empty.
    """
    domain_path = get_context_providers_path() / domain
    if not domain_path.exists():
        return None

    date_dirs = sorted(
        [d.name for d in domain_path.iterdir() if d.is_dir()],
        reverse=True,
    )
    return date_dirs[0] if date_dirs else None


# ── Init & Lock ───────────────────────────────────────────────────────

def init_storage_directories() -> None:
    """Initialize all required storage directories."""
    settings = get_settings()
    directories = [
        settings.data_ingested_path / TUS_TEMP_DIR,
        settings.data_ingested_path / STATE_DIR,
        settings.data_ingested_path / CONTROLS_DIR,
        settings.data_ingested_path / MODEL_RUNS_DIR / "taxonomy",
        settings.data_ingested_path / MODEL_RUNS_DIR / "enrichment",
        settings.data_ingested_path / MODEL_RUNS_DIR / "clean_text",
        settings.data_ingested_path / MODEL_RUNS_DIR / "embeddings",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured storage directory: {}", directory)

    logger.info("Storage directories initialized")


def get_lock_file_path() -> Path:
    """Get path to the processing lock file."""
    return get_state_path() / LOCK_FILE


def acquire_processing_lock(upload_id: str, owner: str) -> None:
    """Acquire a global processing lock to ensure only one pipeline runs at a time."""
    import json
    from datetime import datetime, timedelta

    lock_path = get_lock_file_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    while True:
        now = datetime.utcnow()
        payload = {
            "upload_id": upload_id,
            "owner": owner,
            "pid": os.getpid(),
            "started_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=2)).isoformat(),
        }

        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, indent=2))
            logger.info("Acquired processing lock for upload {} by {}", upload_id, owner)
            return
        except FileExistsError:
            try:
                existing = json.loads(lock_path.read_text())
            except Exception:
                existing = None

            expires_dt = None
            if existing:
                expires_at = existing.get("expires_at")
                if expires_at:
                    try:
                        expires_dt = datetime.fromisoformat(expires_at)
                    except Exception:
                        expires_dt = None

            if not existing or not expires_dt or expires_dt <= now:
                try:
                    lock_path.unlink()
                    logger.warning("Removed stale processing lock: {}", lock_path)
                    continue
                except FileNotFoundError:
                    # Another process resolved lock state; retry acquire.
                    continue
                except Exception as e:
                    raise RuntimeError(f"Failed to clear stale processing lock: {e}") from e

            raise RuntimeError(
                f"Pipeline already running for upload '{existing.get('upload_id')}' "
                f"by '{existing.get('owner')}'."
            )


def release_processing_lock() -> None:
    """Release the global processing lock if held."""
    lock_path = get_lock_file_path()
    try:
        lock_path.unlink()
        logger.info("Released processing lock")
    except FileNotFoundError:
        return


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
                    lock_path.unlink(missing_ok=True)
                    return False
            except Exception:
                lock_path.unlink(missing_ok=True)
                return False
        return True
    except Exception:
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False
