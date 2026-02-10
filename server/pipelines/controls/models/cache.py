"""Cache management for model outputs.

This module provides a cache manager that stores and retrieves model outputs
in JSONL format for most models and NPZ format for embeddings.

Cache types:
- taxonomy: NFR taxonomy classification
- enrichment: 5W analysis and entity extraction
- clean_text: Text cleaning results
- embeddings: Vector embeddings (NPZ)
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from server.logging_config import get_logger

logger = get_logger(name=__name__)


class ModelCache:
    """Manages cache files for model outputs.

    The cache uses JSONL (JSON Lines) format where each line contains:
    {
        "control_id": "CTRL-001",
        "response": {
            "status": "success",
            "error": null,
            "data": {...}
        }
    }

    Cache files are named: {cache_type}_results.jsonl (except embeddings).
    """

    CACHE_FILES = {
        "taxonomy": "taxonomy_results.jsonl",
        "enrichment": "enrichment_results.jsonl",
        "clean_text": "clean_text_results.jsonl",
    }

    EMBEDDINGS_CACHE_FILE = "embeddings_results.npz"
    EMBEDDINGS_FIELDS = [
        "control_title_embedding",
        "control_description_embedding",
        "evidence_description_embedding",
        "local_functional_information_embedding",
        "control_as_event_embedding",
        "control_as_issues_embedding",
    ]

    def __init__(self, cache_dir: Path):
        """Initialize cache manager.

        Args:
            cache_dir: Directory where cache files are stored
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._caches: Dict[str, Dict[str, Any]] = {}
        self._embeddings_cache: Optional[Dict[str, Any]] = None

    def _get_cache_file(self, cache_type: str) -> Path:
        """Get the file path for a cache type.

        Args:
            cache_type: Type of cache (taxonomy, enrichment, clean_text, embeddings)

        Returns:
            Path to cache file

        Raises:
            ValueError: If cache_type is invalid
        """
        if cache_type not in self.CACHE_FILES:
            raise ValueError(
                f"Invalid cache_type: {cache_type}. Must be one of {list(self.CACHE_FILES.keys())}"
            )
        return self.cache_dir / self.CACHE_FILES[cache_type]

    def _get_embeddings_cache_file(self) -> Path:
        """Get the file path for embeddings cache (NPZ)."""
        return self.cache_dir / self.EMBEDDINGS_CACHE_FILE

    def _load_embeddings_cache(self) -> Dict[str, Any]:
        """Load embeddings cache from NPZ file into memory."""
        if self._embeddings_cache is not None:
            return self._embeddings_cache

        cache_file = self._get_embeddings_cache_file()
        if not cache_file.exists():
            self._embeddings_cache = {}
            return self._embeddings_cache

        try:
            data_ctx = np.load(cache_file, allow_pickle=False)
        except Exception as e:
            logger.warning("Failed to load embeddings cache {}: {}", cache_file, e)
            self._embeddings_cache = {}
            return self._embeddings_cache

        with data_ctx as data:
            control_ids = data["control_id"] if "control_id" in data else None
            if control_ids is None:
                self._embeddings_cache = {}
                return self._embeddings_cache

            control_ids = [str(cid) for cid in control_ids.tolist()]
            hashes = data["hash"] if "hash" in data else None
            effective_at = data["effective_at"] if "effective_at" in data else None

            def normalize_scalar(value: Optional[str]) -> Optional[str]:
                if value is None:
                    return None
                val = str(value)
                return val if val else None

            cache: Dict[str, Any] = {}
            for idx, cid in enumerate(control_ids):
                record: Dict[str, Any] = {
                    "control_id": cid,
                    "hash": normalize_scalar(hashes[idx]) if hashes is not None else None,
                    "effective_at": normalize_scalar(effective_at[idx]) if effective_at is not None else None,
                }

                for field in self.EMBEDDINGS_FIELDS:
                    field_arr = data[field] if field in data else None
                    if field_arr is None:
                        record[field] = None
                        continue
                    vec = field_arr[idx]
                    if vec.size == 0:
                        record[field] = None
                    elif np.isnan(vec).all():
                        record[field] = None
                    else:
                        record[field] = vec.tolist()

                cache[cid] = record

        self._embeddings_cache = cache
        return self._embeddings_cache

    def _write_embeddings_cache(self) -> None:
        """Persist embeddings cache to NPZ file."""
        if self._embeddings_cache is None:
            return

        cache_file = self._get_embeddings_cache_file()
        control_ids = list(self._embeddings_cache.keys())
        if not control_ids:
            if cache_file.exists():
                cache_file.unlink()
            return

        control_arr = np.array(control_ids, dtype="U")
        hash_arr = np.array(
            [self._embeddings_cache[cid].get("hash") or "" for cid in control_ids],
            dtype="U",
        )
        effective_arr = np.array(
            [self._embeddings_cache[cid].get("effective_at") or "" for cid in control_ids],
            dtype="U",
        )

        arrays: Dict[str, Any] = {
            "control_id": control_arr,
            "hash": hash_arr,
            "effective_at": effective_arr,
        }

        for field in self.EMBEDDINGS_FIELDS:
            dim = 0
            for cid in control_ids:
                vec = self._embeddings_cache[cid].get(field)
                if vec:
                    dim = len(vec)
                    break

            if dim == 0:
                arrays[field] = np.empty((len(control_ids), 0), dtype=np.float32)
                continue

            mat = np.full((len(control_ids), dim), np.nan, dtype=np.float32)
            for idx, cid in enumerate(control_ids):
                vec = self._embeddings_cache[cid].get(field)
                if vec is None:
                    continue
                arr = np.asarray(vec, dtype=np.float32)
                if arr.shape[0] != dim:
                    logger.warning(
                        "Embeddings cache dimension mismatch for {} ({}): expected {}, got {}",
                        field, cid, dim, arr.shape[0],
                    )
                    continue
                mat[idx] = arr
            arrays[field] = mat

        np.savez_compressed(cache_file, **arrays)

    def load_cache(self, cache_type: str) -> Dict[str, Any]:
        """Load cache from JSONL file into memory.

        Args:
            cache_type: Type of cache to load

        Returns:
            Dictionary mapping control_id to response data
        """
        if cache_type == "embeddings":
            return self._load_embeddings_cache()

        if cache_type in self._caches:
            return self._caches[cache_type]

        cache_file = self._get_cache_file(cache_type)
        cache: Dict[str, Any] = {}

        if not cache_file.exists():
            self._caches[cache_type] = cache
            return cache

        with open(cache_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line.strip())
                    control_id = record.get("control_id")
                    response = record.get("response", {})

                    if not control_id:
                        continue

                    # Extract data from response envelope if present
                    if "status" in response and "data" in response:
                        if response.get("status") == "success":
                            cache[control_id] = response.get("data", {})
                    else:
                        # Legacy format without envelope
                        cache[control_id] = response

                except json.JSONDecodeError:
                    # Skip invalid JSON lines
                    continue

        self._caches[cache_type] = cache
        return cache

    def get_cached(self, cache_type: str, control_id: str) -> Optional[Dict]:
        """Get cached result for a control.

        Args:
            cache_type: Type of cache to check
            control_id: Control ID to look up

        Returns:
            Cached data if found, None otherwise
        """
        cache = self.load_cache(cache_type)
        return cache.get(control_id)

    def save_to_cache(self, cache_type: str, control_id: str, response: Dict[str, Any]) -> None:
        """Save a result to cache (both in-memory and on disk).

        Args:
            cache_type: Type of cache to save to
            control_id: Control ID
            response: Response data to cache (should include status, error, data)
        """
        if cache_type == "embeddings":
            if "status" in response and "data" in response:
                if response.get("status") != "success":
                    return
                data = response.get("data", {})
            else:
                data = response

            cache = self._load_embeddings_cache()
            cache[control_id] = data
            self._write_embeddings_cache()
            return

        cache_file = self._get_cache_file(cache_type)

        # Append to JSONL file
        with open(cache_file, "a") as f:
            record = {"control_id": control_id, "response": response}
            f.write(json.dumps(record) + "\n")

        # Update in-memory cache if loaded
        if cache_type in self._caches:
            if "status" in response and "data" in response:
                if response.get("status") == "success":
                    self._caches[cache_type][control_id] = response.get("data", {})
            else:
                self._caches[cache_type][control_id] = response

