"""SurrealDB Schema Setup Functions.

This module provides async functions to create, drop, and reset the SurrealDB
schema for the controls management system.

Functions:
    - create_schema: Create all tables, fields, indexes, and relationships
    - drop_schema: Drop all tables to reset the database
    - reset_schema: Drop and recreate the schema (drop + create)

Usage:
    from surrealdb import AsyncSurreal
    from server.pipelines.controls.schema import create_schema, reset_schema

    async with get_surrealdb_connection() as db:
        await create_schema(db)
        # or
        await reset_schema(db)
"""

from typing import List
from surrealdb import AsyncSurreal

from server.logging_config import get_logger
from .definitions import SCHEMA_STATEMENTS, ALL_TABLES

logger = get_logger(name=__name__)


async def create_schema(db: AsyncSurreal) -> None:
    """Create all tables, fields, indexes, and graph relations.

    This function creates the complete SurrealDB schema including:
    - Source reference tables (src_controls_ref_*)
    - Source main tables (src_controls_main, src_controls_versions)
    - Source relationship edges (src_controls_rel_*)
    - AI model output tables (ai_controls_model_*)
    - AI relationship edges (ai_controls_rel_*)
    - Indexes and full-text search analyzers

    Args:
        db: Connected SurrealDB client instance.

    Raises:
        Exception: If any schema creation statement fails.

    Example:
        async with get_surrealdb_connection() as db:
            await create_schema(db)
            logger.info("Schema created successfully")
    """
    logger.info("Creating SurrealDB schema...")
    total = len(SCHEMA_STATEMENTS)
    success = 0
    failed = 0
    errors: List[str] = []

    for i, stmt in enumerate(SCHEMA_STATEMENTS, 1):
        try:
            await db.query(stmt)
            success += 1

            # Extract table/index/field name for cleaner logging
            parts = stmt.split()
            obj_type = parts[1]  # TABLE, FIELD, INDEX, ANALYZER
            obj_name = parts[2] if obj_type != "FIELD" else parts[2]

            if obj_type == "FIELD":
                obj_name = f"{parts[2]} on {parts[5]}"
            elif obj_type == "INDEX":
                obj_name = f"{parts[2]} on {parts[5]}"

            logger.debug(f"[{i}/{total}] Created {obj_type} {obj_name}")

        except Exception as e:
            failed += 1
            error_msg = f"[{i}/{total}] Failed: {stmt[:50]}... Error: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    logger.info(
        f"Schema creation complete. Success: {success}, Failed: {failed}"
    )

    if failed > 0:
        logger.warning(f"Schema creation had {failed} failures")
        for error in errors[:5]:  # Log first 5 errors
            logger.error(error)
        if len(errors) > 5:
            logger.error(f"... and {len(errors) - 5} more errors")


async def drop_schema(db: AsyncSurreal) -> None:
    """Drop all tables to reset the database.

    This function removes all tables defined in the schema. Use with caution
    as this will delete all data and table definitions.

    Args:
        db: Connected SurrealDB client instance.

    Raises:
        Exception: If any table drop operation fails.

    Example:
        async with get_surrealdb_connection() as db:
            await drop_schema(db)
            logger.info("Schema dropped successfully")
    """
    logger.info("Dropping all SurrealDB tables...")
    success = 0
    failed = 0
    errors: List[str] = []

    for table in ALL_TABLES:
        try:
            await db.query(f"REMOVE TABLE IF EXISTS {table}")
            success += 1
            logger.debug(f"Dropped: {table}")
        except Exception as e:
            failed += 1
            error_msg = f"Error dropping {table}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    logger.info(
        f"Schema drop complete. Success: {success}, Failed: {failed}"
    )

    if failed > 0:
        logger.warning(f"Schema drop had {failed} failures")
        for error in errors:
            logger.error(error)


async def reset_schema(db: AsyncSurreal) -> None:
    """Reset the schema by dropping and recreating all tables.

    This is a convenience function that combines drop_schema and create_schema.
    Use this when you want a clean slate for the database.

    Args:
        db: Connected SurrealDB client instance.

    Raises:
        Exception: If drop or create operations fail.

    Example:
        async with get_surrealdb_connection() as db:
            await reset_schema(db)
            logger.info("Schema reset successfully")
    """
    logger.info("Resetting SurrealDB schema (drop + create)...")
    await drop_schema(db)
    await create_schema(db)
    logger.info("Schema reset complete")
