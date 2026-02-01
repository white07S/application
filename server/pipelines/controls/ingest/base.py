"""Base Ingestion Module.

This module handles base ingestion of controls data into SurrealDB.
Base ingestion clears all existing data and loads all controls from CSV files.

Process:
1. Load all CSV tables from split_dir
2. Populate reference tables (risk_themes, functions, locations, sox_assertions, category_flags)
3. Insert all controls into src_controls_main with nested structure
4. Create all relationship edges
5. Create version records

Uses batches of 10 records for processing (user requirement).
"""

import csv
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Set, Optional

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
    ALL_TABLES,
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


def load_csv(file_path: Path) -> List[Dict[str, Any]]:
    """Load CSV file into list of dicts."""
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    with open(file_path, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)


async def clear_all_tables(db: AsyncSurreal, tracker: IngestionTracker) -> None:
    """Clear all data from all tables."""
    tracker.set_phase("clearing_tables", "Clearing all existing tables")
    logger.info("Clearing all tables for base ingestion")

    for table in ALL_TABLES:
        try:
            await db.query(f"DELETE FROM {table}")
            logger.debug(f"Cleared table: {table}")
        except Exception as e:
            error_msg = f"Error clearing {table}: {e}"
            logger.warning(error_msg)
            tracker.add_error(error_msg)


async def ingest_lookup_tables(
    db: AsyncSurreal,
    split_dir: Path,
    tracker: IngestionTracker,
) -> Dict[str, Dict[str, str]]:
    """Load CSV files and create lookup table records.

    Returns:
        Dict mapping lookup types to {value -> record_id}
    """
    tracker.set_phase("loading_reference_tables", "Loading reference tables")
    logger.info("Loading reference tables from CSV files")

    # Load all related CSV files
    risk_themes = load_csv(split_dir / CSV_FILES["controls_risk_themes"])
    functions = load_csv(split_dir / CSV_FILES["controls_related_functions"])
    locations = load_csv(split_dir / CSV_FILES["controls_related_locations"])
    sox_assertions = load_csv(split_dir / CSV_FILES["controls_sox_assertions"])
    category_flags = load_csv(split_dir / CSV_FILES["controls_category_flags"])

    logger.debug(
        f"Loaded CSV: risk_themes={len(risk_themes)}, "
        f"functions={len(functions)}, locations={len(locations)}, "
        f"sox_assertions={len(sox_assertions)}, category_flags={len(category_flags)}"
    )

    # Build unique lookup data and record ID mappings
    id_maps: Dict[str, Dict[str, str]] = {
        "risk_theme": {},
        "org_function": {},
        "org_location": {},
        "sox_assertion": {},
        "category_flag": {},
    }

    # Insert unique risk themes
    logger.debug("Inserting risk theme records")
    unique_themes: Dict[str, Dict[str, str]] = {}
    for r in risk_themes:
        rt_id = r.get("risk_theme_number", "")
        if rt_id and rt_id not in unique_themes:
            unique_themes[rt_id] = {
                "risk_theme_id": rt_id,
                "risk_theme_name": r.get("risk_theme", ""),
                "taxonomy_number": r.get("taxonomy_number", ""),
            }

    for rt_id, data in unique_themes.items():
        try:
            safe_id = rt_id.replace(".", "_")
            await db.query(
                f"CREATE {SRC_CONTROLS_REF_RISK_THEME}:{safe_id} SET "
                "risk_theme_id = $rid, risk_theme_name = $name, taxonomy_number = $tax",
                {"rid": data["risk_theme_id"], "name": data["risk_theme_name"], "tax": data["taxonomy_number"]}
            )
            id_maps["risk_theme"][rt_id] = f"{SRC_CONTROLS_REF_RISK_THEME}:{safe_id}"
            tracker.stats.risk_themes_added += 1
        except Exception as e:
            tracker.add_error(f"Risk theme insert {rt_id}: {e}")

    logger.info(f"Inserted {tracker.stats.risk_themes_added} risk themes")

    # Insert unique functions
    logger.debug("Inserting function records")
    unique_functions: Dict[str, str] = {}
    for r in functions:
        func_id = r.get("related_function_id", "")
        if func_id and func_id not in unique_functions:
            unique_functions[func_id] = r.get("related_function_name", "")

    for func_id, func_name in unique_functions.items():
        try:
            await db.query(
                f"CREATE {SRC_CONTROLS_REF_ORG_FUNCTION}:{func_id} SET "
                "function_id = $fid, function_name = $name",
                {"fid": func_id, "name": func_name}
            )
            id_maps["org_function"][func_id] = f"{SRC_CONTROLS_REF_ORG_FUNCTION}:{func_id}"
            tracker.stats.functions_added += 1
        except Exception as e:
            tracker.add_error(f"Function insert {func_id}: {e}")

    logger.info(f"Inserted {tracker.stats.functions_added} functions")

    # Insert unique locations
    logger.debug("Inserting location records")
    unique_locations: Dict[str, str] = {}
    for r in locations:
        loc_id = r.get("related_location_id", "")
        if loc_id and loc_id not in unique_locations:
            unique_locations[loc_id] = r.get("related_location_name", "")

    for loc_id, loc_name in unique_locations.items():
        try:
            await db.query(
                f"CREATE {SRC_CONTROLS_REF_ORG_LOCATION}:{loc_id} SET "
                "location_id = $lid, location_name = $name",
                {"lid": loc_id, "name": loc_name}
            )
            id_maps["org_location"][loc_id] = f"{SRC_CONTROLS_REF_ORG_LOCATION}:{loc_id}"
            tracker.stats.locations_added += 1
        except Exception as e:
            tracker.add_error(f"Location insert {loc_id}: {e}")

    logger.info(f"Inserted {tracker.stats.locations_added} locations")

    # Insert unique SOX assertions
    logger.debug("Inserting SOX assertion records")
    unique_assertions: Set[str] = set()
    for r in sox_assertions:
        assertion = r.get("sox_assertion", "")
        if assertion:
            unique_assertions.add(assertion)

    for assertion in unique_assertions:
        try:
            safe_id = assertion.replace(" ", "_").replace("&", "and")
            await db.query(
                f"CREATE {SRC_CONTROLS_REF_SOX_ASSERTION}:{safe_id} SET assertion_name = $name",
                {"name": assertion}
            )
            id_maps["sox_assertion"][assertion] = f"{SRC_CONTROLS_REF_SOX_ASSERTION}:{safe_id}"
            tracker.stats.sox_assertions_added += 1
        except Exception as e:
            tracker.add_error(f"SOX assertion insert {assertion}: {e}")

    logger.info(f"Inserted {tracker.stats.sox_assertions_added} SOX assertions")

    # Insert unique category flags
    logger.debug("Inserting category flag records")
    unique_flags: Set[str] = set()
    for r in category_flags:
        flag = r.get("category_flag", "")
        if flag:
            unique_flags.add(flag)

    for flag in unique_flags:
        try:
            safe_id = flag.replace(" ", "_")
            await db.query(
                f"CREATE {SRC_CONTROLS_REF_CATEGORY_FLAG}:{safe_id} SET flag_name = $name",
                {"name": flag}
            )
            id_maps["category_flag"][flag] = f"{SRC_CONTROLS_REF_CATEGORY_FLAG}:{safe_id}"
            tracker.stats.category_flags_added += 1
        except Exception as e:
            tracker.add_error(f"Category flag insert {flag}: {e}")

    logger.info(f"Inserted {tracker.stats.category_flags_added} category flags")

    return id_maps


async def ingest_controls_main(
    db: AsyncSurreal,
    split_dir: Path,
    tracker: IngestionTracker,
    id_maps: Dict[str, Dict[str, str]],
) -> Dict[str, str]:
    """Load src_controls_main records and create relationships.

    Returns:
        Dict mapping control_id -> record_id
    """
    tracker.set_phase("loading_controls", "Loading controls and creating relationships")
    logger.info("Loading controls from CSV files")

    # Load CSV files
    main_records = load_csv(split_dir / CSV_FILES["controls_main"])
    function_hierarchy_records = load_csv(split_dir / CSV_FILES["controls_function_hierarchy"])
    location_hierarchy_records = load_csv(split_dir / CSV_FILES["controls_location_hierarchy"])
    metadata_records = load_csv(split_dir / CSV_FILES["controls_metadata"])
    category_flags_records = load_csv(split_dir / CSV_FILES["controls_category_flags"])
    sox_assertions_records = load_csv(split_dir / CSV_FILES["controls_sox_assertions"])
    risk_themes_records = load_csv(split_dir / CSV_FILES["controls_risk_themes"])
    functions_records = load_csv(split_dir / CSV_FILES["controls_related_functions"])
    locations_records = load_csv(split_dir / CSV_FILES["controls_related_locations"])

    logger.info(f"Loaded {len(main_records)} control records from CSV")

    # Build lookup dicts
    function_hierarchy_by_id = {r["control_id"]: r for r in function_hierarchy_records}
    location_hierarchy_by_id = {r["control_id"]: r for r in location_hierarchy_records}
    metadata_by_id = {r["control_id"]: r for r in metadata_records}

    # Build 1-to-many lookups
    category_flags_by_id: Dict[str, List[str]] = {}
    for r in category_flags_records:
        cid = r["control_id"]
        if cid not in category_flags_by_id:
            category_flags_by_id[cid] = []
        if r.get("category_flag"):
            category_flags_by_id[cid].append(r["category_flag"])

    sox_by_id: Dict[str, List[str]] = {}
    for r in sox_assertions_records:
        cid = r["control_id"]
        if cid not in sox_by_id:
            sox_by_id[cid] = []
        if r.get("sox_assertion"):
            sox_by_id[cid].append(r["sox_assertion"])

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

    # Track control_id -> record_id mapping
    control_record_ids: Dict[str, str] = {}
    now_iso = datetime.now().isoformat() + "Z"

    # Insert src_controls_main records in batches
    logger.info(f"Inserting controls in batches of {BATCH_SIZE}")
    total_batches = (len(main_records) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(main_records))
        batch = main_records[start_idx:end_idx]

        tracker.start_batch(batch_num + 1, len(batch))
        logger.debug(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch)} records)")

        for main_data in batch:
            control_id = main_data["control_id"]

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

                # Build owning hierarchy objects
                owning_function_hierarchy_obj = {
                    k: (v if v else None)
                    for k, v in function_hierarchy_data.items()
                    if k != "control_id"
                } or None

                owning_location_hierarchy_obj = {
                    k: (v if v else None)
                    for k, v in location_hierarchy_data.items()
                    if k != "control_id"
                } or None

                # Build metadata object
                metadata_obj = {
                    k: (v if v else None)
                    for k, v in metadata_data.items()
                    if k != "control_id"
                }

                last_modified_iso = normalize_datetime(main_data.get("last_modified_on", ""))

                # Create control record with control_id as the record identifier
                safe_control_id = control_id.replace("-", "_")
                await db.query(
                    f"CREATE {SRC_CONTROLS_MAIN}:{safe_control_id} SET "
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
                        "owning_function_hierarchy": owning_function_hierarchy_obj,
                        "owning_location_hierarchy": owning_location_hierarchy_obj,
                        "metadata": metadata_obj,
                    }
                )
                control_record_ids[control_id] = f"{SRC_CONTROLS_MAIN}:{safe_control_id}"

                # Create version record
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
                            "owning_function_hierarchy": owning_function_hierarchy_obj,
                            "owning_location_hierarchy": owning_location_hierarchy_obj,
                            "metadata": metadata_obj,
                        },
                    }
                )

                tracker.complete_record(control_id, operation="inserted", is_new=True)

            except Exception as e:
                error_msg = f"Control insert {control_id}: {e}"
                logger.error(error_msg)
                tracker.fail_record(control_id, str(e))

    logger.info(f"Inserted {len(control_record_ids)} controls")

    # Create relationship edges
    tracker.set_phase("creating_edges", "Creating relationship edges")
    logger.info("Creating relationship edges")

    edge_count = 0
    for control_id, record_id in control_record_ids.items():
        # Risk theme edges
        for rt_id in risk_themes_by_id.get(control_id, []):
            if rt_id in id_maps["risk_theme"]:
                try:
                    await db.query(
                        f"RELATE {record_id}->{SRC_CONTROLS_REL_HAS_RISK_THEME}->{id_maps['risk_theme'][rt_id]} "
                        "SET created_at = <datetime>$now, source = 'base_ingest'",
                        {"now": now_iso}
                    )
                    edge_count += 1
                except Exception as e:
                    tracker.add_error(f"Risk theme edge {control_id}->{rt_id}: {e}")

        # Related function edges
        for func_data in functions_by_id.get(control_id, []):
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
                    tracker.add_error(f"Related function edge {control_id}->{func_id}: {e}")

        # Related location edges
        for loc_data in locations_by_id.get(control_id, []):
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
                    tracker.add_error(f"Related location edge {control_id}->{loc_id}: {e}")

        # SOX assertion edges
        for assertion in sox_by_id.get(control_id, []):
            if assertion in id_maps["sox_assertion"]:
                try:
                    await db.query(
                        f"RELATE {record_id}->{SRC_CONTROLS_REL_HAS_SOX_ASSERTION}->{id_maps['sox_assertion'][assertion]} "
                        "SET created_at = <datetime>$now",
                        {"now": now_iso}
                    )
                    edge_count += 1
                except Exception as e:
                    tracker.add_error(f"SOX assertion edge {control_id}->{assertion}: {e}")

        # Category flag edges
        for flag in category_flags_by_id.get(control_id, []):
            if flag in id_maps["category_flag"]:
                try:
                    await db.query(
                        f"RELATE {record_id}->{SRC_CONTROLS_REL_HAS_CATEGORY_FLAG}->{id_maps['category_flag'][flag]} "
                        "SET created_at = <datetime>$now",
                        {"now": now_iso}
                    )
                    edge_count += 1
                except Exception as e:
                    tracker.add_error(f"Category flag edge {control_id}->{flag}: {e}")

    tracker.increment_edges_created(edge_count)
    logger.info(f"Created {edge_count} relationship edges")

    return control_record_ids


async def ingest_base(db: AsyncSurreal, split_dir: Path, tracker: IngestionTracker) -> Dict[str, str]:
    """Run base ingestion process.

    Args:
        db: SurrealDB connection
        split_dir: Directory containing split CSV files
        tracker: Progress tracker

    Returns:
        Dict mapping control_id -> record_id for all inserted controls
    """
    logger.info(f"Starting base ingestion from {split_dir}")

    try:
        # Clear all tables
        await clear_all_tables(db, tracker)

        # Create lookup tables
        id_maps = await ingest_lookup_tables(db, split_dir, tracker)

        # Load controls and create relationships
        control_record_ids = await ingest_controls_main(db, split_dir, tracker, id_maps)

        logger.info("Base ingestion completed successfully")
        return control_record_ids

    except Exception as e:
        error_msg = f"Base ingestion failed: {e}"
        logger.error(error_msg)
        tracker.add_error(error_msg)
        raise
