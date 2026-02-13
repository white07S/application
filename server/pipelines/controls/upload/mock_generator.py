"""Mock JSONL generator for controls data.

Generates realistic mock controls JSONL data based on production data profiles.
Used temporarily until real CSV-to-JSONL conversion is implemented.

Loads actual org node IDs and risk theme IDs from context_providers JSONL files
so that generated controls have valid FK references.

Adapted from new_mock_data/mock_data/controls/controls_mock.py.
"""

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import orjson
from pydantic import TypeAdapter, ValidationError

from server.logging_config import get_logger
from server.pipelines.controls.schema_validation import ControlRecord
from server.settings import get_settings

logger = get_logger(name=__name__)

# Default profile (derived from 2026-02-10 real data).
NUM_CONTROLS = 56856
SEED = 1337
BASE_N = 56856

STRING_NULL_COUNTS = {
    "additional_information_on_deactivation": 37344,
    "control_assessor": 27836,
    "control_assessor_gpn": 27836,
    "control_created_by": 3545,
    "control_created_by_gpn": 3545,
    "control_created_on": 0,
    "control_delegate": 53257,
    "control_delegate_gpn": 53257,
    "control_description": 1,
    "control_id": 0,
    "control_instance_owner_role": 25056,
    "control_owner": 14558,
    "control_owner_gpn": 14558,
    "control_status": 0,
    "control_status_date_change": 47122,
    "control_title": 0,
    "evidence_available_from": 37798,
    "evidence_description": 12014,
    "execution_frequency": 13501,
    "financial_statement_line_item": 50264,
    "hierarchy_level": 0,
    "it_application_system_supporting_control_instance": 36019,
    "kpci_governance_forum": 26073,
    "last_control_modification_requested_by": 4271,
    "last_control_modification_requested_by_gpn": 4271,
    "last_modification_on": 4498,
    "last_modified_on": 0,
    "local_functional_information": 20220,
    "manual_automated": 24123,
    "owning_organization_function_id": 0,
    "owning_organization_location_id": 0,
    "parent_control_id": 10891,
    "performance_measures_available_from": 53574,
    "preventative_detective": 2,
    "reason_for_deactivation": 37143,
    "sox_rationale": 55431,
    "status_updates": 47008,
    "valid_from": 9338,
    "valid_until": 26203,
}

BOOL_COUNTS = {
    "key_control": {"true": 50867, "false": 5989},
    "four_eyes_check": {"null": 56856},
    "performance_measures_required": {"true": 7596, "false": 38371, "null": 10889},
    "is_assessor_control_owner": {"true": 26344, "false": 6389, "null": 24123},
    "sox_relevant": {"true": 5654, "false": 51202},
    "ccar_relevant": {"true": 774, "false": 56080, "null": 2},
    "bcbs239_relevant": {"true": 409, "false": 43214, "null": 13233},
    "ey_reliant": {"true": 2870, "false": 14102, "null": 39884},
}

LIST_LENGTH_COUNTS = {
    "control_administrator": {0: 13233, 1: 11169, 2: 10422, 3: 8744, 4: 6111, 5: 1869, 6: 1596, 7: 1032, 8: 953, 9: 1725, 10: 2},
    "related_functions": {
        0: 24204, 1: 18761, 2: 4194, 3: 3060, 4: 1453, 5: 1281, 6: 1019, 7: 750, 8: 363, 9: 265, 10: 221,
        11: 141, 12: 158, 13: 78, 14: 113, 15: 98, 16: 59, 17: 123, 18: 22, 19: 91, 20: 11, 21: 1, 22: 6,
        23: 2, 24: 297, 25: 35, 28: 3, 38: 1, 47: 24, 50: 1, 60: 1, 81: 1, 90: 1, 120: 13, 128: 1, 130: 1, 141: 3,
    },
    "related_locations": {
        0: 24215, 1: 20390, 2: 3433, 3: 1775, 4: 1177, 5: 917, 6: 1099, 7: 804, 8: 413, 9: 330, 10: 301,
        11: 231, 12: 150, 13: 292, 14: 178, 15: 91, 16: 117, 17: 86, 18: 204, 19: 51, 20: 67, 21: 68, 22: 103, 23: 43,
        24: 87, 25: 16, 26: 31, 27: 9, 28: 7, 29: 12, 30: 12, 31: 2, 32: 5, 33: 3, 34: 9, 35: 2, 36: 1, 37: 4, 38: 3,
        39: 2, 40: 3, 41: 1, 50: 1, 59: 1, 60: 8, 61: 4, 62: 3, 65: 29, 67: 1, 68: 1, 69: 1, 70: 1, 80: 1, 83: 1,
        102: 2, 107: 3, 112: 5, 140: 2, 141: 1, 149: 1, 150: 1, 179: 1, 180: 1, 194: 4, 204: 1, 205: 25, 206: 5,
        220: 1, 221: 2, 224: 5,
    },
    "risk_theme": {0: 46081, 1: 7316, 2: 3219, 3: 145, 4: 46, 5: 20, 6: 7, 7: 5, 8: 10, 9: 2, 11: 2, 13: 1, 18: 1, 21: 1},
    "category_flags": {0: 43305, 1: 12062, 2: 1258, 3: 207, 4: 23, 5: 1},
    "sox_assertions": {0: 53026, 1: 1348, 2: 435, 3: 435, 4: 743, 5: 869},
}

CONTROL_STATUS_WEIGHTS = {"Active": 30804, "Expired": 25982, "Rejected": 66, "Approval Pending": 4}
PREVENTATIVE_DETECTIVE_WEIGHTS = {
    "1st Line Detective": 26330, "Preventative": 18355, "2nd Line Detective": 9716,
    "Preventative & Detective": 2448, "TBA": 5, None: 2,
}
MANUAL_AUTOMATED_WEIGHTS = {None: 24123, "IT Dependent Manual": 16404, "Manual": 14946, "Automated": 1383}
EXECUTION_FREQUENCY_WEIGHTS = {
    None: 13501, "Annually": 9398, "Monthly": 9177, "Event Triggered": 7344,
    "Quarterly": 6146, "Semi-Annually": 5483, "Daily": 3485, "Other": 1396,
    "Weekly": 641, "Intraday": 151, "TBA": 134,
}

CATEGORY_FLAGS = [
    "Conflict of Interest", "Integration - Legacy CS Control", "Designated Market Activity",
    "Credit Risk Control Framework", "Treasury Risk Control Framework",
    "Environmental Social Governance (ESG) / Sustainable Investing (SI)", "FATCA/AEI/QI",
    "Market Risk Control Framework", "Sustainability and Climate Risk (SCR) Control Framework",
    "Volker", "Electronic Trading", "Designated Market Activity (holistic)", "Swap Dealer",
    "Designated Market Activity (most impactful)", "Artificial Intelligence",
]
SOX_ASSERTIONS = ["Completeness", "Existence/Occurrence", "Valuation/Allocation", "Rights & Obligations", "Presentation & Disclosure"]
RISK_THEMES = [
    "Business Continuity, Resilience and Crisis Management", "Cyber and Technology Risk",
    "Financial Crime", "Model Risk", "Operational Resilience", "Third Party Risk",
    "Data Management", "Market Conduct", "People Risk", "Regulatory Compliance",
]

FIRST_NAMES = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Jamie", "Riley", "Cameron", "Avery",
               "Robin", "Drew", "Hayden", "Harper", "Logan", "Quinn", "Reese", "Rowan", "Skyler", "Parker"]
LAST_NAMES = ["Smith", "Johnson", "Brown", "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris",
              "Martin", "Thompson", "Garcia", "Martinez", "Robinson", "Clark", "Rodriguez", "Lewis", "Lee", "Walker"]
APPLICATIONS = ["Sabre", "Aladdin", "Murex", "Calypso", "Snowflake", "SAP", "ServiceNow", "Jira", "Excel"]
KPCI_FORUMS = ["IBO KPCi Governance", "P&C CIC Risk Forum", "Group Risk Forum", "Operational Risk Forum"]


# ── Context provider loaders ─────────────────────────────────────────

def _find_latest_date_dir(base: Path) -> Optional[Path]:
    """Find the latest date-named subdirectory under a base path."""
    if not base.is_dir():
        return None
    date_dirs = sorted(
        [d for d in base.iterdir() if d.is_dir() and len(d.name) == 10],
        reverse=True,
    )
    return date_dirs[0] if date_dirs else None


def _load_org_ids_from_context_providers(ctx_path: Path) -> Tuple[List[str], List[str]]:
    """Load function and location source_ids from context_providers JSONL.

    Returns:
        (function_ids, location_ids) — raw source IDs as used in the `id` field.
    """
    org_base = ctx_path / "organization"
    date_dir = _find_latest_date_dir(org_base)
    if date_dir is None:
        logger.warning("No organization date directory found under {}", org_base)
        return [], []

    function_ids: List[str] = []
    location_ids: List[str] = []

    # Functions
    func_file = date_dir / "functions.jsonl"
    if func_file.exists():
        with func_file.open("rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = orjson.loads(line)
                sid = str(row.get("id", "")).strip()
                if sid:
                    function_ids.append(sid)

    # Locations
    loc_file = date_dir / "locations.jsonl"
    if loc_file.exists():
        with loc_file.open("rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = orjson.loads(line)
                sid = str(row.get("id", "")).strip()
                if sid:
                    location_ids.append(sid)

    logger.info(
        "Loaded {} function IDs, {} location IDs from context_providers",
        len(function_ids), len(location_ids),
    )
    return function_ids, location_ids


def _load_risk_theme_ids_from_context_providers(ctx_path: Path) -> Tuple[List[str], List[str]]:
    """Load risk theme IDs and taxonomy IDs from context_providers JSONL.

    Returns:
        (theme_ids, taxonomy_ids)
    """
    rt_base = ctx_path / "risk_theme"
    date_dir = _find_latest_date_dir(rt_base)
    if date_dir is None:
        logger.warning("No risk_theme date directory found under {}", rt_base)
        return [], []

    theme_ids: List[str] = []
    taxonomy_ids: List[str] = []
    seen_themes: set = set()
    seen_taxonomies: set = set()

    rt_file = date_dir / "risk_theme.jsonl"
    if rt_file.exists():
        with rt_file.open("rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = orjson.loads(line)
                tid = str(row.get("risk_theme_id", "")).strip()
                if tid and tid not in seen_themes:
                    theme_ids.append(tid)
                    seen_themes.add(tid)
                tax_id = str(row.get("taxonomy_id", "")).strip()
                if tax_id and tax_id not in seen_taxonomies:
                    taxonomy_ids.append(tax_id)
                    seen_taxonomies.add(tax_id)

    logger.info(
        "Loaded {} risk theme IDs, {} taxonomy IDs from context_providers",
        len(theme_ids), len(taxonomy_ids),
    )
    return theme_ids, taxonomy_ids


# ── Helpers ──────────────────────────────────────────────────────────

def _weighted_choice(rng: random.Random, weights: Dict[Any, int]) -> Any:
    items = list(weights.items())
    choices, w = zip(*items)
    return rng.choices(list(choices), weights=list(w), k=1)[0]


def _prob_null(field: str) -> float:
    return float(STRING_NULL_COUNTS.get(field, 0)) / float(BASE_N)


def _bool_from_profile(rng: random.Random, field: str) -> bool | None:
    dist = BOOL_COUNTS.get(field)
    if not dist:
        return None
    choices: List[bool | None] = []
    weights: List[int] = []
    for k, w in dist.items():
        if k == "true":
            choices.append(True)
        elif k == "false":
            choices.append(False)
        elif k == "null":
            choices.append(None)
        weights.append(w)
    return rng.choices(choices, weights=weights, k=1)[0]


def _sample_len(rng: random.Random, field: str) -> int:
    dist = LIST_LENGTH_COUNTS.get(field, {0: 1})
    items = list(dist.items())
    lengths, weights = zip(*items)
    return int(rng.choices(list(lengths), weights=list(weights), k=1)[0])


def _make_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _make_gpn(rng: random.Random) -> str:
    if rng.random() < 0.02:
        return f"FR{rng.randint(1, 99999):05d}"
    return f"{rng.randint(1, 99999999):08d}"


def _make_multiline(field: str, cid: str) -> str:
    return (
        f"{field} for {cid}\n"
        f"(WHEN) Monthly\n"
        f"(WHO) Mock Owner\n"
        f"(WHAT) Mock procedure steps\n"
        f"(WHY) Mock rationale"
    )


def _make_iso_dt(base: datetime, i: int) -> str:
    dt = base + timedelta(seconds=(i * 9973) % (365 * 24 * 3600))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _make_mon_dt(base: datetime, i: int) -> str:
    dt = base + timedelta(seconds=(i * 9973) % (365 * 24 * 3600))
    return dt.strftime("%d-%b-%Y %I:%M:%S %p")


def _make_iso_date(base: datetime, i: int) -> str:
    dt = base + timedelta(days=(i * 73) % 365)
    return dt.strftime("%Y-%m-%d")


# ── Main generator ───────────────────────────────────────────────────

def generate_mock_jsonl(
    output_path: Path,
    num_controls: int = NUM_CONTROLS,
    seed: int = SEED,
) -> int:
    """Generate mock controls JSONL file.

    Loads real org node IDs and risk theme IDs from context_providers so that
    generated controls have valid FK references for ingestion into PostgreSQL.

    Args:
        output_path: Path where the JSONL file will be written.
        num_controls: Number of control records to generate.
        seed: Random seed for reproducibility.

    Returns:
        Number of records written.
    """
    rng = random.Random(seed)
    adapter = TypeAdapter(ControlRecord)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load real IDs from context_providers
    settings = get_settings()
    ctx_path = Path(settings.context_providers_path)

    function_ids, location_ids = _load_org_ids_from_context_providers(ctx_path)
    theme_ids, taxonomy_ids = _load_risk_theme_ids_from_context_providers(ctx_path)

    if not function_ids:
        raise RuntimeError(
            f"No function IDs found in {ctx_path / 'organization'}. "
            "Run context provider ingestion first."
        )
    if not location_ids:
        raise RuntimeError(
            f"No location IDs found in {ctx_path / 'organization'}. "
            "Run context provider ingestion first."
        )
    if not theme_ids:
        raise RuntimeError(
            f"No risk theme IDs found in {ctx_path / 'risk_theme'}. "
            "Run context provider ingestion first."
        )

    # Build theme_id → taxonomy_id mapping for risk_theme entries
    # Re-read to get the pairing
    rt_base = ctx_path / "risk_theme"
    date_dir = _find_latest_date_dir(rt_base)
    theme_to_taxonomy: Dict[str, str] = {}
    if date_dir:
        rt_file = date_dir / "risk_theme.jsonl"
        if rt_file.exists():
            with rt_file.open("rb") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = orjson.loads(line)
                    tid = str(row.get("risk_theme_id", "")).strip()
                    tax = str(row.get("taxonomy_id", "")).strip()
                    if tid and tax:
                        theme_to_taxonomy[tid] = tax

    level1_ratio = float(STRING_NULL_COUNTS["parent_control_id"]) / float(BASE_N)
    n_level1 = max(1, min(num_controls, int(round(num_controls * level1_ratio))))

    base_dt = datetime(2026, 2, 1, 9, 0, 0)
    level1_ids = [f"CTRL-{i:010d}" for i in range(1, n_level1 + 1)]

    written = 0
    with output_path.open("wb") as out_f:
        for i in range(1, num_controls + 1):
            cid = f"CTRL-{i:010d}"

            record: Dict[str, Any] = {k: None for k in ControlRecord.model_fields.keys()}
            for list_field in [
                "control_administrator", "control_administrator_gpn",
                "related_functions", "related_locations",
                "risk_theme", "category_flags", "sox_assertions",
            ]:
                record[list_field] = []

            # ---- identity / hierarchy
            record["control_id"] = cid
            record["owning_organization_function_id"] = rng.choice(function_ids)
            record["owning_organization_location_id"] = rng.choice(location_ids)

            if i <= n_level1:
                record["hierarchy_level"] = "Level 1"
                record["parent_control_id"] = None
            else:
                record["hierarchy_level"] = "Level 2"
                record["parent_control_id"] = rng.choice(level1_ids)

            # ---- required-ish strings
            record["control_title"] = f"Mock Control Title {i}"
            record["control_status"] = _weighted_choice(rng, CONTROL_STATUS_WEIGHTS)

            # ---- core text
            record["control_description"] = _make_multiline("control_description", cid) if rng.random() > _prob_null("control_description") else None
            record["evidence_description"] = _make_multiline("evidence_description", cid) if rng.random() > _prob_null("evidence_description") else None
            record["local_functional_information"] = _make_multiline("local_functional_information", cid) if rng.random() > _prob_null("local_functional_information") else None
            record["status_updates"] = _make_multiline("status_updates", cid) if rng.random() > _prob_null("status_updates") else None

            # ---- enumerations
            record["preventative_detective"] = _weighted_choice(rng, PREVENTATIVE_DETECTIVE_WEIGHTS)
            record["manual_automated"] = _weighted_choice(rng, MANUAL_AUTOMATED_WEIGHTS)
            record["execution_frequency"] = _weighted_choice(rng, EXECUTION_FREQUENCY_WEIGHTS)
            record["it_application_system_supporting_control_instance"] = (
                rng.choice(APPLICATIONS) if rng.random() > _prob_null("it_application_system_supporting_control_instance") else None
            )
            record["kpci_governance_forum"] = rng.choice(KPCI_FORUMS) if rng.random() > _prob_null("kpci_governance_forum") else None
            record["financial_statement_line_item"] = (
                f"FS Line Item {rng.randint(1, 50)}" if rng.random() > _prob_null("financial_statement_line_item") else None
            )
            record["additional_information_on_deactivation"] = (
                f"Mock deactivation info {i}" if rng.random() > _prob_null("additional_information_on_deactivation") else None
            )
            record["reason_for_deactivation"] = (
                f"Mock reason {rng.randint(1, 5)}" if rng.random() > _prob_null("reason_for_deactivation") else None
            )
            record["sox_rationale"] = f"Mock SOX rationale {i}" if rng.random() > _prob_null("sox_rationale") else None
            record["evidence_available_from"] = (
                f"Mock source {rng.randint(1, 10)}" if rng.random() > _prob_null("evidence_available_from") else None
            )
            record["performance_measures_available_from"] = (
                f"Mock PM source {rng.randint(1, 10)}" if rng.random() > _prob_null("performance_measures_available_from") else None
            )

            # ---- dates
            record["last_modified_on"] = _make_iso_dt(base_dt, i)
            record["control_created_on"] = _make_mon_dt(base_dt, i)
            record["last_modification_on"] = _make_mon_dt(base_dt, i) if rng.random() > _prob_null("last_modification_on") else None
            record["control_status_date_change"] = _make_mon_dt(base_dt, i) if rng.random() > _prob_null("control_status_date_change") else None
            record["valid_from"] = _make_iso_date(base_dt, i) if rng.random() > _prob_null("valid_from") else None
            record["valid_until"] = _make_iso_date(base_dt, i + 90) if rng.random() > _prob_null("valid_until") else None

            # ---- booleans
            for bf in BOOL_COUNTS.keys():
                record[bf] = _bool_from_profile(rng, bf)

            # ---- owner/assessor/delegate identity
            def fill_person(name_field: str, gpn_field: str) -> None:
                if rng.random() < _prob_null(name_field):
                    record[name_field] = None
                    record[gpn_field] = None
                else:
                    record[name_field] = _make_name(rng)
                    record[gpn_field] = _make_gpn(rng)

            fill_person("control_owner", "control_owner_gpn")
            fill_person("control_assessor", "control_assessor_gpn")
            fill_person("control_delegate", "control_delegate_gpn")
            fill_person("control_created_by", "control_created_by_gpn")
            fill_person("last_control_modification_requested_by", "last_control_modification_requested_by_gpn")

            # ---- admin arrays (parallel)
            admin_len = _sample_len(rng, "control_administrator")
            record["control_administrator"] = [_make_name(rng) for _ in range(admin_len)]
            record["control_administrator_gpn"] = [_make_gpn(rng) for _ in range(admin_len)]

            # ---- related functions (sample from real function IDs)
            rf_len = _sample_len(rng, "related_functions")
            record["related_functions"] = []
            for _ in range(rf_len):
                has_id = rng.random() > (9680 / 92276)
                record["related_functions"].append({
                    "related_function_id": rng.choice(function_ids) if has_id else None,
                    "related_functions_locations_comments": "Based on Owning Org" if not has_id else "See related functions/locations",
                })

            # ---- related locations (sample from real location IDs)
            rl_len = _sample_len(rng, "related_locations")
            record["related_locations"] = []
            for _ in range(rl_len):
                has_id = rng.random() > (10508 / 109469)
                record["related_locations"].append({
                    "related_location_id": rng.choice(location_ids) if has_id else None,
                    "related_functions_locations_comments": "Based on Owning Org" if not has_id else "See related functions/locations",
                })

            # ---- risk themes (sample from real theme IDs + taxonomy IDs)
            rt_len = _sample_len(rng, "risk_theme")
            record["risk_theme"] = []
            for _ in range(rt_len):
                include_numbers = rng.random() > (2258 / 14722)
                if include_numbers and theme_ids:
                    chosen_theme_id = rng.choice(theme_ids)
                    chosen_taxonomy_id = theme_to_taxonomy.get(chosen_theme_id)
                    record["risk_theme"].append({
                        "risk_theme": rng.choice(RISK_THEMES),
                        "taxonomy_number": chosen_taxonomy_id,
                        "risk_theme_number": chosen_theme_id,
                    })
                else:
                    record["risk_theme"].append({
                        "risk_theme": rng.choice(RISK_THEMES),
                        "taxonomy_number": None,
                        "risk_theme_number": None,
                    })

            # ---- multi-value scalars
            cf_len = _sample_len(rng, "category_flags")
            record["category_flags"] = rng.sample(CATEGORY_FLAGS, k=min(cf_len, len(CATEGORY_FLAGS)))

            sa_len = _sample_len(rng, "sox_assertions")
            record["sox_assertions"] = rng.sample(SOX_ASSERTIONS, k=min(sa_len, len(SOX_ASSERTIONS)))

            # ---- validate before writing
            try:
                adapter.validate_python(record)
            except ValidationError as e:
                raise ValueError(f"Generated record failed schema validation at i={i} control_id={cid}: {e}") from e

            out_f.write(orjson.dumps(record, option=orjson.OPT_APPEND_NEWLINE))
            written += 1

    logger.info("Generated {} mock controls to {}", written, output_path)
    return written
