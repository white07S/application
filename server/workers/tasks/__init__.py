"""Celery tasks for background processing."""

from .ingestion import run_controls_ingestion_task

__all__ = ["run_controls_ingestion_task"]