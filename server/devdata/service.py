"""Service layer for Dev Data PostgreSQL + Qdrant browser.

Iterates over SQLAlchemy Table objects registered in shared metadata
to discover tables, record counts, and provide paginated browsing.
"""

import math
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from server.config.postgres import get_engine
from server.logging_config import get_logger
from server.pipelines.schema.base import metadata
from server.pipelines.controls import qdrant_service
from server.settings import get_settings

logger = get_logger(name=__name__)

# Tables that represent temporal relations (edge tables)
_RELATION_TABLE_NAMES = {
    "src_orgs_rel_child",
    "src_orgs_rel_cross_link",
    "src_controls_rel_parent",
    "src_controls_rel_owns_function",
    "src_controls_rel_owns_location",
    "src_controls_rel_related_function",
    "src_controls_rel_related_location",
    "src_controls_rel_risk_theme",
    "src_risks_rel_taxonomy_theme",
}


def _serialize_value(value: Any) -> Any:
    """Convert database types to JSON-serializable form."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    # Handle datetime objects
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _serialize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize a full record for JSON response."""
    return {k: _serialize_value(v) for k, v in record.items()}


def categorize_table(name: str) -> str:
    """Categorize a table by naming convention patterns."""
    if "_ref_" in name:
        return "reference"
    if "_rel_" in name:
        return "relation"
    if "_model_" in name:
        return "model"
    if "_ver_" in name:
        return "version"
    if "_main" in name:
        return "main"

    parts = name.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"

    return "other"


async def get_connection_status() -> Dict[str, Any]:
    """Check PostgreSQL connection and return status."""
    settings = get_settings()
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            return {
                "connected": True,
                "url": settings.postgres_url.split("@")[-1] if "@" in settings.postgres_url else settings.postgres_url,
                "database": "PostgreSQL",
                "error": None,
            }
    except Exception as e:
        return {
            "connected": False,
            "url": "",
            "database": "PostgreSQL",
            "error": str(e),
        }


async def get_tables_with_counts() -> List[Dict[str, Any]]:
    """Get all known tables with record counts from PostgreSQL."""
    tables = []
    engine = get_engine()

    async with engine.connect() as conn:
        for table_name, table_obj in sorted(metadata.tables.items()):
            try:
                result = await conn.execute(
                    select(func.count()).select_from(table_obj)
                )
                count = result.scalar_one()
            except Exception as e:
                logger.warning("Error counting table {}: {}", table_name, e)
                count = -1

            tables.append({
                "name": table_name,
                "category": categorize_table(table_name),
                "record_count": count,
                "is_relation": table_name in _RELATION_TABLE_NAMES,
            })

    return tables


async def get_table_records(
    table_name: str,
    page: int = 1,
    page_size: int = 50,
) -> Optional[Dict[str, Any]]:
    """Get paginated records from a table."""
    table_obj = metadata.tables.get(table_name)
    if table_obj is None:
        return None

    is_relation = table_name in _RELATION_TABLE_NAMES

    engine = get_engine()
    async with engine.connect() as conn:
        # Total count
        count_result = await conn.execute(
            select(func.count()).select_from(table_obj)
        )
        total = count_result.scalar_one()

        # Paginated records
        offset = (page - 1) * page_size
        result = await conn.execute(
            select(table_obj).limit(page_size).offset(offset)
        )
        rows = result.mappings().all()
        records = [_serialize_record(dict(row)) for row in rows]

        return {
            "table_name": table_name,
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, math.ceil(total / page_size)),
            "is_relation": is_relation,
            "has_embeddings": False,
        }


async def get_single_record(table_name: str, record_id: str) -> Optional[Dict[str, Any]]:
    """Get a single record by its primary key value."""
    table_obj = metadata.tables.get(table_name)
    if table_obj is None:
        return None

    # Find primary key column
    pk_cols = [c for c in table_obj.columns if c.primary_key]
    if not pk_cols:
        return None

    pk_col = pk_cols[0]

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(table_obj).where(pk_col == record_id).limit(1)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return _serialize_record(dict(row))


async def expand_relationship(table_name: str, record_id: str) -> Optional[Dict[str, Any]]:
    """Expand a relation table record to show linked records.

    Relations use FK columns. We detect FK columns and fetch the referenced records.
    """
    table_obj = metadata.tables.get(table_name)
    if table_obj is None or table_name not in _RELATION_TABLE_NAMES:
        return None

    # Get the edge record
    pk_cols = [c for c in table_obj.columns if c.primary_key]
    if not pk_cols:
        return None
    pk_col = pk_cols[0]

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(table_obj).where(pk_col == record_id).limit(1)
        )
        row = result.mappings().first()
        if row is None:
            return None

        edge = _serialize_record(dict(row))

        # Find FK columns and their referenced tables
        in_record = None
        out_record = None
        in_table = ""
        out_table = ""

        fk_columns = [
            (c.name, list(c.foreign_keys))
            for c in table_obj.columns
            if c.foreign_keys
        ]

        for idx, (col_name, fks) in enumerate(fk_columns):
            if not fks:
                continue
            fk = list(fks)[0]
            ref_table_name = fk.column.table.name
            ref_col = fk.column
            ref_table = metadata.tables.get(ref_table_name)
            if ref_table is None:
                continue

            fk_value = row[col_name]
            if fk_value is None:
                continue

            try:
                linked = await conn.execute(
                    select(ref_table).where(ref_col == fk_value).limit(1)
                )
                linked_row = linked.mappings().first()
                if linked_row:
                    linked_data = _serialize_record(dict(linked_row))
                    if idx == 0:
                        in_record = linked_data
                        in_table = ref_table_name
                    else:
                        out_record = linked_data
                        out_table = ref_table_name
            except Exception as e:
                logger.warning("Error fetching linked record from {}: {}", ref_table_name, e)

        return {
            "edge": edge,
            "in_record": in_record,
            "out_record": out_record,
            "in_table": in_table,
            "out_table": out_table,
        }


async def get_qdrant_stats() -> Optional[Dict[str, Any]]:
    """Get Qdrant collection stats for DevData UI."""
    return await qdrant_service.get_collection_info()


async def get_data_consistency_stats() -> Dict[str, Any]:
    """Get data consistency stats comparing PostgreSQL and Qdrant.

    Returns counts to verify data integrity between systems.
    """
    from server.pipelines.controls.schema import src_controls_ref_control

    engine = get_engine()

    # Get PostgreSQL control count
    async with engine.connect() as conn:
        result = await conn.execute(
            select(func.count()).select_from(src_controls_ref_control)
        )
        postgres_control_count = result.scalar_one()

    # Get Qdrant stats
    qdrant_stats = await qdrant_service.get_collection_info()
    qdrant_points_count = qdrant_stats["points_count"] if qdrant_stats else 0

    # Check consistency
    is_consistent = postgres_control_count == qdrant_points_count

    return {
        "postgres_controls": postgres_control_count,
        "qdrant_points": qdrant_points_count,
        "is_consistent": is_consistent,
        "difference": abs(postgres_control_count - qdrant_points_count),
    }
