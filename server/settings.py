import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Auth settings
TENANT_ID = _get_required_env("TENANT_ID")
CLIENT_ID = _get_required_env("CLIENT_ID")
CLIENT_SECRET = _get_required_env("CLIENT_SECRET")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

GRAPH_SCOPES = _split_csv(os.getenv("GRAPH_SCOPES", ""))
if not GRAPH_SCOPES:
    raise RuntimeError("GRAPH_SCOPES must contain at least one scope")

GROUP_CHAT_ACCESS = _get_required_env("GROUP_CHAT_ACCESS")
GROUP_DASHBOARD_ACCESS = _get_required_env("GROUP_DASHBOARD_ACCESS")
GROUP_PIPELINES_INGESTION_ACCESS = _get_required_env("GROUP_PIPELINES_INGESTION_ACCESS")
GROUP_PIPELINES_ADMIN_ACCESS = os.getenv("GROUP_PIPELINES_ADMIN_ACCESS", "ad51a2ff-5627-45c1-882f-659a424bb87c")

# Data Ingestion settings
DATA_INGESTION_PATH = Path(_get_required_env("DATA_INGESTION_PATH")).resolve()

# CORS / app settings
ALLOWED_ORIGINS = _split_csv(_get_required_env("ALLOWED_ORIGINS"))

DOCS_CONTENT_DIR = (PROJECT_ROOT / "docs" / "docs_content").resolve()

UVICORN_HOST = os.getenv("UVICORN_HOST", "0.0.0.0")
UVICORN_PORT = int(os.getenv("UVICORN_PORT", "8000"))
