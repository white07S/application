"""Configuration service for ingestion pipeline.

This module provides functions to retrieve and manage ingestion configurations
that define how parquet files map to data layer tables.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from server.database import DataSource, IngestionConfig, IngestionFieldMapping, UploadBatch
from server.logging_config import get_logger

from .. import storage

logger = get_logger(name=__name__)


def get_ingestion_configs_by_source(db: Session, data_source_code: str) -> List[IngestionConfig]:
    """Get all active ingestion configs for a data source.

    Args:
        db: Database session
        data_source_code: The data source code (issues, controls, actions)

    Returns:
        List of IngestionConfig records ordered by processing_order
    """
    source = db.query(DataSource).filter_by(source_code=data_source_code).first()
    if not source:
        logger.warning("Data source not found: {}", data_source_code)
        return []

    configs = db.query(IngestionConfig).filter_by(
        data_source_id=source.id,
        is_active=True
    ).order_by(IngestionConfig.processing_order).all()

    logger.debug("Found {} ingestion configs for {}", len(configs), data_source_code)
    return configs


def get_ingestion_config_by_name(db: Session, name: str) -> Optional[IngestionConfig]:
    """Get a specific ingestion config by name.

    Args:
        db: Database session
        name: The config name (e.g., 'controls_main')

    Returns:
        IngestionConfig or None if not found
    """
    return db.query(IngestionConfig).filter_by(name=name, is_active=True).first()


def get_config_with_mappings(db: Session, config_id: int) -> Optional[Dict]:
    """Get an ingestion config with all its field mappings.

    Args:
        db: Database session
        config_id: The ingestion config ID

    Returns:
        Dict with config and field_mappings, or None if not found
    """
    config = db.query(IngestionConfig).filter_by(id=config_id).first()
    if not config:
        return None

    return {
        "id": config.id,
        "name": config.name,
        "description": config.description,
        "source_parquet_name": config.source_parquet_name,
        "target_table_name": config.target_table_name,
        "primary_key_columns": json.loads(config.primary_key_columns),
        "version_strategy": config.version_strategy,
        "processing_order": config.processing_order,
        "is_active": config.is_active,
        "field_mappings": [
            {
                "id": fm.id,
                "source_column": fm.source_column,
                "target_column": fm.target_column,
                "data_type": fm.data_type,
                "is_required": fm.is_required,
                "is_primary_key": fm.is_primary_key,
                "default_value": fm.default_value,
                "transform_function": fm.transform_function,
            }
            for fm in sorted(config.field_mappings, key=lambda x: x.column_order)
        ]
    }


def get_ingestion_plan(db: Session, batch_id: int) -> List[Dict]:
    """Get the ingestion plan for a batch.

    This returns the list of datasets to ingest from a batch's parquet files,
    including the file paths and configuration for each.

    Args:
        db: Database session
        batch_id: The upload batch ID

    Returns:
        List of dicts with ingestion plan details for each parquet file
    """
    batch = db.query(UploadBatch).filter_by(id=batch_id).first()
    if not batch:
        logger.warning("Batch not found: {}", batch_id)
        return []

    # Get data source
    source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
    if not source:
        logger.warning("Data source not found for batch: {}", batch_id)
        return []

    # Get preprocessed path where parquet files are stored
    preprocessed_path = storage.get_preprocessed_batch_path(batch.upload_id, source.source_code)

    if not preprocessed_path.exists():
        logger.warning("Preprocessed path does not exist: {}", preprocessed_path)
        return []

    # Get all ingestion configs for this data source
    configs = get_ingestion_configs_by_source(db, source.source_code)

    # Build ingestion plan
    plan = []
    for config in configs:
        parquet_file = preprocessed_path / config.source_parquet_name

        if not parquet_file.exists():
            logger.debug("Parquet file not found (may be empty): {}", parquet_file)
            continue

        plan.append({
            "config_id": config.id,
            "config_name": config.name,
            "source_parquet_path": str(parquet_file),
            "target_table_name": config.target_table_name,
            "primary_key_columns": json.loads(config.primary_key_columns),
            "version_strategy": config.version_strategy,
            "processing_order": config.processing_order,
        })

    logger.info(
        "Built ingestion plan for batch %s: %d datasets",
        batch.upload_id, len(plan)
    )

    return plan


def list_all_configs(db: Session, data_source_code: Optional[str] = None) -> List[Dict]:
    """List all ingestion configs, optionally filtered by data source.

    Args:
        db: Database session
        data_source_code: Optional filter by data source code

    Returns:
        List of config summaries
    """
    query = db.query(IngestionConfig)

    if data_source_code:
        source = db.query(DataSource).filter_by(source_code=data_source_code).first()
        if source:
            query = query.filter(IngestionConfig.data_source_id == source.id)

    configs = query.order_by(
        IngestionConfig.data_source_id,
        IngestionConfig.processing_order
    ).all()

    result = []
    for config in configs:
        source = db.query(DataSource).filter_by(id=config.data_source_id).first()
        result.append({
            "id": config.id,
            "name": config.name,
            "description": config.description,
            "data_source": source.source_code if source else "unknown",
            "source_parquet_name": config.source_parquet_name,
            "target_table_name": config.target_table_name,
            "primary_key_columns": json.loads(config.primary_key_columns),
            "version_strategy": config.version_strategy,
            "processing_order": config.processing_order,
            "is_active": config.is_active,
            "field_mappings_count": len(config.field_mappings),
        })

    return result


def get_parquet_files_for_batch(db: Session, batch_id: int) -> List[Dict]:
    """Get list of parquet files available for a batch.

    Args:
        db: Database session
        batch_id: The upload batch ID

    Returns:
        List of dicts with parquet file info
    """
    batch = db.query(UploadBatch).filter_by(id=batch_id).first()
    if not batch:
        return []

    source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
    if not source:
        return []

    preprocessed_path = storage.get_preprocessed_batch_path(batch.upload_id, source.source_code)

    if not preprocessed_path.exists():
        return []

    files = []
    for parquet_file in preprocessed_path.glob("*.parquet"):
        stat = parquet_file.stat()
        files.append({
            "filename": parquet_file.name,
            "path": str(parquet_file),
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        })

    return sorted(files, key=lambda x: x["filename"])
