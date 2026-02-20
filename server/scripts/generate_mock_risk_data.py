"""Generate mock risk-theme JSONL data into the context_providers directory.

Produces a single file::

    {CONTEXT_PROVIDERS_PATH}/risk_theme/{today}/risk_theme.jsonl

Reads CONTEXT_PROVIDERS_PATH from .env by default.

Usage:
    python -m server.scripts.generate_mock_risk_data
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

SEED = 42
DEFAULT_ROWS = 25


# ---------------------------------------------------------------------------
# Generator (adapted from new_mock_data/mock_data/risk_themes/risk_themes_mock.py)
# ---------------------------------------------------------------------------

def _iso8601(rng: random.Random) -> str:
    base = datetime(2026, 1, 23, 12, 39, 33, tzinfo=timezone.utc)
    jitter = timedelta(seconds=rng.randint(-3600, 3600))
    return (base + jitter).isoformat().replace("+00:00", "+00:00")


def generate_risk_theme_jsonl(out_path: Path, *, seed: int = SEED, rows: int = DEFAULT_ROWS) -> int:
    """Write *rows* mock risk-theme records to *out_path* and return the count."""
    rng = random.Random(seed)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for i in range(1, rows + 1):
            taxonomy_idx = ((i - 1) % 6) + 1
            rt_idx = ((i - 1) % 8) + 1
            taxonomy_id = str(taxonomy_idx)
            taxonomy = f"Mock Taxonomy {taxonomy_idx}"
            taxonomy_description = f"Description for {taxonomy}."
            risk_theme_id = f"{taxonomy_idx}.{rt_idx}"
            risk_theme = f"Mock Risk Theme {taxonomy_idx}-{rt_idx}"
            risk_theme_description = f"Description for {risk_theme}."
            risk_theme_mapping_considerations = (
                f"Map data points related to {risk_theme}. "
                f"Notes: {rng.choice(['scope', 'controls', 'process', 'people', 'systems'])}."
            )
            status = rng.choice(["Active", "Expired"])
            row = {
                "taxonomy_id": taxonomy_id,
                "taxonomy": taxonomy,
                "taxonomy_description": taxonomy_description,
                "risk_theme_id": risk_theme_id,
                "risk_theme": risk_theme,
                "risk_theme_description": risk_theme_description,
                "risk_theme_mapping_considerations": risk_theme_mapping_considerations,
                "status": status,
                "last_updated_on": _iso8601(rng),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1

    return count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.scripts.generate_mock_risk_data",
        description="Generate mock risk-theme JSONL into the context_providers directory.",
    )
    parser.add_argument(
        "--context-providers-path",
        type=Path,
        default=None,
        help="Root context_providers directory. Defaults to CONTEXT_PROVIDERS_PATH from .env.",
    )
    parser.add_argument("--date", type=str, default=None, help="Date folder name (default: today, YYYY-MM-DD).")
    parser.add_argument("--seed", type=int, default=SEED, help="RNG seed.")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS, help="Number of rows to generate.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    # Resolve context_providers path
    if args.context_providers_path is not None:
        ctx_path = args.context_providers_path.resolve()
    else:
        from server.settings import get_settings
        ctx_path = get_settings().context_providers_path.resolve()

    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = ctx_path / "risk_theme" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "risk_theme.jsonl"
    n = generate_risk_theme_jsonl(out_path, seed=args.seed, rows=args.rows)
    print(f"Wrote {n:,} rows -> {out_path}")


if __name__ == "__main__":
    main()
