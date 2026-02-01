"""Configuration settings for the application.

This module provides a centralized Settings class using Pydantic BaseSettings
for loading and validating environment variables.
"""

import os
from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Uses pydantic BaseSettings to automatically load from .env file
    and validate configuration values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # SurrealDB Configuration
    surrealdb_url: str = Field(
        default="ws://127.0.0.1:4132/rpc",
        description="SurrealDB WebSocket URL"
    )
    surrealdb_namespace: str = Field(
        default="nfr_connect",
        description="SurrealDB namespace"
    )
    surrealdb_database: str = Field(
        default="nfr_connect_db",
        description="SurrealDB database name"
    )
    surrealdb_user: str = Field(
        default="root",
        description="SurrealDB username"
    )
    surrealdb_pass: str = Field(
        default="root",
        description="SurrealDB password"
    )

    # Job Tracking SQLite
    job_tracking_db_path: Path = Field(
        default=Path("/Users/preetam/Develop/application/data_ingested/jobs/jobs.db"),
        description="Path to job tracking SQLite database"
    )

    # Data paths
    data_ingestion_path: Path = Field(
        default=Path("/Users/preetam/Develop/application/data_ingested"),
        description="Base path for data ingestion"
    )

    # Model output cache path (JSONL files)
    model_output_cache_path: Path = Field(
        default=Path("/Users/preetam/Develop/application/data_ingested/model_cache"),
        description="Path for model output JSONL cache files"
    )

    @property
    def job_tracking_db_dir(self) -> Path:
        """Get the directory containing the job tracking database."""
        return self.job_tracking_db_path.parent

    def ensure_job_tracking_dir(self) -> None:
        """Ensure the job tracking database directory exists."""
        self.job_tracking_db_dir.mkdir(parents=True, exist_ok=True)

    def ensure_model_cache_dir(self) -> None:
        """Ensure the model output cache directory exists."""
        self.model_output_cache_path.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance (singleton pattern).

    Returns:
        Settings instance loaded from environment variables.

    Example:
        from server.config import get_settings

        settings = get_settings()
        print(settings.surrealdb_url)
    """
    return Settings()


# Convenience instance for direct import
settings = get_settings()
