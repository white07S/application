"""TUS (resumable upload) protocol implementation for FastAPI (async PostgreSQL).

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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

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

def get_tus_upload_file_path(tus_id: str) -> Path:
    """Get the path for a specific TUS upload file."""
    return storage.get_uploads_path() / tus_id


def parse_upload_metadata(metadata_header: Optional[str]) -> dict:
    """Parse TUS Upload-Metadata header.

    Format: key base64value,key2 base64value2
    Keys are ASCII, values are Base64-encoded.
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
                value = parts[1].strip()
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
    """Return TUS server capabilities."""
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
    db: AsyncSession = Depends(get_jobs_db),
) -> Response:
    """Create a new TUS upload."""
    if tus_resumable != TUS_VERSION:
        raise HTTPException(
            status_code=412,
            detail=f"Unsupported TUS version: {tus_resumable}. Server supports {TUS_VERSION}",
        )

    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        logger.warning("User {} denied access to TUS upload", access.user)
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to upload pipeline data",
        )

    if upload_length is None:
        raise HTTPException(status_code=400, detail="Upload-Length header is required")

    if upload_length < 0:
        raise HTTPException(status_code=400, detail="Upload-Length must be non-negative")

    if upload_length > TUS_MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Upload-Length exceeds maximum size of {TUS_MAX_SIZE} bytes",
        )

    metadata = parse_upload_metadata(upload_metadata)
    logger.info("TUS create request - metadata: {}", metadata)

    filename = metadata.get("filename")
    data_type = metadata.get("data_type")
    batch_session_id = metadata.get("batch_session_id")
    expected_files_str = metadata.get("expected_files", "1")

    if not filename:
        raise HTTPException(status_code=400, detail="Upload-Metadata must include 'filename'")

    if not data_type:
        raise HTTPException(status_code=400, detail="Upload-Metadata must include 'data_type'")

    if data_type not in ("issues", "controls", "actions"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid data_type: {data_type}. Must be one of: issues, controls, actions",
        )

    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail=f"File '{filename}' must be a .csv file")

    try:
        expected_files = int(expected_files_str)
    except ValueError:
        expected_files = 1

    expected_file_counts = {"issues": 4, "controls": 1, "actions": 1}
    required_count = expected_file_counts.get(data_type, 1)
    if expected_files != required_count:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid expected_files for {data_type}: expected {required_count}, got {expected_files}",
        )

    if not batch_session_id:
        batch_session_id = str(uuid.uuid4())

    # Check if this batch_session already has the expected number of files
    count_result = await db.execute(
        select(func.count()).select_from(TusUpload).where(
            TusUpload.batch_session_id == batch_session_id
        )
    )
    existing_in_session = count_result.scalar_one()
    if existing_in_session >= expected_files:
        raise HTTPException(
            status_code=400,
            detail=f"Batch session {batch_session_id} already has {existing_in_session} file(s). "
                   f"Maximum for {data_type} is {expected_files}.",
        )

    tus_id = str(uuid.uuid4())

    tus_dir = storage.get_uploads_path()
    tus_dir.mkdir(parents=True, exist_ok=True)

    upload_file_path = get_tus_upload_file_path(tus_id)
    upload_file_path.touch()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=TUS_UPLOAD_EXPIRATION_HOURS)

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
        created_at=now,
        expires_at=expires_at,
    )
    db.add(tus_upload)
    await db.commit()

    logger.info(
        "TUS upload created: id=%s, filename=%s, data_type=%s, size=%d, user=%s",
        tus_id, filename, data_type, upload_length, access.user,
    )

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
    db: AsyncSession = Depends(get_jobs_db),
) -> Response:
    """Get the current offset for a TUS upload."""
    if tus_resumable != TUS_VERSION:
        raise HTTPException(status_code=412, detail=f"Unsupported TUS version: {tus_resumable}")

    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(select(TusUpload).where(TusUpload.id == upload_id))
    tus_upload = result.scalar_one_or_none()

    if not tus_upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if tus_upload.expires_at and datetime.now(timezone.utc) > tus_upload.expires_at:
        raise HTTPException(status_code=410, detail="Upload has expired")

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
    db: AsyncSession = Depends(get_jobs_db),
) -> Response:
    """Upload a chunk of data to a TUS upload."""
    if tus_resumable != TUS_VERSION:
        raise HTTPException(status_code=412, detail=f"Unsupported TUS version: {tus_resumable}")

    if content_type != "application/offset+octet-stream":
        raise HTTPException(
            status_code=415, detail="Content-Type must be application/offset+octet-stream"
        )

    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(select(TusUpload).where(TusUpload.id == upload_id))
    tus_upload = result.scalar_one_or_none()

    if not tus_upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if tus_upload.expires_at and datetime.now(timezone.utc) > tus_upload.expires_at:
        raise HTTPException(status_code=410, detail="Upload has expired")

    if tus_upload.is_complete:
        raise HTTPException(status_code=410, detail="Upload already completed")

    if upload_offset != tus_upload.offset:
        raise HTTPException(
            status_code=409,
            detail=f"Upload-Offset mismatch. Expected {tus_upload.offset}, got {upload_offset}",
        )

    chunk_data = await request.body()
    chunk_size = len(chunk_data)

    if chunk_size == 0:
        raise HTTPException(status_code=400, detail="Empty chunk")

    new_offset = tus_upload.offset + chunk_size
    if new_offset > tus_upload.file_size:
        raise HTTPException(
            status_code=400,
            detail=f"Chunk would exceed declared file size. Current: {tus_upload.offset}, "
                   f"Chunk: {chunk_size}, Max: {tus_upload.file_size}",
        )

    upload_file_path = Path(tus_upload.temp_path)
    if not upload_file_path.exists():
        if upload_offset == 0:
            upload_file_path.parent.mkdir(parents=True, exist_ok=True)
            upload_file_path.touch()
        else:
            raise HTTPException(
                status_code=409,
                detail="Upload file missing or offset mismatch. Please retry from offset 0.",
            )

    try:
        on_disk_size = upload_file_path.stat().st_size
    except Exception:
        logger.exception("Failed to stat upload file for {}", upload_id)
        raise HTTPException(status_code=500, detail="Failed to access upload file")

    if on_disk_size != tus_upload.offset:
        raise HTTPException(
            status_code=409,
            detail=f"Upload file offset mismatch. Expected {tus_upload.offset}, got {on_disk_size}",
        )

    try:
        with open(upload_file_path, "r+b") as f:
            f.seek(upload_offset)
            f.write(chunk_data)
    except Exception:
        logger.exception("Failed to write chunk for upload {}", upload_id)
        raise HTTPException(status_code=500, detail="Failed to write chunk data")

    tus_upload.offset = new_offset
    await db.commit()

    logger.info(
        "TUS chunk uploaded: id=%s, offset=%d->%d, size=%d",
        upload_id, upload_offset, new_offset, chunk_size,
    )

    if new_offset == tus_upload.file_size:
        await _complete_upload(tus_upload, db)

    response = create_tus_response(
        status_code=204,
        headers={"Upload-Offset": str(new_offset)},
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
    db: AsyncSession = Depends(get_jobs_db),
) -> Response:
    """Terminate/abort a TUS upload."""
    if tus_resumable != TUS_VERSION:
        raise HTTPException(status_code=412, detail=f"Unsupported TUS version: {tus_resumable}")

    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(select(TusUpload).where(TusUpload.id == upload_id))
    tus_upload = result.scalar_one_or_none()

    if not tus_upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload_file_path = Path(tus_upload.temp_path)
    if upload_file_path.exists():
        upload_file_path.unlink()
        logger.info("Deleted TUS upload file: {}", upload_file_path)

    await db.delete(tus_upload)
    await db.commit()

    logger.info("TUS upload terminated: id={}", upload_id)

    return create_tus_response(status_code=204)


async def _complete_upload(tus_upload: TusUpload, db: AsyncSession) -> None:
    """Handle completion of a single TUS file upload.

    Called when all bytes have been received for a single file.
    Marks the file as complete and checks if all files in the batch session
    are complete. Only when ALL files are complete does it create the UploadBatch.
    """
    import shutil

    logger.info(
        "TUS file upload complete: id=%s, filename=%s, size=%d, session=%s",
        tus_upload.id, tus_upload.filename, tus_upload.file_size, tus_upload.batch_session_id,
    )

    now = datetime.now(timezone.utc)
    tus_upload.is_complete = True
    tus_upload.completed_at = now
    await db.flush()

    # Check how many files in this batch session are complete
    # Use FOR UPDATE lock to prevent race condition
    result = await db.execute(
        select(TusUpload)
        .where(TusUpload.batch_session_id == tus_upload.batch_session_id)
        .with_for_update()
    )
    session_uploads = result.scalars().all()

    completed_count = sum(1 for u in session_uploads if u.is_complete)
    expected_count = tus_upload.expected_files

    logger.info(
        "Batch session %s: %d/%d files complete",
        tus_upload.batch_session_id, completed_count, expected_count,
    )

    if completed_count < expected_count:
        await db.commit()
        return

    # Check if batch session was already processed (race condition guard)
    existing_upload_id = next(
        (u.upload_id for u in session_uploads if u.upload_id is not None),
        None
    )
    if existing_upload_id:
        logger.info(
            "Batch session %s already processed (upload_id=%s), skipping",
            tus_upload.batch_session_id, existing_upload_id,
        )
        tus_upload.upload_id = existing_upload_id
        await db.commit()
        return

    logger.info(
        "All %d files complete for batch session %s. Creating UploadBatch...",
        expected_count, tus_upload.batch_session_id,
    )

    # Generate a single upload ID for the entire batch
    upload_id = await upload_tracker.generate_upload_id(db)

    # Move the CSV to data_ingested/controls/{upload_id}.csv
    csv_dest = storage.get_control_csv_path(upload_id)
    csv_dest.parent.mkdir(parents=True, exist_ok=True)

    for upload in session_uploads:
        temp_file_path = Path(upload.temp_path)
        try:
            if temp_file_path.exists():
                shutil.move(str(temp_file_path), str(csv_dest))
                logger.info("Moved TUS file to: {}", csv_dest)
            upload.upload_id = upload_id
        except Exception:
            logger.exception("Failed to move TUS upload file: {}", upload.filename)
            raise

    batch = UploadBatch(
        upload_id=upload_id,
        data_type=tus_upload.data_type,
        status="pending",
        source_path=str(csv_dest),
        uploaded_by=tus_upload.uploaded_by,
        file_count=expected_count,
        created_at=now,
    )
    db.add(batch)
    await db.flush()

    logger.info(
        "Created UploadBatch for TUS session: upload_id=%s, batch_id=%d, files=%d",
        upload_id, batch.id, expected_count,
    )

    if tus_upload.data_type == "controls":
        await _process_controls_upload(db, batch, upload_id)
    else:
        logger.error(
            "Data type %s is not supported - Issues and Actions are disabled (In Development)",
            tus_upload.data_type
        )
        batch.status = "failed"
        batch.error_code = "unsupported_data_type"
        batch.error_details = f"Data type '{tus_upload.data_type}' is not supported. Only 'controls' uploads are currently enabled."
        batch.completed_at = datetime.now(timezone.utc)
        await db.flush()

    await db.commit()


async def _process_controls_upload(db: AsyncSession, batch: UploadBatch, upload_id: str) -> None:
    """Process controls upload: generate mock JSONL and validate."""
    from ..upload.mock_generator import generate_mock_jsonl

    try:
        batch.status = "validating"
        batch.started_at = datetime.now(timezone.utc)
        await db.flush()

        jsonl_path = storage.get_control_jsonl_path(upload_id)

        logger.info("Generating mock JSONL for upload {}", upload_id)
        total_records = generate_mock_jsonl(output_path=jsonl_path)

        logger.info("Validating JSONL schema for upload {}", upload_id)
        _validate_controls_jsonl(jsonl_path)

        batch.status = "validated"
        batch.total_records = total_records
        batch.completed_at = datetime.now(timezone.utc)
        await db.flush()

        logger.info(
            "Controls upload processing complete: upload_id={}, records={}",
            upload_id, total_records,
        )

    except ValueError as e:
        logger.warning("Schema validation failed for {}: {}", upload_id, e)
        batch.status = "failed"
        batch.error_code = "schema_validation_error"
        batch.error_details = str(e)
        batch.completed_at = datetime.now(timezone.utc)
        await db.flush()

    except Exception as e:
        logger.exception("Failed to process controls upload: {}", e)
        batch.status = "failed"
        batch.error_code = "unexpected_error"
        batch.error_details = str(e)
        batch.completed_at = datetime.now(timezone.utc)
        await db.flush()


def _validate_controls_jsonl(jsonl_path: Path) -> None:
    """Validate a controls JSONL file against the Pydantic schema.

    Reads the file line by line and validates each record.
    Checks for duplicate control_ids and missing parent references.

    Raises:
        ValueError: If validation fails.
    """
    import orjson
    from pydantic import TypeAdapter, ValidationError as PydanticValidationError
    from server.pipelines.controls.schema_validation import ControlRecord

    adapter = TypeAdapter(ControlRecord)
    seen: set = set()
    parents: set = set()
    n = 0

    with jsonl_path.open("rb") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            n += 1

            try:
                obj = orjson.loads(line)
            except Exception as e:
                raise ValueError(f"Invalid JSON at line {line_num}: {e}") from e

            try:
                rec = adapter.validate_python(obj)
            except PydanticValidationError as e:
                raise ValueError(f"Schema validation failed at line {line_num}: {e}") from e

            if rec.control_id in seen:
                raise ValueError(f"Duplicate control_id {rec.control_id!r} at line {line_num}")
            seen.add(rec.control_id)

            if rec.parent_control_id is not None:
                parents.add(rec.parent_control_id)

    missing_parents = sorted(parents - seen)
    if missing_parents:
        raise ValueError(f"Parent references missing controls (sample): {missing_parents[:20]}")

    logger.info("JSONL validation passed: {} records, {} unique control_ids", n, len(seen))


# ============== TUS Status Endpoint ==============

@router.get("/{upload_id}/status")
async def tus_status(
    upload_id: str,
    token: str = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_jobs_db),
) -> dict:
    """Get detailed status of a TUS upload."""
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(select(TusUpload).where(TusUpload.id == upload_id))
    tus_upload = result.scalar_one_or_none()

    if not tus_upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    progress = (tus_upload.offset / tus_upload.file_size * 100) if tus_upload.file_size > 0 else 0

    session_result = await db.execute(
        select(TusUpload).where(TusUpload.batch_session_id == tus_upload.batch_session_id)
    )
    session_uploads = session_result.scalars().all()
    completed_in_session = sum(1 for u in session_uploads if u.is_complete)

    result_dict = {
        "id": tus_upload.id,
        "upload_id": tus_upload.upload_id,
        "filename": tus_upload.filename,
        "data_type": tus_upload.data_type,
        "file_size": tus_upload.file_size,
        "offset": tus_upload.offset,
        "progress": round(progress, 2),
        "is_complete": tus_upload.is_complete,
        "uploaded_by": tus_upload.uploaded_by,
        "created_at": tus_upload.created_at.isoformat(),
        "completed_at": tus_upload.completed_at.isoformat() if tus_upload.completed_at else None,
        "expires_at": tus_upload.expires_at.isoformat() if tus_upload.expires_at else None,
        "batch_session_id": tus_upload.batch_session_id,
        "expected_files": tus_upload.expected_files,
        "completed_files_in_session": completed_in_session,
        "all_files_complete": completed_in_session >= tus_upload.expected_files,
    }

    if tus_upload.is_complete and tus_upload.upload_id:
        batch_result = await db.execute(
            select(UploadBatch).where(UploadBatch.upload_id == tus_upload.upload_id)
        )
        batch = batch_result.scalar_one_or_none()
        if batch:
            result_dict["batch_id"] = batch.id
            result_dict["batch_status"] = batch.status
            result_dict["validation_errors"] = batch.error_details if batch.error_code else None

    return result_dict
