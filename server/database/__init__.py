"""Database module for the application.

This module provides SQLAlchemy database configuration and session management.
"""

from server.database.engine import (
    DATABASE_DIR,
    DATABASE_PATH,
    DATABASE_URL,
    SessionLocal,
    engine,
    get_db,
)
from server.database.models import (
    Base,
    DataSource,
    SchemaRegistry,
    DatasetConfig,
    ModelConfig,
    IngestionConfig,
    IngestionFieldMapping,
    UploadBatch,
    PipelineRun,
    RecordProcessingLog,
    TusUpload,
    ProcessingJob,
    # Data Layer - Controls
    DLControl,
    DLControlHierarchy,
    DLControlMetadata,
    DLControlRiskTheme,
    DLControlCategoryFlag,
    DLControlSoxAssertion,
    DLControlRelatedFunction,
    DLControlRelatedLocation,
    # Data Layer - Issues
    DLIssue,
    DLIssueHierarchy,
    DLIssueAudit,
    DLIssueRiskTheme,
    DLIssueRelatedFunction,
    DLIssueRelatedLocation,
    DLIssueControl,
    DLIssueRelatedIssue,
    # Data Layer - Actions
    DLIssueAction,
    DLIssueActionHierarchy,
    # Data Layer - Model Outputs
    DLControlModelOutput,
    DLIssueModelOutput,
)
from server.database.init_db import init_database

__all__ = [
    "DATABASE_DIR",
    "DATABASE_PATH",
    "DATABASE_URL",
    "SessionLocal",
    "engine",
    "get_db",
    "Base",
    "DataSource",
    "SchemaRegistry",
    "DatasetConfig",
    "ModelConfig",
    "IngestionConfig",
    "IngestionFieldMapping",
    "UploadBatch",
    "PipelineRun",
    "RecordProcessingLog",
    "TusUpload",
    "ProcessingJob",
    # Data Layer - Controls
    "DLControl",
    "DLControlHierarchy",
    "DLControlMetadata",
    "DLControlRiskTheme",
    "DLControlCategoryFlag",
    "DLControlSoxAssertion",
    "DLControlRelatedFunction",
    "DLControlRelatedLocation",
    # Data Layer - Issues
    "DLIssue",
    "DLIssueHierarchy",
    "DLIssueAudit",
    "DLIssueRiskTheme",
    "DLIssueRelatedFunction",
    "DLIssueRelatedLocation",
    "DLIssueControl",
    "DLIssueRelatedIssue",
    # Data Layer - Actions
    "DLIssueAction",
    "DLIssueActionHierarchy",
    # Data Layer - Model Outputs
    "DLControlModelOutput",
    "DLIssueModelOutput",
    "init_database",
]
