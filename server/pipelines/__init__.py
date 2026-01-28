"""Pipelines module for data upload, validation, and processing.

This module is organized into subpackages:
- api: FastAPI routers for HTTP endpoints
- config: Configuration loading and services
- processing: Core processing logic (batch, graph, ingestion)
- validation: Data validation and schema checking

For backward compatibility, key components are re-exported here.
"""

# Re-export API routers for backward compatibility
from .api.upload import router as upload_router
from .api.config import router as config_router
from .api.processing import router as processing_router
from .api.tus import router as tus_router

# Backward compatibility: expose router_v2.router as the main router
from .api.upload import router

__all__ = [
    "router",
    "upload_router",
    "config_router",
    "processing_router",
    "tus_router",
]
