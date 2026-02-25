"""Disk-based snapshot metadata — single source of truth.

All snapshot operations (list, find, restore-tracking, ID generation)
read and write metadata.json files on disk.  No PostgreSQL tables are
required for snapshot management.

Disk layout:
    $BACKUP_PATH/YYYY-MM-DD/<SNAP-ID>/metadata.json
    $BACKUP_PATH/YYYY-MM-DD/<SNAP-ID>/backup.dump      (PG)
    $BACKUP_PATH/YYYY-MM-DD/<SNAP-ID>/snapshot.snapshot (Qdrant)
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from server.logging_config import get_logger

logger = get_logger(name=__name__)


@dataclass
class DiskSnapshotMeta:
    """Snapshot metadata read from a metadata.json file on disk."""

    # Core identity
    snapshot_id: str
    name: str
    description: Optional[str]
    created_by: str
    created_at: datetime
    status: str  # completed / failed / in_progress

    # File info
    file_path: str  # absolute path to backup file
    file_size: int
    checksum: Optional[str]

    # Date folder the snapshot lives in
    date_folder: str  # e.g. "2026-02-25"

    # Path to the metadata.json itself
    metadata_path: Path

    # --- PG-specific (None for Qdrant) ---
    alembic_version: Optional[str] = None
    table_count: Optional[int] = None
    total_records: Optional[int] = None
    compressed: Optional[bool] = None
    postgres_host: Optional[str] = None
    postgres_port: Optional[int] = None
    postgres_database: Optional[str] = None
    postgres_username: Optional[str] = None

    # --- Qdrant-specific (None for PG) ---
    collection_name: Optional[str] = None
    qdrant_snapshot_name: Optional[str] = None
    points_count: Optional[int] = None
    vectors_count: Optional[int] = None
    qdrant_url: Optional[str] = None

    # --- Restore tracking ---
    restored_count: int = 0
    last_restored_at: Optional[datetime] = None
    last_restored_by: Optional[str] = None

    # --- Schedule (PG only) ---
    is_scheduled: bool = False
    schedule_id: Optional[str] = None

    # --- Error ---
    error_message: Optional[str] = None

    # Raw dict for anything extra
    raw: Dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_datetime(value) -> Optional[datetime]:
    """Safely parse an ISO datetime string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _load_metadata_json(metadata_file: Path) -> Optional[Dict]:
    """Read and parse a metadata.json, returning None on failure."""
    try:
        with open(metadata_file) as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to read {}: {}", metadata_file, e)
        return None


def _meta_to_disk(meta: Dict, metadata_file: Path, backup_filename: str) -> Optional[DiskSnapshotMeta]:
    """Convert a raw metadata dict + its file path into a DiskSnapshotMeta."""
    snap_id = meta.get("snapshot_id")
    if not snap_id:
        return None

    snapshot_dir = metadata_file.parent
    date_folder = snapshot_dir.parent.name
    backup_file = snapshot_dir / backup_filename

    if not backup_file.exists():
        logger.debug("Backup file missing for {}: {}", snap_id, backup_file)
        return None

    created_at = _parse_datetime(meta.get("created_at"))
    if created_at is None:
        created_at = datetime.now(timezone.utc)

    return DiskSnapshotMeta(
        snapshot_id=snap_id,
        name=meta.get("name", snap_id),
        description=meta.get("description"),
        created_by=meta.get("created_by", "unknown"),
        created_at=created_at,
        status=meta.get("status", "completed"),
        file_path=str(backup_file),
        file_size=meta.get("file_size", backup_file.stat().st_size),
        checksum=meta.get("checksum"),
        date_folder=date_folder,
        metadata_path=metadata_file,
        # PG
        alembic_version=meta.get("alembic_version"),
        table_count=meta.get("table_count"),
        total_records=meta.get("total_records"),
        compressed=meta.get("compressed"),
        postgres_host=meta.get("postgres_host"),
        postgres_port=meta.get("postgres_port"),
        postgres_database=meta.get("postgres_database"),
        postgres_username=meta.get("postgres_username"),
        # Qdrant
        collection_name=meta.get("collection_name"),
        qdrant_snapshot_name=meta.get("qdrant_snapshot_name"),
        points_count=meta.get("points_count"),
        vectors_count=meta.get("vectors_count"),
        qdrant_url=meta.get("qdrant_url"),
        # Restore tracking
        restored_count=meta.get("restored_count", 0),
        last_restored_at=_parse_datetime(meta.get("last_restored_at")),
        last_restored_by=meta.get("last_restored_by"),
        # Schedule
        is_scheduled=meta.get("is_scheduled", False),
        schedule_id=meta.get("schedule_id"),
        # Error
        error_message=meta.get("error_message"),
        raw=meta,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_pg_snapshots(backup_path: Path) -> List[DiskSnapshotMeta]:
    """Scan postgres backup directory for all completed snapshots.

    Deduplicates by snapshot_id — latest date folder wins.
    Returns list sorted by created_at descending.
    """
    return _scan_snapshots(backup_path, backup_filename="backup.dump", id_prefix="SNAP-")


def scan_qdrant_snapshots(
    backup_path: Path,
    collection_filter: Optional[str] = None,
) -> List[DiskSnapshotMeta]:
    """Scan qdrant backup directory for all completed snapshots.

    Deduplicates by snapshot_id — latest date folder wins.
    Optionally filters by collection_name.
    Returns list sorted by created_at descending.
    """
    results = _scan_snapshots(backup_path, backup_filename="snapshot.snapshot", id_prefix="QSNAP-")
    if collection_filter:
        results = [s for s in results if s.collection_name == collection_filter]
    return results


def _scan_snapshots(
    backup_path: Path,
    backup_filename: str,
    id_prefix: str,
) -> List[DiskSnapshotMeta]:
    """Core scanner: find all metadata.json under backup_path, deduplicate, sort."""
    if not backup_path.exists():
        return []

    seen_ids: Dict[str, DiskSnapshotMeta] = {}

    # Sort by date folder descending so latest date wins
    metadata_files = sorted(
        backup_path.rglob("metadata.json"),
        key=lambda p: p.parent.parent.name,
        reverse=True,
    )

    for mf in metadata_files:
        meta_dict = _load_metadata_json(mf)
        if meta_dict is None:
            continue

        snap_id = meta_dict.get("snapshot_id", "")
        if not snap_id.startswith(id_prefix):
            continue

        if snap_id in seen_ids:
            continue  # already have the latest-date version

        entry = _meta_to_disk(meta_dict, mf, backup_filename)
        if entry and entry.status == "completed":
            seen_ids[snap_id] = entry

    # Sort by created_at descending
    return sorted(seen_ids.values(), key=lambda s: s.created_at, reverse=True)


def find_snapshot(
    backup_path: Path,
    snapshot_id: str,
    backup_filename: str,
    date_str: Optional[str] = None,
) -> Optional[DiskSnapshotMeta]:
    """Find a specific snapshot on disk.

    If date_str is provided, looks only in that date folder.
    Otherwise scans all date folders and returns the latest.
    """
    if not backup_path.exists():
        return None

    if date_str:
        # Look in a specific date folder
        metadata_file = backup_path / date_str / snapshot_id / "metadata.json"
        if not metadata_file.exists():
            return None
        meta_dict = _load_metadata_json(metadata_file)
        if meta_dict is None:
            return None
        return _meta_to_disk(meta_dict, metadata_file, backup_filename)

    # Scan all date folders, return latest
    candidates: List[DiskSnapshotMeta] = []
    for date_dir in sorted(backup_path.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        snap_dir = date_dir / snapshot_id
        metadata_file = snap_dir / "metadata.json"
        if not metadata_file.exists():
            continue
        meta_dict = _load_metadata_json(metadata_file)
        if meta_dict is None:
            continue
        entry = _meta_to_disk(meta_dict, metadata_file, backup_filename)
        if entry:
            return entry  # first match is latest (sorted desc)

    return None


def get_available_dates(
    backup_path: Path,
    snapshot_id: str,
    backup_filename: str,
) -> List[str]:
    """List all date folders that contain a given snapshot ID, sorted descending."""
    if not backup_path.exists():
        return []

    dates = []
    for date_dir in sorted(backup_path.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        snap_dir = date_dir / snapshot_id
        if (snap_dir / backup_filename).exists():
            dates.append(date_dir.name)

    return dates


def update_restore_tracking(
    metadata_path: Path,
    user: str,
) -> None:
    """Increment restored_count and write back to metadata.json."""
    try:
        with open(metadata_path) as f:
            meta = json.load(f)

        meta["restored_count"] = meta.get("restored_count", 0) + 1
        meta["last_restored_at"] = datetime.now(timezone.utc).isoformat()
        meta["last_restored_by"] = user

        with open(metadata_path, "w") as f:
            json.dump(meta, f, indent=2)

        logger.info("Updated restore tracking in {}", metadata_path)
    except Exception as e:
        logger.error("Failed to update restore tracking in {}: {}", metadata_path, e)


def generate_snapshot_id(backup_path: Path, prefix: str) -> str:
    """Generate the next snapshot ID by scanning disk.

    Scans all date folders for IDs matching `prefix-YYYY-XXXX` and returns
    the next sequential ID for the current year.

    Args:
        backup_path: Base backup directory
        prefix: "SNAP" or "QSNAP"

    Returns:
        e.g. "SNAP-2026-0003" or "QSNAP-2026-0001"
    """
    current_year = datetime.now(timezone.utc).year
    pattern = re.compile(rf"^{re.escape(prefix)}-{current_year}-(\d{{4}})$")

    max_seq = 0

    if backup_path.exists():
        for date_dir in backup_path.iterdir():
            if not date_dir.is_dir():
                continue
            for snap_dir in date_dir.iterdir():
                if not snap_dir.is_dir():
                    continue
                m = pattern.match(snap_dir.name)
                if m:
                    seq = int(m.group(1))
                    if seq > max_seq:
                        max_seq = seq

    return f"{prefix}-{current_year}-{max_seq + 1:04d}"
