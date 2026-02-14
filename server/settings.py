"""Unified settings for the application.

All values MUST be defined in .env file. No defaults.
Missing values will raise an error at startup.
"""

from pathlib import Path
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Server directory (for .env file location)
_SERVER_DIR = Path(__file__).resolve().parent


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
    group_explorer_access: str = Field(description="Group ID for explorer access")
    group_pipelines_ingestion_access: str = Field(description="Group ID for ingestion")
    group_pipelines_admin_access: str = Field(description="Group ID for admin access")
    group_dev_data_access: str = Field(description="Group ID for dev data access")

    # === PostgreSQL - ALL REQUIRED ===
    postgres_url: str = Field(
        description="PostgreSQL async connection URL (postgresql+asyncpg://...)"
    )
    postgres_pool_size: int = Field(
        default=5,
        description="Connection pool size",
        ge=1,
    )
    postgres_max_overflow: int = Field(
        default=10,
        description="Max pool overflow connections",
        ge=0,
    )
    postgres_write_batch_size: int = Field(
        default=500,
        description="Batch size for ingestion writers",
        ge=1,
    )

    # === Qdrant ===
    qdrant_url: str = Field(
        default="http://localhost:16333",
        description="Qdrant REST API URL",
    )
    qdrant_collection_prefix: str = Field(
        default="nfr_connect",
        description="Qdrant collection name prefix (e.g., nfr_connect_controls, nfr_connect_issues)",
    )

    @property
    def qdrant_collection(self) -> str:
        """Get the controls collection name (backward compatibility)."""
        return f"{self.qdrant_collection_prefix}_controls"

    def get_qdrant_collection(self, data_type: str = "controls") -> str:
        """Get collection name for a specific data type."""
        return f"{self.qdrant_collection_prefix}_{data_type}"

    # === Paths - ALL REQUIRED ===
    # Context providers (org charts + risk themes, date-partitioned)
    context_providers_path: Path = Field(description="Base path for context provider data")

    # Data ingested (controls, model runs, TUS temp, state)
    data_ingested_path: Path = Field(description="Base path for ingested controls and model outputs")

    # Documentation
    docs_content_dir: Path = Field(description="Path to docs content directory")

    # === Server - ALL REQUIRED ===
    allowed_origins: str = Field(description="Comma-separated CORS origins")
    uvicorn_host: str = Field(description="Server host")
    uvicorn_port: int = Field(description="Server port")

    # === Path Validators ===
    @field_validator(
        'context_providers_path',
        'data_ingested_path',
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


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings singleton.

    Automatically creates all required directories on first call.
    """
    settings = Settings()

    # Context providers directory (org charts + risk themes)
    settings.context_providers_path.mkdir(parents=True, exist_ok=True)

    # Data ingested directory and subdirectories
    settings.data_ingested_path.mkdir(parents=True, exist_ok=True)
    (settings.data_ingested_path / "controls").mkdir(parents=True, exist_ok=True)
    (settings.data_ingested_path / "model_runs" / "taxonomy").mkdir(parents=True, exist_ok=True)
    (settings.data_ingested_path / "model_runs" / "enrichment").mkdir(parents=True, exist_ok=True)
    (settings.data_ingested_path / "model_runs" / "clean_text").mkdir(parents=True, exist_ok=True)
    (settings.data_ingested_path / "model_runs" / "embeddings").mkdir(parents=True, exist_ok=True)
    (settings.data_ingested_path / ".tus_temp").mkdir(parents=True, exist_ok=True)
    (settings.data_ingested_path / ".state").mkdir(parents=True, exist_ok=True)

    # Docs directory - must exist, don't auto-create
    if not settings.docs_content_dir.exists():
        raise FileNotFoundError(
            f"DOCS_CONTENT_DIR does not exist: {settings.docs_content_dir}\n"
            "Please create this directory manually or update the path in .env"
        )

    return settings


# Module-level exports for backward compatibility
settings = get_settings()

# Legacy variable names (for backward compatibility)
CLIENT_ID = settings.client_id
CLIENT_SECRET = settings.client_secret
AUTHORITY = settings.authority
GRAPH_SCOPES = settings.graph_scopes_list
GROUP_CHAT_ACCESS = settings.group_chat_access
GROUP_EXPLORER_ACCESS = settings.group_explorer_access
GROUP_PIPELINES_INGESTION_ACCESS = settings.group_pipelines_ingestion_access
GROUP_PIPELINES_ADMIN_ACCESS = settings.group_pipelines_admin_access
GROUP_DEV_DATA_ACCESS = settings.group_dev_data_access
DOCS_CONTENT_DIR = settings.docs_content_dir
ALLOWED_ORIGINS = settings.allowed_origins_list
UVICORN_HOST = settings.uvicorn_host
UVICORN_PORT = settings.uvicorn_port
