"""Mock model functions for NFR taxonomy, enrichment, and embeddings.

These are placeholder implementations that generate deterministic mock outputs.
In production, these would call actual ML models/APIs.
"""
import hashlib
import json
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from server.logging_config import get_logger
from server.auth.token_manager import get_trimmed_token

# Simulate model processing time (seconds per record)
# Set to 0 for fast processing, or higher values to see progress in UI
MOCK_DELAY_PER_RECORD = 0.5  # 0.5 seconds per record

logger = get_logger(name=__name__)

# Current model versions
MODEL_VERSIONS = {
    "nfr_taxonomy": "v1",
    "enrichment": "v1",
    "embeddings": "v1",
}

# NFR Risk Taxonomy Reference
# Format: (taxonomy_id, theme_name, keywords)
NFR_TAXONOMY = [
    (1, "Technology Production Stability", ["system", "outage", "availability", "infrastructure", "platform", "production"]),
    (2, "Cyber and Information Security", ["cyber", "security", "breach", "vulnerability", "attack", "data protection"]),
    (3, "Data Management", ["data", "quality", "governance", "retention", "privacy", "gdpr"]),
    (4, "Technology Change Management", ["change", "deployment", "release", "upgrade", "migration", "implementation"]),
    (5, "Third Party Management", ["vendor", "third party", "supplier", "outsourcing", "contractor"]),
    (6, "Financial Crime Prevention", ["fraud", "financial crime", "aml", "kyc", "sanctions"]),
    (7, "Conduct Risk", ["conduct", "mis-selling", "customer", "complaint", "suitability"]),
    (8, "Regulatory Compliance", ["regulatory", "compliance", "regulation", "audit", "examination"]),
    (9, "Business Continuity", ["continuity", "disaster", "recovery", "resilience", "backup"]),
    (10, "Process Execution", ["process", "manual", "error", "operational", "procedure", "workflow"]),
]


def compute_input_hash(record: Dict[str, Any], input_columns: List[str]) -> str:
    """Compute deterministic hash of input columns for caching.

    Args:
        record: Record data dictionary
        input_columns: List of column names to include in hash

    Returns:
        SHA-256 hash string
    """
    # Extract only relevant columns, sorted for determinism
    input_data = {col: record.get(col) for col in sorted(input_columns)}

    # Normalize: convert to JSON with sorted keys
    normalized = json.dumps(input_data, sort_keys=True, default=str)

    # Compute SHA-256 hash
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def _score_text_against_taxonomy(text: str) -> List[Tuple[int, str, float]]:
    """Score text against NFR taxonomy keywords.

    Returns list of (taxonomy_id, theme_name, score) sorted by score descending.
    """
    if not text:
        return []

    text_lower = text.lower()
    scores = []

    for taxonomy_id, theme_name, keywords in NFR_TAXONOMY:
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores.append((taxonomy_id, theme_name, score))

    # Sort by score descending
    scores.sort(key=lambda x: x[2], reverse=True)
    return scores


def nfr_taxonomy_classify(
    record: Dict[str, Any],
    input_columns: List[str],
    graph_token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Mock NFR taxonomy classification.

    Analyzes input text columns and assigns top 2 risk themes based on keyword matching.

    Args:
        record: Record data with text columns
        input_columns: Columns to analyze for classification
        graph_token: Microsoft Graph API token for model calls (optional)

    Returns:
        Dictionary with risk_theme_option_1/2 fields, or None if no themes match
    """
    # Log token for debugging (trimmed for security)
    logger.debug("nfr_taxonomy_classify called with token: {}", get_trimmed_token(graph_token))

    # Simulate model processing time
    if MOCK_DELAY_PER_RECORD > 0:
        time.sleep(MOCK_DELAY_PER_RECORD)

    # Combine input columns into single text for analysis
    combined_text = " ".join(
        str(record.get(col, "")) for col in input_columns
    )

    # Score against taxonomy
    scores = _score_text_against_taxonomy(combined_text)

    if not scores:
        # No themes matched - return None (don't store)
        return None

    result = {}

    # Option 1 (best match)
    if len(scores) >= 1:
        result["risk_theme_option_1_id"] = scores[0][0]
        result["risk_theme_option_1"] = scores[0][1]
        result["risk_theme_option_1_reasoning"] = json.dumps([
            f"Keyword match score: {scores[0][2]}",
            f"Matched in columns: {', '.join(input_columns)}",
        ])

    # Option 2 (second best match)
    if len(scores) >= 2:
        result["risk_theme_option_2_id"] = scores[1][0]
        result["risk_theme_option_2"] = scores[1][1]
        result["risk_theme_option_2_reasoning"] = json.dumps([
            f"Keyword match score: {scores[1][2]}",
            f"Secondary classification",
        ])

    return result


def enrichment_control(
    record: Dict[str, Any],
    input_columns: List[str],
    graph_token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Mock enrichment for controls.

    Generates control_written_as_issue, control_summary, and complexity_score.

    Args:
        record: Control record data
        input_columns: Columns to use for enrichment
        graph_token: Microsoft Graph API token for model calls (optional)

    Returns:
        Dictionary with enrichment fields
    """
    # Log token for debugging (trimmed for security)
    logger.debug("enrichment_control called with token: {}", get_trimmed_token(graph_token))

    # Simulate model processing time
    if MOCK_DELAY_PER_RECORD > 0:
        time.sleep(MOCK_DELAY_PER_RECORD)

    control_title = record.get("control_title", "")
    control_description = record.get("control_description", "")
    preventative_detective = record.get("preventative_detective", "")
    manual_automated = record.get("manual_automated", "")

    if not control_title:
        return None

    # Generate control written as issue
    written_as_issue = f"Potential control failure: {control_title}. "
    if control_description:
        written_as_issue += f"This could result in: {control_description[:200]}..."

    # Generate summary
    summary = f"{preventative_detective} {manual_automated} control: {control_title[:100]}"

    # Calculate complexity score (1-10) based on description length and type
    base_score = 5
    if len(control_description or "") > 500:
        base_score += 2
    if manual_automated == "Manual":
        base_score += 1
    if preventative_detective == "Detective":
        base_score += 1

    complexity_score = min(10, max(1, base_score))

    return {
        "control_written_as_issue": written_as_issue,
        "control_summary": summary,
        "control_complexity_score": complexity_score,
    }


def enrichment_issue(
    record: Dict[str, Any],
    input_columns: List[str],
    graph_token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Mock enrichment for issues.

    Generates issue_summary, recommended_actions, and severity_assessment.

    Args:
        record: Issue record data
        input_columns: Columns to use for enrichment
        graph_token: Microsoft Graph API token for model calls (optional)

    Returns:
        Dictionary with enrichment fields
    """
    # Log token for debugging (trimmed for security)
    logger.debug("enrichment_issue called with token: {}", get_trimmed_token(graph_token))

    # Simulate model processing time
    if MOCK_DELAY_PER_RECORD > 0:
        time.sleep(MOCK_DELAY_PER_RECORD)

    issue_title = record.get("issue_title", "")
    control_deficiency = record.get("control_deficiency", "")
    root_cause = record.get("root_cause", "")
    symptoms = record.get("symptoms", "")

    if not issue_title:
        return None

    # Generate summary
    summary = f"Issue: {issue_title[:100]}. "
    if root_cause:
        summary += f"Root cause: {root_cause[:150]}..."

    # Generate recommended actions based on content
    actions = []
    text_lower = (issue_title + " " + control_deficiency).lower()

    if "process" in text_lower or "manual" in text_lower:
        actions.append("Review and document current process")
        actions.append("Implement process automation where feasible")
    if "system" in text_lower or "technology" in text_lower:
        actions.append("Conduct system assessment")
        actions.append("Evaluate technology upgrade options")
    if "training" in text_lower or "awareness" in text_lower:
        actions.append("Develop training program")
        actions.append("Conduct awareness sessions")
    if not actions:
        actions = ["Conduct root cause analysis", "Develop remediation plan", "Implement monitoring"]

    # Severity assessment based on keywords
    severity_keywords = {
        "critical": ["critical", "severe", "major", "significant", "high risk"],
        "moderate": ["moderate", "medium", "standard"],
        "low": ["minor", "low", "minimal"],
    }

    severity = "Moderate"
    for level, keywords in severity_keywords.items():
        if any(kw in text_lower for kw in keywords):
            severity = level.capitalize()
            break

    return {
        "issue_summary": summary,
        "recommended_actions": json.dumps(actions),
        "severity_assessment": severity,
    }


def generate_embedding(
    record: Dict[str, Any],
    input_columns: List[str],
    dimensions: int = 3072,
    graph_token: Optional[str] = None,
) -> Optional[str]:
    """Generate mock embedding vector.

    Creates a deterministic pseudo-random vector based on input hash.
    In production, this would call an embedding API (OpenAI, etc.).

    Args:
        record: Record data
        input_columns: Columns to embed
        dimensions: Vector dimensions (default 3072 for OpenAI)
        graph_token: Microsoft Graph API token for model calls (optional)

    Returns:
        JSON string of embedding vector, or None if no input
    """
    # Log token for debugging (trimmed for security)
    logger.debug("generate_embedding called with token: {}", get_trimmed_token(graph_token))

    # Simulate model processing time
    if MOCK_DELAY_PER_RECORD > 0:
        time.sleep(MOCK_DELAY_PER_RECORD)

    # Combine input columns
    combined_text = " ".join(
        str(record.get(col, "")) for col in input_columns
    )

    if not combined_text.strip():
        return None

    # Use hash as seed for deterministic "random" vector
    input_hash = compute_input_hash(record, input_columns)
    seed = int(input_hash[:8], 16)
    random.seed(seed)

    # Generate normalized vector
    vector = [random.gauss(0, 1) for _ in range(dimensions)]

    # Normalize to unit length
    magnitude = sum(v ** 2 for v in vector) ** 0.5
    if magnitude > 0:
        vector = [v / magnitude for v in vector]

    # Return as JSON (for simplicity - in production use binary format)
    return json.dumps(vector)


def get_model_version(model_function: str) -> str:
    """Get current version for a model function."""
    return MODEL_VERSIONS.get(model_function, "v1")
