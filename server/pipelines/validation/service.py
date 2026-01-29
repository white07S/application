"""Validation service with pipeline tracking.

This module wraps the validation functions with proper database tracking,
creating PipelineRun records and updating status throughout the process.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from server.database import PipelineRun, UploadBatch
from server.logging_config import get_logger

from .. import storage
from .core import (
    ValidationResult,
    validate_and_split,
)

logger = get_logger(name=__name__)


def create_validation_run(db: Session, batch_id: int) -> PipelineRun:
    """Create a new PipelineRun for validation.

    Args:
        db: Database session
        batch_id: The upload batch ID

    Returns:
        The created PipelineRun record
    """
    run = PipelineRun(
        upload_batch_id=batch_id,
        pipeline_type="validation",
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.flush()

    logger.info("Created validation PipelineRun: id={}, batch_id={}", run.id, batch_id)
    return run


def start_validation_run(db: Session, run: PipelineRun) -> None:
    """Mark a validation run as started.

    Args:
        db: Database session
        run: The PipelineRun to update
    """
    run.status = "running"
    run.started_at = datetime.utcnow()
    db.flush()

    logger.info("Started validation run: id={}", run.id)


def complete_validation_run(
    db: Session,
    run: PipelineRun,
    success: bool,
    records_total: int = 0,
    records_processed: int = 0,
    records_failed: int = 0,
    error_details: Optional[str] = None,
) -> None:
    """Mark a validation run as complete.

    Args:
        db: Database session
        run: The PipelineRun to update
        success: Whether validation succeeded
        records_total: Total number of records validated
        records_processed: Number of records successfully processed
        records_failed: Number of records that failed validation
        error_details: JSON string with error details if failed
    """
    run.status = "success" if success else "failed"
    run.completed_at = datetime.utcnow()
    run.records_total = records_total
    run.records_processed = records_processed
    run.records_failed = records_failed
    run.error_details = error_details
    db.flush()

    logger.info(
        "Completed validation run: id={}, status={}, total={}, processed={}, failed={}",
        run.id, run.status, records_total, records_processed, records_failed
    )


def run_validation(
    db: Session,
    batch: UploadBatch,
    data_type: str,
    batch_path: Path,
) -> Tuple[bool, Optional[Dict[str, pd.DataFrame]], PipelineRun]:
    """Run validation for an upload batch with full tracking.

    This function:
    1. Creates a PipelineRun record for validation
    2. Reads files from batch_path
    3. Runs appropriate validation based on data_type
    4. Saves parquet files if valid
    5. Updates PipelineRun with results
    6. Updates UploadBatch status

    Args:
        db: Database session
        batch: The UploadBatch to validate
        data_type: Type of data (issues, controls, actions)
        batch_path: Path to the uploaded files

    Returns:
        Tuple of (success, parquet_tables dict or None, PipelineRun)
    """
    # Create validation run
    run = create_validation_run(db, batch.id)
    start_validation_run(db, run)

    # Update batch status
    batch.status = "validating"
    batch.started_at = datetime.utcnow()
    db.flush()

    try:
        # Collect file paths (CSV files)
        file_paths = [
            file_path for file_path in batch_path.iterdir()
            if file_path.suffix.lower() == ".csv"
        ]

        logger.info(
            "Running validation for batch {}: data_type={}, file_count={}, files={}",
            batch.upload_id, data_type, len(file_paths), [f.name for f in file_paths]
        )

        # Run unified validation (initial parsing + schema validation + table splitting)
        # File count validation is handled by the initial_validation.py module
        validation_result, parquet_tables = validate_and_split(data_type, file_paths)

        logger.info(
            "{} validation complete: is_valid={}, errors={}",
            data_type.capitalize(),
            validation_result.is_valid,
            [e.to_dict() for e in validation_result.errors[:10]]
        )

        # Log validation result details
        logger.info(
            "Validation result for batch {}: is_valid={}, errors={}, warnings={}, rows={}, cols={}",
            batch.upload_id,
            validation_result.is_valid,
            len(validation_result.errors),
            len(validation_result.warnings),
            validation_result.row_count,
            validation_result.column_count,
        )

        if validation_result.errors:
            for err in validation_result.errors[:5]:  # Log first 5 errors
                logger.warning(
                    "Validation error: column={}, type={}, message={}",
                    err.column, err.error_type, err.message
                )

        # Check validation result
        if not validation_result.is_valid:
            error_details = json.dumps(validation_result.to_dict())

            complete_validation_run(
                db, run,
                success=False,
                records_total=validation_result.row_count,
                records_failed=len(validation_result.errors),
                error_details=error_details,
            )

            batch.status = "failed"
            batch.error_code = "VALIDATION_ERROR"
            batch.error_details = error_details
            batch.completed_at = datetime.utcnow()
            db.flush()

            logger.warning(
                "Validation failed for batch {}: {} errors",
                batch.upload_id, len(validation_result.errors)
            )
            return False, None, run

        # Save parquet files to preprocessed directory
        preprocessed_path = storage.get_preprocessed_batch_path(batch.upload_id, data_type)
        preprocessed_path.mkdir(parents=True, exist_ok=True)

        total_records = 0
        if parquet_tables:
            for table_name, df in parquet_tables.items():
                parquet_file = preprocessed_path / f"{table_name}.parquet"
                df.to_parquet(parquet_file, index=False)
                total_records += len(df)
                logger.info("Saved parquet: {} ({} rows)", parquet_file, len(df))

        # Complete validation run successfully
        complete_validation_run(
            db, run,
            success=True,
            records_total=validation_result.row_count,
            records_processed=validation_result.row_count,
        )

        # Update batch status
        batch.status = "validated"
        batch.total_records = total_records
        db.flush()

        logger.info(
            "Validation successful for batch {}: {} tables, {} total records",
            batch.upload_id, len(parquet_tables) if parquet_tables else 0, total_records
        )

        return True, parquet_tables, run

    except Exception as e:
        logger.exception("Validation error for batch {}", batch.upload_id)

        complete_validation_run(
            db, run,
            success=False,
            error_details=json.dumps({"error": "VALIDATION_EXCEPTION", "message": str(e)}),
        )

        batch.status = "failed"
        batch.error_code = "VALIDATION_EXCEPTION"
        batch.error_details = str(e)
        batch.completed_at = datetime.utcnow()
        db.flush()

        return False, None, run


def get_validation_status(db: Session, batch_id: int) -> Optional[dict]:
    """Get the validation status for a batch.

    Args:
        db: Database session
        batch_id: The upload batch ID

    Returns:
        Dict with validation status or None if not found
    """
    run = db.query(PipelineRun).filter_by(
        upload_batch_id=batch_id,
        pipeline_type="validation"
    ).order_by(PipelineRun.created_at.desc()).first()

    if not run:
        return None

    return {
        "run_id": run.id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "records_total": run.records_total,
        "records_processed": run.records_processed,
        "records_failed": run.records_failed,
        "error_details": json.loads(run.error_details) if run.error_details else None,
    }
