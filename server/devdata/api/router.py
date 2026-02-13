"""API endpoints for Dev Data — read-only PostgreSQL + Qdrant browser."""

from fastapi import APIRouter, Depends, HTTPException, Query

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.logging_config import get_logger
from server.devdata.models import (
    ConnectionStatus,
    TableListResponse,
    TableInfo,
    PaginatedRecords,
    RelationshipExpansion,
    QdrantStats,
)
from server.devdata.service import (
    get_connection_status,
    get_tables_with_counts,
    get_table_records,
    get_single_record,
    expand_relationship,
    get_qdrant_stats,
    get_data_consistency_stats,
)

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/devdata", tags=["DevData"])


async def _require_dev_data_access(token: str = Depends(get_token_from_header)):
    """Dependency that verifies the user has dev data access."""
    access = await get_access_control(token)
    if not access.hasDevDataAccess:
        raise HTTPException(status_code=403, detail="Dev data access required")
    return access


@router.get("/connection", response_model=ConnectionStatus)
async def connection_status(_=Depends(_require_dev_data_access)):
    """Get PostgreSQL connection status."""
    result = await get_connection_status()
    return ConnectionStatus(**result)


@router.get("/tables", response_model=TableListResponse)
async def list_tables(_=Depends(_require_dev_data_access)):
    """List all PostgreSQL tables with record counts."""
    tables = await get_tables_with_counts()
    return TableListResponse(tables=[TableInfo(**t) for t in tables])


@router.get("/tables/{table_name}", response_model=PaginatedRecords)
async def table_records(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _=Depends(_require_dev_data_access),
):
    """Get paginated records from a specific table."""
    result = await get_table_records(table_name, page, page_size)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return PaginatedRecords(**result)


@router.get("/tables/{table_name}/record/{record_id:path}")
async def single_record(
    table_name: str,
    record_id: str,
    _=Depends(_require_dev_data_access),
):
    """Get a single record by its primary key."""
    result = await get_single_record(table_name, record_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Record '{record_id}' not found")
    return result


@router.get("/relationships/{table_name}/{record_id:path}", response_model=RelationshipExpansion)
async def relationship_expansion(
    table_name: str,
    record_id: str,
    _=Depends(_require_dev_data_access),
):
    """Expand a relationship record to show linked records via foreign keys."""
    result = await expand_relationship(table_name, record_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Relationship '{record_id}' not found or table is not a relation")
    return RelationshipExpansion(**result)


@router.get("/qdrant/stats", response_model=QdrantStats)
async def qdrant_stats(_=Depends(_require_dev_data_access)):
    """Get Qdrant collection statistics."""
    result = await get_qdrant_stats()
    if result is None:
        raise HTTPException(status_code=503, detail="Qdrant collection not available")
    return QdrantStats(**result)


@router.get("/consistency")
async def data_consistency(_=Depends(_require_dev_data_access)):
    """Get data consistency stats between PostgreSQL and Qdrant."""
    return await get_data_consistency_stats()
