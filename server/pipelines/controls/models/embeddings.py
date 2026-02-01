"""Embeddings model runner.

This module generates vector embeddings (3072 dimensions) for controls
and creates SurrealDB records with graph edges.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from server.pipelines.controls.models.cache import ModelCache
from server.pipelines.controls.models.functions.mock import generate_embeddings
from server.pipelines.controls.schema import (
    AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT,
    AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS,
    AI_CONTROLS_REL_HAS_EMBEDDINGS,
)


def normalize_datetime(dt_str: str) -> Optional[str]:
    """Convert datetime string to ISO format for SurrealDB."""
    if not dt_str:
        return None
    if " " in dt_str and "T" not in dt_str:
        return dt_str.replace(" ", "T") + "Z"
    if "T" in dt_str and not dt_str.endswith("Z"):
        return dt_str + "Z"
    return dt_str


async def run_embeddings(
    db: Any,
    control_id: str,
    record_id: str,
    clean_text_data: Dict[str, Any],
    cache: ModelCache,
    graph_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Run embedding generation for a control.

    This function:
    1. Checks cache for existing embeddings result
    2. If not cached, runs mock embeddings function
    3. Saves result to cache
    4. Creates SurrealDB current and version records
    5. Creates graph edge from control to embeddings

    Args:
        db: SurrealDB async connection
        control_id: The control ID
        record_id: SurrealDB record ID for the control
        clean_text_data: Clean text data from previous step
        cache: Model cache manager
        graph_token: Optional Graph API token (for future real model integration)

    Returns:
        Dictionary with embeddings data and status
    """
    # Check cache first
    cached = cache.get_cached("embeddings", control_id)
    if cached:
        return {
            "status": "cached",
            "data": cached,
        }

    # Run mock embeddings function (depends on clean_text output)
    response = generate_embeddings(control_id, clean_text_data, graph_token)

    # Save to cache
    cache.save_to_cache("embeddings", control_id, response)

    # If failed, return error
    if response.get("status") != "success":
        return {
            "status": "error",
            "error": response.get("error"),
            "data": response.get("data"),
        }

    embeddings_data = response.get("data", {})

    # Create SurrealDB records
    try:
        safe_control_id = control_id.replace("-", "_")
        effective_at_iso = normalize_datetime(embeddings_data.get("effective_at"))
        emb_record_id = f"{AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT}:{safe_control_id}"

        # Create current record
        await db.query(
            f"""CREATE {emb_record_id} SET
                control_id = $control_id,
                hash = $hash,
                effective_at = <datetime>$effective_at,
                control_title_embedding = $title_emb,
                control_description_embedding = $desc_emb,
                evidence_description_embedding = $evidence_emb,
                local_functional_information_embedding = $local_emb,
                control_as_event_embedding = $event_emb,
                control_as_issues_embedding = $issues_emb
            """,
            {
                "control_id": control_id,
                "hash": embeddings_data.get("hash"),
                "effective_at": effective_at_iso,
                "title_emb": embeddings_data.get("control_title_embedding"),
                "desc_emb": embeddings_data.get("control_description_embedding"),
                "evidence_emb": embeddings_data.get("evidence_description_embedding"),
                "local_emb": embeddings_data.get("local_functional_information_embedding"),
                "event_emb": embeddings_data.get("control_as_event_embedding"),
                "issues_emb": embeddings_data.get("control_as_issues_embedding"),
            }
        )

        # Create version record
        await db.query(
            f"""CREATE {AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS} SET
                control_id = $cid,
                hash = $hash,
                version_date = <datetime>$vdate,
                snapshot = $snapshot
            """,
            {
                "cid": control_id,
                "hash": embeddings_data.get("hash"),
                "vdate": effective_at_iso,
                "snapshot": embeddings_data
            }
        )

        # Create graph edge
        now_iso = datetime.now().isoformat() + "Z"
        await db.query(
            f"""RELATE {record_id}->{AI_CONTROLS_REL_HAS_EMBEDDINGS}->{emb_record_id}
                SET created_at = <datetime>$now, model_version = 'mock_v1'
            """,
            {"now": now_iso}
        )

        return {
            "status": "success",
            "data": embeddings_data,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "data": embeddings_data,
        }
