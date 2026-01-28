"""API endpoints for ingestion configuration management."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control
from server.database import get_db
from server.logging_config import get_logger

from ..config import service as config_service
from server.database import DataSource, DatasetConfig, ModelConfig

logger = get_logger(name=__name__)

router = APIRouter(prefix="/v2/config", tags=["Configuration"])


# ============== Response Models ==============

class FieldMappingResponse(BaseModel):
    """Response for field mapping."""
    id: int
    source_column: str
    target_column: str
    data_type: str
    is_required: bool
    is_primary_key: bool
    default_value: Optional[str]
    transform_function: Optional[str]


class IngestionConfigSummary(BaseModel):
    """Summary response for ingestion config."""
    id: int
    name: str
    description: Optional[str]
    data_source: str
    source_parquet_name: str
    target_table_name: str
    primary_key_columns: List[str]
    version_strategy: str
    processing_order: int
    is_active: bool
    field_mappings_count: int


class IngestionConfigDetail(BaseModel):
    """Detailed response for ingestion config with field mappings."""
    id: int
    name: str
    description: Optional[str]
    source_parquet_name: str
    target_table_name: str
    primary_key_columns: List[str]
    version_strategy: str
    processing_order: int
    is_active: bool
    field_mappings: List[FieldMappingResponse]


class IngestionConfigListResponse(BaseModel):
    """Response for list of ingestion configs."""
    configs: List[IngestionConfigSummary]
    total: int


class IngestionPlanItem(BaseModel):
    """Single item in an ingestion plan."""
    config_id: int
    config_name: str
    source_parquet_path: str
    target_table_name: str
    primary_key_columns: List[str]
    version_strategy: str
    processing_order: int


class IngestionPlanResponse(BaseModel):
    """Response for ingestion plan."""
    batch_id: int
    upload_id: str
    datasets: List[IngestionPlanItem]
    total: int


class ParquetFileInfo(BaseModel):
    """Info about a parquet file."""
    filename: str
    path: str
    size_bytes: int
    modified_at: float


class ParquetFilesResponse(BaseModel):
    """Response for parquet files list."""
    batch_id: int
    files: List[ParquetFileInfo]
    total: int


# ============== Endpoints ==============

@router.get("/ingestion", response_model=IngestionConfigListResponse)
async def list_ingestion_configs(
    data_source: Optional[str] = Query(None, description="Filter by data source (issues, controls, actions)"),
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    List all ingestion configurations.

    Returns the mapping configurations that define how parquet files
    from validation are ingested into data layer tables.

    - **data_source**: Optional filter by data source type
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    configs = config_service.list_all_configs(db, data_source)

    return IngestionConfigListResponse(
        configs=[IngestionConfigSummary(**c) for c in configs],
        total=len(configs)
    )


@router.get("/ingestion/{config_id}", response_model=IngestionConfigDetail)
async def get_ingestion_config(
    config_id: int,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    Get a specific ingestion configuration with field mappings.

    - **config_id**: The ingestion config ID
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    config = config_service.get_config_with_mappings(db, config_id)

    if not config:
        raise HTTPException(status_code=404, detail=f"Config {config_id} not found")

    return IngestionConfigDetail(**config)


@router.get("/ingestion/by-source/{data_source}", response_model=IngestionConfigListResponse)
async def get_configs_by_source(
    data_source: str,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    Get all ingestion configurations for a specific data source.

    - **data_source**: The data source code (issues, controls, actions)
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    if data_source not in ("issues", "controls", "actions"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid data source: {data_source}. Must be one of: issues, controls, actions"
        )

    configs = config_service.list_all_configs(db, data_source)

    return IngestionConfigListResponse(
        configs=[IngestionConfigSummary(**c) for c in configs],
        total=len(configs)
    )


@router.get("/ingestion-plan/{batch_id}", response_model=IngestionPlanResponse)
async def get_ingestion_plan(
    batch_id: int,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    Get the ingestion plan for a batch.

    Returns the list of datasets that will be ingested from a batch's
    validated parquet files, in processing order.

    - **batch_id**: The upload batch ID
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get batch info
    from server.database import UploadBatch
    batch = db.query(UploadBatch).filter_by(id=batch_id).first()

    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    if batch.status != "validated":
        raise HTTPException(
            status_code=400,
            detail=f"Batch {batch_id} is not validated (status: {batch.status})"
        )

    plan = config_service.get_ingestion_plan(db, batch_id)

    return IngestionPlanResponse(
        batch_id=batch_id,
        upload_id=batch.upload_id,
        datasets=[IngestionPlanItem(**item) for item in plan],
        total=len(plan)
    )


@router.get("/parquet-files/{batch_id}", response_model=ParquetFilesResponse)
async def get_parquet_files(
    batch_id: int,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    Get list of parquet files for a batch.

    Returns the parquet files generated by validation for this batch.

    - **batch_id**: The upload batch ID
    """
    access = await get_access_control(token)

    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    files = config_service.get_parquet_files_for_batch(db, batch_id)

    return ParquetFilesResponse(
        batch_id=batch_id,
        files=[ParquetFileInfo(**f) for f in files],
        total=len(files)
    )


# ============== Dataset Config Endpoints ==============

class DatasetConfigResponse(BaseModel):
    """Complete configuration for a data source."""
    data_source: str
    dataset_config: List[dict]
    ingestion_configs: List[dict]
    model_configs: List[dict]


@router.get("/dataset/{data_source}", response_model=DatasetConfigResponse)
async def get_dataset_config(
    data_source: str,
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
):
    """
    Get complete configuration for a data source.

    Returns central config including dataset, ingestion, and model configurations.

    - **data_source**: The data source code (issues, controls, actions)
    """
    access = await get_access_control(token)
    if not access.hasPipelinesIngestionAccess:
        raise HTTPException(status_code=403, detail="Access denied")

    if data_source not in ("issues", "controls", "actions"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid data source: {data_source}. Must be one of: issues, controls, actions"
        )

    source = db.query(DataSource).filter_by(source_code=data_source).first()
    if not source:
        raise HTTPException(status_code=404, detail=f"Data source {data_source} not found")

    dataset_config = config_service.list_all_configs(db, data_source_code=data_source)
    model_configs = [
        {
            "model_function": mc.model_function,
            "input_columns": mc.input_columns,
            "output_schema": mc.output_schema,
            "current_model_version": mc.current_model_version,
            "is_locked": mc.is_locked,
        }
        for mc in db.query(ModelConfig).filter_by(data_source_id=source.id).all()
    ]
    dataset_entries = [
        {"config_key": cfg.config_key, "config_value": cfg.config_value, "is_locked": cfg.is_locked}
        for cfg in db.query(DatasetConfig).filter_by(data_source_id=source.id).all()
    ]

    return DatasetConfigResponse(
        data_source=data_source,
        dataset_config=dataset_entries,
        ingestion_configs=dataset_config,
        model_configs=model_configs,
    )
