"""Alembic environment configuration for async PostgreSQL."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from server.settings import get_settings

# Import all schema modules so their tables register on shared metadata
from server.pipelines.orgs.schema import *  # noqa: F401,F403
from server.pipelines.risks.schema import *  # noqa: F401,F403
from server.pipelines.controls.schema import *  # noqa: F401,F403
from server.pipelines.assessment_units.schema import *  # noqa: F401,F403
from server.jobs.models import *  # noqa: F401,F403
from server.devdata.snapshot_models import *  # noqa: F401,F403

from server.pipelines.schema.base import metadata as target_metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL script."""
    settings = get_settings()
    context.configure(
        url=settings.postgres_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to DB."""
    settings = get_settings()
    engine = create_async_engine(settings.postgres_url)

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
