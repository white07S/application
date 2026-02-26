"""Snapshot builder: captures aggregate dashboard metrics after each ingestion.

Called at the end of the controls ingestion pipeline to create an append-only
time-series row in the dashboard_snapshots table.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from sqlalchemy import insert, select, func

from server.config.postgres import get_engine
from server.explorer.dashboard.schema import dashboard_snapshots
from server.explorer.dashboard.service import (
    _compute_attribute_distributions,
    _compute_criterion_pass_rates,
    _compute_function_breakdown,
    _compute_l1_score_distribution,
    _compute_l2_score_distribution,
    _compute_portfolio_summary,
    _compute_risk_theme_breakdown,
)
from server.logging_config import get_logger

logger = get_logger(name=__name__)


async def capture_dashboard_snapshot(
    upload_id: str | None = None,
    snapshot_type: str = "ingestion",
) -> int:
    """Compute global aggregates and insert one row into dashboard_snapshots.

    Returns the snapshot_id of the newly created row.
    """
    start = time.monotonic()
    engine = get_engine()

    async with engine.connect() as conn:
        # Run all aggregate queries in parallel (no filters = global snapshot)
        (
            summary,
            l1_dist,
            l2_dist,
            criteria,
            attr_dists,
            funcs,
            themes,
        ) = await asyncio.gather(
            _compute_portfolio_summary(conn),
            _compute_l1_score_distribution(conn),
            _compute_l2_score_distribution(conn),
            _compute_criterion_pass_rates(conn),
            _compute_attribute_distributions(conn),
            _compute_function_breakdown(conn),
            _compute_risk_theme_breakdown(conn),
        )

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Build criterion pass rates dict
        criterion_rates = {c.criterion: c.pass_rate for c in criteria}

        # Build attribute distribution dicts
        prev_det = {}
        manual_auto = {}
        exec_freq = {}
        for ad in attr_dists:
            if ad.field == "preventative_detective":
                prev_det = ad.values
            elif ad.field == "manual_automated":
                manual_auto = ad.values
            elif ad.field == "execution_frequency":
                exec_freq = ad.values

        # Build function/theme breakdown lists
        func_list = [
            {"node_id": f.node_id, "name": f.name, "control_count": f.control_count}
            for f in funcs
        ]
        theme_list = [
            {"theme_id": t.theme_id, "name": t.name, "control_count": t.control_count}
            for t in themes
        ]

        # Count full marks and zero scores
        full_marks_l1 = l1_dist.distribution.get("7", 0)
        full_marks_l2 = l2_dist.distribution.get("14", 0)
        zero_l1 = l1_dist.distribution.get("0", 0)
        zero_l2 = l2_dist.distribution.get("0", 0)

        row = {
            "snapshot_at": datetime.now(timezone.utc),
            "upload_id": upload_id,
            "snapshot_type": snapshot_type,
            "total_controls": summary.total_controls,
            "total_l1": summary.total_l1,
            "total_l2": summary.total_l2,
            "active_controls": summary.active_controls,
            "inactive_controls": summary.inactive_controls,
            "key_controls": summary.key_controls,
            "avg_l1_score": l1_dist.avg_score,
            "avg_l2_score": l2_dist.avg_score,
            "median_l1_score": l1_dist.median_score,
            "median_l2_score": l2_dist.median_score,
            "controls_scoring_full_marks": full_marks_l1 + full_marks_l2,
            "controls_scoring_zero": zero_l1 + zero_l2,
            "l1_score_distribution": l1_dist.distribution,
            "l2_score_distribution": l2_dist.distribution,
            "criterion_pass_rates": criterion_rates,
            "preventative_detective_dist": prev_det,
            "manual_automated_dist": manual_auto,
            "execution_frequency_dist": exec_freq,
            "sox_relevant_count": summary.sox_relevant,
            "ccar_relevant_count": summary.ccar_relevant,
            "bcbs239_relevant_count": summary.bcbs239_relevant,
            "function_breakdown": func_list,
            "risk_theme_breakdown": theme_list,
            "computation_ms": elapsed_ms,
        }

        result = await conn.execute(
            insert(dashboard_snapshots).values(row).returning(dashboard_snapshots.c.snapshot_id)
        )
        await conn.commit()
        snapshot_id = result.scalar_one()

    total_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "Dashboard snapshot captured: snapshot_id={}, upload_id={}, computation_ms={}",
        snapshot_id, upload_id, total_ms,
    )
    return snapshot_id


async def seed_initial_snapshot() -> None:
    """Create the first dashboard snapshot if none exists yet.

    Called during server startup so trends have data from day one.
    Skips silently if snapshots already exist.
    """
    engine = get_engine()
    async with engine.connect() as conn:
        count = await conn.scalar(
            select(func.count()).select_from(dashboard_snapshots)
        )
    if count and count > 0:
        logger.info("Dashboard snapshots already exist ({}), skipping seed", count)
        return
    logger.info("No dashboard snapshots found — seeding initial snapshot...")
    await capture_dashboard_snapshot(snapshot_type="manual")
