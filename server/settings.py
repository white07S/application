"""Unified settings for the application.

All values MUST be defined in .env file. No defaults.
Missing values will raise an error at startup.
"""

from pathlib import Path
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root (for .env file location)
_SERVER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _SERVER_DIR.parent


def _split_csv(value: str) -> List[str]:
    """Split comma-separated string into list."""
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """All settings loaded from .env file. No defaults."""

    model_config = SettingsConfigDict(
        env_file=_SERVER_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Auth Settings (Azure AD) - ALL REQUIRED ===
    tenant_id: str = Field(description="Azure AD Tenant ID")
    client_id: str = Field(description="Azure AD Client ID")
    client_secret: str = Field(description="Azure AD Client Secret")
    graph_scopes: str = Field(description="Comma-separated Graph scopes")
    group_chat_access: str = Field(description="Group ID for chat access")
    group_dashboard_access: str = Field(description="Group ID for dashboard access")
    group_pipelines_ingestion_access: str = Field(description="Group ID for ingestion")
    group_pipelines_admin_access: str = Field(description="Group ID for admin access")

    # === SurrealDB - ALL REQUIRED ===
    surrealdb_url: str = Field(description="SurrealDB WebSocket URL")
    surrealdb_namespace: str = Field(description="SurrealDB namespace")
    surrealdb_database: str = Field(description="SurrealDB database name")
    surrealdb_user: str = Field(description="SurrealDB username")
    surrealdb_pass: str = Field(description="SurrealDB password")

    # === Paths - ALL REQUIRED, NO DYNAMIC CREATION ===
    data_ingestion_path: Path = Field(description="Base path for data ingestion")
    job_tracking_db_path: Path = Field(description="Path to jobs SQLite database")
    model_output_cache_path: Path = Field(description="Path for model cache files")
    docs_content_dir: Path = Field(description="Path to docs content directory")

    # === Server - ALL REQUIRED ===
    allowed_origins: str = Field(description="Comma-separated CORS origins")
    uvicorn_host: str = Field(description="Server host")
    uvicorn_port: int = Field(description="Server port")

    # === Path Validators ===
    @field_validator(
        'data_ingestion_path',
        'job_tracking_db_path',
        'model_output_cache_path',
        'docs_content_dir',
        mode='before'
    )
    @classmethod
    def convert_to_path(cls, v):
        if v is None:
            raise ValueError("Path must be specified in .env file")
        return Path(v)

    # === Computed Properties (derived, not from .env) ===
    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def graph_scopes_list(self) -> List[str]:
        return _split_csv(self.graph_scopes)

    @property
    def allowed_origins_list(self) -> List[str]:
        return _split_csv(self.allowed_origins)

    @property
    def job_tracking_db_dir(self) -> Path:
        return self.job_tracking_db_path.parent

    # === Directory Helpers ===
    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.data_ingestion_path.mkdir(parents=True, exist_ok=True)
        self.job_tracking_db_dir.mkdir(parents=True, exist_ok=True)
        self.model_output_cache_path.mkdir(parents=True, exist_ok=True)

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
    """Get cached settings singleton."""
    return Settings()


# Module-level exports for backward compatibility
settings = get_settings()
BASE_DIR = PROJECT_ROOT / "server"

# Legacy variable names
TENANT_ID = settings.tenant_id
CLIENT_ID = settings.client_id
CLIENT_SECRET = settings.client_secret
AUTHORITY = settings.authority
GRAPH_SCOPES = settings.graph_scopes_list
GROUP_CHAT_ACCESS = settings.group_chat_access
GROUP_DASHBOARD_ACCESS = settings.group_dashboard_access
GROUP_PIPELINES_INGESTION_ACCESS = settings.group_pipelines_ingestion_access
GROUP_PIPELINES_ADMIN_ACCESS = settings.group_pipelines_admin_access
DATA_INGESTION_PATH = settings.data_ingestion_path
DOCS_CONTENT_DIR = settings.docs_content_dir
ALLOWED_ORIGINS = settings.allowed_origins_list
UVICORN_HOST = settings.uvicorn_host
UVICORN_PORT = settings.uvicorn_port
