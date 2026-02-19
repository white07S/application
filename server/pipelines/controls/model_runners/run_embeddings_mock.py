from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from server.pipelines.controls.model_runners.common import (
    FEATURE_NAMES,
    HASH_COLUMN_NAMES,
    MASK_COLUMN_NAMES,
    controls_jsonl_path,
    default_run_date,
    load_controls,
    load_jsonl_by_control_id,
    model_output_path,
    resolve_data_ingested_path,
    write_npz_index,
)

MODEL_NAME = "embeddings"
EMBEDDING_FIELDS = [f"{f}_embedding" for f in FEATURE_NAMES]


def text_to_embedding(text: Any, dim: int) -> np.ndarray:
    """Generate a deterministic sparse mock embedding from text hash."""
    if text is None or str(text).strip() == "":
        return np.zeros((dim,), dtype=np.float16)

    digest = hashlib.sha256(str(text).encode("utf-8")).digest()
    vec = np.zeros((dim,), dtype=np.float16)

    for i in range(0, 24, 2):
        idx = ((digest[i] << 8) | digest[i + 1]) % dim
        raw = digest[(i + 8) % len(digest)]
        val = (float(raw) / 255.0) * 2.0 - 1.0
        vec[idx] = np.float16(val)

    return vec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.pipelines.controls.model_runners.run_embeddings_mock",
        description="Run mock embeddings model for controls.",
    )
    parser.add_argument("--upload-id", required=True, help="Upload ID (e.g. UPL-2026-0001)")
    parser.add_argument("--data-ingested-path", type=Path, default=None, help="Base data_ingested directory (default: from .env)")
    parser.add_argument("--run-date", type=str, default=None, help="ISO date (default: today)")
    parser.add_argument("--embedding-dim", type=int, default=3072)
    parser.add_argument("--qdrant-dataset-path", type=Path, default=None, help="Path to Qdrant/DBpedia Arrow IPC dataset for real embeddings")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_date = args.run_date or default_run_date()
    data_ingested_path = resolve_data_ingested_path(args.data_ingested_path)

    input_path = controls_jsonl_path(data_ingested_path, args.upload_id)
    if not input_path.exists():
        print(f"ERROR: Controls JSONL not found: {input_path}")
        return 1
    controls_rows = load_controls(input_path, limit=args.limit)

    # Load clean_text output (required dependency — provides per-feature hashes)
    clean_text_path = model_output_path(data_ingested_path, "clean_text", args.upload_id)
    if not clean_text_path.exists():
        print(f"ERROR: Clean text output not found: {clean_text_path}")
        print("Run clean_text model first: python -m server.pipelines.controls.model_runners.run_clean_text_mock --upload-id " + args.upload_id)
        return 1
    clean_text_rows = load_jsonl_by_control_id(clean_text_path)

    output_npz_path = model_output_path(data_ingested_path, MODEL_NAME, args.upload_id, suffix=".npz")
    if output_npz_path.exists() and not args.overwrite:
        print(f"ERROR: {output_npz_path} already exists. Use --overwrite.")
        return 1
    output_npz_path.parent.mkdir(parents=True, exist_ok=True)

    # Load real embeddings from dataset if path provided
    dataset_embeddings: Optional[Dict[str, np.ndarray]] = None
    if args.qdrant_dataset_path is not None:
        from server.pipelines.controls.model_runners.dataset_pool import load_embeddings_for_controls
        print(f"Loading real embeddings from dataset: {args.qdrant_dataset_path}")
        dataset_embeddings = load_embeddings_for_controls(
            args.qdrant_dataset_path,
            len(controls_rows),
            dim=args.embedding_dim,
            dtype=np.float16,
        )
        print(f"Loaded real embeddings for {len(controls_rows)} controls")

    control_ids: List[str] = []
    hashes_by_control_id: Dict[str, Dict[str, Optional[str]]] = {}

    # Allocate embedding arrays
    n = len(controls_rows)
    embeddings_by_field = {name: np.zeros((n, args.embedding_dim), dtype=np.float16) for name in EMBEDDING_FIELDS}

    features_generated = 0
    features_skipped = 0
    features_masked = 0

    for row_idx, row in enumerate(controls_rows):
        control_id = str(row["control_id"])
        clean_row = clean_text_rows.get(control_id, {})
        control_ids.append(control_id)

        # Read 6 per-feature hashes + masks from clean_text output
        feature_hashes: Dict[str, Optional[str]] = {}
        for hash_col in HASH_COLUMN_NAMES:
            feature_hashes[hash_col] = clean_row.get(hash_col)
        # Include mask values in the index for downstream consumers
        for mask_col in MASK_COLUMN_NAMES:
            feature_hashes[mask_col] = clean_row.get(mask_col, True)
        hashes_by_control_id[control_id] = feature_hashes

        # Generate embeddings only for distinguishing features (mask=True AND hash non-None)
        for feat_idx, (feat_name, emb_field) in enumerate(zip(FEATURE_NAMES, EMBEDDING_FIELDS)):
            hash_val = feature_hashes.get(f"hash_{feat_name}")
            mask_val = feature_hashes.get(f"mask_{feat_name}", True)

            if hash_val is None:
                # No text for this feature → zero vector (already initialized)
                features_skipped += 1
                continue

            if not mask_val:
                # Feature is inherited from parent → zero vector (not distinguishing)
                features_masked += 1
                continue

            features_generated += 1

            if dataset_embeddings is not None:
                # Use real embeddings from dataset
                if emb_field in dataset_embeddings:
                    embeddings_by_field[emb_field][row_idx] = dataset_embeddings[emb_field][row_idx]
            else:
                # Fallback: deterministic hash-based sparse embeddings
                text = clean_row.get(feat_name)
                embeddings_by_field[emb_field][row_idx] = text_to_embedding(text, args.embedding_dim)

    npz_payload = {
        "control_id": np.array(control_ids, dtype=np.str_),
    }
    npz_payload.update(embeddings_by_field)
    np.savez_compressed(output_npz_path, **npz_payload)

    index_path = write_npz_index(
        output_npz_path=output_npz_path, model_name=MODEL_NAME,
        run_date=run_date, control_ids=control_ids,
        hashes_by_control_id=hashes_by_control_id, embedding_dim=args.embedding_dim,
    )

    print(f"clean_text_input={clean_text_path if clean_text_rows else 'none'}")
    print(f"output={output_npz_path}")
    print(f"index={index_path}")
    print(f"rows={len(control_ids)}")
    print(f"embedding_dim={args.embedding_dim}")
    print(f"features_generated={features_generated}, features_skipped={features_skipped}, features_masked={features_masked}")
    print(f"source={'dataset' if dataset_embeddings is not None else 'hash-based'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
