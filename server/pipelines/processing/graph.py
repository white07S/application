"""Graph-driven pipeline runner.

Orchestrates batch processing for data ingestion and model execution
using configuration-driven graph approach.
"""
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
from sqlalchemy.orm import Session

from server.database import DataSource, UploadBatch, PipelineRun
from server.database.models.pipeline import RecordProcessingLog
from server.logging_config import get_logger

from ..config.loader import ConfigLoader, DatasetConfig, GraphConfig
from .tracker import TransactionTracker
from .batch import BatchProcessor, BatchResult, create_batch_processor
from . import ingestion
from .. import storage

logger = get_logger(name=__name__)


@dataclass
class PipelineStats:
    """Statistics for a complete pipeline run."""
    records_total: int = 0
    records_processed: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    batches_total: int = 0
    batches_completed: int = 0
    duration_seconds: float = 0.0


ProgressCallback = Callable[[str, int, Dict[str, Any]], None]


class GraphRunner:
    """Runs the configured pipeline graph for a batch.

    Key features:
    - Loads configuration from JSON config files
    - Processes records in configurable batch sizes
    - Parallel processing within each batch
    - Progress reporting via callback
    - Failure file generation for failed records
    """

    def __init__(self, data_source: str, graph_token: Optional[str] = None):
        """Initialize the graph runner.

        Args:
            data_source: One of 'issues', 'controls', 'actions'
            graph_token: Microsoft Graph API token for model calls
        """
        self.data_source = data_source
        self.config = ConfigLoader.load(data_source)
        self.graph_config = self.config.graph
        self.graph_token = graph_token

    def run(
        self,
        db: Session,
        batch: UploadBatch,
        pipeline_run: PipelineRun,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Run the complete pipeline for a batch.

        Args:
            db: Database session
            batch: Upload batch to process
            pipeline_run: Pipeline run record for tracking
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with final statistics
        """
        start_time = time.time()
        stats = PipelineStats()

        # Load data from parquet files
        logger.info("Loading parquet data for {} batch {}", self.data_source, batch.upload_id)
        preprocessed_path = storage.get_preprocessed_batch_path(batch.upload_id, self.data_source)

        # Load main table data
        main_parquet = self.graph_config.parquet_mapping.get(self.graph_config.main_table)
        main_path = preprocessed_path / main_parquet

        if not main_path.exists():
            raise FileNotFoundError(f"Main parquet file not found: {main_path}")

        main_data = ingestion.load_parquet_by_pk(
            main_path,
            self.graph_config.primary_key,
        )
        all_pks = list(main_data.keys())
        stats.records_total = len(all_pks)

        logger.info("Loaded {} records from main parquet", stats.records_total)

        # Load child table data
        child_data: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for child_table in self.graph_config.child_tables:
            child_parquet = self.graph_config.parquet_mapping.get(child_table)
            if not child_parquet:
                continue

            child_path = preprocessed_path / child_parquet
            child_config = ingestion.get_table_config(child_table)
            if child_config:
                child_data[child_table] = ingestion.load_child_parquet_by_pk(
                    child_path,
                    child_config.parent_pk_column,
                    child_config.model,
                )
                logger.debug("Loaded child data for {}: {} parents", child_table, len(child_data[child_table]))

        # Update pipeline run
        pipeline_run.records_total = stats.records_total
        pipeline_run.status = "running"
        pipeline_run.started_at = datetime.utcnow()
        db.flush()

        # Create batch processor and tracker
        processor, tracker = create_batch_processor(
            config=self.config,
            db=db,
            batch_id=batch.id,
            pipeline_run_id=pipeline_run.id,
            graph_token=self.graph_token,
        )

        # Set up progress tracking
        def on_progress(progress: Dict[str, Any]) -> None:
            if progress_callback:
                # Use tracker's real-time values for progress display
                tracker_processed = progress.get("records_processed", 0)
                tracker_failed = progress.get("records_failed", 0)

                # Calculate percentage based on tracker's real-time progress
                tracker_done = tracker_processed + tracker_failed
                percent = int((tracker_done / stats.records_total) * 100) if stats.records_total > 0 else 0

                # Current batch number
                current_batch = stats.batches_completed + 1

                progress_callback(
                    f"Processing batch {current_batch}/{stats.batches_total}",
                    percent,
                    {
                        "records_total": stats.records_total,
                        # Use tracker's real-time processed count for immediate feedback
                        "records_processed": tracker_processed,
                        # Use stats for inserted/updated (only known after batch completion)
                        "records_inserted": stats.records_inserted,
                        "records_updated": stats.records_updated,
                        "records_failed": tracker_failed,
                        "batches_total": stats.batches_total,
                        "batches_completed": stats.batches_completed,
                    },
                )

        tracker.set_progress_callback(on_progress)

        # Split into batches
        batch_size = self.graph_config.batch_size
        pk_batches = [all_pks[i:i + batch_size] for i in range(0, len(all_pks), batch_size)]
        stats.batches_total = len(pk_batches)

        logger.info("Processing {} records in {} batches (batch_size={})",
                    stats.records_total, stats.batches_total, batch_size)

        # Process each batch
        for batch_idx, pk_batch in enumerate(pk_batches):
            logger.info("Processing batch {}/{} with {} records",
                        batch_idx + 1, stats.batches_total, len(pk_batch))

            try:
                result = processor.process_batch(
                    pks=pk_batch,
                    main_data=main_data,
                    child_data=child_data,
                )

                # Update stats
                stats.records_processed += result.successful_records + result.skipped_records
                stats.records_inserted += result.new_records
                stats.records_updated += result.updated_records
                stats.records_skipped += result.skipped_records
                stats.records_failed += result.failed_records
                stats.batches_completed += 1

                # Update pipeline run
                pipeline_run.records_processed = stats.records_processed
                pipeline_run.records_inserted = stats.records_inserted
                pipeline_run.records_updated = stats.records_updated
                pipeline_run.records_skipped = stats.records_skipped
                pipeline_run.records_failed = stats.records_failed
                pipeline_run.last_checkpoint_at = datetime.utcnow()
                db.flush()

                logger.info(
                    "Batch {} complete: {} success, {} failed, {} skipped",
                    batch_idx + 1, result.successful_records,
                    result.failed_records, result.skipped_records
                )

            except Exception as e:
                logger.exception("Batch {} failed: {}", batch_idx + 1, e)
                stats.records_failed += len(pk_batch)
                db.rollback()

        # Generate failure file if any failures
        if stats.records_failed > 0:
            failure_path = storage.get_preprocessed_batch_path(batch.upload_id, self.data_source)
            tracker.write_failure_file(batch.upload_id, failure_path)

        # Final stats
        stats.duration_seconds = time.time() - start_time

        logger.info(
            "Pipeline complete for {} batch {}: total={}, processed={}, "
            "inserted={}, updated={}, skipped={}, failed={}, duration={:.1f}s",
            self.data_source, batch.upload_id,
            stats.records_total, stats.records_processed,
            stats.records_inserted, stats.records_updated,
            stats.records_skipped, stats.records_failed,
            stats.duration_seconds,
        )

        return {
            "records_total": stats.records_total,
            "records_processed": stats.records_processed,
            "records_inserted": stats.records_inserted,
            "records_updated": stats.records_updated,
            "records_skipped": stats.records_skipped,
            "records_failed": stats.records_failed,
            "batches_total": stats.batches_total,
            "batches_completed": stats.batches_completed,
            "duration_seconds": stats.duration_seconds,
        }


def run_graph_for_batch(
    db: Session,
    batch: UploadBatch,
    pipeline_run: PipelineRun,
    progress_callback: Optional[ProgressCallback] = None,
    graph_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the pipeline graph for a batch.

    This is the main entry point called by processing_service.

    Args:
        db: Database session
        batch: Upload batch to process
        pipeline_run: Pipeline run record for tracking
        progress_callback: Optional callback for progress updates
        graph_token: Microsoft Graph API token for model calls

    Returns:
        Dict with final statistics
    """
    # Get data source from batch
    data_source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
    if not data_source:
        raise ValueError(f"Data source not found for batch {batch.id}")

    data_type = data_source.source_code

    # Create and run graph runner
    runner = GraphRunner(data_type, graph_token=graph_token)
    return runner.run(
        db=db,
        batch=batch,
        pipeline_run=pipeline_run,
        progress_callback=progress_callback,
    )
