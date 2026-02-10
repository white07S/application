"""Taxonomy model runner.

This module runs NFR taxonomy classification on controls and creates
SurrealDB records with graph edges.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from server.pipelines.controls.models.cache import ModelCache
from server.pipelines.controls.models.functions.mock import (
    build_nested_record,
    compute_hash,
    generate_mock_taxonomy,
)
from server.pipelines.controls.schema import (
    AI_CONTROLS_MODEL_TAXONOMY_CURRENT,
    AI_CONTROLS_MODEL_TAXONOMY_VERSIONS,
    AI_CONTROLS_REL_HAS_TAXONOMY,
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


async def run_taxonomy(
    db: Any,
    control_id: str,
    record_id: str,
    tables: Dict[str, Any],
    cache: ModelCache,
    graph_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Run taxonomy classification for a control.

    This function:
    1. Checks cache for existing taxonomy result
    2. If not cached, runs mock taxonomy function
    3. Saves result to cache
    4. Creates SurrealDB current and version records
    5. Creates graph edge from control to taxonomy

    Args:
        db: SurrealDB async connection
        control_id: The control ID
        record_id: SurrealDB record ID for the control
        tables: Dictionary of DataFrames with control data
        cache: Model cache manager
        graph_token: Optional Graph API token (for future real model integration)

    Returns:
        Dictionary with taxonomy data and status
    """
    # Check cache first
    cached = cache.get_cached("taxonomy", control_id)
    if cached:
        return {
            "status": "cached",
            "data": cached,
        }

    # Build record and compute hash
    record = build_nested_record(control_id, tables)
    hash_value = compute_hash({
        "control_id": control_id,
        "control_title": record.get("control", {}).get("control_title"),
        "control_description": record.get("control", {}).get("control_description"),
    })

    # Run mock taxonomy function
    response = generate_mock_taxonomy(record, hash_value, graph_token)

    # Save to cache
    cache.save_to_cache("taxonomy", control_id, response)

    # If failed, return error
    if response.get("status") != "success":
        return {
            "status": "error",
            "error": response.get("error"),
            "data": response.get("data"),
        }

    taxonomy_data = response.get("data", {})

    # Create SurrealDB records
    try:
        safe_control_id = control_id.replace("-", "_")
        effective_at_iso = normalize_datetime(taxonomy_data.get("effective_at"))
        tax_record_id = f"{AI_CONTROLS_MODEL_TAXONOMY_CURRENT}:{safe_control_id}"

        # Create current record
        await db.query(
            f"""CREATE {tax_record_id} SET
                control_id = $control_id,
                hash = $hash,
                effective_at = <datetime>$effective_at,
                primary_nfr_risk_theme = $primary_theme,
                primary_risk_theme_id = $primary_id,
                secondary_nfr_risk_theme = $secondary_theme,
                secondary_risk_theme_id = $secondary_id,
                primary_risk_theme_reasoning_steps = $primary_steps,
                secondary_risk_theme_reasoning_steps = $secondary_steps
            """,
            {
                "control_id": control_id,
                "hash": taxonomy_data.get("hash"),
                "effective_at": effective_at_iso,
                "primary_theme": taxonomy_data.get("primary_nfr_risk_theme"),
                "primary_id": taxonomy_data.get("primary_risk_theme_id"),
                "secondary_theme": taxonomy_data.get("secondary_nfr_risk_theme"),
                "secondary_id": taxonomy_data.get("secondary_risk_theme_id"),
                "primary_steps": taxonomy_data.get("primary_risk_theme_reasoning_steps", []),
                "secondary_steps": taxonomy_data.get("secondary_risk_theme_reasoning_steps", []),
            }
        )

        # Create version record
        await db.query(
            f"""CREATE {AI_CONTROLS_MODEL_TAXONOMY_VERSIONS} SET
                control_id = $cid,
                hash = $hash,
                version_date = <datetime>$vdate,
                snapshot = $snapshot
            """,
            {
                "cid": control_id,
                "hash": taxonomy_data.get("hash"),
                "vdate": effective_at_iso,
                "snapshot": taxonomy_data
            }
        )

        # Create graph edge
        now_iso = datetime.now().isoformat() + "Z"
        await db.query(
            f"""RELATE {record_id}->{AI_CONTROLS_REL_HAS_TAXONOMY}->{tax_record_id}
                SET created_at = <datetime>$now, model_version = 'mock_v1'
            """,
            {"now": now_iso}
        )

        return {
            "status": "success",
            "data": taxonomy_data,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "data": taxonomy_data,
        }
