"""Precompute similar controls via hybrid multi-feature scoring.

Similarity is computed only between L1 Active Key controls using 3 semantic
features (what, why, where). Each pair is scored by averaging per-feature
scores, where each feature score = (embedding_cosine + tfidf_cosine) / 2.

Thresholds:
  - score >= 0.90  →  "near_duplicate"
  - 0.60 <= score < 0.90  →  "weak_similar"
  - score < 0.60  →  discarded (not stored)

Supports two modes:
1. Full rebuild: O(n²) recomputation of all L1 Active Key controls
2. Incremental: O(Δ×n) for daily delta uploads

Results are stored in ai_controls_similar_controls with temporal versioning.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sparse_cosine_similarity
from sqlalchemy import insert, select, update, and_

from server.config.postgres import get_engine
from server.logging_config import get_logger
from server.pipelines.controls.model_runners.common import FEATURE_NAMES, MASK_COLUMN_NAMES
from server.pipelines.controls.schema import (
    ai_controls_model_feature_prep as feature_prep_tbl,
    ai_controls_similar_controls as similar_tbl,
    src_controls_rel_parent as rel_parent_tbl,
    src_controls_ver_control as ver_control_tbl,
)

logger = get_logger(name=__name__)

# ── Constants ────────────────────────────────────────────────────────

# NPZ field names (with _embedding suffix)
_NPZ_FIELDS = [f"{f}_embedding" for f in FEATURE_NAMES]

TOP_K_NEIGHBORS = 50      # semantic neighbors per feature (full rebuild)
TOP_SIMILAR = 3            # final similar controls per control
CHUNK_SIZE = 500           # controls per chunk for dot product
NEAR_DUPLICATE_THRESHOLD = 0.90
WEAK_SIMILAR_THRESHOLD = 0.60
ZERO_NORM_THRESHOLD = 0.01 # L2 norm below this = missing vector
BATCH_INSERT_SIZE = 5000   # rows per insert batch

# Incremental mode constants
HUB_GUARDRAIL_THRESHOLD = 20_000


def _categorize_score(score: float) -> Optional[str]:
    """Assign category label based on score threshold."""
    if score >= NEAR_DUPLICATE_THRESHOLD:
        return "near_duplicate"
    elif score >= WEAK_SIMILAR_THRESHOLD:
        return "weak_similar"
    return None


# ── TF-IDF computation ──────────────────────────────────────────────

def _build_tfidf_matrices(
    texts_per_feature: List[Dict[int, str]],
    n: int,
) -> List[Optional[csr_matrix]]:
    """Build TF-IDF sparse matrices for each feature.

    Returns list of sparse matrices (one per feature), or None if the
    feature has no non-empty texts.
    """
    matrices: List[Optional[csr_matrix]] = []

    for f_idx, feat_texts in enumerate(texts_per_feature):
        if not feat_texts:
            matrices.append(None)
            continue

        # Build corpus: all n controls, empty string for missing
        corpus = [""] * n
        for idx, text in feat_texts.items():
            corpus[idx] = text

        # Check if any non-empty text exists
        if not any(t.strip() for t in corpus):
            matrices.append(None)
            continue

        vectorizer = TfidfVectorizer(
            max_features=10000,
            min_df=1,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        tfidf_matrix = vectorizer.fit_transform(corpus)
        matrices.append(tfidf_matrix)
        logger.info(
            "TF-IDF feature '{}': vocab={}, non-empty={}",
            FEATURE_NAMES[f_idx],
            len(vectorizer.vocabulary_),
            sum(1 for t in corpus if t.strip()),
        )

    return matrices


# ── Scoring function ────────────────────────────────────────────────

def _compute_pair_score(
    i: int,
    j: int,
    feature_embeddings: List[np.ndarray],
    feature_valid: List[np.ndarray],
    tfidf_matrices: List[Optional[csr_matrix]],
    parent_child_pairs: Set[Tuple[str, str]],
    control_ids: List[str],
) -> Optional[Tuple[float, Dict[str, float]]]:
    """Compute hybrid score between two controls.

    Per-feature score = (embedding_cosine + tfidf_cosine) / 2
    Final score = mean of per-feature scores across features with data.

    Returns (final_score, per_feature_scores) or None if pair is excluded.
    """
    cid_i = control_ids[i]
    cid_j = control_ids[j]

    # Exclude direct parent-child pairs
    pair_key = (cid_i, cid_j) if cid_i < cid_j else (cid_j, cid_i)
    if pair_key in parent_child_pairs:
        return None

    per_feature: Dict[str, float] = {}
    feature_scores: List[float] = []

    for f_idx, feat_name in enumerate(FEATURE_NAMES):
        # Embedding cosine
        if feature_valid[f_idx][i] and feature_valid[f_idx][j]:
            embed_cos = float(feature_embeddings[f_idx][i] @ feature_embeddings[f_idx][j])
            embed_cos = max(0.0, min(1.0, embed_cos))
        else:
            embed_cos = 0.0

        # TF-IDF cosine
        tfidf_cos = 0.0
        if tfidf_matrices[f_idx] is not None:
            tfidf_i = tfidf_matrices[f_idx][i]
            tfidf_j = tfidf_matrices[f_idx][j]
            if tfidf_i.nnz > 0 and tfidf_j.nnz > 0:
                sim = sparse_cosine_similarity(tfidf_i, tfidf_j)
                tfidf_cos = float(sim[0, 0])
                tfidf_cos = max(0.0, min(1.0, tfidf_cos))

        # Per-feature score: average of both signals
        feat_score = (embed_cos + tfidf_cos) / 2.0
        per_feature[feat_name] = round(feat_score, 4)
        feature_scores.append(feat_score)

    # Final score: mean across features
    if not feature_scores:
        return None

    final_score = sum(feature_scores) / len(feature_scores)
    return (round(final_score, 4), per_feature)


def _rescan_control_top3(
    i: int,
    n: int,
    feature_embeddings: List[np.ndarray],
    feature_valid: List[np.ndarray],
    tfidf_matrices: List[Optional[csr_matrix]],
    parent_child_pairs: Set[Tuple[str, str]],
    control_ids: List[str],
    return_all_scores: bool = False,
) -> List[Tuple[int, float, Dict[str, float], Optional[str]]]:
    """Full rescan of control i against all n controls. Returns sorted top-3.

    Returns list of (j_idx, score, feature_scores, category).
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

    # Vectorized cosine similarities per feature
    n_features = len(FEATURE_NAMES)
    cosine_per_feature = np.zeros((n_features, n), dtype=np.float32)
    for f_idx in range(n_features):
        if feature_valid[f_idx][i]:
            cosine_per_feature[f_idx] = feature_embeddings[f_idx][i] @ feature_embeddings[f_idx].T
            np.clip(cosine_per_feature[f_idx], 0.0, 1.0, out=cosine_per_feature[f_idx])
            cosine_per_feature[f_idx] *= feature_valid[f_idx]

    # Quick upper bound to find top candidates
    cosine_sum = cosine_per_feature.sum(axis=0) / n_features  # rough avg
    n_candidates = max(TOP_SIMILAR * 10, 200)

    for ex_idx in excluded:
        cosine_sum[ex_idx] = -1.0

    if n_candidates < n:
        candidate_indices = np.argpartition(cosine_sum, -n_candidates)[-n_candidates:]
    else:
        candidate_indices = np.arange(n)

    scored: List[Tuple[int, float, Dict[str, float], Optional[str]]] = []

    for j in candidate_indices:
        j = int(j)
        if j in excluded or cosine_sum[j] <= 0:
            continue

        result = _compute_pair_score(
            i, j, feature_embeddings, feature_valid, tfidf_matrices,
            parent_child_pairs, control_ids,
        )
        if result is None:
            continue

        score, feat_scores = result
        category = _categorize_score(score)

        if not return_all_scores and category is None:
            continue  # Below weak_similar threshold

        scored.append((j, score, feat_scores, category))

    scored.sort(key=lambda x: x[1], reverse=True)

    if return_all_scores:
        return scored
    return scored[:TOP_SIMILAR]


# ── L1 Active Key filter ────────────────────────────────────────────

async def _load_l1_active_key_ids() -> Set[str]:
    """Load control IDs that are L1 + Active + Key Control from PostgreSQL."""
    engine = get_engine()
    vc = ver_control_tbl

    async with engine.connect() as conn:
        q = (
            select(vc.c.ref_control_id)
            .where(vc.c.tx_to.is_(None))
            .where(vc.c.hierarchy_level == "Level 1")
            .where(vc.c.control_status == "Active")
            .where(vc.c.key_control.is_(True))
        )
        rows = (await conn.execute(q)).fetchall()

    ids = {r[0] for r in rows}
    logger.info("L1 Active Key controls: {}", len(ids))
    return ids


# ── Main entry point ────────────────────────────────────────────────

async def compute_similar_controls(
    embedding_arrays: Dict[str, Any],
    embeddings_index: Dict[str, Any],
    changed_control_ids: Optional[Set[str]] = None,
    new_control_ids: Optional[Set[str]] = None,
    progress_callback: Optional[Callable] = None,
    force_full_rebuild: bool = False,
) -> None:
    """Compute and store similar controls (L1 Active Key only).

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

    # Load L1 Active Key filter
    l1_active_key_ids = await _load_l1_active_key_ids()

    # Build ordered control_id list — only L1 Active Key controls
    control_ids: List[str] = []
    row_to_idx: Dict[int, int] = {}
    cid_to_idx: Dict[str, int] = {}

    for cid, meta in sorted(by_cid.items()):
        if cid not in l1_active_key_ids:
            continue
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
        cid_to_idx[cid] = idx

    n = len(control_ids)
    if n == 0:
        logger.warning("No L1 Active Key controls with valid embeddings, skipping")
        return

    # Filter delta sets to only L1 Active Key
    changed_control_ids = changed_control_ids & l1_active_key_ids
    new_control_ids = new_control_ids & l1_active_key_ids

    # Decide mode
    delta_cids = changed_control_ids | new_control_ids
    use_incremental = (
        not force_full_rebuild
        and len(delta_cids) > 0
        and len(delta_cids) < n
    )

    mode_label = "incremental" if use_incremental else "full rebuild"
    logger.info(
        "Starting similarity computation: mode={}, n={} (L1 Active Key), delta={}",
        mode_label, n, len(delta_cids),
    )

    # ── Common setup: load embeddings, TF-IDF, parent-child ──────

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

    # Load clean text for TF-IDF and build TF-IDF matrices
    engine = get_engine()
    async with engine.connect() as conn:
        texts_per_feature = await _load_feature_texts(conn, control_ids, cid_to_idx)
        parent_child_pairs = await _load_parent_child_pairs(conn)

    tfidf_matrices = _build_tfidf_matrices(texts_per_feature, n)

    # Log feature stats
    for f_idx, feat_name in enumerate(FEATURE_NAMES):
        n_valid = int(feature_valid[f_idx].sum())
        n_texts = len(texts_per_feature[f_idx])
        has_tfidf = tfidf_matrices[f_idx] is not None
        logger.info(
            "Feature '{}': {} valid vectors, {} texts, tfidf={}",
            feat_name, n_valid, n_texts, has_tfidf,
        )

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
            tfidf_matrices=tfidf_matrices,
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
            tfidf_matrices=tfidf_matrices,
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
    tfidf_matrices: List[Optional[csr_matrix]],
    parent_child_pairs: Set[Tuple[str, str]],
    progress_callback: Optional[Callable] = None,
    p_start: float = 97,
    p_end: float = 99,
) -> None:
    """Full O(n²) similarity recomputation for L1 Active Key controls."""
    logger.info("Running full rebuild for {} L1 Active Key controls", n)
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

            # Yield to event loop between chunks so other requests can be served
            await asyncio.sleep(0)

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
                i, j, feature_embeddings, feature_valid, tfidf_matrices,
                parent_child_pairs, control_ids,
            )
            if result is not None:
                scored.append((j, result[0], result[1]))

        scored.sort(key=lambda x: x[1], reverse=True)

        rank = 0
        for j, score, feat_scores in scored:
            category = _categorize_score(score)
            if category is None:
                continue  # Below weak_similar threshold
            rank += 1
            if rank > TOP_SIMILAR:
                break
            results.append({
                "ref_control_id": control_ids[i],
                "similar_control_id": control_ids[j],
                "rank": rank,
                "score": round(score, 4),
                "category": category,
                "feature_scores": feat_scores,
            })

        # Yield to event loop periodically so job status and other requests can be served
        if (i + 1) % 100 == 0:
            await asyncio.sleep(0)

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


# ── Incremental ──────────────────────────────────────────────────────

async def _compute_incremental(
    control_ids: List[str],
    cid_to_idx: Dict[str, int],
    n: int,
    feature_embeddings: List[np.ndarray],
    feature_valid: List[np.ndarray],
    tfidf_matrices: List[Optional[csr_matrix]],
    parent_child_pairs: Set[Tuple[str, str]],
    changed_control_ids: Set[str],
    new_control_ids: Set[str],
    progress_callback: Optional[Callable] = None,
    p_start: float = 97,
    p_end: float = 99,
) -> None:
    """Incremental similarity update.

    Step 1: Load current top-3 + kth_score from DB
    Step 2: DELETE phase — rescan controls that pointed to changed controls
    Step 3: INSERT phase — score new/changed controls against all, reverse kth_score check
    Step 4: Atomic write of changes
    """
    delta_cids = changed_control_ids | new_control_ids
    logger.info(
        "Incremental similarity: {} changed, {} new, {} total L1 Active Key",
        len(changed_control_ids), len(new_control_ids), n,
    )

    # Step 1: Load current top-3 from DB
    engine = get_engine()

    # current_top3[idx] = [(similar_idx, score, rank, feature_scores, category), ...]
    current_top3: Dict[int, List[Tuple[int, float, int, Dict[str, float], Optional[str]]]] = defaultdict(list)
    kth_score: Dict[int, float] = {}

    async with engine.connect() as conn:
        q = (
            select(
                similar_tbl.c.ref_control_id,
                similar_tbl.c.similar_control_id,
                similar_tbl.c.rank,
                similar_tbl.c.score,
                similar_tbl.c.category,
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
        current_top3[ref_idx].append((
            sim_idx,
            float(r["score"]),
            int(r["rank"]),
            r["feature_scores"] or {},
            r["category"],
        ))

    for idx in range(n):
        entries = current_top3.get(idx, [])
        if len(entries) >= TOP_SIMILAR:
            kth_score[idx] = min(e[1] for e in entries)
        else:
            kth_score[idx] = 0.0

    logger.info("Loaded current top-3 for {} controls", len(current_top3))

    modified_controls: Set[int] = set()

    # Step 2: DELETE phase
    affected_set: Set[int] = set()

    for cid in changed_control_ids:
        changed_idx = cid_to_idx.get(cid)
        if changed_idx is None:
            continue
        for ref_idx, entries in current_top3.items():
            for sim_idx, _score, _rank, _fs, _cat in entries:
                if sim_idx == changed_idx:
                    affected_set.add(ref_idx)
                    break

    logger.info(
        "DELETE phase: {} changed controls affect {} existing controls' top-3",
        len(changed_control_ids), len(affected_set),
    )

    if len(affected_set) > HUB_GUARDRAIL_THRESHOLD:
        logger.warning(
            "Hub guardrail triggered: affected_set={} > threshold={}. Falling back to full rebuild.",
            len(affected_set), HUB_GUARDRAIL_THRESHOLD,
        )
        await _compute_full_rebuild(
            control_ids=control_ids, n=n,
            feature_embeddings=feature_embeddings, feature_valid=feature_valid,
            tfidf_matrices=tfidf_matrices, parent_child_pairs=parent_child_pairs,
            progress_callback=progress_callback, p_start=p_start, p_end=p_end,
        )
        return

    rescan_count = 0
    for ref_idx in affected_set:
        new_top3 = _rescan_control_top3(
            ref_idx, n, feature_embeddings, feature_valid, tfidf_matrices,
            parent_child_pairs, control_ids,
        )
        current_top3[ref_idx] = [
            (j, score, rank, fs, cat) for rank, (j, score, fs, cat) in enumerate(new_top3, start=1)
        ]
        if new_top3:
            kth_score[ref_idx] = new_top3[-1][1] if len(new_top3) >= TOP_SIMILAR else 0.0
        else:
            kth_score[ref_idx] = 0.0
        modified_controls.add(ref_idx)
        rescan_count += 1

        if rescan_count % 100 == 0:
            await asyncio.sleep(0)
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
    delta_idx_set = {cid_to_idx[c] for c in delta_cids if c in cid_to_idx}

    insert_count = 0
    for cid in delta_cids:
        x_idx = cid_to_idx.get(cid)
        if x_idx is None:
            continue

        x_all_scored = _rescan_control_top3(
            x_idx, n, feature_embeddings, feature_valid, tfidf_matrices,
            parent_child_pairs, control_ids, return_all_scores=True,
        )
        x_top3 = [s for s in x_all_scored if _categorize_score(s[1]) is not None][:TOP_SIMILAR]
        current_top3[x_idx] = [
            (j, score, rank, fs, cat)
            for rank, (j, score, fs, cat) in enumerate(x_top3, start=1)
        ]
        if x_top3:
            kth_score[x_idx] = x_top3[-1][1] if len(x_top3) >= TOP_SIMILAR else 0.0
        else:
            kth_score[x_idx] = 0.0
        modified_controls.add(x_idx)

        # Reverse check
        for y_idx, score_xy, feat_scores_xy, cat_xy in x_all_scored:
            if y_idx in delta_idx_set:
                continue

            if score_xy > kth_score.get(y_idx, 0.0) and _categorize_score(score_xy) is not None:
                y_entries = list(current_top3.get(y_idx, []))
                y_entries.append((x_idx, score_xy, 0, feat_scores_xy, _categorize_score(score_xy)))
                y_entries.sort(key=lambda e: e[1], reverse=True)
                y_entries = [e for e in y_entries if _categorize_score(e[1]) is not None][:TOP_SIMILAR]
                current_top3[y_idx] = [
                    (j, score, rank, fs, cat)
                    for rank, (j, score, _, fs, cat) in enumerate(y_entries, start=1)
                ]
                kth_score[y_idx] = y_entries[-1][1] if len(y_entries) >= TOP_SIMILAR else 0.0
                modified_controls.add(y_idx)

        insert_count += 1
        if insert_count % 50 == 0:
            await asyncio.sleep(0)
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

    if progress_callback:
        await progress_callback(
            f"Similar controls: writing {len(modified_controls)} modified controls",
            n, n, int(p_end - 0.5),
        )

    await _write_incremental(control_ids, current_top3, modified_controls)


async def _write_incremental(
    control_ids: List[str],
    current_top3: Dict[int, List[Tuple[int, float, int, Dict[str, float], Optional[str]]]],
    modified_controls: Set[int],
) -> None:
    """Atomically write only modified controls' similarity rows."""
    if not modified_controls:
        logger.info("No similarity changes to write")
        return

    tx_from = datetime.now(timezone.utc)
    engine = get_engine()

    modified_cids = [control_ids[idx] for idx in modified_controls]

    new_rows: List[dict] = []
    for idx in modified_controls:
        cid = control_ids[idx]
        for sim_idx, score, rank, feat_scores, category in current_top3.get(idx, []):
            new_rows.append({
                "ref_control_id": cid,
                "similar_control_id": control_ids[sim_idx],
                "rank": rank,
                "score": round(score, 4),
                "category": category,
                "feature_scores": feat_scores,
                "tx_from": tx_from,
                "tx_to": None,
            })

    async with engine.begin() as conn:
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

        for batch_start in range(0, len(new_rows), BATCH_INSERT_SIZE):
            batch = new_rows[batch_start:batch_start + BATCH_INSERT_SIZE]
            await conn.execute(insert(similar_tbl), batch)

    logger.info(
        "Incremental write complete: {} controls updated, {} rows written",
        len(modified_controls), len(new_rows),
    )


# ── Helpers ──────────────────────────────────────────────────────────

async def _load_feature_texts(
    conn,
    control_ids: List[str],
    cid_to_idx: Dict[str, int],
) -> List[Dict[int, str]]:
    """Load clean text from PostgreSQL for TF-IDF computation."""
    result: List[Dict[int, str]] = [{} for _ in FEATURE_NAMES]

    batch_size = 10000
    cid_list = list(control_ids)

    for batch_start in range(0, len(cid_list), batch_size):
        batch_cids = cid_list[batch_start:batch_start + batch_size]

        q = (
            select(
                feature_prep_tbl.c.ref_control_id,
                feature_prep_tbl.c.what,
                feature_prep_tbl.c.why,
                feature_prep_tbl.c.where,
            )
            .where(feature_prep_tbl.c.tx_to.is_(None))
            .where(feature_prep_tbl.c.ref_control_id.in_(batch_cids))
        )
        rows = (await conn.execute(q)).mappings().all()

        for r in rows:
            cid = r["ref_control_id"]
            idx = cid_to_idx.get(cid)
            if idx is None:
                continue

            for f_idx, feat_name in enumerate(FEATURE_NAMES):
                text_val = r.get(feat_name) or ""
                if text_val.strip():
                    result[f_idx][idx] = text_val

    logger.info("Feature texts loaded for {} controls", len(control_ids))
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
