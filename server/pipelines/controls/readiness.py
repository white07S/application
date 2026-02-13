"""Ingestion readiness checker for controls uploads.

Verifies that all required files exist and contain matching control_ids
before allowing ingestion to proceed.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

import orjson

from server.logging_config import get_logger
from server.pipelines import storage

logger = get_logger(name=__name__)

MODEL_CHECKS = [
    {"name": "taxonomy", "suffix": ".jsonl"},
    {"name": "enrichment", "suffix": ".jsonl"},
    {"name": "clean_text", "suffix": ".jsonl"},
    {"name": "embeddings", "suffix": ".npz"},
]


@dataclass
class ReadinessResult:
    """Result of ingestion readiness check."""

    ready: bool = False
    source_jsonl: bool = False
    taxonomy: bool = False
    enrichment: bool = False
    clean_text: bool = False
    embeddings: bool = False
    missing_models: List[str] = field(default_factory=list)
    missing_control_ids: Dict[str, List[str]] = field(default_factory=dict)
    message: str | None = None

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "source_jsonl": self.source_jsonl,
            "taxonomy": self.taxonomy,
            "enrichment": self.enrichment,
            "clean_text": self.clean_text,
            "embeddings": self.embeddings,
            "missing_models": self.missing_models,
            "missing_control_ids": self.missing_control_ids,
            "message": self.message,
        }


def _load_control_ids_from_jsonl(jsonl_path: Path) -> Set[str]:
    """Load control_ids from a JSONL file (first field scan)."""
    ids: Set[str] = set()
    with jsonl_path.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = orjson.loads(line)
            cid = obj.get("control_id")
            if isinstance(cid, str):
                ids.add(cid)
    return ids


def _load_control_ids_from_index(index_path: Path) -> Set[str]:
    """Load control_ids from an index sidecar JSON file."""
    data = orjson.loads(index_path.read_bytes())
    by_control_id = data.get("by_control_id", {})
    return set(by_control_id.keys())


def check_ingestion_readiness(upload_id: str) -> ReadinessResult:
    """Check if all required files exist for ingesting an upload.

    Verifies:
    1. Source controls JSONL exists
    2. All 4 model output files exist (with index sidecars)
    3. All control_ids from source are present in each model index

    Args:
        upload_id: Upload ID (e.g. UPL-2026-0001)

    Returns:
        ReadinessResult with per-model status and any missing control_ids.
    """
    result = ReadinessResult()

    # Check source JSONL
    source_path = storage.get_control_jsonl_path(upload_id)
    if not source_path.exists():
        result.message = f"Source JSONL not found: {source_path}"
        return result

    result.source_jsonl = True

    # Load source control_ids
    try:
        source_ids = _load_control_ids_from_jsonl(source_path)
    except Exception as e:
        result.message = f"Failed to read source JSONL: {e}"
        return result

    if not source_ids:
        result.message = "Source JSONL contains no control_ids"
        return result

    # Check each model
    for check in MODEL_CHECKS:
        model_name = check["name"]
        suffix = check["suffix"]

        output_path = storage.get_model_output_path(model_name, upload_id, suffix)
        index_path = storage.get_model_index_path(model_name, upload_id, suffix)

        if not output_path.exists() or not index_path.exists():
            result.missing_models.append(model_name)
            setattr(result, model_name, False)
            continue

        # Verify control_ids match
        try:
            index_ids = _load_control_ids_from_index(index_path)
        except Exception as e:
            logger.warning("Failed to read index for {}: {}", model_name, e)
            result.missing_models.append(model_name)
            setattr(result, model_name, False)
            continue

        missing = sorted(source_ids - index_ids)
        if missing:
            result.missing_control_ids[model_name] = missing[:20]  # Sample
            result.missing_models.append(model_name)
            setattr(result, model_name, False)
        else:
            setattr(result, model_name, True)

    if result.missing_models:
        result.ready = False
        result.message = "Contact developer to perform model run"
    else:
        result.ready = True

    return result
