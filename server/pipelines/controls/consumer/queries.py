"""SurrealQL query constants and helper functions for consumer module.

This module defines SurrealQL query patterns for graph traversal and temporal queries
used by the ControlsConsumer service.
"""

from typing import Dict, Any


# =============================================================================
# GRAPH TRAVERSAL QUERY PATTERNS
# =============================================================================

def get_risk_themes_query(record_id: str) -> str:
    """Get risk themes linked to a control via graph traversal."""
    return f"SELECT ->src_controls_rel_has_risk_theme->src_controls_ref_risk_theme.* AS risk_themes FROM {record_id}"


def get_functions_query(record_id: str) -> str:
    """Get functions linked to a control via graph traversal."""
    return f"SELECT ->src_controls_rel_has_related_function->src_controls_ref_org_function.* AS functions FROM {record_id}"


def get_locations_query(record_id: str) -> str:
    """Get locations linked to a control via graph traversal."""
    return f"SELECT ->src_controls_rel_has_related_location->src_controls_ref_org_location.* AS locations FROM {record_id}"


def get_sox_assertions_query(record_id: str) -> str:
    """Get SOX assertions linked to a control via graph traversal."""
    return f"SELECT ->src_controls_rel_has_sox_assertion->src_controls_ref_sox_assertion.* AS assertions FROM {record_id}"


def get_category_flags_query(record_id: str) -> str:
    """Get category flags linked to a control via graph traversal."""
    return f"SELECT ->src_controls_rel_has_category_flag->src_controls_ref_category_flag.* AS flags FROM {record_id}"


def get_taxonomy_query(record_id: str) -> str:
    """Get taxonomy linked to a control via graph traversal."""
    return f"SELECT ->ai_controls_rel_has_taxonomy->ai_controls_model_taxonomy_current.* AS taxonomy FROM {record_id}"


def get_enrichment_query(record_id: str) -> str:
    """Get enrichment linked to a control via graph traversal."""
    return f"SELECT ->ai_controls_rel_has_enrichment->ai_controls_model_enrichment_current.* AS enrichment FROM {record_id}"


def get_clean_text_query(record_id: str) -> str:
    """Get cleaned text linked to a control via graph traversal."""
    return f"SELECT ->ai_controls_rel_has_cleaned_text->ai_controls_model_cleaned_text_current.* AS clean_text FROM {record_id}"


def get_embeddings_query(record_id: str) -> str:
    """Get embeddings linked to a control via graph traversal (excluding vectors)."""
    return f"SELECT ->ai_controls_rel_has_embeddings->ai_controls_model_embeddings_current.{{control_id, hash, effective_at}} AS embeddings FROM {record_id}"


# =============================================================================
# REVERSE GRAPH TRAVERSAL QUERY PATTERNS
# =============================================================================

def get_controls_by_risk_theme_query(risk_theme_record_id: str) -> str:
    """Find all controls linked to a risk theme (reverse traversal)."""
    return f"SELECT <-src_controls_rel_has_risk_theme<-src_controls_main.* AS controls FROM {risk_theme_record_id}"


def get_controls_by_function_query(function_record_id: str) -> str:
    """Find all controls linked to a function (reverse traversal)."""
    return f"SELECT <-src_controls_rel_has_related_function<-src_controls_main.* AS controls FROM {function_record_id}"


def get_controls_by_location_query(location_record_id: str) -> str:
    """Find all controls linked to a location (reverse traversal)."""
    return f"SELECT <-src_controls_rel_has_related_location<-src_controls_main.* AS controls FROM {location_record_id}"


# =============================================================================
# COMPLETE GRAPH QUERY
# =============================================================================

def get_control_graph_query(record_id: str) -> str:
    """Get complete graph view of a control including all edge metadata."""
    return f"""
        SELECT
            *,
            ->src_controls_rel_has_risk_theme AS risk_theme_edges,
            ->src_controls_rel_has_related_function AS related_function_edges,
            ->src_controls_rel_has_related_location AS related_location_edges,
            ->src_controls_rel_has_sox_assertion AS sox_edges,
            ->src_controls_rel_has_category_flag AS category_flag_edges,
            ->ai_controls_rel_has_taxonomy AS taxonomy_edges,
            ->ai_controls_rel_has_enrichment AS enrichment_edges,
            ->ai_controls_rel_has_cleaned_text AS cleaned_text_edges,
            ->ai_controls_rel_has_embeddings AS embeddings_edges
        FROM {record_id}
    """


# =============================================================================
# TEMPORAL QUERY PATTERNS
# =============================================================================

VERSION_EXACT_MATCH_QUERY = """
    SELECT * FROM {table}
    WHERE control_id = $cid AND version_date = $date
    LIMIT 1
"""

VERSION_BEFORE_DATE_QUERY = """
    SELECT * FROM {table}
    WHERE control_id = $cid AND version_date < $date
    ORDER BY version_date DESC
    LIMIT 1
"""

CURRENT_RECORD_QUERY = """
    SELECT * FROM {table}
    WHERE control_id = $cid
    LIMIT 1
"""

RECORD_HISTORY_QUERY = """
    SELECT * FROM {table}
    WHERE control_id = $cid
    ORDER BY version_date ASC
"""


# =============================================================================
# SNAPSHOT QUERY PATTERNS
# =============================================================================

TABLE_SELECT_ALL_QUERY = "SELECT * FROM {table}"

TABLE_COUNT_QUERY = "SELECT count() FROM {table} GROUP ALL"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_control_id_for_record(control_id: str) -> str:
    """Normalize control_id to valid SurrealDB record ID format.

    Converts hyphens to underscores for use in record IDs.
    Example: "CTRL-001" -> "src_controls_main:CTRL_001"
    """
    safe_id = control_id.replace("-", "_")
    return f"src_controls_main:{safe_id}"


def normalize_risk_theme_id_for_record(risk_theme_id: str) -> str:
    """Normalize risk_theme_id to valid SurrealDB record ID format.

    Converts dots to underscores for use in record IDs.
    Example: "1.2" -> "src_controls_ref_risk_theme:1_2"
    """
    safe_id = risk_theme_id.replace(".", "_")
    return f"src_controls_ref_risk_theme:{safe_id}"


def extract_list_from_result(result: Any, key: str) -> list:
    """Extract list data from SurrealDB result.

    SurrealDB graph traversal results can return data in various formats.
    This helper ensures we always get a list.

    Args:
        result: The result from a SurrealDB query (list of dicts)
        key: The key to extract from the first result dict

    Returns:
        List of items, empty list if none found
    """
    if not result or len(result) == 0:
        return []

    data = result[0].get(key, [])

    # Handle various result formats
    if isinstance(data, list):
        return data
    elif data:
        return [data]
    else:
        return []


def extract_single_from_result(result: Any, key: str) -> Any:
    """Extract single item data from SurrealDB result.

    For model outputs that should only have one record.

    Args:
        result: The result from a SurrealDB query (list of dicts)
        key: The key to extract from the first result dict

    Returns:
        Single item or None if not found
    """
    if not result or len(result) == 0:
        return None

    data = result[0].get(key, None)

    # If data is a list, get first item, otherwise return as-is
    if isinstance(data, list) and data:
        return data[0]
    elif data:
        return data
    else:
        return None
