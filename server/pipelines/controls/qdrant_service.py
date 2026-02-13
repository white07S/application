"""Qdrant service for controls embeddings.

Manages embedding upserts and deletions in the controls_embeddings collection.
Each control has a single point with 6 named vectors, identified by a UUID5
derived deterministically from the control_id.

Optimized using Strategy C benchmarks: upload_points with multiprocessing
for 4x faster ingestion compared to sequential upsert.
"""

import asyncio
import uuid
from typing import Callable, Dict, List, Optional, Any

import numpy as np
from qdrant_client import QdrantClient  # Sync client for upload_points
from qdrant_client.models import PointStruct, NamedVector

from server.config.qdrant import get_qdrant_client
from server.logging_config import get_logger
from server.settings import get_settings

logger = get_logger(name=__name__)

# Control-specific embedding configuration
EMBEDDING_DIM = 3072
NAMED_VECTORS: List[str] = [
    "control_title",
    "control_description",
    "evidence_description",
    "local_functional_information",
    "control_as_event",
    "control_as_issues",
]

# Fixed namespace for UUID5 generation (deterministic point IDs)
CONTROLS_UUID_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Optimal batch size from benchmarks (for 3072-dim vectors)
QDRANT_BATCH_SIZE = 256

# Number of parallel workers (CPU cores)
QDRANT_PARALLEL_WORKERS = 6


def get_controls_collection_config() -> Dict[str, Any]:
    """Get the vector configuration for controls collection.

    Returns:
        Dict with 'vectors_config' for collection creation.
    """
    from qdrant_client.models import Distance, VectorParams

    return {
        "vectors_config": {
            name: VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
                on_disk=True,  # Essential for datasets >100k vectors
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
    """Coerce an embedding vector to a list of floats, or return a zero vector.

    Handles numpy arrays, lists, and malformed data gracefully.
    """
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


async def upsert_embeddings(
    control_ids: List[str],
    embedding_data: Dict[str, Dict[str, Any]],
    progress_callback: Optional[Callable] = None,
) -> int:
    """Upsert embeddings for a list of control IDs into Qdrant.

    Uses the optimal Strategy C approach from benchmarks: upload_points with
    multiprocessing for 4x faster ingestion compared to sequential upsert.

    Each control creates ONE Qdrant point with 6 named vectors:
    - control_title
    - control_description
    - evidence_description
    - local_functional_information
    - control_as_event
    - control_as_issues

    When searching, specify the named vector to search against.

    Args:
        control_ids: List of control IDs to upsert.
        embedding_data: Dict mapping control_id -> {feature_name: vector}.
            Each vector is a numpy array or list of floats.
        progress_callback: Optional async callback(step, upserted, total) for
            reporting progress during the upsert.

    Returns:
        Number of points upserted.
    """
    settings = get_settings()
    # Get collection name for controls (e.g., "nfr_connect_controls")
    collection = settings.qdrant_collection

    # Build all points first
    logger.info("Building {} points for Qdrant upload...", len(control_ids))
    points = []
    for cid in control_ids:
        point_id = control_id_to_uuid(cid)
        vectors = {}

        cid_data = embedding_data.get(cid, {})
        for feature_name in NAMED_VECTORS:
            raw_vec = cid_data.get(feature_name)
            vectors[feature_name] = coerce_embedding_vector_or_zero(raw_vec)

        points.append(
            PointStruct(
                id=point_id,
                vector=vectors,
                payload={"control_id": cid},
            )
        )

    total_points = len(points)

    if progress_callback:
        await progress_callback(
            f"Uploading {total_points} points to Qdrant",
            0,
            total_points,
        )

    # Use synchronous client for upload_points (required for multiprocessing)
    logger.info(
        "Starting Qdrant upload_points: batch_size={}, parallel={}, wait=False",
        QDRANT_BATCH_SIZE,
        QDRANT_PARALLEL_WORKERS,
    )

    # Run synchronous upload_points in executor to avoid blocking event loop
    def _sync_upload():
        """Synchronous upload using QdrantClient with multiprocessing."""
        sync_client = QdrantClient(url=settings.qdrant_url, timeout=600)

        # upload_points with wait=True to ensure completion
        # This is slower but gives us certainty that points are uploaded
        sync_client.upload_points(
            collection_name=collection,
            points=points,
            batch_size=QDRANT_BATCH_SIZE,
            parallel=QDRANT_PARALLEL_WORKERS,
            wait=True,  # Wait for confirmation to track progress properly
            max_retries=3,
        )

        # Close the sync client
        sync_client.close()
        return total_points

    # Execute in thread pool to avoid blocking async event loop
    loop = asyncio.get_event_loop()

    # Start the upload
    logger.info("Uploading {} points to Qdrant (this may take a while)...", total_points)
    points_uploaded = await loop.run_in_executor(None, _sync_upload)

    # Report completion
    if progress_callback:
        await progress_callback(
            f"Upload complete, waiting for indexing...",
            points_uploaded,
            total_points,
        )

    logger.info("Qdrant upload complete: {} points uploaded", points_uploaded)
    return points_uploaded


async def optimize_collection_for_ingestion(collection_name: str = None) -> None:
    """Optimize Qdrant collection settings for bulk ingestion.

    Based on benchmarks: Disables HNSW indexing during bulk load for faster ingestion.
    Should be called before bulk ingestion, paired with restore_collection_after_ingestion().

    Args:
        collection_name: Collection to optimize. Uses default from settings if not provided.
    """
    settings = get_settings()
    collection = collection_name or settings.qdrant_collection

    try:
        from qdrant_client.models import HnswConfigDiff, OptimizersConfigDiff

        logger.info("Optimizing collection '{}' for bulk ingestion...", collection)

        # Use sync client for collection updates
        def _sync_optimize():
            sync_client = QdrantClient(url=settings.qdrant_url, timeout=60)

            # Disable HNSW indexing and optimize for bulk loading
            sync_client.update_collection(
                collection_name=collection,
                hnsw_config=HnswConfigDiff(
                    m=0,  # Disable HNSW during ingestion
                    ef_construct=128,
                ),
                optimizers_config=OptimizersConfigDiff(
                    indexing_threshold=0,  # Defer all indexing
                    max_segment_size=500_000,
                    memmap_threshold=10_000,  # Aggressive memmap
                ),
            )
            sync_client.close()

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_optimize)

        logger.info("Collection optimized for bulk ingestion (HNSW disabled)")
    except Exception as e:
        logger.warning("Could not optimize collection for ingestion: {}", e)


async def restore_collection_after_ingestion(collection_name: str = None) -> None:
    """Restore optimal Qdrant collection settings after bulk ingestion.

    Re-enables HNSW indexing for fast searches and waits for indexing to complete.
    Should be called after bulk ingestion completes.

    Args:
        collection_name: Collection to restore. Uses default from settings if not provided.
    """
    settings = get_settings()
    collection = collection_name or settings.qdrant_collection

    try:
        from qdrant_client.models import HnswConfigDiff, OptimizersConfigDiff

        logger.info("Restoring collection '{}' after bulk ingestion...", collection)

        # Use sync client for collection updates
        def _sync_restore():
            sync_client = QdrantClient(url=settings.qdrant_url, timeout=60)

            # Re-enable HNSW for fast searches
            sync_client.update_collection(
                collection_name=collection,
                hnsw_config=HnswConfigDiff(
                    m=16,  # Re-enable HNSW with optimal settings
                    ef_construct=128,
                ),
                optimizers_config=OptimizersConfigDiff(
                    indexing_threshold=20_000,
                    max_segment_size=500_000,
                ),
            )
            sync_client.close()

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_restore)

        logger.info("Collection restored (HNSW re-enabled for fast searches)")
    except Exception as e:
        logger.warning("Could not restore collection settings: {}", e)


async def wait_for_collection_green(
    collection_name: str = None,
    max_wait_seconds: int = 600,
    poll_interval: int = 5,
    progress_callback: Optional[Callable] = None,
) -> bool:
    """Wait for Qdrant collection status to turn green (indexing complete).

    Args:
        collection_name: Collection to check. Uses default from settings if not provided.
        max_wait_seconds: Maximum time to wait for indexing (default: 10 minutes).
        poll_interval: Seconds between status checks (default: 5).
        progress_callback: Optional callback for progress updates.

    Returns:
        True if collection turned green, False if timeout.
    """
    settings = get_settings()
    collection = collection_name or settings.qdrant_collection

    logger.info("Waiting for Qdrant collection '{}' to finish indexing...", collection)

    start_time = asyncio.get_event_loop().time()
    checks = 0
    last_status = None

    def _check_status():
        """Check collection status synchronously."""
        sync_client = QdrantClient(url=settings.qdrant_url, timeout=60)
        try:
            info = sync_client.get_collection(collection)

            # Get status
            if hasattr(info, 'status'):
                if hasattr(info.status, 'value'):
                    status = info.status.value
                else:
                    status = str(info.status).lower()
            else:
                status = "unknown"

            # Get counts
            points_count = getattr(info, 'points_count', 0)

            # Try to get indexed count (may not be available)
            indexed_vectors_count = getattr(info, 'indexed_vectors_count', None)

            # Convert indexed_vectors_count to indexed_points_count
            # Since we have 6 named vectors per point, we need to handle this carefully
            indexed_points_count = None
            if indexed_vectors_count is not None and indexed_vectors_count > 0:
                # Each point has 6 named vectors
                num_named_vectors = len(NAMED_VECTORS)  # Should be 6

                # Log raw values for debugging
                logger.debug(
                    "Qdrant raw counts - vectors: {}, points: {}, named_vectors: {}",
                    indexed_vectors_count, points_count, num_named_vectors
                )

                # Try to determine if indexed_vectors_count is counting vectors or something else
                if indexed_vectors_count <= points_count:
                    # Likely counting points already
                    indexed_points_count = indexed_vectors_count
                elif indexed_vectors_count <= (points_count * num_named_vectors):
                    # Likely counting individual vectors across all named vectors
                    indexed_points_count = indexed_vectors_count // num_named_vectors
                else:
                    # Something unexpected - cap at points_count
                    logger.warning(
                        "Unexpected indexed_vectors_count: {} for {} points with {} named vectors",
                        indexed_vectors_count, points_count, num_named_vectors
                    )
                    indexed_points_count = points_count if status == "green" else points_count // 2

                # Final sanity check - indexed points should never exceed total points
                indexed_points_count = min(indexed_points_count, points_count)

            elif status == "green":
                # If green and no indexed count, assume all indexed
                indexed_points_count = points_count

            return status, points_count, indexed_points_count
        finally:
            sync_client.close()

    while True:
        # Check status
        loop = asyncio.get_event_loop()
        status, points_count, indexed_points_count = await loop.run_in_executor(None, _check_status)
        checks += 1

        # Log status changes
        if status != last_status:
            logger.info(
                "Qdrant status changed: {} -> {} (points: {}, indexed: {})",
                last_status, status, points_count, indexed_points_count
            )
            last_status = status

        if status == "green":
            logger.info("Qdrant collection is GREEN - indexing complete!")
            if progress_callback:
                await progress_callback(
                    "Qdrant indexing complete",
                    points_count,
                    points_count,
                )
            return True

        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait_seconds:
            logger.warning(
                "Timeout waiting for Qdrant indexing after {}s (status: {})",
                max_wait_seconds, status
            )
            return False

        # Report progress
        if progress_callback:
            if status == "yellow" and indexed_points_count is not None:
                # We have actual indexing progress
                pct = min(100.0, (indexed_points_count / points_count) * 100) if points_count > 0 else 0
                await progress_callback(
                    f"Qdrant indexing: {indexed_points_count}/{points_count} points ({pct:.1f}%)",
                    indexed_points_count,
                    points_count,
                )
            elif status == "yellow":
                # Indexing in progress, but we don't know exact progress
                await progress_callback(
                    f"Qdrant indexing in progress (status: {status})",
                    0,
                    points_count,
                )
            else:
                await progress_callback(
                    f"Waiting for Qdrant (status: {status})",
                    0,
                    points_count,
                )

        # Wait before next check
        await asyncio.sleep(poll_interval)


async def delete_points(control_ids: List[str]) -> int:
    """Delete Qdrant points for the given control IDs.

    NOTE: Currently unused — reserved for future re-ingest / delete workflows.

    Returns:
        Number of points requested for deletion.
    """
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
    """Get Qdrant collection stats for the DevData UI.

    Returns:
        Dict with collection info including indexing progress, or None if collection doesn't exist.
    """
    try:
        settings = get_settings()

        def _get_info():
            sync_client = QdrantClient(url=settings.qdrant_url, timeout=60)
            try:
                info = sync_client.get_collection(settings.qdrant_collection)

                # Get status (handle different Qdrant client versions)
                if hasattr(info, 'status'):
                    if hasattr(info.status, 'value'):
                        status = info.status.value
                    else:
                        status = str(info.status)
                else:
                    status = "unknown"

                # Get points count
                points_count = getattr(info, 'points_count', 0)

                # Calculate total vectors (points × named vectors)
                # Each point has 6 named vectors
                vectors_count = points_count * len(NAMED_VECTORS)

                # Try to get indexed vectors count (may not be available)
                indexed_vectors_count = getattr(info, 'indexed_vectors_count', None)

                # Calculate indexing progress if available
                indexing_progress = None
                if indexed_vectors_count is not None and points_count > 0:
                    indexing_progress = round((indexed_vectors_count / points_count) * 100, 1)

                result = {
                    "collection_name": settings.qdrant_collection,
                    "points_count": points_count,
                    "vectors_count": vectors_count,
                    "status": status,
                    "named_vectors": NAMED_VECTORS,
                }

                # Add indexing info if status is yellow and we have the data
                if status == "yellow" and indexing_progress is not None:
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
