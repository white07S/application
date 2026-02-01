"""Mock model functions for controls processing.

This module contains mock implementations of model functions that generate
deterministic outputs for taxonomy, enrichment, clean text, and embeddings.

These functions follow the exact logic from the reference implementations
and are designed to be replaced with real model calls in the future.
"""

import hashlib
import json
import random
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

# ============================================================
# NFR TAXONOMY CONFIGURATION
# ============================================================

NFR_TAXONOMY = [
    {"risk_theme_id": "1.1", "risk_theme": "Technology Production Stability"},
    {"risk_theme_id": "1.2", "risk_theme": "Cyber and Information Security"},
    {"risk_theme_id": "1.3", "risk_theme": "Data Management"},
    {"risk_theme_id": "1.4", "risk_theme": "Technology Change Management"},
    {"risk_theme_id": "2.1", "risk_theme": "Third Party Management"},
    {"risk_theme_id": "2.2", "risk_theme": "Outsourcing Risk"},
    {"risk_theme_id": "2.3", "risk_theme": "Intragroup Dependencies"},
    {"risk_theme_id": "3.1", "risk_theme": "Financial Crime Prevention"},
    {"risk_theme_id": "3.2", "risk_theme": "Anti-Money Laundering"},
    {"risk_theme_id": "3.3", "risk_theme": "Sanctions Compliance"},
    {"risk_theme_id": "4.1", "risk_theme": "Conduct Risk"},
    {"risk_theme_id": "4.2", "risk_theme": "Market Conduct"},
    {"risk_theme_id": "4.3", "risk_theme": "Client Suitability"},
    {"risk_theme_id": "5.1", "risk_theme": "Regulatory Compliance"},
    {"risk_theme_id": "5.2", "risk_theme": "Legal Risk"},
    {"risk_theme_id": "5.3", "risk_theme": "Regulatory Change"},
    {"risk_theme_id": "6.1", "risk_theme": "Business Continuity"},
    {"risk_theme_id": "6.2", "risk_theme": "Physical Security"},
    {"risk_theme_id": "6.3", "risk_theme": "Operational Resilience"},
    {"risk_theme_id": "7.1", "risk_theme": "Talent and Resource Management"},
    {"risk_theme_id": "7.2", "risk_theme": "Organizational Culture"},
    {"risk_theme_id": "8.1", "risk_theme": "Process Execution"},
    {"risk_theme_id": "8.2", "risk_theme": "Transaction Processing"},
]

# ============================================================
# TEXT CLEANING CONFIGURATION
# ============================================================

# Common "weird" chars seen in enterprise docs (PDF/Word/email exports)
ZERO_WIDTH = dict.fromkeys(map(ord, [
    "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"  # ZWSP/ZWNJ/ZWJ/WJ/BOM
]), "")

# Normalize various dashes/quotes/bullets/arrows to stable ASCII-ish forms
TRANSLATE = str.maketrans({
    # Quotes
    "\u2018": "'", "\u2019": "'", "\u201A": "'", "\u201B": "'",
    "\u201C": '"', "\u201D": '"', "\u201E": '"', "\u201F": '"',
    "\u00AB": '"', "\u00BB": '"',
    # Dashes/minus
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
    # Bullets / list markers
    "\u2022": "-", "\u25CF": "-", "\u25E6": "-", "\u2043": "-", "\u2219": "-", "\u00B7": "-",
    # Arrows
    "\u2192": "->", "\u21D2": "=>", "\u27A1": "->",
    # Ellipsis
    "\u2026": "...",
    # Non-breaking / odd spaces
    "\u00A0": " ", "\u2007": " ", "\u202F": " ",
})

_TRIPLE_QUOTE_RE = re.compile(r'("""|\'\'\')')
_CRLF_RE = re.compile(r"\r\n?")  # CRLF or CR -> LF
_HARD_WRAP_RE = re.compile(r"[ \t]*\n[ \t]*")  # normalize newline surrounds
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_CONTROL_EXCEPT_NL_TAB = re.compile(r"[\x00-\x08\x0B-\x1F\x7F]")  # keep \n (\x0A) and \t (\x09)
_TRAILING_SPACES_PER_LINE = re.compile(r"[ \t]+(?=\n)")

EMBEDDING_DIM = 3072

# ============================================================
# HELPER FUNCTIONS
# ============================================================


def clean_val(val: Any) -> Any:
    """Clean a value from CSV/DataFrame."""
    if pd.isna(val):
        return None
    if isinstance(val, str) and val.strip().lower() in {"nan", "none", ""}:
        return None
    return val


def build_nested_record(control_id: str, tables: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Build nested control record from tables.

    Args:
        control_id: The control ID to build record for
        tables: Dictionary of DataFrames with table data

    Returns:
        Nested dictionary with control data
    """
    main = tables["controls_main"]
    func_hier = tables["controls_function_hierarchy"]
    loc_hier = tables["controls_location_hierarchy"]
    meta = tables["controls_metadata"]

    main_row = main.loc[main["control_id"] == control_id].iloc[0].apply(clean_val).to_dict()
    func_hier_row = func_hier.loc[func_hier["control_id"] == control_id].iloc[0].apply(clean_val).to_dict()
    loc_hier_row = loc_hier.loc[loc_hier["control_id"] == control_id].iloc[0].apply(clean_val).to_dict()
    # Merge function and location hierarchy into single dict for compatibility
    hier_row = {**func_hier_row, **loc_hier_row}
    meta_row = meta.loc[meta["control_id"] == control_id].iloc[0].apply(clean_val).to_dict()

    flags = tables["controls_category_flags"]
    sox = tables["controls_sox_assertions"]
    risks = tables["controls_risk_themes"]
    rel_funcs = tables["controls_related_functions"]
    rel_locs = tables["controls_related_locations"]

    flag_list: List[str] = []
    if not flags.empty:
        flag_list = [clean_val(x) for x in flags.loc[flags["control_id"] == control_id, "category_flag"].tolist()]

    sox_list: List[str] = []
    if not sox.empty:
        sox_list = [clean_val(x) for x in sox.loc[sox["control_id"] == control_id, "sox_assertion"].tolist()]

    risk_list: List[Dict[str, Any]] = []
    if not risks.empty:
        risk_subset = risks.loc[risks["control_id"] == control_id]
        risk_list = [
            {
                "risk_theme": clean_val(row["risk_theme"]),
                "taxonomy_number": clean_val(row["taxonomy_number"]),
                "risk_theme_number": clean_val(row["risk_theme_number"]),
            }
            for _, row in risk_subset.iterrows()
        ]

    rel_func_list: List[Dict[str, Any]] = []
    if not rel_funcs.empty:
        func_subset = rel_funcs.loc[rel_funcs["control_id"] == control_id]
        rel_func_list = [
            {
                "related_function_id": clean_val(row["related_function_id"]),
                "related_function_name": clean_val(row["related_function_name"]),
                "related_functions_locations_comments": clean_val(row["related_functions_locations_comments"]),
            }
            for _, row in func_subset.iterrows()
        ]

    rel_loc_list: List[Dict[str, Any]] = []
    if not rel_locs.empty:
        loc_subset = rel_locs.loc[rel_locs["control_id"] == control_id]
        rel_loc_list = [
            {
                "related_location_id": clean_val(row["related_location_id"]),
                "related_location_name": clean_val(row["related_location_name"]),
                "related_functions_locations_comments": clean_val(row["related_functions_locations_comments"]),
            }
            for _, row in loc_subset.iterrows()
        ]

    return {
        "control": main_row,
        "hierarchy": hier_row,
        "metadata": meta_row,
        "category_flags": flag_list,
        "sox_assertions": sox_list,
        "risk_themes": risk_list,
        "related_functions": rel_func_list,
        "related_locations": rel_loc_list,
    }


def compute_hash(data: Dict[str, Any]) -> str:
    """Compute SHA256 hash from data for change detection.

    Args:
        data: Dictionary to hash

    Returns:
        First 16 characters of SHA256 hash
    """
    hash_input = json.dumps(data, sort_keys=True)
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def clean_business_text(
    s: str,
    *,
    keep_newlines: bool = True,
    max_consecutive_newlines: int = 2,
    normalize_unicode: str = "NFC",   # "NFC" or "NFKC"
    strip: bool = True,
) -> str:
    """Clean text coming from mixed business systems (PDF/Word/email/ETL).

    - Normalizes Unicode (NFC default)
    - Removes zero-width chars + BOM
    - Normalizes smart quotes/dashes/bullets/arrows/odd spaces
    - Normalizes line endings, trims trailing spaces, collapses repeated spaces/newlines
    - Removes control characters (except newline and tab)
    - Removes literal triple-quote markers

    Args:
        s: String to clean
        keep_newlines: Whether to preserve newlines
        max_consecutive_newlines: Maximum number of consecutive newlines
        normalize_unicode: Unicode normalization form
        strip: Whether to strip leading/trailing whitespace

    Returns:
        Cleaned text
    """
    if s is None:
        return ""

    # Ensure it's a string
    if not isinstance(s, str):
        s = str(s)

    # Unicode normalization
    if normalize_unicode:
        s = unicodedata.normalize(normalize_unicode, s)

    # Remove zero-width chars / BOM
    s = s.translate(ZERO_WIDTH)

    # Normalize line endings
    s = _CRLF_RE.sub("\n", s)

    # Normalize common enterprise punctuation/symbol variants
    s = s.translate(TRANSLATE)

    # Remove literal triple quote markers often introduced by dumps
    s = _TRIPLE_QUOTE_RE.sub("", s)

    # Remove other control chars
    s = _CONTROL_EXCEPT_NL_TAB.sub("", s)

    # Remove trailing spaces on each line
    s = _TRAILING_SPACES_PER_LINE.sub("", s)

    # Normalize newline surrounding spaces
    s = _HARD_WRAP_RE.sub("\n", s)

    # Collapse repeated spaces (keep tabs as-is)
    s = _MULTI_SPACE_RE.sub(" ", s)

    if keep_newlines:
        # Collapse excessive blank lines
        if max_consecutive_newlines is not None and max_consecutive_newlines >= 1:
            s = re.sub(r"\n{" + str(max_consecutive_newlines + 1) + r",}", "\n" * max_consecutive_newlines, s)
        else:
            s = _MULTI_NEWLINE_RE.sub("\n\n", s)
    else:
        # Turn newlines into spaces
        s = re.sub(r"\n+", " ", s)
        s = _MULTI_SPACE_RE.sub(" ", s)

    return s.strip() if strip else s


# ============================================================
# MOCK MODEL FUNCTIONS
# ============================================================


def generate_mock_taxonomy(record: Dict[str, Any], hash_value: str, graph_token: Optional[str] = None) -> Dict[str, Any]:
    """Generate mock taxonomy classification for a control record.

    Args:
        record: Nested control record
        hash_value: Hash value for change detection
        graph_token: Optional Graph API token (for future real model integration)

    Returns:
        Status envelope with:
        - status: "success" or "failure"
        - error: null on success, error message on failure
        - data: the taxonomy result (with values on success, NULLs on failure)
    """
    control = record.get("control", {})
    control_id = control.get("control_id")

    try:
        # Pick primary risk theme (random but deterministic based on control_id)
        random.seed(hash(control_id))
        primary = random.choice(NFR_TAXONOMY)

        # 70% chance of having a secondary theme
        secondary: Optional[Dict[str, str]] = None
        if random.random() < 0.7:
            others = [t for t in NFR_TAXONOMY if t["risk_theme_id"] != primary["risk_theme_id"]]
            secondary = random.choice(others)

        # Generate reasoning steps
        primary_reasoning = [
            f"Step 1: Analyzed control title '{control.get('control_title', 'N/A')}'",
            f"Step 2: Reviewed control description for key themes",
            f"Step 3: Identified primary risk theme as {primary['risk_theme']}",
            f"Step 4: Validated against taxonomy definitions",
        ]

        secondary_reasoning: List[str] = []
        if secondary:
            secondary_reasoning = [
                f"Step 1: Identified additional risk indicators in control",
                f"Step 2: Found secondary alignment with {secondary['risk_theme']}",
                f"Step 3: Confirmed secondary classification",
            ]

        data = {
            "control_id": control_id,
            "hash": hash_value,
            "effective_at": datetime.now().isoformat(),
            "primary_nfr_risk_theme": primary["risk_theme"],
            "primary_risk_theme_id": primary["risk_theme_id"],
            "secondary_nfr_risk_theme": secondary["risk_theme"] if secondary else None,
            "secondary_risk_theme_id": secondary["risk_theme_id"] if secondary else None,
            "primary_risk_theme_reasoning_steps": primary_reasoning,
            "secondary_risk_theme_reasoning_steps": secondary_reasoning,
        }

        return {
            "status": "success",
            "error": None,
            "data": data,
        }

    except Exception as e:
        return {
            "status": "failure",
            "error": str(e),
            "data": {
                "control_id": control_id,
                "hash": hash_value,
                "effective_at": datetime.now().isoformat(),
                "primary_nfr_risk_theme": None,
                "primary_risk_theme_id": None,
                "secondary_nfr_risk_theme": None,
                "secondary_risk_theme_id": None,
                "primary_risk_theme_reasoning_steps": None,
                "secondary_risk_theme_reasoning_steps": None,
            },
        }


def generate_mock_enrichment(record: Dict[str, Any], hash_value: str, graph_token: Optional[str] = None) -> Dict[str, Any]:
    """Generate mock enrichment data for a control record.

    Args:
        record: Nested control record
        hash_value: Hash value for change detection
        graph_token: Optional Graph API token (for future real model integration)

    Returns:
        Status envelope with:
        - status: "success" or "failure"
        - error: null on success, error message on failure
        - data: the enrichment result (with values on success, NULLs on failure)
    """
    control = record.get("control", {})
    hierarchy = record.get("hierarchy", {})
    metadata = record.get("metadata", {})
    control_id = control.get("control_id")

    try:
        # Use control_id for deterministic randomness
        random.seed(hash(control_id))

        title = control.get("control_title", "Unknown Control")
        description = control.get("control_description", "")
        division = hierarchy.get("division_name", "Unknown Division")
        function_name = hierarchy.get("function_name", "Unknown Function")

        # Generate yes/no responses (70% yes)
        def yes_no():
            return "Yes" if random.random() < 0.7 else "No"

        # Generate mock enrichment
        data = {
            "control_id": control_id,
            "hash": hash_value,
            "effective_at": datetime.now().isoformat(),

            # Summary
            "summary": f"This control ensures {title.lower()} within {division}. "
                       f"It is operated by {function_name} to maintain compliance and operational integrity.",

            # What
            "what_yes_no": yes_no(),
            "what_details": f"The control performs {title.lower()} activities including validation, "
                            f"monitoring, and reporting of key metrics.",

            # Where
            "where_yes_no": yes_no(),
            "where_details": f"Control is executed within {division}, specifically in {function_name}.",

            # Who
            "who_yes_no": yes_no(),
            "who_details": f"Control owner: {metadata.get('control_owner', 'Not specified')}. "
                           f"Administrator: {metadata.get('control_administrator', 'Not specified')}.",

            # When
            "when_yes_no": yes_no(),
            "when_details": f"Execution frequency: {control.get('execution_frequency', 'Not specified')}. "
                            f"Valid from: {control.get('valid_from', 'Not specified')}.",

            # Why
            "why_yes_no": yes_no(),
            "why_details": f"Control exists to ensure compliance with regulatory requirements "
                           f"and to mitigate operational risks in {division}.",

            # What-Why combined
            "what_why_yes_no": yes_no(),
            "what_why_details": f"The control {title.lower()} to ensure regulatory compliance "
                                f"and operational risk mitigation within {function_name}.",

            # Risk theme
            "risk_theme_yes_no": yes_no(),
            "risk_theme_details": f"Control is aligned with risk themes for {division} operations.",

            # Frequency
            "frequency_yes_no": yes_no(),
            "frequency_details": f"Control operates {control.get('execution_frequency', 'periodically')}.",

            # Preventative/Detective
            "preventative_detective_yes_no": yes_no(),
            "preventative_detective_details": f"Control is {control.get('preventative_detective', 'Preventative')} "
                                              f"in nature, designed to {'prevent issues before they occur' if control.get('preventative_detective') == 'Preventative' else 'detect issues after occurrence'}.",

            # Automation level
            "automation_level_yes_no": yes_no(),
            "automation_level_details": f"Control is {control.get('manual_automated', 'Manual')}. "
                                        f"Supporting system: {metadata.get('it_application_system_supporting', 'Not specified')}.",

            # Follow-up
            "followup_yes_no": yes_no(),
            "followup_details": "Follow-up actions are documented and tracked through the control management system.",

            # Escalation
            "escalation_yes_no": yes_no(),
            "escalation_details": f"Escalation path: Control Owner -> {metadata.get('kpci_governance_forum', 'Management Committee')}.",

            # Evidence
            "evidence_yes_no": yes_no(),
            "evidence_details": control.get("evidence_description", "Evidence documentation maintained as per policy."),

            # Abbreviations
            "abbreviations_yes_no": yes_no(),
            "abbreviations_details": "Common abbreviations: SOX (Sarbanes-Oxley), KYC (Know Your Customer), "
                                     "AML (Anti-Money Laundering), CCAR (Comprehensive Capital Analysis and Review).",

            # Entities
            "people": f"{metadata.get('control_owner', '')}, {metadata.get('control_administrator', '')}".strip(", "),
            "process": f"{title} process within {function_name}",
            "product": f"Services related to {division}",
            "service": function_name,
            "regulations": "SOX, Basel III, CCAR" if metadata.get("sox_relevant") == "True" else "Internal Policy",

            # Control reframing
            "control_as_issues": f"Failure in {title.lower()} could result in compliance breaches, "
                                 f"financial misstatement, or operational disruption in {division}.",
            "control_as_event": f"Event: {title} execution completed. "
                                f"Outcome: Control operating effectively as of last review.",
        }

        return {
            "status": "success",
            "error": None,
            "data": data,
        }

    except Exception as e:
        return {
            "status": "failure",
            "error": str(e),
            "data": {
                "control_id": control_id,
                "hash": hash_value,
                "effective_at": datetime.now().isoformat(),
                "summary": None,
                "what_yes_no": None,
                "what_details": None,
                "where_yes_no": None,
                "where_details": None,
                "who_yes_no": None,
                "who_details": None,
                "when_yes_no": None,
                "when_details": None,
                "why_yes_no": None,
                "why_details": None,
                "what_why_yes_no": None,
                "what_why_details": None,
                "risk_theme_yes_no": None,
                "risk_theme_details": None,
                "frequency_yes_no": None,
                "frequency_details": None,
                "preventative_detective_yes_no": None,
                "preventative_detective_details": None,
                "automation_level_yes_no": None,
                "automation_level_details": None,
                "followup_yes_no": None,
                "followup_details": None,
                "escalation_yes_no": None,
                "escalation_details": None,
                "evidence_yes_no": None,
                "evidence_details": None,
                "abbreviations_yes_no": None,
                "abbreviations_details": None,
                "people": None,
                "process": None,
                "product": None,
                "service": None,
                "regulations": None,
                "control_as_issues": None,
                "control_as_event": None,
            },
        }


def generate_clean_text(control_id: str, tables: Dict[str, pd.DataFrame], enrichment_data: Dict[str, Any], graph_token: Optional[str] = None) -> Dict[str, Any]:
    """Generate cleaned text for a control record.

    Args:
        control_id: The control ID
        tables: Dictionary of DataFrames with control data
        enrichment_data: Enrichment data from previous step
        graph_token: Optional Graph API token (for future real model integration)

    Returns:
        Status envelope with:
        - status: "success" or "failure"
        - error: null on success, error message on failure
        - data: the clean text result (with values on success, NULLs on failure)
    """
    try:
        main = tables["controls_main"]
        meta = tables["controls_metadata"]

        main_row = main.loc[main["control_id"] == control_id].iloc[0]
        meta_row = meta.loc[meta["control_id"] == control_id].iloc[0]

        # Get raw text fields from control data
        control_title = clean_val(main_row.get("control_title")) or ""
        control_description = clean_val(main_row.get("control_description")) or ""
        evidence_description = clean_val(main_row.get("evidence_description")) or ""
        local_functional_information = clean_val(meta_row.get("local_functional_information")) or ""

        # Get control_as_event and control_as_issues from enrichment
        enrichment = enrichment_data.get("data", {}) if isinstance(enrichment_data, dict) else {}
        control_as_event = enrichment.get("control_as_event") or ""
        control_as_issues = enrichment.get("control_as_issues") or ""

        # Apply text cleaning
        cleaned_texts = {
            "control_title": clean_business_text(control_title),
            "control_description": clean_business_text(control_description),
            "evidence_description": clean_business_text(evidence_description),
            "local_functional_information": clean_business_text(local_functional_information),
            "control_as_event": clean_business_text(control_as_event),
            "control_as_issues": clean_business_text(control_as_issues),
        }

        # Compute hash from cleaned texts
        hash_val = compute_hash(cleaned_texts)

        data = {
            "control_id": control_id,
            "hash": hash_val,
            "effective_at": datetime.now().isoformat(),
            **cleaned_texts,
        }

        return {
            "status": "success",
            "error": None,
            "data": data,
        }

    except Exception as e:
        return {
            "status": "failure",
            "error": str(e),
            "data": {
                "control_id": control_id,
                "hash": None,
                "effective_at": datetime.now().isoformat(),
                "control_title": None,
                "control_description": None,
                "evidence_description": None,
                "local_functional_information": None,
                "control_as_event": None,
                "control_as_issues": None,
            },
        }


def generate_embeddings(control_id: str, clean_text_data: Dict[str, Any], graph_token: Optional[str] = None) -> Dict[str, Any]:
    """Generate mock embeddings for a control record.

    Args:
        control_id: The control ID
        clean_text_data: Clean text data from previous step
        graph_token: Optional Graph API token (for future real model integration)

    Returns:
        Status envelope with:
        - status: "success" or "failure"
        - error: null on success, error message on failure
        - data: the embeddings result (with values on success, NULLs on failure)
    """
    try:
        # Use control_id hash as base seed for reproducibility
        base_seed = hash(control_id)

        # Get text fields from clean_text_data
        text_data = clean_text_data.get("data", {}) if isinstance(clean_text_data, dict) else clean_text_data

        control_title = text_data.get("control_title")
        control_description = text_data.get("control_description")
        evidence_description = text_data.get("evidence_description")
        local_functional_information = text_data.get("local_functional_information")
        control_as_event = text_data.get("control_as_event")
        control_as_issues = text_data.get("control_as_issues")

        # Compute hash (same as clean_text hash for consistency)
        hash_val = text_data.get("hash") or compute_hash(text_data)

        def generate_mock_embedding(text: Optional[str], seed: int) -> Optional[List[float]]:
            """Generate a mock embedding vector for the given text."""
            if not text or text.strip() == "":
                return None

            # Use hash of text + seed for deterministic but varied embeddings
            random.seed(hash(text) + seed)

            # Generate normalized random vector (mimicking real embeddings)
            embedding = [random.gauss(0, 1) for _ in range(EMBEDDING_DIM)]

            # Normalize to unit length (common for embedding models)
            magnitude = sum(x * x for x in embedding) ** 0.5
            embedding = [x / magnitude for x in embedding]

            return embedding

        data = {
            "control_id": control_id,
            "hash": hash_val,
            "effective_at": datetime.now().isoformat(),
            "control_title_embedding": generate_mock_embedding(control_title, base_seed + 1),
            "control_description_embedding": generate_mock_embedding(control_description, base_seed + 2),
            "evidence_description_embedding": generate_mock_embedding(evidence_description, base_seed + 3),
            "local_functional_information_embedding": generate_mock_embedding(local_functional_information, base_seed + 4),
            "control_as_event_embedding": generate_mock_embedding(control_as_event, base_seed + 5),
            "control_as_issues_embedding": generate_mock_embedding(control_as_issues, base_seed + 6),
        }

        return {
            "status": "success",
            "error": None,
            "data": data,
        }

    except Exception as e:
        return {
            "status": "failure",
            "error": str(e),
            "data": {
                "control_id": control_id,
                "hash": None,
                "effective_at": datetime.now().isoformat(),
                "control_title_embedding": None,
                "control_description_embedding": None,
                "evidence_description_embedding": None,
                "local_functional_information_embedding": None,
                "control_as_event_embedding": None,
                "control_as_issues_embedding": None,
            },
        }
