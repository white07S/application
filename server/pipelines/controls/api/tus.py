"""TUS (resumable upload) protocol implementation for FastAPI.

This module implements the TUS 1.0.0 resumable upload protocol.
See: https://tus.io/protocols/resumable-upload

Supported extensions:
- creation: POST to create new uploads
- expiration: Upload expiration timestamps
- termination: DELETE to abort uploads

Endpoints:
- OPTIONS /tus - Return TUS capabilities
- POST /tus - Create new upload
- HEAD /tus/{upload_id} - Get upload offset/status
- PATCH /tus/{upload_id} - Upload chunk
- DELETE /tus/{upload_id} - Abort upload (termination extension)
"""
import base64
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from server import settings
from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.jobs import get_jobs_db, TusUpload, UploadBatch
from server.logging_config import get_logger

from ... import upload_tracker
from ... import storage

logger = get_logger(name=__name__)

# TUS Protocol constants
TUS_VERSION = "1.0.0"
TUS_EXTENSIONS = "creation,expiration,termination"
TUS_MAX_SIZE = 10 * 1024 * 1024 * 1024  # 10GB max upload size
TUS_UPLOAD_EXPIRATION_HOURS = 24  # Uploads expire after 24 hours

# Directory for TUS partial uploads
TUS_UPLOADS_DIR = ".tus_uploads"


def get_tus_uploads_path() -> Path:
    """Get the TUS uploads directory path."""
    return settings.DATA_INGESTION_PATH / TUS_UPLOADS_DIR


def get_tus_upload_file_path(tus_id: str) -> Path:
    """Get the path for a specific TUS upload file."""
    return get_tus_uploads_path() / tus_id


def parse_upload_metadata(metadata_header: Optional[str]) -> dict:
    """Parse TUS Upload-Metadata header.

    Format: key base64value,key2 base64value2
    Keys are ASCII, values are Base64-encoded.

    Args:
        metadata_header: The Upload-Metadata header value

    Returns:
        dict: Parsed metadata key-value pairs
    """
    if not metadata_header:
        return {}

    metadata = {}
    pairs = metadata_header.split(",")

    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue

        parts = pair.split(" ", 1)
        key = parts[0].strip()

        if len(parts) > 1 and parts[1].strip():
            try:
                value = base64.b64decode(parts[1].strip()).decode("utf-8")
            except Exception:
                value = parts[1].strip()  # Use raw value if decode fails
        else:
            value = ""

        metadata[key] = value

    return metadata


def add_tus_headers(response: Response) -> None:
    """Add common TUS headers to response."""
    response.headers["Tus-Resumable"] = TUS_VERSION
    response.headers["Access-Control-Expose-Headers"] = (
        "Location, Upload-Offset, Upload-Length, Tus-Version, "
        "Tus-Resumable, Tus-Max-Size, Tus-Extension, Upload-Expires"
    )


def create_tus_response(
    status_code: int = 204,
    headers: Optional[dict] = None,
    content: Optional[bytes] = None,
) -> Response:
    """Create a response with TUS headers."""
    response = Response(
        content=content,
        status_code=status_code,
        media_type="application/octet-stream" if content else None,
    )
    add_tus_headers(response)

    if headers:
        for key, value in headers.items():
            response.headers[key] = str(value)

    return response


router = APIRouter(prefix="/v2/pipelines/tus", tags=["TUS Resumable Upload"])


@router.options("")
@router.options("/")
async def tus_options() -> Response:
    """Return TUS server capabilities.

    This endpoint tells clients what TUS features this server supports.
    """
    response = create_tus_response(status_code=204)
    response.headers["Tus-Version"] = TUS_VERSION
    response.headers["Tus-Extension"] = TUS_EXTENSIONS
    response.headers["Tus-Max-Size"] = str(TUS_MAX_SIZE)
    return response


@router.options("/{upload_id}")
async def tus_options_upload(upload_id: str) -> Response:
    """Return TUS server capabilities for specific upload URL."""
    return await tus_options()


@router.post("")
@router.post("/")
async def tus_create(
    request: Request,
    upload_length: Optional[int] = Header(None, alias="Upload-Length"),
    upload_metadata: Optional[str] = Header(None, alias="Upload-Metadata"),
    tus_resumable: str = Header(..., alias="Tus-Resumable"),
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
) -> Response:
    """Create a new TUS upload.

    This endpoint creates a new upload resource and returns a Location header
    with the URL to use for uploading chunks.

    Required headers:
    - Upload-Length: Total file size in bytes
    - Tus-Resumable: Must be 1.0.0
    - Upload-Metadata: Base64 encoded metadata (filename, data_type required)

    Returns:
    - 201 Created with Location header
    """
    # Validate TUS version
    if tus_resumable != TUS_VERSION:
        raise HTTPException(
            status_code=412,
            detail=f"Unsupported TUS version: {tus_resumable}. Server supports {TUS_VERSION}",
        )

    # Check authentication and authorization
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        logger.warning("User {} denied access to TUS upload", access.user)
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to upload pipeline data",
        )

    # Validate Upload-Length
    if upload_length is None:
        raise HTTPException(
            status_code=400,
            detail="Upload-Length header is required",
        )

    if upload_length < 0:
        raise HTTPException(
            status_code=400,
            detail="Upload-Length must be non-negative",
        )

    if upload_length > TUS_MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Upload-Length exceeds maximum size of {TUS_MAX_SIZE} bytes",
        )

    # Parse metadata
    metadata = parse_upload_metadata(upload_metadata)
    logger.info("TUS create request - metadata: {}", metadata)

    # Extract required metadata fields
    filename = metadata.get("filename")
    data_type = metadata.get("data_type")
    batch_session_id = metadata.get("batch_session_id")
    expected_files_str = metadata.get("expected_files", "1")

    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Upload-Metadata must include 'filename'",
        )

    if not data_type:
        raise HTTPException(
            status_code=400,
            detail="Upload-Metadata must include 'data_type'",
        )

    if data_type not in ("issues", "controls", "actions"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid data_type: {data_type}. Must be one of: issues, controls, actions",
        )

    # Validate file extension
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' must be a .csv file",
        )

    # Parse expected_files
    try:
        expected_files = int(expected_files_str)
    except ValueError:
        expected_files = 1

    # Validate expected_files matches data_type requirements
    expected_file_counts = {"issues": 4, "controls": 1, "actions": 1}
    required_count = expected_file_counts.get(data_type, 1)
    if expected_files != required_count:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid expected_files for {data_type}: expected {required_count}, got {expected_files}",
        )

    # Generate batch_session_id if not provided (for single file uploads)
    if not batch_session_id:
        batch_session_id = str(uuid.uuid4())

    # Check if this batch_session already has the expected number of files
    existing_in_session = db.query(TusUpload).filter_by(
        batch_session_id=batch_session_id
    ).count()
    if existing_in_session >= expected_files:
        raise HTTPException(
            status_code=400,
            detail=f"Batch session {batch_session_id} already has {existing_in_session} file(s). "
                   f"Maximum for {data_type} is {expected_files}.",
        )

    # Generate TUS upload ID (UUID)
    tus_id = str(uuid.uuid4())

    # Create TUS uploads directory if needed
    tus_dir = get_tus_uploads_path()
    tus_dir.mkdir(parents=True, exist_ok=True)

    # Create empty file for the upload
    upload_file_path = get_tus_upload_file_path(tus_id)
    upload_file_path.touch()

    # Calculate expiration time
    expires_at = datetime.utcnow() + timedelta(hours=TUS_UPLOAD_EXPIRATION_HOURS)

    # Create TUS upload record in database
    tus_upload = TusUpload(
        id=tus_id,
        batch_session_id=batch_session_id,
        data_type=data_type,
        filename=filename,
        file_size=upload_length,
        offset=0,
        is_complete=False,
        uploaded_by=access.user,
        temp_path=str(upload_file_path),
        metadata_json=json.dumps(metadata),
        expected_files=expected_files,
        created_at=datetime.utcnow(),
        expires_at=expires_at,
    )
    db.add(tus_upload)
    db.commit()

    logger.info(
        "TUS upload created: id=%s, filename=%s, data_type=%s, size=%d, user=%s",
        tus_id, filename, data_type, upload_length, access.user,
    )

    # Build location URL
    location = f"{tus_id}"

    response = create_tus_response(
        status_code=201,
        headers={
            "Location": location,
            "Upload-Expires": expires_at.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        },
    )

    return response


@router.head("/{upload_id}")
async def tus_head(
    upload_id: str,
    tus_resumable: str = Header(..., alias="Tus-Resumable"),
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
) -> Response:
    """Get the current offset for a TUS upload.

    This endpoint allows clients to determine the current state of an upload
    so they can resume from the correct position.

    Returns:
    - 200 OK with Upload-Offset and Upload-Length headers
    - 404 if upload not found
    - 410 if upload expired or completed
    """
    # Validate TUS version
    if tus_resumable != TUS_VERSION:
        raise HTTPException(
            status_code=412,
            detail=f"Unsupported TUS version: {tus_resumable}",
        )

    # Check authentication
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get upload record
    tus_upload = db.query(TusUpload).filter_by(id=upload_id).first()

    if not tus_upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Check if expired
    if tus_upload.expires_at and datetime.utcnow() > tus_upload.expires_at:
        raise HTTPException(status_code=410, detail="Upload has expired")

    # Check if already complete
    if tus_upload.is_complete:
        raise HTTPException(status_code=410, detail="Upload already completed")

    response = create_tus_response(
        status_code=200,
        headers={
            "Upload-Offset": str(tus_upload.offset),
            "Upload-Length": str(tus_upload.file_size),
            "Cache-Control": "no-store",
        },
    )

    if tus_upload.expires_at:
        response.headers["Upload-Expires"] = tus_upload.expires_at.strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

    return response


@router.patch("/{upload_id}")
async def tus_patch(
    upload_id: str,
    request: Request,
    upload_offset: int = Header(..., alias="Upload-Offset"),
    content_type: str = Header(..., alias="Content-Type"),
    tus_resumable: str = Header(..., alias="Tus-Resumable"),
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
) -> Response:
    """Upload a chunk of data to a TUS upload.

    This endpoint appends data to an existing upload at the specified offset.

    Required headers:
    - Upload-Offset: The byte offset to start writing at
    - Content-Type: Must be application/offset+octet-stream
    - Tus-Resumable: Must be 1.0.0

    Returns:
    - 204 No Content with new Upload-Offset on success
    - 409 Conflict if Upload-Offset doesn't match current offset
    """
    # Validate TUS version
    if tus_resumable != TUS_VERSION:
        raise HTTPException(
            status_code=412,
            detail=f"Unsupported TUS version: {tus_resumable}",
        )

    # Validate Content-Type
    if content_type != "application/offset+octet-stream":
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/offset+octet-stream",
        )

    # Check authentication
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get upload record
    tus_upload = db.query(TusUpload).filter_by(id=upload_id).first()

    if not tus_upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Check if expired
    if tus_upload.expires_at and datetime.utcnow() > tus_upload.expires_at:
        raise HTTPException(status_code=410, detail="Upload has expired")

    # Check if already complete
    if tus_upload.is_complete:
        raise HTTPException(status_code=410, detail="Upload already completed")

    # Validate offset matches current position
    if upload_offset != tus_upload.offset:
        raise HTTPException(
            status_code=409,
            detail=f"Upload-Offset mismatch. Expected {tus_upload.offset}, got {upload_offset}",
        )

    # Read the chunk data
    chunk_data = await request.body()
    chunk_size = len(chunk_data)

    if chunk_size == 0:
        raise HTTPException(status_code=400, detail="Empty chunk")

    # Validate chunk doesn't exceed file size
    new_offset = tus_upload.offset + chunk_size
    if new_offset > tus_upload.file_size:
        raise HTTPException(
            status_code=400,
            detail=f"Chunk would exceed declared file size. Current: {tus_upload.offset}, "
                   f"Chunk: {chunk_size}, Max: {tus_upload.file_size}",
        )

    # Write chunk to file
    upload_file_path = Path(tus_upload.temp_path)
    try:
        with open(upload_file_path, "ab") as f:
            f.write(chunk_data)
    except Exception as e:
        logger.exception("Failed to write chunk for upload {}", upload_id)
        raise HTTPException(status_code=500, detail="Failed to write chunk data")

    # Update offset in database
    tus_upload.offset = new_offset
    db.commit()

    logger.info(
        "TUS chunk uploaded: id=%s, offset=%d->%d, size=%d",
        upload_id, upload_offset, new_offset, chunk_size,
    )

    # Check if upload is complete
    if new_offset == tus_upload.file_size:
        await _complete_upload(tus_upload, db)

    response = create_tus_response(
        status_code=204,
        headers={
            "Upload-Offset": str(new_offset),
        },
    )

    if tus_upload.expires_at:
        response.headers["Upload-Expires"] = tus_upload.expires_at.strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

    return response


@router.delete("/{upload_id}")
async def tus_delete(
    upload_id: str,
    tus_resumable: str = Header(..., alias="Tus-Resumable"),
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
) -> Response:
    """Terminate/abort a TUS upload.

    This endpoint implements the TUS termination extension, allowing
    clients to abort an upload and free server resources.

    Returns:
    - 204 No Content on success
    - 404 if upload not found
    """
    # Validate TUS version
    if tus_resumable != TUS_VERSION:
        raise HTTPException(
            status_code=412,
            detail=f"Unsupported TUS version: {tus_resumable}",
        )

    # Check authentication
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get upload record
    tus_upload = db.query(TusUpload).filter_by(id=upload_id).first()

    if not tus_upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Delete the temp file
    upload_file_path = Path(tus_upload.temp_path)
    if upload_file_path.exists():
        upload_file_path.unlink()
        logger.info("Deleted TUS upload file: {}", upload_file_path)

    # Delete the database record
    db.delete(tus_upload)
    db.commit()

    logger.info("TUS upload terminated: id={}", upload_id)

    return create_tus_response(status_code=204)


async def _complete_upload(tus_upload: TusUpload, db: Session) -> None:
    """Handle completion of a single TUS file upload.

    This function is called when all bytes have been received for a single file.
    It marks the file as complete and checks if all files in the batch session
    are complete. Only when ALL files are complete does it create the UploadBatch
    and trigger split + validation for controls.

    Args:
        tus_upload: The completed TUS upload record
        db: Database session
    """
    import shutil

    logger.info(
        "TUS file upload complete: id=%s, filename=%s, size=%d, session=%s",
        tus_upload.id, tus_upload.filename, tus_upload.file_size, tus_upload.batch_session_id,
    )

    # Mark this file as complete
    tus_upload.is_complete = True
    tus_upload.completed_at = datetime.utcnow()
    db.flush()

    # Check how many files in this batch session are complete
    session_uploads = db.query(TusUpload).filter_by(
        batch_session_id=tus_upload.batch_session_id
    ).all()

    completed_count = sum(1 for u in session_uploads if u.is_complete)
    expected_count = tus_upload.expected_files

    logger.info(
        "Batch session %s: %d/%d files complete",
        tus_upload.batch_session_id, completed_count, expected_count,
    )

    # If not all files are complete yet, just return
    if completed_count < expected_count:
        db.commit()
        return

    # Check if this batch session was already processed (race condition guard)
    # If any upload in this session already has an upload_id, the batch was created
    existing_upload_id = next(
        (u.upload_id for u in session_uploads if u.upload_id is not None),
        None
    )
    if existing_upload_id:
        logger.info(
            "Batch session %s already processed (upload_id=%s), skipping",
            tus_upload.batch_session_id, existing_upload_id,
        )
        # Just set this file's upload_id to match
        tus_upload.upload_id = existing_upload_id
        db.commit()
        return

    # All files are complete! Create the UploadBatch and run processing
    logger.info(
        "All %d files complete for batch session %s. Creating UploadBatch...",
        expected_count, tus_upload.batch_session_id,
    )

    # Generate a single upload ID for the entire batch
    upload_id = upload_tracker.generate_upload_id()

    # Create the batch directory directly in preprocessed
    batch_path = storage.get_preprocessed_batch_path(upload_id, tus_upload.data_type)
    batch_path.mkdir(parents=True, exist_ok=True)

    # Move ALL files from this session to the batch directory
    for upload in session_uploads:
        temp_file_path = Path(upload.temp_path)
        final_file_path = batch_path / upload.filename

        try:
            if temp_file_path.exists():
                shutil.move(str(temp_file_path), str(final_file_path))
                logger.info("Moved TUS file to: {}", final_file_path)
            # Update the upload record with the batch upload_id
            upload.upload_id = upload_id
        except Exception as e:
            logger.exception("Failed to move TUS upload file: {}", upload.filename)
            raise

    # Create UploadBatch record
    batch = UploadBatch(
        upload_id=upload_id,
        data_type=tus_upload.data_type,
        status="pending",
        source_path=str(batch_path),
        uploaded_by=tus_upload.uploaded_by,
        file_count=expected_count,
        created_at=datetime.utcnow(),
    )
    db.add(batch)
    db.flush()

    logger.info(
        "Created UploadBatch for TUS session: upload_id=%s, batch_id=%d, files=%d",
        upload_id, batch.id, expected_count,
    )

    # Process based on data type
    if tus_upload.data_type == "controls":
        # Use new upload module for controls
        await _process_controls_upload(db, batch, batch_path, upload_id)
    else:
        # Issues and Actions are disabled ("In Development")
        logger.error(
            "Data type %s is not supported - Issues and Actions are disabled (In Development)",
            tus_upload.data_type
        )
        batch.status = "failed"
        batch.error_code = "unsupported_data_type"
        batch.error_details = f"Data type '{tus_upload.data_type}' is not supported. Only 'controls' uploads are currently enabled."
        batch.completed_at = datetime.utcnow()
        db.flush()

    db.commit()


async def _process_controls_upload(db: Session, batch: UploadBatch, batch_path: Path, upload_id: str) -> None:
    """Process controls upload using new upload module.

    Steps:
    1. Split enterprise CSV into component tables
    2. Validate component tables
    3. Convert to parquet (reusing existing infrastructure)
    4. Update batch status based on result

    Args:
        db: Database session
        batch: Upload batch record
        batch_path: Path to batch directory with CSV file
        upload_id: Upload ID (UPL-YYYY-XXXX)
    """
    from ..upload import split_controls_csv, validate_controls

    try:
        # Update batch status to validating
        batch.status = "validating"
        batch.started_at = datetime.utcnow()
        db.flush()

        # Find the enterprise CSV file
        csv_files = list(batch_path.glob("*.csv"))
        if not csv_files:
            raise ValueError(f"No CSV file found in batch directory: {batch_path}")

        enterprise_csv = csv_files[0]
        logger.info("Processing controls CSV: {}", enterprise_csv)

        # Step 1: Split enterprise CSV into component tables
        split_dir = storage.get_split_batch_path(upload_id, "controls")
        split_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Splitting controls CSV to: {}", split_dir)
        tables = split_controls_csv(enterprise_csv, split_dir)

        logger.info("Split complete: {} tables created", len(tables))

        # Step 2: Validate component tables
        logger.info("Validating component tables...")
        validation_result = validate_controls(split_dir)

        if not validation_result.is_valid:
            # Validation failed
            logger.warning(
                "Validation failed for batch {}: {} errors",
                upload_id, len(validation_result.errors)
            )

            batch.status = "failed"
            batch.error_code = "validation_failed"
            batch.error_details = json.dumps({
                "errors": [
                    {"table": e.table, "column": e.column, "message": e.message}
                    for e in validation_result.errors
                ],
                "warnings": [
                    {"table": w.table, "column": w.column, "message": w.message}
                    for w in validation_result.warnings
                ],
            })
            batch.completed_at = datetime.utcnow()
            db.flush()
            return

        # Step 3: Convert validated CSV files to parquet
        logger.info("Validation passed, converting to parquet...")

        # Load the split CSV files into DataFrames
        split_csv_files = list(split_dir.glob("*.csv"))
        parquet_tables = {}

        for csv_file in split_csv_files:
            table_name = csv_file.stem  # filename without extension
            df = pd.read_csv(csv_file)
            parquet_tables[table_name] = df
            logger.info("Loaded table {} with {} rows", table_name, len(df))

        # Save parquet files to preprocessed directory
        preprocessed_path = storage.get_preprocessed_batch_path(upload_id, "controls")
        preprocessed_path.mkdir(parents=True, exist_ok=True)

        for table_name, df in parquet_tables.items():
            parquet_file = preprocessed_path / f"{table_name}.parquet"
            df.to_parquet(parquet_file, index=False)
            logger.info("Saved parquet: {} ({} rows)", parquet_file, len(df))

        # Count unique controls from controls_main (not sum of all tables)
        total_records = len(parquet_tables.get("controls_main", []))

        # Success!
        batch.status = "validated"
        batch.total_records = total_records
        batch.completed_at = datetime.utcnow()
        db.flush()

        logger.info(
            "Controls upload processing complete: batch={}, records={}",
            upload_id, total_records
        )

    except Exception as e:
        logger.exception("Failed to process controls upload: {}", e)
        batch.status = "failed"
        batch.error_code = "processing_error"
        batch.error_details = str(e)
        batch.completed_at = datetime.utcnow()
        db.flush()
        raise


# ============== TUS Status Endpoint ==============

@router.get("/{upload_id}/status")
async def tus_status(
    upload_id: str,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_jobs_db),
) -> dict:
    """Get detailed status of a TUS upload.

    This is a convenience endpoint (not part of TUS protocol) that returns
    JSON status information about an upload.

    Returns JSON with:
    - id: TUS upload ID
    - upload_id: UPL-YYYY-XXXX (if complete)
    - filename: Original filename
    - data_type: Type of data
    - file_size: Total file size
    - offset: Current upload offset
    - progress: Upload progress percentage
    - is_complete: Whether upload is finished
    - batch_status: UploadBatch status (if complete)
    """
    # Check authentication
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get upload record
    tus_upload = db.query(TusUpload).filter_by(id=upload_id).first()

    if not tus_upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Calculate progress
    progress = (tus_upload.offset / tus_upload.file_size * 100) if tus_upload.file_size > 0 else 0

    # Get batch session progress
    session_uploads = db.query(TusUpload).filter_by(
        batch_session_id=tus_upload.batch_session_id
    ).all()
    completed_in_session = sum(1 for u in session_uploads if u.is_complete)

    result = {
        "id": tus_upload.id,
        "upload_id": tus_upload.upload_id,
        "filename": tus_upload.filename,
        "data_type": tus_upload.data_type,
        "file_size": tus_upload.file_size,
        "offset": tus_upload.offset,
        "progress": round(progress, 2),
        "is_complete": tus_upload.is_complete,
        "uploaded_by": tus_upload.uploaded_by,
        "created_at": tus_upload.created_at.isoformat() + "Z",
        "completed_at": tus_upload.completed_at.isoformat() + "Z" if tus_upload.completed_at else None,
        "expires_at": tus_upload.expires_at.isoformat() + "Z" if tus_upload.expires_at else None,
        "batch_session_id": tus_upload.batch_session_id,
        "expected_files": tus_upload.expected_files,
        "completed_files_in_session": completed_in_session,
        "all_files_complete": completed_in_session >= tus_upload.expected_files,
    }

    # If complete, get batch and validation status
    if tus_upload.is_complete and tus_upload.upload_id:
        batch = db.query(UploadBatch).filter_by(upload_id=tus_upload.upload_id).first()
        if batch:
            result["batch_id"] = batch.id
            result["batch_status"] = batch.status
            result["validation_errors"] = batch.error_details if batch.error_code else None

    return result
