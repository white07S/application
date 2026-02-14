"""Typed models for DevData Qdrant read-only APIs."""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

PointId = Union[int, str]


class StandardApiError(BaseModel):
    code: str
    message: str
    status: int
    details: Dict[str, Any] = Field(default_factory=dict)


class BaseReadRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    limit: Optional[int] = Field(default=None, ge=1)
    timeout: Optional[int] = Field(default=None, ge=1)


class ScrollPointsRequest(BaseReadRequest):
    pass


class QueryPointsRequest(BaseReadRequest):
    pass


class RetrievePointsRequest(BaseReadRequest):
    ids: Optional[List[PointId]] = None


class FacetRequest(BaseReadRequest):
    key: Optional[str] = None


class MatrixPairsRequest(BaseReadRequest):
    sample: Optional[int] = Field(default=None, ge=1)


class CollectionInsightsRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    sample_limit: int = Field(default=1000, ge=1, le=5000)
    filter: Optional[Dict[str, Any]] = None


class CollectionListItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    status: Optional[str] = None
    points_count: Optional[int] = None
    vectors_count: Optional[int] = None


class CollectionListResponse(BaseModel):
    collections: List[CollectionListItem] = Field(default_factory=list)


class CollectionInfoResponse(BaseModel):
    collection_name: str
    status: Optional[str] = None
    points_count: int = 0
    vectors_count: int = 0
    named_vectors: List[str] = Field(default_factory=list)
    payload_schema: Dict[str, Any] = Field(default_factory=dict)
    info: Dict[str, Any] = Field(default_factory=dict)


class CollectionSummaryResponse(BaseModel):
    collection_name: str
    status: Optional[str] = None
    points_count: int = 0
    vectors_count: int = 0
    vectors: List[str] = Field(default_factory=list)
    aliases_count: int = 0
    snapshots_count: int = 0


class PointRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: PointId
    payload: Optional[Dict[str, Any]] = None
    vector: Optional[Any] = None
    score: Optional[float] = None


class ScrollPointsResponse(BaseModel):
    points: List[PointRecord] = Field(default_factory=list)
    next_page_offset: Optional[PointId] = None
    total_loaded: int = 0


class QueryPointsResponse(BaseModel):
    points: List[PointRecord] = Field(default_factory=list)
    total_loaded: int = 0


class RetrievePointsResponse(BaseModel):
    points: List[PointRecord] = Field(default_factory=list)
    total_loaded: int = 0


class FacetHit(BaseModel):
    model_config = ConfigDict(extra="allow")

    value: Any
    count: Optional[int] = None


class FacetResponse(BaseModel):
    hits: List[FacetHit] = Field(default_factory=list)


class AliasItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    alias_name: str
    collection_name: Optional[str] = None


class AliasListResponse(BaseModel):
    aliases: List[AliasItem] = Field(default_factory=list)


class SnapshotListItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    creation_time: Optional[str] = None
    size: Optional[int] = None


class SnapshotListResponse(BaseModel):
    snapshots: List[SnapshotListItem] = Field(default_factory=list)


class ClusterStatusResponse(BaseModel):
    status: str
    peers: Dict[str, Any] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)


class CollectionClusterResponse(BaseModel):
    status: str
    result: Dict[str, Any] = Field(default_factory=dict)
    local_shards: List[Dict[str, Any]] = Field(default_factory=list)
    remote_shards: List[Dict[str, Any]] = Field(default_factory=list)


class OptimizationsResponse(BaseModel):
    result: Dict[str, Any] = Field(default_factory=dict)


class MatrixPair(BaseModel):
    model_config = ConfigDict(extra="allow")

    a: PointId
    b: PointId
    score: Optional[float] = None


class MatrixPairsResponse(BaseModel):
    pairs: List[MatrixPair] = Field(default_factory=list)


class TopFieldValue(BaseModel):
    value: Any
    count: int
    pct: float


class PayloadFieldQuality(BaseModel):
    field: str
    coverage_pct: float
    null_pct: float
    empty_pct: float
    distinct_count: int
    top_values: List[TopFieldValue] = Field(default_factory=list)
    type_conflicts: List[str] = Field(default_factory=list)


class PayloadQualityResponse(BaseModel):
    sample_points: int
    fields: List[PayloadFieldQuality] = Field(default_factory=list)


class VectorNormPercentiles(BaseModel):
    p05: Optional[float] = None
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None
    p95: Optional[float] = None


class VectorHealthEntry(BaseModel):
    vector_name: str
    expected_dim: Optional[int] = None
    points_seen: int
    present_count: int
    missing_rate_pct: float
    dimension_mismatch_count: int
    unsupported_format_count: int
    zero_vector_rate_pct: float
    norm_percentiles: VectorNormPercentiles


class VectorHealthResponse(BaseModel):
    sample_points: int
    vectors: List[VectorHealthEntry] = Field(default_factory=list)
