"""Shared loader for DBpedia Arrow IPC dataset text + embeddings.

Provides deterministic mapping of dataset entries to control fields.
Each control uses 6 dataset entries (one per text field):
  6*i + 0 → control_title
  6*i + 1 → control_description
  6*i + 2 → evidence_description
  6*i + 3 → local_functional_information
  6*i + 4 → control_as_event
  6*i + 5 → control_as_issues

Dataset: HuggingFace-format Arrow IPC stream files with columns:
  _id, title, text, text-embedding-ada-002-1536-embedding,
  text-embedding-3-large-3072-embedding
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np
import pyarrow as pa

FIELDS_PER_CONTROL = 6
FIELD_NAMES = [
    "control_title",
    "control_description",
    "evidence_description",
    "local_functional_information",
    "control_as_event",
    "control_as_issues",
]

EMBEDDING_COLUMN = "text-embedding-3-large-3072-embedding"
TEXT_COLUMN = "text"

# Pattern for shard filenames: *-train-XXXXX-of-YYYYY.arrow
_SHARD_RE = re.compile(r"-train-(\d+)-of-(\d+)\.arrow$")


def find_arrow_shards(dataset_path: Path) -> List[Path]:
    """Find and sort .arrow shard files from the HuggingFace directory.

    Navigates: dataset_path / default / X.Y.Z / <hash> / *.arrow
    Returns shard paths sorted by shard index.
    """
    # Navigate the HuggingFace directory structure
    candidates: List[Path] = []

    # Try direct path first
    if dataset_path.is_file() and dataset_path.suffix == ".arrow":
        return [dataset_path]

    # HuggingFace structure: dataset_path/default/0.0.0/<hash>/*.arrow
    for arrow_file in dataset_path.rglob("*.arrow"):
        if _SHARD_RE.search(arrow_file.name):
            candidates.append(arrow_file)

    if not candidates:
        raise FileNotFoundError(
            f"No Arrow IPC shard files found under {dataset_path}"
        )

    # Sort by shard index
    def _shard_index(p: Path) -> int:
        m = _SHARD_RE.search(p.name)
        return int(m.group(1)) if m else 0

    candidates.sort(key=_shard_index)
    return candidates


def _read_shard_table(shard_path: Path, columns: Optional[List[str]] = None) -> pa.Table:
    """Read an Arrow IPC stream file into a PyArrow Table."""
    reader = pa.ipc.open_stream(shard_path)
    table = reader.read_all()
    if columns:
        table = table.select(columns)
    return table


def iter_texts(dataset_path: Path, needed: int) -> Iterator[str]:
    """Stream text entries from Arrow shards.

    Yields up to `needed` text strings from the dataset's text column.
    Memory efficient: reads one shard at a time.
    """
    shards = find_arrow_shards(dataset_path)
    yielded = 0

    for shard_path in shards:
        if yielded >= needed:
            break

        table = _read_shard_table(shard_path, columns=[TEXT_COLUMN])
        text_col = table.column(TEXT_COLUMN)

        for i in range(len(text_col)):
            if yielded >= needed:
                break
            val = text_col[i].as_py()
            if val and isinstance(val, str) and val.strip():
                yielded += 1
                yield val.strip()

        del table, text_col

    if yielded < needed:
        raise ValueError(
            f"Dataset has only {yielded} valid text entries, but {needed} were requested"
        )


def load_text_pool(dataset_path: Path, num_controls: int) -> List[Dict[str, str]]:
    """Load 6 texts per control from the dataset.

    Returns:
        List of dicts (one per control), each mapping field_name → text string.
        Length = num_controls.
    """
    needed = num_controls * FIELDS_PER_CONTROL
    texts = list(iter_texts(dataset_path, needed))

    pool: List[Dict[str, str]] = []
    for i in range(num_controls):
        base = i * FIELDS_PER_CONTROL
        entry = {}
        for j, field_name in enumerate(FIELD_NAMES):
            entry[field_name] = texts[base + j]
        pool.append(entry)

    return pool


def iter_embeddings_chunked(
    dataset_path: Path,
    num_controls: int,
    dim: int = 3072,
    dtype: np.dtype = np.float16,
) -> Iterator[Tuple[int, Dict[str, np.ndarray]]]:
    """Yield (control_idx, {field_name: embedding}) from Arrow shards.

    Processes shard-by-shard to manage memory. Each shard contributes
    embeddings for a range of controls based on the deterministic mapping.

    Args:
        dataset_path: Path to the HuggingFace dataset directory.
        num_controls: Total number of controls.
        dim: Embedding dimension (default 3072).
        dtype: Output numpy dtype (default float16).

    Yields:
        Tuples of (control_index, dict mapping field_name to embedding array).
    """
    shards = find_arrow_shards(dataset_path)
    needed = num_controls * FIELDS_PER_CONTROL
    global_idx = 0  # tracks position across all shards

    for shard_path in shards:
        if global_idx >= needed:
            break

        table = _read_shard_table(shard_path, columns=[EMBEDDING_COLUMN])
        emb_col = table.column(EMBEDDING_COLUMN)
        shard_len = len(emb_col)

        for row_in_shard in range(shard_len):
            if global_idx >= needed:
                break

            control_idx = global_idx // FIELDS_PER_CONTROL
            field_idx = global_idx % FIELDS_PER_CONTROL

            if control_idx >= num_controls:
                break

            field_name = FIELD_NAMES[field_idx]
            raw = emb_col[row_in_shard].as_py()

            if raw and len(raw) == dim:
                vec = np.array(raw, dtype=dtype)
            else:
                vec = np.zeros((dim,), dtype=dtype)

            # Accumulate fields for this control
            if field_idx == 0:
                current_entry: Dict[str, np.ndarray] = {}

            current_entry[field_name] = vec

            if field_idx == FIELDS_PER_CONTROL - 1:
                yield control_idx, current_entry

            global_idx += 1

        del table, emb_col


def load_embeddings_for_controls(
    dataset_path: Path,
    num_controls: int,
    dim: int = 3072,
    dtype: np.dtype = np.float16,
) -> Dict[str, np.ndarray]:
    """Load all embeddings into pre-allocated arrays.

    Uses bulk numpy conversion per shard instead of per-row .as_py() calls.

    Returns:
        Dict mapping "{field_name}_embedding" → np.ndarray of shape (num_controls, dim).
    """
    embedding_field_names = [f"{fn}_embedding" for fn in FIELD_NAMES]
    arrays = {
        name: np.zeros((num_controls, dim), dtype=dtype)
        for name in embedding_field_names
    }

    shards = find_arrow_shards(dataset_path)
    needed = num_controls * FIELDS_PER_CONTROL
    global_idx = 0

    for shard_path in shards:
        if global_idx >= needed:
            break

        table = _read_shard_table(shard_path, columns=[EMBEDDING_COLUMN])
        emb_col = table.column(EMBEDDING_COLUMN)
        shard_len = len(emb_col)

        # Bulk convert: list<float> column → flat numpy → reshape to (shard_len, dim)
        # combine_chunks() merges ChunkedArray into a single ListArray so we can access .values
        flat = emb_col.combine_chunks().values.to_numpy(zero_copy_only=False)
        shard_matrix = flat.reshape(shard_len, dim).astype(dtype)

        rows_to_use = min(shard_len, needed - global_idx)

        # Vectorized assignment: compute control/field indices for all rows at once
        gi = np.arange(global_idx, global_idx + rows_to_use)
        ctrl_indices = gi // FIELDS_PER_CONTROL
        field_indices = gi % FIELDS_PER_CONTROL
        valid = ctrl_indices < num_controls

        for f_idx in range(FIELDS_PER_CONTROL):
            mask = (field_indices == f_idx) & valid
            if mask.any():
                arrays[embedding_field_names[f_idx]][ctrl_indices[mask]] = shard_matrix[:rows_to_use][mask]

        global_idx += shard_len
        del table, emb_col, flat, shard_matrix

    return arrays
