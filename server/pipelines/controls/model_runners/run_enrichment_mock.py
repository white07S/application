from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.pipelines.controls.model_runners.common import (
    controls_jsonl_path,
    default_run_date,
    is_active_status,
    load_controls,
    model_output_path,
    normalize_text,
    resolve_data_ingested_path,
    write_jsonl_with_index,
)

MODEL_NAME = "enrichment"

ENRICHMENT_FIELDS = [
    "summary",
    "what_yes_no",
    "what_details",
    "where_yes_no",
    "where_details",
    "who_yes_no",
    "who_details",
    "when_yes_no",
    "when_details",
    "why_yes_no",
    "why_details",
    "what_why_yes_no",
    "what_why_details",
    "risk_theme_yes_no",
    "risk_theme_details",
    "people",
    "process",
    "product",
    "service",
    "regulations",
    "frequency_yes_no",
    "frequency_details",
    "preventative_detective_yes_no",
    "preventative_detective_details",
    "automation_level_yes_no",
    "automation_level_details",
    "followup_yes_no",
    "followup_details",
    "escalation_yes_no",
    "escalation_details",
    "evidence_yes_no",
    "evidence_details",
    "abbreviations_yes_no",
    "abbreviations_details",
    "control_as_issues",
    "control_as_event",
]


def enrichment_hash(row: Dict[str, Any]) -> str:
    # Runner-specific hash: include enrichment-driving features.
    parts = [
        str(row.get("control_status") or "").strip().lower(),
        str(row.get("control_title") or "").strip().lower(),
        str(row.get("control_description") or "").strip().lower(),
        str(row.get("evidence_description") or "").strip().lower(),
        str(row.get("local_functional_information") or "").strip().lower(),
        str(row.get("execution_frequency") or "").strip().lower(),
        str(row.get("owning_organization_location_id") or "").strip().lower(),
        str(row.get("control_owner") or "").strip().lower(),
        str(row.get("preventative_detective") or "").strip().lower(),
        str(row.get("manual_automated") or "").strip().lower(),
        str(bool(row.get("risk_theme"))).lower(),
    ]
    payload = "|".join(parts)
    if not payload:
        payload = str(row.get("control_id") or "")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    bucket = int(digest[:16], 16) % 10000
    return "EN{:04d}".format(bucket)


def _yes_no(condition: bool) -> str:
    return "yes" if condition else "no"


def _seed_int(control_id: str, hash_value: str) -> int:
    digest = hashlib.sha256("{}|{}".format(control_id, hash_value).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def null_enrichment_payload() -> Dict[str, Any]:
    return {field: None for field in ENRICHMENT_FIELDS}


def build_active_payload(row: Dict[str, Any], hash_value: str) -> Dict[str, Any]:
    control_id = str(row["control_id"])
    title = normalize_text(row.get("control_title"))
    desc = normalize_text(row.get("control_description"))
    evidence = normalize_text(row.get("evidence_description"))
    local_info = normalize_text(row.get("local_functional_information"))
    seed = _seed_int(control_id, hash_value)

    summary = desc or title
    if summary:
        summary = summary[:240]

    when_hint = normalize_text(row.get("execution_frequency"))
    where_hint = normalize_text(row.get("owning_organization_location_id"))
    who_hint = normalize_text(row.get("control_owner"))
    preventative_detective = normalize_text(row.get("preventative_detective"))
    automation_level = normalize_text(row.get("manual_automated"))

    payload = {
        "summary": summary,
        "what_yes_no": _yes_no(bool(title or desc)),
        "what_details": desc or title,
        "where_yes_no": _yes_no(bool(where_hint)),
        "where_details": where_hint,
        "who_yes_no": _yes_no(bool(who_hint)),
        "who_details": who_hint,
        "when_yes_no": _yes_no(bool(when_hint)),
        "when_details": when_hint,
        "why_yes_no": _yes_no(bool(desc)),
        "why_details": "Control objective inferred from description." if desc else None,
        "what_why_yes_no": _yes_no(bool(title and desc)),
        "what_why_details": "What/Why linkage present in source control text." if title and desc else None,
        "risk_theme_yes_no": _yes_no(bool(row.get("risk_theme"))),
        "risk_theme_details": "risk_theme entries: {}".format(len(row.get("risk_theme") or [])),
        "people": normalize_text(row.get("control_owner")) or normalize_text(row.get("control_assessor")),
        "process": title,
        "product": normalize_text(row.get("it_application_system_supporting_control_instance")),
        "service": normalize_text(row.get("kpci_governance_forum")),
        "regulations": "SOX" if row.get("sox_relevant") else None,
        "frequency_yes_no": _yes_no(bool(when_hint)),
        "frequency_details": when_hint,
        "preventative_detective_yes_no": _yes_no(bool(preventative_detective)),
        "preventative_detective_details": preventative_detective,
        "automation_level_yes_no": _yes_no(bool(automation_level)),
        "automation_level_details": automation_level,
        "followup_yes_no": "yes" if seed % 2 == 0 else "no",
        "followup_details": "Follow-up cadence tracked in mock workflow." if seed % 2 == 0 else None,
        "escalation_yes_no": "yes" if seed % 5 in {0, 1} else "no",
        "escalation_details": "Escalation path documented in mock metadata." if seed % 5 in {0, 1} else None,
        "evidence_yes_no": _yes_no(bool(evidence)),
        "evidence_details": evidence,
        "abbreviations_yes_no": "yes" if seed % 7 == 0 else "no",
        "abbreviations_details": "Abbreviations detected in mock parsing." if seed % 7 == 0 else None,
        "control_as_issues": local_info,
        "control_as_event": evidence or desc,
    }
    return payload


def build_record(
    *,
    row: Dict[str, Any],
    hash_value: str,
    previous_row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    control_id = str(row["control_id"])
    last_modified_on = row.get("last_modified_on")

    if is_active_status(row.get("control_status")):
        if previous_row and previous_row.get("hash") == hash_value:
            payload = {
                field: previous_row.get(field)
                for field in ENRICHMENT_FIELDS
            }
        else:
            payload = build_active_payload(row, hash_value)
    else:
        payload = null_enrichment_payload()

    record = {
        "control_id": control_id,
        "hash": hash_value,
        "last_modified_on": last_modified_on,
    }
    record.update(payload)
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.pipelines.controls.model_runners.run_enrichment_mock",
        description="Run mock enrichment model for controls.",
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

    output_path = model_output_path(data_ingested_path, MODEL_NAME, args.upload_id)
    if output_path.exists() and not args.overwrite:
        print(f"ERROR: {output_path} already exists. Use --overwrite.")
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_records = []
    hash_by_control_id = {}
    matched_count = 0

    for row in controls_rows:
        control_id = str(row["control_id"])
        hash_value = enrichment_hash(row)
        hash_by_control_id[control_id] = hash_value
        if is_active_status(row.get("control_status")):
            matched_count += 1
        output_records.append(build_record(row=row, hash_value=hash_value, previous_row=None))

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
