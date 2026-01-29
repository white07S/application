"""Ingestion engine for loading parquet data into data layer tables.

Delta detection is based on `last_modified_on` timestamp comparison (NOT hash).
Versioning creates new records when data changes, marking old versions as non-current.
"""
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from server.database.models.data_layer import (
    # Controls
    DLControl,
    DLControlHierarchy,
    DLControlMetadata,
    DLControlRiskTheme,
    DLControlCategoryFlag,
    DLControlSoxAssertion,
    DLControlRelatedFunction,
    DLControlRelatedLocation,
    # Issues
    DLIssue,
    DLIssueHierarchy,
    DLIssueAudit,
    DLIssueRiskTheme,
    DLIssueRelatedFunction,
    DLIssueRelatedLocation,
    DLIssueControl,
    DLIssueRelatedIssue,
    # Actions
    DLIssueAction,
    DLIssueActionHierarchy,
)
from server.database.models.pipeline import RecordProcessingLog
from server.database.models.pipeline import PipelineRun
from server.logging_config import get_logger

logger = get_logger(name=__name__)


@dataclass
class IngestionStats:
    """Statistics for an ingestion run."""
    records_total: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    # PKs of records that were inserted or updated (for child table processing)
    updated_pks: List[str] = field(default_factory=list)


@dataclass
class TableConfig:
    """Configuration for a data layer table."""
    model: Type
    pk_column: str  # Primary key column in the parquet/model
    last_modified_column: Optional[str]  # Column for delta detection (None for child tables)
    is_main_table: bool  # True for main tables (controls, issues, actions)
    parent_pk_column: Optional[str] = None  # For child tables, the parent's PK column


# Table configuration mapping
# Maps target_table_name from IngestionConfig to table configuration
TABLE_CONFIGS: Dict[str, TableConfig] = {
    # Controls - Main table
    "dl_controls": TableConfig(
        model=DLControl,
        pk_column="control_id",
        last_modified_column="last_modified_on",
        is_main_table=True,
    ),
    # Controls - Child tables (linked by control_id)
    "dl_controls_hierarchy": TableConfig(
        model=DLControlHierarchy,
        pk_column="control_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="control_id",
    ),
    "dl_controls_metadata": TableConfig(
        model=DLControlMetadata,
        pk_column="control_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="control_id",
    ),
    "dl_controls_risk_themes": TableConfig(
        model=DLControlRiskTheme,
        pk_column="control_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="control_id",
    ),
    "dl_controls_category_flags": TableConfig(
        model=DLControlCategoryFlag,
        pk_column="control_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="control_id",
    ),
    "dl_controls_sox_assertions": TableConfig(
        model=DLControlSoxAssertion,
        pk_column="control_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="control_id",
    ),
    "dl_controls_related_functions": TableConfig(
        model=DLControlRelatedFunction,
        pk_column="control_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="control_id",
    ),
    "dl_controls_related_locations": TableConfig(
        model=DLControlRelatedLocation,
        pk_column="control_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="control_id",
    ),
    # Issues - Main table
    "dl_issues": TableConfig(
        model=DLIssue,
        pk_column="issue_id",
        last_modified_column="last_modified_on",
        is_main_table=True,
    ),
    # Issues - Child tables
    "dl_issues_hierarchy": TableConfig(
        model=DLIssueHierarchy,
        pk_column="issue_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="issue_id",
    ),
    "dl_issues_audit": TableConfig(
        model=DLIssueAudit,
        pk_column="issue_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="issue_id",
    ),
    "dl_issues_risk_themes": TableConfig(
        model=DLIssueRiskTheme,
        pk_column="issue_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="issue_id",
    ),
    "dl_issues_related_functions": TableConfig(
        model=DLIssueRelatedFunction,
        pk_column="issue_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="issue_id",
    ),
    "dl_issues_related_locations": TableConfig(
        model=DLIssueRelatedLocation,
        pk_column="issue_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="issue_id",
    ),
    "dl_issues_controls": TableConfig(
        model=DLIssueControl,
        pk_column="issue_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="issue_id",
    ),
    "dl_issues_related_issues": TableConfig(
        model=DLIssueRelatedIssue,
        pk_column="issue_id",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="issue_id",
    ),
    # Actions - Main table
    "dl_issues_actions": TableConfig(
        model=DLIssueAction,
        pk_column="composite_key",
        last_modified_column="last_modified_on",
        is_main_table=True,
    ),
    # Actions - Child table
    "dl_issues_actions_hierarchy": TableConfig(
        model=DLIssueActionHierarchy,
        pk_column="composite_key",
        last_modified_column=None,
        is_main_table=False,
        parent_pk_column="composite_key",
    ),
}


def detect_delta(
    db: Session,
    model: Type,
    pk_column: str,
    pk_value: str,
    incoming_last_modified: datetime,
) -> Tuple[str, Optional[Any]]:
    """Detect if a record needs to be inserted, updated, or skipped.

    Delta detection is based on `last_modified_on` comparison only.
    - If record not in DB → 'insert'
    - If last_modified_on matches → 'skip'
    - If last_modified_on differs → 'update'

    Args:
        db: Database session
        model: SQLAlchemy model class
        pk_column: Name of primary key column
        pk_value: Value of the primary key
        incoming_last_modified: The last_modified_on from incoming data

    Returns:
        Tuple of (operation, current_record)
        - operation: 'insert', 'update', or 'skip'
        - current_record: The current record if exists, else None
    """
    # Find current version
    current = db.query(model).filter(
        getattr(model, pk_column) == pk_value,
        model.is_current == True
    ).first()

    if not current:
        return 'insert', None

    # Compare last_modified_on timestamps
    current_modified = getattr(current, 'last_modified_on')

    # Normalize both to compare (handle timezone/format differences)
    if isinstance(incoming_last_modified, str):
        incoming_last_modified = pd.to_datetime(incoming_last_modified)
    if isinstance(current_modified, str):
        current_modified = pd.to_datetime(current_modified)

    # Convert to datetime if pandas Timestamp
    if hasattr(incoming_last_modified, 'to_pydatetime'):
        incoming_last_modified = incoming_last_modified.to_pydatetime()
    if hasattr(current_modified, 'to_pydatetime'):
        current_modified = current_modified.to_pydatetime()

    # Remove timezone info for comparison if present
    if incoming_last_modified and hasattr(incoming_last_modified, 'replace'):
        incoming_last_modified = incoming_last_modified.replace(tzinfo=None)
    if current_modified and hasattr(current_modified, 'replace'):
        current_modified = current_modified.replace(tzinfo=None)

    if current_modified == incoming_last_modified:
        return 'skip', current

    return 'update', current


def create_new_version(
    db: Session,
    model: Type,
    current_record: Optional[Any],
    record_data: Dict[str, Any],
    batch_id: int,
) -> Any:
    """Create a new version of a record.

    If current_record exists:
    - Mark it as is_current=False
    - Set updated_at to now (serves as version end time)
    - Create new record with version+1

    Args:
        db: Database session
        model: SQLAlchemy model class
        current_record: Existing current record (or None for new insert)
        record_data: Data for the new record
        batch_id: Upload batch ID

    Returns:
        The newly created record
    """
    now = datetime.utcnow()

    if current_record:
        # Mark current as non-current
        current_record.is_current = False
        if hasattr(current_record, "valid_to"):
            setattr(current_record, "valid_to", now)
        current_record.updated_at = now
        new_version = current_record.version + 1
    else:
        new_version = 1

    # Create new record
    new_record = model(
        **record_data,
        batch_id=batch_id,
        version=new_version,
        is_current=True,
        **({"valid_from": now} if hasattr(model, "valid_from") else {}),
        created_at=now,
        updated_at=now,
    )
    db.add(new_record)

    return new_record


def replace_child_records(
    db: Session,
    model: Type,
    parent_pk_column: str,
    parent_pk_value: str,
    new_records: List[Dict[str, Any]],
    batch_id: int,
) -> int:
    """Replace child records for a parent entity.

    Child tables don't have version tracking - when parent is updated,
    we mark old child records as non-current and insert new ones from the dump.

    Args:
        db: Database session
        model: SQLAlchemy model class for child table
        parent_pk_column: Column name linking to parent (e.g., 'control_id')
        parent_pk_value: Value of parent's primary key
        new_records: List of new child records from the dump
        batch_id: Upload batch ID

    Returns:
        Number of records inserted
    """
    now = datetime.utcnow()

    # Build update dict - only include updated_at if model has it
    update_dict = {'is_current': False}
    if hasattr(model, 'updated_at'):
        update_dict['updated_at'] = now
    if hasattr(model, 'valid_to'):
        update_dict['valid_to'] = now

    # Mark existing current child records as non-current
    db.query(model).filter(
        getattr(model, parent_pk_column) == parent_pk_value,
        model.is_current == True
    ).update(update_dict, synchronize_session=False)

    # Determine next version for this parent if version column exists
    new_version = None
    if hasattr(model, "version"):
        max_version = db.query(model).with_entities(model.version).filter(
            getattr(model, parent_pk_column) == parent_pk_value
        ).order_by(model.version.desc()).first()
        current_max = max_version[0] if max_version else 0
        new_version = current_max + 1

    # Insert new child records
    count = 0
    for record_data in new_records:
        extra_fields = {}
        if new_version is not None:
            extra_fields["version"] = new_version
        if hasattr(model, "valid_from"):
            extra_fields["valid_from"] = now
        record = model(
            **record_data,
            batch_id=batch_id,
            is_current=True,
            **extra_fields,
            created_at=now,
        )
        db.add(record)
        count += 1

    return count


def prepare_record_data(
    row: pd.Series,
    model: Type,
    exclude_columns: List[str] = None,
) -> Dict[str, Any]:
    """Prepare record data from a pandas row for insertion.

    Handles:
    - Column name mapping
    - NULL/NaN conversion
    - Type conversions (datetime, boolean)

    Args:
        row: Pandas Series representing a row
        model: SQLAlchemy model class
        exclude_columns: Columns to exclude (system columns)

    Returns:
        Dictionary of column->value for model creation
    """
    from sqlalchemy import DateTime
    from dateutil import parser as dateutil_parser

    if exclude_columns is None:
        exclude_columns = ['id', 'batch_id', 'version', 'is_current', 'created_at', 'updated_at', 'record_hash', 'valid_from', 'valid_to']

    # Get model column info (name -> type)
    model_columns = {c.name: c for c in model.__table__.columns}

    data = {}
    for col, value in row.items():
        # Skip excluded columns
        if col in exclude_columns:
            continue

        # Skip if column not in model
        if col not in model_columns:
            continue

        # Handle NaN/None
        if pd.isna(value):
            data[col] = None
        # Handle numpy types
        elif hasattr(value, 'item'):
            data[col] = value.item()
        # Handle pandas Timestamp
        elif isinstance(value, pd.Timestamp):
            data[col] = value.to_pydatetime()
        # Handle string datetime for DateTime columns
        elif isinstance(value, str) and isinstance(model_columns[col].type, DateTime):
            try:
                data[col] = dateutil_parser.parse(value)
            except (ValueError, TypeError):
                data[col] = None
        else:
            data[col] = value

    return data


def ingest_main_table(
    db: Session,
    parquet_path: Path,
    table_config: TableConfig,
    batch_id: int,
    pipeline_run_id: int,
    checkpoint_record_id: Optional[str] = None,
) -> IngestionStats:
    """Ingest a main table (controls, issues, or actions) from parquet.

    Processes records one at a time with per-record commits.
    Supports checkpoint-based resume.

    Args:
        db: Database session
        parquet_path: Path to parquet file
        table_config: Configuration for this table
        batch_id: Upload batch ID
        pipeline_run_id: Pipeline run ID for logging
        checkpoint_record_id: Resume from after this record ID

    Returns:
        IngestionStats with counts
    """
    stats = IngestionStats()

    # Read parquet file
    df = pd.read_parquet(parquet_path)
    stats.records_total = len(df)

    # Track pipeline run for checkpointing
    pipeline_run = db.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
    if pipeline_run:
        pipeline_run.records_total = stats.records_total

    logger.info(
        "Starting main table ingestion: table=%s, records=%d, checkpoint=%s",
        table_config.model.__tablename__,
        stats.records_total,
        checkpoint_record_id,
    )

    # Resume handling - skip until checkpoint
    skip_until_found = checkpoint_record_id is not None

    for idx, row in df.iterrows():
        pk_value = row[table_config.pk_column]

        # Resume logic: skip records until we find the checkpoint
        if skip_until_found:
            if str(pk_value) == str(checkpoint_record_id):
                skip_until_found = False
            continue

        try:
            # Get last_modified_on from row
            last_modified = row.get(table_config.last_modified_column)
            if pd.isna(last_modified):
                raise ValueError(f"Missing last_modified_on for {pk_value}")

            # Detect delta
            operation, current_record = detect_delta(
                db,
                table_config.model,
                table_config.pk_column,
                pk_value,
                last_modified,
            )

            if operation == 'skip':
                stats.records_skipped += 1
                _log_record_processing(db, pipeline_run_id, pk_value, 'skip')
            else:
                # Prepare record data
                record_data = prepare_record_data(row, table_config.model)

                # Create new version
                new_record = create_new_version(
                    db,
                    table_config.model,
                    current_record,
                    record_data,
                    batch_id,
                )

                # Track this PK as updated (for child table processing)
                stats.updated_pks.append(str(pk_value))

                if operation == 'insert':
                    stats.records_inserted += 1
                    _log_record_processing(db, pipeline_run_id, pk_value, 'insert', new_record.version)
                else:
                    stats.records_updated += 1
                    _log_record_processing(db, pipeline_run_id, pk_value, 'update', new_record.version)

            # Commit after each record (atomic unit)
            db.commit()
            if pipeline_run:
                pipeline_run.last_processed_record_id = str(pk_value)
                pipeline_run.last_checkpoint_at = datetime.utcnow()
                pipeline_run.records_processed += 1
                pipeline_run.records_inserted = stats.records_inserted
                pipeline_run.records_updated = stats.records_updated
                pipeline_run.records_skipped = stats.records_skipped
                db.flush()

        except Exception as e:
            db.rollback()
            stats.records_failed += 1
            logger.error(
                "Failed to process record: pk=%s, error=%s",
                pk_value, str(e)
            )
            _log_record_processing(db, pipeline_run_id, pk_value, 'fail', error=str(e))
            if pipeline_run:
                pipeline_run.records_failed += 1
            db.commit()

    logger.info(
        "Completed main table ingestion: table=%s, inserted=%d, updated=%d, skipped=%d, failed=%d",
        table_config.model.__tablename__,
        stats.records_inserted,
        stats.records_updated,
        stats.records_skipped,
        stats.records_failed,
    )

    return stats


def ingest_child_table(
    db: Session,
    parquet_path: Path,
    table_config: TableConfig,
    batch_id: int,
    parent_pks_updated: set,
) -> IngestionStats:
    """Ingest a child table from parquet.

    Child tables are replaced entirely when their parent is updated.
    Only processes records for parents that were inserted/updated.

    Args:
        db: Database session
        parquet_path: Path to parquet file
        table_config: Configuration for this table
        batch_id: Upload batch ID
        parent_pks_updated: Set of parent PKs that were inserted/updated

    Returns:
        IngestionStats with counts
    """
    stats = IngestionStats()

    # Read parquet file
    df = pd.read_parquet(parquet_path)
    stats.records_total = len(df)

    logger.info(
        "Starting child table ingestion: table=%s, records=%d, parents_updated=%d",
        table_config.model.__tablename__,
        stats.records_total,
        len(parent_pks_updated),
    )

    # Group records by parent PK
    parent_pk_col = table_config.parent_pk_column
    grouped = df.groupby(parent_pk_col)

    for parent_pk, group_df in grouped:
        # Only process if parent was updated
        if str(parent_pk) not in parent_pks_updated:
            stats.records_skipped += len(group_df)
            continue

        try:
            # Prepare child records
            child_records = []
            for idx, row in group_df.iterrows():
                record_data = prepare_record_data(row, table_config.model)
                child_records.append(record_data)

            # Replace child records
            count = replace_child_records(
                db,
                table_config.model,
                parent_pk_col,
                parent_pk,
                child_records,
                batch_id,
            )

            stats.records_inserted += count
            db.commit()

        except Exception as e:
            db.rollback()
            stats.records_failed += len(group_df)
            logger.error(
                "Failed to process child records: parent_pk=%s, error=%s",
                parent_pk, str(e)
            )

    logger.info(
        "Completed child table ingestion: table=%s, inserted=%d, skipped=%d, failed=%d",
        table_config.model.__tablename__,
        stats.records_inserted,
        stats.records_skipped,
        stats.records_failed,
    )

    return stats


def _log_record_processing(
    db: Session,
    pipeline_run_id: int,
    record_id: str,
    operation: str,
    version: int = None,
    error: str = None,
):
    """Log a record processing event."""
    log = RecordProcessingLog(
        pipeline_run_id=pipeline_run_id,
        record_business_id=str(record_id),
        operation=operation,
        version_created=version,
        error_details=error,
    )
    db.add(log)


def get_table_config(target_table_name: str) -> Optional[TableConfig]:
    """Get table configuration by target table name."""
    return TABLE_CONFIGS.get(target_table_name)


# ============================================================================
# Single-record processing methods (for batch processor)
# ============================================================================

@dataclass
class RecordResult:
    """Result of processing a single record."""
    pk: str
    success: bool
    operation: str  # 'insert', 'update', 'skip', 'fail'
    version: Optional[int] = None
    error: Optional[str] = None
    new_record: Optional[Any] = None  # The created/updated record


def process_single_main_record(
    db: Session,
    pk_value: str,
    row_data: Dict[str, Any],
    table_config: TableConfig,
    batch_id: int,
) -> RecordResult:
    """Process a single main table record.

    This method does NOT commit - caller is responsible for committing the batch.

    Args:
        db: Database session
        pk_value: Primary key value
        row_data: Dict of column->value for the record
        table_config: Configuration for this table
        batch_id: Upload batch ID

    Returns:
        RecordResult with operation details
    """
    try:
        # Get last_modified_on from row
        last_modified = row_data.get(table_config.last_modified_column)
        if last_modified is None:
            raise ValueError(f"Missing {table_config.last_modified_column} for {pk_value}")

        # Detect delta
        operation, current_record = detect_delta(
            db,
            table_config.model,
            table_config.pk_column,
            pk_value,
            last_modified,
        )

        if operation == 'skip':
            return RecordResult(
                pk=str(pk_value),
                success=True,
                operation='skip',
            )

        # Create new version
        new_record = create_new_version(
            db,
            table_config.model,
            current_record,
            row_data,
            batch_id,
        )

        return RecordResult(
            pk=str(pk_value),
            success=True,
            operation=operation,
            version=new_record.version,
            new_record=new_record,
        )

    except Exception as e:
        return RecordResult(
            pk=str(pk_value),
            success=False,
            operation='fail',
            error=str(e),
        )


def process_single_record_children(
    db: Session,
    pk_value: str,
    child_data: Dict[str, List[Dict[str, Any]]],
    table_configs: Dict[str, TableConfig],
    batch_id: int,
) -> List[RecordResult]:
    """Process all child records for a single parent PK.

    This method does NOT commit - caller is responsible for committing the batch.

    Args:
        db: Database session
        pk_value: Parent primary key value
        child_data: Dict mapping child_table_name -> list of child record dicts
        table_configs: Dict mapping child_table_name -> TableConfig
        batch_id: Upload batch ID

    Returns:
        List of RecordResult (one per child table)
    """
    results = []

    for table_name, records in child_data.items():
        config = table_configs.get(table_name)
        if not config:
            results.append(RecordResult(
                pk=str(pk_value),
                success=False,
                operation='fail',
                error=f"Unknown child table: {table_name}",
            ))
            continue

        try:
            count = replace_child_records(
                db,
                config.model,
                config.parent_pk_column,
                pk_value,
                records,
                batch_id,
            )

            results.append(RecordResult(
                pk=str(pk_value),
                success=True,
                operation='insert',
                version=count,  # Using version field to store count
            ))

        except Exception as e:
            results.append(RecordResult(
                pk=str(pk_value),
                success=False,
                operation='fail',
                error=str(e),
            ))

    return results


def load_parquet_by_pk(
    parquet_path: Path,
    pk_column: str,
) -> Dict[str, pd.Series]:
    """Load parquet file and return dict mapping PK -> row data.

    Args:
        parquet_path: Path to parquet file
        pk_column: Column to use as key

    Returns:
        Dict mapping pk_value -> row Series
    """
    df = pd.read_parquet(parquet_path)
    result = {}
    for idx, row in df.iterrows():
        pk = str(row[pk_column])
        result[pk] = row
    return result


def load_child_parquet_by_pk(
    parquet_path: Path,
    pk_column: str,
    model: Type,
) -> Dict[str, List[Dict[str, Any]]]:
    """Load child parquet file and group by parent PK.

    Args:
        parquet_path: Path to parquet file
        pk_column: Parent PK column to group by
        model: SQLAlchemy model class

    Returns:
        Dict mapping pk_value -> list of prepared record dicts
    """
    if not parquet_path.exists():
        return {}

    df = pd.read_parquet(parquet_path)
    result: Dict[str, List[Dict[str, Any]]] = {}

    for idx, row in df.iterrows():
        pk = str(row[pk_column])
        record_data = prepare_record_data(row, model)
        if pk not in result:
            result[pk] = []
        result[pk].append(record_data)

    return result


def get_unique_pks(parquet_path: Path, pk_column: str) -> List[str]:
    """Get list of unique PKs from a parquet file.

    Args:
        parquet_path: Path to parquet file
        pk_column: Column containing primary keys

    Returns:
        List of unique PK values as strings
    """
    df = pd.read_parquet(parquet_path, columns=[pk_column])
    return df[pk_column].dropna().astype(str).unique().tolist()
