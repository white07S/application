"""Enrichment model runner.

This module runs 5W analysis and entity extraction on controls and creates
SurrealDB records with graph edges.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from server.pipelines.controls.models.cache import ModelCache
from server.pipelines.controls.models.functions.mock import (
    build_nested_record,
    compute_hash,
    generate_mock_enrichment,
)
from server.pipelines.controls.schema import (
    AI_CONTROLS_MODEL_ENRICHMENT_CURRENT,
    AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS,
    AI_CONTROLS_REL_HAS_ENRICHMENT,
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


async def run_enrichment(
    db: Any,
    control_id: str,
    record_id: str,
    tables: Dict[str, Any],
    cache: ModelCache,
    graph_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Run enrichment analysis for a control.

    This function:
    1. Checks cache for existing enrichment result
    2. If not cached, runs mock enrichment function
    3. Saves result to cache
    4. Creates SurrealDB current and version records
    5. Creates graph edge from control to enrichment

    Args:
        db: SurrealDB async connection
        control_id: The control ID
        record_id: SurrealDB record ID for the control
        tables: Dictionary of DataFrames with control data
        cache: Model cache manager
        graph_token: Optional Graph API token (for future real model integration)

    Returns:
        Dictionary with enrichment data and status
    """
    # Check cache first
    cached = cache.get_cached("enrichment", control_id)
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
        "evidence_description": record.get("control", {}).get("evidence_description"),
    })

    # Run mock enrichment function
    response = generate_mock_enrichment(record, hash_value, graph_token)

    # Save to cache
    cache.save_to_cache("enrichment", control_id, response)

    # If failed, return error
    if response.get("status") != "success":
        return {
            "status": "error",
            "error": response.get("error"),
            "data": response.get("data"),
        }

    enrichment_data = response.get("data", {})

    # Create SurrealDB records
    try:
        safe_control_id = control_id.replace("-", "_")
        effective_at_iso = normalize_datetime(enrichment_data.get("effective_at"))
        enr_record_id = f"{AI_CONTROLS_MODEL_ENRICHMENT_CURRENT}:{safe_control_id}"

        # Create current record
        await db.query(
            f"""CREATE {enr_record_id} SET
                control_id = $control_id,
                hash = $hash,
                effective_at = <datetime>$effective_at,
                summary = $summary,
                what_yes_no = $what_yn,
                what_details = $what_d,
                where_yes_no = $where_yn,
                where_details = $where_d,
                who_yes_no = $who_yn,
                who_details = $who_d,
                when_yes_no = $when_yn,
                when_details = $when_d,
                why_yes_no = $why_yn,
                why_details = $why_d,
                what_why_yes_no = $ww_yn,
                what_why_details = $ww_d,
                risk_theme_yes_no = $rt_yn,
                risk_theme_details = $rt_d,
                frequency_yes_no = $freq_yn,
                frequency_details = $freq_d,
                preventative_detective_yes_no = $pd_yn,
                preventative_detective_details = $pd_d,
                automation_level_yes_no = $al_yn,
                automation_level_details = $al_d,
                followup_yes_no = $fu_yn,
                followup_details = $fu_d,
                escalation_yes_no = $esc_yn,
                escalation_details = $esc_d,
                evidence_yes_no = $ev_yn,
                evidence_details = $ev_d,
                abbreviations_yes_no = $ab_yn,
                abbreviations_details = $ab_d,
                people = $people,
                process = $process,
                product = $product,
                service = $service,
                regulations = $regulations,
                control_as_issues = $issues,
                control_as_event = $event
            """,
            {
                "control_id": control_id,
                "hash": enrichment_data.get("hash"),
                "effective_at": effective_at_iso,
                "summary": enrichment_data.get("summary"),
                "what_yn": enrichment_data.get("what_yes_no"),
                "what_d": enrichment_data.get("what_details"),
                "where_yn": enrichment_data.get("where_yes_no"),
                "where_d": enrichment_data.get("where_details"),
                "who_yn": enrichment_data.get("who_yes_no"),
                "who_d": enrichment_data.get("who_details"),
                "when_yn": enrichment_data.get("when_yes_no"),
                "when_d": enrichment_data.get("when_details"),
                "why_yn": enrichment_data.get("why_yes_no"),
                "why_d": enrichment_data.get("why_details"),
                "ww_yn": enrichment_data.get("what_why_yes_no"),
                "ww_d": enrichment_data.get("what_why_details"),
                "rt_yn": enrichment_data.get("risk_theme_yes_no"),
                "rt_d": enrichment_data.get("risk_theme_details"),
                "freq_yn": enrichment_data.get("frequency_yes_no"),
                "freq_d": enrichment_data.get("frequency_details"),
                "pd_yn": enrichment_data.get("preventative_detective_yes_no"),
                "pd_d": enrichment_data.get("preventative_detective_details"),
                "al_yn": enrichment_data.get("automation_level_yes_no"),
                "al_d": enrichment_data.get("automation_level_details"),
                "fu_yn": enrichment_data.get("followup_yes_no"),
                "fu_d": enrichment_data.get("followup_details"),
                "esc_yn": enrichment_data.get("escalation_yes_no"),
                "esc_d": enrichment_data.get("escalation_details"),
                "ev_yn": enrichment_data.get("evidence_yes_no"),
                "ev_d": enrichment_data.get("evidence_details"),
                "ab_yn": enrichment_data.get("abbreviations_yes_no"),
                "ab_d": enrichment_data.get("abbreviations_details"),
                "people": enrichment_data.get("people"),
                "process": enrichment_data.get("process"),
                "product": enrichment_data.get("product"),
                "service": enrichment_data.get("service"),
                "regulations": enrichment_data.get("regulations"),
                "issues": enrichment_data.get("control_as_issues"),
                "event": enrichment_data.get("control_as_event"),
            }
        )

        # Create version record
        await db.query(
            f"""CREATE {AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS} SET
                control_id = $cid,
                hash = $hash,
                version_date = <datetime>$vdate,
                snapshot = $snapshot
            """,
            {
                "cid": control_id,
                "hash": enrichment_data.get("hash"),
                "vdate": effective_at_iso,
                "snapshot": enrichment_data
            }
        )

        # Create graph edge
        now_iso = datetime.now().isoformat() + "Z"
        await db.query(
            f"""RELATE {record_id}->{AI_CONTROLS_REL_HAS_ENRICHMENT}->{enr_record_id}
                SET created_at = <datetime>$now, model_version = 'mock_v1'
            """,
            {"now": now_iso}
        )

        return {
            "status": "success",
            "data": enrichment_data,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "data": enrichment_data,
        }
