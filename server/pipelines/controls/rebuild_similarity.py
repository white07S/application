"""CLI: Force full rebuild of similar controls.

Reads the latest embeddings NPZ and recomputes all similarity scores from
scratch.  Intended as a monthly safety-net (run on weekends/off-hours) to
correct any drift from daily incremental updates.

Usage:
    python -m server.pipelines.controls.rebuild_similarity \
        --upload-id UPL-2026-0001

The script:
1. Loads the full embeddings NPZ + index for the specified upload
2. Runs full O(n²) similarity recomputation
3. Atomically replaces all rows in ai_controls_similar_controls
4. Logs timestamps and counts for audit
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np

from server.pipelines.controls.model_runners.common import FEATURE_NAMES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.pipelines.controls.rebuild_similarity",
        description="Force full rebuild of similar controls (monthly safety net).",
    )
    parser.add_argument(
        "--upload-id", required=True,
        help="Upload ID whose embeddings to use (e.g. UPL-2026-0001)",
    )
    parser.add_argument(
        "--data-ingested-path", type=Path, default=None,
        help="Base data_ingested directory (default: from .env)",
    )
    return parser.parse_args()


async def run_rebuild(upload_id: str, data_ingested_path: Path = None) -> int:
    """Run the full similarity rebuild."""
    from server.pipelines.controls.model_runners.common import (
        model_output_path,
        read_index,
        resolve_data_ingested_path,
    )

    data_path = resolve_data_ingested_path(data_ingested_path)
    started_at = datetime.now(timezone.utc)

    print(f"[{started_at.isoformat()}] Starting full similarity rebuild")
    print(f"  upload_id: {upload_id}")
    print(f"  data_path: {data_path}")

    # Load embeddings NPZ
    npz_path = model_output_path(data_path, "embeddings", upload_id, suffix=".npz")
    if not npz_path.exists():
        print(f"ERROR: Embeddings NPZ not found: {npz_path}")
        return 1

    index_path = npz_path.with_suffix(npz_path.suffix + ".index.json")
    if not index_path.exists():
        print(f"ERROR: Embeddings index not found: {index_path}")
        return 1

    print(f"  Loading embeddings from {npz_path}")
    embeddings_npz = np.load(npz_path, allow_pickle=True)
    embeddings_index = read_index(index_path)

    embedding_fields = [f"{f}_embedding" for f in FEATURE_NAMES]
    embedding_arrays: Dict[str, Any] = {}
    npz_keys = set(getattr(embeddings_npz, "files", []))
    for npz_field in embedding_fields:
        if npz_field in npz_keys:
            embedding_arrays[npz_field] = embeddings_npz[npz_field]
        else:
            print(f"  WARNING: Missing embedding array '{npz_field}'")

    n_controls = len(embeddings_index.get("by_control_id", {}))
    print(f"  Controls: {n_controls}")
    print(f"  Embedding arrays: {len(embedding_arrays)}/{len(embedding_fields)}")

    if len(embedding_arrays) < len(embedding_fields):
        print("ERROR: Not enough embedding arrays for rebuild")
        return 1

    # Progress callback for terminal output
    last_msg = ""

    async def _progress(step: str, processed: int, total: int, pct: int = 0):
        nonlocal last_msg
        msg = f"  [{pct:3d}%] {step}"
        if msg != last_msg:
            print(msg)
            last_msg = msg

    # Run full rebuild
    from server.pipelines.controls.similarity import compute_similar_controls

    await compute_similar_controls(
        embedding_arrays=embedding_arrays,
        embeddings_index=embeddings_index,
        force_full_rebuild=True,
        progress_callback=_progress,
    )

    finished_at = datetime.now(timezone.utc)
    duration = finished_at - started_at

    print(f"\n[{finished_at.isoformat()}] Full similarity rebuild complete")
    print(f"  Duration: {duration}")
    print(f"  Controls processed: {n_controls}")

    try:
        embeddings_npz.close()
    except Exception:
        pass

    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(run_rebuild(args.upload_id, args.data_ingested_path))


if __name__ == "__main__":
    sys.exit(main())
