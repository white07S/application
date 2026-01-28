from fastapi import APIRouter

from server.auth import router as auth_router
from server.pipelines.api.upload import router as pipelines_v2_router
from server.pipelines.api.tus import router as tus_router
from server.pipelines.api.config import router as config_router
from server.pipelines.api.processing import router as processing_router
from . import docs
from . import health

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(pipelines_v2_router)
api_router.include_router(tus_router)
api_router.include_router(config_router)
api_router.include_router(processing_router)
api_router.include_router(docs.router)
api_router.include_router(health.router)
