import asyncio
import os
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
    """Application lifespan handler with multi-worker safety."""

    worker_id = f"worker-{os.getpid()}"
    logger.info(f"Starting NFR Connect server ({worker_id})...")

    # ═══════════════════════════════════════════════════════════════════
    # Phase 1: Initialize connections (every worker needs these)
    # ═══════════════════════════════════════════════════════════════════

    # Initialize PostgreSQL engine (each worker needs its own pool)
    try:
        from server.config.postgres import init_engine, get_engine
        from server.settings import get_settings
        s = get_settings()

        # Detect if we're running with multiple workers
        worker_count = int(os.environ.get("GUNICORN_WORKERS", "1"))
        if worker_count > 1:
            # Reduce pool size for multi-worker deployment
            pool_size = max(2, s.postgres_pool_size // worker_count)
            logger.info(f"{worker_id}: Adjusting pool size to {pool_size} (multi-worker mode)")
        else:
            pool_size = s.postgres_pool_size

        init_engine(s.postgres_url, pool_size, s.postgres_max_overflow)

        # Quick connectivity check
        engine = get_engine()
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(f"{worker_id}: PostgreSQL connection verified")
    except Exception as e:
        logger.error(f"{worker_id}: PostgreSQL connection failed: {e}")
        raise

    # Initialize Redis (needed for coordination and caching)
    try:
        from server.config.redis import init_redis, get_redis_coordination
        await init_redis(s.redis_url)
        logger.info(f"{worker_id}: Redis clients initialized")
    except Exception as e:
        logger.error(f"{worker_id}: Redis initialization failed: {e}")
        raise

    # ═══════════════════════════════════════════════════════════════════
    # Phase 2: One-time initialization (coordinated across workers)
    # ═══════════════════════════════════════════════════════════════════

    from server.core.worker_sync import WorkerSync, InitTask
    redis_coord = get_redis_coordination()
    sync_manager = WorkerSync(redis_coord)

    # Alembic migration check (only one worker should do this)
    was_leader, _ = await sync_manager.run_once(
        InitTask.ALEMBIC_MIGRATION,
        _check_alembic_migration
    )
    if was_leader:
        logger.info(f"{worker_id}: Completed Alembic migration check")

    # Context providers verification (only once)
    was_leader, _ = await sync_manager.run_once(
        InitTask.CONTEXT_PROVIDERS,
        _verify_context_providers
    )
    if was_leader:
        logger.info(f"{worker_id}: Completed context providers verification")

    # Storage directories initialization (only once)
    was_leader, _ = await sync_manager.run_once(
        InitTask.STORAGE_DIRECTORIES,
        _init_storage_dirs
    )
    if was_leader:
        logger.info(f"{worker_id}: Completed storage directories initialization")

    # ═══════════════════════════════════════════════════════════════════
    # Phase 3: Initialize remaining connections (every worker)
    # ═══════════════════════════════════════════════════════════════════

    # Initialize Qdrant client (with safe collection creation)
    try:
        await _init_qdrant_safe(s.qdrant_url, s.qdrant_collection_prefix, sync_manager)
        logger.info(f"{worker_id}: Qdrant client initialized")
    except Exception as e:
        logger.error(f"{worker_id}: Qdrant initialization failed: {e}")
        raise

    # ═══════════════════════════════════════════════════════════════════
    # Phase 4: Optional optimizations (only leader does these)
    # ═══════════════════════════════════════════════════════════════════

    # Cache warmup (nice to have, only one worker)
    was_leader, _ = await sync_manager.run_once(
        InitTask.CACHE_WARMUP,
        _warm_up_caches
    )
    if was_leader:
        logger.info(f"{worker_id}: Completed cache warmup")

    # Dashboard snapshot seeding (only once)
    was_leader, _ = await sync_manager.run_once(
        InitTask.DASHBOARD_SNAPSHOT,
        _seed_dashboard_snapshot
    )
    if was_leader:
        logger.info(f"{worker_id}: Completed dashboard snapshot seed")

    logger.info(f"{worker_id}: Server initialization complete")

    yield

    # ═══════════════════════════════════════════════════════════════════
    # Shutdown
    # ═══════════════════════════════════════════════════════════════════

    logger.info(f"Shutting down NFR Connect server ({worker_id})...")

    # Shutdown MSAL thread pools
    try:
        from server.auth.service import _msal_executor
        _msal_executor.shutdown(wait=False)
        logger.info(f"{worker_id}: Auth MSAL thread pool shut down")
    except Exception as e:
        logger.warning(f"{worker_id}: Error shutting down auth MSAL executor: {e}")

    try:
        from server.auth.token_manager import _token_executor
        _token_executor.shutdown(wait=False)
        logger.info(f"{worker_id}: Token manager thread pool shut down")
    except Exception as e:
        logger.warning(f"{worker_id}: Error shutting down token manager executor: {e}")

    # Close Redis clients
    try:
        from server.config.redis import close_redis
        await close_redis()
        logger.info(f"{worker_id}: Redis clients closed")
    except Exception as e:
        logger.warning(f"{worker_id}: Error closing Redis clients: {e}")

    # Close Qdrant client
    try:
        from server.config.qdrant import close_qdrant
        await close_qdrant()
        logger.info(f"{worker_id}: Qdrant client closed")
    except Exception as e:
        logger.warning(f"{worker_id}: Error closing Qdrant client: {e}")

    # Dispose PostgreSQL engine
    try:
        from server.config.postgres import dispose_engine
        await dispose_engine()
        logger.info(f"{worker_id}: PostgreSQL engine disposed")
    except Exception as e:
        logger.warning(f"{worker_id}: Error disposing PostgreSQL engine: {e}")


# ═══════════════════════════════════════════════════════════════════
# Helper functions for one-time initialization
# ═══════════════════════════════════════════════════════════════════

async def _check_alembic_migration():
    """Check Alembic migration status."""
    from server.pipelines.schema.setup import check_alembic_current
    await check_alembic_current()


async def _verify_context_providers():
    """Verify context providers are loaded."""
    from server.pipelines.schema.setup import verify_context_providers_loaded
    await verify_context_providers_loaded()


async def _init_storage_dirs():
    """Initialize storage directories."""
    from server.pipelines.storage import init_storage_directories
    init_storage_directories()


async def _init_qdrant_safe(url: str, prefix: str, sync_manager):
    """Initialize Qdrant with safe collection creation."""
    from server.config.qdrant import init_qdrant
    from server.core.worker_sync import InitTask

    # Each worker needs a client
    from qdrant_client import AsyncQdrantClient
    from server.config import qdrant

    qdrant._client = AsyncQdrantClient(url=url)

    # But only one creates collections
    was_leader, _ = await sync_manager.run_once(
        InitTask.QDRANT_COLLECTIONS,
        _create_qdrant_collections,
        prefix
    )

    logger.info(f"Qdrant client ready (collections created: {was_leader})")


async def _create_qdrant_collections(prefix: str):
    """Create Qdrant collections (only once)."""
    from server.config.qdrant import _ensure_controls_collection
    await _ensure_controls_collection(prefix)


async def _warm_up_caches():
    """Warm up explorer filter caches."""
    try:
        from server.explorer.filters.service import (
            get_function_tree,
            get_location_tree,
            get_consolidated_entities,
            get_assessment_units,
            get_risk_taxonomies,
        )
        await asyncio.gather(
            get_function_tree(),
            get_location_tree(),
            get_consolidated_entities(),
            get_assessment_units(),
            get_risk_taxonomies(),
        )
    except Exception as e:
        logger.warning(f"Explorer cache warmup failed (non-fatal): {e}")


async def _seed_dashboard_snapshot():
    """Seed initial dashboard snapshot."""
    try:
        from server.explorer.dashboard.snapshot_builder import seed_initial_snapshot
        await seed_initial_snapshot()
    except Exception as e:
        logger.warning(f"Dashboard snapshot seed failed (non-fatal): {e}")


# ═══════════════════════════════════════════════════════════════════
# FastAPI Application
# ═══════════════════════════════════════════════════════════════════

app = FastAPI(lifespan=lifespan, title="NFR Connect API")

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

    # For development - single worker
    uvicorn.run(app, host=settings.UVICORN_HOST, port=settings.UVICORN_PORT)