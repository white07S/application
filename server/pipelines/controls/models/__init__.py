"""Model Run Module.

This module provides the complete model pipeline for controls processing:
- Taxonomy classification (NFR risk themes)
- Enrichment analysis (5W, entities)
- Text cleaning
- Embeddings generation (3072 dimensions)

All outputs are cached in JSONL format and stored in SurrealDB with graph edges.

Usage:
    from server.pipelines.controls.models.cache import ModelCache
    from server.pipelines.controls.models.runner import run_model_pipeline

    cache = ModelCache(cache_dir=settings.model_cache_path)
    result = await run_model_pipeline(
        db=db,
        control_id="CTRL-001",
        record_id="src_controls_main:CTRL_001",
        tables=tables,
        cache=cache,
        graph_token=None
    )
"""

from server.pipelines.controls.models.cache import ModelCache
from server.pipelines.controls.models.runner import (
    ModelPipelineResult,
    get_pipeline_stats,
    run_model_pipeline,
)

__all__ = [
    # Cache management
    "ModelCache",
    # Pipeline orchestration
    "run_model_pipeline",
    "ModelPipelineResult",
    "get_pipeline_stats",
]
