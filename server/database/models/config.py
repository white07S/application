"""Config layer database models."""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .system import DataSource


class DatasetConfig(Base):
    """Model for dataset_config table.

    Stores configuration settings for each dataset/data source.
    """
    __tablename__ = "dataset_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), nullable=False)
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    is_locked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint on data_source_id and config_key
    __table_args__ = (UniqueConstraint('data_source_id', 'config_key', name='uq_dataset_config_source_key'),)

    # Relationships
    data_source: Mapped["DataSource"] = relationship("DataSource")

    def __repr__(self) -> str:
        return f"<DatasetConfig(id={self.id}, data_source_id={self.data_source_id}, config_key='{self.config_key}')>"


class ModelConfig(Base):
    """Model for model_config table.

    Stores ML/AI model configurations for different functions per data source.
    """
    __tablename__ = "model_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_function: Mapped[str] = mapped_column(String(100), nullable=False)  # 'nfr_taxonomy', 'enrichment', 'embeddings'
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), nullable=False)
    input_columns: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    output_schema: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    current_model_version: Mapped[str] = mapped_column(String(20), default="v1")
    is_active: Mapped[bool] = mapped_column(default=True)
    is_locked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint on model_function and data_source_id
    __table_args__ = (UniqueConstraint('model_function', 'data_source_id', name='uq_model_config_function_source'),)

    # Relationships
    data_source: Mapped["DataSource"] = relationship("DataSource")

    def __repr__(self) -> str:
        return f"<ModelConfig(id={self.id}, model_function='{self.model_function}', data_source_id={self.data_source_id})>"


class IngestionConfig(Base):
    """Configuration for ingesting parquet files into data layer tables.

    Each IngestionConfig defines:
    - Which parquet file (from validation) to read
    - Which data layer table to write to
    - Primary key columns for delta detection
    - Versioning strategy (snapshot or scd2)
    """
    __tablename__ = "ingestion_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), nullable=False)
    source_parquet_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    primary_key_columns: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    version_strategy: Mapped[str] = mapped_column(String(20), default="snapshot")  # snapshot or scd2
    processing_order: Mapped[int] = mapped_column(default=0)  # Order for processing within a data source
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, onupdate=datetime.utcnow)

    # Relationships
    data_source: Mapped["DataSource"] = relationship("DataSource")
    field_mappings: Mapped[List["IngestionFieldMapping"]] = relationship(
        "IngestionFieldMapping", back_populates="ingestion_config", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_ingestion_configs_data_source', 'data_source_id'),
        Index('idx_ingestion_configs_active', 'is_active'),
    )

    def __repr__(self) -> str:
        return f"<IngestionConfig(id={self.id}, name='{self.name}', target='{self.target_table_name}')>"


class IngestionFieldMapping(Base):
    """Column-level mapping from source parquet to target data layer table.

    Defines how each column in the parquet file maps to the data layer table,
    including data type, required status, and optional transformations.
    """
    __tablename__ = "ingestion_field_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingestion_config_id: Mapped[int] = mapped_column(ForeignKey("ingestion_configs.id"), nullable=False)
    source_column: Mapped[str] = mapped_column(String(100), nullable=False)
    target_column: Mapped[str] = mapped_column(String(100), nullable=False)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)  # string, int, float, bool, datetime
    is_required: Mapped[bool] = mapped_column(default=False)
    is_primary_key: Mapped[bool] = mapped_column(default=False)
    default_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transform_function: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    column_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    ingestion_config: Mapped["IngestionConfig"] = relationship("IngestionConfig", back_populates="field_mappings")

    __table_args__ = (
        Index('idx_field_mappings_config', 'ingestion_config_id'),
    )

    def __repr__(self) -> str:
        return f"<IngestionFieldMapping(id={self.id}, source='{self.source_column}', target='{self.target_column}')>"
