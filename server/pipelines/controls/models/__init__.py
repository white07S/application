"""Model Run Module.

This module provides the complete model pipeline for controls processing:
- Taxonomy classification (NFR risk themes)
- Enrichment analysis (5W, entities)
- Text cleaning
- Embeddings generation (3072 dimensions)

All outputs are cached in JSONL format and stored in SurrealDB with graph edges.

Usage:
    from server.pipelines.controls.models import get_model_cache, run_model_pipeline

    cache = get_model_cache()  # Uses configured path from settings
    result = await run_model_pipeline(
        db=db,
        control_id="CTRL-001",
        record_id="src_controls_main:CTRL_001",
        tables=tables,
        cache=cache,
        graph_token=None
    )
"""

from server.settings import get_settings
from server.pipelines.controls.models.cache import ModelCache


def get_model_cache() -> ModelCache:
    """Get a ModelCache instance using the configured path from settings.

    Returns:
        ModelCache: Cache manager configured with MODEL_OUTPUT_CACHE_PATH
    """
    settings = get_settings()
    settings.ensure_model_cache_dir()
    return ModelCache(cache_dir=settings.model_output_cache_path)
from server.pipelines.controls.models.clean_text import run_clean_text
from server.pipelines.controls.models.embeddings import run_embeddings
from server.pipelines.controls.models.enrichment import run_enrichment
from server.pipelines.controls.models.runner import (
    ModelPipelineResult,
    get_pipeline_stats,
    run_model_pipeline,
    run_model_pipeline_batch,
)
from server.pipelines.controls.models.taxonomy import run_taxonomy

__all__ = [
    # Cache management
    "ModelCache",
    "get_model_cache",
    # Individual model runners
    "run_taxonomy",
    "run_enrichment",
    "run_clean_text",
    "run_embeddings",
    # Pipeline orchestration
    "run_model_pipeline",
    "run_model_pipeline_batch",
    "ModelPipelineResult",
    "get_pipeline_stats",
]
