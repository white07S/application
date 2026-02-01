"""Legacy settings module - redirects to unified config/settings.py.

DEPRECATED: Import settings from server.config.settings instead:
    from server.config.settings import get_settings
    settings = get_settings()

This module exists for backward compatibility only.
"""

from server.config.settings import get_settings, PROJECT_ROOT

# Get unified settings
_settings = get_settings()

# Export backward-compatible module-level variables
BASE_DIR = PROJECT_ROOT / "server"

# Auth settings
TENANT_ID = _settings.tenant_id
CLIENT_ID = _settings.client_id
CLIENT_SECRET = _settings.client_secret
AUTHORITY = _settings.authority
GRAPH_SCOPES = _settings.graph_scopes_list
GROUP_CHAT_ACCESS = _settings.group_chat_access
GROUP_DASHBOARD_ACCESS = _settings.group_dashboard_access
GROUP_PIPELINES_INGESTION_ACCESS = _settings.group_pipelines_ingestion_access
GROUP_PIPELINES_ADMIN_ACCESS = _settings.group_pipelines_admin_access

# Data paths
DATA_INGESTION_PATH = _settings.data_ingestion_path
DOCS_CONTENT_DIR = _settings.docs_content_dir

# Server settings
ALLOWED_ORIGINS = _settings.allowed_origins_list
UVICORN_HOST = _settings.uvicorn_host
UVICORN_PORT = _settings.uvicorn_port
