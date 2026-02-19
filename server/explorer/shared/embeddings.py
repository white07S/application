"""OpenAI embedding utility for semantic search queries."""

from __future__ import annotations

import logging

import httpx

from server.settings import get_settings

logger = logging.getLogger(__name__)

_EMBED_MODEL = "text-embedding-3-large"
_EMBED_DIMENSIONS = 3072
_EMBED_URL = "https://api.openai.com/v1/embeddings"


async def embed_query(
    query: str,
    *,
    graph_token: str | None = None,
) -> list[float]:
    """Embed a single query string using OpenAI text-embedding-3-large.

    Returns a 3072-dimensional float vector.

    Raises RuntimeError if OPENAI_API_KEY is not configured.
    """
    api_key = get_settings().openai_api_key
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set in .env — semantic search is unavailable"
        )

    logger.debug("embed_query: model=%s len=%d graph_token=%s", _EMBED_MODEL, len(query), bool(graph_token))

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _EMBED_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": _EMBED_MODEL,
                "input": query,
                "dimensions": _EMBED_DIMENSIONS,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    embedding: list[float] = data["data"][0]["embedding"]
    logger.debug("embed_query: received %d-dim vector", len(embedding))
    return embedding
