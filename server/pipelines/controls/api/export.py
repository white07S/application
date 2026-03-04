"""API endpoints for template-based exports (Celery-backed)."""

import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.logging_config import get_logger
from server.settings import get_settings
from server.workers.celery_app import celery_app

from ..export.registry import list_templates

# Force template registration on import
import server.pipelines.controls.export.templates  # noqa: F401

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/export", tags=["Export"])


# ── Helpers ───────────────────────────────────────────────────────

def _export_path(template_name: str, date_str: str) -> Path:
    settings = get_settings()
    return settings.export_dir / template_name / f"{template_name}_{date_str}.xlsx"


def _lock_key(template_name: str, date_str: str) -> str:
    return f"export:lock:{template_name}:{date_str}"


# ── Request / Response models ────────────────────────────────────

class ExportRequest(BaseModel):
    template_name: str
    evaluation_date: date


class TemplateInfo(BaseModel):
    name: str
    description: str


class TemplatesResponse(BaseModel):
    templates: list[TemplateInfo]


class ExportStartResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ExportJobStatus(BaseModel):
    job_id: str
    status: str  # queued | running | completed | failed
    progress_percent: int
    current_step: str
    file_ready: bool
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/templates", response_model=TemplatesResponse)
async def get_available_templates(
    token: str = Depends(get_token_from_header),
):
    """List all registered export templates."""
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="No export access")

    templates = list_templates()
    return TemplatesResponse(
        templates=[TemplateInfo(**t) for t in templates]
    )


@router.post("/run", response_model=ExportStartResponse)
async def run_template_export(
    request: ExportRequest,
    token: str = Depends(get_token_from_header),
):
    """Submit an export job or return cached file info.

    - If the file already exists on disk, returns status='completed' immediately.
    - If a job is already running for this template+date, returns the existing job_id.
    - Otherwise, submits a new Celery task and returns the job_id.
    """
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="No export access")

    date_str = request.evaluation_date.strftime("%Y%m%d")
    date_iso = request.evaluation_date.isoformat()
    out_path = _export_path(request.template_name, date_str)
    lock_key = _lock_key(request.template_name, date_str)

    # 1) Cache hit — file already on disk
    if out_path.exists():
        return ExportStartResponse(
            job_id="cached",
            status="completed",
            message="Export already available for download.",
        )

    # 2) Check if a job is already running for this template+date
    from server.config.redis import get_redis_sync_client
    redis_client = get_redis_sync_client()
    existing_job = redis_client.get(lock_key)

    if existing_job:
        # Verify the task is still alive
        result = AsyncResult(existing_job, app=celery_app)
        if result.state in ('PENDING', 'PROGRESS'):
            return ExportStartResponse(
                job_id=existing_job,
                status="running",
                message="Export is already in progress.",
            )
        # Lock exists but task finished — clean up stale lock
        redis_client.delete(lock_key)

    # 3) Submit new Celery task
    from server.workers.tasks.export import run_export_task

    job_id = str(uuid.uuid4())
    run_export_task.apply_async(
        args=[request.template_name, date_iso],
        task_id=job_id,
        queue='export',
    )

    logger.info(
        "Submitted export job: job_id={}, template={}, date={}",
        job_id, request.template_name, date_iso,
    )

    return ExportStartResponse(
        job_id=job_id,
        status="queued",
        message="Export job submitted.",
    )


@router.get("/job/{job_id}", response_model=ExportJobStatus)
async def get_export_job_status(
    job_id: str,
    token: str = Depends(get_token_from_header),
):
    """Poll the status of an export job."""
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="No export access")

    result = AsyncResult(job_id, app=celery_app)

    try:
        task_state = result.state
    except (ValueError, KeyError, TypeError):
        return ExportJobStatus(
            job_id=job_id,
            status='failed',
            progress_percent=0,
            current_step='Task result corrupted',
            file_ready=False,
            error_message='Task result was corrupted. Please retry.',
        )

    if task_state == 'PENDING':
        return ExportJobStatus(
            job_id=job_id,
            status='queued',
            progress_percent=0,
            current_step='Waiting to start...',
            file_ready=False,
        )

    if task_state == 'PROGRESS':
        info = result.info or {}
        return ExportJobStatus(
            job_id=job_id,
            status='running',
            progress_percent=info.get('progress_percent', 0),
            current_step=info.get('current_step', 'Processing...'),
            file_ready=False,
        )

    if task_state == 'SUCCESS':
        info = result.info or {}
        if not info.get('success', False):
            return ExportJobStatus(
                job_id=job_id,
                status='failed',
                progress_percent=100,
                current_step='Failed',
                file_ready=False,
                error_message=info.get('message', 'Unknown error'),
            )
        return ExportJobStatus(
            job_id=job_id,
            status='completed',
            progress_percent=100,
            current_step='Completed',
            file_ready=True,
            started_at=info.get('started_at'),
            completed_at=info.get('completed_at'),
        )

    if task_state == 'FAILURE':
        info = result.info or {}
        error_message = info.get('message', str(info)) if isinstance(info, dict) else str(info)
        return ExportJobStatus(
            job_id=job_id,
            status='failed',
            progress_percent=100,
            current_step='Failed',
            file_ready=False,
            error_message=error_message,
        )

    # RETRY, REVOKED, etc.
    return ExportJobStatus(
        job_id=job_id,
        status=task_state.lower(),
        progress_percent=0,
        current_step=f"Status: {task_state}",
        file_ready=False,
    )


@router.get("/download")
async def download_export(
    template_name: str,
    evaluation_date: date,
    token: str = Depends(get_token_from_header),
):
    """Download a completed export file.

    Query params:
        template_name: The export template name.
        evaluation_date: The evaluation date (YYYY-MM-DD).
    """
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="No export access")

    date_str = evaluation_date.strftime("%Y%m%d")
    out_path = _export_path(template_name, date_str)

    if not out_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found. Run the export first.")

    filename = out_path.name
    return FileResponse(
        path=out_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
