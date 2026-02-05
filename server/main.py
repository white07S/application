from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server import settings
from server.api import api_router
from server.middleware import RequestLoggingMiddleware
from server.logging_config import configure_logging, get_logger
from server.jobs import init_jobs_database, shutdown_jobs_engine
from server.pipelines.storage import init_storage_directories

# Configure shared Loguru logging
configure_logging()
logger = get_logger(name=__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Starting NFR Connect server...")

    # Validate database connectivity on startup
    try:
        from server.config.surrealdb import get_surrealdb_connection
        async with get_surrealdb_connection() as surreal_db:
            await surreal_db.query("SELECT * FROM src_controls_main LIMIT 1")
        logger.info("SurrealDB connection verified")
    except Exception as e:
        logger.error("SurrealDB connection failed on startup: {}", e)
        raise

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

    # Checkpoint WAL and dispose jobs database engine
    try:
        shutdown_jobs_engine()
        logger.info("Jobs database engine shut down")
    except Exception as e:
        logger.warning("Error shutting down jobs database engine: {}", e)


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
