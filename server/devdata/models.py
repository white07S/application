"""Response models for the Dev Data API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ConnectionStatus(BaseModel):
    connected: bool
    url: str
    database: str
    error: Optional[str] = None


class TableInfo(BaseModel):
    name: str
    category: str
    domain: str
    record_count: int
    is_relation: bool


class TableListResponse(BaseModel):
    tables: List[TableInfo]


class PaginatedRecords(BaseModel):
    table_name: str
    records: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int
    is_relation: bool
    has_embeddings: bool


class RelationshipExpansion(BaseModel):
    edge: Dict[str, Any]
    in_record: Optional[Dict[str, Any]] = None
    out_record: Optional[Dict[str, Any]] = None
    in_table: str
    out_table: str


class QdrantStats(BaseModel):
    collection_name: str
    points_count: int
    vectors_count: int
    status: str
    named_vectors: List[str]
    indexing_progress: Optional[float] = None
    indexed_vectors_count: Optional[int] = None
