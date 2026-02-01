"""Upload processing service.

This module orchestrates the upload flow:
1. Split enterprise CSV into component tables
2. Validate component tables
3. Return success/failure with details
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from server.logging_config import get_logger

from .split_controls import split_controls_csv
from .validate_controls import ValidationIssue, validate_controls

logger = get_logger(name=__name__)


@dataclass
class UploadResult:
    """Result of upload processing."""

    success: bool
    batch_id: str
    message: str
    errors: List[Dict] = field(default_factory=list)
    warnings: List[Dict] = field(default_factory=list)
    table_counts: Dict[str, int] = field(default_factory=dict)
    processed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "batch_id": self.batch_id,
            "message": self.message,
            "errors": self.errors,
            "warnings": self.warnings,
            "table_counts": self.table_counts,
            "processed_at": self.processed_at.isoformat(),
        }


def process_upload(upload_path: Path, batch_id: str) -> UploadResult:
    """Process an uploaded controls file.

    This function orchestrates the upload flow:
    1. Split enterprise CSV into component tables
    2. Validate component tables
    3. Return success/failure with details

    Args:
        upload_path: Path to the uploaded CSV file
        batch_id: Unique batch identifier

    Returns:
        UploadResult with success status and details
    """
    logger.info("Processing upload for batch {}: {}", batch_id, upload_path)

    try:
        # Step 1: Split enterprise CSV into components
        logger.info("Step 1: Splitting enterprise CSV")

        # Create output directory for split files
        split_dir = upload_path.parent / "split"
        split_dir.mkdir(parents=True, exist_ok=True)

        # Split the CSV
        tables = split_controls_csv(upload_path, split_dir)

        # Count records in each table
        table_counts = {name: len(df) for name, df in tables.items()}
        logger.info("Split complete: {} tables created", len(tables))

        # Step 2: Validate components
        logger.info("Step 2: Validating component tables")
        validation_result = validate_controls(split_dir)

        if not validation_result.is_valid:
            logger.warning(
                "Validation failed for batch {}: {} errors",
                batch_id, len(validation_result.errors)
            )

            return UploadResult(
                success=False,
                batch_id=batch_id,
                message=f"Validation failed with {len(validation_result.errors)} errors",
                errors=[
                    {"table": e.table, "column": e.column, "message": e.message}
                    for e in validation_result.errors
                ],
                warnings=[
                    {"table": w.table, "column": w.column, "message": w.message}
                    for w in validation_result.warnings
                ],
                table_counts=table_counts,
            )

        # Step 3: Success
        logger.info("Upload processing complete for batch {}", batch_id)

        return UploadResult(
            success=True,
            batch_id=batch_id,
            message="Upload processed successfully",
            errors=[],
            warnings=[
                {"table": w.table, "column": w.column, "message": w.message}
                for w in validation_result.warnings
            ],
            table_counts=table_counts,
        )

    except FileNotFoundError as e:
        logger.error("File not found during upload processing: {}", e)
        return UploadResult(
            success=False,
            batch_id=batch_id,
            message=f"File not found: {str(e)}",
            errors=[{"table": "SYSTEM", "column": None, "message": str(e)}],
        )

    except Exception as e:
        logger.exception("Upload processing failed for batch {}", batch_id)
        return UploadResult(
            success=False,
            batch_id=batch_id,
            message=f"Processing error: {str(e)}",
            errors=[{"table": "SYSTEM", "column": None, "message": str(e)}],
        )
