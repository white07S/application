"""Ingest org charts and risk themes into PostgreSQL.

Standalone CLI script for loading context-provider data (organization
hierarchies and risk-theme taxonomies) from date-partitioned JSONL files.

Supports delta detection: compares file contents against the current DB
state and creates / closes / updates version records accordingly.

Usage:
    python -m server.scripts.ingest_context_providers

Reads CONTEXT_PROVIDERS_PATH from .env by default. Override with --context-providers-path.

Directory layout expected under *context_providers_path*::

    organization/
      2026-02-11/
        functions.jsonl
        locations.jsonl
        consolidated.jsonl
    risk_theme/
      2026-02-11/
        risk_theme.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import orjson
from sqlalchemy import insert, update, select, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

# ---------------------------------------------------------------------------
# Logging – configure early so every import below gets the right level
# ---------------------------------------------------------------------------
from server.logging_config import configure_logging, get_logger

logger = get_logger(name=__name__)

# ---------------------------------------------------------------------------
# PostgreSQL config + schema table objects
# ---------------------------------------------------------------------------
from server.config.postgres import init_engine, get_engine, dispose_engine  # noqa: E402
from server.pipelines.orgs.schema import (  # noqa: E402
    src_orgs_ref_node,
    src_orgs_ver_function,
    src_orgs_ver_location,
    src_orgs_ver_consolidated,
    src_orgs_rel_child,
)
from server.pipelines.risks.schema import (  # noqa: E402
    src_risks_ref_taxonomy,
    src_risks_ver_taxonomy,
    src_risks_ref_theme,
    src_risks_ver_theme,
    src_risks_rel_taxonomy_theme,
)
from server.settings import get_settings  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SETTINGS = get_settings()
BATCH_SIZE = _SETTINGS.postgres_write_batch_size

# Map tree name -> SQLAlchemy version table object
VER_TABLE_MAP = {
    "function": src_orgs_ver_function,
    "location": src_orgs_ver_location,
    "consolidated": src_orgs_ver_consolidated,
}

TREE_CONFIGS = {
    "function": {
        "file": "functions.jsonl",
        "id_field": "id",               # field holding the node identifier
        "ver_table": src_orgs_ver_function,
        "name_field": "name",            # field in the JSONL row
        "name_is_set": False,            # single string, not set<string>
        "status_field": "id_status",     # field name in the JSONL row
    },
    "location": {
        "file": "locations.jsonl",
        "id_field": "id",
        "ver_table": src_orgs_ver_location,
        "name_field": "location_name",
        "name_is_set": True,
        "status_field": "location_status",
    },
    "consolidated": {
        "file": "consolidated.jsonl",
        "id_field": "location_id",       # consolidated uses location_id
        "ver_table": src_orgs_ver_consolidated,
        "name_field": "location_name",
        "name_is_set": True,
        "status_field": "location_status",
    },
}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
@dataclass
class IngestionStats:
    """Accumulates per-entity-type counters."""

    new: int = 0
    changed: int = 0
    unchanged: int = 0
    disappeared: int = 0
    errors: int = 0
    error_messages: List[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors += 1
        if len(self.error_messages) < 50:
            self.error_messages.append(msg)

    def summary_line(self) -> str:
        return (
            f"new={self.new}  changed={self.changed}  "
            f"unchanged={self.unchanged}  disappeared={self.disappeared}  "
            f"errors={self.errors}"
        )


@dataclass
class AllStats:
    """Container for per-tree and per-risk stats."""

    orgs_function: IngestionStats = field(default_factory=IngestionStats)
    orgs_location: IngestionStats = field(default_factory=IngestionStats)
    orgs_consolidated: IngestionStats = field(default_factory=IngestionStats)
    risks_taxonomy: IngestionStats = field(default_factory=IngestionStats)
    risks_theme: IngestionStats = field(default_factory=IngestionStats)

    def print_summary(self) -> None:
        sections = [
            ("Orgs / function", self.orgs_function),
            ("Orgs / location", self.orgs_location),
            ("Orgs / consolidated", self.orgs_consolidated),
            ("Risks / taxonomy", self.risks_taxonomy),
            ("Risks / theme", self.risks_theme),
        ]
        print("\n" + "=" * 72)
        print("  INGESTION SUMMARY")
        print("=" * 72)
        for label, stats in sections:
            print(f"  {label:30s}  {stats.summary_line()}")
        print("=" * 72 + "\n")


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read a JSONL file using *orjson* and return a list of dicts."""
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")
    rows: List[Dict[str, Any]] = []
    with open(path, "rb") as fh:
        for lineno, raw_line in enumerate(fh, 1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(orjson.loads(line))
            except orjson.JSONDecodeError as exc:
                logger.warning("Skipping malformed line {} in {}: {}", lineno, path, exc)
    return rows


def _find_latest_date_dir(base: Path) -> Optional[Path]:
    """Return the newest *valid* YYYY-MM-DD subdirectory under *base*.

    Only considers directories whose name is a parseable date, so stray
    folders (``temp/``, ``backup/``, etc.) are silently ignored.
    """
    if not base.is_dir():
        return None
    dated: list[tuple[datetime, Path]] = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        try:
            dt = datetime.strptime(d.name, "%Y-%m-%d")
            dated.append((dt, d))
        except ValueError:
            logger.debug("Skipping non-date directory: {}", d)
    if not dated:
        return None
    dated.sort(key=lambda pair: pair[0], reverse=True)
    latest = dated[0][1]
    logger.info("Latest date directory under {}: {} (of {} found)", base.name, latest.name, len(dated))
    return latest


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------

def _node_id(tree: str, source_id: str) -> str:
    """Build the composite text PK for src_orgs_ref_node."""
    return f"{tree}:{source_id}"


def _now_iso() -> str:
    """Current UTC time in ISO-8601 with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _date_dir_to_tx_from(date_dir: Path) -> str:
    """Convert a date directory name (YYYY-MM-DD) to a tx_from ISO string."""
    return f"{date_dir.name}T00:00:00Z"


def _parse_iso(iso_str: str) -> datetime:
    """Parse an ISO-8601 datetime string to a timezone-aware datetime."""
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Normalisation helpers – make values comparable across file vs DB
# ---------------------------------------------------------------------------

def _normalise_names(raw: Any) -> Set[str]:
    """Turn a name value (str | list[str] | None) into a comparable frozenset."""
    if raw is None:
        return set()
    if isinstance(raw, list):
        return set(raw)
    return {str(raw)}


def _normalise_str(val: Any) -> Optional[str]:
    """Coerce to str or None, trimming whitespace."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


# ---------------------------------------------------------------------------
# DB helpers – fetch current versions (PostgreSQL / SQLAlchemy)
# ---------------------------------------------------------------------------

async def _get_current_org_nodes(
    engine: AsyncEngine,
    tree: str,
    ver_table,
    name_is_set: bool,
) -> Dict[str, Dict[str, Any]]:
    """Return {source_id: {name/names, status, children}} for all current nodes
    of *tree* type.  'Current' means tx_to IS NULL on the version row.
    """
    async with engine.connect() as conn:
        # Get current version rows
        if name_is_set:
            ver_query = select(
                ver_table.c.ref_node_id,
                ver_table.c.names,
                ver_table.c.status,
            ).where(ver_table.c.tx_to.is_(None))
        else:
            ver_query = select(
                ver_table.c.ref_node_id,
                ver_table.c.name,
                ver_table.c.status,
            ).where(ver_table.c.tx_to.is_(None))

        result = await conn.execute(ver_query)
        ver_rows = result.fetchall()

        # Build a map from source_id to version data
        current: Dict[str, Dict[str, Any]] = {}
        for row in ver_rows:
            ref_node_id = row.ref_node_id
            # ref_node_id looks like "function:N00000" – extract source_id
            source_id = _extract_source_id_from_node_id(ref_node_id, tree)
            if not source_id:
                continue
            if name_is_set:
                raw_names = row.names
                names = set(raw_names) if raw_names else set()
            else:
                names = {row.name} if row.name else set()
            current[source_id] = {
                "names": names,
                "status": _normalise_str(row.status),
            }

        # Get current child edges for this tree
        # Only edges where the parent belongs to *tree*
        edge_query = select(
            src_orgs_rel_child.c.in_node_id,
            src_orgs_rel_child.c.out_node_id,
        ).where(
            and_(
                src_orgs_rel_child.c.tx_to.is_(None),
                src_orgs_rel_child.c.in_node_id.like(f"{tree}:%"),
            )
        )
        edge_result = await conn.execute(edge_query)
        edge_rows = edge_result.fetchall()

        for edge in edge_rows:
            parent_sid = _extract_source_id_from_node_id(edge.in_node_id, tree)
            child_sid = _extract_source_id_from_node_id(edge.out_node_id, tree)
            if parent_sid and child_sid:
                entry = current.get(parent_sid)
                if entry is not None:
                    entry.setdefault("children", set()).add(child_sid)

        # Ensure every entry has a children key
        for entry in current.values():
            entry.setdefault("children", set())

    return current


def _extract_source_id_from_node_id(node_id: str, tree: str) -> Optional[str]:
    """Extract the source_id from a node_id string like 'function:N00000'."""
    prefix = f"{tree}:"
    if node_id.startswith(prefix):
        return node_id[len(prefix):]
    return None


async def _get_current_taxonomies(engine: AsyncEngine) -> Dict[str, Dict[str, Any]]:
    """Return {taxonomy_id: {name, description}} for current taxonomy versions."""
    async with engine.connect() as conn:
        result = await conn.execute(
            select(
                src_risks_ver_taxonomy.c.ref_taxonomy_id,
                src_risks_ver_taxonomy.c.name,
                src_risks_ver_taxonomy.c.description,
            ).where(src_risks_ver_taxonomy.c.tx_to.is_(None))
        )
        rows = result.fetchall()

    result_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        tid = row.ref_taxonomy_id
        if tid:
            result_map[tid] = {
                "name": _normalise_str(row.name),
                "description": _normalise_str(row.description),
            }
    return result_map


async def _get_current_themes(engine: AsyncEngine) -> Dict[str, Dict[str, Any]]:
    """Return {theme_source_id: {name, description, mapping_considerations, status}}."""
    async with engine.connect() as conn:
        # Join ref_theme to ver_theme to get source_id
        result = await conn.execute(
            select(
                src_risks_ref_theme.c.source_id,
                src_risks_ver_theme.c.name,
                src_risks_ver_theme.c.description,
                src_risks_ver_theme.c.mapping_considerations,
                src_risks_ver_theme.c.status,
            ).select_from(
                src_risks_ver_theme.join(
                    src_risks_ref_theme,
                    src_risks_ver_theme.c.ref_theme_id == src_risks_ref_theme.c.theme_id,
                )
            ).where(src_risks_ver_theme.c.tx_to.is_(None))
        )
        rows = result.fetchall()

    result_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        source_id = row.source_id
        if source_id:
            result_map[source_id] = {
                "name": _normalise_str(row.name),
                "description": _normalise_str(row.description),
                "mapping_considerations": _normalise_str(row.mapping_considerations),
                "status": _normalise_str(row.status),
            }
    return result_map


# ---------------------------------------------------------------------------
# Batch execution helper (PostgreSQL / SQLAlchemy)
# ---------------------------------------------------------------------------

async def _execute_batch(
    engine: AsyncEngine,
    ref_inserts: List[Dict[str, Any]],
    ver_inserts: List[Dict[str, Any]],
    edge_inserts: List[Dict[str, Any]],
    ver_close_stmts: List[Any],
    edge_close_stmts: List[Any],
    ref_table,
    ver_table,
    edge_table,
    stats: IngestionStats,
    label: str,
    dry_run: bool = False,
) -> None:
    """Execute a batch of inserts and updates within a single transaction.

    On dry_run, just log counts.
    """
    total = len(ref_inserts) + len(ver_inserts) + len(edge_inserts) + len(ver_close_stmts) + len(edge_close_stmts)
    if total == 0:
        return
    if dry_run:
        logger.info(
            "[DRY RUN] [{}] ref_inserts={}, ver_inserts={}, edge_inserts={}, "
            "ver_closes={}, edge_closes={}",
            label, len(ref_inserts), len(ver_inserts), len(edge_inserts),
            len(ver_close_stmts), len(edge_close_stmts),
        )
        return

    try:
        async with engine.begin() as conn:
            # 1. Insert ref nodes (ON CONFLICT DO NOTHING for idempotency)
            if ref_inserts:
                for batch_start in range(0, len(ref_inserts), BATCH_SIZE):
                    batch = ref_inserts[batch_start:batch_start + BATCH_SIZE]
                    stmt = pg_insert(ref_table).on_conflict_do_nothing(
                        index_elements=[ref_table.c[ref_table.primary_key.columns.keys()[0]]]
                    )
                    await conn.execute(stmt, batch)

            # 2. Close old versions (UPDATE tx_to)
            for close_stmt in ver_close_stmts:
                await conn.execute(close_stmt)

            # 3. Close old edges (UPDATE tx_to)
            for close_stmt in edge_close_stmts:
                await conn.execute(close_stmt)

            # 4. Insert new versions
            if ver_inserts:
                for batch_start in range(0, len(ver_inserts), BATCH_SIZE):
                    batch = ver_inserts[batch_start:batch_start + BATCH_SIZE]
                    await conn.execute(insert(ver_table), batch)

            # 5. Insert new edges
            if edge_inserts:
                for batch_start in range(0, len(edge_inserts), BATCH_SIZE):
                    batch = edge_inserts[batch_start:batch_start + BATCH_SIZE]
                    await conn.execute(insert(edge_table), batch)

    except Exception as exc:
        msg = f"[{label}] Batch execution failed: {exc}"
        logger.error(msg)
        stats.add_error(msg)


# ---------------------------------------------------------------------------
# Org ingestion
# ---------------------------------------------------------------------------

async def ingest_org_tree(
    engine: AsyncEngine,
    tree: str,
    date_dir: Path,
    stats: IngestionStats,
    dry_run: bool,
) -> None:
    """Ingest one org tree (function / location / consolidated)."""
    cfg = TREE_CONFIGS[tree]
    file_path = date_dir / cfg["file"]
    if not file_path.exists():
        logger.warning("File not found, skipping tree '{}': {}", tree, file_path)
        return

    tx_from = _date_dir_to_tx_from(date_dir)
    tx_from_dt = _parse_iso(tx_from)
    now = _now_iso()
    now_dt = _parse_iso(now)
    ver_table = cfg["ver_table"]

    # 1. Load file rows
    rows = load_jsonl(file_path)
    logger.info("Loaded {} rows for tree '{}'", len(rows), tree)

    # Build file-side lookup: source_id -> row data
    id_field = cfg.get("id_field", "id")
    file_nodes: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        sid = str(row.get(id_field, "")).strip()
        if not sid:
            continue
        raw_name = row.get(cfg["name_field"])
        names = _normalise_names(raw_name)
        status = _normalise_str(row.get(cfg["status_field"]))
        children = set()
        for child_id in (row.get("out_id") or []):
            child_id_str = str(child_id).strip()
            if child_id_str:
                children.add(child_id_str)
        file_nodes[sid] = {
            "names": names,
            "status": status,
            "children": children,
            "node_type": _normalise_str(row.get("id_type")),
            "raw_name": raw_name,
        }

    # 2. Load DB current state
    db_nodes = await _get_current_org_nodes(engine, tree, ver_table, cfg["name_is_set"])

    file_ids = set(file_nodes.keys())
    db_ids = set(db_nodes.keys())

    new_ids = file_ids - db_ids
    disappeared_ids = db_ids - file_ids
    common_ids = file_ids & db_ids

    logger.info(
        "Tree '{}' delta: new={}, disappeared={}, common={}",
        tree, len(new_ids), len(disappeared_ids), len(common_ids),
    )

    # ------------------------------------------------------------------
    # 3. NEW nodes
    # ------------------------------------------------------------------
    ref_inserts: List[Dict[str, Any]] = []
    ver_inserts: List[Dict[str, Any]] = []
    edge_inserts: List[Dict[str, Any]] = []

    for sid in new_ids:
        node = file_nodes[sid]
        nid = _node_id(tree, sid)

        # Ref node insert
        ref_row: Dict[str, Any] = {
            "node_id": nid,
            "tree": tree,
            "source_id": sid,
            "node_type": node["node_type"],
        }
        ref_inserts.append(ref_row)

        # Version insert
        if cfg["name_is_set"]:
            ver_row: Dict[str, Any] = {
                "ref_node_id": nid,
                "names": sorted(node["names"]),
                "status": node["status"],
                "tx_from": tx_from_dt,
                "tx_to": None,
            }
        else:
            ver_row = {
                "ref_node_id": nid,
                "name": next(iter(node["names"]), None),
                "status": node["status"],
                "tx_from": tx_from_dt,
                "tx_to": None,
            }
        ver_inserts.append(ver_row)

        # Child edges
        for child_sid in node["children"]:
            child_nid = _node_id(tree, child_sid)
            # Ensure child ref node exists too
            ref_inserts.append({
                "node_id": child_nid,
                "tree": tree,
                "source_id": child_sid,
                "node_type": None,
            })
            edge_inserts.append({
                "in_node_id": nid,
                "out_node_id": child_nid,
                "tx_from": tx_from_dt,
                "tx_to": None,
            })

        stats.new += 1

        if len(ref_inserts) + len(ver_inserts) + len(edge_inserts) >= BATCH_SIZE:
            await _execute_batch(
                engine, ref_inserts, ver_inserts, edge_inserts, [], [],
                src_orgs_ref_node, ver_table, src_orgs_rel_child,
                stats, f"new-{tree}", dry_run,
            )
            ref_inserts.clear()
            ver_inserts.clear()
            edge_inserts.clear()

    await _execute_batch(
        engine, ref_inserts, ver_inserts, edge_inserts, [], [],
        src_orgs_ref_node, ver_table, src_orgs_rel_child,
        stats, f"new-{tree}", dry_run,
    )
    ref_inserts.clear()
    ver_inserts.clear()
    edge_inserts.clear()

    # ------------------------------------------------------------------
    # 4. DISAPPEARED nodes – close current ver, create Inactive ver,
    #    close child edges
    # ------------------------------------------------------------------
    ver_close_stmts: List[Any] = []
    edge_close_stmts: List[Any] = []

    for sid in disappeared_ids:
        nid = _node_id(tree, sid)

        # Close current version
        ver_close_stmts.append(
            update(ver_table)
            .where(and_(ver_table.c.ref_node_id == nid, ver_table.c.tx_to.is_(None)))
            .values(tx_to=now_dt)
        )

        # Create new Inactive version
        if cfg["name_is_set"]:
            old_names = db_nodes[sid].get("names", set())
            ver_inserts.append({
                "ref_node_id": nid,
                "names": sorted(old_names),
                "status": "Inactive",
                "tx_from": now_dt,
                "tx_to": None,
            })
        else:
            old_name = next(iter(db_nodes[sid].get("names", set())), None)
            ver_inserts.append({
                "ref_node_id": nid,
                "name": old_name,
                "status": "Inactive",
                "tx_from": now_dt,
                "tx_to": None,
            })

        # Close child edges where this node is parent
        edge_close_stmts.append(
            update(src_orgs_rel_child)
            .where(and_(
                src_orgs_rel_child.c.in_node_id == nid,
                src_orgs_rel_child.c.tx_to.is_(None),
            ))
            .values(tx_to=now_dt)
        )
        # Close child edges where this node is child
        edge_close_stmts.append(
            update(src_orgs_rel_child)
            .where(and_(
                src_orgs_rel_child.c.out_node_id == nid,
                src_orgs_rel_child.c.tx_to.is_(None),
            ))
            .values(tx_to=now_dt)
        )

        stats.disappeared += 1

        if len(ver_inserts) + len(ver_close_stmts) + len(edge_close_stmts) >= BATCH_SIZE:
            await _execute_batch(
                engine, [], ver_inserts, [], ver_close_stmts, edge_close_stmts,
                src_orgs_ref_node, ver_table, src_orgs_rel_child,
                stats, f"disappeared-{tree}", dry_run,
            )
            ver_inserts.clear()
            ver_close_stmts.clear()
            edge_close_stmts.clear()

    await _execute_batch(
        engine, [], ver_inserts, [], ver_close_stmts, edge_close_stmts,
        src_orgs_ref_node, ver_table, src_orgs_rel_child,
        stats, f"disappeared-{tree}", dry_run,
    )
    ver_inserts.clear()
    ver_close_stmts.clear()
    edge_close_stmts.clear()

    # ------------------------------------------------------------------
    # 5. EXISTING – compare and update if changed
    # ------------------------------------------------------------------
    for sid in common_ids:
        file_node = file_nodes[sid]
        db_node = db_nodes[sid]

        file_names = file_node["names"]
        db_names = db_node.get("names", set())
        file_status = file_node["status"]
        db_status = db_node.get("status")
        file_children = file_node["children"]
        db_children = db_node.get("children", set())

        names_changed = file_names != db_names
        status_changed = file_status != db_status
        children_changed = file_children != db_children

        if not (names_changed or status_changed or children_changed):
            stats.unchanged += 1
            continue

        nid = _node_id(tree, sid)

        # Close old version
        ver_close_stmts.append(
            update(ver_table)
            .where(and_(ver_table.c.ref_node_id == nid, ver_table.c.tx_to.is_(None)))
            .values(tx_to=now_dt)
        )

        # Create new version
        if cfg["name_is_set"]:
            ver_inserts.append({
                "ref_node_id": nid,
                "names": sorted(file_names),
                "status": file_status,
                "tx_from": now_dt,
                "tx_to": None,
            })
        else:
            ver_inserts.append({
                "ref_node_id": nid,
                "name": next(iter(file_names), None),
                "status": file_status,
                "tx_from": now_dt,
                "tx_to": None,
            })

        if children_changed:
            # Close all current child edges for this parent
            edge_close_stmts.append(
                update(src_orgs_rel_child)
                .where(and_(
                    src_orgs_rel_child.c.in_node_id == nid,
                    src_orgs_rel_child.c.tx_to.is_(None),
                ))
                .values(tx_to=now_dt)
            )
            # Re-create child edges from file
            for child_sid in file_children:
                child_nid = _node_id(tree, child_sid)
                # Ensure child ref node exists
                ref_inserts.append({
                    "node_id": child_nid,
                    "tree": tree,
                    "source_id": child_sid,
                    "node_type": None,
                })
                edge_inserts.append({
                    "in_node_id": nid,
                    "out_node_id": child_nid,
                    "tx_from": now_dt,
                    "tx_to": None,
                })

        stats.changed += 1

        if len(ref_inserts) + len(ver_inserts) + len(edge_inserts) + len(ver_close_stmts) + len(edge_close_stmts) >= BATCH_SIZE:
            await _execute_batch(
                engine, ref_inserts, ver_inserts, edge_inserts,
                ver_close_stmts, edge_close_stmts,
                src_orgs_ref_node, ver_table, src_orgs_rel_child,
                stats, f"existing-{tree}", dry_run,
            )
            ref_inserts.clear()
            ver_inserts.clear()
            edge_inserts.clear()
            ver_close_stmts.clear()
            edge_close_stmts.clear()

    await _execute_batch(
        engine, ref_inserts, ver_inserts, edge_inserts,
        ver_close_stmts, edge_close_stmts,
        src_orgs_ref_node, ver_table, src_orgs_rel_child,
        stats, f"existing-{tree}", dry_run,
    )


# ---------------------------------------------------------------------------
# Risk theme ingestion
# ---------------------------------------------------------------------------

async def ingest_risk_themes(
    engine: AsyncEngine,
    date_dir: Path,
    tax_stats: IngestionStats,
    theme_stats: IngestionStats,
    dry_run: bool,
) -> None:
    """Ingest risk_theme.jsonl (denormalized: taxonomy + theme per row)."""
    file_path = date_dir / "risk_theme.jsonl"
    if not file_path.exists():
        logger.warning("risk_theme.jsonl not found: {}", file_path)
        return

    tx_from = _date_dir_to_tx_from(date_dir)
    tx_from_dt = _parse_iso(tx_from)
    now = _now_iso()
    now_dt = _parse_iso(now)

    rows = load_jsonl(file_path)
    logger.info("Loaded {} risk theme rows", len(rows))

    # De-duplicate taxonomies and themes from the denormalized file
    file_taxonomies: Dict[str, Dict[str, Any]] = {}
    file_themes: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        tid = str(row.get("taxonomy_id", "")).strip()
        if tid:
            file_taxonomies[tid] = {
                "name": _normalise_str(row.get("taxonomy")),
                "description": _normalise_str(row.get("taxonomy_description")),
            }
        theme_id = str(row.get("risk_theme_id", "")).strip()
        if theme_id:
            file_themes[theme_id] = {
                "taxonomy_id": tid,
                "name": _normalise_str(row.get("risk_theme")),
                "description": _normalise_str(row.get("risk_theme_description")),
                "mapping_considerations": _normalise_str(row.get("risk_theme_mapping_considerations")),
                "status": _normalise_str(row.get("status")),
            }

    # Load DB current state
    db_taxonomies = await _get_current_taxonomies(engine)
    db_themes = await _get_current_themes(engine)

    # ------------------------------------------------------------------
    # Taxonomies
    # ------------------------------------------------------------------
    file_tax_ids = set(file_taxonomies.keys())
    db_tax_ids = set(db_taxonomies.keys())
    new_tax_ids = file_tax_ids - db_tax_ids
    common_tax_ids = file_tax_ids & db_tax_ids

    ref_inserts: List[Dict[str, Any]] = []
    ver_inserts: List[Dict[str, Any]] = []
    ver_close_stmts: List[Any] = []

    # New taxonomies
    for tid in new_tax_ids:
        tax = file_taxonomies[tid]
        ref_inserts.append({
            "taxonomy_id": tid,
        })
        ver_inserts.append({
            "ref_taxonomy_id": tid,
            "name": tax["name"],
            "description": tax["description"],
            "tx_from": tx_from_dt,
            "tx_to": None,
        })
        tax_stats.new += 1

    # Existing taxonomies – compare
    for tid in common_tax_ids:
        file_tax = file_taxonomies[tid]
        db_tax = db_taxonomies[tid]
        if file_tax["name"] == db_tax["name"] and file_tax["description"] == db_tax["description"]:
            tax_stats.unchanged += 1
            continue

        ver_close_stmts.append(
            update(src_risks_ver_taxonomy)
            .where(and_(
                src_risks_ver_taxonomy.c.ref_taxonomy_id == tid,
                src_risks_ver_taxonomy.c.tx_to.is_(None),
            ))
            .values(tx_to=now_dt)
        )
        ver_inserts.append({
            "ref_taxonomy_id": tid,
            "name": file_tax["name"],
            "description": file_tax["description"],
            "tx_from": now_dt,
            "tx_to": None,
        })
        tax_stats.changed += 1

    # Execute taxonomy batch
    if ref_inserts or ver_inserts or ver_close_stmts:
        if dry_run:
            logger.info(
                "[DRY RUN] [taxonomy] ref_inserts={}, ver_inserts={}, ver_closes={}",
                len(ref_inserts), len(ver_inserts), len(ver_close_stmts),
            )
        else:
            try:
                async with engine.begin() as conn:
                    if ref_inserts:
                        stmt = pg_insert(src_risks_ref_taxonomy).on_conflict_do_nothing(
                            index_elements=["taxonomy_id"]
                        )
                        await conn.execute(stmt, ref_inserts)
                    for close_stmt in ver_close_stmts:
                        await conn.execute(close_stmt)
                    if ver_inserts:
                        await conn.execute(insert(src_risks_ver_taxonomy), ver_inserts)
            except Exception as exc:
                msg = f"[taxonomy] Batch execution failed: {exc}"
                logger.error(msg)
                tax_stats.add_error(msg)

    ref_inserts.clear()
    ver_inserts.clear()
    ver_close_stmts.clear()

    # ------------------------------------------------------------------
    # Themes
    # ------------------------------------------------------------------
    file_theme_ids = set(file_themes.keys())
    db_theme_ids = set(db_themes.keys())
    new_theme_ids = file_theme_ids - db_theme_ids
    common_theme_ids = file_theme_ids & db_theme_ids

    theme_ref_inserts: List[Dict[str, Any]] = []
    theme_ver_inserts: List[Dict[str, Any]] = []
    theme_rel_inserts: List[Dict[str, Any]] = []
    theme_ver_close_stmts: List[Any] = []

    # New themes
    for theme_id in new_theme_ids:
        theme = file_themes[theme_id]
        theme_ref_inserts.append({
            "theme_id": theme_id,
            "source_id": theme_id,
        })
        theme_ver_inserts.append({
            "ref_theme_id": theme_id,
            "name": theme["name"],
            "description": theme["description"],
            "mapping_considerations": theme["mapping_considerations"],
            "status": theme["status"],
            "tx_from": tx_from_dt,
            "tx_to": None,
        })
        # Taxonomy -> Theme relationship
        if theme.get("taxonomy_id"):
            theme_rel_inserts.append({
                "taxonomy_id": theme["taxonomy_id"],
                "theme_id": theme_id,
            })
        theme_stats.new += 1

    # Existing themes – compare
    for theme_id in common_theme_ids:
        file_theme = file_themes[theme_id]
        db_theme = db_themes[theme_id]

        changed = (
            file_theme["name"] != db_theme.get("name")
            or file_theme["description"] != db_theme.get("description")
            or file_theme["mapping_considerations"] != db_theme.get("mapping_considerations")
            or file_theme["status"] != db_theme.get("status")
        )
        if not changed:
            theme_stats.unchanged += 1
            continue

        theme_ver_close_stmts.append(
            update(src_risks_ver_theme)
            .where(and_(
                src_risks_ver_theme.c.ref_theme_id == theme_id,
                src_risks_ver_theme.c.tx_to.is_(None),
            ))
            .values(tx_to=now_dt)
        )
        theme_ver_inserts.append({
            "ref_theme_id": theme_id,
            "name": file_theme["name"],
            "description": file_theme["description"],
            "mapping_considerations": file_theme["mapping_considerations"],
            "status": file_theme["status"],
            "tx_from": now_dt,
            "tx_to": None,
        })
        theme_stats.changed += 1

    # Execute theme batch
    if theme_ref_inserts or theme_ver_inserts or theme_rel_inserts or theme_ver_close_stmts:
        if dry_run:
            logger.info(
                "[DRY RUN] [theme] ref_inserts={}, ver_inserts={}, rel_inserts={}, ver_closes={}",
                len(theme_ref_inserts), len(theme_ver_inserts),
                len(theme_rel_inserts), len(theme_ver_close_stmts),
            )
        else:
            try:
                async with engine.begin() as conn:
                    if theme_ref_inserts:
                        stmt = pg_insert(src_risks_ref_theme).on_conflict_do_nothing(
                            index_elements=["theme_id"]
                        )
                        await conn.execute(stmt, theme_ref_inserts)
                    for close_stmt in theme_ver_close_stmts:
                        await conn.execute(close_stmt)
                    if theme_ver_inserts:
                        await conn.execute(insert(src_risks_ver_theme), theme_ver_inserts)
                    if theme_rel_inserts:
                        stmt = pg_insert(src_risks_rel_taxonomy_theme).on_conflict_do_nothing(
                            index_elements=["taxonomy_id", "theme_id"]
                        )
                        await conn.execute(stmt, theme_rel_inserts)
            except Exception as exc:
                msg = f"[theme] Batch execution failed: {exc}"
                logger.error(msg)
                theme_stats.add_error(msg)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

async def run_ingestion(
    context_providers_path: Path,
    dry_run: bool,
    postgres_url: Optional[str] = None,
) -> AllStats:
    """Top-level async entry point."""
    all_stats = AllStats()

    # ----- Resolve directory structure -----
    org_base = context_providers_path / "organization"
    risk_base = context_providers_path / "risk_theme"

    org_date_dir = _find_latest_date_dir(org_base)
    risk_date_dir = _find_latest_date_dir(risk_base)

    if org_date_dir is None and risk_date_dir is None:
        logger.error(
            "No date-partitioned directories found under {} or {}",
            org_base, risk_base,
        )
        raise SystemExit(1)

    if org_date_dir:
        logger.info("Organization data directory: {}", org_date_dir)
    if risk_date_dir:
        logger.info("Risk theme data directory:    {}", risk_date_dir)

    # ----- Init PostgreSQL engine -----
    settings = get_settings()
    db_url = postgres_url or settings.postgres_url
    init_engine(
        database_url=db_url,
        pool_size=settings.postgres_pool_size,
        max_overflow=settings.postgres_max_overflow,
    )
    engine = get_engine()
    logger.info("Connected to PostgreSQL")
    logger.info("Writer config: batch_size={}", BATCH_SIZE)

    try:
        # ----- Orgs -----
        if org_date_dir:
            logger.info("--- Ingesting organization trees ---")
            for tree, stats_attr in [
                ("function", "orgs_function"),
                ("location", "orgs_location"),
                ("consolidated", "orgs_consolidated"),
            ]:
                tree_stats: IngestionStats = getattr(all_stats, stats_attr)
                try:
                    await ingest_org_tree(engine, tree, org_date_dir, tree_stats, dry_run)
                except Exception as exc:
                    logger.error("Failed ingesting tree '{}': {}", tree, exc, exc_info=True)
                    tree_stats.add_error(str(exc))

        # ----- Risk themes -----
        if risk_date_dir:
            logger.info("--- Ingesting risk themes ---")
            try:
                await ingest_risk_themes(
                    engine, risk_date_dir,
                    all_stats.risks_taxonomy,
                    all_stats.risks_theme,
                    dry_run,
                )
            except Exception as exc:
                logger.error("Failed ingesting risk themes: {}", exc, exc_info=True)
                all_stats.risks_taxonomy.add_error(str(exc))
                all_stats.risks_theme.add_error(str(exc))

    finally:
        await dispose_engine()

    return all_stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.scripts.ingest_context_providers",
        description="Ingest org charts and risk themes into PostgreSQL.",
    )
    parser.add_argument(
        "--context-providers-path",
        type=Path,
        default=None,
        help="Root directory containing organization/ and risk_theme/ subdirectories. "
             "Defaults to CONTEXT_PROVIDERS_PATH from .env.",
    )
    parser.add_argument(
        "--postgres-url",
        type=str,
        default=None,
        help="Override PostgreSQL URL (default: value from .env).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would be done without writing to the database.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    # Configure logging level
    import os
    if args.verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"
    configure_logging()

    # Resolve path: CLI arg > .env
    if args.context_providers_path is not None:
        ctx_path = args.context_providers_path.resolve()
    else:
        from server.settings import get_settings
        ctx_path = get_settings().context_providers_path.resolve()
        logger.info("Using CONTEXT_PROVIDERS_PATH from .env: {}", ctx_path)

    if not ctx_path.is_dir():
        logger.error("Context providers path does not exist: {}", ctx_path)
        sys.exit(1)

    logger.info("Starting context-provider ingestion from {}", ctx_path)
    if args.dry_run:
        logger.info("DRY RUN mode enabled — no data will be written")

    try:
        all_stats = asyncio.run(
            run_ingestion(
                context_providers_path=ctx_path,
                dry_run=args.dry_run,
                postgres_url=args.postgres_url,
            )
        )
    except SystemExit:
        raise
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(130)
    except Exception as exc:
        logger.error("Ingestion failed: {}", exc, exc_info=True)
        sys.exit(1)

    all_stats.print_summary()

    # Check for errors
    total_errors = sum(
        getattr(all_stats, attr).errors
        for attr in (
            "orgs_function", "orgs_location", "orgs_consolidated",
            "risks_taxonomy", "risks_theme",
        )
    )
    if total_errors > 0:
        logger.warning("Completed with {} error(s)", total_errors)
        sys.exit(1)

    logger.info("Ingestion completed successfully")


if __name__ == "__main__":
    main()
