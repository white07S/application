"""API routers for controls pipeline module."""

from .upload import router as upload_router
from .config import router as config_router
from .processing import router as processing_router
from .tus import router as tus_router

__all__ = ["upload_router", "config_router", "processing_router", "tus_router"]
