"""Validate controls CSV tables for schema and relationship consistency.

This module validates the split controls CSV tables to ensure:
- Required columns exist
- Date formats are valid
- Boolean values are correct
- Referential integrity (control_ids match across tables)
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from server.logging_config import get_logger

logger = get_logger(name=__name__)

# File mapping from split_controls
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

# Date columns to validate
DATE_COLUMNS = [
    "evidence_available_from",
    "performance_measures_available_from",
    "valid_from",
    "valid_until",
    "last_modified_on",
    "control_created_on",
    "last_modification_on",
    "control_status_date_change",
]

# Boolean columns to validate
BOOL_COLUMNS = [
    "key_control",
    "four_eyes_check",
    "performance_measures_required",
    "is_assessor_control_owner",
    "sox_relevant",
    "ccar_relevant",
    "bcbs239_relevant",
    "ey_reliant",
]


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""

    table: str
    column: Optional[str]
    message: str

    def __str__(self) -> str:
        """String representation of the issue."""
        prefix = f"{self.column}: " if self.column else ""
        return f"[{self.table}] {prefix}{self.message}"


@dataclass
class ValidationResult:
    """Result of validation with errors and warnings."""

    is_valid: bool
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)



def load_tables_from_csv(base_dir: Path) -> Dict[str, pd.DataFrame]:
    """Load all controls tables from CSV files.

    Args:
        base_dir: Directory containing the split CSV files

    Returns:
        Dictionary mapping table names to DataFrames

    Raises:
        FileNotFoundError: If required files are missing
    """
    dataframes: Dict[str, pd.DataFrame] = {}
    for name, filename in TABLE_FILE_MAP.items():
        path = base_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing required file: {path}")
        dataframes[name] = pd.read_csv(path, dtype=str)
        logger.debug("Loaded {}: {} rows", filename, len(dataframes[name]))

    return dataframes


def validate_columns(table_name: str, df: pd.DataFrame, report: ValidationResult) -> None:
    """Validate basic column requirements.

    Args:
        table_name: Name of the table being validated
        df: DataFrame to validate
        report: ValidationResult to append errors to
    """
    # Check if all values are null/empty
    if df.isnull().all(axis=None):
        report.errors.append(ValidationIssue(table_name, None, "All values are null/empty."))

    # Check for required control_id column
    if "control_id" not in df.columns:
        report.errors.append(ValidationIssue(table_name, None, "Missing control_id column."))


def validate_dates(table_name: str, df: pd.DataFrame, report: ValidationResult) -> None:
    """Validate date column formats.

    Args:
        table_name: Name of the table being validated
        df: DataFrame to validate
        report: ValidationResult to append errors to
    """
    for col in DATE_COLUMNS:
        if col not in df.columns:
            continue

        series = df[col].dropna()
        for value in series:
            try:
                pd.to_datetime(value)
            except Exception:
                report.errors.append(
                    ValidationIssue(table_name, col, f"Unparseable date value: {value}")
                )


def validate_bools(table_name: str, df: pd.DataFrame, report: ValidationResult) -> None:
    """Validate boolean column values.

    Args:
        table_name: Name of the table being validated
        df: DataFrame to validate
        report: ValidationResult to append errors to
    """
    allowed = {True, False, "True", "False", 1, 0, "1", "0"}

    for col in BOOL_COLUMNS:
        if col not in df.columns:
            continue

        invalid = df[col].dropna().apply(lambda v: v not in allowed)
        if invalid.any():
            bad_values = df.loc[invalid, col].unique()[:5]
            report.errors.append(
                ValidationIssue(
                    table_name,
                    col,
                    f"Found non-boolean values: {', '.join(str(v) for v in bad_values)}"
                )
            )


def validate_relationships(dataframes: Dict[str, pd.DataFrame], report: ValidationResult) -> None:
    """Validate referential integrity across tables.

    Ensures that:
    - No duplicate control_ids in controls_main
    - All control_ids in child tables exist in controls_main

    Args:
        dataframes: Dictionary of table DataFrames
        report: ValidationResult to append errors to
    """
    # Get all control_ids from main table
    main_ids = set(dataframes["controls_main"]["control_id"].dropna())

    # Check for duplicates in controls_main
    duplicates = dataframes["controls_main"]["control_id"].dropna().duplicated()
    if duplicates.any():
        dup_ids = dataframes["controls_main"].loc[duplicates, "control_id"].unique()[:5]
        report.errors.append(
            ValidationIssue(
                "controls_main",
                "control_id",
                f"Duplicate control_id values: {', '.join(dup_ids)}"
            )
        )

    # Check referential integrity for child tables
    for table_name, df in dataframes.items():
        if table_name == "controls_main":
            continue

        missing_refs = set(df["control_id"].dropna()) - main_ids
        if missing_refs:
            report.errors.append(
                ValidationIssue(
                    table_name,
                    "control_id",
                    f"{len(missing_refs)} records reference unknown control_id values."
                )
            )


def validate_controls(split_dir: Path) -> ValidationResult:
    """Validate controls CSV tables.

    Validates:
    - Schema (required columns exist)
    - Dates (valid format)
    - Booleans (True/False values)
    - Referential integrity (control_ids match across tables)

    Args:
        split_dir: Directory containing split CSV files

    Returns:
        ValidationResult with success/failure and error details
    """
    logger.info("Starting validation for controls in {}", split_dir)

    report = ValidationResult(is_valid=True)

    try:
        # Load all tables
        dataframes = load_tables_from_csv(split_dir)

        # Validate each table
        for table_name, df in dataframes.items():
            validate_columns(table_name, df, report)

            # Only validate dates and bools in controls_main
            if table_name == "controls_main":
                validate_dates(table_name, df, report)
                validate_bools(table_name, df, report)

        # Validate relationships across tables
        validate_relationships(dataframes, report)

        # Set overall validity
        report.is_valid = len(report.errors) == 0

        logger.info(
            "Validation complete: is_valid={}, errors={}, warnings={}",
            report.is_valid, len(report.errors), len(report.warnings)
        )

    except Exception as e:
        logger.exception("Validation failed with exception")
        report.is_valid = False
        report.errors.append(
            ValidationIssue("SYSTEM", None, f"Validation exception: {str(e)}")
        )

    return report
