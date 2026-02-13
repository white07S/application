"""Qdrant vector database connection management.

Manages the async Qdrant client lifecycle for all collections.
"""

from typing import Any, Dict, Optional

from qdrant_client import AsyncQdrantClient

from server.logging_config import get_logger

logger = get_logger(name=__name__)

_client: AsyncQdrantClient | None = None


async def init_qdrant(url: str, collection_prefix: str = "nfr_connect") -> None:
    """Initialize the Qdrant client and ensure collections exist.

    Args:
        url: Qdrant server URL
        collection_prefix: Prefix for collection names (e.g., 'nfr_connect')
    """
    global _client
    _client = AsyncQdrantClient(url=url)

    # Initialize controls collection
    await _ensure_controls_collection(collection_prefix)

    # Future collections can be added here:
    # await _ensure_issues_collection(collection_prefix)
    # await _ensure_actions_collection(collection_prefix)


async def _ensure_controls_collection(collection_prefix: str) -> None:
    """Ensure the controls collection exists with proper configuration.

    Args:
        collection_prefix: Prefix for collection names
    """
    # Import here to avoid circular dependency
    from server.pipelines.controls.qdrant_service import get_controls_collection_config

    collection_name = f"{collection_prefix}_controls"

    collections = await _client.get_collections()
    existing = [c.name for c in collections.collections]

    if collection_name not in existing:
        config = get_controls_collection_config()
        await _client.create_collection(
            collection_name=collection_name,
            **config
        )
        logger.info("Created Qdrant collection '{}' with controls-specific configuration",
                    collection_name)
    else:
        logger.info("Qdrant collection '{}' already exists", collection_name)


def get_qdrant_client() -> AsyncQdrantClient:
    """Get the global Qdrant client. Raises if not initialized."""
    if _client is None:
        raise RuntimeError(
            "Qdrant client not initialized. Call init_qdrant() first."
        )
    return _client


async def close_qdrant() -> None:
    """Close the Qdrant client connection."""
    global _client
    if _client is not None:
        await _client.close()
        logger.info("Qdrant client closed")
    _client = None
