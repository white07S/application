"""Model pipeline runner.

This module orchestrates the complete model pipeline for a control:
1. Taxonomy classification
2. Enrichment analysis
3. Text cleaning
4. Embeddings generation

Each step uses JSONL cache and creates SurrealDB records with graph edges.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from server.pipelines.controls.models.cache import ModelCache
from server.pipelines.controls.models.clean_text import run_clean_text
from server.pipelines.controls.models.embeddings import run_embeddings
from server.pipelines.controls.models.enrichment import run_enrichment
from server.pipelines.controls.models.taxonomy import run_taxonomy


@dataclass
class ModelPipelineResult:
    """Result of running the complete model pipeline."""
    control_id: str
    success: bool
    taxonomy_status: str
    enrichment_status: str
    clean_text_status: str
    embeddings_status: str
    taxonomy_data: Optional[Dict[str, Any]] = None
    enrichment_data: Optional[Dict[str, Any]] = None
    clean_text_data: Optional[Dict[str, Any]] = None
    embeddings_data: Optional[Dict[str, Any]] = None
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


async def run_model_pipeline(
    db: Any,
    control_id: str,
    record_id: str,
    tables: Dict[str, Any],
    cache: ModelCache,
    graph_token: Optional[str] = None,
) -> ModelPipelineResult:
    """Run the complete model pipeline for a single control.

    This orchestrates the following steps in order:
    1. Taxonomy classification (NFR risk themes)
    2. Enrichment analysis (5W, entities)
    3. Text cleaning (using enrichment output)
    4. Embeddings generation (using clean text output)

    Each step:
    - Checks JSONL cache first
    - Runs mock function if not cached
    - Saves to cache
    - Creates SurrealDB records
    - Creates graph edges

    Args:
        db: SurrealDB async connection
        control_id: The control ID to process
        record_id: SurrealDB record ID for the control (src_controls_main:*)
        tables: Dictionary of DataFrames with control data
        cache: Model cache manager
        graph_token: Optional Graph API token (for future real model integration)

    Returns:
        ModelPipelineResult with status and data from each step
    """
    result = ModelPipelineResult(
        control_id=control_id,
        success=False,
        taxonomy_status="pending",
        enrichment_status="pending",
        clean_text_status="pending",
        embeddings_status="pending",
    )

    try:
        # Step 1: Taxonomy
        taxonomy_result = await run_taxonomy(
            db, control_id, record_id, tables, cache, graph_token
        )
        result.taxonomy_status = taxonomy_result.get("status", "error")
        result.taxonomy_data = taxonomy_result.get("data")

        if taxonomy_result.get("status") == "error":
            result.errors.append(f"Taxonomy: {taxonomy_result.get('error')}")

        # Step 2: Enrichment
        enrichment_result = await run_enrichment(
            db, control_id, record_id, tables, cache, graph_token
        )
        result.enrichment_status = enrichment_result.get("status", "error")
        result.enrichment_data = enrichment_result.get("data")

        if enrichment_result.get("status") == "error":
            result.errors.append(f"Enrichment: {enrichment_result.get('error')}")

        # Step 3: Clean Text (depends on enrichment)
        clean_text_result = await run_clean_text(
            db, control_id, record_id, tables, enrichment_result, cache, graph_token
        )
        result.clean_text_status = clean_text_result.get("status", "error")
        result.clean_text_data = clean_text_result.get("data")

        if clean_text_result.get("status") == "error":
            result.errors.append(f"Clean Text: {clean_text_result.get('error')}")

        # Step 4: Embeddings (depends on clean_text)
        embeddings_result = await run_embeddings(
            db, control_id, record_id, clean_text_result, cache, graph_token
        )
        result.embeddings_status = embeddings_result.get("status", "error")
        result.embeddings_data = embeddings_result.get("data")

        if embeddings_result.get("status") == "error":
            result.errors.append(f"Embeddings: {embeddings_result.get('error')}")

        # Overall success if no critical errors
        result.success = len(result.errors) == 0

    except Exception as e:
        result.errors.append(f"Pipeline error: {str(e)}")
        result.success = False

    return result


async def run_model_pipeline_batch(
    db: Any,
    controls: list[Dict[str, Any]],
    tables: Dict[str, Any],
    cache: ModelCache,
    graph_token: Optional[str] = None,
) -> Dict[str, ModelPipelineResult]:
    """Run model pipeline for multiple controls.

    Args:
        db: SurrealDB async connection
        controls: List of control dicts with control_id and record_id
        tables: Dictionary of DataFrames with control data
        cache: Model cache manager
        graph_token: Optional Graph API token

    Returns:
        Dictionary mapping control_id to ModelPipelineResult
    """
    results = {}

    for control in controls:
        control_id = control["control_id"]
        record_id = control["record_id"]

        result = await run_model_pipeline(
            db, control_id, record_id, tables, cache, graph_token
        )
        results[control_id] = result

    return results


def get_pipeline_stats(results: Dict[str, ModelPipelineResult]) -> Dict[str, Any]:
    """Get statistics from pipeline results.

    Args:
        results: Dictionary of ModelPipelineResult objects

    Returns:
        Dictionary with pipeline statistics
    """
    total = len(results)
    successful = sum(1 for r in results.values() if r.success)
    failed = total - successful

    taxonomy_cached = sum(1 for r in results.values() if r.taxonomy_status == "cached")
    enrichment_cached = sum(1 for r in results.values() if r.enrichment_status == "cached")
    clean_text_cached = sum(1 for r in results.values() if r.clean_text_status == "cached")
    embeddings_cached = sum(1 for r in results.values() if r.embeddings_status == "cached")

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "success_rate": successful / total if total > 0 else 0,
        "cache_stats": {
            "taxonomy_cached": taxonomy_cached,
            "enrichment_cached": enrichment_cached,
            "clean_text_cached": clean_text_cached,
            "embeddings_cached": embeddings_cached,
        },
        "errors": [
            {"control_id": cid, "errors": r.errors}
            for cid, r in results.items()
            if r.errors
        ],
    }
