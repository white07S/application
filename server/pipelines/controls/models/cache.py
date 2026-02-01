"""JSONL cache management for model outputs.

This module provides a cache manager that stores and retrieves model outputs
in JSONL format. Each cache file contains one JSON object per line with
control_id and response data.

Cache types:
- taxonomy: NFR taxonomy classification
- enrichment: 5W analysis and entity extraction
- clean_text: Text cleaning results
- embeddings: Vector embeddings
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


class ModelCache:
    """Manages JSONL cache files for model outputs.

    The cache uses JSONL (JSON Lines) format where each line contains:
    {
        "control_id": "CTRL-001",
        "response": {
            "status": "success",
            "error": null,
            "data": {...}
        }
    }

    Cache files are named: {cache_type}_results.jsonl
    """

    CACHE_FILES = {
        "taxonomy": "taxonomy_results.jsonl",
        "enrichment": "enrichment_results.jsonl",
        "clean_text": "clean_text_results.jsonl",
        "embeddings": "embeddings_results.jsonl",
    }

    def __init__(self, cache_dir: Path):
        """Initialize cache manager.

        Args:
            cache_dir: Directory where cache files are stored
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._caches: Dict[str, Dict[str, Any]] = {}

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
            raise ValueError(f"Invalid cache_type: {cache_type}. Must be one of {list(self.CACHE_FILES.keys())}")
        return self.cache_dir / self.CACHE_FILES[cache_type]

    def load_cache(self, cache_type: str) -> Dict[str, Any]:
        """Load cache from JSONL file into memory.

        Args:
            cache_type: Type of cache to load

        Returns:
            Dictionary mapping control_id to response data
        """
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

    def clear_cache(self, cache_type: str) -> None:
        """Clear a cache (both in-memory and on disk).

        Args:
            cache_type: Type of cache to clear
        """
        cache_file = self._get_cache_file(cache_type)
        if cache_file.exists():
            cache_file.unlink()

        if cache_type in self._caches:
            del self._caches[cache_type]

    def get_cache_stats(self, cache_type: str) -> Dict[str, Any]:
        """Get statistics about a cache.

        Args:
            cache_type: Type of cache to analyze

        Returns:
            Dictionary with cache statistics
        """
        cache = self.load_cache(cache_type)
        cache_file = self._get_cache_file(cache_type)

        return {
            "cache_type": cache_type,
            "file_exists": cache_file.exists(),
            "file_path": str(cache_file),
            "entry_count": len(cache),
            "control_ids": list(cache.keys()),
        }
