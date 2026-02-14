"""Shared temporal query helpers for the explorer module."""

from datetime import date, datetime, timezone

from sqlalchemy import and_, or_, func, select, Column, Table


def temporal_condition(
    tx_from_col: Column,
    tx_to_col: Column,
    as_of: date,
):
    """Build temporal WHERE clause: tx_from <= as_of AND (tx_to IS NULL OR tx_to > as_of)."""
    as_of_dt = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc)
    return and_(
        tx_from_col <= as_of_dt,
        or_(tx_to_col.is_(None), tx_to_col > as_of_dt),
    )


def parse_as_of_date(date_str: str | None) -> date:
    """Parse YYYY-MM-DD string or default to today (UTC)."""
    if date_str:
        return date.fromisoformat(date_str)
    return datetime.now(timezone.utc).date()


async def find_effective_date(
    conn,
    ver_table: Table,
    requested: date,
) -> tuple[date, str | None]:
    """Check if data exists for *requested* date; if not, find closest available.

    Returns (effective_date, warning_message_or_None).
    """
    tc = temporal_condition(ver_table.c.tx_from, ver_table.c.tx_to, requested)
    cnt = (await conn.execute(select(func.count()).select_from(ver_table).where(tc))).scalar_one()
    if cnt > 0:
        return requested, None  # exact match

    # No data for that date — fall back to current data (tx_to IS NULL)
    current_cnt = (
        await conn.execute(
            select(func.count()).select_from(ver_table).where(ver_table.c.tx_to.is_(None))
        )
    ).scalar_one()
    if current_cnt == 0:
        return requested, None  # table is empty, nothing to fall back to

    today = datetime.now(timezone.utc).date()
    warning = (
        f"No data available for {requested.isoformat()}. "
        f"Showing current data ({today.isoformat()}) instead."
    )
    return today, warning
