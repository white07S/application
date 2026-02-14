"""Read-only service orchestration for DevData Qdrant browser."""

from __future__ import annotations

import re
import time
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import Counter

from fastapi.responses import StreamingResponse

from server.devdata_qdrant.mappers import (
    estimate_vectors_count,
    extract_collection_names,
    extract_named_vectors,
    extract_points,
    unwrap_qdrant_result,
)
from server.devdata_qdrant.service.qdrant_read_gateway import (
    QdrantGatewayError,
    get_json,
    post_json,
    stream_get,
)
from server.logging_config import get_logger

logger = get_logger(name=__name__)

_COLLECTION_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MAX_TIMEOUT_SECONDS = 90
_MAX_SCROLL_LIMIT = 500
_MAX_QUERY_LIMIT = 500
_MAX_RETRIEVE_IDS = 500
_MAX_FACET_LIMIT = 100
_MAX_MATRIX_LIMIT = 200
_MAX_MATRIX_SAMPLE = 1000
_MAX_INSIGHT_SAMPLE = 5000
_COLLECTION_CACHE_TTL_SECONDS = 10.0
_collection_cache_names: Set[str] = set()
_collection_cache_expires_at: float = 0.0

# Keys we should never accept inside read-only requests.
_MUTATION_KEYS: Set[str] = {
    "upsert",
    "delete",
    "delete_alias",
    "create_alias",
    "move_shard",
    "abort_resharding",
    "start_resharding",
    "set_payload",
    "delete_payload",
    "overwrite_payload",
    "clear_payload",
    "set_vectors",
    "delete_vectors",
    "create_snapshot",
    "delete_snapshot",
    "recover_snapshot",
    "upload_snapshot",
    "update_collection",
    "update_collection_aliases",
}


@dataclass
class DevDataQdrantError(Exception):
    """Stable service error contract used by router responses."""

    code: str
    message: str
    status: int
    details: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "status": self.status,
            "details": self.details,
        }


@dataclass
class _PayloadFieldAccumulator:
    present_count: int = 0
    null_count: int = 0
    empty_count: int = 0
    non_null_types: Set[str] = field(default_factory=set)
    distinct_values: Set[str] = field(default_factory=set)
    value_counts: Counter = field(default_factory=Counter)
    value_examples: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _VectorHealthAccumulator:
    points_seen: int = 0
    present_count: int = 0
    dimension_mismatch_count: int = 0
    unsupported_format_count: int = 0
    zero_vector_count: int = 0
    norms: List[float] = field(default_factory=list)


def _ensure_valid_collection_name(collection_name: str) -> None:
    if not _COLLECTION_NAME_RE.match(collection_name):
        raise DevDataQdrantError(
            code="INVALID_COLLECTION_NAME",
            message="Collection name is invalid",
            status=400,
            details={"collection_name": collection_name},
        )


def _ensure_snapshot_name(snapshot_name: str) -> None:
    if "/" in snapshot_name or "\\" in snapshot_name:
        raise DevDataQdrantError(
            code="INVALID_SNAPSHOT_NAME",
            message="Snapshot name is invalid",
            status=400,
            details={"snapshot_name": snapshot_name},
        )


def _coerce_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DevDataQdrantError(
            code="INVALID_REQUEST",
            message=f"'{field_name}' must be an integer",
            status=422,
            details={"field": field_name, "value": value},
        )
    return value


def _clamp_field(payload: Dict[str, Any], *, field_name: str, min_value: int, max_value: int) -> None:
    if field_name not in payload or payload[field_name] is None:
        return

    current = _coerce_int(payload[field_name], field_name=field_name)
    if current < min_value:
        raise DevDataQdrantError(
            code="INVALID_REQUEST",
            message=f"'{field_name}' must be >= {min_value}",
            status=422,
            details={"field": field_name, "value": current},
        )
    if current > max_value:
        payload[field_name] = max_value


def _find_mutation_key(candidate: Any) -> Optional[str]:
    if isinstance(candidate, dict):
        for key, value in candidate.items():
            lowered = str(key).lower()
            if lowered in _MUTATION_KEYS:
                return lowered
            nested = _find_mutation_key(value)
            if nested:
                return nested
    elif isinstance(candidate, list):
        for item in candidate:
            nested = _find_mutation_key(item)
            if nested:
                return nested
    return None


def _sanitize_read_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    found_key = _find_mutation_key(payload)
    if found_key:
        raise DevDataQdrantError(
            code="QDRANT_READ_ONLY_VIOLATION",
            message=f"Mutation-like key '{found_key}' is not allowed in read-only endpoints",
            status=400,
            details={"key": found_key},
        )
    return payload


def _sanitize_scroll_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = _sanitize_read_payload(dict(payload))
    _clamp_field(sanitized, field_name="limit", min_value=1, max_value=_MAX_SCROLL_LIMIT)
    _clamp_field(sanitized, field_name="timeout", min_value=1, max_value=_MAX_TIMEOUT_SECONDS)
    return sanitized


def _sanitize_query_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = _sanitize_read_payload(dict(payload))
    _clamp_field(sanitized, field_name="limit", min_value=1, max_value=_MAX_QUERY_LIMIT)
    _clamp_field(sanitized, field_name="timeout", min_value=1, max_value=_MAX_TIMEOUT_SECONDS)
    return sanitized


def _sanitize_retrieve_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = _sanitize_read_payload(dict(payload))
    _clamp_field(sanitized, field_name="timeout", min_value=1, max_value=_MAX_TIMEOUT_SECONDS)

    ids = sanitized.get("ids")
    if ids is not None:
        if not isinstance(ids, list):
            raise DevDataQdrantError(
                code="INVALID_REQUEST",
                message="'ids' must be a list",
                status=422,
                details={"field": "ids"},
            )
        sanitized["ids"] = ids[:_MAX_RETRIEVE_IDS]

    return sanitized


def _sanitize_facet_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = _sanitize_read_payload(dict(payload))
    _clamp_field(sanitized, field_name="limit", min_value=1, max_value=_MAX_FACET_LIMIT)
    _clamp_field(sanitized, field_name="timeout", min_value=1, max_value=_MAX_TIMEOUT_SECONDS)
    return sanitized


def _sanitize_matrix_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = _sanitize_read_payload(dict(payload))
    _clamp_field(sanitized, field_name="limit", min_value=1, max_value=_MAX_MATRIX_LIMIT)
    _clamp_field(sanitized, field_name="sample", min_value=1, max_value=_MAX_MATRIX_SAMPLE)
    _clamp_field(sanitized, field_name="timeout", min_value=1, max_value=_MAX_TIMEOUT_SECONDS)
    return sanitized


def _sanitize_insights_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = _sanitize_read_payload(dict(payload))

    sample_limit_value = sanitized.get("sample_limit", 1000)
    if sample_limit_value is None:
        sample_limit_value = 1000
    sample_limit = _coerce_int(sample_limit_value, field_name="sample_limit")
    if sample_limit < 1:
        raise DevDataQdrantError(
            code="INVALID_REQUEST",
            message="'sample_limit' must be >= 1",
            status=422,
            details={"field": "sample_limit", "value": sample_limit},
        )
    sample_limit = min(sample_limit, _MAX_INSIGHT_SAMPLE)

    request_payload: Dict[str, Any] = {"sample_limit": sample_limit}

    filter_payload = sanitized.get("filter")
    if filter_payload is not None:
        if not isinstance(filter_payload, dict):
            raise DevDataQdrantError(
                code="INVALID_REQUEST",
                message="'filter' must be an object",
                status=422,
                details={"field": "filter"},
            )
        request_payload["filter"] = filter_payload

    return request_payload


def _is_cluster_disabled_error(error: QdrantGatewayError) -> bool:
    status = error.upstream_status or error.details.get("upstream_status")
    body = str(error.details.get("upstream_body", "")).lower()
    if status in {400, 404, 501} and "cluster" in body and "disabled" in body:
        return True
    if "distributed mode is disabled" in body:
        return True
    return False


def _map_gateway_error(error: QdrantGatewayError, *, context: str) -> DevDataQdrantError:
    upstream_status = error.upstream_status or error.details.get("upstream_status")
    detail_payload = dict(error.details)
    if upstream_status is not None:
        detail_payload["upstream_status"] = upstream_status
    detail_payload["context"] = context

    if upstream_status == 404:
        return DevDataQdrantError(
            code="QDRANT_NOT_FOUND",
            message="Requested Qdrant resource was not found",
            status=404,
            details=detail_payload,
        )

    if "timed out" in error.message.lower():
        return DevDataQdrantError(
            code="QDRANT_UPSTREAM_TIMEOUT",
            message="Qdrant upstream request timed out",
            status=504,
            details=detail_payload,
        )

    if "unavailable" in error.message.lower():
        return DevDataQdrantError(
            code="QDRANT_UPSTREAM_UNAVAILABLE",
            message="Qdrant upstream is unavailable",
            status=503,
            details=detail_payload,
        )

    return DevDataQdrantError(
        code="QDRANT_UPSTREAM_ERROR",
        message=error.message,
        status=502,
        details=detail_payload,
    )


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


async def _collection_names(*, force_refresh: bool = False) -> Set[str]:
    global _collection_cache_names, _collection_cache_expires_at

    now = time.monotonic()
    if not force_refresh and now < _collection_cache_expires_at:
        return set(_collection_cache_names)

    try:
        payload = await get_json("/collections")
    except QdrantGatewayError as error:
        raise _map_gateway_error(error, context="list_collections")

    names = extract_collection_names(payload)
    _collection_cache_names = set(names)
    _collection_cache_expires_at = now + _COLLECTION_CACHE_TTL_SECONDS
    return set(_collection_cache_names)


async def _ensure_allowed_collection(collection_name: str) -> None:
    _ensure_valid_collection_name(collection_name)
    names = await _collection_names()
    if collection_name in names:
        return

    # Force refresh to avoid stale-cache false negatives.
    refreshed = await _collection_names(force_refresh=True)
    if collection_name not in refreshed:
        raise DevDataQdrantError(
            code="QDRANT_COLLECTION_NOT_FOUND",
            message=f"Collection '{collection_name}' was not found",
            status=404,
            details={"collection_name": collection_name},
        )


async def _fetch_collection_details(*, collection_name: str, context: str) -> Dict[str, Any]:
    try:
        payload = await get_json(f"/collections/{collection_name}")
    except QdrantGatewayError as error:
        raise _map_gateway_error(error, context=context)

    return _safe_dict(unwrap_qdrant_result(payload))


async def _sample_points(
    *,
    collection_name: str,
    sample_limit: int,
    filter_payload: Optional[Dict[str, Any]],
    with_payload: bool,
    with_vector: bool,
    context: str,
) -> List[Dict[str, Any]]:
    sampled_points: List[Dict[str, Any]] = []
    offset: Optional[Any] = None

    while len(sampled_points) < sample_limit:
        batch_limit = min(_MAX_SCROLL_LIMIT, sample_limit - len(sampled_points))
        request_payload: Dict[str, Any] = {
            "limit": batch_limit,
            "with_payload": with_payload,
            "with_vector": with_vector,
        }
        if filter_payload is not None:
            request_payload["filter"] = filter_payload
        if offset is not None:
            request_payload["offset"] = offset

        try:
            response = await post_json(f"/collections/{collection_name}/points/scroll", request_payload)
        except QdrantGatewayError as error:
            raise _map_gateway_error(error, context=context)

        result = unwrap_qdrant_result(response)
        points = extract_points(result)
        if not points:
            break

        sampled_points.extend(points)
        next_offset = result.get("next_page_offset") if isinstance(result, dict) else None
        if next_offset is None:
            break
        offset = next_offset

    return sampled_points[:sample_limit]


def _log_request(*, user: str, endpoint: str, collection: Optional[str] = None) -> None:
    logger.info(
        "devdata_qdrant request user={} endpoint={} collection={}",
        user,
        endpoint,
        collection or "-",
    )


async def list_collections(*, user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="collections_list")
    collection_names = sorted(await _collection_names())
    return {"collections": [{"name": name} for name in collection_names]}


async def get_collection_info(*, collection_name: str, user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="collection_info", collection=collection_name)
    await _ensure_allowed_collection(collection_name)
    result = await _fetch_collection_details(collection_name=collection_name, context="get_collection_info")
    named_vectors = extract_named_vectors(result)
    points_count = result.get("points_count") if isinstance(result.get("points_count"), int) else 0
    vectors_count = estimate_vectors_count(result, named_vectors)

    return {
        "collection_name": collection_name,
        "status": result.get("status"),
        "points_count": points_count,
        "vectors_count": vectors_count,
        "named_vectors": named_vectors,
        "payload_schema": result.get("payload_schema") if isinstance(result.get("payload_schema"), dict) else {},
        "info": result,
    }


async def get_collection_summary(*, collection_name: str, user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="collection_summary", collection=collection_name)
    info = await get_collection_info(collection_name=collection_name, user=user)
    aliases = await list_collection_aliases(collection_name=collection_name, user=user)
    snapshots = await list_collection_snapshots(collection_name=collection_name, user=user)

    return {
        "collection_name": collection_name,
        "status": info.get("status"),
        "points_count": info.get("points_count", 0),
        "vectors_count": info.get("vectors_count", 0),
        "vectors": info.get("named_vectors", []),
        "aliases_count": len(aliases.get("aliases", [])),
        "snapshots_count": len(snapshots.get("snapshots", [])),
    }


async def scroll_points(*, collection_name: str, payload: Dict[str, Any], user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="points_scroll", collection=collection_name)
    await _ensure_allowed_collection(collection_name)
    request_payload = _sanitize_scroll_payload(payload)

    try:
        response = await post_json(f"/collections/{collection_name}/points/scroll", request_payload)
    except QdrantGatewayError as error:
        raise _map_gateway_error(error, context="scroll_points")

    result = unwrap_qdrant_result(response)
    points = extract_points(result)
    next_page_offset = result.get("next_page_offset") if isinstance(result, dict) else None
    return {
        "points": points,
        "next_page_offset": next_page_offset,
        "total_loaded": len(points),
    }


async def query_points(*, collection_name: str, payload: Dict[str, Any], user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="points_query", collection=collection_name)
    await _ensure_allowed_collection(collection_name)
    request_payload = _sanitize_query_payload(payload)

    try:
        response = await post_json(f"/collections/{collection_name}/points/query", request_payload)
    except QdrantGatewayError as error:
        raise _map_gateway_error(error, context="query_points")

    result = unwrap_qdrant_result(response)
    points = extract_points(result)
    return {
        "points": points,
        "total_loaded": len(points),
    }


async def retrieve_points(*, collection_name: str, payload: Dict[str, Any], user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="points_retrieve", collection=collection_name)
    await _ensure_allowed_collection(collection_name)
    request_payload = _sanitize_retrieve_payload(payload)

    try:
        response = await post_json(f"/collections/{collection_name}/points", request_payload)
    except QdrantGatewayError as error:
        raise _map_gateway_error(error, context="retrieve_points")

    result = unwrap_qdrant_result(response)
    points = extract_points(result)
    return {
        "points": points,
        "total_loaded": len(points),
    }


async def facet_values(*, collection_name: str, payload: Dict[str, Any], user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="facet_values", collection=collection_name)
    await _ensure_allowed_collection(collection_name)
    request_payload = _sanitize_facet_payload(payload)

    try:
        response = await post_json(f"/collections/{collection_name}/facet", request_payload)
    except QdrantGatewayError as error:
        raise _map_gateway_error(error, context="facet_values")

    result = unwrap_qdrant_result(response)
    hits = result.get("hits", []) if isinstance(result, dict) else []
    hits = hits if isinstance(hits, list) else []
    return {"hits": hits}


async def list_collection_aliases(*, collection_name: str, user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="collection_aliases", collection=collection_name)
    await _ensure_allowed_collection(collection_name)

    try:
        payload = await get_json(f"/collections/{collection_name}/aliases")
    except QdrantGatewayError as error:
        raise _map_gateway_error(error, context="collection_aliases")

    result = unwrap_qdrant_result(payload)
    aliases = result.get("aliases", []) if isinstance(result, dict) else []
    aliases = aliases if isinstance(aliases, list) else []
    return {"aliases": aliases}


async def list_collection_snapshots(*, collection_name: str, user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="collection_snapshots", collection=collection_name)
    await _ensure_allowed_collection(collection_name)

    try:
        payload = await get_json(f"/collections/{collection_name}/snapshots")
    except QdrantGatewayError as error:
        raise _map_gateway_error(error, context="collection_snapshots")

    result = unwrap_qdrant_result(payload)
    snapshots = result if isinstance(result, list) else []
    return {"snapshots": snapshots}


async def download_snapshot(*, collection_name: str, snapshot_name: str, user: str) -> StreamingResponse:
    _log_request(user=user, endpoint="snapshot_download", collection=collection_name)
    await _ensure_allowed_collection(collection_name)
    _ensure_snapshot_name(snapshot_name)

    try:
        response, client = await stream_get(f"/collections/{collection_name}/snapshots/{snapshot_name}")
    except QdrantGatewayError as error:
        raise _map_gateway_error(error, context="snapshot_download")

    content_type = response.headers.get("content-type") or "application/octet-stream"
    disposition = response.headers.get("content-disposition") or f'attachment; filename="{snapshot_name}"'
    content_length = response.headers.get("content-length")

    headers = {"Content-Disposition": disposition}
    if content_length:
        headers["Content-Length"] = content_length

    async def iterator():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(iterator(), media_type=content_type, headers=headers)


async def cluster_status(*, user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="cluster_status")
    try:
        payload = await get_json("/cluster")
    except QdrantGatewayError as error:
        if _is_cluster_disabled_error(error):
            return {
                "status": "disabled",
                "peers": {},
                "details": {"message": "Distributed mode is not enabled"},
            }
        raise _map_gateway_error(error, context="cluster_status")

    result = _safe_dict(unwrap_qdrant_result(payload))
    peers = result.get("peers") if isinstance(result.get("peers"), dict) else {}
    status = result.get("status")
    return {
        "status": status if isinstance(status, str) else "unknown",
        "peers": peers,
        "details": result,
    }


async def collection_cluster(*, collection_name: str, user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="collection_cluster", collection=collection_name)
    await _ensure_allowed_collection(collection_name)

    try:
        payload = await get_json(f"/collections/{collection_name}/cluster")
    except QdrantGatewayError as error:
        if _is_cluster_disabled_error(error):
            return {
                "status": "disabled",
                "result": {},
                "local_shards": [],
                "remote_shards": [],
            }
        raise _map_gateway_error(error, context="collection_cluster")

    result = _safe_dict(unwrap_qdrant_result(payload))
    local_shards = result.get("local_shards") if isinstance(result.get("local_shards"), list) else []
    remote_shards = result.get("remote_shards") if isinstance(result.get("remote_shards"), list) else []
    return {
        "status": "enabled",
        "result": result,
        "local_shards": local_shards,
        "remote_shards": remote_shards,
    }


async def collection_optimizations(*, collection_name: str, user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="collection_optimizations", collection=collection_name)
    await _ensure_allowed_collection(collection_name)

    try:
        payload = await get_json(
            f"/collections/{collection_name}/optimizations",
            params={"with": "queued,completed,idle_segments"},
        )
    except QdrantGatewayError as error:
        raise _map_gateway_error(error, context="collection_optimizations")

    result = _safe_dict(unwrap_qdrant_result(payload))
    return {"result": result}


def _percent(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _payload_type_label(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _is_empty_payload_value(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, set, tuple)):
        return len(value) == 0
    return False


def _canonical_payload_value(value: Any) -> Tuple[str, Any]:
    if isinstance(value, str):
        return f"str:{value}", value
    if isinstance(value, bool):
        return f"bool:{value}", value
    if isinstance(value, int):
        return f"int:{value}", value
    if isinstance(value, float):
        if math.isnan(value):
            return "float:nan", "nan"
        if math.isinf(value):
            return f"float:{'inf' if value > 0 else '-inf'}", "inf" if value > 0 else "-inf"
        return f"float:{value}", value
    if value is None:
        return "null", None

    try:
        serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except TypeError:
        serialized = str(value)

    display = serialized if len(serialized) <= 180 else f"{serialized[:177]}..."
    return f"json:{serialized}", display


def _to_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isfinite(numeric):
            return numeric
    return None


def _parse_dense_vector(raw_vector: Any) -> Optional[List[float]]:
    if not isinstance(raw_vector, list):
        return None

    parsed: List[float] = []
    for component in raw_vector:
        numeric = _to_number(component)
        if numeric is None:
            return None
        parsed.append(numeric)
    return parsed


def _parse_sparse_vector(raw_vector: Any) -> Optional[Tuple[List[float], Optional[List[int]]]]:
    if not isinstance(raw_vector, dict):
        return None

    values = raw_vector.get("values")
    if not isinstance(values, list):
        return None

    parsed_values: List[float] = []
    for component in values:
        numeric = _to_number(component)
        if numeric is None:
            return None
        parsed_values.append(numeric)

    indices = raw_vector.get("indices")
    if indices is None:
        return parsed_values, None
    if not isinstance(indices, list) or len(indices) != len(parsed_values):
        return None

    parsed_indices: List[int] = []
    for raw_index in indices:
        if isinstance(raw_index, bool) or not isinstance(raw_index, int) or raw_index < 0:
            return None
        parsed_indices.append(raw_index)

    return parsed_values, parsed_indices


def _vector_norm(values: List[float]) -> float:
    return math.sqrt(sum(component * component for component in values))


def _is_zero_vector(values: List[float]) -> bool:
    return all(abs(component) <= 1e-12 for component in values)


def _percentile(sorted_values: List[float], quantile: float) -> Optional[float]:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return round(sorted_values[0], 6)

    index = (len(sorted_values) - 1) * quantile
    lower_index = int(math.floor(index))
    upper_index = int(math.ceil(index))
    if lower_index == upper_index:
        return round(sorted_values[lower_index], 6)

    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    weight = index - lower_index
    return round(lower + (upper - lower) * weight, 6)


def _vector_dimensions(collection_info: Dict[str, Any]) -> Dict[str, Optional[int]]:
    config = collection_info.get("config") if isinstance(collection_info, dict) else None
    params = config.get("params") if isinstance(config, dict) else None
    vectors = params.get("vectors") if isinstance(params, dict) else None

    if not isinstance(vectors, dict):
        return {"default": None}

    if "size" in vectors:
        size = vectors.get("size")
        return {"default": size if isinstance(size, int) and size > 0 else None}

    dimensions: Dict[str, Optional[int]] = {}
    for name, vector_config in vectors.items():
        size: Optional[int] = None
        if isinstance(vector_config, dict):
            candidate = vector_config.get("size")
            if isinstance(candidate, int) and candidate > 0:
                size = candidate
        dimensions[str(name)] = size
    return dimensions or {"default": None}


def _resolve_vector_value(
    *,
    point: Dict[str, Any],
    vector_name: str,
    has_named_vectors: bool,
) -> Any:
    raw_vector = point.get("vector")
    if raw_vector is None:
        return None

    if has_named_vectors:
        if isinstance(raw_vector, dict):
            return raw_vector.get(vector_name)
        return None

    if isinstance(raw_vector, dict):
        if vector_name in raw_vector:
            return raw_vector.get(vector_name)
        if "default" in raw_vector:
            return raw_vector.get("default")
        if len(raw_vector) == 1:
            return next(iter(raw_vector.values()))
        return None

    return raw_vector


async def payload_quality(*, collection_name: str, payload: Dict[str, Any], user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="payload_quality", collection=collection_name)
    await _ensure_allowed_collection(collection_name)
    request_payload = _sanitize_insights_payload(payload)
    sample_limit = request_payload["sample_limit"]
    filter_payload = request_payload.get("filter")

    collection_info = await _fetch_collection_details(
        collection_name=collection_name,
        context="payload_quality_collection_info",
    )
    payload_schema = collection_info.get("payload_schema") if isinstance(collection_info.get("payload_schema"), dict) else {}

    sampled_points = await _sample_points(
        collection_name=collection_name,
        sample_limit=sample_limit,
        filter_payload=filter_payload,
        with_payload=True,
        with_vector=False,
        context="payload_quality_sample",
    )

    sample_points = len(sampled_points)
    accumulators: Dict[str, _PayloadFieldAccumulator] = {
        key: _PayloadFieldAccumulator() for key in payload_schema.keys()
    }

    for point in sampled_points:
        payload_obj = _safe_dict(point.get("payload"))
        for key, value in payload_obj.items():
            accumulator = accumulators.setdefault(key, _PayloadFieldAccumulator())
            accumulator.present_count += 1

            value_type = _payload_type_label(value)
            if value is None:
                accumulator.null_count += 1
                continue

            if _is_empty_payload_value(value):
                accumulator.empty_count += 1

            accumulator.non_null_types.add(value_type)
            value_key, value_example = _canonical_payload_value(value)
            accumulator.distinct_values.add(value_key)
            accumulator.value_counts[value_key] += 1
            accumulator.value_examples.setdefault(value_key, value_example)

    fields: List[Dict[str, Any]] = []
    for field_name in sorted(accumulators.keys()):
        accumulator = accumulators[field_name]
        non_null_count = max(accumulator.present_count - accumulator.null_count, 0)
        top_values: List[Dict[str, Any]] = []
        for value_key, count in accumulator.value_counts.most_common(8):
            top_values.append(
                {
                    "value": accumulator.value_examples.get(value_key),
                    "count": count,
                    "pct": _percent(count, non_null_count),
                }
            )

        type_conflicts = sorted(accumulator.non_null_types) if len(accumulator.non_null_types) > 1 else []
        fields.append(
            {
                "field": field_name,
                "coverage_pct": _percent(accumulator.present_count, sample_points),
                "null_pct": _percent(accumulator.null_count, sample_points),
                "empty_pct": _percent(accumulator.empty_count, sample_points),
                "distinct_count": len(accumulator.distinct_values),
                "top_values": top_values,
                "type_conflicts": type_conflicts,
            }
        )

    return {
        "sample_points": sample_points,
        "fields": fields,
    }


async def vector_health(*, collection_name: str, payload: Dict[str, Any], user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="vector_health", collection=collection_name)
    await _ensure_allowed_collection(collection_name)
    request_payload = _sanitize_insights_payload(payload)
    sample_limit = request_payload["sample_limit"]
    filter_payload = request_payload.get("filter")

    collection_info = await _fetch_collection_details(
        collection_name=collection_name,
        context="vector_health_collection_info",
    )
    named_vectors = extract_named_vectors(collection_info)
    has_named_vectors = len(named_vectors) > 0
    vector_names = named_vectors if has_named_vectors else ["default"]
    expected_dimensions = _vector_dimensions(collection_info)
    for vector_name in vector_names:
        expected_dimensions.setdefault(vector_name, None)

    sampled_points = await _sample_points(
        collection_name=collection_name,
        sample_limit=sample_limit,
        filter_payload=filter_payload,
        with_payload=False,
        with_vector=True,
        context="vector_health_sample",
    )
    sample_points = len(sampled_points)

    accumulators: Dict[str, _VectorHealthAccumulator] = {
        vector_name: _VectorHealthAccumulator(points_seen=sample_points) for vector_name in vector_names
    }

    for point in sampled_points:
        for vector_name in vector_names:
            accumulator = accumulators[vector_name]
            vector_value = _resolve_vector_value(
                point=point,
                vector_name=vector_name,
                has_named_vectors=has_named_vectors,
            )
            if vector_value is None:
                continue

            accumulator.present_count += 1
            expected_dimension = expected_dimensions.get(vector_name)

            dense_values = _parse_dense_vector(vector_value)
            if dense_values is not None:
                if expected_dimension is not None and len(dense_values) != expected_dimension:
                    accumulator.dimension_mismatch_count += 1
                if _is_zero_vector(dense_values):
                    accumulator.zero_vector_count += 1
                accumulator.norms.append(_vector_norm(dense_values))
                continue

            sparse_payload = _parse_sparse_vector(vector_value)
            if sparse_payload is not None:
                sparse_values, sparse_indices = sparse_payload
                if expected_dimension is not None and sparse_indices:
                    if any(index >= expected_dimension for index in sparse_indices):
                        accumulator.dimension_mismatch_count += 1
                if _is_zero_vector(sparse_values):
                    accumulator.zero_vector_count += 1
                accumulator.norms.append(_vector_norm(sparse_values))
                continue

            accumulator.unsupported_format_count += 1

    vectors: List[Dict[str, Any]] = []
    for vector_name in sorted(vector_names):
        accumulator = accumulators[vector_name]
        sorted_norms = sorted(norm for norm in accumulator.norms if math.isfinite(norm))
        vectors.append(
            {
                "vector_name": vector_name,
                "expected_dim": expected_dimensions.get(vector_name),
                "points_seen": accumulator.points_seen,
                "present_count": accumulator.present_count,
                "missing_rate_pct": _percent(accumulator.points_seen - accumulator.present_count, accumulator.points_seen),
                "dimension_mismatch_count": accumulator.dimension_mismatch_count,
                "unsupported_format_count": accumulator.unsupported_format_count,
                "zero_vector_rate_pct": _percent(accumulator.zero_vector_count, accumulator.present_count),
                "norm_percentiles": {
                    "p05": _percentile(sorted_norms, 0.05),
                    "p25": _percentile(sorted_norms, 0.25),
                    "p50": _percentile(sorted_norms, 0.50),
                    "p75": _percentile(sorted_norms, 0.75),
                    "p95": _percentile(sorted_norms, 0.95),
                },
            }
        )

    return {
        "sample_points": sample_points,
        "vectors": vectors,
    }


async def matrix_pairs(*, collection_name: str, payload: Dict[str, Any], user: str) -> Dict[str, Any]:
    _log_request(user=user, endpoint="matrix_pairs", collection=collection_name)
    await _ensure_allowed_collection(collection_name)
    request_payload = _sanitize_matrix_payload(payload)

    try:
        response = await post_json(
            f"/collections/{collection_name}/points/search/matrix/pairs",
            request_payload,
        )
    except QdrantGatewayError as error:
        upstream_status = error.upstream_status or error.details.get("upstream_status")
        if upstream_status == 404:
            raise DevDataQdrantError(
                code="QDRANT_FEATURE_UNAVAILABLE",
                message="Matrix pairs endpoint is unavailable on the connected Qdrant version",
                status=501,
                details={"endpoint": "points/search/matrix/pairs"},
            )
        raise _map_gateway_error(error, context="matrix_pairs")

    result = unwrap_qdrant_result(response)
    pairs = result.get("pairs", []) if isinstance(result, dict) else []
    pairs = pairs if isinstance(pairs, list) else []
    return {"pairs": pairs}
