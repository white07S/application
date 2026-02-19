"""Qdrant service for controls embeddings.

Manages embedding upserts and deletions in the controls_embeddings collection.
Each control has a single point with 6 named vectors, identified by a UUID5
derived deterministically from the control_id.

Supports per-feature delta detection: only re-uploads vectors whose hash
changed, using hashes stored in each point's payload.
"""

import asyncio
import uuid
from typing import Callable, Dict, List, Optional, Any, Set, Tuple

import numpy as np
from qdrant_client import QdrantClient  # Sync client for upload_points
from qdrant_client.models import PointStruct

from server.config.qdrant import get_qdrant_client
from server.logging_config import get_logger
from server.pipelines.controls.model_runners.common import FEATURE_NAMES, HASH_COLUMN_NAMES, MASK_COLUMN_NAMES
from server.settings import get_settings

logger = get_logger(name=__name__)

# Control-specific embedding configuration
EMBEDDING_DIM = 3072
NAMED_VECTORS: List[str] = FEATURE_NAMES

# Fixed namespace for UUID5 generation (deterministic point IDs)
CONTROLS_UUID_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Batch size for Qdrant upserts.
# Each point has 6 named vectors × 3072 dims. JSON-serialized floats use
# ~8-10 bytes each, so per point ≈ 6×3072×10 ≈ 184 KB.
# Qdrant default payload limit is 32 MB → 32000/184 ≈ 170 points max.
QDRANT_BATCH_SIZE = 64

# Number of parallel workers (CPU cores)
QDRANT_PARALLEL_WORKERS = 6

# Threshold: only disable/re-enable HNSW for bulk loads above this size
HNSW_TOGGLE_THRESHOLD = 500


def get_controls_collection_config() -> Dict[str, Any]:
    """Get the vector configuration for controls collection."""
    from qdrant_client.models import Distance, VectorParams

    return {
        "vectors_config": {
            name: VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
                on_disk=True,
            )
            for name in NAMED_VECTORS
        }
    }


def control_id_to_uuid(control_id: str) -> str:
    """Convert a control_id to a deterministic UUID5 string."""
    return str(uuid.uuid5(CONTROLS_UUID_NAMESPACE, control_id))


def coerce_embedding_vector_or_zero(
    vector: Any,
    dim: int = EMBEDDING_DIM,
) -> List[float]:
    """Coerce an embedding vector to a list of floats, or return a zero vector."""
    if vector is None:
        return [0.0] * dim

    try:
        if isinstance(vector, np.ndarray):
            arr = vector.astype(float).flatten().tolist()
        elif isinstance(vector, (list, tuple)):
            arr = [float(x) for x in vector]
        else:
            return [0.0] * dim

        if len(arr) != dim:
            logger.warning(
                "Embedding dimension mismatch: expected {}, got {}. Using zero vector.",
                dim, len(arr),
            )
            return [0.0] * dim

        return arr
    except (ValueError, TypeError) as e:
        logger.warning("Failed to coerce embedding vector: {}. Using zero vector.", e)
        return [0.0] * dim


# ── Hash-based delta detection ──────────────────────────────────────


async def read_current_hashes() -> Dict[str, Dict[str, Optional[str]]]:
    """Read current per-feature hashes from all Qdrant point payloads.

    Returns:
        Dict mapping control_id → {hash_control_title: ..., hash_control_description: ..., ...}
    """
    settings = get_settings()
    collection = settings.qdrant_collection

    result: Dict[str, Dict[str, Optional[str]]] = {}

    def _scroll_all():
        sync_client = QdrantClient(url=settings.qdrant_url, timeout=120)
        try:
            offset = None
            while True:
                points, next_offset = sync_client.scroll(
                    collection_name=collection,
                    limit=1000,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                for point in points:
                    payload = point.payload or {}
                    cid = payload.get("control_id")
                    if not isinstance(cid, str):
                        continue
                    hashes = {}
                    for hash_col in HASH_COLUMN_NAMES:
                        hashes[hash_col] = payload.get(hash_col)
                    for mask_col in MASK_COLUMN_NAMES:
                        hashes[mask_col] = payload.get(mask_col, True)
                    result[cid] = hashes

                if next_offset is None:
                    break
                offset = next_offset
        finally:
            sync_client.close()

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _scroll_all)

    logger.info("Read current hashes from Qdrant: {} controls", len(result))
    return result


def compute_embedding_delta(
    incoming_hashes: Dict[str, Dict[str, Optional[str]]],
    current_hashes: Dict[str, Dict[str, Optional[str]]],
) -> Tuple[
    Set[str],                           # new_control_ids: full upsert
    Dict[str, List[str]],               # changed_features: {cid → [feature_names]}
    Set[str],                           # unchanged_control_ids
]:
    """Compare incoming vs current per-feature hashes to determine what needs updating.

    Returns:
        - new_control_ids: Controls not in Qdrant → need full 6-vector upsert
        - changed_features: Controls with some features changed → need per-feature update
        - unchanged_control_ids: No changes needed
    """
    new_controls: Set[str] = set()
    changed_features: Dict[str, List[str]] = {}
    unchanged: Set[str] = set()

    for cid, incoming in incoming_hashes.items():
        current = current_hashes.get(cid)

        if current is None:
            # Control not in Qdrant → full upsert
            new_controls.add(cid)
            continue

        # Compare each feature hash
        features_changed: List[str] = []
        for feat_name, hash_col in zip(FEATURE_NAMES, HASH_COLUMN_NAMES):
            incoming_hash = incoming.get(hash_col)
            current_hash = current.get(hash_col)
            if incoming_hash != current_hash:
                features_changed.append(feat_name)

        if features_changed:
            changed_features[cid] = features_changed
        else:
            unchanged.add(cid)

    logger.info(
        "Embedding delta: {} new, {} changed, {} unchanged",
        len(new_controls), len(changed_features), len(unchanged),
    )
    return new_controls, changed_features, unchanged


# ── Upsert functions ────────────────────────────────────────────────


async def upsert_new_controls(
    control_ids: List[str],
    embedding_data: Dict[str, Dict[str, Any]],
    hashes: Dict[str, Dict[str, Optional[str]]],
    progress_callback: Optional[Callable] = None,
) -> int:
    """Upsert full points for new controls (all 6 vectors + payload with hashes).

    Returns number of points upserted.
    """
    if not control_ids:
        return 0

    settings = get_settings()
    collection = settings.qdrant_collection

    points = []
    for cid in control_ids:
        point_id = control_id_to_uuid(cid)
        vectors = {}
        cid_data = embedding_data.get(cid, {})
        for feature_name in NAMED_VECTORS:
            raw_vec = cid_data.get(feature_name)
            vectors[feature_name] = coerce_embedding_vector_or_zero(raw_vec)

        # Payload: control_id + 6 per-feature hashes + 6 feature masks
        payload: Dict[str, Any] = {"control_id": cid}
        cid_hashes = hashes.get(cid, {})
        for hash_col in HASH_COLUMN_NAMES:
            payload[hash_col] = cid_hashes.get(hash_col)
        for mask_col in MASK_COLUMN_NAMES:
            payload[mask_col] = cid_hashes.get(mask_col, True)

        points.append(PointStruct(id=point_id, vector=vectors, payload=payload))

    total_points = len(points)
    use_hnsw_toggle = total_points > HNSW_TOGGLE_THRESHOLD

    if use_hnsw_toggle:
        await optimize_collection_for_ingestion()

    if progress_callback:
        await progress_callback(f"Uploading {total_points} new points", 0, total_points)

    def _sync_upload():
        sync_client = QdrantClient(url=settings.qdrant_url, timeout=600)
        sync_client.upload_points(
            collection_name=collection,
            points=points,
            batch_size=QDRANT_BATCH_SIZE,
            parallel=QDRANT_PARALLEL_WORKERS,
            wait=True,
            max_retries=3,
        )
        sync_client.close()
        return total_points

    loop = asyncio.get_event_loop()
    uploaded = await loop.run_in_executor(None, _sync_upload)

    if use_hnsw_toggle:
        await restore_collection_after_ingestion()

    if progress_callback:
        await progress_callback(f"Uploaded {uploaded} new points", uploaded, total_points)

    logger.info("Upserted {} new control points to Qdrant", uploaded)
    return uploaded


async def update_changed_features(
    changed_features: Dict[str, List[str]],
    embedding_data: Dict[str, Dict[str, Any]],
    hashes: Dict[str, Dict[str, Optional[str]]],
    progress_callback: Optional[Callable] = None,
) -> int:
    """Update only the changed named vectors + payload hashes for existing controls.

    Returns number of controls updated.
    """
    if not changed_features:
        return 0

    settings = get_settings()
    collection = settings.qdrant_collection

    # For controls with changed features, we upsert full points (simpler and
    # Qdrant handles it efficiently — the unchanged vectors remain the same
    # because we pass them through from the NPZ)
    points = []
    for cid, features in changed_features.items():
        point_id = control_id_to_uuid(cid)
        vectors = {}
        cid_data = embedding_data.get(cid, {})
        for feature_name in NAMED_VECTORS:
            raw_vec = cid_data.get(feature_name)
            vectors[feature_name] = coerce_embedding_vector_or_zero(raw_vec)

        payload: Dict[str, Any] = {"control_id": cid}
        cid_hashes = hashes.get(cid, {})
        for hash_col in HASH_COLUMN_NAMES:
            payload[hash_col] = cid_hashes.get(hash_col)
        for mask_col in MASK_COLUMN_NAMES:
            payload[mask_col] = cid_hashes.get(mask_col, True)

        points.append(PointStruct(id=point_id, vector=vectors, payload=payload))

    total = len(points)

    if progress_callback:
        await progress_callback(f"Updating {total} changed controls", 0, total)

    def _sync_upsert():
        sync_client = QdrantClient(url=settings.qdrant_url, timeout=600)
        sync_client.upload_points(
            collection_name=collection,
            points=points,
            batch_size=QDRANT_BATCH_SIZE,
            parallel=min(QDRANT_PARALLEL_WORKERS, 2),  # fewer workers for small batches
            wait=True,
            max_retries=3,
        )
        sync_client.close()

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_upsert)

    if progress_callback:
        await progress_callback(f"Updated {total} changed controls", total, total)

    logger.info("Updated {} controls with changed features in Qdrant", total)
    return total


# ── Collection management ───────────────────────────────────────────


async def optimize_collection_for_ingestion(collection_name: str = None) -> None:
    """Disable HNSW indexing for bulk load. Only used for large uploads (>500 points)."""
    settings = get_settings()
    collection = collection_name or settings.qdrant_collection

    try:
        from qdrant_client.models import HnswConfigDiff, OptimizersConfigDiff

        logger.info("Optimizing collection '{}' for bulk ingestion...", collection)

        def _sync_optimize():
            sync_client = QdrantClient(url=settings.qdrant_url, timeout=60)
            sync_client.update_collection(
                collection_name=collection,
                hnsw_config=HnswConfigDiff(m=0, ef_construct=128),
                optimizers_config=OptimizersConfigDiff(
                    indexing_threshold=0,
                    max_segment_size=500_000,
                    memmap_threshold=10_000,
                ),
            )
            sync_client.close()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_optimize)
        logger.info("Collection optimized for bulk ingestion (HNSW disabled)")
    except Exception as e:
        logger.warning("Could not optimize collection for ingestion: {}", e)


async def restore_collection_after_ingestion(collection_name: str = None) -> None:
    """Re-enable HNSW indexing after bulk load."""
    settings = get_settings()
    collection = collection_name or settings.qdrant_collection

    try:
        from qdrant_client.models import HnswConfigDiff, OptimizersConfigDiff

        logger.info("Restoring collection '{}' after bulk ingestion...", collection)

        def _sync_restore():
            sync_client = QdrantClient(url=settings.qdrant_url, timeout=60)
            sync_client.update_collection(
                collection_name=collection,
                hnsw_config=HnswConfigDiff(m=16, ef_construct=128),
                optimizers_config=OptimizersConfigDiff(
                    indexing_threshold=20_000,
                    max_segment_size=500_000,
                ),
            )
            sync_client.close()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_restore)
        logger.info("Collection restored (HNSW re-enabled)")
    except Exception as e:
        logger.warning("Could not restore collection settings: {}", e)


async def wait_for_collection_green(
    collection_name: str = None,
    max_wait_seconds: int = 600,
    poll_interval: int = 5,
    progress_callback: Optional[Callable] = None,
) -> bool:
    """Wait for Qdrant collection status to turn green (indexing complete)."""
    settings = get_settings()
    collection = collection_name or settings.qdrant_collection

    logger.info("Waiting for Qdrant collection '{}' to finish indexing...", collection)

    start_time = asyncio.get_event_loop().time()
    last_status = None

    def _check_status():
        sync_client = QdrantClient(url=settings.qdrant_url, timeout=60)
        try:
            info = sync_client.get_collection(collection)
            if hasattr(info, 'status'):
                status = info.status.value if hasattr(info.status, 'value') else str(info.status).lower()
            else:
                status = "unknown"
            points_count = getattr(info, 'points_count', 0)
            indexed_vectors_count = getattr(info, 'indexed_vectors_count', None)

            indexed_points_count = None
            if indexed_vectors_count is not None and indexed_vectors_count > 0:
                num_named_vectors = len(NAMED_VECTORS)
                if indexed_vectors_count <= points_count:
                    indexed_points_count = indexed_vectors_count
                elif indexed_vectors_count <= (points_count * num_named_vectors):
                    indexed_points_count = indexed_vectors_count // num_named_vectors
                else:
                    indexed_points_count = points_count if status == "green" else points_count // 2
                indexed_points_count = min(indexed_points_count, points_count)
            elif status == "green":
                indexed_points_count = points_count

            return status, points_count, indexed_points_count
        finally:
            sync_client.close()

    while True:
        loop = asyncio.get_event_loop()
        status, points_count, indexed_points_count = await loop.run_in_executor(None, _check_status)

        if status != last_status:
            logger.info(
                "Qdrant status: {} -> {} (points: {}, indexed: {})",
                last_status, status, points_count, indexed_points_count
            )
            last_status = status

        if status == "green":
            logger.info("Qdrant collection is GREEN - indexing complete!")
            if progress_callback:
                await progress_callback("Qdrant indexing complete", points_count, points_count)
            return True

        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait_seconds:
            logger.warning("Timeout waiting for Qdrant indexing after {}s", max_wait_seconds)
            return False

        if progress_callback:
            if status == "yellow" and indexed_points_count is not None:
                pct = min(100.0, (indexed_points_count / points_count) * 100) if points_count > 0 else 0
                await progress_callback(
                    f"Qdrant indexing: {indexed_points_count}/{points_count} ({pct:.1f}%)",
                    indexed_points_count, points_count,
                )
            else:
                await progress_callback(f"Waiting for Qdrant (status: {status})", 0, points_count)

        await asyncio.sleep(poll_interval)


async def delete_points(control_ids: List[str]) -> int:
    """Delete Qdrant points for the given control IDs."""
    if not control_ids:
        return 0

    client = get_qdrant_client()
    settings = get_settings()
    collection = settings.qdrant_collection

    point_ids = [control_id_to_uuid(cid) for cid in control_ids]

    await client.delete(
        collection_name=collection,
        points_selector=point_ids,
    )

    logger.info("Qdrant deleted {} points", len(point_ids))
    return len(point_ids)


async def get_collection_info() -> Optional[Dict[str, Any]]:
    """Get Qdrant collection stats for the DevData UI."""
    try:
        settings = get_settings()

        def _get_info():
            sync_client = QdrantClient(url=settings.qdrant_url, timeout=60)
            try:
                info = sync_client.get_collection(settings.qdrant_collection)
                if hasattr(info, 'status'):
                    status = info.status.value if hasattr(info.status, 'value') else str(info.status)
                else:
                    status = "unknown"
                points_count = getattr(info, 'points_count', 0)
                vectors_count = points_count * len(NAMED_VECTORS)
                indexed_vectors_count = getattr(info, 'indexed_vectors_count', None)

                result = {
                    "collection_name": settings.qdrant_collection,
                    "points_count": points_count,
                    "vectors_count": vectors_count,
                    "status": status,
                    "named_vectors": NAMED_VECTORS,
                }

                if status == "yellow" and indexed_vectors_count is not None:
                    indexing_progress = round((indexed_vectors_count / points_count) * 100, 1) if points_count > 0 else 0
                    result["indexing_progress"] = indexing_progress
                    result["indexed_vectors_count"] = indexed_vectors_count

                return result
            finally:
                sync_client.close()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_info)

    except Exception as e:
        logger.warning("Failed to get Qdrant collection info: {}", e)
        return None
