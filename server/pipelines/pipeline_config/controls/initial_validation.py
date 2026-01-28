"""Initial validation and parsing for Controls data.

This module handles file validation, CSV parsing, and parquet conversion
for Controls data. It replaces the JSON-based validation.json configuration.
"""
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import re

import numpy as np
import pandas as pd

from server.logging_config import get_logger

logger = get_logger(name=__name__)

# Path to schema file for type conversion
SCHEMA_PATH = Path(__file__).parent / "schema.json"


def convert_to_bool(value: Any) -> Optional[bool]:
    """Convert various boolean representations to Python bool."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        val_lower = value.strip().lower()
        if val_lower in ('true', 'yes', 'y', '1'):
            return True
        if val_lower in ('false', 'no', 'n', '0', ''):
            return False
    return None


def convert_to_datetime(value: Any) -> Optional[pd.Timestamp]:
    """Convert various datetime representations to pandas Timestamp."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if pd.isna(value):
        return None
    try:
        return pd.to_datetime(value)
    except (ValueError, TypeError):
        return None


def convert_to_int(value: Any) -> Optional[int]:
    """Convert various numeric representations to int."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if pd.isna(value):
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


class InitialValidationError(Exception):
    """Error during initial validation/parsing."""

    def __init__(self, message: str, error_type: str = "PARSE_ERROR", details: Optional[Dict] = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


def normalize_column_name(name: Any) -> str:
    """Normalize column name to lowercase with underscores."""
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return ""
    name_str = str(name).strip()
    normalized = re.sub(r'\s+', '_', name_str).lower()
    normalized = re.sub(r'_+', '_', normalized)
    return normalized


class InitialValidator:
    """Handles file validation, parsing, and parquet conversion for Controls.

    This class defines:
    - Expected file count and patterns
    - Minimum file size requirements
    - Allowed file extensions
    - How to parse CSV files and convert to normalized DataFrames
    """

    # File requirements
    expected_file_count: int = 1
    expected_file_patterns: List[str] = ["controls*.csv", "*.csv"]
    min_file_size_kb: int = 5
    allowed_extensions: List[str] = [".csv"]

    # Cache for schema
    _schema_cache: Optional[Dict[str, Any]] = None

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """Load and cache the schema for type conversion."""
        if cls._schema_cache is None:
            if SCHEMA_PATH.exists():
                cls._schema_cache = json.loads(SCHEMA_PATH.read_text())
            else:
                cls._schema_cache = {}
        return cls._schema_cache

    def convert_column_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert column types based on schema definitions.

        Converts string representations to proper Python types:
        - bool: "True"/"False", "Yes"/"No", "1"/"0" -> bool
        - int: numeric strings -> int
        - datetime: date strings -> pandas Timestamp

        Args:
            df: DataFrame with string columns from CSV

        Returns:
            DataFrame with converted column types
        """
        schema = self.get_schema()
        columns_spec = schema.get("columns", {})

        for col_name, col_spec in columns_spec.items():
            if col_name not in df.columns:
                continue

            col_type = col_spec.get("type")

            if col_type == "bool":
                df[col_name] = df[col_name].apply(convert_to_bool)
                logger.debug("Converted column '{}' to bool", col_name)

            elif col_type == "int":
                df[col_name] = df[col_name].apply(convert_to_int)
                # Use nullable integer type
                df[col_name] = df[col_name].astype("Int64")
                logger.debug("Converted column '{}' to int", col_name)

            elif col_type == "datetime":
                df[col_name] = df[col_name].apply(convert_to_datetime)
                logger.debug("Converted column '{}' to datetime", col_name)

        return df

    def validate_file_requirements(self, file_paths: List[Path]) -> None:
        """Validate that files meet basic requirements.

        Args:
            file_paths: List of uploaded file paths

        Raises:
            InitialValidationError: If requirements not met
        """
        # Check file count
        if len(file_paths) != self.expected_file_count:
            raise InitialValidationError(
                f"Expected {self.expected_file_count} file(s) for controls, got {len(file_paths)}",
                error_type="FILE_COUNT_MISMATCH",
                details={"expected": self.expected_file_count, "received": len(file_paths)}
            )

        # Check each file
        for file_path in file_paths:
            # Check extension
            if file_path.suffix.lower() not in self.allowed_extensions:
                raise InitialValidationError(
                    f"File '{file_path.name}' has invalid extension. Allowed: {self.allowed_extensions}",
                    error_type="INVALID_EXTENSION",
                    details={"file": file_path.name, "extension": file_path.suffix}
                )

            # Check file size
            size_kb = file_path.stat().st_size / 1024
            if size_kb < self.min_file_size_kb:
                raise InitialValidationError(
                    f"File '{file_path.name}' is too small ({size_kb:.1f}KB). Minimum: {self.min_file_size_kb}KB",
                    error_type="FILE_TOO_SMALL",
                    details={"file": file_path.name, "size_kb": size_kb, "min_kb": self.min_file_size_kb}
                )

    def parse_csv(self, file_path: Path) -> pd.DataFrame:
        """Parse a CSV file in enterprise format into a DataFrame.

        Enterprise format structure:
        - Rows 1-9: Metadata rows (ignored)
        - Row 10, Column B: Contains "Timestamp:" marker
        - Row 11: Column headers
        - Row 12+: Data rows
        - Column A: Empty/index column (removed)

        Args:
            file_path: Path to the CSV file

        Returns:
            Parsed DataFrame with normalized column names

        Raises:
            InitialValidationError: If parsing fails
        """
        try:
            # Read CSV without headers to handle enterprise format
            raw_df = pd.read_csv(
                file_path,
                encoding='utf-8',
                header=None,
                low_memory=False,
            )

            # Validate minimum dimensions for enterprise format
            if raw_df.shape[0] < 11 or raw_df.shape[1] < 2:
                raise InitialValidationError(
                    f"File '{file_path.name}' is too small for enterprise format "
                    f"(rows: {raw_df.shape[0]}, cols: {raw_df.shape[1]}). "
                    f"Expected at least 11 rows and 2 columns.",
                    error_type="FORMAT_ERROR",
                    details={"file": file_path.name, "rows": raw_df.shape[0], "cols": raw_df.shape[1]}
                )

            # Validate timestamp marker in row 10 (index 9), column B (index 1)
            timestamp_cell = raw_df.iloc[9, 1]
            if not isinstance(timestamp_cell, str) or "timestamp" not in timestamp_cell.lower():
                raise InitialValidationError(
                    f"File '{file_path.name}' does not match enterprise format. "
                    f"Expected 'Timestamp:' in row 10 column B, found: '{timestamp_cell}'",
                    error_type="FORMAT_ERROR",
                    details={"file": file_path.name, "found": str(timestamp_cell)}
                )

            # Remove first column (Column A - usually empty/index)
            df_no_first_col = raw_df.iloc[:, 1:]

            # Extract headers from row 11 (index 10)
            raw_headers = df_no_first_col.iloc[10].tolist()
            normalized_headers = [normalize_column_name(h) for h in raw_headers]

            # Extract data starting from row 12 (index 11)
            data_df = df_no_first_col.iloc[11:].copy()
            data_df.columns = normalized_headers
            data_df.reset_index(drop=True, inplace=True)

            # Remove empty columns (columns with empty string names)
            data_df = data_df.loc[:, data_df.columns != '']

            # Remove completely empty rows
            data_df = data_df.dropna(how='all')

            # Convert column types based on schema
            data_df = self.convert_column_types(data_df)

            logger.info(
                "Parsed controls CSV (enterprise format): {} rows, {} columns from {}",
                len(data_df), len(data_df.columns), file_path.name
            )

            return data_df

        except InitialValidationError:
            raise
        except pd.errors.EmptyDataError:
            raise InitialValidationError(
                f"File '{file_path.name}' is empty or contains no data",
                error_type="EMPTY_FILE",
                details={"file": file_path.name}
            )
        except pd.errors.ParserError as e:
            raise InitialValidationError(
                f"Failed to parse CSV file '{file_path.name}': {e}",
                error_type="PARSE_ERROR",
                details={"file": file_path.name, "error": str(e)}
            )
        except Exception as e:
            raise InitialValidationError(
                f"Unexpected error reading '{file_path.name}': {e}",
                error_type="READ_ERROR",
                details={"file": file_path.name, "error": str(e)}
            )

    def parse_and_convert(self, file_paths: List[Path]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse CSV files and return a combined DataFrame.

        This is the main entry point for initial validation.

        Args:
            file_paths: List of uploaded CSV file paths

        Returns:
            Tuple of (DataFrame, metadata dict with parsing info)

        Raises:
            InitialValidationError: If validation or parsing fails
        """
        # Validate file requirements first
        self.validate_file_requirements(file_paths)

        # Parse the single controls file
        file_path = file_paths[0]
        df = self.parse_csv(file_path)

        metadata = {
            "source_file": file_path.name,
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
        }

        return df, metadata


# Module-level instance for easy access
validator = InitialValidator()


def get_validator() -> InitialValidator:
    """Get the validator instance for controls."""
    return validator
