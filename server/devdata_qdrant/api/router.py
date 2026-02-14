"""Read-only DevData Qdrant API router."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from server.auth.models import AccessResponse
from server.devdata_qdrant.api.models import (
    AliasListResponse,
    ClusterStatusResponse,
    CollectionClusterResponse,
    CollectionInfoResponse,
    CollectionInsightsRequest,
    CollectionListResponse,
    CollectionSummaryResponse,
    FacetRequest,
    FacetResponse,
    MatrixPairsRequest,
    MatrixPairsResponse,
    OptimizationsResponse,
    PayloadQualityResponse,
    QueryPointsRequest,
    QueryPointsResponse,
    RetrievePointsRequest,
    RetrievePointsResponse,
    ScrollPointsRequest,
    ScrollPointsResponse,
    SnapshotListResponse,
    StandardApiError,
    VectorHealthResponse,
)
from server.devdata_qdrant.dependencies import require_dev_data_access
from server.devdata_qdrant.service import qdrant_read_service
from server.devdata_qdrant.service.qdrant_read_service import DevDataQdrantError

router = APIRouter(prefix="/v2/devdata/qdrant", tags=["DevData Qdrant"])

_ERROR_RESPONSES: Dict[int, Dict[str, Any]] = {
    400: {"model": StandardApiError},
    401: {"model": StandardApiError},
    403: {"model": StandardApiError},
    404: {"model": StandardApiError},
    422: {"model": StandardApiError},
    500: {"model": StandardApiError},
    501: {"model": StandardApiError},
    502: {"model": StandardApiError},
    503: {"model": StandardApiError},
    504: {"model": StandardApiError},
}


def _error_response(error: DevDataQdrantError) -> JSONResponse:
    return JSONResponse(status_code=error.status, content=error.to_payload())


async def _run(coro):
    try:
        return await coro
    except DevDataQdrantError as error:
        return _error_response(error)


@router.get("/collections", response_model=CollectionListResponse, responses=_ERROR_RESPONSES)
async def list_collections(access: AccessResponse = Depends(require_dev_data_access)):
    return await _run(qdrant_read_service.list_collections(user=access.user))


@router.get(
    "/collections/{collection_name}",
    response_model=CollectionInfoResponse,
    responses=_ERROR_RESPONSES,
)
async def collection_info(collection_name: str, access: AccessResponse = Depends(require_dev_data_access)):
    return await _run(
        qdrant_read_service.get_collection_info(
            collection_name=collection_name,
            user=access.user,
        )
    )


@router.get(
    "/collections/{collection_name}/summary",
    response_model=CollectionSummaryResponse,
    responses=_ERROR_RESPONSES,
)
async def collection_summary(collection_name: str, access: AccessResponse = Depends(require_dev_data_access)):
    return await _run(
        qdrant_read_service.get_collection_summary(
            collection_name=collection_name,
            user=access.user,
        )
    )


@router.post(
    "/collections/{collection_name}/points/scroll",
    response_model=ScrollPointsResponse,
    responses=_ERROR_RESPONSES,
)
async def points_scroll(
    collection_name: str,
    request: ScrollPointsRequest = Body(default_factory=ScrollPointsRequest),
    access: AccessResponse = Depends(require_dev_data_access),
):
    return await _run(
        qdrant_read_service.scroll_points(
            collection_name=collection_name,
            payload=request.model_dump(exclude_none=True),
            user=access.user,
        )
    )


@router.post(
    "/collections/{collection_name}/points/query",
    response_model=QueryPointsResponse,
    responses=_ERROR_RESPONSES,
)
async def points_query(
    collection_name: str,
    request: QueryPointsRequest = Body(default_factory=QueryPointsRequest),
    access: AccessResponse = Depends(require_dev_data_access),
):
    return await _run(
        qdrant_read_service.query_points(
            collection_name=collection_name,
            payload=request.model_dump(exclude_none=True),
            user=access.user,
        )
    )


@router.post(
    "/collections/{collection_name}/points/retrieve",
    response_model=RetrievePointsResponse,
    responses=_ERROR_RESPONSES,
)
async def points_retrieve(
    collection_name: str,
    request: RetrievePointsRequest = Body(default_factory=RetrievePointsRequest),
    access: AccessResponse = Depends(require_dev_data_access),
):
    return await _run(
        qdrant_read_service.retrieve_points(
            collection_name=collection_name,
            payload=request.model_dump(exclude_none=True),
            user=access.user,
        )
    )


@router.post(
    "/collections/{collection_name}/facet",
    response_model=FacetResponse,
    responses=_ERROR_RESPONSES,
)
async def collection_facet(
    collection_name: str,
    request: FacetRequest = Body(default_factory=FacetRequest),
    access: AccessResponse = Depends(require_dev_data_access),
):
    return await _run(
        qdrant_read_service.facet_values(
            collection_name=collection_name,
            payload=request.model_dump(exclude_none=True),
            user=access.user,
        )
    )


@router.get(
    "/collections/{collection_name}/aliases",
    response_model=AliasListResponse,
    responses=_ERROR_RESPONSES,
)
async def collection_aliases(collection_name: str, access: AccessResponse = Depends(require_dev_data_access)):
    return await _run(
        qdrant_read_service.list_collection_aliases(
            collection_name=collection_name,
            user=access.user,
        )
    )


@router.get(
    "/collections/{collection_name}/snapshots",
    response_model=SnapshotListResponse,
    responses=_ERROR_RESPONSES,
)
async def collection_snapshots(collection_name: str, access: AccessResponse = Depends(require_dev_data_access)):
    return await _run(
        qdrant_read_service.list_collection_snapshots(
            collection_name=collection_name,
            user=access.user,
        )
    )


@router.get(
    "/collections/{collection_name}/snapshots/{snapshot_name}/download",
    responses=_ERROR_RESPONSES,
)
async def collection_snapshot_download(
    collection_name: str,
    snapshot_name: str,
    access: AccessResponse = Depends(require_dev_data_access),
):
    return await _run(
        qdrant_read_service.download_snapshot(
            collection_name=collection_name,
            snapshot_name=snapshot_name,
            user=access.user,
        )
    )


@router.get("/cluster", response_model=ClusterStatusResponse, responses=_ERROR_RESPONSES)
async def qdrant_cluster(access: AccessResponse = Depends(require_dev_data_access)):
    return await _run(qdrant_read_service.cluster_status(user=access.user))


@router.get(
    "/collections/{collection_name}/cluster",
    response_model=CollectionClusterResponse,
    responses=_ERROR_RESPONSES,
)
async def qdrant_collection_cluster(collection_name: str, access: AccessResponse = Depends(require_dev_data_access)):
    return await _run(
        qdrant_read_service.collection_cluster(
            collection_name=collection_name,
            user=access.user,
        )
    )


@router.get(
    "/collections/{collection_name}/optimizations",
    response_model=OptimizationsResponse,
    responses=_ERROR_RESPONSES,
)
async def qdrant_collection_optimizations(
    collection_name: str,
    access: AccessResponse = Depends(require_dev_data_access),
):
    return await _run(
        qdrant_read_service.collection_optimizations(
            collection_name=collection_name,
            user=access.user,
        )
    )


@router.post(
    "/collections/{collection_name}/insights/payload",
    response_model=PayloadQualityResponse,
    responses=_ERROR_RESPONSES,
)
async def qdrant_collection_payload_quality(
    collection_name: str,
    request: CollectionInsightsRequest = Body(default_factory=CollectionInsightsRequest),
    access: AccessResponse = Depends(require_dev_data_access),
):
    return await _run(
        qdrant_read_service.payload_quality(
            collection_name=collection_name,
            payload=request.model_dump(exclude_none=True),
            user=access.user,
        )
    )


@router.post(
    "/collections/{collection_name}/insights/vectors",
    response_model=VectorHealthResponse,
    responses=_ERROR_RESPONSES,
)
async def qdrant_collection_vector_health(
    collection_name: str,
    request: CollectionInsightsRequest = Body(default_factory=CollectionInsightsRequest),
    access: AccessResponse = Depends(require_dev_data_access),
):
    return await _run(
        qdrant_read_service.vector_health(
            collection_name=collection_name,
            payload=request.model_dump(exclude_none=True),
            user=access.user,
        )
    )


@router.post(
    "/collections/{collection_name}/points/search/matrix/pairs",
    response_model=MatrixPairsResponse,
    responses=_ERROR_RESPONSES,
)
async def qdrant_collection_matrix_pairs(
    collection_name: str,
    request: MatrixPairsRequest = Body(default_factory=MatrixPairsRequest),
    access: AccessResponse = Depends(require_dev_data_access),
):
    return await _run(
        qdrant_read_service.matrix_pairs(
            collection_name=collection_name,
            payload=request.model_dump(exclude_none=True),
            user=access.user,
        )
    )
