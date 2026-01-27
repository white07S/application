import re
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from itertools import zip_longest
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ============================================================================
# Data classes
# ============================================================================


@dataclass
class ValidationError:
    column: str
    error_type: str
    message: str
    file_name: Optional[str] = None
    row_indices: Optional[List[int]] = None
    sample_values: Optional[List[Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column": self.column,
            "code": self.error_type,
            "message": self.message,
            "fileName": self.file_name,
            "rows": self.row_indices,
            "sampleValues": self.sample_values,
        }


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    validated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "isValid": self.is_valid,
            "errors": [err.to_dict() for err in self.errors],
            "warnings": [warn.to_dict() for warn in self.warnings],
            "rowCount": self.row_count,
            "columnCount": self.column_count,
            "validatedAt": self.validated_at.isoformat(),
        }


# ============================================================================
# Constants and helpers
# ============================================================================

TYPE_MAPPING = {
    "string": ["object", "string", "str"],
    "int": ["int64", "int32", "Int64", "Int32"],
    "float": ["float64", "float32", "Float64"],
    "bool": ["bool", "boolean"],
    "datetime": ["datetime64[ns]", "datetime64", "object"],
}

# Risk theme lookup (theme -> taxonomy numbers)
RISK_THEME_MAP: Dict[str, Tuple[str, str]] = {
    "technology production stability": ("1", "1.1"),
    "cyber and information security": ("1", "1.2"),
    "data management": ("1", "1.3"),
    "technology change management": ("1", "1.4"),
    "third party management": ("2", "2.1"),
    "outsourcing risk": ("2", "2.2"),
    "intragroup dependencies": ("2", "2.3"),
    "financial crime prevention": ("3", "3.1"),
    "anti-money laundering": ("3", "3.2"),
    "sanctions compliance": ("3", "3.3"),
    "conduct risk": ("4", "4.1"),
    "market conduct": ("4", "4.2"),
    "client suitability": ("4", "4.3"),
    "regulatory compliance": ("5", "5.1"),
    "legal risk": ("5", "5.2"),
    "regulatory change": ("5", "5.3"),
    "business continuity": ("6", "6.1"),
    "physical security": ("6", "6.2"),
    "operational resilience": ("6", "6.3"),
    "talent and resource management": ("7", "7.1"),
    "organizational culture": ("7", "7.2"),
    "process execution": ("8", "8.1"),
    "transaction processing": ("8", "8.2"),
}

FUNCTION_COLUMNS = [
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

LOCATION_COLUMNS = [
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


def _split_to_list(value: Any) -> List[str]:
    """Split comma-separated strings into a clean list."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, (int, float)):
        return [str(value)]
    if not isinstance(value, str):
        return []
    return [item.strip() for item in value.split(",") if item and item.strip()]


def _risk_theme_lookup(theme: str) -> Tuple[Optional[str], Optional[str]]:
    if not theme:
        return None, None
    entry = RISK_THEME_MAP.get(theme.strip().lower())
    if not entry:
        return None, None
    return entry


# ============================================================================
# Enterprise Excel reader
# ============================================================================


def read_excel_with_enterprise_format(
    file_bytes: bytes, file_name: str, sheet_name: int | str = 0
) -> Tuple[Optional[pd.DataFrame], ValidationResult]:
    """
    Validate enterprise Excel format and return dataframe without padding.
    """
    result = ValidationResult(is_valid=True)

    try:
        raw_df = pd.read_excel(
            BytesIO(file_bytes),
            sheet_name=sheet_name,
            header=None,
            engine="openpyxl",
        )
    except Exception as exc:
        result.is_valid = False
        result.errors.append(
            ValidationError(
                column="FILE",
                error_type="READ_ERROR",
                message=f"Failed to read Excel file: {exc}",
                file_name=file_name,
            )
        )
        return None, result

    # Expect at least 11 rows and 2 columns
    if raw_df.shape[0] < 11 or raw_df.shape[1] < 2:
        result.is_valid = False
        result.errors.append(
            ValidationError(
                column="FILE",
                error_type="FORMAT_ERROR",
                message=f"File too small for enterprise format (rows: {raw_df.shape[0]}, cols: {raw_df.shape[1]}).",
                file_name=file_name,
            )
        )
        return None, result

    timestamp_cell = raw_df.iloc[9, 1]  # Row 10, Column B (0-indexed)
    if not isinstance(timestamp_cell, str) or "timestamp" not in timestamp_cell.lower():
        result.is_valid = False
        result.errors.append(
            ValidationError(
                column="FILE",
                error_type="FORMAT_ERROR",
                message=f"Row 10 Column B should contain 'Timestamp:'; found: {timestamp_cell}",
                file_name=file_name,
            )
        )
        return None, result

    # Drop first column, first 10 rows; row 11 becomes header
    df_no_first_col = raw_df.iloc[:, 1:]
    headers = df_no_first_col.iloc[10].tolist()
    data_df = df_no_first_col.iloc[11:].copy()
    data_df.columns = headers
    data_df.reset_index(drop=True, inplace=True)

    result.row_count = len(data_df)
    result.column_count = len(data_df.columns)

    return data_df, result


# ============================================================================
# Schema definitions (aligned with reference validation)
# ============================================================================


def get_controls_schema() -> Dict[str, Dict[str, Any]]:
    return {
        "control_id": {"type": "string", "required": True, "nullable": False, "pattern": r"^CTRL-\d{10}$"},
        "control_title": {"type": "string", "required": True, "nullable": False},
        "control_description": {"type": "string", "required": True, "nullable": True},
        "key_control": {"type": "bool", "required": False, "nullable": True},
        "hierarchy_level": {"type": "string", "required": True, "nullable": False, "allowed_values": ["Level 1", "Level 2"]},
        "parent_control_id": {"type": "string", "required": False, "nullable": True, "pattern": r"^CTRL-\d{10}$"},
        "preventative_detective": {"type": "string", "required": True, "nullable": False,
                                   "allowed_values": ["Preventative", "Detective", "1st Line Detective", "2nd Line Detective"]},
        "manual_automated": {"type": "string", "required": True, "nullable": False,
                             "allowed_values": ["Manual", "Automated", "IT Dependent Manual"]},
        "execution_frequency": {"type": "string", "required": True, "nullable": False,
                                "allowed_values": ["Daily", "Weekly", "Monthly", "Quarterly", "Semi-Annually",
                                                   "Annually", "Event Triggered", "Intraday", "Others"]},
        "four_eyes_check": {"type": "bool", "required": False, "nullable": True},
        "evidence_description": {"type": "string", "required": False, "nullable": True},
        "evidence_available_from": {"type": "datetime", "required": False, "nullable": True},
        "performance_measures_required": {"type": "bool", "required": False, "nullable": True},
        "performance_measures_available_from": {"type": "datetime", "required": False, "nullable": True},
        "control_status": {"type": "string", "required": True, "nullable": False,
                           "allowed_values": ["Active", "Inactive"]},
        "valid_from": {"type": "datetime", "required": True, "nullable": False},
        "valid_until": {"type": "datetime", "required": False, "nullable": True},
        "reason_for_deactivation": {"type": "string", "required": False, "nullable": True},
        "status_updates": {"type": "string", "required": False, "nullable": True},
        "last_modified_on": {"type": "datetime", "required": True, "nullable": False},
        "group_id": {"type": "string", "required": True, "nullable": False},
        "group_name": {"type": "string", "required": True, "nullable": False},
        "division_id": {"type": "string", "required": True, "nullable": False},
        "division_name": {"type": "string", "required": True, "nullable": False},
        "unit_id": {"type": "string", "required": True, "nullable": False},
        "unit_name": {"type": "string", "required": True, "nullable": False},
        "area_id": {"type": "string", "required": True, "nullable": False},
        "area_name": {"type": "string", "required": True, "nullable": False},
        "sector_id": {"type": "string", "required": True, "nullable": False},
        "sector_name": {"type": "string", "required": True, "nullable": False},
        "segment_id": {"type": "string", "required": True, "nullable": False},
        "segment_name": {"type": "string", "required": True, "nullable": False},
        "function_id": {"type": "string", "required": True, "nullable": False},
        "function_name": {"type": "string", "required": True, "nullable": False},
        "l0_location_id": {"type": "string", "required": True, "nullable": False},
        "l0_location_name": {"type": "string", "required": True, "nullable": False},
        "region_id": {"type": "string", "required": True, "nullable": False},
        "region_name": {"type": "string", "required": True, "nullable": False},
        "sub_region_id": {"type": "string", "required": True, "nullable": False},
        "sub_region_name": {"type": "string", "required": True, "nullable": False},
        "country_id": {"type": "string", "required": True, "nullable": False},
        "country_name": {"type": "string", "required": True, "nullable": False},
        "company_id": {"type": "string", "required": True, "nullable": False},
        "company_short_name": {"type": "string", "required": True, "nullable": False},
        "control_owner": {"type": "string", "required": True, "nullable": False},
        "control_owner_gpn": {"type": "string", "required": True, "nullable": False, "pattern": r"^\d{8}$"},
        "sox_relevant": {"type": "bool", "required": False, "nullable": True},
        "ccar_relevant": {"type": "bool", "required": False, "nullable": True},
        "bcbs239_relevant": {"type": "bool", "required": False, "nullable": True},
    }


def get_issues_schema() -> Dict[str, Dict[str, Any]]:
    return {
        "issue_id": {"type": "string", "required": True, "nullable": False, "pattern": r"^ISSUE-\d{10}$"},
        "issue_title": {"type": "string", "required": True, "nullable": False},
        "issue_type": {"type": "string", "required": True, "nullable": False,
                       "allowed_values": ["Audit", "Self-Identified", "Regulatory", "Restricted Regulatory"]},
        "control_deficiency": {"type": "string", "required": True, "nullable": False},
        "root_cause": {"type": "string", "required": True, "nullable": False},
        "symptoms": {"type": "string", "required": True, "nullable": True},
        "risk_description": {"type": "string", "required": True, "nullable": False},
        "success_criteria": {"type": "string", "required": True, "nullable": False},
        "issue_status": {"type": "string", "required": True, "nullable": False,
                         "allowed_values": ["Draft", "Open-Grace Period", "Open", "Completed", "Closed"]},
        "issue_rag_status": {"type": "string", "required": True, "nullable": False,
                             "allowed_values": ["Red", "Amber", "Green"]},
        "issue_rag_justification": {"type": "string", "required": True, "nullable": True},
        "original_mitigation_date": {"type": "datetime", "required": True, "nullable": False},
        "current_mitigation_date": {"type": "datetime", "required": True, "nullable": False},
        "mitigation_date_change_count": {"type": "int", "required": False, "nullable": True},
        "open_action_plans": {"type": "int", "required": True, "nullable": False},
        "total_action_plans": {"type": "int", "required": True, "nullable": False},
        "severity_rating": {"type": "int", "required": True, "nullable": False, "allowed_values": [3, 4, 5]},
        "created_on": {"type": "datetime", "required": True, "nullable": False},
        "last_modified_on": {"type": "datetime", "required": True, "nullable": False},
        "group_id": {"type": "string", "required": True, "nullable": False},
        "division_name": {"type": "string", "required": True, "nullable": False},
        "function_name": {"type": "string", "required": True, "nullable": False},
        "country_name": {"type": "string", "required": True, "nullable": False},
        "issue_owner": {"type": "string", "required": True, "nullable": False},
        "issue_owner_gpn": {"type": "string", "required": True, "nullable": False, "pattern": r"^\d{8}$"},
    }


def get_actions_schema() -> Dict[str, Dict[str, Any]]:
    return {
        "issue_id": {"type": "string", "required": True, "nullable": False, "pattern": r"^ISSUE-\d{10}$"},
        "action_id": {"type": "string", "required": True, "nullable": False, "pattern": r"^ACTION-\d{10}$"},
        "composite_key": {"type": "string", "required": True, "nullable": False},
        "action_title": {"type": "string", "required": True, "nullable": False},
        "action_description": {"type": "string", "required": True, "nullable": True},
        "issue_type": {"type": "string", "required": True, "nullable": False,
                       "allowed_values": ["Audit", "Self-Identified", "Regulatory", "Restricted Regulatory"]},
        "action_status": {"type": "string", "required": True, "nullable": False,
                          "allowed_values": ["Open", "In Progress", "Completed", "Closed", "Cancelled", "On Hold"]},
        "action_rag_status": {"type": "string", "required": True, "nullable": False,
                              "allowed_values": ["Red", "Amber", "Green"]},
        "action_rag_justification": {"type": "string", "required": True, "nullable": True},
        "current_due_date": {"type": "datetime", "required": True, "nullable": False},
        "original_due_date": {"type": "datetime", "required": True, "nullable": False},
        "extension_date": {"type": "datetime", "required": False, "nullable": True},
        "extension_count": {"type": "int", "required": False, "nullable": True},
        "closed_date": {"type": "datetime", "required": False, "nullable": True},
        "reopening_date": {"type": "datetime", "required": False, "nullable": True},
        "action_owner": {"type": "string", "required": True, "nullable": False},
        "action_owner_gpn": {"type": "string", "required": True, "nullable": False, "pattern": r"^\d{8}$"},
        "action_administrator": {"type": "string", "required": True, "nullable": False},
        "action_administrator_gpn": {"type": "string", "required": True, "nullable": False, "pattern": r"^\d{8}$"},
        "minimum_standards_for_closure_met": {"type": "bool", "required": False, "nullable": True},
        "reopen_flag": {"type": "bool", "required": False, "nullable": True},
        "program_id": {"type": "string", "required": False, "nullable": True},
        "ubs_change_program": {"type": "bool", "required": False, "nullable": True},
        "created_on": {"type": "datetime", "required": True, "nullable": False},
        "last_modified_on": {"type": "datetime", "required": True, "nullable": False},
    }


# ============================================================================
# Column validation helpers
# ============================================================================


def validate_column_type(series: pd.Series, expected_type: str) -> Tuple[bool, Optional[List[int]]]:
    expected_dtypes = TYPE_MAPPING.get(expected_type, [expected_type])
    actual_dtype = str(series.dtype)

    if expected_type == "string":
        if actual_dtype in ["object", "string", "str"]:
            return True, None

    if expected_type == "datetime":
        if actual_dtype in ["datetime64[ns]", "datetime64"]:
            return True, None
        invalid_indices = []
        for idx, val in series.items():
            if pd.notna(val):
                try:
                    pd.to_datetime(val)
                except (ValueError, TypeError):
                    invalid_indices.append(idx)
        return len(invalid_indices) == 0, invalid_indices if invalid_indices else None

    if expected_type in ["int", "float"]:
        if actual_dtype in TYPE_MAPPING.get(expected_type, []):
            return True, None
        if expected_type == "int":
            try:
                numeric_series = pd.to_numeric(series, errors="coerce")
                invalid = series.notna() & numeric_series.isna()
                invalid_indices = series[invalid].index.tolist()
                return len(invalid_indices) == 0, invalid_indices if invalid_indices else None
            except Exception:
                return False, None

    if expected_type == "bool":
        if actual_dtype in ["bool", "boolean"]:
            return True, None
        valid_bool_values = {True, False, 1, 0, "True", "False", "true", "false", "1", "0", None}
        invalid_indices = []
        for idx, val in series.items():
            if pd.notna(val) and val not in valid_bool_values:
                invalid_indices.append(idx)
        return len(invalid_indices) == 0, invalid_indices if invalid_indices else None

    return actual_dtype in expected_dtypes, None


def validate_pattern(series: pd.Series, pattern: str) -> Tuple[bool, List[int]]:
    invalid_indices = []
    regex = re.compile(pattern)
    for idx, val in series.items():
        if pd.notna(val) and not regex.match(str(val)):
            invalid_indices.append(idx)
    return len(invalid_indices) == 0, invalid_indices


def validate_allowed_values(series: pd.Series, allowed_values: List[Any]) -> Tuple[bool, List[int]]:
    invalid_mask = series.notna() & ~series.isin(allowed_values)
    invalid_indices = series[invalid_mask].index.tolist()
    return len(invalid_indices) == 0, invalid_indices


def validate_dataframe(
    df: pd.DataFrame, schema: Dict[str, Dict[str, Any]], strict_columns: bool = False
) -> ValidationResult:
    errors: List[ValidationError] = []
    warnings: List[ValidationError] = []

    required_columns = [col for col, spec in schema.items() if spec.get("required", False)]
    missing_columns = set(required_columns) - set(df.columns)
    for col in missing_columns:
        errors.append(
            ValidationError(
                column=col,
                error_type="MISSING_COLUMN",
                message=f"Required column '{col}' is missing",
            )
        )

    schema_columns = set(schema.keys())
    extra_columns = set(df.columns) - schema_columns
    for col in extra_columns:
        container = errors if strict_columns else warnings
        container.append(
            ValidationError(
                column=col,
                error_type="EXTRA_COLUMN",
                message=f"Column '{col}' not in schema",
            )
        )

    for col, spec in schema.items():
        if col not in df.columns:
            continue
        series = df[col]
        if not spec.get("nullable", True):
            null_count = series.isna().sum()
            if null_count > 0:
                null_indices = series[series.isna()].index.tolist()
                errors.append(
                    ValidationError(
                        column=col,
                        error_type="NULL_VALUES",
                        message=f"Found {null_count} null values in non-nullable column",
                        row_indices=null_indices,
                    )
                )

        expected_type = spec.get("type")
        if expected_type:
            type_valid, invalid_indices = validate_column_type(series, expected_type)
            if not type_valid:
                sample_values = None
                if invalid_indices:
                    sample_values = series.iloc[invalid_indices[:5]].tolist()
                errors.append(
                    ValidationError(
                        column=col,
                        error_type="TYPE_MISMATCH",
                        message=f"Expected type '{expected_type}', got '{series.dtype}'",
                        row_indices=invalid_indices,
                        sample_values=sample_values,
                    )
                )

        pattern = spec.get("pattern")
        if pattern:
            pattern_valid, invalid_indices = validate_pattern(series, pattern)
            if not pattern_valid:
                sample_values = series.iloc[invalid_indices[:5]].tolist()
                errors.append(
                    ValidationError(
                        column=col,
                        error_type="PATTERN_MISMATCH",
                        message=f"Values don't match pattern '{pattern}'",
                        row_indices=invalid_indices,
                        sample_values=sample_values,
                    )
                )

        allowed_values = spec.get("allowed_values")
        if allowed_values:
            values_valid, invalid_indices = validate_allowed_values(series, allowed_values)
            if not values_valid:
                invalid_values = series.iloc[invalid_indices[:5]].unique().tolist()
                errors.append(
                    ValidationError(
                        column=col,
                        error_type="INVALID_VALUE",
                        message=f"Invalid values found. Allowed: {allowed_values}",
                        row_indices=invalid_indices,
                        sample_values=invalid_values,
                    )
                )

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        row_count=len(df),
        column_count=len(df.columns),
    )


# ============================================================================
# Table splitting helpers
# ============================================================================


def _split_controls_tables(df: pd.DataFrame) -> Tuple[Dict[str, pd.DataFrame], List[ValidationError]]:
    errors: List[ValidationError] = []

    if "control_id" not in df.columns:
        errors.append(
            ValidationError(
                column="control_id",
                error_type="MISSING_COLUMN",
                message="control_id column is required to split controls data",
            )
        )
        return {}, errors

    controls_main_cols = [
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
    controls_metadata_cols = [
        "control_id",
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

    hierarchy_cols = ["control_id"] + FUNCTION_COLUMNS + LOCATION_COLUMNS

    dataframes: Dict[str, pd.DataFrame] = {
        "controls_main": df[[c for c in controls_main_cols if c in df.columns]].copy(),
        "controls_hierarchy": df[[c for c in hierarchy_cols if c in df.columns]].copy(),
        "controls_metadata": df[[c for c in controls_metadata_cols if c in df.columns]].copy(),
    }

    # Category flags
    cat_records: List[Dict[str, Any]] = []
    if "category_flags" in df.columns:
        for idx, row in df.iterrows():
            for flag in _split_to_list(row.get("category_flags")):
                cat_records.append({"control_id": row["control_id"], "category_flag": flag})
    dataframes["controls_category_flags"] = pd.DataFrame(cat_records, columns=["control_id", "category_flag"])

    # SOX assertions
    sox_records: List[Dict[str, Any]] = []
    if "sox_assertions" in df.columns:
        for idx, row in df.iterrows():
            for assertion in _split_to_list(row.get("sox_assertions")):
                sox_records.append({"control_id": row["control_id"], "sox_assertion": assertion})
    dataframes["controls_sox_assertions"] = pd.DataFrame(sox_records, columns=["control_id", "sox_assertion"])

    # Risk themes
    risk_records: List[Dict[str, Any]] = []
    if "risk_themes" in df.columns:
        for idx, row in df.iterrows():
            for theme in _split_to_list(row.get("risk_themes")):
                taxonomy_number, risk_theme_number = _risk_theme_lookup(theme)
                risk_records.append(
                    {
                        "control_id": row["control_id"],
                        "risk_theme": theme,
                        "taxonomy_number": taxonomy_number,
                        "risk_theme_number": risk_theme_number,
                    }
                )
    dataframes["controls_risk_theme"] = pd.DataFrame(
        risk_records, columns=["control_id", "risk_theme", "taxonomy_number", "risk_theme_number"]
    )

    # Related functions
    func_records: List[Dict[str, Any]] = []
    id_col = df.get("related_function_ids")
    name_col = df.get("related_function_names")
    comment_col = df.get("related_functions_comments")
    for idx, row in df.iterrows():
        ids = _split_to_list(row.get("related_function_ids"))
        names = _split_to_list(row.get("related_function_names"))
        comments = row.get("related_functions_comments")
        if ids and names and len(ids) != len(names):
            errors.append(
                ValidationError(
                    column="related_function_ids",
                    error_type="RELATIONSHIP_MISMATCH",
                    message="related_function_ids and related_function_names counts differ",
                    row_indices=[idx],
                    file_name=None,
                )
            )
        for fid, fname in zip_longest(ids, names, fillvalue=None):
            func_records.append(
                {
                    "control_id": row["control_id"],
                    "related_functions_locations_comments": comments,
                    "related_function_id": fid,
                    "related_function_name": fname,
                }
            )
    dataframes["controls_related_functions"] = pd.DataFrame(
        func_records,
        columns=[
            "control_id",
            "related_functions_locations_comments",
            "related_function_id",
            "related_function_name",
        ],
    )

    # Related locations
    loc_records: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        ids = _split_to_list(row.get("related_location_ids"))
        names = _split_to_list(row.get("related_location_names"))
        if ids and names and len(ids) != len(names):
            errors.append(
                ValidationError(
                    column="related_location_ids",
                    error_type="RELATIONSHIP_MISMATCH",
                    message="related_location_ids and related_location_names counts differ",
                    row_indices=[idx],
                )
            )
        for rid, rname in zip_longest(ids, names, fillvalue=None):
            loc_records.append(
                {
                    "control_id": row["control_id"],
                    "related_location_id": rid,
                    "related_location_name": rname,
                }
            )
    dataframes["controls_related_locations"] = pd.DataFrame(
        loc_records,
        columns=["control_id", "related_location_id", "related_location_name"],
    )

    return dataframes, errors


def _split_issues_tables(df: pd.DataFrame) -> Tuple[Dict[str, pd.DataFrame], List[ValidationError]]:
    errors: List[ValidationError] = []
    if "issue_id" not in df.columns:
        errors.append(
            ValidationError(
                column="issue_id",
                error_type="MISSING_COLUMN",
                message="issue_id column is required to split issues data",
            )
        )
        return {}, errors

    issues_main_cols = [
        "issue_id",
        "issue_title",
        "issue_type",
        "control_deficiency",
        "root_cause",
        "symptoms",
        "risk_description",
        "success_criteria",
        "issue_status",
        "issue_rag_status",
        "issue_rag_justification",
        "original_mitigation_date",
        "current_mitigation_date",
        "mitigation_date_change_count",
        "open_action_plans",
        "total_action_plans",
        "severity_rating",
        "created_on",
        "last_modified_on",
    ]
    issues_audit_cols = [
        "issue_id",
        "issue_owner",
        "issue_owner_gpn",
        "issue_administrator",
        "issue_administrator_gpn",
        "issue_delegate",
        "issue_delegate_gpn",
        "first_level_reviewer",
        "first_level_reviewer_gpn",
        "orc_reviewer",
        "orc_reviewer_gpn",
        "orc_articulation_check",
        "orc_rating_check",
        "orc_mitigation_date_check",
        "orc_action_plan_check",
        "orc_mapping_check",
        "regulatory_manager",
        "regulatory_manager_gpn",
        "regulator_country",
        "regulator_type",
        "audit_rating",
        "audit_report_id",
        "finding_id",
        "mra_mria",
        "dsori_program",
        "gsori_program",
        "eandy_relevant",
        "operating_committee",
        "reprioritization_risk_acceptance_justification",
        "risk_acceptance_approval_date",
        "category_flags",
        "draft_date",
        "open_grace_period_date",
        "open_date",
        "completed_date",
        "closed_date",
        "last_comment",
        "last_comment_date",
        "last_commenter",
        "last_commenter_gpn",
    ]
    hierarchy_cols = ["issue_id"] + FUNCTION_COLUMNS + LOCATION_COLUMNS

    dataframes: Dict[str, pd.DataFrame] = {
        "issues_main": df[[c for c in issues_main_cols if c in df.columns]].copy(),
        "issues_hierarchy": df[[c for c in hierarchy_cols if c in df.columns]].copy(),
        "issues_audit": df[[c for c in issues_audit_cols if c in df.columns]].copy(),
    }

    # Related functions
    func_records: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        ids = _split_to_list(row.get("related_function_ids"))
        names = _split_to_list(row.get("related_function_names"))
        if ids and names and len(ids) != len(names):
            errors.append(
                ValidationError(
                    column="related_function_ids",
                    error_type="RELATIONSHIP_MISMATCH",
                    message="related_function_ids and related_function_names counts differ",
                    row_indices=[idx],
                )
            )
        for fid, fname in zip_longest(ids, names, fillvalue=None):
            func_records.append(
                {
                    "issue_id": row["issue_id"],
                    "related_function_id": fid,
                    "related_function_name": fname,
                }
            )
    dataframes["issues_related_functions"] = pd.DataFrame(
        func_records, columns=["issue_id", "related_function_id", "related_function_name"]
    )

    # Related locations
    loc_records: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        ids = _split_to_list(row.get("related_location_ids"))
        names = _split_to_list(row.get("related_location_names"))
        if ids and names and len(ids) != len(names):
            errors.append(
                ValidationError(
                    column="related_location_ids",
                    error_type="RELATIONSHIP_MISMATCH",
                    message="related_location_ids and related_location_names counts differ",
                    row_indices=[idx],
                )
            )
        for rid, rname in zip_longest(ids, names, fillvalue=None):
            loc_records.append(
                {
                    "issue_id": row["issue_id"],
                    "related_location_id": rid,
                    "related_location_name": rname,
                }
            )
    dataframes["issues_related_locations"] = pd.DataFrame(
        loc_records, columns=["issue_id", "related_location_id", "related_location_name"]
    )

    # Linked controls
    control_records: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        for cid in _split_to_list(row.get("linked_control_ids")):
            control_records.append({"issue_id": row["issue_id"], "control_id": cid})
    dataframes["issues_controls"] = pd.DataFrame(control_records, columns=["issue_id", "control_id"])

    # Related issues
    related_issue_records: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        for rid in _split_to_list(row.get("related_issue_ids")):
            related_issue_records.append({"issue_id": row["issue_id"], "related_issue_id": rid, "relationship_type": None})
    dataframes["issues_related_issues"] = pd.DataFrame(
        related_issue_records, columns=["issue_id", "related_issue_id", "relationship_type"]
    )

    # Risk themes
    risk_records: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        for theme in _split_to_list(row.get("risk_themes")):
            taxonomy_number, risk_theme_number = _risk_theme_lookup(theme)
            risk_records.append(
                {
                    "issue_id": row["issue_id"],
                    "risk_theme": theme,
                    "taxonomy_number": taxonomy_number,
                    "risk_theme_number": risk_theme_number,
                }
            )
    dataframes["issues_risk_theme"] = pd.DataFrame(
        risk_records, columns=["issue_id", "risk_theme", "taxonomy_number", "risk_theme_number"]
    )

    return dataframes, errors


def _split_actions_tables(df: pd.DataFrame) -> Tuple[Dict[str, pd.DataFrame], List[ValidationError]]:
    errors: List[ValidationError] = []
    if "composite_key" not in df.columns or "issue_id" not in df.columns or "action_id" not in df.columns:
        errors.append(
            ValidationError(
                column="composite_key",
                error_type="MISSING_COLUMN",
                message="issue_id, action_id and composite_key are required to split actions data",
            )
        )
        return {}, errors

    action_cols = [
        "issue_id",
        "action_id",
        "composite_key",
        "action_title",
        "action_description",
        "issue_type",
        "action_status",
        "action_rag_status",
        "action_rag_justification",
        "current_due_date",
        "original_due_date",
        "extension_date",
        "extension_count",
        "closed_date",
        "reopening_date",
        "action_owner",
        "action_owner_gpn",
        "action_administrator",
        "action_administrator_gpn",
        "minimum_standards_for_closure_met",
        "reopen_action",
        "reopen_flag",
        "program_id",
        "ubs_change_program",
        "created_by",
        "created_by_gpn",
        "originator",
        "originator_gpn",
        "created_on",
        "last_modified_on",
    ]

    hierarchy_cols = ["issue_id", "action_id", "composite_key"] + FUNCTION_COLUMNS + LOCATION_COLUMNS

    dataframes: Dict[str, pd.DataFrame] = {
        "issues_actions": df[[c for c in action_cols if c in df.columns]].copy(),
    }

    hierarchy_df = df[[c for c in hierarchy_cols if c in df.columns]].copy()
    if not hierarchy_df.empty:
        dataframes["issues_actions_hierarchy"] = hierarchy_df
    else:
        dataframes["issues_actions_hierarchy"] = pd.DataFrame(columns=hierarchy_cols)

    return dataframes, errors


# ============================================================================
# Public conversion helpers
# ============================================================================


def validate_and_split_controls(file_bytes: bytes, file_name: str) -> Tuple[ValidationResult, Optional[Dict[str, pd.DataFrame]]]:
    df, format_result = read_excel_with_enterprise_format(file_bytes, file_name)
    if not format_result.is_valid or df is None:
        return format_result, None

    schema_result = validate_dataframe(df, get_controls_schema())
    if not schema_result.is_valid:
        return schema_result, None

    tables, split_errors = _split_controls_tables(df)
    schema_result.errors.extend(split_errors)
    schema_result.is_valid = schema_result.is_valid and len(split_errors) == 0
    return schema_result, tables if schema_result.is_valid else None


def validate_and_split_issues(files: List[Tuple[str, bytes]]) -> Tuple[ValidationResult, Optional[Dict[str, pd.DataFrame]]]:
    combined_errors: List[ValidationError] = []
    issue_dfs: Dict[str, pd.DataFrame] = {}
    required_types = {"Audit", "Self-Identified", "Regulatory", "Restricted Regulatory"}

    for file_name, content in files:
        df, fmt_result = read_excel_with_enterprise_format(content, file_name)
        if not fmt_result.is_valid or df is None:
            combined_errors.extend(fmt_result.errors)
            continue

        issue_types = [val for val in df.get("issue_type", pd.Series()).dropna().unique()]
        if len(issue_types) != 1:
            combined_errors.append(
                ValidationError(
                    column="issue_type",
                    error_type="INVALID_VALUE",
                    message=f"Expected exactly one issue_type per file, found: {issue_types or ['<missing>']}",
                    file_name=file_name,
                )
            )
            continue
        issue_type_value = issue_types[0]
        if issue_type_value not in required_types:
            combined_errors.append(
                ValidationError(
                    column="issue_type",
                    error_type="INVALID_VALUE",
                    message=f"Unexpected issue_type '{issue_type_value}' in file {file_name}",
                    file_name=file_name,
                )
            )
            continue
        if issue_type_value in issue_dfs:
            combined_errors.append(
                ValidationError(
                    column="issue_type",
                    error_type="DUPLICATE_TYPE",
                    message=f"Duplicate file for issue_type '{issue_type_value}'",
                    file_name=file_name,
                )
            )
            continue
        issue_dfs[issue_type_value] = df

    missing_types = required_types - set(issue_dfs.keys())
    for missing in sorted(missing_types):
        combined_errors.append(
            ValidationError(
                column="issue_type",
                error_type="MISSING_FILE",
                message=f"Missing file for issue_type '{missing}'",
            )
        )

    if combined_errors:
        return ValidationResult(is_valid=False, errors=combined_errors), None

    combined_df = pd.concat(issue_dfs.values(), ignore_index=True)
    schema_result = validate_dataframe(combined_df, get_issues_schema())
    if not schema_result.is_valid:
        return schema_result, None

    tables, split_errors = _split_issues_tables(combined_df)
    schema_result.errors.extend(split_errors)
    schema_result.is_valid = schema_result.is_valid and len(split_errors) == 0
    return schema_result, tables if schema_result.is_valid else None


def validate_and_split_actions(file_bytes: bytes, file_name: str) -> Tuple[ValidationResult, Optional[Dict[str, pd.DataFrame]]]:
    df, format_result = read_excel_with_enterprise_format(file_bytes, file_name)
    if not format_result.is_valid or df is None:
        return format_result, None

    schema_result = validate_dataframe(df, get_actions_schema())
    if not schema_result.is_valid:
        return schema_result, None

    tables, split_errors = _split_actions_tables(df)
    schema_result.errors.extend(split_errors)
    schema_result.is_valid = schema_result.is_valid and len(split_errors) == 0
    return schema_result, tables if schema_result.is_valid else None
