"""API endpoints for template-based exports."""

from datetime import date, datetime, time, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.config.postgres import get_db_session
from server.logging_config import get_logger

from ..export.registry import list_templates
from ..export.service import run_export

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/export", tags=["Export"])


# ── Request / Response models ──────────────────────────────────────

class ExportRequest(BaseModel):
    template_name: str
    evaluation_date: date


class TemplateInfo(BaseModel):
    name: str
    description: str


class TemplatesResponse(BaseModel):
    templates: list[TemplateInfo]


# ── Endpoints ──────────────────────────────────────────────────────

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


@router.post("/run")
async def run_template_export(
    request: ExportRequest,
    token: str = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_db_session),
):
    """Run an export template and return the Excel file for download."""
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="No export access")

    evaluation_dt = datetime.combine(
        request.evaluation_date, time.max, tzinfo=timezone.utc
    )

    try:
        xlsx_bytes, filename = await run_export(request.template_name, evaluation_dt, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Export failed unexpectedly for template '{}'", request.template_name)
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {type(exc).__name__}: {exc}",
        )

    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
