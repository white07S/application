import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Tuple

from fastapi import HTTPException, UploadFile

from server import settings
from server.logging_config import get_logger

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


async def save_files(
    files: List[UploadFile], data_type: DataType, ingestion_id: str, user: str
) -> int:
    """
    Save uploaded files to the appropriate directory.
    Returns number of files saved.
    """
    # Ensure directory exists
    target_dir = settings.DATA_INGESTION_PATH / data_type
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_count = 0

    for file in files:
        if not file.filename:
            continue

        # Create filename with ingestion ID prefix
        new_filename = f"{ingestion_id}_{file.filename}"
        file_path = target_dir / new_filename

        # Read and save file content
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(
            "File saved: %s (size: %d bytes) by user: %s",
            file_path,
            len(content),
            user,
        )
        saved_count += 1

    return saved_count


async def ingest_files(
    files: List[UploadFile], data_type: DataType, user: str
) -> dict:
    """
    Main ingestion function that validates and saves files.
    """
    # Validate files
    is_valid, error_message = await validate_files(files, data_type)
    if not is_valid:
        logger.warning("Validation failed for %s: %s", data_type, error_message)
        raise HTTPException(status_code=400, detail=error_message)

    # Generate ingestion ID
    ingestion_id = generate_ingestion_id()
    logger.info("Generated ingestion ID: %s for data type: %s", ingestion_id, data_type)

    # Calculate total size and collect file names before saving
    file_names = []
    total_size = 0
    for file in files:
        if file.filename:
            file_names.append(file.filename)
        content = await file.read()
        total_size += len(content)
        await file.seek(0)  # Reset for save_files

    # Save files
    saved_count = await save_files(files, data_type, ingestion_id, user)

    # Save history record
    history_record = {
        "ingestionId": ingestion_id,
        "dataType": data_type,
        "filesCount": saved_count,
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
        "message": f"Successfully ingested {saved_count} file(s)",
        "filesUploaded": saved_count,
        "dataType": data_type,
    }
