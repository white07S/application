"""Controls search service — sidebar filters, FTS, Qdrant semantic, hybrid RRF."""

from __future__ import annotations

import asyncio
import base64
from collections import defaultdict

from sqlalchemy import select, func, and_, or_, literal_column, union_all, intersect_all, text

from server.config.postgres import get_engine
from server.config.qdrant import get_qdrant_client
from server.explorer.shared.embeddings import embed_query
from server.explorer.shared.models import (
    SEARCH_FIELD_NAMES,
    AIEnrichmentResponse,
    ControlResponse,
    ControlRelationshipsResponse,
    ControlWithDetailsResponse,
    ControlsSearchParams,
    ControlsSearchResponse,
    NamedItem,
    ParentL1ScoreResponse,
    SimilarControlResponse,
)
from server.logging_config import get_logger
from server.settings import get_settings

# Schema imports
from server.pipelines.controls.schema import (
    src_controls_ver_control as ver_control,
    src_controls_rel_parent as rel_parent,
    src_controls_rel_owns_function as rel_owns_func,
    src_controls_rel_owns_location as rel_owns_loc,
    src_controls_rel_related_function as rel_related_func,
    src_controls_rel_related_location as rel_related_loc,
    src_controls_rel_risk_theme as rel_risk_theme,
    ai_controls_model_enrichment as ai_enrichment,
    ai_controls_model_taxonomy as ai_taxonomy,
    ai_controls_model_clean_text as ai_clean_text,
    ai_controls_similar_controls as similar_controls,
)
from server.pipelines.orgs.schema import (
    src_orgs_ver_function as ver_function,
    src_orgs_ver_location as ver_location,
    src_orgs_rel_cross_link as rel_cross_link,
)
from server.pipelines.assessment_units.schema import src_au_ver_unit as ver_au
from server.pipelines.controls.qdrant_service import control_id_to_uuid, NAMED_VECTORS

from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    NamedVector,
    SearchRequest,
)

logger = get_logger(name=__name__)

# RRF constant (standard value from the original RRF paper)
_RRF_K = 60

# Batch size for IN clauses — asyncpg limit is 32767 parameters per statement
_BATCH_SIZE = 30_000

# Map clean_text field names → tsvector column names
_TS_COLUMN_MAP = {
    "control_title": "ts_control_title",
    "control_description": "ts_control_description",
    "evidence_description": "ts_evidence_description",
    "local_functional_information": "ts_local_functional_information",
    "control_as_event": "ts_control_as_event",
    "control_as_issues": "ts_control_as_issues",
}

# L1 W-criteria yes/no columns
_L1_YES_NO_COLS = [
    "what_yes_no", "where_yes_no", "who_yes_no", "when_yes_no",
    "why_yes_no", "what_why_yes_no", "risk_theme_yes_no",
]
# L2 operational criteria yes/no columns
_L2_YES_NO_COLS = [
    "frequency_yes_no", "preventative_detective_yes_no",
    "automation_level_yes_no", "followup_yes_no",
    "escalation_yes_no", "evidence_yes_no", "abbreviations_yes_no",
]


def _is_current(col):
    """Temporal filter: tx_to IS NULL means 'current version'."""
    return col.is_(None)


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return int(base64.urlsafe_b64decode(cursor).decode())
    except Exception:
        return 0


# ──────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────

async def search_controls(
    params: ControlsSearchParams,
    graph_token: str | None = None,
) -> ControlsSearchResponse:
    """Orchestrate controls search: sidebar filter → search → toolbar filter → paginate → hydrate."""
    engine = get_engine()

    async with engine.connect() as conn:
        # 1. Sidebar filter → candidate control_ids (or None = all)
        candidates = await _resolve_sidebar_candidates(conn, params)

        # 2. Determine search mode
        query = (params.search_query or "").strip()
        mode = params.search_mode

        if query and not mode:
            # Auto-detect: if looks like a control ID, use ID mode
            mode = "id" if _looks_like_control_id(query) else "hybrid"

        # 3. Search → ranked list of (control_id, score)
        has_search = bool(query)
        if query and mode == "id":
            ranked = await _search_by_id(conn, query, candidates)
        elif query and mode == "keyword":
            ranked = await _search_by_keyword(conn, query, params.search_fields, candidates)
        elif query and mode == "semantic":
            ranked = await _search_by_semantic(query, params.search_fields, candidates, graph_token)
        elif query and mode == "hybrid":
            ranked = await _search_hybrid(conn, query, params.search_fields, candidates, graph_token)
        else:
            # No search query: push toolbar filters directly into the browse
            # query to avoid a separate IN-clause that could exceed asyncpg's
            # 32 767 parameter limit with large control sets.
            ranked = await _browse_all(conn, candidates, toolbar=params.toolbar)
            has_search = False

        # 4. Toolbar filters — only needed when a search was performed
        #    (browse_all already applied them inline)
        if has_search and _has_toolbar_filters(params.toolbar):
            ranked = await _apply_toolbar_filters(conn, ranked, params.toolbar)

        # 5. Paginate
        total_estimate = len(ranked)
        offset = _decode_cursor(params.cursor)
        page = ranked[offset: offset + params.page_size]
        has_more = (offset + params.page_size) < total_estimate
        next_cursor = _encode_cursor(offset + params.page_size) if has_more else None

        if not page:
            return ControlsSearchResponse(
                items=[], cursor=next_cursor, total_estimate=total_estimate, has_more=has_more,
            )

        # 6. Hydrate
        page_ids = [cid for cid, _ in page]
        score_map = {cid: score for cid, score in page}
        items = await _hydrate_controls(conn, page_ids, score_map)

        return ControlsSearchResponse(
            items=items, cursor=next_cursor, total_estimate=total_estimate, has_more=has_more,
        )


# ──────────────────────────────────────────────────────────────────────
# Sidebar filter resolution
# ──────────────────────────────────────────────────────────────────────

async def _resolve_sidebar_candidates(
    conn,
    params: ControlsSearchParams,
) -> set[str] | None:
    """Resolve sidebar filter selections to a set of control_ids, or None if no filters."""
    sidebar = params.sidebar
    if not sidebar.has_any:
        return None

    scope = params.relationship_scope
    category_sets: list[set[str]] = []

    # Functions
    if sidebar.functions:
        ids = await _controls_by_org_nodes(conn, sidebar.functions, "function", scope)
        category_sets.append(ids)

    # Locations
    if sidebar.locations:
        ids = await _controls_by_org_nodes(conn, sidebar.locations, "location", scope)
        category_sets.append(ids)

    # Assessment Units → resolve to function/location → controls
    if sidebar.assessment_units:
        ids = await _controls_by_aus(conn, sidebar.assessment_units, scope)
        category_sets.append(ids)

    # Consolidated Entities → resolve via cross_link → function/location → controls
    if sidebar.consolidated_entities:
        ids = await _controls_by_ces(conn, sidebar.consolidated_entities, scope)
        category_sets.append(ids)

    # Risk Themes
    if sidebar.risk_themes:
        ids = await _controls_by_risk_themes(conn, sidebar.risk_themes)
        category_sets.append(ids)

    if not category_sets:
        return None

    # Combine: AND = intersection, OR = union
    if params.filter_logic == "and":
        result = category_sets[0]
        for s in category_sets[1:]:
            result = result & s
    else:
        result = set()
        for s in category_sets:
            result = result | s

    return result


async def _controls_by_org_nodes(
    conn, node_ids: list[str], org_type: str, scope: str,
) -> set[str]:
    """Find control_ids linked to given org node_ids via owns/related tables."""
    queries = []

    if org_type == "function":
        owns_tbl, related_tbl = rel_owns_func, rel_related_func
    else:
        owns_tbl, related_tbl = rel_owns_loc, rel_related_loc

    if scope in ("owns", "both"):
        q = (
            select(owns_tbl.c.control_id)
            .where(owns_tbl.c.node_id.in_(node_ids))
            .where(_is_current(owns_tbl.c.tx_to))
        )
        queries.append(q)

    if scope in ("related", "both"):
        q = (
            select(related_tbl.c.control_id)
            .where(related_tbl.c.node_id.in_(node_ids))
            .where(_is_current(related_tbl.c.tx_to))
        )
        queries.append(q)

    if not queries:
        return set()

    combined = union_all(*queries)
    rows = (await conn.execute(combined)).fetchall()
    return {r[0] for r in rows}


async def _controls_by_aus(conn, unit_ids: list[str], scope: str) -> set[str]:
    """Resolve AU → function/location node_ids → controls."""
    q = (
        select(ver_au.c.function_node_id, ver_au.c.location_node_id)
        .where(ver_au.c.ref_unit_id.in_(unit_ids))
        .where(_is_current(ver_au.c.tx_to))
    )
    rows = (await conn.execute(q)).fetchall()

    func_ids = list({r[0] for r in rows if r[0]})
    loc_ids = list({r[1] for r in rows if r[1]})

    results: set[str] = set()
    if func_ids:
        results |= await _controls_by_org_nodes(conn, func_ids, "function", scope)
    if loc_ids:
        results |= await _controls_by_org_nodes(conn, loc_ids, "location", scope)
    return results


async def _controls_by_ces(conn, ce_node_ids: list[str], scope: str) -> set[str]:
    """Resolve CE → cross_link → function/location node_ids → controls."""
    q = (
        select(rel_cross_link.c.out_node_id)
        .where(rel_cross_link.c.in_node_id.in_(ce_node_ids))
        .where(_is_current(rel_cross_link.c.tx_to))
    )
    rows = (await conn.execute(q)).fetchall()
    linked_node_ids = [r[0] for r in rows]

    if not linked_node_ids:
        return set()

    # Try both function and location paths
    results: set[str] = set()
    results |= await _controls_by_org_nodes(conn, linked_node_ids, "function", scope)
    results |= await _controls_by_org_nodes(conn, linked_node_ids, "location", scope)
    return results


async def _controls_by_risk_themes(conn, theme_ids: list[str]) -> set[str]:
    """Find control_ids linked to given risk theme_ids."""
    q = (
        select(rel_risk_theme.c.control_id)
        .where(rel_risk_theme.c.theme_id.in_(theme_ids))
        .where(_is_current(rel_risk_theme.c.tx_to))
    )
    rows = (await conn.execute(q)).fetchall()
    return {r[0] for r in rows}


# ──────────────────────────────────────────────────────────────────────
# Search modes
# ──────────────────────────────────────────────────────────────────────

def _looks_like_control_id(q: str) -> bool:
    """Heuristic: if query starts with CTL- or is purely alphanumeric+dashes, treat as ID."""
    q = q.strip().upper()
    return q.startswith("CTL-") or q.startswith("CTL_")


async def _search_by_id(
    conn, query: str, candidates: set[str] | None,
) -> list[tuple[str, float]]:
    """Exact or prefix match on control_id."""
    pattern = query.strip() + "%"
    q = (
        select(ver_control.c.ref_control_id)
        .where(_is_current(ver_control.c.tx_to))
        .where(ver_control.c.ref_control_id.ilike(pattern))
        .order_by(ver_control.c.ref_control_id)
        .limit(500)
    )
    if candidates is not None:
        q = q.where(ver_control.c.ref_control_id.in_(candidates))

    rows = (await conn.execute(q)).fetchall()
    return [(r[0], 1.0) for r in rows]


async def _search_by_keyword(
    conn,
    query: str,
    search_fields: list[str],
    candidates: set[str] | None,
) -> list[tuple[str, float]]:
    """Full-text search via tsvector columns in ai_controls_model_clean_text."""
    ts_query = func.plainto_tsquery("english", query)

    # Build rank expression: sum of ts_rank across selected fields
    rank_parts = []
    for field in search_fields:
        ts_col_name = _TS_COLUMN_MAP.get(field)
        if ts_col_name:
            ts_col = getattr(ai_clean_text.c, ts_col_name)
            rank_parts.append(func.coalesce(func.ts_rank(ts_col, ts_query), 0))

    if not rank_parts:
        return []

    total_rank = rank_parts[0]
    for part in rank_parts[1:]:
        total_rank = total_rank + part

    q = (
        select(
            ai_clean_text.c.ref_control_id,
            total_rank.label("rank"),
        )
        .where(_is_current(ai_clean_text.c.tx_to))
        .where(total_rank > 0)
        .order_by(total_rank.desc())
        .limit(2000)
    )

    if candidates is not None:
        q = q.where(ai_clean_text.c.ref_control_id.in_(candidates))

    rows = (await conn.execute(q)).fetchall()
    return [(r[0], float(r[1])) for r in rows]


async def _search_by_semantic(
    query: str,
    search_fields: list[str],
    candidates: set[str] | None,
    graph_token: str | None,
) -> list[tuple[str, float]]:
    """Semantic search via Qdrant named vectors, merged with RRF."""
    embedding = await embed_query(query, graph_token=graph_token)
    settings = get_settings()
    qdrant = get_qdrant_client()
    collection = settings.qdrant_collection

    # Build Qdrant filter if we have candidates
    qdrant_filter = None
    if candidates is not None and len(candidates) <= 5000:
        point_ids = [control_id_to_uuid(cid) for cid in candidates]
        qdrant_filter = Filter(must=[
            FieldCondition(key="control_id", match=MatchAny(any=list(candidates)))
        ])

    # Search each named vector in parallel
    valid_fields = [f for f in search_fields if f in NAMED_VECTORS]
    if not valid_fields:
        return []

    search_requests = [
        SearchRequest(
            vector=NamedVector(name=field, vector=embedding),
            filter=qdrant_filter,
            limit=200,
            with_payload=["control_id"],
        )
        for field in valid_fields
    ]

    results = await qdrant.search_batch(
        collection_name=collection,
        requests=search_requests,
    )

    # Merge via RRF across fields
    return _rrf_merge([
        [(hit.payload["control_id"], hit.score) for hit in field_results]
        for field_results in results
    ])


async def _search_hybrid(
    conn,
    query: str,
    search_fields: list[str],
    candidates: set[str] | None,
    graph_token: str | None,
) -> list[tuple[str, float]]:
    """Hybrid = keyword + semantic, merged with RRF."""
    # Check if semantic search is available
    has_openai_key = bool(get_settings().openai_api_key)

    if has_openai_key:
        keyword_task = _search_by_keyword(conn, query, search_fields, candidates)
        semantic_task = _search_by_semantic(query, search_fields, candidates, graph_token)
        keyword_results, semantic_results = await asyncio.gather(keyword_task, semantic_task)
        return _rrf_merge([keyword_results, semantic_results])
    else:
        # Fall back to keyword-only
        return await _search_by_keyword(conn, query, search_fields, candidates)


async def _browse_all(
    conn, candidates: set[str] | None, toolbar=None,
) -> list[tuple[str, float]]:
    """No search query: return all controls (ordered by control_id).

    Toolbar filters are pushed directly into the SQL to avoid a separate
    IN-clause round-trip that would exceed asyncpg's 32 767 parameter limit
    when the full control set is large.
    """
    conditions = [_is_current(ver_control.c.tx_to)]

    if candidates is not None:
        conditions.append(ver_control.c.ref_control_id.in_(candidates))

    # Inline toolbar filters
    if toolbar:
        if toolbar.active_only:
            conditions.append(ver_control.c.control_status == "Active")
        if toolbar.key_control is not None:
            conditions.append(ver_control.c.key_control == toolbar.key_control)
        if toolbar.level1 and not toolbar.level2:
            conditions.append(ver_control.c.hierarchy_level == "Level 1")
        elif toolbar.level2 and not toolbar.level1:
            conditions.append(ver_control.c.hierarchy_level == "Level 2")
        elif toolbar.level1 and toolbar.level2:
            conditions.append(ver_control.c.hierarchy_level.in_(["Level 1", "Level 2"]))
        conditions.extend(_build_date_conditions(toolbar))

    q = (
        select(ver_control.c.ref_control_id)
        .where(and_(*conditions))
        .order_by(ver_control.c.ref_control_id)
    )
    rows = (await conn.execute(q)).fetchall()
    ranked = [(r[0], 0.0) for r in rows]

    # AI score filter requires enrichment data — handle in Python with batching
    if toolbar and toolbar.ai_score_max is not None:
        control_ids = {cid for cid, _ in ranked}
        passing = await _filter_by_ai_score(conn, control_ids, toolbar.ai_score_max)
        ranked = [(cid, s) for cid, s in ranked if cid in passing]

    return ranked


# ──────────────────────────────────────────────────────────────────────
# RRF merge
# ──────────────────────────────────────────────────────────────────────

def _rrf_merge(ranked_lists: list[list[tuple[str, float]]]) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score = Σ 1/(k + rank_i) across all lists."""
    scores: dict[str, float] = defaultdict(float)

    for ranked in ranked_lists:
        for rank_idx, (control_id, _original_score) in enumerate(ranked):
            scores[control_id] += 1.0 / (_RRF_K + rank_idx + 1)

    # Sort by RRF score descending
    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return merged


# ──────────────────────────────────────────────────────────────────────
# Toolbar filters
# ──────────────────────────────────────────────────────────────────────

def _has_toolbar_filters(toolbar) -> bool:
    return (
        toolbar.active_only
        or toolbar.key_control is not None
        or toolbar.level1
        or toolbar.level2
        or toolbar.ai_score_max is not None
        or toolbar.date_from is not None
        or toolbar.date_to is not None
    )


def _build_date_conditions(toolbar) -> list:
    """Build SQLAlchemy conditions for the date range filter."""
    conditions = []
    if toolbar.date_from is None and toolbar.date_to is None:
        return conditions

    date_col = (
        ver_control.c.control_created_on
        if toolbar.date_field == "created_on"
        else ver_control.c.last_modified_on
    )
    if toolbar.date_from is not None:
        conditions.append(date_col >= toolbar.date_from)
    if toolbar.date_to is not None:
        conditions.append(date_col <= toolbar.date_to)
    return conditions


async def _apply_toolbar_filters(
    conn,
    ranked: list[tuple[str, float]],
    toolbar,
) -> list[tuple[str, float]]:
    """Apply toolbar quick-filters to the ranked list.

    Uses batched IN clauses to stay within asyncpg's 32 767 parameter limit.
    """
    if not ranked:
        return ranked

    control_ids = [cid for cid, _ in ranked]

    # Build shared filter conditions (everything except the IN clause)
    extra_conditions = []
    if toolbar.active_only:
        extra_conditions.append(ver_control.c.control_status == "Active")
    if toolbar.key_control is not None:
        extra_conditions.append(ver_control.c.key_control == toolbar.key_control)
    if toolbar.level1 and not toolbar.level2:
        extra_conditions.append(ver_control.c.hierarchy_level == "Level 1")
    elif toolbar.level2 and not toolbar.level1:
        extra_conditions.append(ver_control.c.hierarchy_level == "Level 2")
    elif toolbar.level1 and toolbar.level2:
        extra_conditions.append(ver_control.c.hierarchy_level.in_(["Level 1", "Level 2"]))
    extra_conditions.extend(_build_date_conditions(toolbar))

    # Batch IN clause to avoid exceeding asyncpg parameter limit
    matching_ids: set[str] = set()
    for i in range(0, len(control_ids), _BATCH_SIZE):
        batch = control_ids[i : i + _BATCH_SIZE]
        conditions = [
            _is_current(ver_control.c.tx_to),
            ver_control.c.ref_control_id.in_(batch),
            *extra_conditions,
        ]
        q = select(ver_control.c.ref_control_id).where(and_(*conditions))
        rows = (await conn.execute(q)).fetchall()
        matching_ids.update(r[0] for r in rows)

    # AI score filter (if specified)
    if toolbar.ai_score_max is not None:
        matching_ids = await _filter_by_ai_score(conn, matching_ids, toolbar.ai_score_max)

    # Preserve original order
    return [(cid, score) for cid, score in ranked if cid in matching_ids]


async def _filter_by_ai_score(
    conn, control_ids: set[str], max_score: int,
) -> set[str]:
    """Filter controls where AI effective score <= max_score.

    Effective score = count of 'yes' in the 7 relevant yes_no fields.
    L1 controls: count of L1 W-criteria.
    L2 controls: count of L2 operational criteria + parent's L1 score.

    Uses batched IN clauses to stay within asyncpg's 32 767 parameter limit.
    """
    if not control_ids:
        return control_ids

    id_list = list(control_ids)

    # Fetch enrichment data in batches
    cols_to_select = [ai_enrichment.c.ref_control_id]
    for col_name in _L1_YES_NO_COLS + _L2_YES_NO_COLS:
        cols_to_select.append(getattr(ai_enrichment.c, col_name))

    all_enrichment_rows = []
    for i in range(0, len(id_list), _BATCH_SIZE):
        batch = id_list[i : i + _BATCH_SIZE]
        q = (
            select(*cols_to_select)
            .where(_is_current(ai_enrichment.c.tx_to))
            .where(ai_enrichment.c.ref_control_id.in_(batch))
        )
        rows = (await conn.execute(q)).mappings().all()
        all_enrichment_rows.extend(rows)

    # Fetch hierarchy_level in batches
    level_map: dict[str, str] = {}
    for i in range(0, len(id_list), _BATCH_SIZE):
        batch = id_list[i : i + _BATCH_SIZE]
        vc_q = (
            select(ver_control.c.ref_control_id, ver_control.c.hierarchy_level)
            .where(_is_current(ver_control.c.tx_to))
            .where(ver_control.c.ref_control_id.in_(batch))
        )
        vc_rows = (await conn.execute(vc_q)).mappings().all()
        level_map.update({r["ref_control_id"]: r["hierarchy_level"] for r in vc_rows})

    enrichment_map = {}
    for r in all_enrichment_rows:
        cid = r["ref_control_id"]
        l1_count = sum(1 for c in _L1_YES_NO_COLS if (r.get(c) or "").lower() == "yes")
        l2_count = sum(1 for c in _L2_YES_NO_COLS if (r.get(c) or "").lower() == "yes")
        enrichment_map[cid] = (l1_count, l2_count)

    # Get parent relationships for L2 controls (batched)
    l2_ids = [cid for cid in control_ids if level_map.get(cid) == "Level 2"]
    parent_l1_scores: dict[str, int] = {}
    if l2_ids:
        for i in range(0, len(l2_ids), _BATCH_SIZE):
            batch = l2_ids[i : i + _BATCH_SIZE]
            parent_q = (
                select(rel_parent.c.child_control_id, rel_parent.c.parent_control_id)
                .where(_is_current(rel_parent.c.tx_to))
                .where(rel_parent.c.child_control_id.in_(batch))
            )
            parent_rows = (await conn.execute(parent_q)).fetchall()
            for child_id, parent_id in parent_rows:
                if parent_id in enrichment_map:
                    parent_l1_scores[child_id] = enrichment_map[parent_id][0]

    result = set()
    for cid in control_ids:
        level = level_map.get(cid)
        l1_count, l2_count = enrichment_map.get(cid, (0, 0))

        if level == "Level 1":
            score = l1_count
        elif level == "Level 2":
            score = l2_count + parent_l1_scores.get(cid, 0)
        else:
            score = l1_count + l2_count

        if score <= max_score:
            result.add(cid)

    return result


# ──────────────────────────────────────────────────────────────────────
# Hydration — load full details for a page of control_ids
# ──────────────────────────────────────────────────────────────────────


def _build_parent_l1_score(parent_id: str, enrichment_data: dict) -> ParentL1ScoreResponse:
    """Build ParentL1ScoreResponse from a parent control's enrichment data."""
    criteria = []
    for col_name in _L1_YES_NO_COLS:
        key = col_name.replace("_yes_no", "")
        raw = (enrichment_data.get(col_name) or "").strip().lower()
        criteria.append({"key": key, "yes_no": raw == "yes"})

    yes_count = sum(1 for c in criteria if c["yes_no"])
    return ParentL1ScoreResponse(
        control_id=parent_id,
        criteria=criteria,
        yes_count=yes_count,
        total=len(criteria),
    )


async def _hydrate_controls(
    conn,
    control_ids: list[str],
    score_map: dict[str, float],
) -> list[ControlWithDetailsResponse]:
    """Load full details for a list of control_ids (preserving order)."""
    if not control_ids:
        return []

    # Run 5 queries in parallel
    controls_task = _load_controls(conn, control_ids)
    rels_task = _load_relationships(conn, control_ids)
    enrichment_task = _load_enrichment(conn, control_ids)
    taxonomy_task = _load_taxonomy(conn, control_ids)
    similar_task = _load_similar_controls(conn, control_ids)

    controls_map, rels_map, enrichment_map, taxonomy_map, similar_map = await asyncio.gather(
        controls_task, rels_task, enrichment_task, taxonomy_task, similar_task,
    )

    # For L2 controls, load their parent's L1 enrichment so we can include
    # the inherited 7W score regardless of whether the parent is on the page.
    parent_l1_map: dict[str, ParentL1ScoreResponse] = {}
    parent_ids_needed: dict[str, str] = {}  # child_cid → parent_cid
    for cid in control_ids:
        control = controls_map.get(cid)
        if not control or control.hierarchy_level != "Level 2":
            continue
        rels = rels_map.get(cid)
        if rels and rels.parent:
            parent_id = rels.parent.id
            # Check if parent enrichment is already loaded (parent on same page)
            if parent_id in enrichment_map:
                parent_l1_map[cid] = _build_parent_l1_score(parent_id, enrichment_map[parent_id])
            else:
                parent_ids_needed[cid] = parent_id

    # Batch-load any missing parent enrichments
    if parent_ids_needed:
        unique_parent_ids = list(set(parent_ids_needed.values()))
        parent_enrichments = await _load_enrichment(conn, unique_parent_ids)
        for child_cid, parent_id in parent_ids_needed.items():
            p_data = parent_enrichments.get(parent_id)
            if p_data:
                parent_l1_map[child_cid] = _build_parent_l1_score(parent_id, p_data)

    # Assemble in original ranked order
    items = []
    for cid in control_ids:
        control = controls_map.get(cid)
        if not control:
            continue

        ai_data = enrichment_map.get(cid)
        tax_data = taxonomy_map.get(cid)

        ai_response = None
        if ai_data or tax_data:
            ai_response = AIEnrichmentResponse(
                **(ai_data or {}),
                **({"primary_risk_theme_id": tax_data.get("primary_risk_theme_id"),
                    "secondary_risk_theme_id": tax_data.get("secondary_risk_theme_id")}
                   if tax_data else {}),
            )

        items.append(ControlWithDetailsResponse(
            control=control,
            relationships=rels_map.get(cid, ControlRelationshipsResponse()),
            ai=ai_response,
            parent_l1_score=parent_l1_map.get(cid),
            similar_controls=similar_map.get(cid, []),
            search_score=score_map.get(cid),
        ))

    return items


async def _load_controls(conn, control_ids: list[str]) -> dict[str, ControlResponse]:
    """Load core control fields from ver_control."""
    q = (
        select(
            ver_control.c.ref_control_id,
            ver_control.c.control_title,
            ver_control.c.control_description,
            ver_control.c.key_control,
            ver_control.c.hierarchy_level,
            ver_control.c.preventative_detective,
            ver_control.c.manual_automated,
            ver_control.c.execution_frequency,
            ver_control.c.four_eyes_check,
            ver_control.c.control_status,
            ver_control.c.evidence_description,
            ver_control.c.local_functional_information,
            ver_control.c.last_modified_on,
            ver_control.c.control_created_on,
            ver_control.c.control_owner,
            ver_control.c.control_owner_gpn,
            ver_control.c.sox_relevant,
        )
        .where(_is_current(ver_control.c.tx_to))
        .where(ver_control.c.ref_control_id.in_(control_ids))
    )
    rows = (await conn.execute(q)).mappings().all()

    result = {}
    for r in rows:
        cid = r["ref_control_id"]
        result[cid] = ControlResponse(
            control_id=cid,
            control_title=r["control_title"],
            control_description=r["control_description"],
            key_control=r["key_control"],
            hierarchy_level=r["hierarchy_level"],
            preventative_detective=r["preventative_detective"],
            manual_automated=r["manual_automated"],
            execution_frequency=r["execution_frequency"],
            four_eyes_check=r["four_eyes_check"],
            control_status=r["control_status"],
            evidence_description=r["evidence_description"],
            local_functional_information=r["local_functional_information"],
            last_modified_on=r["last_modified_on"],
            control_created_on=r["control_created_on"],
            control_owner=r["control_owner"],
            control_owner_gpn=r["control_owner_gpn"],
            sox_relevant=r["sox_relevant"],
        )
    return result


async def _load_relationships(
    conn, control_ids: list[str],
) -> dict[str, ControlRelationshipsResponse]:
    """Load all relationships for a batch of controls."""
    result: dict[str, ControlRelationshipsResponse] = {}

    # Parent relationships
    parent_q = (
        select(rel_parent.c.child_control_id, rel_parent.c.parent_control_id)
        .where(_is_current(rel_parent.c.tx_to))
        .where(rel_parent.c.child_control_id.in_(control_ids))
    )
    parent_rows = (await conn.execute(parent_q)).fetchall()

    # Children relationships
    children_q = (
        select(rel_parent.c.parent_control_id, rel_parent.c.child_control_id)
        .where(_is_current(rel_parent.c.tx_to))
        .where(rel_parent.c.parent_control_id.in_(control_ids))
    )
    children_rows = (await conn.execute(children_q)).fetchall()

    # Owns functions (with names)
    owns_func_q = (
        select(
            rel_owns_func.c.control_id,
            rel_owns_func.c.node_id,
            ver_function.c.name,
        )
        .outerjoin(ver_function, and_(
            ver_function.c.ref_node_id == rel_owns_func.c.node_id,
            _is_current(ver_function.c.tx_to),
        ))
        .where(_is_current(rel_owns_func.c.tx_to))
        .where(rel_owns_func.c.control_id.in_(control_ids))
    )
    owns_func_rows = (await conn.execute(owns_func_q)).mappings().all()

    # Owns locations (with names)
    owns_loc_q = (
        select(
            rel_owns_loc.c.control_id,
            rel_owns_loc.c.node_id,
            ver_location.c.names[1].label("name"),
        )
        .outerjoin(ver_location, and_(
            ver_location.c.ref_node_id == rel_owns_loc.c.node_id,
            _is_current(ver_location.c.tx_to),
        ))
        .where(_is_current(rel_owns_loc.c.tx_to))
        .where(rel_owns_loc.c.control_id.in_(control_ids))
    )
    owns_loc_rows = (await conn.execute(owns_loc_q)).mappings().all()

    # Related functions (with names)
    related_func_q = (
        select(
            rel_related_func.c.control_id,
            rel_related_func.c.node_id,
            ver_function.c.name,
        )
        .outerjoin(ver_function, and_(
            ver_function.c.ref_node_id == rel_related_func.c.node_id,
            _is_current(ver_function.c.tx_to),
        ))
        .where(_is_current(rel_related_func.c.tx_to))
        .where(rel_related_func.c.control_id.in_(control_ids))
    )
    related_func_rows = (await conn.execute(related_func_q)).mappings().all()

    # Related locations (with names)
    related_loc_q = (
        select(
            rel_related_loc.c.control_id,
            rel_related_loc.c.node_id,
            ver_location.c.names[1].label("name"),
        )
        .outerjoin(ver_location, and_(
            ver_location.c.ref_node_id == rel_related_loc.c.node_id,
            _is_current(ver_location.c.tx_to),
        ))
        .where(_is_current(rel_related_loc.c.tx_to))
        .where(rel_related_loc.c.control_id.in_(control_ids))
    )
    related_loc_rows = (await conn.execute(related_loc_q)).mappings().all()

    # Risk themes (with labels)
    risk_q = (
        select(
            rel_risk_theme.c.control_id,
            rel_risk_theme.c.theme_id,
            rel_risk_theme.c.risk_theme_label,
        )
        .where(_is_current(rel_risk_theme.c.tx_to))
        .where(rel_risk_theme.c.control_id.in_(control_ids))
    )
    risk_rows = (await conn.execute(risk_q)).mappings().all()

    # Assemble
    for cid in control_ids:
        result[cid] = ControlRelationshipsResponse()

    for child_id, parent_id in parent_rows:
        if child_id in result:
            result[child_id].parent = NamedItem(id=parent_id)

    children_map: dict[str, list[NamedItem]] = defaultdict(list)
    for parent_id, child_id in children_rows:
        children_map[parent_id].append(NamedItem(id=child_id))
    for cid, children in children_map.items():
        if cid in result:
            result[cid].children = children

    for r in owns_func_rows:
        cid = r["control_id"]
        if cid in result:
            result[cid].owns_functions.append(NamedItem(id=r["node_id"], name=r["name"]))

    for r in owns_loc_rows:
        cid = r["control_id"]
        if cid in result:
            result[cid].owns_locations.append(NamedItem(id=r["node_id"], name=r["name"]))

    for r in related_func_rows:
        cid = r["control_id"]
        if cid in result:
            result[cid].related_functions.append(NamedItem(id=r["node_id"], name=r["name"]))

    for r in related_loc_rows:
        cid = r["control_id"]
        if cid in result:
            result[cid].related_locations.append(NamedItem(id=r["node_id"], name=r["name"]))

    for r in risk_rows:
        cid = r["control_id"]
        if cid in result:
            result[cid].risk_themes.append(NamedItem(id=r["theme_id"], name=r["risk_theme_label"]))

    return result


async def _load_enrichment(conn, control_ids: list[str]) -> dict[str, dict]:
    """Load AI enrichment data for a batch of controls."""
    cols = [
        ai_enrichment.c.ref_control_id,
        ai_enrichment.c.summary,
        ai_enrichment.c.control_as_event,
        ai_enrichment.c.control_as_issues,
    ]
    for col_name in _L1_YES_NO_COLS + _L2_YES_NO_COLS:
        cols.append(getattr(ai_enrichment.c, col_name))

    q = (
        select(*cols)
        .where(_is_current(ai_enrichment.c.tx_to))
        .where(ai_enrichment.c.ref_control_id.in_(control_ids))
    )
    rows = (await conn.execute(q)).mappings().all()

    result = {}
    for r in rows:
        cid = r["ref_control_id"]
        data = {}
        for col_name in _L1_YES_NO_COLS + _L2_YES_NO_COLS:
            data[col_name] = r[col_name]
        data["summary"] = r["summary"]
        data["control_as_event"] = r["control_as_event"]
        data["control_as_issues"] = r["control_as_issues"]
        result[cid] = data
    return result


async def _load_taxonomy(conn, control_ids: list[str]) -> dict[str, dict]:
    """Load AI taxonomy data for a batch of controls."""
    q = (
        select(
            ai_taxonomy.c.ref_control_id,
            ai_taxonomy.c.primary_risk_theme_id,
            ai_taxonomy.c.secondary_risk_theme_id,
        )
        .where(_is_current(ai_taxonomy.c.tx_to))
        .where(ai_taxonomy.c.ref_control_id.in_(control_ids))
    )
    rows = (await conn.execute(q)).mappings().all()

    result = {}
    for r in rows:
        result[r["ref_control_id"]] = {
            "primary_risk_theme_id": r["primary_risk_theme_id"],
            "secondary_risk_theme_id": r["secondary_risk_theme_id"],
        }
    return result


async def _load_similar_controls(
    conn, control_ids: list[str],
) -> dict[str, list[SimilarControlResponse]]:
    """Load precomputed similar controls for a batch of controls."""
    q = (
        select(
            similar_controls.c.ref_control_id,
            similar_controls.c.similar_control_id,
            similar_controls.c.rank,
            similar_controls.c.score,
        )
        .where(_is_current(similar_controls.c.tx_to))
        .where(similar_controls.c.ref_control_id.in_(control_ids))
        .order_by(similar_controls.c.ref_control_id, similar_controls.c.rank)
    )
    rows = (await conn.execute(q)).mappings().all()

    result: dict[str, list[SimilarControlResponse]] = {}
    for r in rows:
        cid = r["ref_control_id"]
        if cid not in result:
            result[cid] = []
        result[cid].append(SimilarControlResponse(
            control_id=r["similar_control_id"],
            score=r["score"],
            rank=r["rank"],
        ))
    return result
