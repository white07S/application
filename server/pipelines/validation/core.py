"""Core validation logic with config-driven schemas.

This module provides schema validation and table splitting for uploaded data.
Schemas are loaded from JSON config files in pipeline_config/{data_source}/schema.json.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from itertools import zip_longest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from server.logging_config import get_logger

logger = get_logger(name=__name__)

CONFIG_DIR = Path(__file__).parent.parent / "pipeline_config"


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
# Schema Loader
# ============================================================================


class SchemaLoader:
    """Loads validation schemas from JSON config files."""

    _cache: Dict[str, Dict[str, Any]] = {}
    _common_config: Optional[Dict[str, Any]] = None

    @classmethod
    def get_common_config(cls) -> Dict[str, Any]:
        """Load common configuration (type mappings, risk themes, etc.)."""
        if cls._common_config is None:
            common_path = CONFIG_DIR / "common.json"
            if common_path.exists():
                cls._common_config = json.loads(common_path.read_text())
            else:
                cls._common_config = {}
        return cls._common_config

    @classmethod
    def get_schema(cls, data_source: str) -> Dict[str, Any]:
        """Load schema for a data source from JSON config."""
        if data_source not in cls._cache:
            schema_path = CONFIG_DIR / data_source / "schema.json"
            if not schema_path.exists():
                raise ValueError(f"Schema not found for {data_source}: {schema_path}")
            cls._cache[data_source] = json.loads(schema_path.read_text())
            logger.debug("Loaded schema for {}", data_source)
        return cls._cache[data_source]

    @classmethod
    def get_columns_schema(cls, data_source: str) -> Dict[str, Dict[str, Any]]:
        """Get column definitions for a data source."""
        schema = cls.get_schema(data_source)
        return schema.get("columns", {})

    @classmethod
    def get_table_splits(cls, data_source: str) -> Dict[str, List[str]]:
        """Get table split definitions for a data source."""
        schema = cls.get_schema(data_source)
        return schema.get("table_splits", {})

    @classmethod
    def get_multi_value_splits(cls, data_source: str) -> Dict[str, Dict[str, Any]]:
        """Get multi-value split definitions for a data source."""
        schema = cls.get_schema(data_source)
        return schema.get("multi_value_splits", {})

    @classmethod
    def get_type_mapping(cls) -> Dict[str, List[str]]:
        """Get type mapping from common config."""
        common = cls.get_common_config()
        return common.get("type_mapping", {
            "string": ["object", "string", "str"],
            "int": ["int64", "int32", "Int64", "Int32"],
            "float": ["float64", "float32", "Float64"],
            "bool": ["bool", "boolean"],
            "datetime": ["datetime64[ns]", "datetime64", "object"],
        })

    @classmethod
    def get_risk_theme_map(cls) -> Dict[str, List[str]]:
        """Get risk theme lookup from common config."""
        common = cls.get_common_config()
        return common.get("risk_theme_map", {})

    @classmethod
    def reload(cls) -> None:
        """Clear cache and reload schemas."""
        cls._cache.clear()
        cls._common_config = None


# ============================================================================
# Helpers
# ============================================================================


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
    """Look up taxonomy numbers for a risk theme."""
    if not theme:
        return None, None
    risk_map = SchemaLoader.get_risk_theme_map()
    entry = risk_map.get(theme.strip().lower())
    if not entry:
        return None, None
    return entry[0], entry[1]


def normalize_column_name(name: Any) -> str:
    """Normalize column name to lowercase with underscores."""
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return ""
    name_str = str(name).strip()
    normalized = re.sub(r'\s+', '_', name_str).lower()
    normalized = re.sub(r'_+', '_', normalized)
    return normalized


# ============================================================================
# Excel reader
# ============================================================================


def read_excel_with_enterprise_format(
    file_bytes: bytes, file_name: str, sheet_name: int | str = 0
) -> Tuple[Optional[pd.DataFrame], ValidationResult]:
    """Validate enterprise Excel format and return dataframe."""
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

    timestamp_cell = raw_df.iloc[9, 1]
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

    df_no_first_col = raw_df.iloc[:, 1:]
    raw_headers = df_no_first_col.iloc[10].tolist()
    normalized_headers = [normalize_column_name(h) for h in raw_headers]

    data_df = df_no_first_col.iloc[11:].copy()
    data_df.columns = normalized_headers
    data_df.reset_index(drop=True, inplace=True)
    data_df = data_df.loc[:, data_df.columns != '']

    result.row_count = len(data_df)
    result.column_count = len(data_df.columns)

    return data_df, result


# ============================================================================
# Column validation
# ============================================================================


def validate_column_type(series: pd.Series, expected_type: str) -> Tuple[bool, Optional[List[int]]]:
    """Validate that a column matches the expected type."""
    type_mapping = SchemaLoader.get_type_mapping()
    expected_dtypes = type_mapping.get(expected_type, [expected_type])
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
        if actual_dtype in type_mapping.get(expected_type, []):
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
    """Validate column values match a regex pattern."""
    invalid_indices = []
    regex = re.compile(pattern)
    for idx, val in series.items():
        if pd.notna(val) and not regex.match(str(val)):
            invalid_indices.append(idx)
    return len(invalid_indices) == 0, invalid_indices


def validate_allowed_values(series: pd.Series, allowed_values: List[Any]) -> Tuple[bool, List[int]]:
    """Validate column values are in allowed list."""
    invalid_mask = series.notna() & ~series.isin(allowed_values)
    invalid_indices = series[invalid_mask].index.tolist()
    return len(invalid_indices) == 0, invalid_indices


def validate_dataframe(
    df: pd.DataFrame, schema: Dict[str, Dict[str, Any]], strict_columns: bool = False
) -> ValidationResult:
    """Validate a dataframe against a schema."""
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
# Config-driven table splitting
# ============================================================================


def _split_simple_table(df: pd.DataFrame, pk_col: str, columns: List[str]) -> pd.DataFrame:
    """Split a simple table by selecting columns that exist."""
    available_cols = [c for c in columns if c in df.columns]
    return df[available_cols].copy()


def _split_multi_value(
    df: pd.DataFrame,
    pk_col: str,
    config: Dict[str, Any]
) -> Tuple[pd.DataFrame, List[ValidationError]]:
    """Split a multi-value column into separate records."""
    errors: List[ValidationError] = []
    records: List[Dict[str, Any]] = []

    # Single source column case
    if "source_column" in config:
        source_col = config["source_column"]
        value_col = config["value_column"]
        lookup_taxonomy = config.get("lookup_taxonomy", False)
        extra_cols = config.get("extra_columns", {})

        for idx, row in df.iterrows():
            for val in _split_to_list(row.get(source_col)):
                record = {pk_col: row[pk_col], value_col: val}
                if lookup_taxonomy:
                    tax_num, theme_num = _risk_theme_lookup(val)
                    record["taxonomy_number"] = tax_num
                    record["risk_theme_number"] = theme_num
                for extra_key, extra_val in extra_cols.items():
                    record[extra_key] = extra_val
                records.append(record)

        columns = [pk_col, value_col]
        if lookup_taxonomy:
            columns.extend(["taxonomy_number", "risk_theme_number"])
        columns.extend(extra_cols.keys())
        return pd.DataFrame(records, columns=columns), errors

    # Multiple source columns case (paired lists)
    if "source_columns" in config:
        source_cols = config["source_columns"]
        value_cols = config["value_columns"]
        passthrough_cols = config.get("passthrough_columns", {})  # {output_col: source_col}

        for idx, row in df.iterrows():
            lists = [_split_to_list(row.get(col)) for col in source_cols]
            max_len = max((len(lst) for lst in lists), default=0)

            # Check for length mismatch only when BOTH lists have values
            non_empty_lists = [lst for lst in lists if lst]
            if len(non_empty_lists) >= 2:
                lengths = [len(lst) for lst in non_empty_lists]
                if len(set(lengths)) > 1:
                    errors.append(
                        ValidationError(
                            column=source_cols[0],
                            error_type="RELATIONSHIP_MISMATCH",
                            message=f"{source_cols[0]} and {source_cols[1]} have different counts",
                            row_indices=[idx],
                        )
                    )

            for i in range(max_len):
                record = {pk_col: row[pk_col]}
                for j, val_col in enumerate(value_cols):
                    lst = lists[j]
                    record[val_col] = lst[i] if i < len(lst) else None
                # Add passthrough columns (same value for all records)
                for out_col, src_col in passthrough_cols.items():
                    record[out_col] = row.get(src_col)
                records.append(record)

        columns = [pk_col] + value_cols + list(passthrough_cols.keys())
        return pd.DataFrame(records, columns=columns), errors

    return pd.DataFrame(), errors


def split_tables_by_config(
    df: pd.DataFrame, data_source: str
) -> Tuple[Dict[str, pd.DataFrame], List[ValidationError]]:
    """Split a dataframe into multiple tables based on config."""
    errors: List[ValidationError] = []
    dataframes: Dict[str, pd.DataFrame] = {}

    schema = SchemaLoader.get_schema(data_source)
    pk_col = schema["primary_key"]
    table_splits = schema.get("table_splits", {})
    multi_value_splits = schema.get("multi_value_splits", {})

    if pk_col not in df.columns:
        errors.append(
            ValidationError(
                column=pk_col,
                error_type="MISSING_COLUMN",
                message=f"{pk_col} column is required to split data",
            )
        )
        return {}, errors

    # Simple table splits
    for table_name, columns in table_splits.items():
        dataframes[table_name] = _split_simple_table(df, pk_col, columns)

    # Multi-value splits
    for table_name, config in multi_value_splits.items():
        split_df, split_errors = _split_multi_value(df, pk_col, config)
        dataframes[table_name] = split_df
        errors.extend(split_errors)

    return dataframes, errors


# ============================================================================
# Public API
# ============================================================================


def validate_and_split_controls(
    file_bytes: bytes, file_name: str
) -> Tuple[ValidationResult, Optional[Dict[str, pd.DataFrame]]]:
    """Validate and split controls data."""
    df, format_result = read_excel_with_enterprise_format(file_bytes, file_name)
    if not format_result.is_valid or df is None:
        return format_result, None

    schema = SchemaLoader.get_columns_schema("controls")
    schema_result = validate_dataframe(df, schema)
    if not schema_result.is_valid:
        return schema_result, None

    tables, split_errors = split_tables_by_config(df, "controls")
    schema_result.errors.extend(split_errors)
    schema_result.is_valid = schema_result.is_valid and len(split_errors) == 0
    return schema_result, tables if schema_result.is_valid else None


def validate_and_split_issues(
    files: List[Tuple[str, bytes]]
) -> Tuple[ValidationResult, Optional[Dict[str, pd.DataFrame]]]:
    """Validate and split issues data from multiple files."""
    combined_errors: List[ValidationError] = []
    issue_dfs: Dict[str, pd.DataFrame] = {}

    schema_config = SchemaLoader.get_schema("issues")
    required_types = set(schema_config.get("required_issue_types", []))

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
    schema = SchemaLoader.get_columns_schema("issues")
    schema_result = validate_dataframe(combined_df, schema)
    if not schema_result.is_valid:
        return schema_result, None

    tables, split_errors = split_tables_by_config(combined_df, "issues")
    schema_result.errors.extend(split_errors)
    schema_result.is_valid = schema_result.is_valid and len(split_errors) == 0
    return schema_result, tables if schema_result.is_valid else None


def validate_and_split_actions(
    file_bytes: bytes, file_name: str
) -> Tuple[ValidationResult, Optional[Dict[str, pd.DataFrame]]]:
    """Validate and split actions data."""
    df, format_result = read_excel_with_enterprise_format(file_bytes, file_name)
    if not format_result.is_valid or df is None:
        return format_result, None

    schema = SchemaLoader.get_columns_schema("actions")
    schema_result = validate_dataframe(df, schema)
    if not schema_result.is_valid:
        return schema_result, None

    tables, split_errors = split_tables_by_config(df, "actions")
    schema_result.errors.extend(split_errors)
    schema_result.is_valid = schema_result.is_valid and len(split_errors) == 0
    return schema_result, tables if schema_result.is_valid else None
