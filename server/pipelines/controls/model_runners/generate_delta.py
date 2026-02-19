"""Generate delta upload files for testing incremental ingestion.

Takes UPL-YYYY-0001 (full baseline) and produces UPL-YYYY-0002 with:
  - All original controls (full dump, as in production)
  - N controls mutated (text fields changed, last_modified_on bumped)
  - M new controls added

Then re-runs all model runners (enrichment, clean_text, embeddings) on the
new full file so the delta detection in ingestion can exercise both:
  1. Changed records (existing control with updated text/hash)
  2. New records (control_id not seen before)

Usage:
    python -m server.pipelines.controls.model_runners.generate_delta \
        --upload-id UPL-2026-0001 \
        --num-changed 50 \
        --num-new 20

This generates UPL-2026-0002.jsonl and runs enrichment/clean_text/embeddings
mock runners on it.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import orjson

from server.pipelines.controls.model_runners.common import (
    FEATURE_NAMES,
    controls_jsonl_path,
    default_run_date,
    iter_jsonl,
    model_output_path,
    resolve_data_ingested_path,
)


MUTATION_SUFFIXES = [
    " [updated Q1 review]",
    " - revised per audit finding",
    " (enhanced monitoring scope)",
    " [frequency adjusted]",
    " - clarified escalation path",
]

NEW_CONTROL_PREFIXES = [
    "NEW: Automated reconciliation check",
    "NEW: Enhanced fraud detection control",
    "NEW: Regulatory reporting validation",
    "NEW: Data quality assurance process",
    "NEW: Access management review",
]


def _bump_timestamp(ts_str: Optional[str]) -> str:
    """Bump a timestamp by 1 day to simulate a modification."""
    if ts_str:
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            dt = dt + timedelta(days=1)
            return dt.isoformat()
        except (ValueError, TypeError):
            pass
    return datetime.now(timezone.utc).isoformat()


def _mutate_control(control: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    """Apply mutations to a control to simulate a real change.

    L1/L2-aware: L2 controls primarily have evidence_description and
    local_functional_information as distinguishing fields. Mutations target
    the fields that are actually populated for that level.
    """
    mutated = copy.deepcopy(control)
    suffix = rng.choice(MUTATION_SUFFIXES)

    is_l2 = str(mutated.get("hierarchy_level", "")).strip().lower() == "level 2"

    if is_l2:
        # L2: primarily mutate the L2-distinguishing fields
        # 80%: mutate evidence/local_func (the L2-specific fields)
        # 20%: mutate title/desc (forces hash divergence from parent → mask flip)
        if rng.random() < 0.8:
            text_fields = ["evidence_description", "local_functional_information"]
        else:
            text_fields = ["control_title", "control_description", "evidence_description", "local_functional_information"]
    else:
        # L1: title/desc are the distinguishing fields
        text_fields = ["control_title", "control_description"]

    # Pick 1-2 fields to change
    n_change = rng.randint(1, min(2, len(text_fields)))
    fields_to_change = rng.sample(text_fields, k=n_change)

    for field in fields_to_change:
        original = mutated.get(field)
        if original and isinstance(original, str):
            mutated[field] = original + suffix
        else:
            mutated[field] = f"Updated field: {field}{suffix}"

    # Bump last_modified_on
    mutated["last_modified_on"] = _bump_timestamp(mutated.get("last_modified_on"))

    return mutated


def _generate_new_control(
    base_id: str,
    index: int,
    existing_control: Dict[str, Any],
    rng: random.Random,
) -> Dict[str, Any]:
    """Generate a new control by cloning an existing one with new ID and text."""
    new_control = copy.deepcopy(existing_control)
    new_control["control_id"] = f"{base_id}-NEW-{index:04d}"

    prefix = rng.choice(NEW_CONTROL_PREFIXES)
    new_control["control_title"] = f"{prefix} #{index}"
    new_control["control_description"] = (
        f"This is a newly added control for testing delta ingestion. "
        f"Based on template {existing_control.get('control_id', 'unknown')}. "
        f"Added to verify that new controls are correctly detected and processed."
    )
    new_control["last_modified_on"] = datetime.now(timezone.utc).isoformat()

    # Clear parent to avoid FK issues
    new_control["parent_control_id"] = None

    return new_control


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.pipelines.controls.model_runners.generate_delta",
        description="Generate delta upload for testing incremental ingestion.",
    )
    parser.add_argument("--upload-id", required=True, help="Base upload ID (e.g. UPL-2026-0001)")
    parser.add_argument("--data-ingested-path", type=Path, default=None)
    parser.add_argument("--qdrant-dataset-path", type=Path, default=None, help="Path to Qdrant/DBpedia Arrow IPC dataset (passed to enrichment + embeddings runners)")
    parser.add_argument("--num-changed", type=int, default=50, help="Number of existing controls to mutate")
    parser.add_argument("--num-new", type=int, default=20, help="Number of new controls to add")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--run-date", type=str, default=None)
    parser.add_argument("--skip-model-runs", action="store_true", help="Skip running model runners on delta file")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _derive_delta_upload_id(base_upload_id: str) -> str:
    """Derive delta upload ID: UPL-2026-0001 → UPL-2026-0002."""
    parts = base_upload_id.rsplit("-", 1)
    if len(parts) == 2:
        try:
            seq = int(parts[1])
            return f"{parts[0]}-{seq + 1:04d}"
        except ValueError:
            pass
    return f"{base_upload_id}-delta"


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)
    data_ingested_path = resolve_data_ingested_path(args.data_ingested_path)

    base_upload_id = args.upload_id
    delta_upload_id = _derive_delta_upload_id(base_upload_id)
    run_date = args.run_date or default_run_date()

    print(f"Base upload: {base_upload_id}")
    print(f"Delta upload: {delta_upload_id}")
    print(f"Mutations: {args.num_changed} changed, {args.num_new} new")

    # Load base controls
    base_path = controls_jsonl_path(data_ingested_path, base_upload_id)
    if not base_path.exists():
        print(f"ERROR: Base controls not found: {base_path}")
        return 1

    controls: List[Dict[str, Any]] = []
    for _, row in iter_jsonl(base_path):
        controls.append(row)

    print(f"Loaded {len(controls)} controls from base upload")

    if args.num_changed > len(controls):
        print(f"WARNING: num_changed ({args.num_changed}) > total controls ({len(controls)}), capping")
        args.num_changed = len(controls)

    # Select controls to mutate
    indices_to_mutate = rng.sample(range(len(controls)), k=args.num_changed)
    mutated_cids: List[str] = []

    for idx in indices_to_mutate:
        original_cid = controls[idx].get("control_id", "?")
        controls[idx] = _mutate_control(controls[idx], rng)
        mutated_cids.append(original_cid)

    # Generate new controls (using random existing controls as templates)
    new_controls: List[Dict[str, Any]] = []
    for i in range(args.num_new):
        template = rng.choice(controls)
        new_control = _generate_new_control(base_upload_id, i + 1, template, rng)
        new_controls.append(new_control)

    # Combine: all original (with mutations applied) + new controls
    all_controls = controls + new_controls

    # Write delta controls JSONL
    delta_path = controls_jsonl_path(data_ingested_path, delta_upload_id)
    if delta_path.exists() and not args.overwrite:
        print(f"ERROR: {delta_path} already exists. Use --overwrite.")
        return 1
    delta_path.parent.mkdir(parents=True, exist_ok=True)

    with delta_path.open("wb") as f:
        for row in all_controls:
            f.write(orjson.dumps(row))
            f.write(b"\n")

    print(f"\nDelta controls written: {delta_path}")
    print(f"  Total: {len(all_controls)}")
    print(f"  Changed: {len(mutated_cids)}")
    print(f"  New: {len(new_controls)}")

    # Print changed control IDs for debugging
    print(f"\n  Changed control IDs (first 10):")
    for cid in mutated_cids[:10]:
        print(f"    - {cid}")
    if len(mutated_cids) > 10:
        print(f"    ... and {len(mutated_cids) - 10} more")

    new_cids = [c["control_id"] for c in new_controls]
    print(f"\n  New control IDs:")
    for cid in new_cids:
        print(f"    + {cid}")

    if args.skip_model_runs:
        print("\nSkipping model runners (--skip-model-runs)")
        return 0

    # Run model runners on delta file
    print("\n--- Running model runners on delta file ---\n")

    runners = [
        (
            "enrichment",
            [
                sys.executable, "-m",
                "server.pipelines.controls.model_runners.run_enrichment_mock",
                "--upload-id", delta_upload_id,
                "--overwrite",
            ],
        ),
        (
            "clean_text",
            [
                sys.executable, "-m",
                "server.pipelines.controls.model_runners.run_clean_text_mock",
                "--upload-id", delta_upload_id,
                "--overwrite",
            ],
        ),
        (
            "embeddings",
            [
                sys.executable, "-m",
                "server.pipelines.controls.model_runners.run_embeddings_mock",
                "--upload-id", delta_upload_id,
                "--overwrite",
            ],
        ),
        (
            "taxonomy",
            [
                sys.executable, "-m",
                "server.pipelines.controls.model_runners.run_taxonomy_mock",
                "--upload-id", delta_upload_id,
                "--overwrite",
            ],
        ),
    ]

    if args.data_ingested_path:
        for name, cmd in runners:
            cmd.extend(["--data-ingested-path", str(args.data_ingested_path)])

    if args.qdrant_dataset_path:
        for name, cmd in runners:
            if name in ("enrichment", "embeddings"):
                cmd.extend(["--qdrant-dataset-path", str(args.qdrant_dataset_path)])

    for name, cmd in runners:
        print(f"Running {name} mock runner...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {name} runner failed:")
            print(f"  stdout: {result.stdout}")
            print(f"  stderr: {result.stderr}")
            return 1
        print(f"  {result.stdout.strip()}")
        print()

    print("--- Delta generation complete ---")
    print(f"\nTo test ingestion:")
    print(f"  1. Ingest base:  upload_id={base_upload_id}")
    print(f"  2. Ingest delta: upload_id={delta_upload_id}")
    print(f"\nExpected delta detection:")
    print(f"  - {args.num_changed} controls with changed clean_text hashes → Qdrant vector update")
    print(f"  - {args.num_new} new controls → Qdrant full point insert")
    print(f"  - ~{len(controls) - args.num_changed} unchanged controls → skip")

    return 0


if __name__ == "__main__":
    sys.exit(main())
