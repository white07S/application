"""Response mapping helpers for Qdrant read-only APIs."""

from typing import Any, Dict, List


def unwrap_qdrant_result(payload: Any) -> Any:
    """Unwrap Qdrant envelope payloads that use the `result` key."""
    if isinstance(payload, dict) and "result" in payload:
        return payload.get("result")
    return payload


def extract_collection_names(payload: Dict[str, Any]) -> List[str]:
    """Extract and normalize collection names from `GET /collections`."""
    result = unwrap_qdrant_result(payload)
    if not isinstance(result, dict):
        return []

    raw_collections = result.get("collections", [])
    if not isinstance(raw_collections, list):
        return []

    names: List[str] = []
    for collection_item in raw_collections:
        if not isinstance(collection_item, dict):
            continue
        name = collection_item.get("name")
        if isinstance(name, str) and name:
            names.append(name)

    return sorted(set(names))


def extract_named_vectors(collection_info: Dict[str, Any]) -> List[str]:
    """Extract named vectors from collection config when present."""
    config = collection_info.get("config") if isinstance(collection_info, dict) else None
    params = config.get("params") if isinstance(config, dict) else None
    vectors = params.get("vectors") if isinstance(params, dict) else None

    if not isinstance(vectors, dict):
        return []

    # Unnamed vectors are represented as a shape-like object with size/distance fields.
    scalar_vector_keys = {"size", "distance", "hnsw_config", "quantization_config", "on_disk"}
    if set(vectors.keys()).issubset(scalar_vector_keys):
        return []

    return sorted(str(key) for key in vectors.keys())


def estimate_vectors_count(collection_info: Dict[str, Any], named_vectors: List[str]) -> int:
    """Estimate vectors count when Qdrant doesn't return a dedicated count."""
    vectors_count = collection_info.get("vectors_count") if isinstance(collection_info, dict) else None
    if isinstance(vectors_count, int):
        return max(0, vectors_count)

    points_count = collection_info.get("points_count") if isinstance(collection_info, dict) else None
    if not isinstance(points_count, int):
        return 0

    multiplier = len(named_vectors) if named_vectors else 1
    return max(0, points_count * multiplier)


def extract_points(result: Any) -> List[Dict[str, Any]]:
    """Extract point records from Qdrant query/scroll/retrieve responses."""
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]

    if isinstance(result, dict):
        points = result.get("points", [])
        if isinstance(points, list):
            return [item for item in points if isinstance(item, dict)]

    return []

