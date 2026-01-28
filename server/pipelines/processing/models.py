"""Model runner for executing ML model functions on ingested data.

Handles:
- Input hash computation for caching
- Version tracking
- Result storage in model output tables
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from server.database import (
    DataSource,
    DLControl,
    DLIssue,
    DLControlModelOutput,
    DLIssueModelOutput,
    ModelConfig,
    PipelineRun,
    UploadBatch,
)
from server.logging_config import get_logger

from . import model_functions

logger = get_logger(name=__name__)


class ModelRunStats:
    """Statistics for a model run."""

    def __init__(self):
        self.records_total: int = 0
        self.records_processed: int = 0
        self.records_cached: int = 0
        self.records_skipped: int = 0
        self.records_failed: int = 0


def run_models_for_batch(
    db: Session,
    batch: UploadBatch,
    pipeline_run: PipelineRun,
    progress_callback=None,
) -> Tuple[ModelRunStats, List[Dict[str, Any]]]:
    """Run all model functions for a batch.

    Processes records that were ingested in this batch through:
    1. NFR Taxonomy Classification
    2. Enrichment
    3. Embeddings

    Args:
        db: Database session
        batch: Upload batch being processed
        pipeline_run: Pipeline run record for tracking
        progress_callback: Optional callback(step_name, percent, stats)

    Returns:
        Tuple of (overall_stats, step_details)
    """
    source = db.query(DataSource).filter_by(id=batch.data_source_id).first()
    data_type = source.source_code if source else "unknown"

    overall_stats = ModelRunStats()
    step_details = []

    # Define model steps based on data type
    if data_type == "controls":
        steps = [
            ("NFR Taxonomy Classification", "nfr_taxonomy", _run_nfr_taxonomy_controls),
            ("Enrichment Processing", "enrichment", _run_enrichment_controls),
            ("Embeddings Generation", "embeddings", _run_embeddings_controls),
        ]
    elif data_type == "issues":
        steps = [
            ("NFR Taxonomy Classification", "nfr_taxonomy", _run_nfr_taxonomy_issues),
            ("Enrichment Processing", "enrichment", _run_enrichment_issues),
            ("Embeddings Generation", "embeddings", _run_embeddings_issues),
        ]
    else:
        logger.warning("No model steps defined for data type: {}", data_type)
        return overall_stats, step_details

    total_steps = len(steps)

    for i, (step_name, model_type, run_func) in enumerate(steps):
        step_num = i + 1
        if progress_callback:
            progress_callback(step_name, int((step_num / total_steps) * 100), overall_stats)

        step_run = PipelineRun(
            upload_batch_id=batch.id,
            pipeline_type=model_type,
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(step_run)
        db.flush()

        try:
            # Get model config
            model_config = db.query(ModelConfig).filter_by(
                model_function=model_type,
                data_source_id=batch.data_source_id,
            ).first()

            if not model_config:
                logger.warning("No model config for {}/{}", model_type, data_type)
                overall_stats.records_failed += 1
                step_details.append({
                    "step": step_num,
                    "name": step_name,
                    "type": model_type,
                    "skipped": True,
                    "reason": "No model config",
                    "completed_at": datetime.utcnow().isoformat(),
                    "pipeline_run_id": step_run.id,
                })
                step_run.status = "failed"
                step_run.completed_at = datetime.utcnow()
                step_run.error_details = "missing model config"
                db.flush()
                continue

            input_columns = json.loads(model_config.input_columns)
            model_version = model_config.current_model_version

            # Run the model function
            stats = run_func(
                db=db,
                batch_id=batch.id,
                pipeline_run_id=step_run.id,
                input_columns=input_columns,
                model_version=model_version,
            )

            overall_stats.records_total += stats.records_total
            overall_stats.records_processed += stats.records_processed
            overall_stats.records_cached += stats.records_cached
            overall_stats.records_skipped += stats.records_skipped
            overall_stats.records_failed += stats.records_failed

            step_details.append({
                "step": step_num,
                "name": step_name,
                "type": model_type,
                "records_processed": stats.records_processed,
                "records_cached": stats.records_cached,
                "records_skipped": stats.records_skipped,
                "completed_at": datetime.utcnow().isoformat(),
                "pipeline_run_id": step_run.id,
            })
            step_run.status = "success"
            step_run.completed_at = datetime.utcnow()
            step_run.records_total = stats.records_total
            step_run.records_processed = stats.records_processed
            step_run.records_skipped = stats.records_skipped
            step_run.records_failed = stats.records_failed
            db.flush()

        except Exception as e:
            logger.exception("Failed to run model step: {}", step_name)
            step_details.append({
                "step": step_num,
                "name": step_name,
                "type": model_type,
                "error": str(e),
                "completed_at": datetime.utcnow().isoformat(),
                "pipeline_run_id": step_run.id,
            })
            overall_stats.records_failed += 1
            step_run.status = "failed"
            step_run.completed_at = datetime.utcnow()
            step_run.error_details = str(e)
            db.flush()

    return overall_stats, step_details


def _run_nfr_taxonomy_controls(
    db: Session,
    batch_id: int,
    pipeline_run_id: int,
    input_columns: List[str],
    model_version: str,
) -> ModelRunStats:
    """Run NFR taxonomy classification on controls."""
    stats = ModelRunStats()

    # Get current controls from this batch
    controls = db.query(DLControl).filter(
        DLControl.batch_id == batch_id,
        DLControl.is_current == True,
    ).all()

    stats.records_total = len(controls)

    for control in controls:
        try:
            record = _control_to_dict(control)
            input_hash = model_functions.compute_input_hash(record, input_columns)

            # Check cache - if existing output has same hash + model version, skip
            existing = db.query(DLControlModelOutput).filter(
                DLControlModelOutput.control_id == control.control_id,
                DLControlModelOutput.is_current == True,
            ).first()

            if existing and existing.input_hash == input_hash and existing.model_version == model_version:
                stats.records_cached += 1
                continue

            # Run classification
            result = model_functions.nfr_taxonomy_classify(record, input_columns)

            if result is None:
                stats.records_skipped += 1
                continue

            # Mark existing as non-current with valid_to timestamp
            if existing:
                existing.is_current = False
                existing.valid_to = datetime.utcnow()

            # Create new output with input_hash for cache validation
            output = DLControlModelOutput(
                control_id=control.control_id,
                batch_id=batch_id,
                model_run_id=pipeline_run_id,
                is_current=True,
                input_hash=input_hash,
                output_version=(existing.output_version + 1) if existing else 1,
                model_version=model_version,
                risk_theme_option_1_id=result.get("risk_theme_option_1_id"),
                risk_theme_option_1=result.get("risk_theme_option_1"),
                risk_theme_option_1_reasoning=result.get("risk_theme_option_1_reasoning"),
                risk_theme_option_2_id=result.get("risk_theme_option_2_id"),
                risk_theme_option_2=result.get("risk_theme_option_2"),
                risk_theme_option_2_reasoning=result.get("risk_theme_option_2_reasoning"),
            )
            db.add(output)
            db.commit()

            stats.records_processed += 1

        except Exception as e:
            db.rollback()
            logger.error("Failed to process control {}: {}", control.control_id, e)
            stats.records_failed += 1

    return stats


def _run_enrichment_controls(
    db: Session,
    batch_id: int,
    pipeline_run_id: int,
    input_columns: List[str],
    model_version: str,
) -> ModelRunStats:
    """Run enrichment on controls."""
    stats = ModelRunStats()

    # Get current control model outputs (we update existing records)
    outputs = db.query(DLControlModelOutput).filter(
        DLControlModelOutput.batch_id == batch_id,
        DLControlModelOutput.model_run_id == pipeline_run_id,
        DLControlModelOutput.is_current == True,
    ).all()

    stats.records_total = len(outputs)

    for output in outputs:
        try:
            # Get the control record
            control = db.query(DLControl).filter(
                DLControl.control_id == output.control_id,
                DLControl.is_current == True,
            ).first()

            if not control:
                stats.records_skipped += 1
                continue

            record = _control_to_dict(control)

            # Run enrichment
            result = model_functions.enrichment_control(record, input_columns)

            if result is None:
                stats.records_skipped += 1
                continue

            # Update output with enrichment results
            output.control_written_as_issue = result.get("control_written_as_issue")
            output.control_summary = result.get("control_summary")
            output.control_complexity_score = result.get("control_complexity_score")
            db.commit()

            stats.records_processed += 1

        except Exception as e:
            db.rollback()
            logger.error("Failed to enrich control {}: {}", output.control_id, e)
            stats.records_failed += 1

    return stats


def _run_embeddings_controls(
    db: Session,
    batch_id: int,
    pipeline_run_id: int,
    input_columns: List[str],
    model_version: str,
) -> ModelRunStats:
    """Run embeddings on controls."""
    stats = ModelRunStats()

    # Get current control model outputs
    outputs = db.query(DLControlModelOutput).filter(
        DLControlModelOutput.batch_id == batch_id,
        DLControlModelOutput.model_run_id == pipeline_run_id,
        DLControlModelOutput.is_current == True,
    ).all()

    stats.records_total = len(outputs)

    for output in outputs:
        try:
            # Get the control record
            control = db.query(DLControl).filter(
                DLControl.control_id == output.control_id,
                DLControl.is_current == True,
            ).first()

            if not control:
                stats.records_skipped += 1
                continue

            record = _control_to_dict(control)

            # Also include enrichment output for embedding
            if output.control_written_as_issue:
                record["control_written_as_issue"] = output.control_written_as_issue
            if output.control_summary:
                record["control_summary"] = output.control_summary
            if output.control_complexity_score is not None:
                record["control_complexity_score"] = output.control_complexity_score

            # Generate embedding
            embedding = model_functions.generate_embedding(record, input_columns)

            if embedding is None:
                stats.records_skipped += 1
                continue

            # Update output with embedding
            output.embedding_vector = embedding
            db.commit()

            stats.records_processed += 1

        except Exception as e:
            db.rollback()
            logger.error("Failed to generate embedding for control {}: {}", output.control_id, e)
            stats.records_failed += 1

    return stats


def _run_nfr_taxonomy_issues(
    db: Session,
    batch_id: int,
    pipeline_run_id: int,
    input_columns: List[str],
    model_version: str,
) -> ModelRunStats:
    """Run NFR taxonomy classification on issues."""
    stats = ModelRunStats()

    # Get current issues from this batch
    issues = db.query(DLIssue).filter(
        DLIssue.batch_id == batch_id,
        DLIssue.is_current == True,
    ).all()

    stats.records_total = len(issues)

    for issue in issues:
        try:
            record = _issue_to_dict(issue)
            input_hash = model_functions.compute_input_hash(record, input_columns)

            # Check for existing output - if same hash + model version, skip (cached)
            existing = db.query(DLIssueModelOutput).filter(
                DLIssueModelOutput.issue_id == issue.issue_id,
                DLIssueModelOutput.is_current == True,
            ).first()

            if existing and existing.input_hash == input_hash and existing.model_version == model_version:
                stats.records_cached += 1
                continue

            # Run classification
            result = model_functions.nfr_taxonomy_classify(record, input_columns)

            if result is None:
                stats.records_skipped += 1
                continue

            # Mark existing as non-current with valid_to timestamp
            if existing:
                existing.is_current = False
                existing.valid_to = datetime.utcnow()

            # Create new output with input_hash for cache validation
            output = DLIssueModelOutput(
                issue_id=issue.issue_id,
                batch_id=batch_id,
                model_run_id=pipeline_run_id,
                is_current=True,
                input_hash=input_hash,
                output_version=(existing.output_version + 1) if existing else 1,
                model_version=model_version,
                risk_theme_option_1_id=result.get("risk_theme_option_1_id"),
                risk_theme_option_1=result.get("risk_theme_option_1"),
                risk_theme_option_1_reasoning=result.get("risk_theme_option_1_reasoning"),
                risk_theme_option_2_id=result.get("risk_theme_option_2_id"),
                risk_theme_option_2=result.get("risk_theme_option_2"),
                risk_theme_option_2_reasoning=result.get("risk_theme_option_2_reasoning"),
            )
            db.add(output)
            db.commit()

            stats.records_processed += 1

        except Exception as e:
            db.rollback()
            logger.error("Failed to process issue {}: {}", issue.issue_id, e)
            stats.records_failed += 1

    return stats


def _run_enrichment_issues(
    db: Session,
    batch_id: int,
    pipeline_run_id: int,
    input_columns: List[str],
    model_version: str,
) -> ModelRunStats:
    """Run enrichment on issues."""
    stats = ModelRunStats()

    # Get current issue model outputs
    outputs = db.query(DLIssueModelOutput).filter(
        DLIssueModelOutput.batch_id == batch_id,
        DLIssueModelOutput.model_run_id == pipeline_run_id,
        DLIssueModelOutput.is_current == True,
    ).all()

    stats.records_total = len(outputs)

    for output in outputs:
        try:
            # Get the issue record
            issue = db.query(DLIssue).filter(
                DLIssue.issue_id == output.issue_id,
                DLIssue.is_current == True,
            ).first()

            if not issue:
                stats.records_skipped += 1
                continue

            record = _issue_to_dict(issue)

            # Run enrichment
            result = model_functions.enrichment_issue(record, input_columns)

            if result is None:
                stats.records_skipped += 1
                continue

            # Update output with enrichment results
            output.issue_summary = result.get("issue_summary")
            output.recommended_actions = result.get("recommended_actions")
            output.severity_assessment = result.get("severity_assessment")
            db.commit()

            stats.records_processed += 1

        except Exception as e:
            db.rollback()
            logger.error("Failed to enrich issue {}: {}", output.issue_id, e)
            stats.records_failed += 1

    return stats


def _run_embeddings_issues(
    db: Session,
    batch_id: int,
    pipeline_run_id: int,
    input_columns: List[str],
    model_version: str,
) -> ModelRunStats:
    """Run embeddings on issues."""
    stats = ModelRunStats()

    # Get current issue model outputs
    outputs = db.query(DLIssueModelOutput).filter(
        DLIssueModelOutput.batch_id == batch_id,
        DLIssueModelOutput.model_run_id == pipeline_run_id,
        DLIssueModelOutput.is_current == True,
    ).all()

    stats.records_total = len(outputs)

    for output in outputs:
        try:
            # Get the issue record
            issue = db.query(DLIssue).filter(
                DLIssue.issue_id == output.issue_id,
                DLIssue.is_current == True,
            ).first()

            if not issue:
                stats.records_skipped += 1
                continue

            record = _issue_to_dict(issue)
            # Include enrichment outputs if present so embeddings can leverage them
            if output.issue_summary:
                record["issue_summary"] = output.issue_summary
            if output.recommended_actions:
                record["recommended_actions"] = output.recommended_actions
            if output.severity_assessment:
                record["severity_assessment"] = output.severity_assessment

            # Generate embedding
            embedding = model_functions.generate_embedding(record, input_columns)

            if embedding is None:
                stats.records_skipped += 1
                continue

            # Update output with embedding
            output.embedding_vector = embedding
            db.commit()

            stats.records_processed += 1

        except Exception as e:
            db.rollback()
            logger.error("Failed to generate embedding for issue {}: {}", output.issue_id, e)
            stats.records_failed += 1

    return stats


def _control_to_dict(control: DLControl) -> Dict[str, Any]:
    """Convert DLControl model to dictionary."""
    return {
        "control_id": control.control_id,
        "control_title": control.control_title,
        "control_description": control.control_description,
        "preventative_detective": control.preventative_detective,
        "manual_automated": control.manual_automated,
        "execution_frequency": control.execution_frequency,
        "control_status": control.control_status,
    }


def _issue_to_dict(issue: DLIssue) -> Dict[str, Any]:
    """Convert DLIssue model to dictionary."""
    return {
        "issue_id": issue.issue_id,
        "issue_title": issue.issue_title,
        "issue_type": issue.issue_type,
        "control_deficiency": issue.control_deficiency,
        "root_cause": issue.root_cause,
        "symptoms": issue.symptoms,
        "risk_description": issue.risk_description,
        "issue_status": issue.issue_status,
        "severity_rating": issue.severity_rating,
    }
