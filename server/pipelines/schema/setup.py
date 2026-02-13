"""PostgreSQL schema verification functions.

DDL is managed by Alembic — this module only provides runtime checks:
- verify_context_providers_loaded: ensure orgs + risk themes have data
- check_alembic_current: ensure migrations are at head
"""

import os
from pathlib import Path

from sqlalchemy import select, func, text

from server.config.postgres import get_engine
from server.logging_config import get_logger

logger = get_logger(name=__name__)

# Resolve server/ directory (this file is at server/pipelines/schema/setup.py)
_SERVER_DIR = Path(__file__).resolve().parent.parent.parent


async def check_alembic_current() -> None:
    """Verify that the database is at the latest Alembic migration head.

    Raises:
        RuntimeError: If the alembic_version table is missing or not at head.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_SERVER_DIR / "alembic.ini"))
    # Override script_location to absolute path so it works from any cwd
    cfg.set_main_option("script_location", str(_SERVER_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    expected_head = script.get_current_head()

    engine = get_engine()
    async with engine.connect() as conn:
        try:
            result = await conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            row = result.first()
        except Exception:
            raise RuntimeError(
                "alembic_version table not found. Run 'alembic upgrade head' first."
            )

    if row is None:
        raise RuntimeError(
            "No Alembic version found. Run 'alembic upgrade head' first."
        )

    current = row[0]
    if current != expected_head:
        raise RuntimeError(
            f"Database is at Alembic revision {current!r}, but head is {expected_head!r}. "
            f"Run 'alembic upgrade head'."
        )

    logger.info("Alembic migration is current (revision {})", current)


async def verify_context_providers_loaded() -> None:
    """Verify that context provider tables (orgs + risk themes) have data.

    Raises:
        SystemExit: If orgs or risk themes tables are empty.
    """
    from server.pipelines.orgs.schema import src_orgs_ref_node
    from server.pipelines.risks.schema import src_risks_ref_theme

    logger.info("Verifying context providers are loaded...")

    engine = get_engine()
    async with engine.connect() as conn:
        org_result = await conn.execute(
            select(func.count()).select_from(src_orgs_ref_node)
        )
        org_count = org_result.scalar_one()

        theme_result = await conn.execute(
            select(func.count()).select_from(src_risks_ref_theme)
        )
        theme_count = theme_result.scalar_one()

    if org_count == 0 or theme_count == 0:
        missing = []
        if org_count == 0:
            missing.append("org charts (src_orgs_ref_node is empty)")
        if theme_count == 0:
            missing.append("risk themes (src_risks_ref_theme is empty)")

        error_msg = (
            "Context providers not loaded: {}. "
            "Run the context provider ingestion script before starting the server:\n"
            "  python -m server.scripts.ingest_context_providers --context-providers-path <path>"
        ).format(", ".join(missing))
        logger.error(error_msg)
        raise SystemExit(error_msg)

    logger.info(
        "Context providers verified: {} org nodes, {} risk themes",
        org_count,
        theme_count,
    )
