"""Controls domain — upload, ingestion, model runners, and readiness checks.

Submodules:
    api: FastAPI routers for upload (TUS), ingestion, and job status
    ingest: Ingestion service for loading controls into PostgreSQL + Qdrant
    model_runners: CLI scripts for running AI models (taxonomy, enrichment, clean_text, embeddings)
    upload: File processing — CSV splitting and mock JSONL generation
    schema: PostgreSQL table definitions for controls domain
    schema_validation: Pydantic models for JSONL validation
    readiness: Pre-ingestion readiness checker (verifies model outputs exist)
    qdrant_service: Qdrant embedding upsert/delete operations
"""
