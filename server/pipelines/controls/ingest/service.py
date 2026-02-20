"""Controls ingestion service (async PostgreSQL + Qdrant).

Reads controls JSONL + AI model outputs and inserts/updates records
in PostgreSQL using the ref/ver/rel temporal schema, with embeddings
upserted to Qdrant.

Supports initial load and delta detection:
- Source data delta: based on last_modified_on
- AI data delta: based on hash from model index
- Embedding delta: hash comparison → Qdrant upsert for changed controls
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
import orjson
from sqlalchemy import insert, select, update, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from server.config.postgres import get_engine
from server.logging_config import get_logger
from server.pipelines import storage
from server.pipelines.controls.schema import (
    src_controls_ref_control,
    src_controls_ver_control,
    src_controls_rel_parent,
    src_controls_rel_owns_function,
    src_controls_rel_owns_location,
    src_controls_rel_related_function,
    src_controls_rel_related_location,
    src_controls_rel_risk_theme,
    ai_controls_model_taxonomy,
    ai_controls_model_enrichment,
    ai_controls_model_clean_text,
)
from server.pipelines.orgs.schema import src_orgs_ref_node
from server.pipelines.risks.schema import src_risks_ref_theme
from server.pipelines.controls import qdrant_service
from server.pipelines.controls.model_runners.common import (
    FEATURE_NAMES,
    HASH_COLUMN_NAMES,
    MASK_COLUMN_NAMES,
)
from server.settings import get_settings

logger = get_logger(name=__name__)

_SETTINGS = get_settings()
BATCH_SIZE = _SETTINGS.postgres_write_batch_size
DEFAULT_EMBEDDING_DIM = 3072
EMBEDDING_FEATURES: List[tuple[str, str]] = [
    (f, f"{f}_embedding") for f in FEATURE_NAMES
]

# Qdrant named vector keys (feature names without _embedding suffix)
QDRANT_VECTOR_NAMES = FEATURE_NAMES


@dataclass
class IngestionCounts:
    """Tracks ingestion counts."""
    total: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    failed: int = 0
    processed: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class IngestionResult:
    """Result of ingestion operation."""
    success: bool
    message: str
    counts: IngestionCounts

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "total": self.counts.total,
            "new": self.counts.new,
            "changed": self.counts.changed,
            "unchanged": self.counts.unchanged,
            "failed": self.counts.failed,
            "processed": self.counts.processed,
            "errors": self.counts.errors[:10],
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _coerce_utc_iso(value: Any) -> Optional[str]:
    """Parse incoming date-like values as UTC and return ISO string."""
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None

        dt: Optional[datetime] = None
        iso_candidate = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso_candidate)
        except ValueError:
            pass

        if dt is None:
            for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d",
                "%d-%b-%Y %I:%M:%S %p",
            ):
                try:
                    dt = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue

        if dt is None:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.replace(microsecond=0).isoformat()


def _parse_timestamp(value: Any, fallback_iso: str) -> datetime:
    """Parse a timestamp value into a tz-aware datetime."""
    parsed = _coerce_utc_iso(value)
    iso = parsed if parsed is not None else fallback_iso
    return datetime.fromisoformat(iso)


def _parse_optional_timestamp(value: Any) -> Optional[datetime]:
    """Parse a timestamp value into a tz-aware datetime, or None."""
    parsed = _coerce_utc_iso(value)
    if parsed is None:
        return None
    return datetime.fromisoformat(parsed)


def _coerce_list_str(value: Any) -> List[str]:
    """Coerce a value to a list of strings, filtering None."""
    if not isinstance(value, list) or not value:
        return []
    return [str(v) for v in value if v is not None]


# ── File loading ─────────────────────────────────────────────────────

def load_controls_jsonl(jsonl_path: Path) -> List[Dict[str, Any]]:
    """Load all records from controls JSONL."""
    records = []
    with jsonl_path.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(orjson.loads(line))
    return records


def load_model_index(model_name: str, upload_id: str, suffix: str = ".jsonl") -> Dict[str, Any]:
    """Load a model's index sidecar file."""
    index_path = storage.get_model_index_path(model_name, upload_id, suffix)
    if not index_path.exists():
        return {}
    return orjson.loads(index_path.read_bytes())


def load_model_jsonl_by_id(model_name: str, upload_id: str) -> Dict[str, Dict[str, Any]]:
    """Load a model's JSONL output keyed by control_id."""
    output_path = storage.get_model_output_path(model_name, upload_id)
    if not output_path.exists():
        return {}
    result = {}
    with output_path.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = orjson.loads(line)
            cid = obj.get("control_id")
            if isinstance(cid, str):
                result[cid] = obj
    return result


def load_embeddings_npz(upload_id: str) -> Optional[Any]:
    """Load embeddings NPZ file."""
    npz_path = storage.get_model_output_path("embeddings", upload_id, ".npz")
    if not npz_path.exists():
        return None
    return np.load(npz_path, allow_pickle=True)


# ── PostgreSQL queries ───────────────────────────────────────────────

async def _get_existing_control_ids(conn) -> Dict[str, str]:
    """Get all existing control_ids and their last_modified_on from DB.

    Returns:
        Dict mapping control_id to last_modified_on value.
    """
    result = await conn.execute(
        select(
            src_controls_ver_control.c.ref_control_id,
            src_controls_ver_control.c.last_modified_on,
        ).where(src_controls_ver_control.c.tx_to.is_(None))
    )
    return {row.ref_control_id: row.last_modified_on for row in result}


async def _get_existing_model_hashes(conn, table) -> Dict[str, Optional[str]]:
    """Get current hash by control_id for an AI model table (enrichment, taxonomy)."""
    result = await conn.execute(
        select(table.c.ref_control_id, table.c.hash).where(table.c.tx_to.is_(None))
    )
    return {row.ref_control_id: row.hash for row in result}


async def _get_existing_clean_text_hashes(conn) -> Dict[str, Dict[str, Optional[str]]]:
    """Get current per-feature hashes from ai_controls_model_clean_text.

    Returns:
        Dict mapping control_id → {hash_control_title: ..., hash_control_description: ..., ...}
    """
    cols = [ai_controls_model_clean_text.c.ref_control_id]
    for hash_col_name in HASH_COLUMN_NAMES:
        cols.append(getattr(ai_controls_model_clean_text.c, hash_col_name))

    result = await conn.execute(
        select(*cols).where(ai_controls_model_clean_text.c.tx_to.is_(None))
    )

    out: Dict[str, Dict[str, Optional[str]]] = {}
    for row in result:
        cid = row.ref_control_id
        hashes = {}
        for hash_col_name in HASH_COLUMN_NAMES:
            hashes[hash_col_name] = getattr(row, hash_col_name, None)
        out[cid] = hashes
    return out


async def _load_valid_org_node_ids(conn) -> Set[str]:
    """Load all node_id values from src_orgs_ref_node."""
    result = await conn.execute(select(src_orgs_ref_node.c.node_id))
    return {row.node_id for row in result}


async def _load_theme_lookup(conn) -> Tuple[Set[str], Dict[Tuple[str, str], str]]:
    """Load theme lookup: (source_id, name) → internal theme_id.

    Returns:
        (valid_theme_ids, lookup) where:
        - valid_theme_ids: Set of all internal theme_id strings
        - lookup: Dict mapping (source_id, theme_name) → internal theme_id
    """
    result = await conn.execute(
        select(
            src_risks_ref_theme.c.theme_id,
            src_risks_ref_theme.c.source_id,
            src_risks_ver_theme.c.name,
        )
        .join(
            src_risks_ver_theme,
            src_risks_ver_theme.c.ref_theme_id == src_risks_ref_theme.c.theme_id,
        )
        .where(src_risks_ver_theme.c.tx_to.is_(None))
    )
    valid_ids: Set[str] = set()
    lookup: Dict[Tuple[str, str], str] = {}
    for row in result:
        valid_ids.add(row.theme_id)
        if row.source_id and row.name:
            lookup[(row.source_id, row.name)] = row.theme_id
    return valid_ids, lookup


# ── Batch execution helpers ──────────────────────────────────────────

async def _execute_inserts(conn, table, rows: List[dict], label: str) -> None:
    """Execute a batch INSERT of rows into a table."""
    if not rows:
        return
    await conn.execute(insert(table), rows)
    logger.debug("Inserted {} rows into {} ({})", len(rows), table.name, label)


async def _execute_updates(conn, table, column, values, set_values: dict, label: str) -> None:
    """Execute an UPDATE for matching column values."""
    if not values:
        return
    await conn.execute(
        update(table).where(
            and_(column.in_(values), table.c.tx_to.is_(None))
        ).values(**set_values)
    )
    logger.debug("Closed {} current rows in {} ({})", len(values), table.name, label)


# ── Record builders (return dicts for SQLAlchemy Core inserts) ────────

ENRICHMENT_KEYS = [
    "summary", "what_yes_no", "what_details", "where_yes_no", "where_details",
    "who_yes_no", "who_details", "when_yes_no", "when_details",
    "why_yes_no", "why_details", "what_why_yes_no", "what_why_details",
    "risk_theme_yes_no", "risk_theme_details", "roles", "process",
    "product", "service", "frequency_yes_no", "frequency_details",
    "preventative_detective_yes_no", "preventative_detective_details",
    "automation_level_yes_no", "automation_level_details",
    "followup_yes_no", "followup_details", "escalation_yes_no", "escalation_details",
    "evidence_yes_no", "evidence_details", "abbreviations_yes_no", "abbreviations_details",
    "control_as_issues", "control_as_event",
]


def _build_ver_control_row(control: Dict[str, Any], tx_from: datetime) -> dict:
    """Build a dict for inserting into src_controls_ver_control."""
    cid = control["control_id"]

    # Collect unlinked entries
    unlinked_risk_themes = []
    for rt in control.get("risk_theme", []) or []:
        if rt.get("risk_theme_number"):
            continue
        unlinked_risk_themes.append({
            "risk_theme": rt.get("risk_theme"),
            "taxonomy_number": rt.get("taxonomy_number"),
        })

    unlinked_related_functions = []
    for rf in control.get("related_functions", []) or []:
        if rf.get("related_function_id"):
            continue
        unlinked_related_functions.append({
            "comment": rf.get("related_functions_locations_comments"),
        })

    unlinked_related_locations = []
    for rl in control.get("related_locations", []) or []:
        if rl.get("related_location_id"):
            continue
        unlinked_related_locations.append({
            "comment": rl.get("related_functions_locations_comments"),
        })

    return {
        "ref_control_id": cid,
        "control_title": control.get("control_title"),
        "control_description": control.get("control_description"),
        "key_control": control.get("key_control"),
        "hierarchy_level": control.get("hierarchy_level"),
        "preventative_detective": control.get("preventative_detective"),
        "manual_automated": control.get("manual_automated"),
        "execution_frequency": control.get("execution_frequency"),
        "four_eyes_check": control.get("four_eyes_check"),
        "evidence_description": control.get("evidence_description"),
        "evidence_available_from": control.get("evidence_available_from"),
        "performance_measures_required": control.get("performance_measures_required"),
        "performance_measures_available_from": control.get("performance_measures_available_from"),
        "control_status": control.get("control_status"),
        "valid_from": _parse_optional_timestamp(control.get("valid_from")),
        "valid_until": _parse_optional_timestamp(control.get("valid_until")),
        "reason_for_deactivation": control.get("reason_for_deactivation"),
        "status_updates": control.get("status_updates"),
        "last_modified_on": _parse_timestamp(control.get("last_modified_on"), tx_from.isoformat()) if control.get("last_modified_on") else None,
        "control_owner": control.get("control_owner"),
        "control_owner_gpn": control.get("control_owner_gpn"),
        "control_instance_owner_role": control.get("control_instance_owner_role"),
        "control_administrator": _coerce_list_str(control.get("control_administrator", [])),
        "control_administrator_gpn": _coerce_list_str(control.get("control_administrator_gpn", [])),
        "control_delegate": control.get("control_delegate"),
        "control_delegate_gpn": control.get("control_delegate_gpn"),
        "control_assessor": control.get("control_assessor"),
        "control_assessor_gpn": control.get("control_assessor_gpn"),
        "is_assessor_control_owner": control.get("is_assessor_control_owner"),
        "sox_relevant": control.get("sox_relevant"),
        "ccar_relevant": control.get("ccar_relevant"),
        "bcbs239_relevant": control.get("bcbs239_relevant"),
        "ey_reliant": control.get("ey_reliant"),
        "sox_rationale": control.get("sox_rationale"),
        "local_functional_information": control.get("local_functional_information"),
        "kpci_governance_forum": control.get("kpci_governance_forum"),
        "financial_statement_line_item": control.get("financial_statement_line_item"),
        "it_application_system_supporting_control_instance": control.get("it_application_system_supporting_control_instance"),
        "additional_information_on_deactivation": control.get("additional_information_on_deactivation"),
        "control_created_by": control.get("control_created_by"),
        "control_created_by_gpn": control.get("control_created_by_gpn"),
        "control_created_on": _parse_timestamp(control.get("control_created_on"), tx_from.isoformat()) if control.get("control_created_on") else None,
        "last_control_modification_requested_by": control.get("last_control_modification_requested_by"),
        "last_control_modification_requested_by_gpn": control.get("last_control_modification_requested_by_gpn"),
        "last_modification_on": _parse_timestamp(control.get("last_modification_on"), tx_from.isoformat()) if control.get("last_modification_on") else None,
        "control_status_date_change": _parse_timestamp(control.get("control_status_date_change"), tx_from.isoformat()) if control.get("control_status_date_change") else None,
        "category_flags": _coerce_list_str(control.get("category_flags", [])),
        "sox_assertions": _coerce_list_str(control.get("sox_assertions", [])),
        "unlinked_risk_themes": unlinked_risk_themes,
        "unlinked_related_functions": unlinked_related_functions,
        "unlinked_related_locations": unlinked_related_locations,
        "tx_from": tx_from,
        "tx_to": None,
    }


def _build_relation_rows(
    control: Dict[str, Any],
    cid: str,
    tx_from: datetime,
    theme_lookup: Optional[Dict[Tuple[str, str], str]] = None,
) -> Dict[str, List[dict]]:
    """Build all relation table rows for a single control.

    Returns dict mapping table name -> list of row dicts.
    """
    rows: Dict[str, List[dict]] = {
        "parent": [],
        "owns_function": [],
        "owns_location": [],
        "related_function": [],
        "related_location": [],
        "risk_theme": [],
    }

    # Parent edge
    parent_id = control.get("parent_control_id")
    if parent_id:
        rows["parent"].append({
            "parent_control_id": parent_id,
            "child_control_id": cid,
            "tx_from": tx_from,
            "tx_to": None,
        })

    # Owning function
    func_id = control.get("owning_organization_function_id")
    if func_id:
        rows["owns_function"].append({
            "control_id": cid,
            "node_id": f"function:{func_id}",
            "tx_from": tx_from,
            "tx_to": None,
        })

    # Owning location
    loc_id = control.get("owning_organization_location_id")
    if loc_id:
        rows["owns_location"].append({
            "control_id": cid,
            "node_id": f"location:{loc_id}",
            "tx_from": tx_from,
            "tx_to": None,
        })

    # Related functions
    seen_rf: Set[str] = set()
    for rf in control.get("related_functions", []) or []:
        rf_id = rf.get("related_function_id")
        if rf_id:
            rf_key = str(rf_id)
            if rf_key in seen_rf:
                logger.warning(
                    "Duplicate related_function_id '{}' for control '{}'; skipping",
                    rf_key, cid,
                )
                continue
            seen_rf.add(rf_key)
            rows["related_function"].append({
                "control_id": cid,
                "node_id": f"function:{rf_id}",
                "comment": rf.get("related_functions_locations_comments"),
                "tx_from": tx_from,
                "tx_to": None,
            })

    # Related locations
    seen_rl: Set[str] = set()
    for rl in control.get("related_locations", []) or []:
        rl_id = rl.get("related_location_id")
        if rl_id:
            rl_key = str(rl_id)
            if rl_key in seen_rl:
                logger.warning(
                    "Duplicate related_location_id '{}' for control '{}'; skipping",
                    rl_key, cid,
                )
                continue
            seen_rl.add(rl_key)
            rows["related_location"].append({
                "control_id": cid,
                "node_id": f"location:{rl_id}",
                "comment": rl.get("related_functions_locations_comments"),
                "tx_from": tx_from,
                "tx_to": None,
            })

    # Risk theme edges — resolve source_id to internal hash-based theme_id
    seen_rt: Set[str] = set()
    for rt in control.get("risk_theme", []) or []:
        source_id = str(rt.get("risk_theme_number", "")).strip()
        if not source_id:
            continue
        theme_name = (rt.get("risk_theme") or "").strip()

        # Resolve to internal theme_id via lookup
        internal_id: Optional[str] = None
        if theme_lookup:
            internal_id = theme_lookup.get((source_id, theme_name))
            if not internal_id:
                # Fallback: try source_id-only match if only one theme has that source_id
                candidates = [tid for (sid, _), tid in theme_lookup.items() if sid == source_id]
                internal_id = candidates[0] if len(candidates) == 1 else None
        else:
            # Legacy fallback: use source_id directly
            internal_id = source_id

        if not internal_id:
            continue

        if internal_id in seen_rt:
            logger.warning(
                "Duplicate resolved theme_id '{}' for control '{}'; skipping",
                internal_id, cid,
            )
            continue
        seen_rt.add(internal_id)
        rows["risk_theme"].append({
            "control_id": cid,
            "theme_id": internal_id,
            "risk_theme_label": rt.get("risk_theme"),
            "taxonomy_ref": str(rt["taxonomy_number"]) if rt.get("taxonomy_number") is not None else None,
            "tx_from": tx_from,
            "tx_to": None,
        })

    return rows


# ── Main ingestion orchestrator ──────────────────────────────────────

async def run_controls_ingestion(
    batch_id: int,
    upload_id: str,
    progress_callback: Optional[Callable] = None,
) -> IngestionResult:
    """Run controls ingestion into PostgreSQL + Qdrant.

    Reads source JSONL + all AI model outputs and inserts/updates records.

    Args:
        batch_id: UploadBatch ID
        upload_id: Upload ID (e.g. UPL-2026-0001)
        progress_callback: Optional async callback(step, processed, total, percent)

    Returns:
        IngestionResult with counts.
    """
    counts = IngestionCounts()
    tx_from_iso = _now_iso()
    tx_from = datetime.fromisoformat(tx_from_iso)
    embeddings_npz: Optional[Any] = None

    try:
        # ── Load all files ───────────────────────────────────────
        source_path = storage.get_control_jsonl_path(upload_id)
        if not source_path.exists():
            return IngestionResult(
                success=False,
                message=f"Source JSONL not found: {source_path}",
                counts=counts,
            )

        logger.info("Loading source controls from {}", source_path)
        controls = load_controls_jsonl(source_path)
        counts.total = len(controls)

        logger.info("Loading AI model outputs for {}", upload_id)
        taxonomy_rows = load_model_jsonl_by_id("taxonomy", upload_id)
        enrichment_rows = load_model_jsonl_by_id("enrichment", upload_id)
        clean_text_rows = load_model_jsonl_by_id("clean_text", upload_id)

        # Load embeddings
        embeddings_npz = load_embeddings_npz(upload_id)
        embeddings_index = load_model_index("embeddings", upload_id, ".npz")
        embeddings_by_cid = embeddings_index.get("by_control_id", {})
        embedding_dim = int(embeddings_index.get("embedding_dim") or DEFAULT_EMBEDDING_DIM)

        embedding_arrays: Dict[str, Any] = {}
        embedding_last_modified_col: Optional[Any] = None
        if embeddings_npz is not None:
            npz_keys = set(getattr(embeddings_npz, "files", []))
            for _, npz_field in EMBEDDING_FEATURES:
                if npz_field in npz_keys:
                    vec_arr = embeddings_npz[npz_field]
                    embedding_arrays[npz_field] = vec_arr
                    if hasattr(vec_arr, "shape") and len(vec_arr.shape) == 2 and vec_arr.shape[1] > 0:
                        embedding_dim = int(vec_arr.shape[1])
                else:
                    logger.warning(
                        "Embedding feature array '{}' is missing in NPZ; using zero vectors",
                        npz_field,
                    )
            if "last_modified_on" in npz_keys:
                embedding_last_modified_col = embeddings_npz["last_modified_on"]

        logger.info(
            "Loaded: {} controls, {} taxonomy, {} enrichment, {} clean_text, {} embeddings",
            len(controls),
            len(taxonomy_rows),
            len(enrichment_rows),
            len(clean_text_rows),
            len(embeddings_by_cid),
        )
        logger.info("PostgreSQL writer config: batch_size={}", BATCH_SIZE)

        # ── Connect and ingest ───────────────────────────────────
        engine = get_engine()

        # Parallelize all startup queries using separate connections
        logger.info("Loading existing data in parallel (6 queries)...")

        async def _pq(query_fn, *args):
            """Run a query on its own connection from the pool."""
            async with engine.connect() as c:
                return await query_fn(c, *args)

        # Read current Qdrant hashes in parallel with PG queries
        qdrant_hashes_task = qdrant_service.read_current_hashes()

        (
            existing,
            existing_taxonomy_hashes,
            existing_enrichment_hashes,
            existing_clean_text_hashes,
            valid_node_ids,
            theme_lookup_result,
            current_qdrant_hashes,
        ) = await asyncio.gather(
            _pq(_get_existing_control_ids),
            _pq(_get_existing_model_hashes, ai_controls_model_taxonomy),
            _pq(_get_existing_model_hashes, ai_controls_model_enrichment),
            _pq(_get_existing_clean_text_hashes),
            _pq(_load_valid_org_node_ids),
            _pq(_load_theme_lookup),
            qdrant_hashes_task,
        )
        valid_theme_ids, theme_lookup = theme_lookup_result
        existing_ids = set(existing.keys())
        logger.info(
            "Parallel load complete: {} existing controls, {} org nodes, {} risk themes",
            len(existing_ids), len(valid_node_ids), len(valid_theme_ids),
        )

        if progress_callback:
            await progress_callback("Loading existing data", 0, counts.total, 5)

        async with engine.begin() as conn:
            logger.info("Connected to PostgreSQL, starting ingestion")

            # Accumulators for batch inserts
            ref_rows: List[dict] = []
            ver_rows: List[dict] = []
            rel_parent_rows: List[dict] = []
            rel_owns_func_rows: List[dict] = []
            rel_owns_loc_rows: List[dict] = []
            rel_related_func_rows: List[dict] = []
            rel_related_loc_rows: List[dict] = []
            rel_risk_theme_rows: List[dict] = []
            ai_taxonomy_rows: List[dict] = []
            ai_enrichment_rows: List[dict] = []
            ai_clean_text_rows: List[dict] = []

            # Control IDs that need version/relation closing
            cids_to_close_ver: List[str] = []
            cids_to_close_rel: List[str] = []
            # AI model control IDs that need closing
            cids_to_close_taxonomy: List[str] = []
            cids_to_close_enrichment: List[str] = []
            cids_to_close_clean_text: List[str] = []

            total_pending = 0

            for idx, control in enumerate(controls):
                cid_raw = control.get("control_id")
                if not isinstance(cid_raw, str) or not cid_raw.strip():
                    raise RuntimeError(f"Invalid control_id at row {idx}: {cid_raw!r}")
                cid = cid_raw.strip()

                is_new = cid not in existing_ids
                # Normalize both sides to ISO string for comparison
                # (old_lmo is datetime from DB, new_lmo is string from JSONL)
                old_lmo = _coerce_utc_iso(existing.get(cid))
                new_lmo = _coerce_utc_iso(control.get("last_modified_on"))
                source_changed = is_new or old_lmo != new_lmo

                if is_new:
                    counts.new += 1
                elif source_changed:
                    counts.changed += 1
                else:
                    counts.unchanged += 1

                if source_changed:
                    # Ref row (INSERT ... ON CONFLICT DO NOTHING for idempotency)
                    if is_new:
                        ref_rows.append({
                            "control_id": cid,
                            "created_at": tx_from,
                        })

                    # Close old version + relations if updating
                    if not is_new:
                        cids_to_close_ver.append(cid)
                        cids_to_close_rel.append(cid)

                    # New version row
                    ver_rows.append(_build_ver_control_row(control, tx_from))

                    # New relation rows
                    rels = _build_relation_rows(control, cid, tx_from, theme_lookup=theme_lookup)
                    rel_parent_rows.extend(rels["parent"])
                    rel_owns_func_rows.extend(rels["owns_function"])
                    rel_owns_loc_rows.extend(rels["owns_location"])
                    rel_related_func_rows.extend(rels["related_function"])
                    rel_related_loc_rows.extend(rels["related_location"])
                    rel_risk_theme_rows.extend(rels["risk_theme"])

                # AI Taxonomy
                tax_row = taxonomy_rows.get(cid)
                if tax_row:
                    incoming_hash = tax_row.get("hash")
                    if not isinstance(incoming_hash, str):
                        incoming_hash = None
                    existing_hash = existing_taxonomy_hashes.get(cid)
                    if existing_hash != incoming_hash:
                        if existing_hash is not None:
                            cids_to_close_taxonomy.append(cid)
                        model_run_ts = _parse_timestamp(tax_row.get("last_modified_on"), tx_from_iso)
                        primary_reasoning = tax_row.get("primary_risk_theme_reasoning")
                        secondary_reasoning = tax_row.get("secondary_risk_theme_reasoning")
                        ai_taxonomy_rows.append({
                            "ref_control_id": cid,
                            "hash": incoming_hash,
                            "model_run_timestamp": model_run_ts,
                            "parent_primary_risk_theme_id": str(tax_row["parent_primary_risk_theme_id"]) if tax_row.get("parent_primary_risk_theme_id") is not None else None,
                            "primary_risk_theme_id": str(tax_row["primary_risk_theme_id"]) if tax_row.get("primary_risk_theme_id") is not None else None,
                            "primary_risk_theme_reasoning": _coerce_list_str(primary_reasoning) if primary_reasoning else None,
                            "parent_secondary_risk_theme_id": str(tax_row["parent_secondary_risk_theme_id"]) if tax_row.get("parent_secondary_risk_theme_id") is not None else None,
                            "secondary_risk_theme_id": str(tax_row["secondary_risk_theme_id"]) if tax_row.get("secondary_risk_theme_id") is not None else None,
                            "secondary_risk_theme_reasoning": _coerce_list_str(secondary_reasoning) if secondary_reasoning else None,
                            "tx_from": tx_from,
                            "tx_to": None,
                        })
                        existing_taxonomy_hashes[cid] = incoming_hash

                # AI Enrichment
                enrich_row = enrichment_rows.get(cid)
                if enrich_row:
                    incoming_hash = enrich_row.get("hash")
                    if not isinstance(incoming_hash, str):
                        incoming_hash = None
                    existing_hash = existing_enrichment_hashes.get(cid)
                    if existing_hash != incoming_hash:
                        if existing_hash is not None:
                            cids_to_close_enrichment.append(cid)
                        model_run_ts = _parse_timestamp(enrich_row.get("last_modified_on"), tx_from_iso)
                        row_dict = {
                            "ref_control_id": cid,
                            "hash": incoming_hash,
                            "model_run_timestamp": model_run_ts,
                            "tx_from": tx_from,
                            "tx_to": None,
                        }
                        for key in ENRICHMENT_KEYS:
                            row_dict[key] = enrich_row.get(key)
                        ai_enrichment_rows.append(row_dict)
                        existing_enrichment_hashes[cid] = incoming_hash

                # AI Clean Text (6 per-feature hashes)
                clean_row = clean_text_rows.get(cid)
                if clean_row:
                    incoming_ct_hashes = {
                        h: clean_row.get(h) for h in HASH_COLUMN_NAMES
                    }
                    existing_ct_hashes = existing_clean_text_hashes.get(cid, {})
                    ct_changed = any(
                        incoming_ct_hashes.get(h) != existing_ct_hashes.get(h)
                        for h in HASH_COLUMN_NAMES
                    )
                    if ct_changed:
                        if existing_ct_hashes:
                            cids_to_close_clean_text.append(cid)
                        model_run_ts = _parse_timestamp(clean_row.get("last_modified_on"), tx_from_iso)
                        row_dict = {
                            "ref_control_id": cid,
                            "model_run_timestamp": model_run_ts,
                            "control_title": clean_row.get("control_title"),
                            "control_description": clean_row.get("control_description"),
                            "evidence_description": clean_row.get("evidence_description"),
                            "local_functional_information": clean_row.get("local_functional_information"),
                            "control_as_event": clean_row.get("control_as_event"),
                            "control_as_issues": clean_row.get("control_as_issues"),
                            "tx_from": tx_from,
                            "tx_to": None,
                        }
                        for h in HASH_COLUMN_NAMES:
                            row_dict[h] = incoming_ct_hashes.get(h)
                        ai_clean_text_rows.append(row_dict)
                        existing_clean_text_hashes[cid] = incoming_ct_hashes

                # Embedding delta detection is done after the loop via Qdrant hashes
                # (no per-control work needed here)

                counts.processed += 1

                # Track total pending rows for batch flushing
                total_pending = (
                    len(ref_rows) + len(ver_rows) +
                    len(rel_parent_rows) + len(rel_owns_func_rows) + len(rel_owns_loc_rows) +
                    len(rel_related_func_rows) + len(rel_related_loc_rows) + len(rel_risk_theme_rows) +
                    len(ai_taxonomy_rows) + len(ai_enrichment_rows) + len(ai_clean_text_rows)
                )

                if total_pending >= BATCH_SIZE:
                    await _flush_batch(
                        conn, tx_from,
                        ref_rows, ver_rows,
                        cids_to_close_ver, cids_to_close_rel,
                        rel_parent_rows, rel_owns_func_rows, rel_owns_loc_rows,
                        rel_related_func_rows, rel_related_loc_rows, rel_risk_theme_rows,
                        cids_to_close_taxonomy, cids_to_close_enrichment, cids_to_close_clean_text,
                        ai_taxonomy_rows, ai_enrichment_rows, ai_clean_text_rows,
                        f"batch-{idx}",
                        valid_node_ids=valid_node_ids,
                        valid_theme_ids=valid_theme_ids,
                    )
                    # Clear accumulators
                    ref_rows.clear()
                    ver_rows.clear()
                    cids_to_close_ver.clear()
                    cids_to_close_rel.clear()
                    rel_parent_rows.clear()
                    rel_owns_func_rows.clear()
                    rel_owns_loc_rows.clear()
                    rel_related_func_rows.clear()
                    rel_related_loc_rows.clear()
                    rel_risk_theme_rows.clear()
                    cids_to_close_taxonomy.clear()
                    cids_to_close_enrichment.clear()
                    cids_to_close_clean_text.clear()
                    ai_taxonomy_rows.clear()
                    ai_enrichment_rows.clear()
                    ai_clean_text_rows.clear()

                # Progress callback
                if progress_callback and (idx + 1) % max(1, BATCH_SIZE) == 0:
                    total = max(counts.total, 1)
                    pct = 10 + int((counts.processed / total) * 80)
                    await progress_callback(
                        "Ingesting controls",
                        counts.processed,
                        counts.total,
                        min(pct, 90),
                    )

            # Flush remaining
            await _flush_batch(
                conn, tx_from,
                ref_rows, ver_rows,
                cids_to_close_ver, cids_to_close_rel,
                rel_parent_rows, rel_owns_func_rows, rel_owns_loc_rows,
                rel_related_func_rows, rel_related_loc_rows, rel_risk_theme_rows,
                cids_to_close_taxonomy, cids_to_close_enrichment, cids_to_close_clean_text,
                ai_taxonomy_rows, ai_enrichment_rows, ai_clean_text_rows,
                "final",
                valid_node_ids=valid_node_ids,
                valid_theme_ids=valid_theme_ids,
            )

        # Transaction committed at this point

        # ── Qdrant delta upsert (outside Postgres transaction) ──────────
        if embeddings_npz is not None and embeddings_by_cid:
            if progress_callback:
                await progress_callback("Computing embedding delta...", counts.processed, counts.total, 91)

            # Build incoming hashes + masks from embeddings index (per-feature)
            incoming_emb_hashes: Dict[str, Dict[str, Optional[str]]] = {}
            for cid_str, meta in embeddings_by_cid.items():
                if not isinstance(meta, dict):
                    continue
                hashes: Dict[str, Any] = {h: meta.get(h) for h in HASH_COLUMN_NAMES}
                for m in MASK_COLUMN_NAMES:
                    hashes[m] = meta.get(m, True)
                incoming_emb_hashes[cid_str] = hashes

            # Per-feature delta detection against Qdrant
            new_cids, changed_features, unchanged_cids = qdrant_service.compute_embedding_delta(
                incoming_emb_hashes, current_qdrant_hashes,
            )

            # Build embedding_data for controls that need Qdrant updates
            all_upsert_cids = new_cids | set(changed_features.keys())
            embedding_data: Dict[str, Dict[str, Any]] = {}

            for cid_str in all_upsert_cids:
                emb_meta = embeddings_by_cid.get(cid_str)
                row_idx: Optional[int] = None
                row_idx_raw = emb_meta.get("row") if isinstance(emb_meta, dict) else None
                if row_idx_raw is not None:
                    try:
                        row_idx = int(row_idx_raw)
                    except Exception:
                        row_idx = None
                if row_idx is not None and row_idx < 0:
                    row_idx = None

                cid_vectors: Dict[str, Any] = {}
                for feature_name, npz_field in EMBEDDING_FEATURES:
                    vec_arr = embedding_arrays.get(npz_field)
                    raw_vec = None
                    if vec_arr is not None and row_idx is not None:
                        try:
                            if row_idx < vec_arr.shape[0]:
                                raw_vec = vec_arr[row_idx]
                        except Exception:
                            raw_vec = None
                    cid_vectors[feature_name] = raw_vec
                embedding_data[cid_str] = cid_vectors

            # Progress adapter
            async def _qdrant_progress(step: str, uploaded: int, total: int):
                if progress_callback:
                    await progress_callback(step, counts.processed, counts.total, 93)

            # Upsert new controls (full points)
            points_new = await qdrant_service.upsert_new_controls(
                sorted(new_cids), embedding_data, incoming_emb_hashes,
                progress_callback=_qdrant_progress,
            )

            # Update changed features on existing controls
            points_updated = await qdrant_service.update_changed_features(
                changed_features, embedding_data, incoming_emb_hashes,
                progress_callback=_qdrant_progress,
            )

            total_qdrant = points_new + points_updated

            # Wait for indexing if we did a large batch (HNSW was toggled)
            if points_new > qdrant_service.HNSW_TOGGLE_THRESHOLD:
                if progress_callback:
                    await progress_callback("Waiting for Qdrant indexing...", counts.processed, counts.total, 95)

                async def _indexing_progress(step: str, indexed: int, total: int):
                    if progress_callback:
                        await progress_callback(step, counts.processed, counts.total, 95)

                green_status = await qdrant_service.wait_for_collection_green(
                    progress_callback=_indexing_progress
                )
                if not green_status:
                    logger.warning("Qdrant indexing timeout")

            logger.info(
                "Qdrant delta complete: {} new, {} updated, {} unchanged",
                points_new, points_updated, len(unchanged_cids),
            )

            if progress_callback:
                await progress_callback(f"Qdrant complete ({total_qdrant} points)", counts.processed, counts.total, 96)

            # ── Compute similar controls (incremental) ────────────
            if embedding_arrays and len(embedding_arrays) >= len(EMBEDDING_FEATURES):
                from server.pipelines.controls.similarity import compute_similar_controls

                await compute_similar_controls(
                    embedding_arrays=embedding_arrays,
                    embeddings_index=embeddings_index,
                    changed_control_ids=set(changed_features.keys()),
                    new_control_ids=new_cids,
                    progress_callback=progress_callback,
                )

        elif embeddings_npz is not None:
            logger.info("No embeddings index found, skipping Qdrant")

        logger.info(
            "Ingestion complete: total={}, new={}, changed={}, unchanged={}, failed={}",
            counts.total,
            counts.new,
            counts.changed,
            counts.unchanged,
            counts.failed,
        )

        return IngestionResult(
            success=True,
            message=(
                f"Ingestion completed. "
                f"Total: {counts.total}, New: {counts.new}, "
                f"Changed: {counts.changed}, Unchanged: {counts.unchanged}, "
                f"Failed: {counts.failed}"
            ),
            counts=counts,
        )

    except Exception as e:
        logger.exception("Ingestion failed: {}", e)
        counts.errors.append(str(e))
        return IngestionResult(
            success=False,
            message=f"Ingestion failed: {e}",
            counts=counts,
        )
    finally:
        if embeddings_npz is not None:
            try:
                embeddings_npz.close()
            except Exception:
                logger.warning("Failed to close embeddings NPZ cleanly")


async def _flush_batch(
    conn,
    tx_from: datetime,
    ref_rows: List[dict],
    ver_rows: List[dict],
    cids_to_close_ver: List[str],
    cids_to_close_rel: List[str],
    rel_parent_rows: List[dict],
    rel_owns_func_rows: List[dict],
    rel_owns_loc_rows: List[dict],
    rel_related_func_rows: List[dict],
    rel_related_loc_rows: List[dict],
    rel_risk_theme_rows: List[dict],
    cids_to_close_taxonomy: List[str],
    cids_to_close_enrichment: List[str],
    cids_to_close_clean_text: List[str],
    ai_taxonomy_rows: List[dict],
    ai_enrichment_rows: List[dict],
    ai_clean_text_rows: List[dict],
    label: str,
    valid_node_ids: Optional[Set[str]] = None,
    valid_theme_ids: Optional[Set[str]] = None,
) -> None:
    """Flush accumulated rows to PostgreSQL in correct dependency order."""
    has_work = (
        ref_rows or ver_rows or cids_to_close_ver or cids_to_close_rel or
        rel_parent_rows or rel_owns_func_rows or rel_owns_loc_rows or
        rel_related_func_rows or rel_related_loc_rows or rel_risk_theme_rows or
        cids_to_close_taxonomy or cids_to_close_enrichment or cids_to_close_clean_text or
        ai_taxonomy_rows or ai_enrichment_rows or ai_clean_text_rows
    )
    if not has_work:
        return

    close_values = {"tx_to": tx_from}

    # 1. Insert new ref_control rows (ON CONFLICT DO NOTHING for idempotency)
    if ref_rows:
        stmt = pg_insert(src_controls_ref_control).on_conflict_do_nothing(
            index_elements=["control_id"]
        )
        await conn.execute(stmt, ref_rows)
        logger.debug("Inserted {} ref_control rows ({})", len(ref_rows), label)

    # 2. Close old versions for changed controls
    if cids_to_close_ver:
        await _execute_updates(
            conn, src_controls_ver_control,
            src_controls_ver_control.c.ref_control_id,
            cids_to_close_ver, close_values, f"close-ver-{label}",
        )

    # 3. Close old relation edges for changed controls
    if cids_to_close_rel:
        # Parent edges: close where either parent or child matches
        await conn.execute(
            update(src_controls_rel_parent).where(
                and_(
                    src_controls_rel_parent.c.tx_to.is_(None),
                    (
                        src_controls_rel_parent.c.parent_control_id.in_(cids_to_close_rel)
                        | src_controls_rel_parent.c.child_control_id.in_(cids_to_close_rel)
                    ),
                )
            ).values(**close_values)
        )

        # Other relation tables: close by control_id
        for rel_table in [
            src_controls_rel_owns_function,
            src_controls_rel_owns_location,
            src_controls_rel_related_function,
            src_controls_rel_related_location,
            src_controls_rel_risk_theme,
        ]:
            await _execute_updates(
                conn, rel_table,
                rel_table.c.control_id,
                cids_to_close_rel, close_values, f"close-rel-{rel_table.name}-{label}",
            )

    # 4. Insert new version rows
    if ver_rows:
        await _execute_inserts(conn, src_controls_ver_control, ver_rows, label)

    # 5. Filter relation rows for valid FK targets, then insert
    if valid_node_ids is not None:
        for rows_list, fk_col, tbl_name in [
            (rel_owns_func_rows, "node_id", "rel_owns_function"),
            (rel_owns_loc_rows, "node_id", "rel_owns_location"),
            (rel_related_func_rows, "node_id", "rel_related_function"),
            (rel_related_loc_rows, "node_id", "rel_related_location"),
        ]:
            before = len(rows_list)
            filtered = [r for r in rows_list if r[fk_col] in valid_node_ids]
            skipped = before - len(filtered)
            if skipped:
                logger.warning(
                    "{}: skipped {} rows with missing org node references ({})",
                    tbl_name, skipped, label,
                )
            rows_list[:] = filtered

    if valid_theme_ids is not None and rel_risk_theme_rows:
        before = len(rel_risk_theme_rows)
        filtered = [r for r in rel_risk_theme_rows if r["theme_id"] in valid_theme_ids]
        skipped = before - len(filtered)
        if skipped:
            logger.warning(
                "rel_risk_theme: skipped {} rows with missing theme references ({})",
                skipped, label,
            )
        rel_risk_theme_rows[:] = filtered

    if rel_parent_rows:
        await _execute_inserts(conn, src_controls_rel_parent, rel_parent_rows, label)
    if rel_owns_func_rows:
        await _execute_inserts(conn, src_controls_rel_owns_function, rel_owns_func_rows, label)
    if rel_owns_loc_rows:
        await _execute_inserts(conn, src_controls_rel_owns_location, rel_owns_loc_rows, label)
    if rel_related_func_rows:
        await _execute_inserts(conn, src_controls_rel_related_function, rel_related_func_rows, label)
    if rel_related_loc_rows:
        await _execute_inserts(conn, src_controls_rel_related_location, rel_related_loc_rows, label)
    if rel_risk_theme_rows:
        await _execute_inserts(conn, src_controls_rel_risk_theme, rel_risk_theme_rows, label)

    # 6. Close old AI model rows
    if cids_to_close_taxonomy:
        await _execute_updates(
            conn, ai_controls_model_taxonomy,
            ai_controls_model_taxonomy.c.ref_control_id,
            cids_to_close_taxonomy, close_values, f"close-taxonomy-{label}",
        )
    if cids_to_close_enrichment:
        await _execute_updates(
            conn, ai_controls_model_enrichment,
            ai_controls_model_enrichment.c.ref_control_id,
            cids_to_close_enrichment, close_values, f"close-enrichment-{label}",
        )
    if cids_to_close_clean_text:
        await _execute_updates(
            conn, ai_controls_model_clean_text,
            ai_controls_model_clean_text.c.ref_control_id,
            cids_to_close_clean_text, close_values, f"close-clean_text-{label}",
        )

    # 7. Insert new AI model rows
    if ai_taxonomy_rows:
        await _execute_inserts(conn, ai_controls_model_taxonomy, ai_taxonomy_rows, label)
    if ai_enrichment_rows:
        await _execute_inserts(conn, ai_controls_model_enrichment, ai_enrichment_rows, label)
    if ai_clean_text_rows:
        await _execute_inserts(conn, ai_controls_model_clean_text, ai_clean_text_rows, label)

    logger.debug("Flushed batch {} to PostgreSQL", label)
