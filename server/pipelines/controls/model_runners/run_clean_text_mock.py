from __future__ import annotations

import argparse
import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.pipelines.controls.model_runners.common import (
    controls_jsonl_path,
    default_run_date,
    load_controls,
    load_jsonl_by_control_id,
    model_output_path,
    resolve_data_ingested_path,
    write_jsonl_with_index,
)

MODEL_NAME = "clean_text"

# ============================================================
# Text Cleaning Functions
# ============================================================

# Common "weird" chars seen in enterprise docs (PDF/Word/email exports)
ZERO_WIDTH = dict.fromkeys(
    map(
        ord,
        [
            "\u200b",
            "\u200c",
            "\u200d",
            "\u2060",
            "\ufeff",  # ZWSP/ZWNJ/ZWJ/WJ/BOM
        ],
    ),
    "",
)

# Normalize various dashes/quotes/bullets/arrows to stable ASCII-ish forms
TRANSLATE = str.maketrans(
    {
        # Quotes
        "\u2018": "'",
        "\u2019": "'",
        "\u201A": "'",
        "\u201B": "'",
        "\u201C": '"',
        "\u201D": '"',
        "\u201E": '"',
        "\u201F": '"',
        "\u00AB": '"',
        "\u00BB": '"',
        # Dashes/minus
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        # Bullets / list markers
        "\u2022": "-",
        "\u25CF": "-",
        "\u25E6": "-",
        "\u2043": "-",
        "\u2219": "-",
        "\u00B7": "-",
        # Arrows
        "\u2192": "->",
        "\u21D2": "=>",
        "\u27A1": "->",
        # Ellipsis
        "\u2026": "...",
        # Non-breaking / odd spaces
        "\u00A0": " ",
        "\u2007": " ",
        "\u202F": " ",
    }
)

_TRIPLE_QUOTE_RE = re.compile(r'("""|\'\'\')')
_CRLF_RE = re.compile(r"\r\n?")  # CRLF or CR -> LF
_HARD_WRAP_RE = re.compile(r"[ \t]*\n[ \t]*")  # normalize newline surrounds
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_CONTROL_EXCEPT_NL_TAB = re.compile(r"[\x00-\x08\x0B-\x1F\x7F]")  # keep \n (\x0A) and \t (\x09)
_TRAILING_SPACES_PER_LINE = re.compile(r"[ \t]+(?=\n)")


def clean_business_text(
    s: str,
    *,
    keep_newlines: bool = True,
    max_consecutive_newlines: int = 2,
    normalize_unicode: str = "NFC",  # "NFC" or "NFKC"
    strip: bool = True,
) -> str:
    """
    Cleans text coming from mixed business systems (PDF/Word/email/ETL).

    - Normalizes Unicode (NFC default)
    - Removes zero-width chars + BOM
    - Normalizes smart quotes/dashes/bullets/arrows/odd spaces
    - Normalizes line endings, trims trailing spaces, collapses repeated spaces/newlines
    - Removes control characters (except newline and tab)
    - Removes literal triple-quote markers
    """
    if s is None:
        return ""

    # Ensure it's a string
    if not isinstance(s, str):
        s = str(s)

    # Unicode normalization
    if normalize_unicode:
        s = unicodedata.normalize(normalize_unicode, s)

    # Remove zero-width chars / BOM
    s = s.translate(ZERO_WIDTH)

    # Normalize line endings
    s = _CRLF_RE.sub("\n", s)

    # Normalize common enterprise punctuation/symbol variants
    s = s.translate(TRANSLATE)

    # Remove literal triple quote markers often introduced by dumps
    s = _TRIPLE_QUOTE_RE.sub("", s)

    # Remove other control chars
    s = _CONTROL_EXCEPT_NL_TAB.sub("", s)

    # Remove trailing spaces on each line
    s = _TRAILING_SPACES_PER_LINE.sub("", s)

    # Normalize newline surrounding spaces
    s = _HARD_WRAP_RE.sub("\n", s)

    # Collapse repeated spaces (keep tabs as-is)
    s = _MULTI_SPACE_RE.sub(" ", s)

    if keep_newlines:
        # Collapse excessive blank lines
        if max_consecutive_newlines is not None and max_consecutive_newlines >= 1:
            s = re.sub(
                r"\n{" + str(max_consecutive_newlines + 1) + r",}",
                "\n" * max_consecutive_newlines,
                s,
            )
        else:
            s = _MULTI_NEWLINE_RE.sub("\n\n", s)
    else:
        # Turn newlines into spaces
        s = re.sub(r"\n+", " ", s)
        s = _MULTI_SPACE_RE.sub(" ", s)

    return s.strip() if strip else s


def clean_nullable_text(value: Any, *, keep_newlines: bool = True) -> Optional[str]:
    cleaned = clean_business_text(value, keep_newlines=keep_newlines)
    return cleaned if cleaned else None


def clean_text_hash(
    control_row: Dict[str, Any],
    enrichment_row: Optional[Dict[str, Any]],
) -> str:
    enrichment_row = enrichment_row or {}
    parts = [
        clean_business_text(control_row.get("control_title"), keep_newlines=False),
        clean_business_text(control_row.get("control_description"), keep_newlines=False),
        clean_business_text(control_row.get("evidence_description"), keep_newlines=False),
        clean_business_text(control_row.get("local_functional_information"), keep_newlines=False),
        clean_business_text(enrichment_row.get("control_as_event"), keep_newlines=False),
        clean_business_text(enrichment_row.get("control_as_issues"), keep_newlines=False),
    ]
    payload = "|".join(parts)
    if not payload:
        payload = str(control_row.get("control_id") or "")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    bucket = int(digest[:16], 16) % 10000
    return "CL{:04d}".format(bucket)


def build_record(
    *,
    control_row: Dict[str, Any],
    enrichment_row: Optional[Dict[str, Any]],
    previous_row: Optional[Dict[str, Any]],
    can_reuse_previous: bool,
) -> Dict[str, Any]:
    control_id = str(control_row["control_id"])
    last_modified_on = control_row.get("last_modified_on")

    if previous_row and can_reuse_previous:
        return {
            "control_id": control_id,
            "hash": None,
            "last_modified_on": last_modified_on,
            "control_title": previous_row.get("control_title"),
            "control_description": previous_row.get("control_description"),
            "evidence_description": previous_row.get("evidence_description"),
            "local_functional_information": previous_row.get("local_functional_information"),
            "control_as_event": previous_row.get("control_as_event"),
            "control_as_issues": previous_row.get("control_as_issues"),
        }

    return {
        "control_id": control_id,
        "hash": None,
        "last_modified_on": last_modified_on,
        "control_title": clean_nullable_text(control_row.get("control_title")),
        "control_description": clean_nullable_text(control_row.get("control_description")),
        "evidence_description": clean_nullable_text(control_row.get("evidence_description")),
        "local_functional_information": clean_nullable_text(control_row.get("local_functional_information")),
        "control_as_event": clean_nullable_text((enrichment_row or {}).get("control_as_event")),
        "control_as_issues": clean_nullable_text((enrichment_row or {}).get("control_as_issues")),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.pipelines.controls.model_runners.run_clean_text_mock",
        description="Run mock clean_text model for controls.",
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
    hash_by_control_id = {}

    for control_row in controls_rows:
        control_id = str(control_row["control_id"])
        enrichment_row = enrichment_rows.get(control_id)
        hash_value = clean_text_hash(control_row, enrichment_row)
        hash_by_control_id[control_id] = hash_value
        output_records.append(build_record(
            control_row=control_row, enrichment_row=enrichment_row,
            previous_row=None, can_reuse_previous=False,
        ))

    index_path = write_jsonl_with_index(
        records=output_records, output_path=output_path,
        model_name=MODEL_NAME, run_date=run_date,
        hash_by_control_id=hash_by_control_id,
    )

    print(f"enrichment_input={enrichment_path if enrichment_rows else 'none'}")
    print(f"output={output_path}")
    print(f"index={index_path}")
    print(f"rows={len(output_records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
