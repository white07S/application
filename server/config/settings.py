"""Unified configuration settings for the application.

This module provides a centralized Settings class using Pydantic BaseSettings
for loading and validating all environment variables.

All configuration should be accessed through this module:
    from server.config.settings import get_settings
    settings = get_settings()
"""

import os
from pathlib import Path
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Compute project root from this file's location
_CONFIG_DIR = Path(__file__).resolve().parent
_SERVER_DIR = _CONFIG_DIR.parent
PROJECT_ROOT = _SERVER_DIR.parent


def _split_csv(value: str) -> List[str]:
    """Split a comma-separated string into a list."""
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Uses pydantic BaseSettings to automatically load from .env file
    and validate configuration values.

    Environment variables can be set in .env file or system environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==================== Auth Settings (Microsoft Azure AD) ====================
    tenant_id: str = Field(
        description="Azure AD Tenant ID"
    )
    client_id: str = Field(
        description="Azure AD Application (Client) ID"
    )
    client_secret: str = Field(
        description="Azure AD Client Secret"
    )
    graph_scopes: str = Field(
        default="",
        description="Comma-separated list of Microsoft Graph scopes"
    )
    group_chat_access: str = Field(
        description="Azure AD Group ID for chat access"
    )
    group_dashboard_access: str = Field(
        description="Azure AD Group ID for dashboard access"
    )
    group_pipelines_ingestion_access: str = Field(
        description="Azure AD Group ID for pipelines ingestion access"
    )
    group_pipelines_admin_access: str = Field(
        default="ad51a2ff-5627-45c1-882f-659a424bb87c",
        description="Azure AD Group ID for pipelines admin access"
    )

    # ==================== SurrealDB Configuration ====================
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

    # ==================== Data Paths ====================
    data_ingestion_path: Path = Field(
        default=None,
        description="Base path for data ingestion"
    )

    # ==================== Server Configuration ====================
    allowed_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins"
    )
    uvicorn_host: str = Field(
        default="0.0.0.0",
        description="Uvicorn server host"
    )
    uvicorn_port: int = Field(
        default=8000,
        description="Uvicorn server port"
    )

    @field_validator('data_ingestion_path', mode='before')
    @classmethod
    def set_default_data_path(cls, v):
        """Set default data ingestion path relative to project root."""
        if v is None:
            return PROJECT_ROOT / "data_ingested"
        return Path(v)

    # ==================== Computed Properties ====================

    @property
    def authority(self) -> str:
        """Azure AD authority URL."""
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def graph_scopes_list(self) -> List[str]:
        """Get graph scopes as a list."""
        return _split_csv(self.graph_scopes)

    @property
    def allowed_origins_list(self) -> List[str]:
        """Get allowed origins as a list."""
        return _split_csv(self.allowed_origins)

    @property
    def job_tracking_db_path(self) -> Path:
        """Path to job tracking SQLite database."""
        return self.data_ingestion_path / "jobs" / "jobs.db"

    @property
    def job_tracking_db_dir(self) -> Path:
        """Get the directory containing the job tracking database."""
        return self.job_tracking_db_path.parent

    @property
    def model_output_cache_path(self) -> Path:
        """Path for model output JSONL cache files."""
        return self.data_ingestion_path / "model_cache"

    @property
    def docs_content_dir(self) -> Path:
        """Path to documentation content directory."""
        return PROJECT_ROOT / "docs" / "docs_content"

    # ==================== Directory Management ====================

    def ensure_job_tracking_dir(self) -> None:
        """Ensure the job tracking database directory exists."""
        self.job_tracking_db_dir.mkdir(parents=True, exist_ok=True)

    def ensure_model_cache_dir(self) -> None:
        """Ensure the model output cache directory exists."""
        self.model_output_cache_path.mkdir(parents=True, exist_ok=True)

    def ensure_data_ingestion_dir(self) -> None:
        """Ensure the data ingestion directory exists."""
        self.data_ingestion_path.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance (singleton pattern).

    Returns:
        Settings instance loaded from environment variables.

    Example:
        from server.config.settings import get_settings

        settings = get_settings()
        print(settings.surrealdb_url)
    """
    return Settings()


# Convenience instance for direct import
settings = get_settings()
