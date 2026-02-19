from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

import orjson


# ---------------------------------------------------------------------------
# Feature names (single source of truth for all 6 searchable/embeddable fields)
# ---------------------------------------------------------------------------

FEATURE_NAMES: List[str] = [
    "control_title",
    "control_description",
    "evidence_description",
    "local_functional_information",
    "control_as_event",
    "control_as_issues",
]

HASH_COLUMN_NAMES: List[str] = [f"hash_{f}" for f in FEATURE_NAMES]
MASK_COLUMN_NAMES: List[str] = [f"mask_{f}" for f in FEATURE_NAMES]


# ---------------------------------------------------------------------------
# Path helpers (simplified directory structure)
# ---------------------------------------------------------------------------

def resolve_data_ingested_path(cli_value: Optional[Path] = None) -> Path:
    """Resolve data_ingested_path from CLI arg or .env settings.

    If a CLI value is provided, use it. Otherwise, fall back to
    DATA_INGESTED_PATH from the server .env file.
    """
    if cli_value is not None:
        return cli_value
    from server.settings import get_settings
    return get_settings().data_ingested_path


def controls_jsonl_path(data_ingested_path: Path, upload_id: str) -> Path:
    return data_ingested_path / "controls" / f"{upload_id}.jsonl"


def model_output_path(data_ingested_path: Path, model_name: str, upload_id: str, suffix: str = ".jsonl") -> Path:
    return data_ingested_path / "model_runs" / model_name / f"{upload_id}{suffix}"


def model_index_path(data_ingested_path: Path, model_name: str, upload_id: str, suffix: str = ".jsonl") -> Path:
    return data_ingested_path / "model_runs" / model_name / f"{upload_id}{suffix}.index.json"


def default_run_date() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def iter_jsonl(path: Path) -> Iterator[Tuple[int, Dict[str, Any]]]:
    with path.open("rb") as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            obj = orjson.loads(line)
            if not isinstance(obj, dict):
                raise ValueError("Expected object JSON on line {} in {}".format(line_num, path))
            yield line_num, obj


def normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).replace("\r", " ").replace("\n", " ")
    compact = " ".join(text.split())
    return compact if compact else None


def is_active_status(value: Any) -> bool:
    return str(value or "").strip().lower() == "active"


def is_key_control_yes(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "yes", "y", "1"}


def is_level_one(value: Any) -> bool:
    return str(value or "").strip().lower() == "level 1"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_controls(
    controls_jsonl: Path, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen_control_ids = set()

    for _, row in iter_jsonl(controls_jsonl):
        control_id = row.get("control_id")
        if not isinstance(control_id, str) or not control_id:
            raise ValueError("Missing/invalid control_id in {}".format(controls_jsonl))
        if control_id in seen_control_ids:
            raise ValueError("Duplicate control_id {} in {}".format(control_id, controls_jsonl))
        seen_control_ids.add(control_id)
        rows.append(row)
        if limit is not None and len(rows) >= limit:
            break
    return rows


def load_jsonl_by_control_id(jsonl_path: Path) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for _, row in iter_jsonl(jsonl_path):
        control_id = row.get("control_id")
        if isinstance(control_id, str):
            out[control_id] = row
    return out


def read_index(index_path: Path) -> Dict[str, Any]:
    return orjson.loads(index_path.read_bytes())


# ---------------------------------------------------------------------------
# Index / output writers
# ---------------------------------------------------------------------------

def write_jsonl_with_index(
    *,
    records: Sequence[Mapping[str, Any]],
    output_path: Path,
    model_name: str,
    run_date: str,
    hashes_by_control_id: Mapping[str, Dict[str, Optional[str]]],
) -> Path:
    """Write JSONL records and a companion index JSON file.

    Args:
        hashes_by_control_id: Maps control_id → {hash_control_title: ..., hash_control_description: ..., ...}
            Each value is a dict of 6 per-feature hashes (or None for empty features).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    by_control_id: Dict[str, Dict[str, Any]] = {}
    seen_control_ids = set()

    with output_path.open("wb") as f:
        for row_index, record in enumerate(records):
            control_id = record.get("control_id")
            if not isinstance(control_id, str) or not control_id:
                raise ValueError("Output record missing valid control_id")
            if control_id in seen_control_ids:
                raise ValueError("Duplicate control_id in output: {}".format(control_id))
            seen_control_ids.add(control_id)

            offset = f.tell()
            f.write(orjson.dumps(record))
            f.write(b"\n")

            feature_hashes = hashes_by_control_id.get(control_id, {})
            entry: Dict[str, Any] = {
                "row": row_index,
                "offset": offset,
            }
            entry.update(feature_hashes)
            by_control_id[control_id] = entry

    index_doc = {
        "model": model_name,
        "run_date": run_date,
        "created_at_utc": utc_now_iso(),
        "output_file": str(output_path),
        "records": len(records),
        "by_control_id": by_control_id,
    }
    index_path = output_path.with_suffix(output_path.suffix + ".index.json")
    index_path.write_bytes(
        orjson.dumps(index_doc, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
    )
    return index_path


def write_npz_index(
    *,
    output_npz_path: Path,
    model_name: str,
    run_date: str,
    control_ids: Sequence[str],
    hashes_by_control_id: Mapping[str, Dict[str, Optional[str]]],
    embedding_dim: int,
) -> Path:
    """Write NPZ index JSON file with per-feature hashes.

    Args:
        hashes_by_control_id: Maps control_id → {hash_control_title: ..., ...}
    """
    by_control_id: Dict[str, Dict[str, Any]] = {}

    for row_index, control_id in enumerate(control_ids):
        feature_hashes = hashes_by_control_id.get(control_id, {})
        entry: Dict[str, Any] = {"row": row_index}
        entry.update(feature_hashes)
        by_control_id[control_id] = entry

    index_doc = {
        "model": model_name,
        "run_date": run_date,
        "created_at_utc": utc_now_iso(),
        "output_file": str(output_npz_path),
        "records": len(control_ids),
        "embedding_dim": embedding_dim,
        "by_control_id": by_control_id,
    }
    index_path = output_npz_path.with_suffix(output_npz_path.suffix + ".index.json")
    index_path.write_bytes(
        orjson.dumps(index_doc, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
    )
    return index_path
