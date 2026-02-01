"""Split an enterprise-format controls CSV into component CSV tables.

This module takes an enterprise-format CSV file (with blank rows and timestamp)
and splits it into 9 component CSV tables for further processing.
"""
import csv
from pathlib import Path
from typing import Dict

import pandas as pd

from server.logging_config import get_logger

logger = get_logger(name=__name__)

# Expected file names for output tables
TABLE_FILE_MAP = {
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

# Column definitions for each table
CONTROLS_MAIN_COLUMNS = [
    "control_id",
    "control_title",
    "control_description",
    "key_control",
    "hierarchy_level",
    "parent_control_id",
    "preventative_detective",
    "manual_automated",
    "execution_frequency",
    "four_eyes_check",
    "evidence_description",
    "evidence_available_from",
    "performance_measures_required",
    "performance_measures_available_from",
    "control_status",
    "valid_from",
    "valid_until",
    "reason_for_deactivation",
    "status_updates",
    "last_modified_on",
]

FUNCTION_HIERARCHY_COLUMNS = [
    "group_id",
    "group_name",
    "division_id",
    "division_name",
    "unit_id",
    "unit_name",
    "area_id",
    "area_name",
    "sector_id",
    "sector_name",
    "segment_id",
    "segment_name",
    "function_id",
    "function_name",
]

LOCATION_HIERARCHY_COLUMNS = [
    "l0_location_id",
    "l0_location_name",
    "region_id",
    "region_name",
    "sub_region_id",
    "sub_region_name",
    "country_id",
    "country_name",
    "company_id",
    "company_short_name",
]

METADATA_COLUMNS = [
    "control_owner",
    "control_owner_gpn",
    "control_instance_owner_role",
    "control_administrator",
    "control_administrator_gpn",
    "control_delegate",
    "control_delegate_gpn",
    "control_assessor",
    "control_assessor_gpn",
    "is_assessor_control_owner",
    "sox_relevant",
    "ccar_relevant",
    "bcbs239_relevant",
    "ey_reliant",
    "sox_rationale",
    "local_functional_information",
    "kpci_governance_forum",
    "financial_statement_line_item",
    "it_application_system_supporting",
    "additional_information_on_deactivation",
    "control_created_by",
    "control_created_by_gpn",
    "control_created_on",
    "last_control_modification_requested_by",
    "last_control_modification_requested_by_gpn",
    "last_modification_on",
    "control_status_date_change",
]


def read_enterprise_csv(input_path: Path) -> pd.DataFrame:
    """Read the enterprise-format CSV.

    The format includes:
    - First 9 rows are blank
    - Row 10 contains timestamp
    - Row 11 has headers (with blank leading column)
    - Data starts from row 12 (with blank leading column)

    Args:
        input_path: Path to the enterprise CSV file

    Returns:
        DataFrame with enterprise data (blank column removed)
    """
    df = pd.read_csv(input_path, skiprows=10)
    df = df.iloc[:, 1:]  # drop blank column A

    logger.info("Read enterprise CSV: {} rows, {} columns", len(df), len(df.columns))
    return df


def split_controls_csv(input_path: Path, output_dir: Path) -> Dict[str, pd.DataFrame]:
    """Split enterprise-format controls CSV into component tables.

    Takes an enterprise-format CSV and splits it into 9 component tables:
    - controls_main: Core control attributes
    - controls_function_hierarchy: Function hierarchy data
    - controls_location_hierarchy: Location hierarchy data
    - controls_metadata: Metadata and ownership information
    - controls_category_flags: Category flags (1:N relationship)
    - controls_sox_assertions: SOX assertions (1:N relationship)
    - controls_risk_themes: Risk themes with taxonomy (1:N relationship)
    - controls_related_functions: Related functions (1:N relationship)
    - controls_related_locations: Related locations (1:N relationship)

    Args:
        input_path: Path to enterprise-format CSV file
        output_dir: Directory to write output CSV files

    Returns:
        Dictionary mapping table names to DataFrames
    """
    logger.info("Starting split for {}", input_path)

    df = read_enterprise_csv(input_path)
    tables: Dict[str, pd.DataFrame] = {}

    # Split simple tables (direct column mapping)
    tables["controls_main"] = df[CONTROLS_MAIN_COLUMNS].copy()
    tables["controls_function_hierarchy"] = df[["control_id"] + FUNCTION_HIERARCHY_COLUMNS].copy()
    tables["controls_location_hierarchy"] = df[["control_id"] + LOCATION_HIERARCHY_COLUMNS].copy()
    tables["controls_metadata"] = df[["control_id"] + METADATA_COLUMNS].copy()

    # Split category_flags (comma-separated values -> individual records)
    cat_records = []
    for _, row in df.iterrows():
        flags = row.get("category_flags")
        if pd.isna(flags) or str(flags).strip() == "":
            continue
        for flag in str(flags).split(","):
            flag = flag.strip()
            if flag:
                cat_records.append({"control_id": row["control_id"], "category_flag": flag})
    tables["controls_category_flags"] = pd.DataFrame(cat_records)

    # Split sox_assertions (comma-separated values -> individual records)
    sox_records = []
    for _, row in df.iterrows():
        val = row.get("sox_assertions")
        if pd.isna(val) or str(val).strip() == "":
            continue
        for assertion in str(val).split(","):
            assertion = assertion.strip()
            if assertion:
                sox_records.append({"control_id": row["control_id"], "sox_assertion": assertion})
    tables["controls_sox_assertions"] = pd.DataFrame(sox_records)

    # Split risk_themes (with taxonomy and theme numbers)
    risk_records = []
    for _, row in df.iterrows():
        names = row.get("risk_themes")
        tax_nums = row.get("risk_theme_taxonomy_numbers")
        theme_nums = row.get("risk_theme_numbers")

        if pd.isna(names) or str(names).strip() == "":
            continue

        name_list = [x.strip() for x in str(names).split(",")]
        tax_list = [x.strip() for x in str(tax_nums).split(",")] if pd.notna(tax_nums) else [""] * len(name_list)
        num_list = [x.strip() for x in str(theme_nums).split(",")] if pd.notna(theme_nums) else [""] * len(name_list)

        for n, t, num in zip(name_list, tax_list, num_list):
            if n:
                risk_records.append({
                    "control_id": row["control_id"],
                    "risk_theme": n,
                    "taxonomy_number": t,
                    "risk_theme_number": num,
                })
    tables["controls_risk_themes"] = pd.DataFrame(risk_records)

    # Split related_functions (paired IDs and names)
    func_records = []
    for _, row in df.iterrows():
        ids = row.get("related_function_ids")
        names = row.get("related_function_names")
        comment = row.get("related_functions_comments")

        if pd.isna(ids) or str(ids).strip() == "":
            continue

        id_list = [x.strip() for x in str(ids).split(",")]
        name_list = [x.strip() for x in str(names).split(",")] if pd.notna(names) else [""] * len(id_list)

        for rid, rname in zip(id_list, name_list):
            if rid or rname:
                func_records.append({
                    "control_id": row["control_id"],
                    "related_functions_locations_comments": comment,
                    "related_function_id": rid,
                    "related_function_name": rname,
                })
    tables["controls_related_functions"] = pd.DataFrame(func_records)

    # Split related_locations (paired IDs and names)
    loc_records = []
    for _, row in df.iterrows():
        ids = row.get("related_location_ids")
        names = row.get("related_location_names")
        comment = row.get("related_locations_comments")

        if pd.isna(ids) or str(ids).strip() == "":
            continue

        id_list = [x.strip() for x in str(ids).split(",")]
        name_list = [x.strip() for x in str(names).split(",")] if pd.notna(names) else [""] * len(id_list)

        for rid, rname in zip(id_list, name_list):
            if rid or rname:
                loc_records.append({
                    "control_id": row["control_id"],
                    "related_functions_locations_comments": comment,
                    "related_location_id": rid,
                    "related_location_name": rname,
                })
    tables["controls_related_locations"] = pd.DataFrame(loc_records)

    # Write all tables to output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, df_out in tables.items():
        output_path = output_dir / TABLE_FILE_MAP[name]
        df_out.to_csv(output_path, index=False)
        logger.info("Wrote {}: {} rows", output_path.name, len(df_out))

    logger.info("Split complete: {} tables written to {}", len(tables), output_dir)
    return tables
