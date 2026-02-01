from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server import settings
from server.api import api_router
from server.middleware import RequestLoggingMiddleware
from server.logging_config import configure_logging, get_logger
from server.jobs import init_jobs_database
from server.pipelines.storage import init_storage_directories

# Configure shared Loguru logging
configure_logging()
logger = get_logger(name=__name__)


# DEPRECATED: Old pipeline directories - replaced by new storage system
# def _init_data_directories() -> None:
#     """Initialize data ingestion directories on startup."""
#     data_types = ["issues", "controls", "actions"]
#
#     # Ensure base directory exists
#     settings.DATA_INGESTION_PATH.mkdir(parents=True, exist_ok=True)
#     logger.info("Data ingestion base path: %s", settings.DATA_INGESTION_PATH)
#
#     # Ensure subdirectories exist
#     for data_type in data_types:
#         type_dir = settings.DATA_INGESTION_PATH / data_type
#         type_dir.mkdir(parents=True, exist_ok=True)
#         logger.info("Ensured directory exists: %s", type_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Starting NFR Connect server...")
    # _init_data_directories()  # DEPRECATED: Old pipeline directories

    # Initialize storage directories (uploads, preprocessed, etc.)
    logger.info("Initializing storage directories...")
    init_storage_directories()
    logger.info("Storage directories initialized")

    # Initialize jobs database (SQLite for tracking)
    logger.info("Initializing jobs database...")
    init_jobs_database()
    logger.info("Jobs database initialization complete")

    logger.info("Server initialization complete")

    yield

    # Shutdown
    logger.info("Shutting down NFR Connect server...")

    # Shutdown MSAL thread pools
    try:
        from server.auth.service import _msal_executor
        _msal_executor.shutdown(wait=False)
        logger.info("Auth MSAL thread pool shut down")
    except Exception as e:
        logger.warning("Error shutting down auth MSAL executor: {}", e)

    try:
        from server.auth.token_manager import _token_executor
        _token_executor.shutdown(wait=False)
        logger.info("Token manager thread pool shut down")
    except Exception as e:
        logger.warning("Error shutting down token manager executor: {}", e)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.UVICORN_HOST, port=settings.UVICORN_PORT)
