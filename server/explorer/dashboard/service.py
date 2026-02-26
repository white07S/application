"""Dashboard service: aggregate SQL queries for portfolio analytics.

Provides live-computation functions for each dashboard tab, plus
trend queries that read from the pre-computed dashboard_snapshots table.
"""

from __future__ import annotations

import asyncio
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, func, or_, select, text

from server.config.postgres import get_engine
from server.explorer.dashboard.models import (
    AttributeDistribution,
    CriterionPassRate,
    DashboardFilters,
    DocQualityResponse,
    ExecutiveOverviewResponse,
    FunctionBreakdown,
    LifecycleHeatmapResponse,
    LifecycleMonthPoint,
    PortfolioAnalyticsResponse,
    PortfolioSummary,
    RegulatoryComplianceResponse,
    RiskThemeBreakdown,
    ScoreDistribution,
    ScoreTrendPoint,
    ScoreTrendResponse,
    SnapshotTrendPoint,
    TrendResponse,
)
from server.explorer.dashboard.schema import dashboard_snapshots
from server.logging_config import get_logger
from server.pipelines.controls.schema import (
    ai_controls_model_enrichment as enr,
    src_controls_rel_owns_function as rel_owns_func,
    src_controls_rel_parent as rel_parent,
    src_controls_rel_risk_theme as rel_risk_theme,
    src_controls_ver_control as vc,
)
from server.pipelines.orgs.schema import src_orgs_ver_function as ver_func
from server.pipelines.risks.schema import (
    src_risks_ref_theme as ref_theme,
    src_risks_ver_theme as ver_theme,
)

logger = get_logger(name=__name__)

# ── Constants ─────────────────────────────────────────────────────────────

_L1_YES_NO_COLS = [
    "what_yes_no", "where_yes_no", "who_yes_no", "when_yes_no",
    "why_yes_no", "what_why_yes_no", "risk_theme_yes_no",
]

_L2_YES_NO_COLS = [
    "frequency_yes_no", "preventative_detective_yes_no",
    "automation_level_yes_no", "followup_yes_no",
    "escalation_yes_no", "evidence_yes_no", "abbreviations_yes_no",
]

_ALL_YES_NO_COLS = _L1_YES_NO_COLS + _L2_YES_NO_COLS

_CRITERION_LABELS = {
    "what_yes_no": "What",
    "where_yes_no": "Where",
    "who_yes_no": "Who",
    "when_yes_no": "When",
    "why_yes_no": "Why",
    "what_why_yes_no": "What/Why Linkage",
    "risk_theme_yes_no": "Risk Theme",
    "frequency_yes_no": "Frequency",
    "preventative_detective_yes_no": "Prev/Detective",
    "automation_level_yes_no": "Automation Level",
    "followup_yes_no": "Follow-up",
    "escalation_yes_no": "Escalation",
    "evidence_yes_no": "Evidence",
    "abbreviations_yes_no": "Abbreviations",
}

_BATCH_SIZE = 30_000


def _is_current(col):
    return col.is_(None)


def _active_key_only(table=vc):
    """Base filter: only Active key controls for dashboard calculations."""
    return and_(table.c.control_status == "Active", table.c.key_control.is_(True))


def _score_expr(columns: list[str], table=enr):
    """Build a SQL expression that sums 'Yes' counts across given columns."""
    parts = []
    for col_name in columns:
        parts.append(
            case(
                (func.lower(getattr(table, col_name)) == "yes", 1),
                else_=0,
            )
        )
    return sum(parts[1:], parts[0])


# ── Sidebar filter resolution (reused from explorer controls service) ────


async def _resolve_candidates(
    conn, filters: DashboardFilters,
) -> set[str] | None:
    """Resolve DashboardFilters into a set of control_ids, or None if no filters."""
    if not filters.has_any:
        return None

    # Lazy import to avoid circular dependency
    from server.explorer.controls.service import (
        _controls_by_aus,
        _controls_by_ces,
        _controls_by_org_nodes,
        _controls_by_risk_themes,
    )

    scope = filters.relationship_scope
    category_sets: list[set[str]] = []

    if filters.functions:
        ids = await _controls_by_org_nodes(conn, filters.functions, "function", scope)
        category_sets.append(ids)

    if filters.locations:
        ids = await _controls_by_org_nodes(conn, filters.locations, "location", scope)
        category_sets.append(ids)

    if filters.assessment_units:
        ids = await _controls_by_aus(conn, filters.assessment_units, scope)
        category_sets.append(ids)

    if filters.consolidated_entities:
        ids = await _controls_by_ces(conn, filters.consolidated_entities, scope)
        category_sets.append(ids)

    if filters.risk_themes:
        ids = await _controls_by_risk_themes(conn, filters.risk_themes)
        category_sets.append(ids)

    if not category_sets:
        return None

    if filters.filter_logic == "and":
        result = category_sets[0]
        for s in category_sets[1:]:
            result = result & s
    else:
        result: set[str] = set()
        for s in category_sets:
            result = result | s

    return result


def _apply_candidate_filter(query, col, candidates: set[str] | None):
    """Add WHERE col IN (candidates) if candidates is not None."""
    if candidates is None:
        return query
    id_list = list(candidates)
    if len(id_list) <= _BATCH_SIZE:
        return query.where(col.in_(id_list))
    # For very large sets, use ANY(array) which avoids parameter limit
    return query.where(col.in_(id_list))


# ── Core Query Functions ──────────────────────────────────────────────────


async def _compute_portfolio_summary(
    conn, candidates: set[str] | None = None,
) -> PortfolioSummary:
    q = select(
        func.count().label("total_controls"),
        func.count().filter(vc.c.hierarchy_level == "Level 1").label("total_l1"),
        func.count().filter(vc.c.hierarchy_level == "Level 2").label("total_l2"),
        func.count().filter(vc.c.control_status == "Active").label("active_controls"),
        func.count().filter(
            or_(vc.c.control_status != "Active", vc.c.control_status.is_(None))
        ).label("inactive_controls"),
        func.count().filter(vc.c.key_control.is_(True)).label("key_controls"),
        func.count().filter(vc.c.sox_relevant.is_(True)).label("sox_relevant"),
        func.count().filter(vc.c.ccar_relevant.is_(True)).label("ccar_relevant"),
        func.count().filter(vc.c.bcbs239_relevant.is_(True)).label("bcbs239_relevant"),
    ).where(_is_current(vc.c.tx_to)).where(_active_key_only())

    q = _apply_candidate_filter(q, vc.c.ref_control_id, candidates)
    row = (await conn.execute(q)).mappings().one()
    return PortfolioSummary(**row)


async def _compute_l1_score_distribution(
    conn, candidates: set[str] | None = None,
) -> ScoreDistribution:
    """Score histogram for Level 1 controls (7 L1 criteria)."""
    score_cols = []
    for col_name in _L1_YES_NO_COLS:
        score_cols.append(
            case((func.lower(getattr(enr.c, col_name)) == "yes", 1), else_=0)
        )
    score_sum = sum(score_cols[1:], score_cols[0])

    q = (
        select(enr.c.ref_control_id, score_sum.label("score"))
        .select_from(
            enr.join(vc, and_(
                vc.c.ref_control_id == enr.c.ref_control_id,
                _is_current(vc.c.tx_to),
            ))
        )
        .where(_is_current(enr.c.tx_to))
        .where(vc.c.hierarchy_level == "Level 1")
        .where(_active_key_only())
    )
    q = _apply_candidate_filter(q, enr.c.ref_control_id, candidates)

    rows = (await conn.execute(q)).fetchall()
    scores = [r[1] for r in rows]
    return _build_score_distribution(scores, max_score=7)


async def _compute_l2_score_distribution(
    conn, candidates: set[str] | None = None,
) -> ScoreDistribution:
    """Score histogram for Level 2 controls (own 7 + inherited parent 7 = 14)."""
    # L2 own score
    l2_score_cols = []
    for col_name in _L2_YES_NO_COLS:
        l2_score_cols.append(
            case((func.lower(getattr(enr.c, col_name)) == "yes", 1), else_=0)
        )
    own_score = sum(l2_score_cols[1:], l2_score_cols[0])

    q_own = (
        select(enr.c.ref_control_id, own_score.label("own_score"))
        .select_from(
            enr.join(vc, and_(
                vc.c.ref_control_id == enr.c.ref_control_id,
                _is_current(vc.c.tx_to),
            ))
        )
        .where(_is_current(enr.c.tx_to))
        .where(vc.c.hierarchy_level == "Level 2")
        .where(_active_key_only())
    )
    q_own = _apply_candidate_filter(q_own, enr.c.ref_control_id, candidates)

    # Parent L1 scores
    parent_enr = enr.alias("parent_enr")
    l1_score_cols = []
    for col_name in _L1_YES_NO_COLS:
        l1_score_cols.append(
            case((func.lower(getattr(parent_enr.c, col_name)) == "yes", 1), else_=0)
        )
    parent_score = sum(l1_score_cols[1:], l1_score_cols[0])

    q_parent = (
        select(
            rel_parent.c.child_control_id,
            parent_score.label("parent_score"),
        )
        .select_from(
            rel_parent.join(parent_enr, and_(
                parent_enr.c.ref_control_id == rel_parent.c.parent_control_id,
                _is_current(parent_enr.c.tx_to),
            ))
        )
        .where(_is_current(rel_parent.c.tx_to))
    )

    own_rows, parent_rows = await asyncio.gather(
        conn.execute(q_own),
        conn.execute(q_parent),
    )

    parent_map: dict[str, int] = {}
    for r in parent_rows.fetchall():
        parent_map[r[0]] = r[1]

    scores = []
    for r in own_rows.fetchall():
        control_id, own = r[0], r[1]
        total = own + parent_map.get(control_id, 0)
        scores.append(total)

    return _build_score_distribution(scores, max_score=14)


def _build_score_distribution(scores: list[int], max_score: int) -> ScoreDistribution:
    dist: dict[str, int] = {str(i): 0 for i in range(max_score + 1)}
    for s in scores:
        key = str(min(s, max_score))
        dist[key] = dist.get(key, 0) + 1

    avg = round(statistics.mean(scores), 2) if scores else None
    med = round(statistics.median(scores), 2) if scores else None

    return ScoreDistribution(
        distribution=dist,
        avg_score=avg,
        median_score=med,
        total_assessed=len(scores),
    )


async def _compute_criterion_pass_rates(
    conn, candidates: set[str] | None = None,
) -> list[CriterionPassRate]:
    cols_to_select = [enr.c.ref_control_id]
    for col_name in _ALL_YES_NO_COLS:
        cols_to_select.append(getattr(enr.c, col_name))

    q = (
        select(*cols_to_select)
        .select_from(
            enr.join(vc, and_(
                vc.c.ref_control_id == enr.c.ref_control_id,
                _is_current(vc.c.tx_to),
            ))
        )
        .where(_is_current(enr.c.tx_to))
        .where(_active_key_only())
    )
    q = _apply_candidate_filter(q, enr.c.ref_control_id, candidates)

    rows = (await conn.execute(q)).mappings().all()
    total = len(rows)
    if total == 0:
        return [
            CriterionPassRate(
                criterion=c, label=_CRITERION_LABELS[c],
                pass_rate=0.0, pass_count=0, total_count=0,
            )
            for c in _ALL_YES_NO_COLS
        ]

    results = []
    for col_name in _ALL_YES_NO_COLS:
        pass_count = sum(
            1 for r in rows if (r.get(col_name) or "").lower() == "yes"
        )
        results.append(CriterionPassRate(
            criterion=col_name,
            label=_CRITERION_LABELS[col_name],
            pass_rate=round(pass_count / total, 4),
            pass_count=pass_count,
            total_count=total,
        ))
    return results


async def _compute_attribute_distributions(
    conn, candidates: set[str] | None = None,
) -> list[AttributeDistribution]:
    results = []
    for field_name in ("preventative_detective", "manual_automated", "execution_frequency"):
        col = getattr(vc.c, field_name)
        q = (
            select(col, func.count().label("cnt"))
            .where(_is_current(vc.c.tx_to))
            .where(_active_key_only())
            .group_by(col)
        )
        q = _apply_candidate_filter(q, vc.c.ref_control_id, candidates)
        rows = (await conn.execute(q)).fetchall()
        values = {(r[0] or "Unknown"): r[1] for r in rows}
        results.append(AttributeDistribution(field=field_name, values=values))
    return results


async def _compute_function_breakdown(
    conn, candidates: set[str] | None = None, limit: int = 20,
) -> list[FunctionBreakdown]:
    q = (
        select(
            ver_func.c.ref_node_id.label("node_id"),
            ver_func.c.name,
            func.count(func.distinct(rel_owns_func.c.control_id)).label("control_count"),
        )
        .select_from(
            ver_func
            .join(rel_owns_func, and_(
                rel_owns_func.c.node_id == ver_func.c.ref_node_id,
                _is_current(rel_owns_func.c.tx_to),
            ))
            .join(vc, and_(
                vc.c.ref_control_id == rel_owns_func.c.control_id,
                _is_current(vc.c.tx_to),
            ))
        )
        .where(_is_current(ver_func.c.tx_to))
        .where(_active_key_only())
        .group_by(ver_func.c.ref_node_id, ver_func.c.name)
        .order_by(func.count(func.distinct(rel_owns_func.c.control_id)).desc())
        .limit(limit)
    )
    if candidates is not None:
        q = q.where(rel_owns_func.c.control_id.in_(list(candidates)))

    rows = (await conn.execute(q)).mappings().all()
    return [FunctionBreakdown(node_id=r["node_id"], name=r["name"], control_count=r["control_count"]) for r in rows]


async def _compute_risk_theme_breakdown(
    conn, candidates: set[str] | None = None, limit: int = 20,
) -> list[RiskThemeBreakdown]:
    q = (
        select(
            ref_theme.c.theme_id,
            ver_theme.c.name,
            func.count(func.distinct(rel_risk_theme.c.control_id)).label("control_count"),
        )
        .select_from(
            ref_theme
            .join(ver_theme, and_(
                ver_theme.c.ref_theme_id == ref_theme.c.theme_id,
                _is_current(ver_theme.c.tx_to),
            ))
            .join(rel_risk_theme, and_(
                rel_risk_theme.c.theme_id == ref_theme.c.theme_id,
                _is_current(rel_risk_theme.c.tx_to),
            ))
            .join(vc, and_(
                vc.c.ref_control_id == rel_risk_theme.c.control_id,
                _is_current(vc.c.tx_to),
            ))
        )
        .where(_active_key_only())
        .group_by(ref_theme.c.theme_id, ver_theme.c.name)
        .order_by(func.count(func.distinct(rel_risk_theme.c.control_id)).desc())
        .limit(limit)
    )
    if candidates is not None:
        q = q.where(rel_risk_theme.c.control_id.in_(list(candidates)))

    rows = (await conn.execute(q)).mappings().all()
    return [RiskThemeBreakdown(theme_id=r["theme_id"], name=r["name"], control_count=r["control_count"]) for r in rows]


async def _compute_controls_by_month(
    conn, date_field: str, candidates: set[str] | None = None,
) -> dict[str, int]:
    """Count controls by month based on a date column (control_created_on or last_modified_on)."""
    col = getattr(vc.c, date_field)
    month_expr = func.to_char(col, "YYYY-MM")
    q = (
        select(month_expr.label("month"), func.count().label("cnt"))
        .where(_is_current(vc.c.tx_to))
        .where(_active_key_only())
        .where(col.isnot(None))
        .group_by(month_expr)
        .order_by(month_expr)
    )
    q = _apply_candidate_filter(q, vc.c.ref_control_id, candidates)
    rows = (await conn.execute(q)).fetchall()
    return {r[0]: r[1] for r in rows}


# ── Public API Functions ──────────────────────────────────────────────────


async def _count_all_controls(conn) -> int:
    """Count all current controls regardless of status or key_control (no base filter)."""
    q = select(func.count()).select_from(vc).where(_is_current(vc.c.tx_to))
    return (await conn.execute(q)).scalar() or 0


async def compute_executive_overview(
    filters: DashboardFilters,
) -> ExecutiveOverviewResponse:
    engine = get_engine()
    async with engine.connect() as conn:
        candidates = await _resolve_candidates(conn, filters)

        summary, l1_dist, l2_dist, criteria, attr_dists, funcs, themes, total_all = (
            await asyncio.gather(
                _compute_portfolio_summary(conn, candidates),
                _compute_l1_score_distribution(conn, candidates),
                _compute_l2_score_distribution(conn, candidates),
                _compute_criterion_pass_rates(conn, candidates),
                _compute_attribute_distributions(conn, candidates),
                _compute_function_breakdown(conn, candidates),
                _compute_risk_theme_breakdown(conn, candidates),
                _count_all_controls(conn),
            )
        )

    return ExecutiveOverviewResponse(
        summary=summary,
        total_all_controls=total_all,
        l1_score_dist=l1_dist,
        l2_score_dist=l2_dist,
        criterion_pass_rates=criteria,
        attribute_distributions=attr_dists,
        top_functions=funcs,
        top_risk_themes=themes,
    )


async def compute_doc_quality(
    filters: DashboardFilters,
) -> DocQualityResponse:
    engine = get_engine()
    async with engine.connect() as conn:
        candidates = await _resolve_candidates(conn, filters)

        l1_dist, l2_dist, criteria, funcs = await asyncio.gather(
            _compute_l1_score_distribution(conn, candidates),
            _compute_l2_score_distribution(conn, candidates),
            _compute_criterion_pass_rates(conn, candidates),
            _compute_function_breakdown(conn, candidates),
        )

    worst = sorted(criteria, key=lambda c: c.pass_rate)

    return DocQualityResponse(
        l1_score_dist=l1_dist,
        l2_score_dist=l2_dist,
        criterion_pass_rates=criteria,
        worst_criteria=worst,
        score_by_function=funcs,
    )


async def compute_portfolio_analytics(
    filters: DashboardFilters,
) -> PortfolioAnalyticsResponse:
    engine = get_engine()
    async with engine.connect() as conn:
        candidates = await _resolve_candidates(conn, filters)

        attr_dists, funcs, themes, created, modified = await asyncio.gather(
            _compute_attribute_distributions(conn, candidates),
            _compute_function_breakdown(conn, candidates),
            _compute_risk_theme_breakdown(conn, candidates),
            _compute_controls_by_month(conn, "control_created_on", candidates),
            _compute_controls_by_month(conn, "last_modified_on", candidates),
        )

    return PortfolioAnalyticsResponse(
        attribute_distributions=attr_dists,
        function_breakdown=funcs,
        risk_theme_breakdown=themes,
        controls_created_by_month=created,
        controls_modified_by_month=modified,
    )


async def compute_regulatory_compliance(
    filters: DashboardFilters,
) -> RegulatoryComplianceResponse:
    engine = get_engine()
    async with engine.connect() as conn:
        candidates = await _resolve_candidates(conn, filters)

        summary = await _compute_portfolio_summary(conn, candidates)

        # SOX-specific score distribution
        sox_q = (
            select(vc.c.ref_control_id)
            .where(_is_current(vc.c.tx_to))
            .where(_active_key_only())
            .where(vc.c.sox_relevant.is_(True))
        )
        sox_q = _apply_candidate_filter(sox_q, vc.c.ref_control_id, candidates)
        sox_rows = (await conn.execute(sox_q)).fetchall()
        sox_ids = {r[0] for r in sox_rows}

        sox_dist = await _compute_l1_score_distribution(conn, sox_ids if sox_ids else set())

        # SOX by function
        sox_funcs = await _compute_function_breakdown(conn, sox_ids if sox_ids else set())

    return RegulatoryComplianceResponse(
        summary=summary,
        sox_controls=summary.sox_relevant,
        ccar_controls=summary.ccar_relevant,
        bcbs239_controls=summary.bcbs239_relevant,
        sox_by_function=sox_funcs,
        sox_score_dist=sox_dist,
    )


# ── Lifecycle Heatmap (created vs retired by month) ──────────────────────


async def compute_lifecycle_heatmap(
    filters: DashboardFilters,
    months: int = 12,
) -> LifecycleHeatmapResponse:
    """For each of the last N months, count controls created and controls retired (Expired).

    Created: control_created_on falls in that month.
    Retired: control_status = 'Expired' AND last_modified_on falls in that month.
    """
    engine = get_engine()

    async with engine.connect() as conn:
        candidates = await _resolve_candidates(conn, filters)

        # Build month boundaries
        cutoff = func.date_trunc("month", func.now() - text(f"interval '{months} months'"))

        # Created per month
        created_q = (
            select(
                func.to_char(vc.c.control_created_on, "YYYY-MM").label("month"),
                func.count().label("cnt"),
            )
            .where(_is_current(vc.c.tx_to))
            .where(_active_key_only())
            .where(vc.c.control_created_on >= cutoff)
            .group_by(text("1"))
        )
        created_q = _apply_candidate_filter(created_q, vc.c.ref_control_id, candidates)

        # Retired per month (Expired controls, keyed by last_modified_on)
        retired_q = (
            select(
                func.to_char(vc.c.last_modified_on, "YYYY-MM").label("month"),
                func.count().label("cnt"),
            )
            .where(_is_current(vc.c.tx_to))
            .where(vc.c.control_status == "Expired")
            .where(vc.c.last_modified_on >= cutoff)
            .group_by(text("1"))
        )
        retired_q = _apply_candidate_filter(retired_q, vc.c.ref_control_id, candidates)

        created_rows, retired_rows = await asyncio.gather(
            conn.execute(created_q),
            conn.execute(retired_q),
        )

    created_map: dict[str, int] = {r[0]: r[1] for r in created_rows if r[0]}
    retired_map: dict[str, int] = {r[0]: r[1] for r in retired_rows if r[0]}

    # Build ordered list of months
    from datetime import timezone
    now = datetime.now(timezone.utc)
    all_months: list[str] = []
    for i in range(months, 0, -1):
        # Subtract i months from now
        y = now.year
        m = now.month - i
        while m <= 0:
            m += 12
            y -= 1
        all_months.append(f"{y:04d}-{m:02d}")
    # Add current month
    all_months.append(f"{now.year:04d}-{now.month:02d}")

    points = [
        LifecycleMonthPoint(
            month=mo,
            created=created_map.get(mo, 0),
            retired=retired_map.get(mo, 0),
        )
        for mo in all_months
    ]

    return LifecycleHeatmapResponse(months=points)


# ── Trend Queries (from dashboard_snapshots) ─────────────────────────────


async def get_snapshot_trends(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 50,
) -> TrendResponse:
    engine = get_engine()
    ds = dashboard_snapshots

    q = (
        select(
            ds.c.snapshot_at,
            ds.c.upload_id,
            ds.c.total_controls,
            ds.c.active_controls,
            ds.c.avg_l1_score,
            ds.c.avg_l2_score,
            ds.c.controls_scoring_full_marks,
            ds.c.controls_scoring_zero,
            ds.c.criterion_pass_rates,
        )
        .order_by(ds.c.snapshot_at.desc())
        .limit(limit)
    )
    if from_date:
        q = q.where(ds.c.snapshot_at >= from_date)
    if to_date:
        q = q.where(ds.c.snapshot_at <= to_date)

    async with engine.connect() as conn:
        rows = (await conn.execute(q)).mappings().all()

    # Count total snapshots
    count_q = select(func.count()).select_from(ds)
    async with engine.connect() as conn:
        total = (await conn.execute(count_q)).scalar() or 0

    points = [
        SnapshotTrendPoint(
            snapshot_at=r["snapshot_at"],
            upload_id=r["upload_id"],
            total_controls=r["total_controls"],
            active_controls=r["active_controls"],
            avg_l1_score=r["avg_l1_score"],
            avg_l2_score=r["avg_l2_score"],
            controls_scoring_full_marks=r["controls_scoring_full_marks"],
            controls_scoring_zero=r["controls_scoring_zero"],
            criterion_pass_rates=r["criterion_pass_rates"] or {},
        )
        for r in reversed(rows)  # chronological order
    ]

    return TrendResponse(points=points, total_snapshots=total)


async def get_score_trends(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 50,
) -> ScoreTrendResponse:
    engine = get_engine()
    ds = dashboard_snapshots

    q = (
        select(
            ds.c.snapshot_at,
            ds.c.l1_score_distribution,
            ds.c.l2_score_distribution,
            ds.c.avg_l1_score,
            ds.c.avg_l2_score,
        )
        .order_by(ds.c.snapshot_at.desc())
        .limit(limit)
    )
    if from_date:
        q = q.where(ds.c.snapshot_at >= from_date)
    if to_date:
        q = q.where(ds.c.snapshot_at <= to_date)

    async with engine.connect() as conn:
        rows = (await conn.execute(q)).mappings().all()

    l1_trend = []
    l2_trend = []
    for r in reversed(rows):
        l1_trend.append(ScoreTrendPoint(
            snapshot_at=r["snapshot_at"],
            distribution=r["l1_score_distribution"] or {},
            avg_score=r["avg_l1_score"],
        ))
        l2_trend.append(ScoreTrendPoint(
            snapshot_at=r["snapshot_at"],
            distribution=r["l2_score_distribution"] or {},
            avg_score=r["avg_l2_score"],
        ))

    return ScoreTrendResponse(l1_trend=l1_trend, l2_trend=l2_trend)
