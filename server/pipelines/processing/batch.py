"""Batch processor for parallel record processing.

Processes records in configurable batches with parallel execution,
retry logic, and transaction tracking.
"""
import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from server.database import SessionLocal
from server.logging_config import get_logger

from ..config.loader import DatasetConfig, GraphConfig, StageConfig
from .tracker import TransactionTracker, TransactionStatus
from . import ingestion
from . import model_functions

logger = get_logger(name=__name__)


@dataclass
class StageResult:
    """Result of executing a single stage for a record."""
    pk: str
    stage: str
    success: bool
    operation: str = "complete"  # "complete", "skip", "fail"
    error: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None


@dataclass
class RecordContext:
    """Context data for processing a single record."""
    pk: str
    main_row: pd.Series
    main_data: Dict[str, Any]
    child_data: Dict[str, List[Dict[str, Any]]]
    model_outputs: Dict[str, Any] = field(default_factory=dict)
    operation: Optional[str] = None  # 'insert', 'update', 'skip'


@dataclass
class BatchResult:
    """Result of processing a batch of records."""
    batch_id: str
    total_records: int
    successful_records: int
    failed_records: int
    skipped_records: int
    new_records: int
    updated_records: int
    successful_pks: List[str]
    failed_pks: List[str]
    duration_seconds: float


class BatchProcessor:
    """Processes records in parallel batches with retry logic.

    Key features:
    - Parallel processing with ThreadPoolExecutor
    - Configurable batch size
    - Retry logic (up to max_retries per stage)
    - Transaction tracking per record
    - Batch commit after all records in batch succeed
    """

    def __init__(
        self,
        config: DatasetConfig,
        tracker: TransactionTracker,
        db: Session,
        batch_id: int,
        pipeline_run_id: int,
        graph_token: Optional[str] = None,
    ):
        self.config = config
        self.graph_config = config.graph
        self.models_config = config.models
        self.tracker = tracker
        self.db = db
        self.batch_id = batch_id
        self.pipeline_run_id = pipeline_run_id
        self.data_source = config.data_source
        self.graph_token = graph_token

        # Get table configs from ingestion
        self.main_table_config = ingestion.get_table_config(self.graph_config.main_table)
        self.child_table_configs = {
            name: ingestion.get_table_config(name)
            for name in self.graph_config.child_tables
        }

    def process_batch(
        self,
        pks: List[str],
        main_data: Dict[str, pd.Series],
        child_data: Dict[str, Dict[str, List[Dict[str, Any]]]],
    ) -> BatchResult:
        """Process a batch of records in parallel.

        Args:
            pks: List of primary keys to process
            main_data: Dict mapping pk -> row Series for main table
            child_data: Dict mapping child_table -> pk -> list of child records

        Returns:
            BatchResult with statistics
        """
        start_time = time.time()

        # Prepare records data for failure file
        records_data = {
            pk: main_data[pk].to_dict() if pk in main_data else {}
            for pk in pks
        }

        # Start batch in tracker
        batch_tx = self.tracker.start_batch(pks, records_data)

        # Create contexts for all records
        contexts: Dict[str, RecordContext] = {}
        for pk in pks:
            if pk not in main_data:
                self.tracker.fail_record(pk, "Missing main data", "data_load")
                continue

            row = main_data[pk]
            row_dict = ingestion.prepare_record_data(row, self.main_table_config.model)

            # Collect child data for this PK
            pk_child_data = {}
            for child_table, pk_children in child_data.items():
                if pk in pk_children:
                    pk_child_data[child_table] = pk_children[pk]

            contexts[pk] = RecordContext(
                pk=pk,
                main_row=row,
                main_data=row_dict,
                child_data=pk_child_data,
            )

        # Process records serially for SQLite compatibility
        # SQLite doesn't handle concurrent writes well, so we use single-threaded processing
        successful_pks = []
        failed_pks = []
        skipped_pks = []
        new_count = 0
        updated_count = 0

        # Use serial processing (max_workers=1) for SQLite database safety
        # Multi-threaded SQLite access causes "database is locked" and "bad parameter" errors
        max_workers = 1

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all records
            futures = {
                executor.submit(self._process_single_record, pk, ctx): pk
                for pk, ctx in contexts.items()
            }

            # Collect results
            for future in as_completed(futures):
                pk = futures[future]
                try:
                    result = future.result()
                    if result.success:
                        if result.operation == 'skip':
                            skipped_pks.append(pk)
                        else:
                            successful_pks.append(pk)
                            if result.operation == 'insert':
                                new_count += 1
                            elif result.operation == 'update':
                                updated_count += 1
                    else:
                        failed_pks.append(pk)
                except Exception as e:
                    logger.exception("Future failed for pk {}: {}", pk, e)
                    failed_pks.append(pk)
                    self.tracker.fail_record(pk, str(e), "future_exception")

        # Commit successful records if any
        if successful_pks or skipped_pks:
            try:
                self.db.commit()
                logger.info(
                    "Committed batch: {} successful, {} skipped, {} failed",
                    len(successful_pks), len(skipped_pks), len(failed_pks)
                )
            except Exception as e:
                logger.exception("Batch commit failed: {}", e)
                self.db.rollback()
                # Mark all as failed since commit failed
                for pk in successful_pks:
                    self.tracker.fail_record(pk, f"Commit failed: {e}", "commit")
                failed_pks.extend(successful_pks)
                successful_pks = []

        # Complete the batch
        self.tracker.complete_batch()

        duration = time.time() - start_time

        return BatchResult(
            batch_id=batch_tx.batch_id,
            total_records=len(pks),
            successful_records=len(successful_pks),
            failed_records=len(failed_pks),
            skipped_records=len(skipped_pks),
            new_records=new_count,
            updated_records=updated_count,
            successful_pks=successful_pks,
            failed_pks=failed_pks,
            duration_seconds=duration,
        )

    def _process_single_record(self, pk: str, ctx: RecordContext) -> StageResult:
        """Process a single record through all pipeline stages.

        This runs in a separate thread.

        Args:
            pk: Primary key
            ctx: Record context with data

        Returns:
            StageResult indicating overall success/failure
        """
        try:
            # Mark record as started
            self.tracker.start_record(pk)

            # Get stages in order
            stages = self.graph_config.stages

            for stage in stages:
                success = self._execute_stage(pk, ctx, stage)
                if not success:
                    return StageResult(
                        pk=pk,
                        stage=stage.name,
                        success=False,
                        operation="fail",
                        error=f"Stage {stage.name} failed after retries",
                    )

            # All stages completed
            self.tracker.complete_record(pk)

            return StageResult(
                pk=pk,
                stage="all",
                success=True,
                operation=ctx.operation or "complete",
            )

        except Exception as e:
            logger.exception("Record processing failed: pk={}", pk)
            self.tracker.fail_record(pk, str(e), "processing")
            return StageResult(
                pk=pk,
                stage="unknown",
                success=False,
                operation="fail",
                error=str(e),
            )

    def _execute_stage(self, pk: str, ctx: RecordContext, stage: StageConfig) -> bool:
        """Execute a single stage with retry logic.

        Args:
            pk: Primary key
            ctx: Record context
            stage: Stage configuration

        Returns:
            True if stage succeeded, False if failed after retries
        """
        max_retries = self.graph_config.max_retries

        for attempt in range(max_retries):
            try:
                self.tracker.start_sub_transaction(pk, stage.name)

                if stage.type == "ingestion":
                    result = self._execute_ingestion_stage(pk, ctx, stage)
                elif stage.type == "model":
                    result = self._execute_model_stage(pk, ctx, stage)
                else:
                    raise ValueError(f"Unknown stage type: {stage.type}")

                if result.success:
                    self.tracker.complete_sub_transaction(pk, stage.name, result.result_data)
                    return True
                else:
                    should_retry = self.tracker.fail_sub_transaction(pk, stage.name, result.error or "Unknown error")
                    if not should_retry:
                        return False
                    # Small delay before retry
                    time.sleep(0.1 * (attempt + 1))

            except Exception as e:
                logger.warning("Stage {} attempt {} failed for {}: {}", stage.name, attempt + 1, pk, e)
                should_retry = self.tracker.fail_sub_transaction(pk, stage.name, str(e))
                if not should_retry:
                    return False
                time.sleep(0.1 * (attempt + 1))

        return False

    def _execute_ingestion_stage(self, pk: str, ctx: RecordContext, stage: StageConfig) -> StageResult:
        """Execute an ingestion stage (insert main or children).

        Args:
            pk: Primary key
            ctx: Record context
            stage: Stage configuration

        Returns:
            StageResult
        """
        if stage.target == "main":
            # Process main table record
            result = ingestion.process_single_main_record(
                db=self.db,
                pk_value=pk,
                row_data=ctx.main_data,
                table_config=self.main_table_config,
                batch_id=self.batch_id,
            )

            # Store operation type in context
            ctx.operation = result.operation

            return StageResult(
                pk=pk,
                stage=stage.name,
                success=result.success,
                operation=result.operation,
                error=result.error,
            )

        elif stage.target == "children":
            # Skip if main record was skipped
            if ctx.operation == 'skip':
                return StageResult(
                    pk=pk,
                    stage=stage.name,
                    success=True,
                    operation="skip",
                )

            # Process child tables
            results = ingestion.process_single_record_children(
                db=self.db,
                pk_value=pk,
                child_data=ctx.child_data,
                table_configs=self.child_table_configs,
                batch_id=self.batch_id,
            )

            # Check if any failed
            failed = [r for r in results if not r.success]
            if failed:
                errors = "; ".join(r.error for r in failed if r.error)
                return StageResult(
                    pk=pk,
                    stage=stage.name,
                    success=False,
                    operation="fail",
                    error=errors,
                )

            return StageResult(
                pk=pk,
                stage=stage.name,
                success=True,
                operation="insert",
            )

        else:
            return StageResult(
                pk=pk,
                stage=stage.name,
                success=False,
                operation="fail",
                error=f"Unknown ingestion target: {stage.target}",
            )

    def _execute_model_stage(self, pk: str, ctx: RecordContext, stage: StageConfig) -> StageResult:
        """Execute a model processing stage.

        Args:
            pk: Primary key
            ctx: Record context
            stage: Stage configuration

        Returns:
            StageResult
        """
        # Skip model stages if record was skipped
        if ctx.operation == 'skip':
            return StageResult(
                pk=pk,
                stage=stage.name,
                success=True,
                operation="skip",
            )

        # Get model config
        model_config = getattr(self.models_config, stage.name, None)
        if not model_config or not model_config.enabled:
            return StageResult(
                pk=pk,
                stage=stage.name,
                success=True,
                operation="skip",
            )

        try:
            # Prepare input data
            if stage.source == "enrichment_output":
                # Use enrichment outputs as input
                input_data = ctx.model_outputs.get("enrichment", {})
                if not input_data:
                    logger.warning(
                        "Stage {} expects enrichment output but none available for pk={}. "
                        "Enrichment may have returned null or failed.",
                        stage.name, pk
                    )
            else:
                # Use main record data
                input_data = ctx.main_data

            # Get input columns
            input_cols = model_config.input_columns

            # Simulate model delay
            delay_range = model_config.mock_delay_seconds
            delay = random.uniform(delay_range[0], delay_range[1])
            time.sleep(delay)

            # Check null probability
            if random.random() < model_config.null_probability:
                return StageResult(
                    pk=pk,
                    stage=stage.name,
                    success=True,
                    operation="skip",  # Model returned NULL
                    result_data=None,
                )

            # Execute model function based on stage name
            # Pass graph_token for API calls (currently logged for debugging)
            if stage.name == "nfr_taxonomy":
                result = model_functions.nfr_taxonomy_classify(input_data, input_cols, graph_token=self.graph_token)
            elif stage.name == "enrichment":
                result = model_functions.enrichment_issue(input_data, input_cols, graph_token=self.graph_token)
            elif stage.name == "embeddings":
                result = model_functions.generate_embedding(input_data, input_cols, graph_token=self.graph_token)
            elif stage.name == "nested_embeddings":
                result = model_functions.generate_embedding(input_data, input_cols, graph_token=self.graph_token)
            else:
                result = None

            # Store result in context for downstream stages
            if result:
                ctx.model_outputs[stage.name] = result

            return StageResult(
                pk=pk,
                stage=stage.name,
                success=True,
                operation="complete",
                result_data=result,
            )

        except Exception as e:
            return StageResult(
                pk=pk,
                stage=stage.name,
                success=False,
                operation="fail",
                error=str(e),
            )


def create_batch_processor(
    config: DatasetConfig,
    db: Session,
    batch_id: int,
    pipeline_run_id: int,
    graph_token: Optional[str] = None,
) -> Tuple[BatchProcessor, TransactionTracker]:
    """Create a batch processor with associated transaction tracker.

    Args:
        config: Dataset configuration
        db: Database session
        batch_id: Upload batch ID
        pipeline_run_id: Pipeline run ID
        graph_token: Microsoft Graph API token for model calls

    Returns:
        Tuple of (BatchProcessor, TransactionTracker)
    """
    tracker = TransactionTracker(
        batch_size=config.graph.batch_size,
        max_retries=config.graph.max_retries,
    )

    processor = BatchProcessor(
        config=config,
        tracker=tracker,
        db=db,
        batch_id=batch_id,
        pipeline_run_id=pipeline_run_id,
        graph_token=graph_token,
    )

    return processor, tracker
