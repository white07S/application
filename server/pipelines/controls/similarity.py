"""Precompute similar controls via hybrid multi-feature scoring.

Supports two modes:
1. Full rebuild: O(n²) recomputation of all controls (initial load, monthly safety net)
2. Incremental (Option D+): O(Δ×n) for daily delta uploads
   - DELETE phase: rescan controls that pointed to changed controls
   - INSERT phase: new/changed controls scored against all, with reverse kth_score check
   - Hub guardrail: falls back to full rebuild if affected set explodes
   - Crash-safe: single atomic transaction for all DB writes

Results are stored in ai_controls_similar_controls with temporal versioning.
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from sqlalchemy import insert, select, update, and_

from server.config.postgres import get_engine
from server.logging_config import get_logger
from server.pipelines.controls.model_runners.common import FEATURE_NAMES, MASK_COLUMN_NAMES
from server.pipelines.controls.schema import (
    ai_controls_model_clean_text as clean_text_tbl,
    ai_controls_similar_controls as similar_tbl,
    src_controls_rel_parent as rel_parent_tbl,
)

logger = get_logger(name=__name__)

# ── Constants ────────────────────────────────────────────────────────

# NPZ field names (with _embedding suffix)
_NPZ_FIELDS = [f"{f}_embedding" for f in FEATURE_NAMES]

TOP_K_NEIGHBORS = 50      # semantic neighbors per feature (full rebuild)
TOP_SIMILAR = 4            # final similar controls per control
CHUNK_SIZE = 500           # controls per chunk for dot product
DUP_THRESHOLD = 0.99       # cosine sim above this = inherited/copied text
DUP_CAP_SCORE = 0.3        # capped score for duplicated features
SEMANTIC_WEIGHT = 0.6      # weight for cosine similarity in hybrid
KEYWORD_WEIGHT = 0.4       # weight for Jaccard in hybrid
DIVERSITY_BONUS = 0.05     # multiplier per diverse feature
DIVERSE_MIN_SCORE = 0.2    # minimum hybrid_f to count as "diverse"
ZERO_NORM_THRESHOLD = 0.01 # L2 norm below this = missing vector
BATCH_INSERT_SIZE = 5000   # rows per insert batch

# Incremental mode constants
HUB_GUARDRAIL_THRESHOLD = 20_000  # if affected set > this, fallback to full rebuild

_TOKEN_RE = re.compile(r"[a-z0-9]+")


# ── Scoring function (shared between full and incremental) ─────────

def _compute_pair_score(
    i: int,
    j: int,
    feature_embeddings: List[np.ndarray],
    feature_valid: List[np.ndarray],
    token_sets: List[Dict[int, frozenset]],
    parent_child_pairs: Set[Tuple[str, str]],
    control_ids: List[str],
) -> Optional[Tuple[float, Dict[str, float]]]:
    """Compute hybrid score between two controls.

    Returns (final_score, per_feature_scores) or None if pair is excluded.
    """
    cid_i = control_ids[i]
    cid_j = control_ids[j]

    # Exclude direct parent-child pairs
    pair_key = (cid_i, cid_j) if cid_i < cid_j else (cid_j, cid_i)
    if pair_key in parent_child_pairs:
        return None

    per_feature: Dict[str, float] = {}
    n_diverse = 0

    for f_idx, feat_name in enumerate(FEATURE_NAMES):
        if not feature_valid[f_idx][i] or not feature_valid[f_idx][j]:
            per_feature[feat_name] = 0.0
            continue

        cosine_f = float(feature_embeddings[f_idx][i] @ feature_embeddings[f_idx][j])
        cosine_f = max(0.0, min(1.0, cosine_f))

        tokens_i = token_sets[f_idx].get(i, frozenset())
        tokens_j = token_sets[f_idx].get(j, frozenset())
        if tokens_i and tokens_j:
            intersection = len(tokens_i & tokens_j)
            union = len(tokens_i | tokens_j)
            jaccard_f = intersection / union if union > 0 else 0.0
        else:
            jaccard_f = 0.0

        is_dup = cosine_f > DUP_THRESHOLD
        if is_dup:
            hybrid_f = DUP_CAP_SCORE
        else:
            hybrid_f = SEMANTIC_WEIGHT * cosine_f + KEYWORD_WEIGHT * jaccard_f

        per_feature[feat_name] = round(hybrid_f, 4)

        if hybrid_f > DIVERSE_MIN_SCORE and not is_dup:
            n_diverse += 1

    raw_score = sum(per_feature.values())
    diversity_multiplier = 1.0 + DIVERSITY_BONUS * n_diverse
    final_score = raw_score * diversity_multiplier

    return (final_score, per_feature)


def _rescan_control_top4(
    i: int,
    n: int,
    feature_embeddings: List[np.ndarray],
    feature_valid: List[np.ndarray],
    token_sets: List[Dict[int, frozenset]],
    parent_child_pairs: Set[Tuple[str, str]],
    control_ids: List[str],
    return_all_scores: bool = False,
) -> List[Tuple[int, float, Dict[str, float]]]:
    """Full rescan of control i against all n controls. Returns sorted top-4.

    If return_all_scores=True, returns scores for ALL controls (for reverse check reuse).
    Otherwise returns only top TOP_SIMILAR.
    """
    cid_i = control_ids[i]

    # Build parent-child exclusion set for control i
    excluded = set()
    excluded.add(i)
    for pid, cid in parent_child_pairs:
        if pid == cid_i:
            j_idx = next((idx for idx, c in enumerate(control_ids) if c == cid), None)
            if j_idx is not None:
                excluded.add(j_idx)
        elif cid == cid_i:
            j_idx = next((idx for idx, c in enumerate(control_ids) if c == pid), None)
            if j_idx is not None:
                excluded.add(j_idx)

    # Vectorized cosine similarities per feature (one matmul per feature)
    cosine_per_feature = np.zeros((len(FEATURE_NAMES), n), dtype=np.float32)
    for f_idx in range(len(FEATURE_NAMES)):
        if feature_valid[f_idx][i]:
            cosine_per_feature[f_idx] = feature_embeddings[f_idx][i] @ feature_embeddings[f_idx].T
            np.clip(cosine_per_feature[f_idx], 0.0, 1.0, out=cosine_per_feature[f_idx])
            # Zero out where j is invalid
            cosine_per_feature[f_idx] *= feature_valid[f_idx]

    # Quick cosine-only upper bound to find top candidates
    # For each j: sum of 0.6*cosine_f across features + maximum possible Jaccard bonus
    cosine_sum = (SEMANTIC_WEIGHT * cosine_per_feature).sum(axis=0)
    # Max possible score = cosine_sum + KEYWORD_WEIGHT * 1.0 * n_features + diversity
    # Use cosine_sum alone as fast filter — get top candidates
    n_candidates = max(TOP_SIMILAR * 10, 200)  # generous candidate set

    # Exclude self and parent-child
    for ex_idx in excluded:
        cosine_sum[ex_idx] = -1.0

    # Get top candidates by cosine
    if n_candidates < n:
        candidate_indices = np.argpartition(cosine_sum, -n_candidates)[-n_candidates:]
    else:
        candidate_indices = np.arange(n)

    # Full hybrid scoring only for candidates
    scored: List[Tuple[int, float, Dict[str, float]]] = []

    for j in candidate_indices:
        j = int(j)
        if j in excluded or cosine_sum[j] <= 0:
            continue

        per_feature: Dict[str, float] = {}
        n_diverse = 0

        for f_idx, feat_name in enumerate(FEATURE_NAMES):
            if not feature_valid[f_idx][i] or not feature_valid[f_idx][j]:
                per_feature[feat_name] = 0.0
                continue

            cosine_f = float(cosine_per_feature[f_idx][j])
            tokens_i = token_sets[f_idx].get(i, frozenset())
            tokens_j = token_sets[f_idx].get(j, frozenset())
            if tokens_i and tokens_j:
                intersection = len(tokens_i & tokens_j)
                union = len(tokens_i | tokens_j)
                jaccard_f = intersection / union if union > 0 else 0.0
            else:
                jaccard_f = 0.0

            is_dup = cosine_f > DUP_THRESHOLD
            if is_dup:
                hybrid_f = DUP_CAP_SCORE
            else:
                hybrid_f = SEMANTIC_WEIGHT * cosine_f + KEYWORD_WEIGHT * jaccard_f

            per_feature[feat_name] = round(hybrid_f, 4)
            if hybrid_f > DIVERSE_MIN_SCORE and not is_dup:
                n_diverse += 1

        base_score = sum(per_feature.values())
        final = base_score * (1.0 + DIVERSITY_BONUS * max(0, n_diverse - 1))
        final = round(final, 4)

        scored.append((j, final, per_feature))

    scored.sort(key=lambda x: x[1], reverse=True)

    if return_all_scores:
        return scored  # return all candidates (for reverse check reuse)
    return scored[:TOP_SIMILAR]


# ── Main entry point ────────────────────────────────────────────────

async def compute_similar_controls(
    embedding_arrays: Dict[str, Any],
    embeddings_index: Dict[str, Any],
    changed_control_ids: Optional[Set[str]] = None,
    new_control_ids: Optional[Set[str]] = None,
    progress_callback: Optional[Callable] = None,
    force_full_rebuild: bool = False,
) -> None:
    """Compute and store similar controls.

    Args:
        embedding_arrays: Dict mapping NPZ field names → numpy arrays [N, dim].
        embeddings_index: Dict with 'by_control_id' mapping.
        changed_control_ids: Controls whose embeddings changed (for incremental mode).
        new_control_ids: Newly added controls (for incremental mode).
        progress_callback: Optional async callback(step, processed, total, percent).
        force_full_rebuild: If True, always do full O(n²) recompute.
    """
    changed_control_ids = changed_control_ids or set()
    new_control_ids = new_control_ids or set()

    by_cid = embeddings_index.get("by_control_id", {})
    if not by_cid:
        logger.warning("No embeddings index found, skipping similarity computation")
        return

    # Build ordered control_id list and row index mapping
    control_ids: List[str] = []
    row_to_idx: Dict[int, int] = {}
    idx_to_cid: Dict[int, str] = {}
    cid_to_idx: Dict[str, int] = {}

    for cid, meta in sorted(by_cid.items()):
        row = meta.get("row") if isinstance(meta, dict) else None
        if row is None:
            continue
        try:
            row = int(row)
        except (ValueError, TypeError):
            continue
        idx = len(control_ids)
        control_ids.append(cid)
        row_to_idx[row] = idx
        idx_to_cid[idx] = cid
        cid_to_idx[cid] = idx

    n = len(control_ids)
    if n == 0:
        logger.warning("No controls with valid embeddings, skipping")
        return

    # Decide mode
    delta_cids = changed_control_ids | new_control_ids
    use_incremental = (
        not force_full_rebuild
        and len(delta_cids) > 0
        and len(delta_cids) < n  # don't use incremental if all controls changed
    )

    mode_label = "incremental" if use_incremental else "full rebuild"
    logger.info(
        "Starting similarity computation: mode={}, n={}, delta={}",
        mode_label, n, len(delta_cids),
    )

    # ── Common setup: load embeddings, tokens, parent-child ──────

    _P_START = 96
    _P_LOAD_END = 97
    _P_COMPUTE_END = 99

    if progress_callback:
        await progress_callback(f"Similar controls ({mode_label}): loading data", 0, n, _P_START)

    # Load and reindex embeddings
    feature_embeddings: List[np.ndarray] = []
    feature_valid: List[np.ndarray] = []

    for feat_name, npz_field in zip(FEATURE_NAMES, _NPZ_FIELDS):
        raw = embedding_arrays.get(npz_field)
        if raw is None:
            logger.warning("Missing embedding array '{}', using zeros", npz_field)
            feature_embeddings.append(np.zeros((n, 3072), dtype=np.float32))
            feature_valid.append(np.zeros(n, dtype=bool))
            continue

        dim = raw.shape[1] if len(raw.shape) == 2 else 3072
        reindexed = np.zeros((n, dim), dtype=np.float32)
        # Vectorized reindexing: build source/dest index arrays
        src_rows = np.array([r for r in row_to_idx.keys() if r < raw.shape[0]], dtype=np.intp)
        dst_rows = np.array([row_to_idx[r] for r in src_rows], dtype=np.intp)
        if len(src_rows) > 0:
            reindexed[dst_rows] = raw[src_rows].astype(np.float32)

        norms = np.linalg.norm(reindexed, axis=1, keepdims=True)
        valid_mask = (norms.ravel() > ZERO_NORM_THRESHOLD)
        norms = np.where(norms > ZERO_NORM_THRESHOLD, norms, 1.0)
        normalized = reindexed / norms

        feature_embeddings.append(normalized)
        feature_valid.append(valid_mask)

    # Build feature mask array from embeddings index (for diagnostics)
    # Mask is True = distinguishing, False = inherited/empty
    feature_mask = np.ones((len(FEATURE_NAMES), n), dtype=bool)  # default: all distinguishing
    for idx, cid in enumerate(control_ids):
        meta = by_cid.get(cid, {})
        if isinstance(meta, dict):
            for f_idx, mask_col in enumerate(MASK_COLUMN_NAMES):
                mask_val = meta.get(mask_col, True)
                feature_mask[f_idx][idx] = bool(mask_val)

    # Log mask vs validity statistics per feature
    for f_idx, feat_name in enumerate(FEATURE_NAMES):
        n_valid = int(feature_valid[f_idx].sum())
        n_masked = int((~feature_mask[f_idx]).sum())
        n_distinguishing = int((feature_valid[f_idx] & feature_mask[f_idx]).sum())
        logger.info(
            "Feature '{}': {} valid vectors, {} inherited (masked), {} distinguishing",
            feat_name, n_valid, n_masked, n_distinguishing,
        )

    # Load token sets and parent-child pairs
    engine = get_engine()
    async with engine.connect() as conn:
        token_sets = await _load_token_sets(conn, control_ids, idx_to_cid)
        parent_child_pairs = await _load_parent_child_pairs(conn)

    if progress_callback:
        await progress_callback(f"Similar controls ({mode_label}): computing", 0, n, _P_LOAD_END)

    # ── Mode dispatch ────────────────────────────────────────────

    if use_incremental:
        await _compute_incremental(
            control_ids=control_ids,
            cid_to_idx=cid_to_idx,
            n=n,
            feature_embeddings=feature_embeddings,
            feature_valid=feature_valid,
            token_sets=token_sets,
            parent_child_pairs=parent_child_pairs,
            changed_control_ids=changed_control_ids,
            new_control_ids=new_control_ids,
            progress_callback=progress_callback,
            p_start=_P_LOAD_END,
            p_end=_P_COMPUTE_END,
        )
    else:
        await _compute_full_rebuild(
            control_ids=control_ids,
            n=n,
            feature_embeddings=feature_embeddings,
            feature_valid=feature_valid,
            token_sets=token_sets,
            parent_child_pairs=parent_child_pairs,
            progress_callback=progress_callback,
            p_start=_P_LOAD_END,
            p_end=_P_COMPUTE_END,
        )


# ── Full rebuild (O(n²)) ────────────────────────────────────────────

async def _compute_full_rebuild(
    control_ids: List[str],
    n: int,
    feature_embeddings: List[np.ndarray],
    feature_valid: List[np.ndarray],
    token_sets: List[Dict[int, frozenset]],
    parent_child_pairs: Set[Tuple[str, str]],
    progress_callback: Optional[Callable] = None,
    p_start: float = 97,
    p_end: float = 99,
) -> None:
    """Full O(n²) similarity recomputation."""
    logger.info("Running full rebuild for {} controls", n)
    n_features = len(FEATURE_NAMES)

    # Phase: semantic nearest neighbors per feature (chunked dot product)
    semantic_neighbors: List[Dict[int, List[Tuple[int, float]]]] = []

    for f_idx in range(n_features):
        emb = feature_embeddings[f_idx]
        valid = feature_valid[f_idx]
        neighbors: Dict[int, List[Tuple[int, float]]] = {}

        for chunk_start in range(0, n, CHUNK_SIZE):
            chunk_end = min(chunk_start + CHUNK_SIZE, n)
            chunk = emb[chunk_start:chunk_end]
            sims = chunk @ emb.T

            for local_i in range(chunk_end - chunk_start):
                global_i = chunk_start + local_i
                if not valid[global_i]:
                    neighbors[global_i] = []
                    continue

                row_sims = sims[local_i].copy()
                row_sims[global_i] = -1.0
                row_sims[~valid] = -1.0

                if n <= TOP_K_NEIGHBORS:
                    top_indices = np.argsort(row_sims)[::-1][:n - 1]
                else:
                    top_indices = np.argpartition(row_sims, -TOP_K_NEIGHBORS)[-TOP_K_NEIGHBORS:]
                    top_indices = top_indices[np.argsort(row_sims[top_indices])[::-1]]

                neighbors[global_i] = [
                    (int(j), float(row_sims[j]))
                    for j in top_indices
                    if row_sims[j] > 0
                ]

        semantic_neighbors.append(neighbors)
        logger.info("Feature '{}': semantic neighbors computed", FEATURE_NAMES[f_idx])

    # Phase: hybrid scoring
    results: List[dict] = []

    for i in range(n):
        candidate_set: Set[int] = set()
        for f_idx in range(n_features):
            for j, _score in semantic_neighbors[f_idx].get(i, []):
                candidate_set.add(j)
        candidate_set.discard(i)

        if not candidate_set:
            continue

        scored: List[Tuple[int, float, Dict[str, float]]] = []
        for j in candidate_set:
            result = _compute_pair_score(
                i, j, feature_embeddings, feature_valid, token_sets,
                parent_child_pairs, control_ids,
            )
            if result is not None:
                scored.append((j, result[0], result[1]))

        scored.sort(key=lambda x: x[1], reverse=True)
        for rank, (j, score, feat_scores) in enumerate(scored[:TOP_SIMILAR], start=1):
            results.append({
                "ref_control_id": control_ids[i],
                "similar_control_id": control_ids[j],
                "rank": rank,
                "score": round(score, 4),
                "feature_scores": feat_scores,
            })

        if (i + 1) % 2000 == 0 or i + 1 == n:
            logger.info("Full rebuild: scored {}/{} controls", i + 1, n)
            if progress_callback:
                pct = p_start + (i + 1) / n * (p_end - p_start)
                await progress_callback(
                    f"Similar controls: scoring ({i + 1:,}/{n:,})",
                    i + 1, n, int(pct),
                )

    logger.info("Full rebuild scoring complete: {} rows", len(results))

    # Write: full replace (close all old, insert all new)
    await _write_full_replace(results)


async def _write_full_replace(results: List[dict]) -> None:
    """Atomically replace all similarity rows (full rebuild mode)."""
    tx_from = datetime.now(timezone.utc)
    engine = get_engine()

    async with engine.begin() as conn:
        await conn.execute(
            update(similar_tbl)
            .where(similar_tbl.c.tx_to.is_(None))
            .values(tx_to=tx_from)
        )
        for batch_start in range(0, len(results), BATCH_INSERT_SIZE):
            batch = results[batch_start:batch_start + BATCH_INSERT_SIZE]
            rows = [{**r, "tx_from": tx_from, "tx_to": None} for r in batch]
            await conn.execute(insert(similar_tbl), rows)

    logger.info("Full rebuild: stored {} similarity rows", len(results))


# ── Incremental (Option D+) ─────────────────────────────────────────

async def _compute_incremental(
    control_ids: List[str],
    cid_to_idx: Dict[str, int],
    n: int,
    feature_embeddings: List[np.ndarray],
    feature_valid: List[np.ndarray],
    token_sets: List[Dict[int, frozenset]],
    parent_child_pairs: Set[Tuple[str, str]],
    changed_control_ids: Set[str],
    new_control_ids: Set[str],
    progress_callback: Optional[Callable] = None,
    p_start: float = 97,
    p_end: float = 99,
) -> None:
    """Incremental similarity update (Option D+).

    Step 1: Load current top-4 + kth_score from DB
    Step 2: DELETE phase — rescan controls that pointed to changed controls
    Step 3: INSERT phase — score new/changed controls against all, reverse kth_score check
    Step 4: Atomic write of changes
    """
    delta_cids = changed_control_ids | new_control_ids
    logger.info(
        "Incremental similarity: {} changed, {} new, {} total corpus",
        len(changed_control_ids), len(new_control_ids), n,
    )

    # Step 1: Load current top-4 from DB
    engine = get_engine()

    # current_top4[idx] = [(similar_idx, score, rank, feature_scores), ...]
    current_top4: Dict[int, List[Tuple[int, float, int, Dict[str, float]]]] = defaultdict(list)
    # kth_score[idx] = score of the weakest neighbor (or 0.0)
    kth_score: Dict[int, float] = {}

    async with engine.connect() as conn:
        q = (
            select(
                similar_tbl.c.ref_control_id,
                similar_tbl.c.similar_control_id,
                similar_tbl.c.rank,
                similar_tbl.c.score,
                similar_tbl.c.feature_scores,
            )
            .where(similar_tbl.c.tx_to.is_(None))
        )
        rows = (await conn.execute(q)).mappings().all()

    for r in rows:
        ref_cid = r["ref_control_id"]
        sim_cid = r["similar_control_id"]
        ref_idx = cid_to_idx.get(ref_cid)
        sim_idx = cid_to_idx.get(sim_cid)
        if ref_idx is None or sim_idx is None:
            continue
        current_top4[ref_idx].append((
            sim_idx,
            float(r["score"]),
            int(r["rank"]),
            r["feature_scores"] or {},
        ))

    # Compute kth_score for all controls
    for idx in range(n):
        entries = current_top4.get(idx, [])
        if len(entries) >= TOP_SIMILAR:
            kth_score[idx] = min(e[1] for e in entries)
        else:
            kth_score[idx] = 0.0

    logger.info("Loaded current top-4 for {} controls", len(current_top4))

    # Track which controls' top-4 actually changed (for final write)
    modified_controls: Set[int] = set()

    # Step 2: DELETE phase
    # For changed controls (not new — new have no existing edges), find who points to them
    affected_set: Set[int] = set()

    for cid in changed_control_ids:
        changed_idx = cid_to_idx.get(cid)
        if changed_idx is None:
            continue
        # Find all controls that currently have this changed control in their top-4
        for ref_idx, entries in current_top4.items():
            for sim_idx, _score, _rank, _fs in entries:
                if sim_idx == changed_idx:
                    affected_set.add(ref_idx)
                    break

    logger.info(
        "DELETE phase: {} changed controls affect {} existing controls' top-4",
        len(changed_control_ids), len(affected_set),
    )

    # Hub guardrail
    if len(affected_set) > HUB_GUARDRAIL_THRESHOLD:
        logger.warning(
            "Hub guardrail triggered: affected_set={} > threshold={}. Falling back to full rebuild.",
            len(affected_set), HUB_GUARDRAIL_THRESHOLD,
        )
        await _compute_full_rebuild(
            control_ids=control_ids,
            n=n,
            feature_embeddings=feature_embeddings,
            feature_valid=feature_valid,
            token_sets=token_sets,
            parent_child_pairs=parent_child_pairs,
            progress_callback=progress_callback,
            p_start=p_start,
            p_end=p_end,
        )
        return

    # Rescan affected controls
    rescan_count = 0
    for ref_idx in affected_set:
        new_top4 = _rescan_control_top4(
            ref_idx, n, feature_embeddings, feature_valid, token_sets,
            parent_child_pairs, control_ids,
        )
        current_top4[ref_idx] = [
            (j, score, rank, fs) for rank, (j, score, fs) in enumerate(new_top4, start=1)
        ]
        if new_top4:
            kth_score[ref_idx] = new_top4[-1][1] if len(new_top4) >= TOP_SIMILAR else 0.0
        else:
            kth_score[ref_idx] = 0.0
        modified_controls.add(ref_idx)
        rescan_count += 1

        if rescan_count % 500 == 0:
            logger.info("DELETE phase: rescanned {}/{}", rescan_count, len(affected_set))

    logger.info("DELETE phase complete: rescanned {} controls", rescan_count)

    if progress_callback:
        pct = p_start + 0.3 * (p_end - p_start)
        await progress_callback(
            f"Similar controls: INSERT phase ({len(delta_cids)} controls)",
            rescan_count, n, int(pct),
        )

    # Step 3: INSERT phase
    # Pre-compute delta index set (fixes O(Δ²×n) generator bug)
    delta_idx_set = {cid_to_idx[c] for c in delta_cids if c in cid_to_idx}

    insert_count = 0
    for cid in delta_cids:
        x_idx = cid_to_idx.get(cid)
        if x_idx is None:
            continue

        # Compute X's top-4 against all controls (returns all scored candidates)
        x_all_scored = _rescan_control_top4(
            x_idx, n, feature_embeddings, feature_valid, token_sets,
            parent_child_pairs, control_ids,
            return_all_scores=True,
        )
        x_top4 = x_all_scored[:TOP_SIMILAR]
        current_top4[x_idx] = [
            (j, score, rank, fs) for rank, (j, score, fs) in enumerate(x_top4, start=1)
        ]
        if x_top4:
            kth_score[x_idx] = x_top4[-1][1] if len(x_top4) >= TOP_SIMILAR else 0.0
        else:
            kth_score[x_idx] = 0.0
        modified_controls.add(x_idx)

        # Reverse check: reuse scores from forward pass (cosine is symmetric)
        # x_all_scored already has score(x, y) for all candidates y.
        # Since our scoring is symmetric, score(y, x) ≈ score(x, y).
        for y_idx, score_xy, feat_scores_xy in x_all_scored:
            if y_idx in delta_idx_set:
                continue  # processed in its own iteration

            if score_xy > kth_score.get(y_idx, 0.0):
                y_entries = list(current_top4.get(y_idx, []))
                y_entries.append((x_idx, score_xy, 0, feat_scores_xy))
                y_entries.sort(key=lambda e: e[1], reverse=True)
                y_entries = y_entries[:TOP_SIMILAR]
                current_top4[y_idx] = [
                    (j, score, rank, fs)
                    for rank, (j, score, _, fs) in enumerate(y_entries, start=1)
                ]
                kth_score[y_idx] = y_entries[-1][1] if len(y_entries) >= TOP_SIMILAR else 0.0
                modified_controls.add(y_idx)

        insert_count += 1
        if insert_count % 50 == 0:
            logger.info("INSERT phase: processed {}/{}", insert_count, len(delta_cids))
            if progress_callback:
                pct = p_start + (0.3 + 0.6 * insert_count / len(delta_cids)) * (p_end - p_start)
                await progress_callback(
                    f"Similar controls: INSERT ({insert_count}/{len(delta_cids)})",
                    insert_count, len(delta_cids), int(pct),
                )

    logger.info(
        "INSERT phase complete: {} delta controls processed, {} total controls modified",
        insert_count, len(modified_controls),
    )

    # Step 4: Atomic write (only modified controls)
    if progress_callback:
        await progress_callback(
            f"Similar controls: writing {len(modified_controls)} modified controls",
            n, n, int(p_end - 0.5),
        )

    await _write_incremental(control_ids, current_top4, modified_controls)


async def _write_incremental(
    control_ids: List[str],
    current_top4: Dict[int, List[Tuple[int, float, int, Dict[str, float]]]],
    modified_controls: Set[int],
) -> None:
    """Atomically write only modified controls' similarity rows."""
    if not modified_controls:
        logger.info("No similarity changes to write")
        return

    tx_from = datetime.now(timezone.utc)
    engine = get_engine()

    modified_cids = [control_ids[idx] for idx in modified_controls]

    # Build new rows for all modified controls
    new_rows: List[dict] = []
    for idx in modified_controls:
        cid = control_ids[idx]
        for sim_idx, score, rank, feat_scores in current_top4.get(idx, []):
            new_rows.append({
                "ref_control_id": cid,
                "similar_control_id": control_ids[sim_idx],
                "rank": rank,
                "score": round(score, 4),
                "feature_scores": feat_scores,
                "tx_from": tx_from,
                "tx_to": None,
            })

    # Single atomic transaction
    async with engine.begin() as conn:
        # Close old rows for modified controls (batched to avoid param limit)
        for batch_start in range(0, len(modified_cids), 5000):
            batch_cids = modified_cids[batch_start:batch_start + 5000]
            await conn.execute(
                update(similar_tbl)
                .where(
                    and_(
                        similar_tbl.c.ref_control_id.in_(batch_cids),
                        similar_tbl.c.tx_to.is_(None),
                    )
                )
                .values(tx_to=tx_from)
            )

        # Insert new rows
        for batch_start in range(0, len(new_rows), BATCH_INSERT_SIZE):
            batch = new_rows[batch_start:batch_start + BATCH_INSERT_SIZE]
            await conn.execute(insert(similar_tbl), batch)

    logger.info(
        "Incremental write complete: {} controls updated, {} rows written",
        len(modified_controls), len(new_rows),
    )


# ── Helpers ──────────────────────────────────────────────────────────

async def _load_token_sets(
    conn,
    control_ids: List[str],
    idx_to_cid: Dict[int, str],
) -> List[Dict[int, frozenset]]:
    """Load clean text from PostgreSQL and tokenize into sets per feature."""
    n = len(control_ids)
    cid_to_idx = {cid: i for i, cid in enumerate(control_ids)}

    result: List[Dict[int, frozenset]] = [{} for _ in FEATURE_NAMES]

    batch_size = 10000
    cid_list = list(control_ids)

    for batch_start in range(0, len(cid_list), batch_size):
        batch_cids = cid_list[batch_start:batch_start + batch_size]

        q = (
            select(
                clean_text_tbl.c.ref_control_id,
                clean_text_tbl.c.control_title,
                clean_text_tbl.c.control_description,
                clean_text_tbl.c.evidence_description,
                clean_text_tbl.c.local_functional_information,
                clean_text_tbl.c.control_as_event,
                clean_text_tbl.c.control_as_issues,
            )
            .where(clean_text_tbl.c.tx_to.is_(None))
            .where(clean_text_tbl.c.ref_control_id.in_(batch_cids))
        )
        rows = (await conn.execute(q)).mappings().all()

        for r in rows:
            cid = r["ref_control_id"]
            idx = cid_to_idx.get(cid)
            if idx is None:
                continue

            for f_idx, feat_name in enumerate(FEATURE_NAMES):
                text_val = r.get(feat_name) or ""
                tokens = frozenset(_TOKEN_RE.findall(text_val.lower()))
                tokens = frozenset(t for t in tokens if len(t) >= 3)
                result[f_idx][idx] = tokens

    logger.info("Token sets loaded for {} controls", n)
    return result


async def _load_parent_child_pairs(conn) -> Set[Tuple[str, str]]:
    """Load all direct parent-child pairs as canonical (min, max) tuples."""
    q = (
        select(
            rel_parent_tbl.c.parent_control_id,
            rel_parent_tbl.c.child_control_id,
        )
        .where(rel_parent_tbl.c.tx_to.is_(None))
    )
    rows = (await conn.execute(q)).fetchall()

    pairs: Set[Tuple[str, str]] = set()
    for parent_id, child_id in rows:
        key = (parent_id, child_id) if parent_id < child_id else (child_id, parent_id)
        pairs.add(key)

    logger.info("Loaded {} parent-child pairs", len(pairs))
    return pairs
