"""Generate mock organisation-chart and assessment-unit JSONL data.

Produces four files::

    {CONTEXT_PROVIDERS_PATH}/organization/{today}/functions.jsonl
    {CONTEXT_PROVIDERS_PATH}/organization/{today}/locations.jsonl
    {CONTEXT_PROVIDERS_PATH}/organization/{today}/consolidated.jsonl
    {CONTEXT_PROVIDERS_PATH}/assessment_unit/{today}/assessment_units.jsonl

Reads CONTEXT_PROVIDERS_PATH from .env by default.

Usage:
    python -m server.scripts.generate_mock_org_data

Adapted from new_mock_data/mock_data/org_charts/org_mock.py — full-scale
realistic distributions (~64k functions, ~21k locations, ~21k consolidated).
"""

from __future__ import annotations

import argparse
import json
import random
import string
import sys
from bisect import bisect_left
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, TypeVar

try:
    import orjson  # type: ignore

    def _json_dumps_bytes(obj: dict) -> bytes:
        return orjson.dumps(obj)
except ImportError:
    def _json_dumps_bytes(obj: dict) -> bytes:  # type: ignore[misc]
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

SEED = 42

# ---------------------------------------------------------------------------
# Row counts (matching real-world scale)
# ---------------------------------------------------------------------------
_FUNCTIONS_TOTAL_ROWS = 64907
_LOCATIONS_TOTAL_ROWS = 21186
_CONSOLIDATED_TOTAL_ROWS = 21570
_ASSESSMENT_UNITS_DEFAULT_ROWS = 200

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
T = TypeVar("T")


def _expand_distribution(dist: dict[int, int], rng: random.Random) -> list[int]:
    out: list[int] = []
    for k, v in dist.items():
        out.extend([k] * v)
    rng.shuffle(out)
    return out


def _make_list_from_counts(counts: dict[T, int], rng: random.Random) -> list[T]:
    out: list[T] = []
    for value, count in counts.items():
        out.extend([value] * count)
    rng.shuffle(out)
    return out


def _star_date_prefix(rng: random.Random) -> str:
    day = rng.randint(1, 28)
    month = rng.randint(1, 12)
    return f"*{day:02d}/{month:02d} "


def _pair_degrees_with_internal_counts(
    degree_dist: dict[int, int],
    internal_children_dist: dict[int, int],
    *,
    rng: random.Random,
) -> list[tuple[int, int]]:
    degrees: list[int] = []
    for d, c in degree_dist.items():
        degrees.extend([d] * c)
    internal_counts: list[int] = []
    for k, c in internal_children_dist.items():
        internal_counts.extend([k] * c)
    degrees.sort()
    internal_counts.sort(reverse=True)
    pairs: list[tuple[int, int]] = []
    for k in internal_counts:
        i = bisect_left(degrees, k)
        if i >= len(degrees):
            raise SystemExit(f"cannot assign internal_children={k}")
        d = degrees.pop(i)
        pairs.append((d, k))
    rng.shuffle(pairs)
    return pairs


class _NumericIdPool:
    def __init__(self) -> None:
        self._next_by_len = {1: 1, 2: 10, 3: 100, 4: 1000, 5: 10000}
        self._max_by_len = {1: 9, 2: 99, 3: 999, 4: 9999, 5: 99999}

    def take(self, length: int, count: int) -> list[str]:
        start = self._next_by_len[length]
        end = start + count - 1
        if end > self._max_by_len[length]:
            raise SystemExit(f"numeric pool exhausted for length={length}")
        self._next_by_len[length] = end + 1
        return [str(i) for i in range(start, end + 1)]


class _NPool:
    def __init__(self, width: int, *, start: int = 0) -> None:
        self._width = width
        self._next = start

    def next(self) -> str:
        self._next += 1
        return f"N{self._next:0{self._width}d}"


class _Letter3Pool:
    def __init__(self, letters: str, *, prefix: str = "") -> None:
        self._letters = letters
        self._prefix = prefix
        self._letter_idx = 0
        self._num = 0

    def next(self) -> str:
        if self._letter_idx >= len(self._letters):
            raise SystemExit("letter3 pool exhausted")
        letter = self._letters[self._letter_idx]
        out = f"{self._prefix}{letter}{self._num:03d}"
        self._num += 1
        if self._num >= 1000:
            self._num = 0
            self._letter_idx += 1
        return out

    def take(self, count: int) -> list[str]:
        return [self.next() for _ in range(count)]


# ---------------------------------------------------------------------------
# FUNCTIONS distribution constants
# ---------------------------------------------------------------------------
_FUNCTIONS_CHILDREN_DISTS: dict[str, dict[int, int]] = {
    "division": {1: 7, 5: 1, 8: 1, 13: 2, 26: 1},
    "unit": {
        0: 6, 1: 9, 2: 14, 3: 9, 4: 5, 5: 5, 6: 2, 7: 3, 8: 2, 9: 1,
        10: 6, 12: 1, 13: 1, 14: 2, 17: 1, 18: 1, 21: 1, 33: 1, 36: 1, 37: 1,
    },
    "area": {
        0: 23, 1: 142, 2: 63, 3: 39, 4: 26, 5: 20, 6: 22, 7: 15, 8: 12,
        9: 9, 10: 10, 11: 8, 12: 6, 13: 4, 14: 4, 15: 2, 16: 2, 17: 4,
        18: 3, 19: 5, 20: 3, 21: 1, 22: 3, 25: 3, 26: 1, 27: 2, 28: 2,
        29: 2, 37: 2, 38: 1, 40: 1, 48: 1, 253: 1,
    },
    "sector": {
        0: 261, 1: 1027, 2: 284, 3: 171, 4: 133, 5: 117, 6: 79, 7: 63,
        8: 48, 9: 44, 10: 47, 11: 34, 12: 29, 13: 24, 14: 20, 15: 22,
        16: 12, 17: 11, 18: 10, 19: 11, 20: 4, 21: 3, 22: 6, 23: 4,
        24: 1, 25: 4, 26: 6, 27: 4, 28: 2, 29: 2, 30: 4, 31: 5, 32: 1,
        33: 1, 34: 1, 36: 3, 38: 2, 39: 2, 40: 1, 42: 1, 43: 1, 46: 1,
        49: 3, 53: 1, 54: 1, 55: 1, 69: 1, 81: 1, 82: 1, 83: 1, 88: 1,
        92: 1, 124: 1,
    },
    "segment": {
        0: 2172, 1: 3119, 2: 1451, 3: 731, 4: 755, 5: 507, 6: 268, 7: 203,
        8: 168, 9: 124, 10: 112, 11: 94, 12: 64, 13: 58, 14: 48, 15: 52,
        16: 39, 17: 36, 18: 29, 19: 27, 20: 22, 21: 15, 22: 21, 23: 11,
        24: 23, 25: 11, 26: 8, 27: 20, 28: 11, 29: 9, 30: 7, 31: 11,
        32: 8, 33: 8, 34: 7, 35: 6, 36: 6, 37: 6, 38: 3, 39: 1, 40: 7,
        41: 4, 42: 4, 43: 2, 44: 6, 45: 2, 46: 4, 47: 2, 48: 3, 49: 1,
        50: 3, 51: 3, 52: 2, 53: 6, 54: 1, 55: 1, 56: 1, 57: 2, 58: 1,
        59: 1, 60: 1, 62: 1, 63: 1, 65: 2, 67: 1, 68: 2, 70: 2, 71: 1,
        72: 1, 73: 4, 74: 2, 75: 1, 76: 1, 77: 2, 78: 2, 81: 2, 83: 1,
        87: 3, 88: 3, 89: 1, 91: 2, 96: 1, 102: 1, 103: 1, 107: 1,
        111: 1, 113: 1, 115: 1, 120: 1, 122: 1, 129: 1, 132: 2, 133: 1,
        138: 1, 144: 1, 148: 2, 152: 1, 160: 1, 179: 1, 189: 1, 192: 2,
        195: 1, 196: 1, 197: 1, 199: 1, 217: 1, 220: 1, 229: 1, 253: 1,
        258: 1, 265: 1, 314: 1, 333: 1, 357: 1, 431: 1, 477: 1, 592: 1,
        694: 1, 909: 1, 1993: 1, 2201: 1,
    },
}

_FUNCTIONS_DIGIT_LEN_COUNTS: dict[str, dict[int, int]] = {
    "unit": {5: 6},
    "area": {5: 23},
    "sector": {2: 1, 3: 1, 4: 53, 5: 206},
    "segment": {2: 11, 3: 23, 4: 488, 5: 1650},
    "function": {1: 8, 2: 78, 3: 876, 4: 8459, 5: 42034},
}

_FUNCTIONS_LEAF_STATUS_COUNTS: dict[str, dict[str, int]] = {
    "unit": {"Active": 4, "Inactive": 2},
    "area": {"Active": 22, "Inactive": 1},
    "sector": {"Active": 139, "Inactive": 90, "Deleted": 32},
    "segment": {"Active": 1251, "Inactive": 921},
    "function": {"Active": 25190, "Inactive": 26265},
}

# ---------------------------------------------------------------------------
# LOCATIONS distribution constants
# ---------------------------------------------------------------------------
_LOCATIONS_CHILDREN_DISTS: dict[str, dict[int, int]] = {
    "region": {1: 1, 2: 1, 3: 2, 4: 1},
    "sub_region": {1: 3, 2: 2, 4: 2, 6: 3, 7: 1, 10: 1, 25: 1},
    "country": {
        1: 10, 2: 2, 3: 4, 4: 7, 5: 3, 6: 6, 7: 2, 8: 3, 9: 2, 10: 1,
        11: 1, 12: 1, 14: 1, 17: 1, 18: 1, 20: 1, 22: 1, 24: 1, 26: 1,
        38: 1, 39: 1, 40: 1, 43: 1, 47: 1, 48: 1, 49: 1, 51: 1, 56: 1,
        60: 2, 63: 1, 70: 1, 72: 1, 73: 2, 76: 1, 81: 1, 96: 1, 230: 2,
        231: 1, 368: 1, 809: 1, 1377: 1, 16377: 1,
    },
}

_LOCATION_COMPANY_STATUS_COUNTS = {"Active": 8560, "Inactive": 12532}
_LOCATION_COMPANY_NAME_LEN_BY_STATUS = {"Active": {1: 152, 2: 8408}, "Inactive": {1: 11, 2: 12521}}
_LOCATION_COMPANY_STAR_BY_STATUS = {"Active": {True: 26, False: 8534}, "Inactive": {True: 12280, False: 252}}

# ---------------------------------------------------------------------------
# CONSOLIDATED distribution constants
# ---------------------------------------------------------------------------
_CONSOLIDATED_LEAF_STATUS_BY_PATTERN = {
    "digits4": {"Active": 1284, "Inactive": 7496},
    "L3": {"Active": 6691, "Inactive": 4630},
    "F3": {"Active": 585, "Inactive": 384},
    "other": {"Inactive": 22},
}

_CONSOLIDATED_INTERNAL_DEGREE_DISTS: dict[str, dict[int, int]] = {
    "N000X": {1: 1, 6: 1, 119: 1, 748: 1},
    "N4": {
        1: 30, 2: 110, 3: 55, 4: 27, 5: 12, 6: 10, 7: 8, 8: 1, 9: 4,
        10: 4, 11: 4, 12: 1, 13: 4, 15: 5, 16: 3, 17: 2, 18: 1, 19: 2,
        20: 2, 21: 1, 24: 1, 25: 1, 26: 1, 27: 1, 28: 1, 29: 1, 30: 1,
        31: 2, 37: 1, 41: 2, 42: 1, 44: 1, 48: 1, 49: 1, 52: 1, 56: 1,
        62: 1, 76: 1, 80: 2, 154: 1, 179: 1, 214: 1,
    },
    "N4A": {
        1: 4, 2: 31, 3: 19, 4: 6, 5: 4, 6: 4, 7: 1, 8: 2, 9: 3, 10: 2,
        11: 4, 12: 1, 14: 1, 15: 2, 16: 2, 18: 1, 23: 2, 24: 1, 32: 1,
        34: 1, 58: 1, 74: 1,
    },
    "Nletter3": {
        1: 12, 2: 31, 3: 22, 4: 18, 5: 5, 6: 6, 7: 6, 8: 3, 9: 1, 10: 3,
        11: 1, 12: 1, 13: 2, 34: 2, 37: 1, 96: 1, 16406: 1,
    },
    "other": {2: 2, 3: 2, 4: 2, 5: 1, 7: 1, 32: 1, 249: 1},
}

_CONSOLIDATED_INTERNAL_CHILDREN_DISTS: dict[str, dict[int, int]] = {
    "N4": {0: 229, 1: 40, 2: 14, 3: 11, 4: 4, 5: 5, 6: 1, 7: 3, 8: 1, 17: 1, 19: 1, 22: 1},
    "N000X": {0: 1, 1: 2, 195: 1},
    "N4A": {0: 69, 1: 13, 2: 7, 3: 4, 10: 1},
    "Nletter3": {0: 94, 1: 15, 2: 5, 5: 1, 17: 1},
    "other": {0: 6, 1: 2, 2: 2},
}

_CONSOLIDATED_INTERNAL_EDGE_COUNTS: dict[tuple[str, str], int] = {
    ("N4", "N4"): 153, ("N4", "N4A"): 50, ("N4", "Nletter3"): 28,
    ("N4", "N000X"): 3, ("N4", "other"): 1, ("N000X", "N4"): 144,
    ("N000X", "Nletter3"): 41, ("N000X", "N4A"): 10, ("N000X", "N000X"): 1,
    ("N000X", "other"): 1, ("N4A", "N4A"): 25, ("N4A", "Nletter3"): 13,
    ("N4A", "N4"): 10, ("N4A", "other"): 1, ("Nletter3", "Nletter3"): 29,
    ("Nletter3", "N4A"): 9, ("Nletter3", "N4"): 3, ("Nletter3", "other"): 6,
    ("other", "Nletter3"): 5, ("other", "other"): 1,
}

_CONSOLIDATED_LEAF_EDGE_COUNTS: dict[str, dict[str, int]] = {
    "N4": {"digits4": 2190, "L3": 225, "F3": 21},
    "N000X": {"digits4": 405, "L3": 166, "F3": 106},
    "N4A": {"digits4": 409, "L3": 205, "F3": 16},
    "Nletter3": {"digits4": 5775, "L3": 10626, "F3": 621, "other": 22},
    "other": {"digits4": 1, "L3": 99, "F3": 205, "other": 0},
}

_CONSOLIDATED_ROOT_INTERNAL_CHILDREN = {"N000X": 3, "Nletter3": 4}
_CONSOLIDATED_ROOT_LEAF_PATTERNS = {"L3": 17, "F3": 5}


# ---------------------------------------------------------------------------
# FUNCTIONS generator
# ---------------------------------------------------------------------------

def iter_mock_functions(rng: random.Random) -> Iterator[dict[str, object]]:
    div_counts = _expand_distribution(_FUNCTIONS_CHILDREN_DISTS["division"], rng)
    unit_counts = _expand_distribution(_FUNCTIONS_CHILDREN_DISTS["unit"], rng)
    area_counts = _expand_distribution(_FUNCTIONS_CHILDREN_DISTS["area"], rng)
    sector_counts = _expand_distribution(_FUNCTIONS_CHILDREN_DISTS["sector"], rng)
    segment_counts = _expand_distribution(_FUNCTIONS_CHILDREN_DISTS["segment"], rng)

    n5_pool = _NPool(5, start=10_000)
    num_pool = _NumericIdPool()

    def _take_digit_ids(dist: dict[int, int]) -> list[str]:
        ids: list[str] = []
        for length, count in sorted(dist.items()):
            ids.extend(num_pool.take(length, count))
        rng.shuffle(ids)
        return ids

    unit_leaf_ids = _take_digit_ids(_FUNCTIONS_DIGIT_LEN_COUNTS["unit"])
    area_leaf_ids = _take_digit_ids(_FUNCTIONS_DIGIT_LEN_COUNTS["area"])
    sector_leaf_ids = _take_digit_ids(_FUNCTIONS_DIGIT_LEN_COUNTS["sector"])
    segment_leaf_ids = _take_digit_ids(_FUNCTIONS_DIGIT_LEN_COUNTS["segment"])
    function_ids = _take_digit_ids(_FUNCTIONS_DIGIT_LEN_COUNTS["function"])

    unit_leaf_status = _make_list_from_counts(_FUNCTIONS_LEAF_STATUS_COUNTS["unit"], rng)
    area_leaf_status = _make_list_from_counts(_FUNCTIONS_LEAF_STATUS_COUNTS["area"], rng)
    sector_leaf_status = _make_list_from_counts(_FUNCTIONS_LEAF_STATUS_COUNTS["sector"], rng)
    segment_leaf_status = _make_list_from_counts(_FUNCTIONS_LEAF_STATUS_COUNTS["segment"], rng)
    function_status = _make_list_from_counts(_FUNCTIONS_LEAF_STATUS_COUNTS["function"], rng)

    def mk_name(kind: str, idx: int, status: str | None) -> str:
        base = f"Mock {kind} {idx:05d}"
        if status == "Inactive":
            return _star_date_prefix(rng) + base
        return base

    root_id = "N00000"
    division_ids = [n5_pool.next() for _ in range(12)]

    yield {"id": root_id, "id_type": "group", "id_status": None, "name": "All Functions", "out_id": division_ids}

    unit_i = area_i = sector_i = segment_i = 0
    unit_name_i = area_name_i = sector_name_i = segment_name_i = function_name_i = 0

    for div_idx, div_id in enumerate(division_ids, start=1):
        n_units = div_counts[div_idx - 1]
        unit_nodes: list[tuple[str, int, str | None]] = []
        for _ in range(n_units):
            c = unit_counts[unit_i]; unit_i += 1
            if c == 0:
                uid = unit_leaf_ids.pop(); st = unit_leaf_status.pop()
            else:
                uid = n5_pool.next(); st = None
            unit_nodes.append((uid, c, st))

        yield {"id": div_id, "id_type": "division", "id_status": None, "name": f"Mock Division {div_idx:03d}", "out_id": [u for (u, _, _) in unit_nodes], "in_id": root_id}

        for uid, u_child, u_status in unit_nodes:
            unit_name_i += 1
            if u_child == 0:
                yield {"id": uid, "id_type": "unit", "id_status": u_status, "name": mk_name("Unit", unit_name_i, u_status), "out_id": [], "in_id": div_id}
                continue

            area_nodes: list[tuple[str, int, str | None]] = []
            for _ in range(u_child):
                c = area_counts[area_i]; area_i += 1
                if c == 0:
                    aid = area_leaf_ids.pop(); st = area_leaf_status.pop()
                else:
                    aid = n5_pool.next(); st = None
                area_nodes.append((aid, c, st))

            yield {"id": uid, "id_type": "unit", "id_status": None, "name": f"Mock Unit {unit_name_i:03d}", "out_id": [a for (a, _, _) in area_nodes], "in_id": div_id}

            for aid, a_child, a_status in area_nodes:
                area_name_i += 1
                if a_child == 0:
                    yield {"id": aid, "id_type": "area", "id_status": a_status, "name": mk_name("Area", area_name_i, a_status), "out_id": [], "in_id": uid}
                    continue

                sector_nodes: list[tuple[str, int, str | None]] = []
                for _ in range(a_child):
                    c = sector_counts[sector_i]; sector_i += 1
                    if c == 0:
                        sid = sector_leaf_ids.pop(); st = sector_leaf_status.pop()
                    else:
                        sid = n5_pool.next(); st = None
                    sector_nodes.append((sid, c, st))

                yield {"id": aid, "id_type": "area", "id_status": None, "name": f"Mock Area {area_name_i:04d}", "out_id": [s for (s, _, _) in sector_nodes], "in_id": uid}

                for sid, s_child, s_status in sector_nodes:
                    sector_name_i += 1
                    if s_child == 0:
                        yield {"id": sid, "id_type": "sector", "id_status": s_status, "name": mk_name("Sector", sector_name_i, s_status), "out_id": [], "in_id": aid}
                        continue

                    segment_nodes: list[tuple[str, int, str | None]] = []
                    for _ in range(s_child):
                        c = segment_counts[segment_i]; segment_i += 1
                        if c == 0:
                            gid = segment_leaf_ids.pop(); st = segment_leaf_status.pop()
                        else:
                            gid = n5_pool.next(); st = None
                        segment_nodes.append((gid, c, st))

                    yield {"id": sid, "id_type": "sector", "id_status": None, "name": f"Mock Sector {sector_name_i:05d}", "out_id": [g for (g, _, _) in segment_nodes], "in_id": aid}

                    for gid, g_child, g_status in segment_nodes:
                        segment_name_i += 1
                        if g_child == 0:
                            yield {"id": gid, "id_type": "segment", "id_status": g_status, "name": mk_name("Segment", segment_name_i, g_status), "out_id": [], "in_id": sid}
                            continue

                        fn_ids = [function_ids.pop() for _ in range(g_child)]
                        yield {"id": gid, "id_type": "segment", "id_status": None, "name": f"Mock Segment {segment_name_i:06d}", "out_id": fn_ids, "in_id": sid}
                        for fid in fn_ids:
                            function_name_i += 1
                            st = function_status.pop()
                            yield {"id": fid, "id_type": "function", "id_status": st, "name": mk_name("Function", function_name_i, st), "out_id": [], "in_id": gid}


# ---------------------------------------------------------------------------
# LOCATIONS generator
# ---------------------------------------------------------------------------

def iter_mock_locations(rng: random.Random) -> Iterator[dict[str, object]]:
    region_counts = _expand_distribution(_LOCATIONS_CHILDREN_DISTS["region"], rng)
    sub_region_counts = _expand_distribution(_LOCATIONS_CHILDREN_DISTS["sub_region"], rng)
    country_counts = _expand_distribution(_LOCATIONS_CHILDREN_DISTS["country"], rng)

    n4_pool = _NPool(4, start=4999)
    root_id = "N0000"
    region_ids = [n4_pool.next() for _ in range(5)]

    digits4_ids = [str(i) for i in range(1000, 1000 + 8780)]
    l3_ids = _Letter3Pool(string.ascii_uppercase).take(12290)
    other_ids = [
        "N22", "N23", "NA", "NA1", "NA2", "NA3", "NA4", "NA5", "NA6", "NA7",
        "NA8", "NA9", "NA10", "NA11", "NA12", "NA13", "NA14", "NA15", "NA16",
        "NA17", "NA20", "NA1215",
    ]

    company_ids = digits4_ids + l3_ids + other_ids
    rng.shuffle(company_ids)

    company_statuses = _make_list_from_counts(_LOCATION_COMPANY_STATUS_COUNTS, rng)
    need_inactive = {"N22", "N23"} | {f"NA{i}" for i in range(1, 21)} | {"NA", "NA1215"}
    for i, cid in enumerate(company_ids):
        if cid not in need_inactive:
            continue
        if company_statuses[i] == "Inactive":
            continue
        for j in range(i + 1, len(company_statuses)):
            if company_statuses[j] == "Inactive" and company_ids[j] not in need_inactive:
                company_statuses[i], company_statuses[j] = company_statuses[j], company_statuses[i]
                break

    name_len_active = _make_list_from_counts(_LOCATION_COMPANY_NAME_LEN_BY_STATUS["Active"], rng)
    name_len_inactive = _make_list_from_counts(_LOCATION_COMPANY_NAME_LEN_BY_STATUS["Inactive"], rng)
    star_active = _make_list_from_counts(_LOCATION_COMPANY_STAR_BY_STATUS["Active"], rng)
    star_inactive = _make_list_from_counts(_LOCATION_COMPANY_STAR_BY_STATUS["Inactive"], rng)

    cities = ["Zurich", "Basel", "Geneva", "London", "New York", "Dublin", "Luxembourg", "Singapore"]

    def mk_company_name(idx: int, status: str) -> list[str]:
        city = rng.choice(cities)
        base = f"Mock Company {idx:05d}"
        if status == "Active":
            star = star_active.pop(); ln = name_len_active.pop()
        else:
            star = star_inactive.pop(); ln = name_len_inactive.pop()
        prefix = _star_date_prefix(rng) if star else ""
        if ln == 1:
            return [base]
        return [f"{prefix}{base}-{city}", base]

    yield {"id": root_id, "id_type": "location", "location_name": ["UBS Group AG (Regional)"], "location_status": None, "out_id": region_ids}

    sub_region_ids = [n4_pool.next() for _ in range(13)]
    country_ids_list = [n4_pool.next() for _ in range(75)]

    sub_region_ptr = country_ptr = company_ptr = 0
    sub_region_i = country_i = company_i = 0

    for r_idx, rid in enumerate(region_ids, start=1):
        n_sub = region_counts[r_idx - 1]
        subs = sub_region_ids[sub_region_ptr: sub_region_ptr + n_sub]
        sub_region_ptr += n_sub

        yield {"id": rid, "id_type": "region", "location_name": [f"Mock Region {r_idx:03d}"], "location_status": None, "out_id": subs, "in_id": root_id}

        for sid in subs:
            n_countries = sub_region_counts[sub_region_i]; sub_region_i += 1
            countries = country_ids_list[country_ptr: country_ptr + n_countries]
            country_ptr += n_countries

            yield {"id": sid, "id_type": "sub_region", "location_name": [f"Mock Sub Region {sub_region_i:03d}"], "location_status": None, "out_id": countries, "in_id": rid}

            for cid in countries:
                n_companies = country_counts[country_i]; country_i += 1
                companies = company_ids[company_ptr: company_ptr + n_companies]
                statuses = company_statuses[company_ptr: company_ptr + n_companies]
                company_ptr += n_companies

                yield {"id": cid, "id_type": "country", "location_name": [f"Mock Country {country_i:03d}"], "location_status": None, "out_id": companies, "in_id": sid}

                for comp_id, status in zip(companies, statuses, strict=True):
                    company_i += 1
                    yield {"id": comp_id, "id_type": "company", "location_name": mk_company_name(company_i, status), "location_status": status, "out_id": [], "in_id": cid}


# ---------------------------------------------------------------------------
# CONSOLIDATED generator
# ---------------------------------------------------------------------------

@dataclass
class _ConsNode:
    node_id: str
    location_name: list[str]
    location_status: str | None
    internal_children_count: int
    degree: int
    internal_children: list["_ConsNode"] = field(default_factory=list)
    leaf_children: list["_ConsNode"] = field(default_factory=list)
    parent_id: str | None = None

    @property
    def out_id(self) -> list[str]:
        return [c.node_id for c in self.leaf_children] + [c.node_id for c in self.internal_children]


def _parent_category(node: _ConsNode) -> str:
    nid = node.node_id
    if nid.startswith("N000") and len(nid) == 5 and nid[-1].isalpha():
        return "N000X"
    if nid.startswith("N") and len(nid) == 5 and nid[1:].isdigit():
        return "N4"
    if nid.startswith("N") and len(nid) == 6 and nid[1:5].isdigit() and nid[5].isalpha():
        return "N4A"
    if nid.startswith("N") and len(nid) == 5 and nid[1].isalpha() and nid[2:].isdigit():
        return "Nletter3"
    return "other"


class _LeafFactory:
    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._digits4_ids = [str(i) for i in range(1000, 1000 + 8780)]
        self._f3_ids = [f"F{i:03d}" for i in range(1, 1 + 969)]
        letters_no_f = "".join(ch for ch in string.ascii_uppercase if ch != "F")
        self._l3_ids = _Letter3Pool(letters_no_f).take(11321)
        self._other_ids = [
            "N22", "N23", "NA", "NA1", "NA2", "NA3", "NA4", "NA5", "NA6", "NA7",
            "NA8", "NA9", "NA10", "NA11", "NA12", "NA13", "NA14", "NA15", "NA16",
            "NA17", "NA20", "NA1215",
        ]
        rng.shuffle(self._digits4_ids)
        rng.shuffle(self._f3_ids)
        rng.shuffle(self._l3_ids)

        self._status_by_pat: dict[str, list[str]] = {}
        for pat, counts in _CONSOLIDATED_LEAF_STATUS_BY_PATTERN.items():
            self._status_by_pat[pat] = _make_list_from_counts(counts, rng)

        self._name_len_active = _make_list_from_counts(_LOCATION_COMPANY_NAME_LEN_BY_STATUS["Active"], rng)
        self._name_len_inactive = _make_list_from_counts(_LOCATION_COMPANY_NAME_LEN_BY_STATUS["Inactive"], rng)
        self._star_active = _make_list_from_counts(_LOCATION_COMPANY_STAR_BY_STATUS["Active"], rng)
        self._star_inactive = _make_list_from_counts(_LOCATION_COMPANY_STAR_BY_STATUS["Inactive"], rng)
        self._leaf_idx = 0

    def make(self, pattern: str) -> _ConsNode:
        if pattern == "digits4":
            node_id = self._digits4_ids.pop()
        elif pattern == "F3":
            node_id = self._f3_ids.pop()
        elif pattern == "L3":
            node_id = self._l3_ids.pop()
        elif pattern == "other":
            node_id = self._other_ids.pop(0)
        else:
            raise ValueError(f"unknown leaf pattern: {pattern}")

        status = self._status_by_pat[pattern].pop()
        self._leaf_idx += 1
        base = f"Mock Legal Entity {self._leaf_idx:05d} (Cons)"
        if status == "Active":
            star = self._star_active.pop(); ln = self._name_len_active.pop()
        else:
            star = self._star_inactive.pop(); ln = self._name_len_inactive.pop()
        prefix = _star_date_prefix(self._rng) if star else ""
        if ln == 1:
            names = [base]
        else:
            names = [f"{prefix}Mock LE {self._leaf_idx:05d} - City", base]

        return _ConsNode(node_id=node_id, location_name=names, location_status=status, internal_children_count=0, degree=0)


def iter_mock_consolidated(rng: random.Random) -> Iterator[dict[str, object]]:
    root = _ConsNode(node_id="N0000", location_name=["UBS Group AG (Consolidated)"], location_status=None, internal_children_count=7, degree=29)

    n000x_pairs = _pair_degrees_with_internal_counts(
        _CONSOLIDATED_INTERNAL_DEGREE_DISTS["N000X"],
        _CONSOLIDATED_INTERNAL_CHILDREN_DISTS["N000X"],
        rng=rng,
    )
    n000x_pairs.sort(reverse=True)
    bucket_ids = ["N000A", "N000B", "N000C", "N000D"]
    buckets = [
        _ConsNode(node_id=bucket_ids[i], location_name=[f"Mock Bucket {bucket_ids[i]}"], location_status=None, internal_children_count=k, degree=d)
        for i, (d, k) in enumerate(n000x_pairs)
    ]

    n4_degree = dict(_CONSOLIDATED_INTERNAL_DEGREE_DISTS["N4"])
    n4_internal = dict(_CONSOLIDATED_INTERNAL_CHILDREN_DISTS["N4"])
    n4_degree[29] -= 1
    if n4_degree[29] == 0:
        del n4_degree[29]
    n4_internal[7] -= 1
    if n4_internal[7] == 0:
        del n4_internal[7]

    n4_pairs = _pair_degrees_with_internal_counts(n4_degree, n4_internal, rng=rng)
    n4_pool = _NPool(4, start=0)
    n4_nodes: list[str] = []
    while len(n4_nodes) < 310:
        nid = n4_pool.next()
        if nid == "N0000":
            continue
        n4_nodes.append(nid)
    n4_internal_nodes = [
        _ConsNode(node_id=nid, location_name=[f"Mock Internal {nid}"], location_status=None, internal_children_count=k, degree=d)
        for nid, (d, k) in zip(n4_nodes, n4_pairs, strict=True)
    ]

    n4a_pairs = _pair_degrees_with_internal_counts(
        _CONSOLIDATED_INTERNAL_DEGREE_DISTS["N4A"],
        _CONSOLIDATED_INTERNAL_CHILDREN_DISTS["N4A"],
        rng=rng,
    )
    n4a_ids = [f"N{i:04d}A" for i in range(1, 95)]
    n4a_nodes = [
        _ConsNode(node_id=nid, location_name=[f"Mock Internal {nid}"], location_status=None, internal_children_count=k, degree=d)
        for nid, (d, k) in zip(n4a_ids, n4a_pairs, strict=True)
    ]

    nletter_pairs = _pair_degrees_with_internal_counts(
        _CONSOLIDATED_INTERNAL_DEGREE_DISTS["Nletter3"],
        _CONSOLIDATED_INTERNAL_CHILDREN_DISTS["Nletter3"],
        rng=rng,
    )
    nletter_pool = _Letter3Pool("BCDEGHIJKLMNOPQRSTUVWXYZ", prefix="N")
    nletter_nodes = [
        _ConsNode(node_id=nletter_pool.next(), location_name=[f"Mock Internal {i+1:03d}"], location_status=None, internal_children_count=k, degree=d)
        for i, (d, k) in enumerate(nletter_pairs)
    ]

    other_pairs = _pair_degrees_with_internal_counts(
        _CONSOLIDATED_INTERNAL_DEGREE_DISTS["other"],
        _CONSOLIDATED_INTERNAL_CHILDREN_DISTS["other"],
        rng=rng,
    )
    other_ids = ["N000C2A", "N000C3", "N000C4", "NC205A", "NC205B", "ND620A", "ND621A", "NF492A", "NF1641", "NW011A"]
    other_nodes = [
        _ConsNode(node_id=nid, location_name=[f"Mock Internal {nid}"], location_status=None, internal_children_count=k, degree=d)
        for nid, (d, k) in zip(other_ids, other_pairs, strict=True)
    ]

    def _branching_first(n: _ConsNode) -> tuple[int, int]:
        return (n.internal_children_count, n.degree)

    unassigned: dict[str, list[_ConsNode]] = {
        "N000X": buckets.copy(),
        "N4": sorted(n4_internal_nodes, key=_branching_first, reverse=True),
        "N4A": sorted(n4a_nodes, key=_branching_first, reverse=True),
        "Nletter3": sorted(nletter_nodes, key=_branching_first, reverse=True),
        "other": sorted(other_nodes, key=_branching_first, reverse=True),
    }

    internal_child_pool: dict[str, list[str]] = defaultdict(list)
    for (p, c), n in _CONSOLIDATED_INTERNAL_EDGE_COUNTS.items():
        internal_child_pool[p].extend([c] * n)
    for p in list(internal_child_pool):
        rng.shuffle(internal_child_pool[p])

    bucket_attach_order = ["N000A", "N000B", "N000D"]
    for bid in bucket_attach_order:
        node = next((n for n in unassigned["N000X"] if n.node_id == bid), None)
        if node is None:
            raise SystemExit(f"consolidated: missing bucket {bid}")
        unassigned["N000X"].remove(node)
        node.parent_id = root.node_id
        root.internal_children.append(node)

    mega = next((n for n in unassigned["Nletter3"] if n.degree == 16406), None)
    if mega is None:
        raise SystemExit("consolidated: missing mega Nletter3 node")
    unassigned["Nletter3"].remove(mega)

    for _ in range(_CONSOLIDATED_ROOT_INTERNAL_CHILDREN["Nletter3"] - 1):
        node = unassigned["Nletter3"].pop(0)
        node.parent_id = root.node_id
        root.internal_children.append(node)
    mega.parent_id = root.node_id
    root.internal_children.append(mega)

    for _ in range(3):
        internal_child_pool["N4"].remove("N000X")
    for _ in range(4):
        internal_child_pool["N4"].remove("Nletter3")

    q: deque[_ConsNode] = deque(root.internal_children)
    while q:
        parent = q.popleft()
        need = parent.internal_children_count
        pool = internal_child_pool[_parent_category(parent)]
        for _ in range(need):
            child_cat = pool.pop()
            child = unassigned[child_cat].pop(0)
            child.parent_id = parent.node_id
            parent.internal_children.append(child)
            q.append(child)

    leaf_pool: dict[str, list[str]] = defaultdict(list)
    for p, dist in _CONSOLIDATED_LEAF_EDGE_COUNTS.items():
        for pat, n in dist.items():
            leaf_pool[p].extend([pat] * n)
            rng.shuffle(leaf_pool[p])

    for pat, n in _CONSOLIDATED_ROOT_LEAF_PATTERNS.items():
        for _ in range(n):
            leaf_pool["N4"].remove(pat)
    for _ in range(_CONSOLIDATED_LEAF_EDGE_COUNTS["Nletter3"]["other"]):
        leaf_pool["Nletter3"].remove("other")

    leaf_factory = _LeafFactory(rng)

    for pat, n in _CONSOLIDATED_ROOT_LEAF_PATTERNS.items():
        for _ in range(n):
            leaf = leaf_factory.make(pat)
            leaf.parent_id = root.node_id
            root.leaf_children.append(leaf)

    def attach_leaves(node: _ConsNode) -> None:
        cat = _parent_category(node)
        leaf_needed = node.degree - node.internal_children_count - len(node.leaf_children)
        if node is mega:
            for _ in range(22):
                leaf = leaf_factory.make("other")
                leaf.parent_id = node.node_id
                node.leaf_children.append(leaf)
            leaf_needed = node.degree - node.internal_children_count - len(node.leaf_children)
        pool = leaf_pool[cat]
        for _ in range(leaf_needed):
            pat = pool.pop()
            leaf = leaf_factory.make(pat)
            leaf.parent_id = node.node_id
            node.leaf_children.append(leaf)

    iq: deque[_ConsNode] = deque([root])
    while iq:
        n = iq.popleft()
        attach_leaves(n)
        iq.extend(n.internal_children)

    def emit(node: _ConsNode) -> Iterator[dict[str, object]]:
        row: dict[str, object] = {
            "location_id": node.node_id,
            "location_name": node.location_name,
            "location_status": node.location_status,
            "out_id": node.out_id,
        }
        if node.parent_id is not None:
            row["in_id"] = node.parent_id
        yield row
        for leaf in node.leaf_children:
            yield {
                "location_id": leaf.node_id,
                "location_name": leaf.location_name,
                "location_status": leaf.location_status,
                "out_id": [],
                "in_id": node.node_id,
            }
        for child in node.internal_children:
            yield from emit(child)

    yield from emit(root)


# ---------------------------------------------------------------------------
# ASSESSMENT UNITS generator
# ---------------------------------------------------------------------------

def _extract_leaf_ids(jsonl_path: Path, id_field: str) -> list[str]:
    """Extract IDs of leaf nodes (out_id is empty) from a JSONL file."""
    ids: list[str] = []
    with jsonl_path.open("rb") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            try:
                if b"orjson" in sys.modules:
                    import orjson as _oj
                    row = _oj.loads(line)
                else:
                    row = json.loads(line)
            except Exception:
                continue
            out = row.get("out_id")
            if isinstance(out, list) and len(out) == 0:
                sid = str(row.get(id_field, "")).strip()
                if sid:
                    ids.append(sid)
    return ids


def generate_assessment_units_jsonl(
    out_path: Path,
    functions_path: Path,
    locations_path: Path,
    consolidated_path: Path,
    *,
    seed: int = SEED,
    rows: int = _ASSESSMENT_UNITS_DEFAULT_ROWS,
) -> int:
    """Generate mock assessment-unit records from existing org leaf nodes.

    Reads leaf-node IDs from the three org JSONL files and produces
    *rows* assessment-unit records referencing valid function and
    location/consolidated IDs.
    """
    rng = random.Random(seed)

    func_ids = _extract_leaf_ids(functions_path, "id")
    loc_ids = _extract_leaf_ids(locations_path, "id")
    cons_ids = _extract_leaf_ids(consolidated_path, "location_id")

    if not func_ids:
        raise SystemExit("No function leaf IDs found — generate org data first")
    if not loc_ids and not cons_ids:
        raise SystemExit("No location/consolidated leaf IDs found — generate org data first")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for i in range(1, rows + 1):
            func_id = rng.choice(func_ids)
            if cons_ids and loc_ids:
                loc_type = rng.choices(["location", "consolidated"], weights=[60, 40])[0]
            elif loc_ids:
                loc_type = "location"
            else:
                loc_type = "consolidated"
            loc_id = rng.choice(loc_ids if loc_type == "location" else cons_ids)
            status = rng.choices(["Active", "Inactive"], weights=[80, 20])[0]
            row = {
                "id": f"AU-{i:04d}",
                "name": f"Mock Assessment Unit {i:04d}",
                "status": status,
                "function_id": func_id,
                "location_id": loc_id,
                "location_type": loc_type,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


# ---------------------------------------------------------------------------
# JSONL writer
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, rows: Iterable[dict[str, object]], *, total: int | None, desc: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf: list[bytes] = []
    written = 0
    progress_every = 10_000

    with path.open("wb") as f:
        for written, row in enumerate(rows, start=1):
            buf.append(_json_dumps_bytes(row))
            if len(buf) >= 10_000:
                f.write(b"\n".join(buf) + b"\n")
                buf.clear()
            if written % progress_every == 0:
                print(f"  {desc}: {written:,} rows...", flush=True)
        if buf:
            f.write(b"\n".join(buf) + b"\n")

    if total is not None and written != total:
        raise SystemExit(f"ERROR: {desc}: wrote {written:,} rows but expected {total:,}")
    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server.scripts.generate_mock_org_data",
        description="Generate mock organisation JSONL into the context_providers directory.",
    )
    parser.add_argument(
        "--context-providers-path",
        type=Path,
        default=None,
        help="Root context_providers directory. Defaults to CONTEXT_PROVIDERS_PATH from .env.",
    )
    parser.add_argument("--date", type=str, default=None, help="Date folder name (default: today, YYYY-MM-DD).")
    parser.add_argument("--seed", type=int, default=SEED, help="RNG seed.")
    parser.add_argument("--au-rows", type=int, default=_ASSESSMENT_UNITS_DEFAULT_ROWS, help="Number of assessment-unit rows to generate.")
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
    out_dir = ctx_path / "organization" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    seed = args.seed
    print(f"Generating mock org data -> {out_dir}")
    print(f"  Expected: functions={_FUNCTIONS_TOTAL_ROWS:,}  locations={_LOCATIONS_TOTAL_ROWS:,}  consolidated={_CONSOLIDATED_TOTAL_ROWS:,}")

    n = _write_jsonl(
        out_dir / "functions.jsonl",
        iter_mock_functions(random.Random(seed + 1)),
        total=_FUNCTIONS_TOTAL_ROWS,
        desc="functions",
    )
    print(f"  functions.jsonl: {n:,} rows")

    n = _write_jsonl(
        out_dir / "locations.jsonl",
        iter_mock_locations(random.Random(seed + 2)),
        total=_LOCATIONS_TOTAL_ROWS,
        desc="locations",
    )
    print(f"  locations.jsonl: {n:,} rows")

    n = _write_jsonl(
        out_dir / "consolidated.jsonl",
        iter_mock_consolidated(random.Random(seed + 3)),
        total=_CONSOLIDATED_TOTAL_ROWS,
        desc="consolidated",
    )
    print(f"  consolidated.jsonl: {n:,} rows")

    # --- Assessment units (reads the just-generated org files) ---
    au_dir = ctx_path / "assessment_unit" / date_str
    au_dir.mkdir(parents=True, exist_ok=True)
    au_path = au_dir / "assessment_units.jsonl"
    print(f"\nGenerating mock assessment units -> {au_dir}")
    n = generate_assessment_units_jsonl(
        au_path,
        functions_path=out_dir / "functions.jsonl",
        locations_path=out_dir / "locations.jsonl",
        consolidated_path=out_dir / "consolidated.jsonl",
        seed=seed + 4,
        rows=args.au_rows,
    )
    print(f"  assessment_units.jsonl: {n:,} rows")

    print("Done.")


if __name__ == "__main__":
    main()
