"""Core validation logic with config-driven schemas.

This module provides schema validation and table splitting for uploaded data.
Schemas are loaded from JSON config files in pipeline_config/{data_source}/schema.json.
Initial parsing is handled by initial_validation.py modules in each data source folder.
"""
import importlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
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
# Initial Validation Module Loader
# ============================================================================


def load_initial_validator(data_source: str):
    """Load the initial validator module for a data source.

    Each data source has an initial_validation.py module that handles
    CSV parsing and preprocessing before schema validation.

    Args:
        data_source: One of 'controls', 'issues', 'actions'

    Returns:
        The InitialValidator class from the module

    Raises:
        ImportError: If the module cannot be loaded
    """
    module_path = f"server.pipelines.pipeline_config.{data_source}.initial_validation"
    try:
        module = importlib.import_module(module_path)
        return module.get_validator()
    except ImportError as e:
        logger.error("Failed to load initial_validation module for {}: {}", data_source, e)
        raise ImportError(f"No initial_validation.py found for {data_source}") from e


def run_initial_validation(
    data_source: str, file_paths: List[Path]
) -> Tuple[Optional[pd.DataFrame], ValidationResult, Dict[str, Any]]:
    """Run initial validation using the data source's validator module.

    This function:
    1. Loads the appropriate initial_validation.py module
    2. Validates file requirements (count, size, extension)
    3. Parses CSV files into a DataFrame
    4. Returns the DataFrame ready for schema validation

    Args:
        data_source: One of 'controls', 'issues', 'actions'
        file_paths: List of uploaded file paths

    Returns:
        Tuple of (DataFrame or None, ValidationResult, metadata dict)
    """
    result = ValidationResult(is_valid=True)
    metadata: Dict[str, Any] = {}

    try:
        validator = load_initial_validator(data_source)
        df, metadata = validator.parse_and_convert(file_paths)

        result.row_count = len(df)
        result.column_count = len(df.columns)

        logger.info(
            "Initial validation successful for {}: {} rows, {} columns",
            data_source, result.row_count, result.column_count
        )

        return df, result, metadata

    except Exception as e:
        # Handle InitialValidationError or any other exception
        error_type = getattr(e, 'error_type', 'PARSE_ERROR')
        details = getattr(e, 'details', {})

        result.is_valid = False
        result.errors.append(
            ValidationError(
                column="FILE",
                error_type=error_type,
                message=str(e),
                file_name=details.get('file'),
            )
        )

        logger.error("Initial validation failed for {}: {}", data_source, e)
        return None, result, metadata


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


def validate_and_split(
    data_source: str, file_paths: List[Path]
) -> Tuple[ValidationResult, Optional[Dict[str, pd.DataFrame]]]:
    """Validate and split data for any data source.

    This is the unified entry point for validation that:
    1. Runs initial validation (CSV parsing via initial_validation.py)
    2. Runs schema validation (against schema.json)
    3. Splits into multiple tables (per schema.json config)

    Args:
        data_source: One of 'controls', 'issues', 'actions'
        file_paths: List of uploaded CSV file paths

    Returns:
        Tuple of (ValidationResult, dict of table DataFrames or None)
    """
    # Step 1: Initial validation - parse CSV files
    df, initial_result, metadata = run_initial_validation(data_source, file_paths)

    if not initial_result.is_valid or df is None:
        return initial_result, None

    # Step 2: Schema validation on the parsed DataFrame
    schema = SchemaLoader.get_columns_schema(data_source)
    schema_result = validate_dataframe(df, schema)

    # Preserve row/column counts from initial validation
    schema_result.row_count = initial_result.row_count
    schema_result.column_count = initial_result.column_count

    if not schema_result.is_valid:
        return schema_result, None

    # Step 3: Split into multiple tables
    tables, split_errors = split_tables_by_config(df, data_source)
    schema_result.errors.extend(split_errors)
    schema_result.is_valid = schema_result.is_valid and len(split_errors) == 0

    return schema_result, tables if schema_result.is_valid else None


def validate_and_split_controls(
    file_paths: List[Path]
) -> Tuple[ValidationResult, Optional[Dict[str, pd.DataFrame]]]:
    """Validate and split controls data.

    Args:
        file_paths: List of uploaded CSV file paths

    Returns:
        Tuple of (ValidationResult, dict of table DataFrames or None)
    """
    return validate_and_split("controls", file_paths)


def validate_and_split_issues(
    file_paths: List[Path]
) -> Tuple[ValidationResult, Optional[Dict[str, pd.DataFrame]]]:
    """Validate and split issues data from multiple files.

    Args:
        file_paths: List of uploaded CSV file paths (4 files expected)

    Returns:
        Tuple of (ValidationResult, dict of table DataFrames or None)
    """
    return validate_and_split("issues", file_paths)


def validate_and_split_actions(
    file_paths: List[Path]
) -> Tuple[ValidationResult, Optional[Dict[str, pd.DataFrame]]]:
    """Validate and split actions data.

    Args:
        file_paths: List of uploaded CSV file paths

    Returns:
        Tuple of (ValidationResult, dict of table DataFrames or None)
    """
    return validate_and_split("actions", file_paths)
