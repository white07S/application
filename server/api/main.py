from fastapi import APIRouter

from server.auth import router as auth_router
from server.pipelines.controls.api.upload import router as pipelines_v2_router
from server.pipelines.controls.api.tus import router as tus_router
from server.pipelines.controls.api.processing import router as ingestion_router
from server.devdata.api.router import router as devdata_router
from server.devdata_qdrant.api.router import router as devdata_qdrant_router
from server.explorer.filters.api.router import router as explorer_filters_router
from . import docs
from . import health
from . import stats

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(pipelines_v2_router)
api_router.include_router(tus_router)
api_router.include_router(ingestion_router)
api_router.include_router(devdata_router)
api_router.include_router(devdata_qdrant_router)
api_router.include_router(explorer_filters_router)
api_router.include_router(docs.router)
api_router.include_router(health.router)
api_router.include_router(stats.router)
