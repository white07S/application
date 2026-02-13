from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from server.pipelines.controls.model_runners.common import (
    controls_jsonl_path,
    default_run_date,
    load_controls,
    load_jsonl_by_control_id,
    model_output_path,
    resolve_data_ingested_path,
    write_npz_index,
)

MODEL_NAME = "embeddings"
EMBEDDING_FIELDS = [
    "control_title_embedding",
    "control_description_embedding",
    "evidence_description_embedding",
    "local_functional_information_embedding",
    "control_as_event_embedding",
    "control_as_issues_embedding",
]


def embeddings_hash(
    control_row: Dict[str, Any],
    clean_row: Optional[Dict[str, Any]],
) -> str:
    clean_row = clean_row or {}
    parts = [
        str(clean_row.get("control_title") or "").strip().lower(),
        str(clean_row.get("control_description") or "").strip().lower(),
        str(clean_row.get("evidence_description") or "").strip().lower(),
        str(clean_row.get("local_functional_information") or "").strip().lower(),
        str(clean_row.get("control_as_event") or "").strip().lower(),
        str(clean_row.get("control_as_issues") or "").strip().lower(),
    ]
    payload = "|".join(parts)
    if not payload:
        payload = str(control_row.get("control_id") or "")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    bucket = int(digest[:16], 16) % 10000
    return "EM{:04d}".format(bucket)


def text_to_embedding(text: Any, dim: int) -> np.ndarray:
    if text is None or str(text).strip() == "":
        return np.zeros((dim,), dtype=np.float16)

    digest = hashlib.sha256(str(text).encode("utf-8")).digest()
    vec = np.zeros((dim,), dtype=np.float16)

    # Sparse deterministic mock embedding: stable and compact on disk.
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

    # Load clean_text output (required dependency)
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

    control_ids = []
    hash_by_control_id = {}
    hash_null_col = []
    last_modified_on_col = []

    # Allocate embedding arrays
    n = len(controls_rows)
    embeddings_by_field = {name: np.zeros((n, args.embedding_dim), dtype=np.float16) for name in EMBEDDING_FIELDS}

    for row_idx, row in enumerate(controls_rows):
        control_id = str(row["control_id"])
        clean_row = clean_text_rows.get(control_id, {})
        hash_value = embeddings_hash(row, clean_row)
        hash_by_control_id[control_id] = hash_value
        control_ids.append(control_id)
        hash_null_col.append(None)
        last_modified_on_col.append(row.get("last_modified_on"))

        embeddings_by_field["control_title_embedding"][row_idx] = text_to_embedding(clean_row.get("control_title"), args.embedding_dim)
        embeddings_by_field["control_description_embedding"][row_idx] = text_to_embedding(clean_row.get("control_description"), args.embedding_dim)
        embeddings_by_field["evidence_description_embedding"][row_idx] = text_to_embedding(clean_row.get("evidence_description"), args.embedding_dim)
        embeddings_by_field["local_functional_information_embedding"][row_idx] = text_to_embedding(clean_row.get("local_functional_information"), args.embedding_dim)
        embeddings_by_field["control_as_event_embedding"][row_idx] = text_to_embedding(clean_row.get("control_as_event"), args.embedding_dim)
        embeddings_by_field["control_as_issues_embedding"][row_idx] = text_to_embedding(clean_row.get("control_as_issues"), args.embedding_dim)

    npz_payload = {
        "control_id": np.array(control_ids, dtype=np.str_),
        "hash": np.array(hash_null_col, dtype=object),
        "last_modified_on": np.array(last_modified_on_col, dtype=object),
    }
    npz_payload.update(embeddings_by_field)
    np.savez_compressed(output_npz_path, **npz_payload)

    index_path = write_npz_index(
        output_npz_path=output_npz_path, model_name=MODEL_NAME,
        run_date=run_date, control_ids=control_ids,
        hash_by_control_id=hash_by_control_id, embedding_dim=args.embedding_dim,
    )

    print(f"clean_text_input={clean_text_path if clean_text_rows else 'none'}")
    print(f"output={output_npz_path}")
    print(f"index={index_path}")
    print(f"rows={len(control_ids)}")
    print(f"embedding_dim={args.embedding_dim}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
