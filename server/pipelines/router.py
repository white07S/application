from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.logging_config import get_logger

from .models import IngestResponse, IngestionHistoryResponse
from . import service

logger = get_logger(name=__name__)

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_files(
    data_type: Literal["issues", "controls", "actions"] = Form(...),
    files: List[UploadFile] = File(...),
    token: str = Depends(get_token_from_header),
):
    """
    Ingest data files for processing.

    - **data_type**: Type of data being ingested (issues, controls, or actions)
    - **files**: Files to upload
        - issues: exactly 4 xlsx files, each >= 5KB
        - controls: exactly 1 xlsx file, >= 5KB
        - actions: exactly 1 xlsx file, >= 5KB
    """
    # Check authentication and authorization
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        logger.warning("User %s denied access to pipelines ingestion", access.user)
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access pipelines ingestion",
        )

    logger.info(
        "Ingestion request from user %s: data_type=%s, files=%d",
        access.user,
        data_type,
        len(files),
    )

    # Process ingestion
    result = await service.ingest_files(files, data_type, access.user)

    return IngestResponse(**result)


@router.get("/history", response_model=IngestionHistoryResponse)
async def get_ingestion_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    token: str = Depends(get_token_from_header),
):
    """
    Get ingestion history records.

    - **limit**: Maximum number of records to return (1-100, default 50)
    - **offset**: Number of records to skip (default 0)
    """
    # Check authentication and authorization
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        logger.warning("User %s denied access to pipelines ingestion history", access.user)
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access pipelines ingestion",
        )

    result = service.get_ingestion_history(limit=limit, offset=offset)
    return IngestionHistoryResponse(**result)
