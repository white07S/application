from fastapi import APIRouter

from server.auth import router as auth_router
from server.pipelines import router as pipelines_router
from . import docs

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(pipelines_router)
api_router.include_router(docs.router)
