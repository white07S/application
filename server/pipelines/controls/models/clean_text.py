"""Clean text model runner.

This module runs text cleaning on controls and creates SurrealDB records
with graph edges.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from server.pipelines.controls.models.cache import ModelCache
from server.pipelines.controls.models.functions.mock import generate_clean_text
from server.pipelines.controls.schema import (
    AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT,
    AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS,
    AI_CONTROLS_REL_HAS_CLEANED_TEXT,
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


async def run_clean_text(
    db: Any,
    control_id: str,
    record_id: str,
    tables: Dict[str, Any],
    enrichment_data: Dict[str, Any],
    cache: ModelCache,
    graph_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Run text cleaning for a control.

    This function:
    1. Checks cache for existing clean text result
    2. If not cached, runs mock clean text function
    3. Saves result to cache
    4. Creates SurrealDB current and version records
    5. Creates graph edge from control to cleaned text

    Args:
        db: SurrealDB async connection
        control_id: The control ID
        record_id: SurrealDB record ID for the control
        tables: Dictionary of DataFrames with control data
        enrichment_data: Enrichment data from previous step
        cache: Model cache manager
        graph_token: Optional Graph API token (for future real model integration)

    Returns:
        Dictionary with clean text data and status
    """
    # Check cache first
    cached = cache.get_cached("clean_text", control_id)
    if cached:
        return {
            "status": "cached",
            "data": cached,
        }

    # Run mock clean text function (depends on enrichment output)
    response = generate_clean_text(control_id, tables, enrichment_data, graph_token)

    # Save to cache
    cache.save_to_cache("clean_text", control_id, response)

    # If failed, return error
    if response.get("status") != "success":
        return {
            "status": "error",
            "error": response.get("error"),
            "data": response.get("data"),
        }

    clean_text_data = response.get("data", {})

    # Create SurrealDB records
    try:
        safe_control_id = control_id.replace("-", "_")
        effective_at_iso = normalize_datetime(clean_text_data.get("effective_at"))
        ct_record_id = f"{AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT}:{safe_control_id}"

        # Create current record
        await db.query(
            f"""CREATE {ct_record_id} SET
                control_id = $control_id,
                hash = $hash,
                effective_at = <datetime>$effective_at,
                control_title = $title,
                control_description = $desc,
                evidence_description = $evidence,
                local_functional_information = $local,
                control_as_event = $event,
                control_as_issues = $issues
            """,
            {
                "control_id": control_id,
                "hash": clean_text_data.get("hash"),
                "effective_at": effective_at_iso,
                "title": clean_text_data.get("control_title"),
                "desc": clean_text_data.get("control_description"),
                "evidence": clean_text_data.get("evidence_description"),
                "local": clean_text_data.get("local_functional_information"),
                "event": clean_text_data.get("control_as_event"),
                "issues": clean_text_data.get("control_as_issues"),
            }
        )

        # Create version record
        await db.query(
            f"""CREATE {AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS} SET
                control_id = $cid,
                hash = $hash,
                version_date = <datetime>$vdate,
                snapshot = $snapshot
            """,
            {
                "cid": control_id,
                "hash": clean_text_data.get("hash"),
                "vdate": effective_at_iso,
                "snapshot": clean_text_data
            }
        )

        # Create graph edge
        now_iso = datetime.now().isoformat() + "Z"
        await db.query(
            f"""RELATE {record_id}->{AI_CONTROLS_REL_HAS_CLEANED_TEXT}->{ct_record_id}
                SET created_at = <datetime>$now, model_version = 'mock_v1'
            """,
            {"now": now_iso}
        )

        return {
            "status": "success",
            "data": clean_text_data,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "data": clean_text_data,
        }
