from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.pipelines.controls.model_runners.common import (
    controls_jsonl_path,
    default_run_date,
    is_active_status,
    is_key_control_yes,
    is_level_one,
    iter_jsonl,
    load_controls,
    model_output_path,
    resolve_data_ingested_path,
    write_jsonl_with_index,
)

MODEL_NAME = "taxonomy"


def taxonomy_hash(row: Dict[str, Any]) -> str:
    # Runner-specific hash: include only taxonomy-driving features.
    parts = [
        str(row.get("control_title") or "").strip().lower(),
        str(row.get("control_description") or "").strip().lower(),
        str(row.get("control_status") or "").strip().lower(),
        str(row.get("key_control") or "").strip().lower(),
        str(row.get("hierarchy_level") or "").strip().lower(),
    ]
    payload = "|".join(parts)
    if not payload:
        payload = str(row.get("control_id") or "")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    bucket = int(digest[:16], 16) % 10000
    return "TX{:04d}".format(bucket)


def load_active_taxonomy_catalog(catalog_jsonl: Path) -> List[Dict[str, str]]:
    if not catalog_jsonl.exists():
        return fallback_catalog()

    entries: List[Dict[str, str]] = []
    for _, row in iter_jsonl(catalog_jsonl):
        if str(row.get("status") or "").strip().lower() != "active":
            continue
        taxonomy_id = row.get("taxonomy_id")
        risk_theme_id = row.get("risk_theme_id")
        risk_theme = row.get("risk_theme")
        if not isinstance(taxonomy_id, str) or not isinstance(risk_theme_id, str):
            continue
        entries.append(
            {
                "taxonomy_id": taxonomy_id,
                "risk_theme_id": risk_theme_id,
                "risk_theme": str(risk_theme or risk_theme_id),
            }
        )

    return entries or fallback_catalog()


def fallback_catalog() -> List[Dict[str, str]]:
    return [
        {"taxonomy_id": "1", "risk_theme_id": "1.1", "risk_theme": "Mock Risk Theme 1-1"},
        {"taxonomy_id": "2", "risk_theme_id": "2.2", "risk_theme": "Mock Risk Theme 2-2"},
        {"taxonomy_id": "3", "risk_theme_id": "3.3", "risk_theme": "Mock Risk Theme 3-3"},
        {"taxonomy_id": "4", "risk_theme_id": "4.4", "risk_theme": "Mock Risk Theme 4-4"},
        {"taxonomy_id": "5", "risk_theme_id": "5.5", "risk_theme": "Mock Risk Theme 5-5"},
        {"taxonomy_id": "6", "risk_theme_id": "6.6", "risk_theme": "Mock Risk Theme 6-6"},
    ]


def choose_themes(
    *,
    control_id: str,
    hash_value: str,
    catalog: List[Dict[str, str]],
) -> Dict[str, Dict[str, str]]:
    seed_hex = hashlib.sha256("{}|{}".format(control_id, hash_value).encode("utf-8")).hexdigest()
    seed = int(seed_hex[:16], 16)

    primary = catalog[seed % len(catalog)]
    secondary = catalog[(seed // len(catalog) + 1) % len(catalog)]
    if len(catalog) > 1 and secondary == primary:
        secondary = catalog[(seed + 1) % len(catalog)]

    return {"primary": primary, "secondary": secondary}


def matches_taxonomy_filter(row: Dict[str, Any]) -> bool:
    return (
        is_active_status(row.get("control_status"))
        and is_key_control_yes(row.get("key_control"))
        and is_level_one(row.get("hierarchy_level"))
    )


def build_record(
    *,
    row: Dict[str, Any],
    hash_value: str,
    catalog: List[Dict[str, str]],
    previous_row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    control_id = str(row["control_id"])
    last_modified_on = row.get("last_modified_on")

    if not matches_taxonomy_filter(row):
        return {
            "control_id": control_id,
            "hash": hash_value,
            "parent_primary_risk_theme_id": None,
            "primary_risk_theme_id": None,
            "primary_risk_theme_reasoning": None,
            "parent_secondary_risk_theme_id": None,
            "secondary_risk_theme_id": None,
            "secondary_risk_theme_reasoning": None,
            "last_modified_on": last_modified_on,
        }

    if previous_row and previous_row.get("hash") == hash_value:
        return {
            "control_id": control_id,
            "hash": hash_value,
            "parent_primary_risk_theme_id": previous_row.get("parent_primary_risk_theme_id"),
            "primary_risk_theme_id": previous_row.get("primary_risk_theme_id"),
            "primary_risk_theme_reasoning": previous_row.get("primary_risk_theme_reasoning"),
            "parent_secondary_risk_theme_id": previous_row.get("parent_secondary_risk_theme_id"),
            "secondary_risk_theme_id": previous_row.get("secondary_risk_theme_id"),
            "secondary_risk_theme_reasoning": previous_row.get("secondary_risk_theme_reasoning"),
            "last_modified_on": last_modified_on,
        }

    themes = choose_themes(control_id=control_id, hash_value=hash_value, catalog=catalog)
    primary = themes["primary"]
    secondary = themes["secondary"]

    primary_reasoning = [
        "Filter matched: control_status=active, key_control=yes, hierarchy_level=Level 1.",
        "Selected from active taxonomy catalog via stable hash bucket.",
        "Primary risk theme: {} ({})".format(primary["risk_theme_id"], primary["risk_theme"]),
    ]
    secondary_reasoning = [
        "Secondary theme selected from a different stable bucket.",
        "Secondary risk theme: {} ({})".format(secondary["risk_theme_id"], secondary["risk_theme"]),
    ]

    return {
        "control_id": control_id,
        "hash": hash_value,
        "parent_primary_risk_theme_id": primary["taxonomy_id"],
        "primary_risk_theme_id": primary["risk_theme_id"],
        "primary_risk_theme_reasoning": primary_reasoning,
        "parent_secondary_risk_theme_id": secondary["taxonomy_id"],
        "secondary_risk_theme_id": secondary["risk_theme_id"],
        "secondary_risk_theme_reasoning": secondary_reasoning,
        "last_modified_on": last_modified_on,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.pipelines.controls.model_runners.run_taxonomy_mock",
        description="Run mock taxonomy model for controls.",
    )
    parser.add_argument("--upload-id", required=True, help="Upload ID (e.g. UPL-2026-0001)")
    parser.add_argument("--data-ingested-path", type=Path, default=None, help="Base data_ingested directory (default: from .env)")
    parser.add_argument("--taxonomy-catalog-jsonl", type=Path, default=None, help="Optional taxonomy catalog JSONL")
    parser.add_argument("--run-date", type=str, default=None, help="ISO date (default: today)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_date = args.run_date or default_run_date()
    data_ingested_path = resolve_data_ingested_path(args.data_ingested_path)

    # Input
    input_path = controls_jsonl_path(data_ingested_path, args.upload_id)
    if not input_path.exists():
        print(f"ERROR: Controls JSONL not found: {input_path}")
        return 1
    controls_rows = load_controls(input_path, limit=args.limit)

    # Catalog
    catalog = load_active_taxonomy_catalog(args.taxonomy_catalog_jsonl) if args.taxonomy_catalog_jsonl else fallback_catalog()

    # Output
    output_path = model_output_path(data_ingested_path, MODEL_NAME, args.upload_id)
    if output_path.exists() and not args.overwrite:
        print(f"ERROR: {output_path} already exists. Use --overwrite.")
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build records (no previous run reuse in simplified version)
    output_records = []
    hash_by_control_id = {}
    matched_count = 0

    for row in controls_rows:
        control_id = str(row["control_id"])
        hash_value = taxonomy_hash(row)
        hash_by_control_id[control_id] = hash_value
        record = build_record(row=row, hash_value=hash_value, catalog=catalog, previous_row=None)
        output_records.append(record)
        if matches_taxonomy_filter(row):
            matched_count += 1

    index_path = write_jsonl_with_index(
        records=output_records, output_path=output_path,
        model_name=MODEL_NAME, run_date=run_date,
        hash_by_control_id=hash_by_control_id,
    )

    print(f"output={output_path}")
    print(f"index={index_path}")
    print(f"rows={len(output_records)}")
    print(f"matched_filter={matched_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
