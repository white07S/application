"""Filter query service — reads org trees, CEs, AUs, risk themes from Postgres."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select, func, text, and_, or_, exists

from server.config.postgres import get_engine
from server.explorer.shared.temporal import temporal_condition, find_effective_date
from server.explorer.shared.models import (
    TreeNodeResponse,
    FlatItemResponse,
    RiskTaxonomyResponse,
    RiskThemeResponse,
)
from server.logging_config import get_logger

from server.pipelines.orgs.schema import (
    src_orgs_ref_node,
    src_orgs_ver_function,
    src_orgs_ver_location,
    src_orgs_ver_consolidated,
    src_orgs_rel_child,
)
from server.pipelines.risks.schema import (
    src_risks_ref_taxonomy,
    src_risks_ver_taxonomy,
    src_risks_ref_theme,
    src_risks_ver_theme,
    src_risks_rel_taxonomy_theme,
)
from server.pipelines.assessment_units.schema import (
    src_au_ref_unit,
    src_au_ver_unit,
)

logger = get_logger(name=__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_tree(rows: list[dict], max_preloaded_level: int) -> list[TreeNodeResponse]:
    """Convert flat rows (node_id, name, level, parent_id, has_children) into nested tree."""
    row_by_id: dict[str, dict] = {r["node_id"]: r for r in rows}

    def get_level(row: dict) -> int:
        if row["level"] >= 0:
            return row["level"]
        parent = row.get("parent_id")
        if not parent or parent not in row_by_id:
            return 0
        return get_level(row_by_id[parent]) + 1

    for row in rows:
        row["level"] = get_level(row)

    nodes_by_id: dict[str, TreeNodeResponse] = {}
    roots: list[TreeNodeResponse] = []

    for row in rows:
        node = TreeNodeResponse(
            id=row["node_id"],
            label=row["name"],
            level=row["level"],
            has_children=row.get("has_children", False),
            children=[],
            node_type=row.get("node_type"),
            status=row.get("status"),
        )
        nodes_by_id[row["node_id"]] = node

    for row in rows:
        parent_id = row.get("parent_id")
        node = nodes_by_id[row["node_id"]]
        if parent_id and parent_id in nodes_by_id:
            nodes_by_id[parent_id].children.append(node)
            nodes_by_id[parent_id].has_children = True
        elif not parent_id:
            roots.append(node)

    return roots


# ---------------------------------------------------------------------------
# Functions tree
# ---------------------------------------------------------------------------

async def get_function_tree(
    as_of: date,
    parent_id: str | None = None,
    search: str | None = None,
) -> tuple[list[TreeNodeResponse], str | None]:
    """Return function hierarchy nodes.

    - parent_id=None, search=None: roots + 2 levels via recursive CTE.
    - parent_id set: direct children of that node (lazy load).
    - search set: ILIKE search across ALL nodes (flat results).

    Returns (nodes, date_warning_or_None).
    """
    engine = get_engine()
    ref = src_orgs_ref_node
    ver = src_orgs_ver_function
    rel = src_orgs_rel_child

    async with engine.connect() as conn:
        if parent_id:
            nodes = await _load_children(conn, parent_id, "function", ver, as_of)
            return nodes, None

        as_of, warning = await find_effective_date(conn, ver, as_of)

        if search:
            return await _search_nodes(conn, "function", ver, as_of, search), warning

        tc_ver = temporal_condition(ver.c.tx_from, ver.c.tx_to, as_of)
        tc_rel = temporal_condition(rel.c.tx_from, rel.c.tx_to, as_of)

        child_ids = (
            select(rel.c.out_node_id)
            .where(tc_rel)
            .correlate(None)
            .scalar_subquery()
        )

        roots_q = (
            select(
                ref.c.node_id,
                ver.c.name,
                ref.c.node_type,
                ver.c.status,
            )
            .join(ver, ver.c.ref_node_id == ref.c.node_id)
            .where(ref.c.tree == "function")
            .where(tc_ver)
            .where(ref.c.node_id.not_in(
                select(rel.c.out_node_id).where(tc_rel)
            ))
            .order_by(ver.c.name)
        )
        root_rows = (await conn.execute(roots_q)).mappings().all()

        all_rows: list[dict] = []
        for rr in root_rows:
            all_rows.append({
                "node_id": rr["node_id"],
                "name": rr["name"],
                "level": 0,
                "parent_id": None,
                "has_children": False,
                "node_type": rr["node_type"],
                "status": rr["status"],
            })

        if root_rows:
            root_ids = [r["node_id"] for r in root_rows]
            l1_rows = await _fetch_children_batch(conn, root_ids, "function", ver, as_of)
            all_rows.extend(l1_rows)

            l1_ids = [r["node_id"] for r in l1_rows]
            if l1_ids:
                l2_rows = await _fetch_children_batch(conn, l1_ids, "function", ver, as_of)
                all_rows.extend(l2_rows)

        return _build_tree(all_rows, max_preloaded_level=2), warning


# ---------------------------------------------------------------------------
# Locations tree
# ---------------------------------------------------------------------------

async def get_location_tree(
    as_of: date,
    parent_id: str | None = None,
    search: str | None = None,
) -> tuple[list[TreeNodeResponse], str | None]:
    """Return location hierarchy nodes. Same approach as functions.

    Returns (nodes, date_warning_or_None).
    """
    engine = get_engine()
    ref = src_orgs_ref_node
    ver = src_orgs_ver_location
    rel = src_orgs_rel_child

    async with engine.connect() as conn:
        if parent_id:
            nodes = await _load_children(conn, parent_id, "location", ver, as_of, name_is_array=True)
            return nodes, None

        as_of, warning = await find_effective_date(conn, ver, as_of)

        if search:
            return await _search_nodes(conn, "location", ver, as_of, search, name_is_array=True), warning

        tc_ver = temporal_condition(ver.c.tx_from, ver.c.tx_to, as_of)
        tc_rel = temporal_condition(rel.c.tx_from, rel.c.tx_to, as_of)

        roots_q = (
            select(
                ref.c.node_id,
                ver.c.names[1].label("name"),
                ref.c.node_type,
                ver.c.status,
            )
            .join(ver, ver.c.ref_node_id == ref.c.node_id)
            .where(ref.c.tree == "location")
            .where(tc_ver)
            .where(ref.c.node_id.not_in(
                select(rel.c.out_node_id).where(tc_rel)
            ))
            .order_by(ver.c.names[1])
        )
        root_rows = (await conn.execute(roots_q)).mappings().all()

        all_rows: list[dict] = []
        for rr in root_rows:
            all_rows.append({
                "node_id": rr["node_id"],
                "name": rr["name"] or rr["node_id"],
                "level": 0,
                "parent_id": None,
                "has_children": False,
                "node_type": rr["node_type"],
                "status": rr["status"],
            })

        if root_rows:
            root_ids = [r["node_id"] for r in root_rows]
            l1_rows = await _fetch_children_batch(conn, root_ids, "location", ver, as_of, name_is_array=True)
            all_rows.extend(l1_rows)

            l1_ids = [r["node_id"] for r in l1_rows]
            if l1_ids:
                l2_rows = await _fetch_children_batch(conn, l1_ids, "location", ver, as_of, name_is_array=True)
                all_rows.extend(l2_rows)

        return _build_tree(all_rows, max_preloaded_level=2), warning


# ---------------------------------------------------------------------------
# Shared tree helpers
# ---------------------------------------------------------------------------

async def _search_nodes(
    conn,
    tree_type: str,
    ver_table,
    as_of: date,
    search: str,
    name_is_array: bool = False,
) -> list[TreeNodeResponse]:
    """Search all nodes by name or node_id (ILIKE), return results as a tree with ancestors."""
    ref = src_orgs_ref_node
    rel = src_orgs_rel_child
    tc_ver = temporal_condition(ver_table.c.tx_from, ver_table.c.tx_to, as_of)
    tc_rel = temporal_condition(rel.c.tx_from, rel.c.tx_to, as_of)
    name_col = ver_table.c.names[1] if name_is_array else ver_table.c.name
    search_pattern = f"%{search}%"

    q = (
        select(
            ref.c.node_id,
            name_col.label("name"),
            ref.c.node_type,
            ver_table.c.status,
        )
        .select_from(
            ref.join(ver_table, ver_table.c.ref_node_id == ref.c.node_id)
        )
        .where(ref.c.tree == tree_type)
        .where(tc_ver)
        .where(or_(
            name_col.ilike(search_pattern),
            ref.c.node_id.ilike(search_pattern),
        ))
        .order_by(name_col)
        .limit(50)
    )
    try:
        rows = (await conn.execute(q)).mappings().all()
    except Exception:
        logger.exception("_search_nodes failed for tree=%s search=%s", tree_type, search)
        return []

    if not rows:
        return []

    matched_ids = [r["node_id"] for r in rows]
    matched_set = set(matched_ids)

    # Collect info for matched nodes
    node_info: dict[str, dict] = {}
    for r in rows:
        node_info[r["node_id"]] = {
            "name": r["name"] or r["node_id"],
            "node_type": r["node_type"],
            "status": r["status"],
        }

    # Walk up tree to find all ancestors
    current_ids = set(matched_ids)
    all_ids = set(matched_ids)
    parent_map: dict[str, str] = {}  # child -> parent

    for _ in range(10):  # safety limit
        if not current_ids:
            break
        parent_q = (
            select(rel.c.out_node_id, rel.c.in_node_id)
            .where(rel.c.out_node_id.in_(list(current_ids)))
            .where(tc_rel)
        )
        parent_rows = (await conn.execute(parent_q)).mappings().all()
        next_ids: set[str] = set()
        for r in parent_rows:
            parent_map[r["out_node_id"]] = r["in_node_id"]
            if r["in_node_id"] not in all_ids:
                next_ids.add(r["in_node_id"])
                all_ids.add(r["in_node_id"])
        current_ids = next_ids

    # Get info for all ancestor nodes
    ancestor_ids = all_ids - matched_set
    if ancestor_ids:
        anc_q = (
            select(
                ref.c.node_id,
                name_col.label("name"),
                ref.c.node_type,
                ver_table.c.status,
            )
            .select_from(ref.join(ver_table, ver_table.c.ref_node_id == ref.c.node_id))
            .where(ref.c.node_id.in_(list(ancestor_ids)))
            .where(ref.c.tree == tree_type)
            .where(tc_ver)
        )
        anc_rows = (await conn.execute(anc_q)).mappings().all()
        for r in anc_rows:
            node_info[r["node_id"]] = {
                "name": r["name"] or r["node_id"],
                "node_type": r["node_type"],
                "status": r["status"],
            }

    # Build children map (parent -> [children])
    children_map: dict[str, list[str]] = defaultdict(list)
    for child_id, pid in parent_map.items():
        if pid in all_ids:
            children_map[pid].append(child_id)

    # Root nodes = nodes with no parent in our set
    root_ids = [nid for nid in all_ids if nid not in parent_map]

    # Build nested tree recursively
    def build_node(node_id: str, level: int) -> TreeNodeResponse | None:
        info = node_info.get(node_id)
        if not info:
            return None
        child_ids = children_map.get(node_id, [])
        children = []
        for cid in child_ids:
            child_node = build_node(cid, level + 1)
            if child_node:
                children.append(child_node)
        return TreeNodeResponse(
            id=node_id,
            label=info["name"],
            level=level,
            has_children=len(children) > 0,
            children=children,
            node_type=info["node_type"],
            status=info["status"],
        )

    roots = []
    for rid in root_ids:
        node = build_node(rid, 0)
        if node:
            roots.append(node)
    return roots


async def _fetch_children_batch(
    conn,
    parent_ids: list[str],
    tree_type: str,
    ver_table,
    as_of: date,
    name_is_array: bool = False,
) -> list[dict]:
    """Fetch direct children for a batch of parent IDs, with has_children flag."""
    ref = src_orgs_ref_node
    rel = src_orgs_rel_child
    tc_ver = temporal_condition(ver_table.c.tx_from, ver_table.c.tx_to, as_of)
    tc_rel = temporal_condition(rel.c.tx_from, rel.c.tx_to, as_of)

    name_col = ver_table.c.names[1] if name_is_array else ver_table.c.name

    grandchild_rel = src_orgs_rel_child.alias("gc_rel")
    tc_gc = temporal_condition(grandchild_rel.c.tx_from, grandchild_rel.c.tx_to, as_of)
    has_gc = exists(
        select(grandchild_rel.c.edge_id)
        .where(grandchild_rel.c.in_node_id == rel.c.out_node_id)
        .where(tc_gc)
    )

    q = (
        select(
            ref.c.node_id,
            name_col.label("name"),
            rel.c.in_node_id.label("parent_id"),
            has_gc.label("has_children"),
            ref.c.node_type,
            ver_table.c.status,
        )
        .select_from(
            rel
            .join(ref, ref.c.node_id == rel.c.out_node_id)
            .join(ver_table, ver_table.c.ref_node_id == ref.c.node_id)
        )
        .where(rel.c.in_node_id.in_(parent_ids))
        .where(tc_rel)
        .where(ref.c.tree == tree_type)
        .where(tc_ver)
        .order_by(name_col)
    )
    rows = (await conn.execute(q)).mappings().all()

    result = []
    for r in rows:
        result.append({
            "node_id": r["node_id"],
            "name": r["name"] or r["node_id"],
            "level": -1,
            "parent_id": r["parent_id"],
            "has_children": r["has_children"],
            "node_type": r["node_type"],
            "status": r["status"],
        })
    return result


async def _load_children(
    conn,
    parent_id: str,
    tree_type: str,
    ver_table,
    as_of: date,
    name_is_array: bool = False,
) -> list[TreeNodeResponse]:
    """Lazy-load direct children for a single parent node."""
    rows = await _fetch_children_batch(conn, [parent_id], tree_type, ver_table, as_of, name_is_array)
    return [
        TreeNodeResponse(
            id=r["node_id"],
            label=r["name"],
            level=0,
            has_children=r["has_children"],
            children=[],
            node_type=r.get("node_type"),
            status=r.get("status"),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Consolidated entities
# ---------------------------------------------------------------------------

async def get_consolidated_entities(
    as_of: date,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Paginated consolidated entities with optional ILIKE search."""
    engine = get_engine()
    ref = src_orgs_ref_node
    ver = src_orgs_ver_consolidated

    async with engine.connect() as conn:
        as_of, warning = await find_effective_date(conn, ver, as_of)

        tc_ver = temporal_condition(ver.c.tx_from, ver.c.tx_to, as_of)
        base = (
            select(
                ref.c.node_id.label("id"),
                ver.c.names[1].label("label"),
            )
            .join(ver, ver.c.ref_node_id == ref.c.node_id)
            .where(ref.c.tree == "consolidated")
            .where(tc_ver)
        )
        if search:
            base = base.where(ver.c.names[1].ilike(f"%{search}%"))

        count_q = select(func.count()).select_from(base.subquery())
        total = (await conn.execute(count_q)).scalar_one()

        offset = (page - 1) * page_size
        data_q = base.order_by(ver.c.names[1]).limit(page_size).offset(offset)
        rows = (await conn.execute(data_q)).mappings().all()

        items = [
            FlatItemResponse(id=r["id"], label=r["label"] or r["id"])
            for r in rows
        ]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": (page * page_size) < total,
            "effective_date": as_of.isoformat(),
            "date_warning": warning,
        }


# ---------------------------------------------------------------------------
# Assessment units
# ---------------------------------------------------------------------------

async def get_assessment_units(as_of: date) -> dict:
    """Return all assessment units (small dataset)."""
    engine = get_engine()
    ref = src_au_ref_unit
    ver = src_au_ver_unit

    async with engine.connect() as conn:
        as_of, warning = await find_effective_date(conn, ver, as_of)

        tc_ver = temporal_condition(ver.c.tx_from, ver.c.tx_to, as_of)
        q = (
            select(
                ref.c.unit_id.label("id"),
                ver.c.name.label("label"),
                ver.c.status.label("description"),
            )
            .join(ver, ver.c.ref_unit_id == ref.c.unit_id)
            .where(tc_ver)
            .order_by(ver.c.name)
        )
        rows = (await conn.execute(q)).mappings().all()
        items = [FlatItemResponse(id=r["id"], label=r["label"], description=r["description"]) for r in rows]
        return {
            "items": items,
            "total": len(items),
            "page": 1,
            "page_size": len(items),
            "has_more": False,
            "effective_date": as_of.isoformat(),
            "date_warning": warning,
        }


# ---------------------------------------------------------------------------
# Risk themes
# ---------------------------------------------------------------------------

async def get_risk_taxonomies(as_of: date) -> tuple[list[RiskTaxonomyResponse], str | None]:
    """Return all risk taxonomies with their active themes.

    Returns (taxonomies, date_warning_or_None).
    """
    engine = get_engine()

    async with engine.connect() as conn:
        as_of, warning = await find_effective_date(conn, src_risks_ver_taxonomy, as_of)

        tc_tax = temporal_condition(
            src_risks_ver_taxonomy.c.tx_from,
            src_risks_ver_taxonomy.c.tx_to,
            as_of,
        )
        tc_theme = temporal_condition(
            src_risks_ver_theme.c.tx_from,
            src_risks_ver_theme.c.tx_to,
            as_of,
        )
        tax_q = (
            select(
                src_risks_ref_taxonomy.c.taxonomy_id.label("id"),
                src_risks_ver_taxonomy.c.name,
            )
            .join(
                src_risks_ver_taxonomy,
                src_risks_ver_taxonomy.c.ref_taxonomy_id == src_risks_ref_taxonomy.c.taxonomy_id,
            )
            .where(tc_tax)
            .order_by(src_risks_ver_taxonomy.c.name)
        )
        tax_rows = (await conn.execute(tax_q)).mappings().all()

        theme_q = (
            select(
                src_risks_rel_taxonomy_theme.c.taxonomy_id,
                src_risks_ref_theme.c.theme_id.label("id"),
                src_risks_ver_theme.c.name,
            )
            .select_from(
                src_risks_rel_taxonomy_theme
                .join(src_risks_ref_theme, src_risks_ref_theme.c.theme_id == src_risks_rel_taxonomy_theme.c.theme_id)
                .join(src_risks_ver_theme, src_risks_ver_theme.c.ref_theme_id == src_risks_ref_theme.c.theme_id)
            )
            .where(tc_theme)
            .where(src_risks_ver_theme.c.status == "active")
            .order_by(src_risks_ver_theme.c.name)
        )
        theme_rows = (await conn.execute(theme_q)).mappings().all()

        themes_by_tax: dict[str, list[RiskThemeResponse]] = defaultdict(list)
        for tr in theme_rows:
            themes_by_tax[tr["taxonomy_id"]].append(
                RiskThemeResponse(id=tr["id"], name=tr["name"])
            )

        taxonomies = [
            RiskTaxonomyResponse(
                id=t["id"],
                name=t["name"],
                themes=themes_by_tax.get(t["id"], []),
            )
            for t in tax_rows
        ]
        return taxonomies, warning
