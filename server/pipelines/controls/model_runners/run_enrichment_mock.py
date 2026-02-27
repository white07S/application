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
    load_controls,
    model_output_path,
    normalize_text,
    resolve_data_ingested_path,
    write_jsonl_with_index,
)

MODEL_NAME = "enrichment"

# 7 W criteria fields (Level 1 scoring)
W_CRITERIA_YES_NO = [
    "what_yes_no", "where_yes_no", "who_yes_no", "when_yes_no",
    "why_yes_no", "what_why_yes_no", "risk_theme_yes_no",
]
W_CRITERIA_DETAILS = [
    "what_details", "where_details", "who_details", "when_details",
    "why_details", "what_why_details", "risk_theme_details",
]

# 7 operational criteria fields (Level 2 scoring)
OP_CRITERIA_YES_NO = [
    "frequency_yes_no", "preventative_detective_yes_no",
    "automation_level_yes_no", "followup_yes_no",
    "escalation_yes_no", "evidence_yes_no", "abbreviations_yes_no",
]
OP_CRITERIA_DETAILS = [
    "frequency_details", "preventative_detective_details",
    "automation_level_details", "followup_details",
    "escalation_details", "evidence_details", "abbreviations_details",
]

# Narrative fields (populated for all qualifying controls regardless of level)
NARRATIVE_FIELDS = [
    "summary", "roles", "process", "product", "service",
]

ENRICHMENT_FIELDS = [
    "summary",
    "what_yes_no", "what_details",
    "where_yes_no", "where_details",
    "who_yes_no", "who_details",
    "when_yes_no", "when_details",
    "why_yes_no", "why_details",
    "what_why_yes_no", "what_why_details",
    "risk_theme_yes_no", "risk_theme_details",
    "roles", "process", "product", "service",
    "frequency_yes_no", "frequency_details",
    "preventative_detective_yes_no", "preventative_detective_details",
    "automation_level_yes_no", "automation_level_details",
    "followup_yes_no", "followup_details",
    "escalation_yes_no", "escalation_details",
    "evidence_yes_no", "evidence_details",
    "abbreviations_yes_no", "abbreviations_details",
]


def enrichment_hash(row: Dict[str, Any]) -> str:
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


def _build_w_criteria(
    row: Dict[str, Any],
    hash_value: str,
    text_pool_entry: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build the 7 W criteria fields (Level 1 scoring).

    Uses text pool from dataset for meaningful what/why/where details when
    available.  Coverage targets (for L1 Active Key):
      what  = 100%
      why   =  99%  (skip when seed % 100 == 0)
      where =  98%  (skip when seed % 50  == 0)
    """
    control_id = str(row["control_id"])
    seed = _seed_int(control_id, hash_value)

    title = normalize_text(row.get("control_title"))
    desc = normalize_text(row.get("control_description"))
    when_hint = normalize_text(row.get("execution_frequency"))
    where_hint = normalize_text(row.get("owning_organization_location_id"))
    who_hint = normalize_text(row.get("control_owner"))

    # ── what_details: 100% coverage ──
    if text_pool_entry and text_pool_entry.get("what"):
        what_details = text_pool_entry["what"]
    else:
        what_details = desc or title

    # ── why_details: 99% coverage ──
    if seed % 100 == 0:
        why_details = None
    elif text_pool_entry and text_pool_entry.get("why"):
        why_details = text_pool_entry["why"]
    else:
        why_details = desc or title

    # ── where_details: 98% coverage ──
    if seed % 50 == 0:
        where_details = None
    elif text_pool_entry and text_pool_entry.get("where"):
        where_details = text_pool_entry["where"]
    else:
        where_details = where_hint

    return {
        "what_yes_no": _yes_no(bool(what_details)),
        "what_details": what_details,
        "where_yes_no": _yes_no(bool(where_details)),
        "where_details": where_details,
        "who_yes_no": _yes_no(bool(who_hint)),
        "who_details": who_hint,
        "when_yes_no": _yes_no(bool(when_hint)),
        "when_details": when_hint,
        "why_yes_no": _yes_no(bool(why_details)),
        "why_details": why_details,
        "what_why_yes_no": _yes_no(bool(what_details and why_details)),
        "what_why_details": "What/Why linkage present in source control text." if what_details and why_details else None,
        "risk_theme_yes_no": _yes_no(bool(row.get("risk_theme"))),
        "risk_theme_details": "risk_theme entries: {}".format(len(row.get("risk_theme") or [])),
    }


def _build_operational_criteria(row: Dict[str, Any], hash_value: str) -> Dict[str, Any]:
    """Build the 7 operational criteria fields (Level 2 scoring)."""
    control_id = str(row["control_id"])
    seed = _seed_int(control_id, hash_value)
    evidence = normalize_text(row.get("evidence_description"))
    when_hint = normalize_text(row.get("execution_frequency"))
    preventative_detective = normalize_text(row.get("preventative_detective"))
    automation_level = normalize_text(row.get("manual_automated"))

    return {
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
    }


def _build_narrative_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    """Build narrative fields populated for all qualifying controls."""
    title = normalize_text(row.get("control_title"))
    desc = normalize_text(row.get("control_description"))

    summary = desc or title
    if summary:
        summary = summary[:240]

    return {
        "summary": summary,
        "roles": normalize_text(row.get("control_owner")) or normalize_text(row.get("control_assessor")),
        "process": title,
        "product": normalize_text(row.get("it_application_system_supporting_control_instance")),
        "service": normalize_text(row.get("kpci_governance_forum")),
    }


def _null_w_criteria() -> Dict[str, Any]:
    """Return None for all 7 W criteria fields."""
    result = {}
    for yn, det in zip(W_CRITERIA_YES_NO, W_CRITERIA_DETAILS):
        result[yn] = None
        result[det] = None
    return result


def _null_operational_criteria() -> Dict[str, Any]:
    """Return None for all 7 operational criteria fields."""
    result = {}
    for yn, det in zip(OP_CRITERIA_YES_NO, OP_CRITERIA_DETAILS):
        result[yn] = None
        result[det] = None
    return result


def build_l1_payload(
    row: Dict[str, Any],
    hash_value: str,
    text_pool_entry: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build enrichment payload for Level 1 + Active + Key Control.

    Populates: 7 W criteria (with meaningful what/why/where from text pool)
               + narrative fields.
    Sets: 7 operational criteria to None, control_as_event/issues to None.
    """
    payload = {}
    payload.update(_build_w_criteria(row, hash_value, text_pool_entry))
    payload.update(_null_operational_criteria())
    payload.update(_build_narrative_fields(row))
    return payload


def build_l2_payload(
    row: Dict[str, Any],
    hash_value: str,
    text_pool_entry: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build enrichment payload for Level 2 + Active + Key Control.

    Populates: 7 operational criteria + narrative fields.
    Sets: 7 W criteria to None, control_as_event/issues to None.
    L2 controls inherit what/why/where from L1 parent, not populated here.
    """
    payload = {}
    payload.update(_null_w_criteria())
    payload.update(_build_operational_criteria(row, hash_value))
    payload.update(_build_narrative_fields(row))
    return payload


def build_record(
    *,
    row: Dict[str, Any],
    hash_value: str,
    run_date: str,
    previous_row: Optional[Dict[str, Any]],
    text_pool_entry: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    control_id = str(row["control_id"])

    status_active = is_active_status(row.get("control_status"))
    key_ctrl = is_key_control_yes(row.get("key_control"))
    level_one = is_level_one(row.get("hierarchy_level"))

    if status_active and key_ctrl:
        if previous_row and previous_row.get("hash") == hash_value:
            payload = {
                field: previous_row.get(field)
                for field in ENRICHMENT_FIELDS
            }
        elif level_one:
            payload = build_l1_payload(row, hash_value, text_pool_entry)
        else:
            payload = build_l2_payload(row, hash_value, text_pool_entry)
    elif level_one:
        # L1 controls always get W-criteria even if not Active/Key,
        # because Level 2 children inherit W-criteria from their parent.
        payload = build_l1_payload(row, hash_value, text_pool_entry)
    else:
        payload = null_enrichment_payload()

    record = {
        "control_id": control_id,
        "hash": hash_value,
        "model_run_timestamp": run_date,
    }
    record.update(payload)
    return record


# ── Intentional duplicate clusters for testing similarity ──────────

# Near-duplicate templates: controls sharing ALL 3 features → score ~1.0
NEAR_DUPLICATE_TEMPLATES = [
    {
        "what": "This control ensures that all bank reconciliation entries are reviewed and approved by an independent party within five business days of month-end close to prevent material misstatements.",
        "why": "Required by SOX Section 404 and internal audit standards to ensure completeness and accuracy of financial reporting and to mitigate the risk of undetected errors in cash balances.",
        "where": "Finance Operations — Treasury and Cash Management division across all regional entities.",
    },
    {
        "what": "Automated validation of trade settlement amounts against counterparty confirmations prior to release of payment instructions through the SWIFT messaging platform.",
        "why": "Regulatory requirement under MiFID II and internal risk framework to prevent settlement failures and reduce operational losses from incorrect payment instructions.",
        "where": "Capital Markets Operations — Trade Settlement and Confirmation unit in London and New York.",
    },
    {
        "what": "Quarterly review of user access rights to critical financial applications including SAP, Oracle EBS, and Bloomberg Terminal to identify and remove inappropriate or excessive privileges.",
        "why": "Mandated by information security policy and SOX ITGC requirements to enforce least-privilege access and prevent unauthorized transactions or data manipulation.",
        "where": "Information Technology — Identity and Access Management team, global scope.",
    },
    {
        "what": "Daily monitoring of intercompany loan balances and automated alerting when balances exceed pre-approved credit limits or deviate more than five percent from expected values.",
        "why": "Transfer pricing compliance and liquidity risk management require continuous monitoring to prevent regulatory penalties and ensure adequate cash flow across entities.",
        "where": "Group Treasury — Intercompany Lending and Borrowing desk, headquarters.",
    },
    {
        "what": "Three-way matching of purchase orders, goods receipts, and vendor invoices before payment authorization, with automated exception flagging for discrepancies exceeding one thousand euros.",
        "why": "Procurement policy and internal controls framework require three-way matching to prevent duplicate payments, overpayments, and fraudulent invoices.",
        "where": "Accounts Payable — Procure-to-Pay operations center serving European entities.",
    },
    {
        "what": "Annual stress testing of credit risk models using macroeconomic scenarios defined by the central bank, with results reported to the board risk committee within thirty days.",
        "why": "Basel III Pillar 2 requirements and supervisory expectations mandate regular stress testing to assess capital adequacy under adverse conditions.",
        "where": "Risk Management — Credit Risk Analytics team, group level.",
    },
]

# Weak-similar templates: controls sharing 2 of 3 features → score ~0.67
# Each group has a shared pair (what+why, what+where, or why+where) and a unique third field
WEAK_SIMILAR_TEMPLATES = [
    {   # Share what + why, different where
        "what": "Monthly reconciliation of derivative instrument valuations between front-office pricing models and independent third-party valuations to detect pricing discrepancies.",
        "why": "IFRS 13 fair value hierarchy and internal risk policy require independent price verification to ensure accurate mark-to-market reporting.",
        "unique_field": "where",
        "variants": [
            "Derivatives Trading — Interest Rate Swaps desk in Frankfurt.",
            "Structured Products — Credit Derivatives team in Singapore.",
            "FX Options — Currency Derivatives unit in Tokyo.",
            "Commodities Trading — Energy Derivatives desk in Houston.",
        ],
    },
    {   # Share what + where, different why
        "what": "Weekly review of suspicious activity monitoring alerts generated by the transaction monitoring system, with escalation of confirmed cases to the financial intelligence unit.",
        "unique_field": "why",
        "where": "Compliance — Anti-Money Laundering operations center, all jurisdictions.",
        "variants": [
            "AML regulations under the Bank Secrecy Act require timely investigation of potentially suspicious transactions to avoid regulatory penalties.",
            "EU Anti-Money Laundering Directive mandates continuous monitoring and reporting of unusual transaction patterns to national authorities.",
            "FATF recommendations and local regulatory expectations require robust transaction surveillance to combat terrorist financing.",
            "Internal compliance framework demands proactive detection and escalation of potential financial crime to protect institutional reputation.",
        ],
    },
    {   # Share why + where, different what
        "why": "Data privacy regulations including GDPR Article 32 require appropriate technical measures to protect personal data and demonstrate accountability to supervisory authorities.",
        "where": "Data Protection Office — Privacy Engineering team, European operations.",
        "unique_field": "what",
        "variants": [
            "Annual data protection impact assessment for all high-risk processing activities involving customer personal data and sensitive financial information.",
            "Automated scanning of databases and file shares to detect and classify unencrypted personal data stores and trigger remediation workflows.",
            "Quarterly audit of data retention schedules to verify that expired personal data records are purged according to the approved retention policy.",
            "Review of third-party data processor agreements to confirm contractual data protection clauses align with current regulatory requirements.",
        ],
    },
    {   # Share what + why, different where
        "what": "Dual authorization requirement for all wire transfers exceeding fifty thousand USD or equivalent, with segregation between payment initiator and approver roles.",
        "why": "Payment fraud prevention policy and banking regulations require maker-checker controls on high-value outgoing payments to prevent unauthorized fund transfers.",
        "unique_field": "where",
        "variants": [
            "Treasury Operations — Payments Processing team in Zurich.",
            "Corporate Banking — Client Payments unit in Dublin.",
            "Retail Banking — High-Value Payments desk in Amsterdam.",
            "Private Banking — Wealth Management transfers team in Geneva.",
        ],
    },
    {   # Share what + where, different why
        "what": "Automated daily backup verification of core banking databases with integrity checksums and monthly restore testing to validate recoverability within the four-hour RTO target.",
        "unique_field": "why",
        "where": "IT Infrastructure — Database Administration team, primary and disaster recovery data centers.",
        "variants": [
            "Business continuity management policy requires validated backup and recovery capabilities to ensure operational resilience during system failures.",
            "Regulatory expectations from the central bank mandate demonstrable disaster recovery capabilities with tested recovery time objectives.",
            "Internal audit findings require formalized backup verification procedures after previous incidents of corrupted backup media went undetected.",
            "SOX ITGC requirements demand evidence of regular backup testing to support the reliability of financial reporting systems.",
        ],
    },
    {   # Share why + where, different what
        "why": "Vendor risk management policy requires ongoing assessment of critical third-party providers to ensure service continuity and protect against concentration risk.",
        "where": "Procurement — Third Party Risk Management function, enterprise-wide.",
        "unique_field": "what",
        "variants": [
            "Annual financial health assessment of tier-one vendors including review of audited financial statements, credit ratings, and insurance coverage adequacy.",
            "Quarterly service level agreement performance review meetings with critical technology vendors to track delivery against contractual commitments.",
            "Biannual on-site audit of key outsourcing partners to verify compliance with information security requirements and data handling procedures.",
            "Continuous monitoring of critical vendor cybersecurity posture through automated threat intelligence feeds and security rating platforms.",
        ],
    },
]


def _inject_similarity_clusters(
    output_records: List[Dict[str, Any]],
    controls_rows: List[Dict[str, Any]],
) -> int:
    """Post-process enrichment records to inject intentional duplicate clusters.

    Finds L1 Active Key controls and overwrites their what/why/where details
    with shared template text to create near-duplicate and weak-similar pairs.

    Returns the number of controls modified.
    """
    # Find indices of L1 Active Key controls
    l1_ak_indices = []
    for idx, row in enumerate(controls_rows):
        if (
            is_level_one(row.get("hierarchy_level"))
            and is_active_status(row.get("control_status"))
            and is_key_control_yes(row.get("key_control"))
        ):
            l1_ak_indices.append(idx)

    if len(l1_ak_indices) < 100:
        return 0  # Not enough controls to inject clusters

    modified = 0
    cluster_size = 4
    cursor = 0  # Index into l1_ak_indices

    # Near-duplicate clusters: overwrite all 3 features with shared text
    for template in NEAR_DUPLICATE_TEMPLATES:
        if cursor + cluster_size > len(l1_ak_indices):
            break
        for k in range(cluster_size):
            rec_idx = l1_ak_indices[cursor + k]
            output_records[rec_idx]["what_details"] = template["what"]
            output_records[rec_idx]["why_details"] = template["why"]
            output_records[rec_idx]["where_details"] = template["where"]
            # Update yes_no flags to reflect populated fields
            output_records[rec_idx]["what_yes_no"] = "yes"
            output_records[rec_idx]["why_yes_no"] = "yes"
            output_records[rec_idx]["where_yes_no"] = "yes"
            modified += 1
        cursor += cluster_size

    # Weak-similar clusters: share 2 features, vary the third
    for template in WEAK_SIMILAR_TEMPLATES:
        if cursor + cluster_size > len(l1_ak_indices):
            break
        unique = template["unique_field"]
        for k in range(cluster_size):
            rec_idx = l1_ak_indices[cursor + k]
            # Set the two shared features
            if unique != "what":
                output_records[rec_idx]["what_details"] = template["what"]
                output_records[rec_idx]["what_yes_no"] = "yes"
            if unique != "why":
                output_records[rec_idx]["why_details"] = template["why"]
                output_records[rec_idx]["why_yes_no"] = "yes"
            if unique != "where":
                output_records[rec_idx]["where_details"] = template["where"]
                output_records[rec_idx]["where_yes_no"] = "yes"
            # Set the unique/variant field
            variant_text = template["variants"][k % len(template["variants"])]
            output_records[rec_idx][f"{unique}_details"] = variant_text
            output_records[rec_idx][f"{unique}_yes_no"] = "yes"
            modified += 1
        cursor += cluster_size

    return modified


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.pipelines.controls.model_runners.run_enrichment_mock",
        description="Run mock enrichment model for controls.",
    )
    parser.add_argument("--upload-id", required=True, help="Upload ID (e.g. UPL-2026-0001)")
    parser.add_argument("--data-ingested-path", type=Path, default=None, help="Base data_ingested directory (default: from .env)")
    parser.add_argument("--run-date", type=str, default=None, help="ISO date (default: today)")
    parser.add_argument("--qdrant-dataset-path", type=Path, default=None, help="Path to Qdrant/DBpedia Arrow IPC dataset for real text")
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

    # Load text pool from dataset if path provided
    text_pool: Optional[list] = None
    if args.qdrant_dataset_path is not None:
        from server.pipelines.controls.model_runners.dataset_pool import load_text_pool
        print(f"Loading text pool from dataset: {args.qdrant_dataset_path}")
        text_pool = load_text_pool(args.qdrant_dataset_path, len(controls_rows))
        print(f"Loaded text pool for {len(text_pool)} controls")

    output_path = model_output_path(data_ingested_path, MODEL_NAME, args.upload_id)
    if output_path.exists() and not args.overwrite:
        print(f"ERROR: {output_path} already exists. Use --overwrite.")
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_records = []
    hashes_by_control_id: Dict[str, Dict[str, Optional[str]]] = {}
    l1_matched = 0
    l2_matched = 0
    skipped = 0

    for idx, row in enumerate(controls_rows):
        control_id = str(row["control_id"])
        hash_value = enrichment_hash(row)
        hashes_by_control_id[control_id] = {"hash": hash_value}

        pool_entry = text_pool[idx] if text_pool is not None and idx < len(text_pool) else None

        status_active = is_active_status(row.get("control_status"))
        key_ctrl = is_key_control_yes(row.get("key_control"))

        if status_active and key_ctrl:
            if is_level_one(row.get("hierarchy_level")):
                l1_matched += 1
            else:
                l2_matched += 1
        else:
            skipped += 1

        output_records.append(build_record(
            row=row, hash_value=hash_value, run_date=run_date,
            previous_row=None, text_pool_entry=pool_entry,
        ))

    # Inject intentional duplicate clusters for similarity testing
    n_injected = _inject_similarity_clusters(output_records, controls_rows)

    index_path = write_jsonl_with_index(
        records=output_records, output_path=output_path,
        model_name=MODEL_NAME, run_date=run_date,
        hashes_by_control_id=hashes_by_control_id,
    )

    print(f"output={output_path}")
    print(f"index={index_path}")
    print(f"rows={len(output_records)}")
    print(f"l1_enriched={l1_matched}")
    print(f"l2_enriched={l2_matched}")
    print(f"skipped={skipped}")
    print(f"similarity_clusters_injected={n_injected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
