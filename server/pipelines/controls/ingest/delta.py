"""Delta Ingestion Module.

This module handles delta ingestion of controls data into SurrealDB.
Delta ingestion detects changes and updates/inserts only modified controls.

Process:
1. Load CSV tables from split_dir
2. Get existing controls from DB (control_id + last_modified_on)
3. Compare: new controls, changed controls, unchanged
4. Process NEW controls: insert + edges + model pipeline
5. Process CHANGED controls: update + recreate edges (keep model edges)
6. Skip unchanged controls

Uses batches of 10 records for processing (user requirement).
"""

import csv
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from surrealdb import AsyncSurreal
from server.logging_config import get_logger
from server.pipelines.controls.schema import (
    SRC_CONTROLS_REF_RISK_THEME,
    SRC_CONTROLS_REF_ORG_FUNCTION,
    SRC_CONTROLS_REF_ORG_LOCATION,
    SRC_CONTROLS_REF_SOX_ASSERTION,
    SRC_CONTROLS_REF_CATEGORY_FLAG,
    SRC_CONTROLS_MAIN,
    SRC_CONTROLS_VERSIONS,
    SRC_CONTROLS_REL_HAS_RISK_THEME,
    SRC_CONTROLS_REL_HAS_RELATED_FUNCTION,
    SRC_CONTROLS_REL_HAS_RELATED_LOCATION,
    SRC_CONTROLS_REL_HAS_SOX_ASSERTION,
    SRC_CONTROLS_REL_HAS_CATEGORY_FLAG,
)
from .tracker import IngestionTracker

logger = get_logger(name=__name__)

# Batch size for processing (user requirement)
BATCH_SIZE = 10

# CSV file mapping
CSV_FILES = {
    "controls_main": "controls_main.csv",
    "controls_function_hierarchy": "controls_function_hierarchy.csv",
    "controls_location_hierarchy": "controls_location_hierarchy.csv",
    "controls_metadata": "controls_metadata.csv",
    "controls_category_flags": "controls_category_flags.csv",
    "controls_sox_assertions": "controls_sox_assertions.csv",
    "controls_risk_themes": "controls_risk_themes.csv",
    "controls_related_functions": "controls_related_functions.csv",
    "controls_related_locations": "controls_related_locations.csv",
}


def normalize_datetime(dt_str: str) -> Optional[str]:
    """Convert datetime string to ISO format for SurrealDB."""
    if not dt_str:
        return None
    if " " in dt_str and "T" not in dt_str:
        return dt_str.replace(" ", "T") + "Z"
    if "T" in dt_str and not dt_str.endswith("Z"):
        return dt_str + "Z"
    return dt_str


def normalize_datetime_for_comparison(dt_str: str) -> str:
    """Normalize datetime string for comparison purposes.

    Strips timezone info and normalizes format to allow comparison
    between CSV datetimes and SurrealDB datetimes.

    Examples:
        "2024-01-15 10:30:00" -> "2024-01-15T10:30:00"
        "2024-01-15T10:30:00Z" -> "2024-01-15T10:30:00"
        "2024-01-15T10:30:00+00:00" -> "2024-01-15T10:30:00"
    """
    if not dt_str:
        return ""
    s = str(dt_str).strip()
    # Replace space with T
    s = s.replace(" ", "T")
    # Remove timezone suffix
    if s.endswith("Z"):
        s = s[:-1]
    if "+00:00" in s:
        s = s.replace("+00:00", "")
    if "-00:00" in s:
        s = s.replace("-00:00", "")
    # Remove any remaining timezone offset like +05:30
    if "+" in s and "T" in s:
        s = s[:s.rfind("+")]
    return s


def is_newer_timestamp(incoming: str, existing: str) -> bool:
    """Check if incoming timestamp is strictly newer than existing.

    Returns True only if incoming > existing.
    Returns False if incoming <= existing (same or older).

    This prevents overwriting newer data with older data.
    """
    incoming_norm = normalize_datetime_for_comparison(incoming)
    existing_norm = normalize_datetime_for_comparison(existing)

    if not incoming_norm:
        return False  # No incoming timestamp, don't update

    if not existing_norm:
        return True  # No existing timestamp, incoming is newer

    # String comparison works for ISO format (YYYY-MM-DDTHH:MM:SS)
    return incoming_norm > existing_norm


def load_csv(file_path: Path) -> List[Dict[str, Any]]:
    """Load CSV file into list of dicts."""
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    with open(file_path, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)


async def get_existing_controls(db: AsyncSurreal) -> Dict[str, str]:
    """Get all existing control_ids and their last_modified_on from DB.

    Returns:
        Dict mapping control_id -> last_modified_on (ISO string)
    """
    result = await db.query(f"SELECT control_id, last_modified_on FROM {SRC_CONTROLS_MAIN}")
    records = result if isinstance(result, list) else []
    return {r["control_id"]: str(r.get("last_modified_on", "")) for r in records}


async def get_existing_lookup_ids(db: AsyncSurreal) -> Dict[str, Dict[str, str]]:
    """Get existing lookup table ID mappings.

    Returns:
        Dict mapping lookup types to {value -> record_id}
    """
    id_maps: Dict[str, Dict[str, str]] = {
        "risk_theme": {},
        "org_function": {},
        "org_location": {},
        "sox_assertion": {},
        "category_flag": {},
    }

    # Risk themes
    result = await db.query(f"SELECT id, risk_theme_id FROM {SRC_CONTROLS_REF_RISK_THEME}")
    for r in (result if isinstance(result, list) else []):
        id_maps["risk_theme"][r["risk_theme_id"]] = str(r["id"])

    # Functions
    result = await db.query(f"SELECT id, function_id FROM {SRC_CONTROLS_REF_ORG_FUNCTION}")
    for r in (result if isinstance(result, list) else []):
        id_maps["org_function"][r["function_id"]] = str(r["id"])

    # Locations
    result = await db.query(f"SELECT id, location_id FROM {SRC_CONTROLS_REF_ORG_LOCATION}")
    for r in (result if isinstance(result, list) else []):
        id_maps["org_location"][r["location_id"]] = str(r["id"])

    # SOX assertions
    result = await db.query(f"SELECT id, assertion_name FROM {SRC_CONTROLS_REF_SOX_ASSERTION}")
    for r in (result if isinstance(result, list) else []):
        id_maps["sox_assertion"][r["assertion_name"]] = str(r["id"])

    # Category flags
    result = await db.query(f"SELECT id, flag_name FROM {SRC_CONTROLS_REF_CATEGORY_FLAG}")
    for r in (result if isinstance(result, list) else []):
        id_maps["category_flag"][r["flag_name"]] = str(r["id"])

    return id_maps


async def ensure_lookup_entries(
    db: AsyncSurreal,
    tracker: IngestionTracker,
    id_maps: Dict[str, Dict[str, str]],
    risk_themes_records: List[Dict],
    functions_records: List[Dict],
    locations_records: List[Dict],
    sox_assertions_records: List[Dict],
    category_flags_records: List[Dict],
) -> None:
    """Ensure all lookup entries exist, adding any new ones."""
    logger.debug("Ensuring lookup table entries exist")

    # Check for new risk themes
    for r in risk_themes_records:
        rt_id = r.get("risk_theme_number", "")
        if rt_id and rt_id not in id_maps["risk_theme"]:
            safe_id = rt_id.replace(".", "_")
            try:
                await db.query(
                    f"CREATE {SRC_CONTROLS_REF_RISK_THEME}:{safe_id} SET "
                    "risk_theme_id = $rid, risk_theme_name = $name, taxonomy_number = $tax",
                    {"rid": rt_id, "name": r.get("risk_theme", ""), "tax": r.get("taxonomy_number", "")}
                )
                id_maps["risk_theme"][rt_id] = f"{SRC_CONTROLS_REF_RISK_THEME}:{safe_id}"
                tracker.stats.risk_themes_added += 1
            except Exception as e:
                msg = f"Risk theme insert {rt_id}: {e}"
                logger.warning(msg)
                tracker.add_error(msg)

    # Check for new functions
    for r in functions_records:
        func_id = r.get("related_function_id", "")
        if func_id and func_id not in id_maps["org_function"]:
            try:
                await db.query(
                    f"CREATE {SRC_CONTROLS_REF_ORG_FUNCTION}:{func_id} SET "
                    "function_id = $fid, function_name = $name",
                    {"fid": func_id, "name": r.get("related_function_name", "")}
                )
                id_maps["org_function"][func_id] = f"{SRC_CONTROLS_REF_ORG_FUNCTION}:{func_id}"
                tracker.stats.functions_added += 1
            except Exception as e:
                msg = f"Function insert {func_id}: {e}"
                logger.warning(msg)
                tracker.add_error(msg)

    # Check for new locations
    for r in locations_records:
        loc_id = r.get("related_location_id", "")
        if loc_id and loc_id not in id_maps["org_location"]:
            try:
                await db.query(
                    f"CREATE {SRC_CONTROLS_REF_ORG_LOCATION}:{loc_id} SET "
                    "location_id = $lid, location_name = $name",
                    {"lid": loc_id, "name": r.get("related_location_name", "")}
                )
                id_maps["org_location"][loc_id] = f"{SRC_CONTROLS_REF_ORG_LOCATION}:{loc_id}"
                tracker.stats.locations_added += 1
            except Exception as e:
                msg = f"Location insert {loc_id}: {e}"
                logger.warning(msg)
                tracker.add_error(msg)

    # Check for new SOX assertions
    seen_assertions = set()
    for r in sox_assertions_records:
        assertion = r.get("sox_assertion", "")
        if assertion and assertion not in id_maps["sox_assertion"] and assertion not in seen_assertions:
            seen_assertions.add(assertion)
            safe_id = assertion.replace(" ", "_").replace("&", "and")
            try:
                await db.query(
                    f"CREATE {SRC_CONTROLS_REF_SOX_ASSERTION}:{safe_id} SET assertion_name = $name",
                    {"name": assertion}
                )
                id_maps["sox_assertion"][assertion] = f"{SRC_CONTROLS_REF_SOX_ASSERTION}:{safe_id}"
                tracker.stats.sox_assertions_added += 1
            except Exception as e:
                msg = f"SOX assertion insert {assertion}: {e}"
                logger.warning(msg)
                tracker.add_error(msg)

    # Check for new category flags
    seen_flags = set()
    for r in category_flags_records:
        flag = r.get("category_flag", "")
        if flag and flag not in id_maps["category_flag"] and flag not in seen_flags:
            seen_flags.add(flag)
            safe_id = flag.replace(" ", "_")
            try:
                await db.query(
                    f"CREATE {SRC_CONTROLS_REF_CATEGORY_FLAG}:{safe_id} SET flag_name = $name",
                    {"name": flag}
                )
                id_maps["category_flag"][flag] = f"{SRC_CONTROLS_REF_CATEGORY_FLAG}:{safe_id}"
                tracker.stats.category_flags_added += 1
            except Exception as e:
                msg = f"Category flag insert {flag}: {e}"
                logger.warning(msg)
                tracker.add_error(msg)


async def delete_control_relationship_edges(db: AsyncSurreal, record_id: str) -> int:
    """Delete relationship edges from a control (for update scenarios).

    Only deletes relationship edges (risk_theme, related_function, related_location, etc.),
    NOT model output edges (taxonomy, enrichment, cleaned_text, embeddings).
    Model output edges are preserved as the model outputs don't change for updates.

    Returns:
        Number of edges deleted
    """
    edge_tables = [
        SRC_CONTROLS_REL_HAS_RISK_THEME,
        SRC_CONTROLS_REL_HAS_RELATED_FUNCTION,
        SRC_CONTROLS_REL_HAS_RELATED_LOCATION,
        SRC_CONTROLS_REL_HAS_SOX_ASSERTION,
        SRC_CONTROLS_REL_HAS_CATEGORY_FLAG,
    ]

    deleted_count = 0
    for table in edge_tables:
        try:
            result = await db.query(f"DELETE FROM {table} WHERE in = {record_id}")
            if isinstance(result, list):
                deleted_count += len(result)
        except Exception as e:
            logger.warning(f"Error deleting edges from {table}: {e}")

    return deleted_count


async def create_control_edges(
    db: AsyncSurreal,
    tracker: IngestionTracker,
    record_id: str,
    id_maps: Dict[str, Dict[str, str]],
    risk_theme_ids: List[str],
    functions_data: List[Dict[str, str]],
    locations_data: List[Dict[str, str]],
    sox_assertions: List[str],
    category_flags: List[str],
    now_iso: str,
) -> int:
    """Create relationship edges for a control.

    Returns:
        Number of edges created
    """
    edge_count = 0

    # Risk theme edges
    for rt_id in risk_theme_ids:
        if rt_id in id_maps["risk_theme"]:
            try:
                await db.query(
                    f"RELATE {record_id}->{SRC_CONTROLS_REL_HAS_RISK_THEME}->{id_maps['risk_theme'][rt_id]} "
                    "SET created_at = <datetime>$now, source = 'delta_ingest'",
                    {"now": now_iso}
                )
                edge_count += 1
            except Exception as e:
                tracker.add_error(f"Risk theme edge: {e}")

    # Related function edges
    for func_data in functions_data:
        func_id = func_data["id"]
        if func_id in id_maps["org_function"]:
            try:
                await db.query(
                    f"RELATE {record_id}->{SRC_CONTROLS_REL_HAS_RELATED_FUNCTION}->{id_maps['org_function'][func_id]} "
                    "SET created_at = <datetime>$now, comments = $comments",
                    {"now": now_iso, "comments": func_data.get("comments")}
                )
                edge_count += 1
            except Exception as e:
                tracker.add_error(f"Related function edge: {e}")

    # Related location edges
    for loc_data in locations_data:
        loc_id = loc_data["id"]
        if loc_id in id_maps["org_location"]:
            try:
                await db.query(
                    f"RELATE {record_id}->{SRC_CONTROLS_REL_HAS_RELATED_LOCATION}->{id_maps['org_location'][loc_id]} "
                    "SET created_at = <datetime>$now, comments = $comments",
                    {"now": now_iso, "comments": loc_data.get("comments")}
                )
                edge_count += 1
            except Exception as e:
                tracker.add_error(f"Related location edge: {e}")

    # SOX assertion edges
    for assertion in sox_assertions:
        if assertion in id_maps["sox_assertion"]:
            try:
                await db.query(
                    f"RELATE {record_id}->{SRC_CONTROLS_REL_HAS_SOX_ASSERTION}->{id_maps['sox_assertion'][assertion]} "
                    "SET created_at = <datetime>$now",
                    {"now": now_iso}
                )
                edge_count += 1
            except Exception as e:
                tracker.add_error(f"SOX assertion edge: {e}")

    # Category flag edges
    for flag in category_flags:
        if flag in id_maps["category_flag"]:
            try:
                await db.query(
                    f"RELATE {record_id}->{SRC_CONTROLS_REL_HAS_CATEGORY_FLAG}->{id_maps['category_flag'][flag]} "
                    "SET created_at = <datetime>$now",
                    {"now": now_iso}
                )
                edge_count += 1
            except Exception as e:
                tracker.add_error(f"Category flag edge: {e}")

    return edge_count


async def ingest_delta(
    db: AsyncSurreal,
    split_dir: Path,
    tracker: IngestionTracker,
) -> Tuple[Dict[str, str], List[str]]:
    """Run delta ingestion process.

    Args:
        db: SurrealDB connection
        split_dir: Directory containing split CSV files
        tracker: Progress tracker

    Returns:
        Tuple of (control_record_ids for NEW controls, list of changed control_ids)
    """
    logger.info(f"Starting delta ingestion from {split_dir}")

    # Load delta CSV files
    tracker.set_phase("loading_csv", "Loading delta CSV files")
    delta_main_records = load_csv(split_dir / CSV_FILES["controls_main"])
    logger.info(f"Loaded {len(delta_main_records)} control records from delta CSV")

    function_hierarchy_records = load_csv(split_dir / CSV_FILES["controls_function_hierarchy"])
    location_hierarchy_records = load_csv(split_dir / CSV_FILES["controls_location_hierarchy"])
    metadata_records = load_csv(split_dir / CSV_FILES["controls_metadata"])
    category_flags_records = load_csv(split_dir / CSV_FILES["controls_category_flags"])
    sox_assertions_records = load_csv(split_dir / CSV_FILES["controls_sox_assertions"])
    risk_themes_records = load_csv(split_dir / CSV_FILES["controls_risk_themes"])
    functions_records = load_csv(split_dir / CSV_FILES["controls_related_functions"])
    locations_records = load_csv(split_dir / CSV_FILES["controls_related_locations"])

    # Build lookup dicts
    function_hierarchy_by_id = {r["control_id"]: r for r in function_hierarchy_records}
    location_hierarchy_by_id = {r["control_id"]: r for r in location_hierarchy_records}
    metadata_by_id = {r["control_id"]: r for r in metadata_records}

    category_flags_by_id: Dict[str, List[str]] = {}
    for r in category_flags_records:
        cid = r["control_id"]
        if cid not in category_flags_by_id:
            category_flags_by_id[cid] = []
        if r.get("category_flag"):
            category_flags_by_id[cid].append(r["category_flag"])

    sox_assertions_by_id: Dict[str, List[str]] = {}
    for r in sox_assertions_records:
        cid = r["control_id"]
        if cid not in sox_assertions_by_id:
            sox_assertions_by_id[cid] = []
        if r.get("sox_assertion"):
            sox_assertions_by_id[cid].append(r["sox_assertion"])

    risk_themes_by_id: Dict[str, List[str]] = {}
    for r in risk_themes_records:
        cid = r["control_id"]
        if cid not in risk_themes_by_id:
            risk_themes_by_id[cid] = []
        if r.get("risk_theme_number"):
            risk_themes_by_id[cid].append(r["risk_theme_number"])

    functions_by_id: Dict[str, List[Dict[str, str]]] = {}
    for r in functions_records:
        cid = r["control_id"]
        if cid not in functions_by_id:
            functions_by_id[cid] = []
        if r.get("related_function_id"):
            functions_by_id[cid].append({
                "id": r["related_function_id"],
                "comments": r.get("related_functions_locations_comments", ""),
            })

    locations_by_id: Dict[str, List[Dict[str, str]]] = {}
    for r in locations_records:
        cid = r["control_id"]
        if cid not in locations_by_id:
            locations_by_id[cid] = []
        if r.get("related_location_id"):
            locations_by_id[cid].append({
                "id": r["related_location_id"],
                "comments": r.get("related_functions_locations_comments", ""),
            })

    # Get existing controls and lookup tables
    tracker.set_phase("analyzing_delta", "Analyzing delta changes")
    existing_controls = await get_existing_controls(db)
    logger.info(f"Found {len(existing_controls)} existing controls in DB")

    id_maps = await get_existing_lookup_ids(db)
    logger.debug(
        f"Existing ref tables: risk_theme={len(id_maps['risk_theme'])}, "
        f"org_function={len(id_maps['org_function'])}, "
        f"org_location={len(id_maps['org_location'])}, "
        f"sox_assertion={len(id_maps['sox_assertion'])}, "
        f"category_flag={len(id_maps['category_flag'])}"
    )

    # Analyze changes
    delta_ids = set(r["control_id"] for r in delta_main_records)
    existing_ids = set(existing_controls.keys())

    new_ids = delta_ids - existing_ids
    common_ids = delta_ids & existing_ids

    logger.info(f"Delta analysis: new={len(new_ids)}, common={len(common_ids)}")

    delta_main_by_id = {r["control_id"]: r for r in delta_main_records}

    controls_to_process = []
    for control_id in delta_ids:
        delta_record = delta_main_by_id[control_id]
        delta_last_modified = delta_record.get("last_modified_on", "")

        if control_id in new_ids:
            controls_to_process.append((control_id, "new", delta_record))
        else:
            existing_last_modified = existing_controls.get(control_id, "")

            # Only update if incoming timestamp is NEWER than existing
            # This prevents overwriting newer data with older data
            if is_newer_timestamp(delta_last_modified, existing_last_modified):
                controls_to_process.append((control_id, "changed", delta_record))
                logger.debug(
                    f"Control {control_id} will be updated: incoming='{delta_last_modified}' > existing='{existing_last_modified}'"
                )
            else:
                # Same or older timestamp - skip this record
                tracker.stats.unchanged_records += 1
                logger.debug(
                    f"Control {control_id} skipped (not newer): incoming='{delta_last_modified}' <= existing='{existing_last_modified}'"
                )

    logger.info(
        f"Controls to process: new={len([c for c in controls_to_process if c[1] == 'new'])}, "
        f"changed={len([c for c in controls_to_process if c[1] == 'changed'])}, "
        f"unchanged={tracker.stats.unchanged_records}"
    )

    if not controls_to_process:
        logger.info("No changes detected, nothing to process")
        return {}, []

    # Ensure lookup tables have all needed entries
    tracker.set_phase("ensuring_lookups", "Ensuring lookup table entries exist")
    await ensure_lookup_entries(
        db, tracker, id_maps,
        risk_themes_records, functions_records, locations_records,
        sox_assertions_records, category_flags_records
    )

    # Process controls in batches
    tracker.set_phase("processing_controls", "Processing new/changed controls")
    tracker.start(len(controls_to_process), "delta_processing")

    new_control_record_ids: Dict[str, str] = {}
    changed_control_ids: List[str] = []
    now_iso = datetime.now().isoformat() + "Z"

    total_batches = (len(controls_to_process) + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(f"Processing {len(controls_to_process)} controls in {total_batches} batches")

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(controls_to_process))
        batch = controls_to_process[start_idx:end_idx]

        tracker.start_batch(batch_num + 1, len(batch))
        logger.debug(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch)} records)")

        for control_id, change_type, main_data in batch:
            try:
                function_hierarchy_data = function_hierarchy_by_id.get(control_id, {})
                location_hierarchy_data = location_hierarchy_by_id.get(control_id, {})
                metadata_data = metadata_by_id.get(control_id, {})

                # Build control object
                control_obj = {
                    "control_title": main_data.get("control_title"),
                    "control_description": main_data.get("control_description"),
                    "key_control": main_data.get("key_control"),
                    "hierarchy_level": main_data.get("hierarchy_level"),
                    "parent_control_id": main_data.get("parent_control_id") or None,
                    "preventative_detective": main_data.get("preventative_detective"),
                    "manual_automated": main_data.get("manual_automated"),
                    "execution_frequency": main_data.get("execution_frequency"),
                    "four_eyes_check": main_data.get("four_eyes_check"),
                    "evidence_description": main_data.get("evidence_description"),
                    "evidence_available_from": main_data.get("evidence_available_from"),
                    "performance_measures_required": main_data.get("performance_measures_required"),
                    "performance_measures_available_from": main_data.get("performance_measures_available_from"),
                    "control_status": main_data.get("control_status"),
                    "valid_from": main_data.get("valid_from"),
                    "valid_until": main_data.get("valid_until") or None,
                    "reason_for_deactivation": main_data.get("reason_for_deactivation") or None,
                    "status_updates": main_data.get("status_updates") or None,
                }

                function_hierarchy_obj = {
                    k: (v if v else None)
                    for k, v in function_hierarchy_data.items()
                    if k != "control_id"
                } or None

                location_hierarchy_obj = {
                    k: (v if v else None)
                    for k, v in location_hierarchy_data.items()
                    if k != "control_id"
                } or None

                metadata_obj = {
                    k: (v if v else None)
                    for k, v in metadata_data.items()
                    if k != "control_id"
                }

                last_modified_iso = normalize_datetime(main_data.get("last_modified_on", ""))
                safe_control_id = control_id.replace("-", "_")
                record_id = f"{SRC_CONTROLS_MAIN}:{safe_control_id}"

                if change_type == "new":
                    # Create new control record
                    await db.query(
                        f"CREATE {record_id} SET "
                        "control_id = $control_id, "
                        "last_modified_on = <datetime>$last_modified_on, "
                        "control = $control, "
                        "owning_function_hierarchy = $owning_function_hierarchy, "
                        "owning_location_hierarchy = $owning_location_hierarchy, "
                        "metadata = $metadata",
                        {
                            "control_id": control_id,
                            "last_modified_on": last_modified_iso,
                            "control": control_obj,
                            "owning_function_hierarchy": function_hierarchy_obj,
                            "owning_location_hierarchy": location_hierarchy_obj,
                            "metadata": metadata_obj,
                        }
                    )
                    new_control_record_ids[control_id] = record_id

                    # Create relationships for new control
                    edge_count = await create_control_edges(
                        db, tracker, record_id, id_maps,
                        risk_themes_by_id.get(control_id, []),
                        functions_by_id.get(control_id, []),
                        locations_by_id.get(control_id, []),
                        sox_assertions_by_id.get(control_id, []),
                        category_flags_by_id.get(control_id, []),
                        now_iso
                    )
                    tracker.increment_edges_created(edge_count)
                    tracker.complete_record(control_id, operation="inserted", is_new=True)

                else:  # changed
                    # Update existing control record
                    await db.query(
                        f"UPDATE {record_id} SET "
                        "last_modified_on = <datetime>$last_modified_on, "
                        "control = $control, "
                        "owning_function_hierarchy = $owning_function_hierarchy, "
                        "owning_location_hierarchy = $owning_location_hierarchy, "
                        "metadata = $metadata",
                        {
                            "last_modified_on": last_modified_iso,
                            "control": control_obj,
                            "owning_function_hierarchy": function_hierarchy_obj,
                            "owning_location_hierarchy": location_hierarchy_obj,
                            "metadata": metadata_obj,
                        }
                    )
                    changed_control_ids.append(control_id)

                    # Delete old relationship edges and recreate them
                    deleted_count = await delete_control_relationship_edges(db, record_id)
                    tracker.increment_edges_deleted(deleted_count)

                    edge_count = await create_control_edges(
                        db, tracker, record_id, id_maps,
                        risk_themes_by_id.get(control_id, []),
                        functions_by_id.get(control_id, []),
                        locations_by_id.get(control_id, []),
                        sox_assertions_by_id.get(control_id, []),
                        category_flags_by_id.get(control_id, []),
                        now_iso
                    )
                    tracker.increment_edges_created(edge_count)
                    tracker.complete_record(control_id, operation="updated", is_updated=True)

                # Create version record for all processed controls
                await db.query(
                    f"CREATE {SRC_CONTROLS_VERSIONS} SET "
                    "control_id = $control_id, "
                    "version_date = <datetime>$version_date, "
                    "snapshot = $snapshot",
                    {
                        "control_id": control_id,
                        "version_date": last_modified_iso,
                        "snapshot": {
                            "control_id": control_id,
                            "last_modified_on": main_data.get("last_modified_on"),
                            "control": control_obj,
                            "owning_function_hierarchy": function_hierarchy_obj,
                            "owning_location_hierarchy": location_hierarchy_obj,
                            "metadata": metadata_obj,
                        },
                    }
                )

            except Exception as e:
                error_msg = f"Control {change_type} {control_id}: {e}"
                logger.error(error_msg)
                tracker.fail_record(control_id, str(e))

    logger.info(
        f"Delta ingestion completed: new={len(new_control_record_ids)}, "
        f"changed={len(changed_control_ids)}, unchanged={tracker.stats.unchanged_records}"
    )

    return new_control_record_ids, changed_control_ids
