import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Tuple

from fastapi import HTTPException, UploadFile

from server import settings
from server.logging_config import get_logger
from . import validation as validator

logger = get_logger(name=__name__)

DataType = Literal["issues", "controls", "actions"]

# Validation requirements per data type
VALIDATION_RULES = {
    "issues": {"file_count": 4, "min_size_kb": 5},
    "controls": {"file_count": 1, "min_size_kb": 5},
    "actions": {"file_count": 1, "min_size_kb": 5},
}


def _get_tracker_path() -> Path:
    """Get path to the ingestion ID tracker file."""
    return settings.DATA_INGESTION_PATH / ".ingestion_tracker.json"


def _get_history_path() -> Path:
    """Get path to the ingestion history file."""
    return settings.DATA_INGESTION_PATH / ".ingestion_history.json"


def _load_history() -> List[dict]:
    """Load ingestion history records."""
    history_path = _get_history_path()
    if history_path.exists():
        with open(history_path, "r") as f:
            return json.load(f)
    return []


def _save_history(records: List[dict]) -> None:
    """Save ingestion history records."""
    history_path = _get_history_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "w") as f:
        json.dump(records, f, indent=2)


def _add_history_record(record: dict) -> None:
    """Add a new record to ingestion history."""
    records = _load_history()
    records.insert(0, record)  # Add to beginning (newest first)
    _save_history(records)


def get_ingestion_history(limit: int = 50, offset: int = 0) -> dict:
    """Get paginated ingestion history."""
    records = _load_history()
    total = len(records)
    paginated = records[offset:offset + limit]
    return {"records": paginated, "total": total}


def _load_tracker() -> dict:
    """Load the ingestion tracker data."""
    tracker_path = _get_tracker_path()
    if tracker_path.exists():
        with open(tracker_path, "r") as f:
            return json.load(f)
    return {"last_year": None, "last_sequence": 0}


def _save_tracker(data: dict) -> None:
    """Save the ingestion tracker data."""
    tracker_path = _get_tracker_path()
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tracker_path, "w") as f:
        json.dump(data, f)


def generate_ingestion_id() -> str:
    """
    Generate a sequential ingestion ID in format ING-YYYY-XXXX.
    Resets sequence at the start of each year.
    """
    current_year = datetime.now().year
    tracker = _load_tracker()

    if tracker["last_year"] != current_year:
        # New year, reset sequence
        sequence = 1
    else:
        sequence = tracker["last_sequence"] + 1

    # Update tracker
    tracker["last_year"] = current_year
    tracker["last_sequence"] = sequence
    _save_tracker(tracker)

    return f"ING-{current_year}-{sequence:04d}"


async def validate_files(
    files: List[UploadFile], data_type: DataType
) -> Tuple[bool, str]:
    """
    Validate uploaded files based on data type requirements.
    Returns (is_valid, error_message).
    """
    rules = VALIDATION_RULES.get(data_type)
    if not rules:
        return False, f"Invalid data type: {data_type}"

    expected_count = rules["file_count"]
    min_size_bytes = rules["min_size_kb"] * 1024

    # Check file count
    if len(files) != expected_count:
        return False, f"Expected {expected_count} file(s) for {data_type}, got {len(files)}"

    # Check each file
    for file in files:
        # Check extension
        if not file.filename or not file.filename.lower().endswith(".xlsx"):
            return False, f"File '{file.filename}' must be an .xlsx file"

        # Check size by reading content
        content = await file.read()
        await file.seek(0)  # Reset file pointer for later use

        if len(content) < min_size_bytes:
            return (
                False,
                f"File '{file.filename}' is too small ({len(content)} bytes). Minimum size is {rules['min_size_kb']}KB",
            )

    return True, ""


async def ingest_files(
    files: List[UploadFile], data_type: DataType, user: str
) -> dict:
    """
    Main ingestion function that validates and saves files.
    """
    # Validate basic file count and extension/size
    is_valid, error_message = await validate_files(files, data_type)
    if not is_valid:
        logger.warning("Validation failed for %s: %s", data_type, error_message)
        raise HTTPException(status_code=400, detail=error_message)

    ingestion_id = generate_ingestion_id()
    logger.info("Generated ingestion ID: %s for data type: %s", ingestion_id, data_type)

    # Read files into memory once for processing and persistence
    file_payloads: List[Tuple[str, bytes]] = []
    file_names: List[str] = []
    total_size = 0
    for file in files:
        content = await file.read()
        await file.seek(0)
        name = file.filename or "uploaded.xlsx"
        file_payloads.append((name, content))
        file_names.append(name)
        total_size += len(content)

    # Validate and split into parquet tables
    try:
        if data_type == "controls":
            validation_result, parquet_tables = validator.validate_and_split_controls(
                file_payloads[0][1], file_payloads[0][0]
            )
        elif data_type == "issues":
            validation_result, parquet_tables = validator.validate_and_split_issues(file_payloads)
        elif data_type == "actions":
            validation_result, parquet_tables = validator.validate_and_split_actions(
                file_payloads[0][1], file_payloads[0][0]
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported data type: {data_type}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during %s validation", data_type)
        raise HTTPException(status_code=500, detail="Internal validation error") from exc

    if not validation_result.is_valid or parquet_tables is None:
        detail = {
            "message": f"Validation failed for {data_type}",
            "errors": [err.to_dict() for err in validation_result.errors],
            "warnings": [warn.to_dict() for warn in validation_result.warnings],
        }
        logger.warning("Validation errors for %s: %s", data_type, detail)
        raise HTTPException(status_code=400, detail=detail)

    # Persist raw uploads and parquet outputs atomically
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"{ingestion_id}_", dir=settings.DATA_INGESTION_PATH))
    raw_dir = tmp_dir / "raw"
    parquet_dir = tmp_dir / "parquet"
    raw_dir.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Save raw uploads with ingestion prefix
        for name, content in file_payloads:
            raw_path = raw_dir / f"{ingestion_id}_{name}"
            raw_path.write_bytes(content)

        # Save parquet tables
        for table_name, df in parquet_tables.items():
            output_path = parquet_dir / f"{table_name}.parquet"
            df.to_parquet(output_path, index=False, engine="pyarrow")

        final_dir = settings.DATA_INGESTION_PATH / data_type / ingestion_id
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_dir), final_dir)
        logger.info(
            "Ingestion %s completed. Stored raw + parquet at %s",
            ingestion_id,
            final_dir,
        )
    except Exception as exc:
        logger.exception("Failed to persist ingestion %s output", ingestion_id)
        # Attempt cleanup of staging directory on failure
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Failed to store processed data") from exc

    # Save history record
    history_record = {
        "ingestionId": ingestion_id,
        "dataType": data_type,
        "filesCount": len(file_payloads),
        "fileNames": file_names,
        "totalSizeBytes": total_size,
        "uploadedBy": user,
        "uploadedAt": datetime.now().isoformat(),
        "status": "success",
    }
    _add_history_record(history_record)
    logger.info("Saved ingestion history record: %s", ingestion_id)

    return {
        "success": True,
        "ingestionId": ingestion_id,
        "message": f"Successfully ingested {len(file_payloads)} file(s) and generated parquet outputs",
        "filesUploaded": len(file_payloads),
        "dataType": data_type,
    }
