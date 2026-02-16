from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server import settings
from server.api import api_router
from server.middleware import RequestLoggingMiddleware
from server.logging_config import configure_logging, get_logger

# Configure shared Loguru logging
configure_logging()
logger = get_logger(name=__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Starting NFR Connect server...")

    # Initialize PostgreSQL engine
    try:
        from server.config.postgres import init_engine, get_engine
        from server.settings import get_settings
        s = get_settings()
        init_engine(s.postgres_url, s.postgres_pool_size, s.postgres_max_overflow)

        # Quick connectivity check
        engine = get_engine()
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connection verified")
    except Exception as e:
        logger.error("PostgreSQL connection failed on startup: {}", e)
        raise

    # Verify Alembic migration is at head
    try:
        from server.pipelines.schema.setup import check_alembic_current
        await check_alembic_current()
    except Exception as e:
        logger.error("Alembic migration check failed: {}", e)
        raise

    # Verify context providers (org charts + risk themes) are loaded
    try:
        from server.pipelines.schema.setup import verify_context_providers_loaded
        await verify_context_providers_loaded()
    except SystemExit:
        raise
    except Exception as e:
        logger.error("Context provider verification failed: {}", e)
        raise

    # Initialize Qdrant client
    try:
        from server.config.qdrant import init_qdrant
        s = get_settings()
        await init_qdrant(s.qdrant_url, s.qdrant_collection_prefix)
        logger.info("Qdrant client initialized with prefix: {}", s.qdrant_collection_prefix)
    except Exception as e:
        logger.error("Qdrant initialization failed: {}", e)
        raise

    # Initialize Redis cache
    try:
        from server.config.redis import init_redis
        await init_redis(s.redis_url)
    except Exception as e:
        logger.error("Redis initialization failed: {}", e)
        raise

    # Initialize storage directories
    from server.pipelines.storage import init_storage_directories
    logger.info("Initializing storage directories...")
    init_storage_directories()
    logger.info("Storage directories initialized")

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

    # Close Redis client
    try:
        from server.config.redis import close_redis
        await close_redis()
    except Exception as e:
        logger.warning("Error closing Redis client: {}", e)

    # Close Qdrant client
    try:
        from server.config.qdrant import close_qdrant
        await close_qdrant()
        logger.info("Qdrant client closed")
    except Exception as e:
        logger.warning("Error closing Qdrant client: {}", e)

    # Dispose PostgreSQL engine
    try:
        from server.config.postgres import dispose_engine
        await dispose_engine()
        logger.info("PostgreSQL engine disposed")
    except Exception as e:
        logger.warning("Error disposing PostgreSQL engine: {}", e)


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
