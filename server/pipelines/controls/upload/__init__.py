"""Upload module for splitting and validating enterprise CSV files.

This module provides functionality to:
- Split enterprise-format CSV files into component tables
- Validate component tables for schema and referential integrity
- Orchestrate the complete upload processing flow
"""
from .service import UploadResult, process_upload
from .split_controls import split_controls_csv
from .validate_controls import ValidationResult, validate_controls

__all__ = [
    "process_upload",
    "split_controls_csv",
    "validate_controls",
    "UploadResult",
    "ValidationResult",
]
