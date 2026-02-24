"""Export service — orchestrates template query + workbook generation."""

from datetime import datetime
from io import BytesIO
from typing import Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from server.logging_config import get_logger

from .registry import get_template

# Force template registration on first import
import server.pipelines.controls.export.templates  # noqa: F401

logger = get_logger(name=__name__)


async def run_export(
    template_name: str,
    evaluation_date: datetime,
    db: AsyncSession,
) -> Tuple[bytes, str]:
    """Run a named export template and return (xlsx_bytes, filename)."""
    template_cls = get_template(template_name)
    template = template_cls()

    logger.info(
        "Running export template '{}' for evaluation_date={}",
        template_name,
        evaluation_date.date(),
    )

    rows = await template.query(db, evaluation_date)
    logger.info("Template '{}' returned {} rows", template_name, len(rows))

    wb = template.build_workbook(rows, evaluation_date)

    buf = BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    filename = f"{template_name}_{evaluation_date.strftime('%Y%m%d')}.xlsx"
    logger.info("Export '{}' generated ({} bytes)", filename, len(xlsx_bytes))
    return xlsx_bytes, filename
