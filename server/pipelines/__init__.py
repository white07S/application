"""Pipelines module — data upload, ingestion, and processing.

Domain packages:
    controls: Controls data (upload, model runners, ingestion, readiness)
    orgs: Organizational chart hierarchies (function, location, consolidated)
    risks: Risk theme taxonomies and themes

Shared modules:
    schema: SQLAlchemy table definitions + Alembic migration support
    api: Job tracking utilities
    processing: Batch listing with readiness status
    storage: File path helpers and processing lock
    upload_tracker: Upload ID sequence generation
"""
