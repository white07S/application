from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.pipelines.controls.model_runners.common import (
    FEATURE_NAMES,
    HASH_COLUMN_NAMES,
    KEYWORD_FIELD_NAMES,
    MASK_COLUMN_NAMES,
    controls_jsonl_path,
    default_run_date,
    is_active_status,
    is_key_control_yes,
    is_level_one,
    load_controls,
    load_jsonl_by_control_id,
    model_output_path,
    normalize_text,
    resolve_data_ingested_path,
    write_jsonl_with_index,
)

MODEL_NAME = "feature_prep"


def feature_hash(text: Optional[str]) -> Optional[str]:
    """Compute a per-feature hash from text for delta detection.

    Returns None if text is empty/None (no vector should be produced).
    """
    if not text or not text.strip():
        return None
    normalized = text.strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"CT{digest[:12]}"


def compute_per_feature_hashes(
    enrichment_row: Optional[Dict[str, Any]],
) -> Dict[str, Optional[str]]:
    """Compute 3 independent per-feature hashes from enrichment details.

    Reads what_details, why_details, where_details from enrichment output.
    Returns dict with keys: hash_what, hash_why, hash_where.
    Value is None if the feature text is empty (no embedding needed).
    """
    enrichment_row = enrichment_row or {}

    hashes: Dict[str, Optional[str]] = {}
    for feat_name in FEATURE_NAMES:
        text = enrichment_row.get(f"{feat_name}_details")
        hashes[f"hash_{feat_name}"] = feature_hash(text)

    return hashes


def compute_feature_mask(
    control_row: Dict[str, Any],
    feature_hashes: Dict[str, Optional[str]],
) -> Dict[str, bool]:
    """Compute per-feature mask: True = should be embedded, False = skip.

    Only L1 Active Key controls get mask=True (they are the similarity scope).
    L2 controls and non-Active/non-Key controls always get mask=False.
    """
    is_l1 = is_level_one(control_row.get("hierarchy_level"))
    is_active = is_active_status(control_row.get("control_status"))
    is_key = is_key_control_yes(control_row.get("key_control"))
    qualify = is_l1 and is_active and is_key

    mask: Dict[str, bool] = {}
    for hash_col, mask_col in zip(HASH_COLUMN_NAMES, MASK_COLUMN_NAMES):
        if not qualify:
            mask[mask_col] = False
        elif feature_hashes.get(hash_col) is None:
            # No text for this feature
            mask[mask_col] = False
        else:
            mask[mask_col] = True

    return mask


def build_record(
    *,
    control_row: Dict[str, Any],
    enrichment_row: Optional[Dict[str, Any]],
    run_date: str,
    feature_hashes: Dict[str, Optional[str]],
    feature_mask: Dict[str, bool],
) -> Dict[str, Any]:
    """Build feature_prep output record.

    Output fields:
    - what, why, where: text values from enrichment _details (no cleaning needed)
    - hash_what, hash_why, hash_where: per-feature hashes for delta detection
    - mask_what, mask_why, mask_where: embedding mask (True = embed)
    - control_title, control_description: keyword FTS fields (pass-through)
    - evidence_description, local_functional_information: keyword FTS (L2)
    """
    enrichment_row = enrichment_row or {}

    record: Dict[str, Any] = {
        "control_id": str(control_row["control_id"]),
        "model_run_timestamp": run_date,
    }

    # Semantic feature texts (from enrichment _details)
    for feat_name in FEATURE_NAMES:
        record[feat_name] = enrichment_row.get(f"{feat_name}_details")

    # Keyword FTS fields (pass-through from source, normalized)
    record["control_title"] = normalize_text(control_row.get("control_title"))
    record["control_description"] = normalize_text(control_row.get("control_description"))
    record["evidence_description"] = normalize_text(control_row.get("evidence_description"))
    record["local_functional_information"] = normalize_text(control_row.get("local_functional_information"))

    # Hashes and masks
    record.update(feature_hashes)
    record.update(feature_mask)
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.pipelines.controls.model_runners.run_feature_prep_mock",
        description="Run mock feature_prep model for controls.",
    )
    parser.add_argument("--upload-id", required=True, help="Upload ID (e.g. UPL-2026-0001)")
    parser.add_argument("--data-ingested-path", type=Path, default=None, help="Base data_ingested directory (default: from .env)")
    parser.add_argument("--run-date", type=str, default=None, help="ISO date (default: today)")
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

    # Load enrichment output (required dependency)
    enrichment_path = model_output_path(data_ingested_path, "enrichment", args.upload_id)
    if not enrichment_path.exists():
        print(f"ERROR: Enrichment output not found: {enrichment_path}")
        print("Run enrichment model first: python -m server.pipelines.controls.model_runners.run_enrichment_mock --upload-id " + args.upload_id)
        return 1
    enrichment_rows = load_jsonl_by_control_id(enrichment_path)

    output_path = model_output_path(data_ingested_path, MODEL_NAME, args.upload_id)
    if output_path.exists() and not args.overwrite:
        print(f"ERROR: {output_path} already exists. Use --overwrite.")
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_records = []
    hashes_by_control_id: Dict[str, Dict[str, Optional[str]]] = {}
    l1_active_key = 0
    skipped = 0

    for control_row in controls_rows:
        control_id = str(control_row["control_id"])
        enrichment_row = enrichment_rows.get(control_id)

        feature_hashes = compute_per_feature_hashes(enrichment_row)
        feature_mask = compute_feature_mask(control_row, feature_hashes)

        # Merge hashes + mask for index
        combined = dict(feature_hashes)
        combined.update(feature_mask)
        hashes_by_control_id[control_id] = combined

        # Track stats
        if any(feature_mask.get(mc) for mc in MASK_COLUMN_NAMES):
            l1_active_key += 1
        else:
            skipped += 1

        record = build_record(
            control_row=control_row, enrichment_row=enrichment_row,
            run_date=run_date,
            feature_hashes=feature_hashes, feature_mask=feature_mask,
        )
        output_records.append(record)

    index_path = write_jsonl_with_index(
        records=output_records, output_path=output_path,
        model_name=MODEL_NAME, run_date=run_date,
        hashes_by_control_id=hashes_by_control_id,
    )

    # Count features with actual text (non-None hashes)
    features_with_text = sum(
        1 for h in hashes_by_control_id.values()
        for k, v in h.items() if k.startswith("hash_") and v is not None
    )
    total_features = len(hashes_by_control_id) * len(FEATURE_NAMES)

    print(f"enrichment_input={enrichment_path}")
    print(f"output={output_path}")
    print(f"index={index_path}")
    print(f"rows={len(output_records)}")
    print(f"l1_active_key_embedded={l1_active_key}")
    print(f"skipped_from_embedding={skipped}")
    print(f"features_with_text={features_with_text}/{total_features}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
