# Configuration Module

This module provides centralized configuration management for the NFR Connect backend.

## Components

### 1. Settings (`server/settings.py`)

Manages all environment variables using Pydantic BaseSettings. Configuration is loaded from `.env` file.

**All values must be defined in `.env` - no defaults. Missing values will raise an error at startup.**

**Usage:**

```python
from server.settings import get_settings

# Get settings instance (singleton)
settings = get_settings()

# Access configuration
print(settings.surrealdb_url)
print(settings.job_tracking_db_path)
print(settings.data_ingestion_path)

# Ensure directories exist
settings.ensure_directories()
```

**Also available via config module:**

```python
from server.config import get_settings, settings
```

**Available Settings (all required in .env):**

| Setting | Description |
|---------|-------------|
| `tenant_id` | Azure AD Tenant ID |
| `client_id` | Azure AD Client ID |
| `client_secret` | Azure AD Client Secret |
| `graph_scopes` | Comma-separated Graph scopes |
| `group_chat_access` | Group ID for chat access |
| `group_dashboard_access` | Group ID for dashboard access |
| `group_pipelines_ingestion_access` | Group ID for ingestion |
| `group_pipelines_admin_access` | Group ID for admin access |
| `surrealdb_url` | SurrealDB WebSocket URL |
| `surrealdb_namespace` | SurrealDB namespace |
| `surrealdb_database` | SurrealDB database name |
| `surrealdb_user` | SurrealDB username |
| `surrealdb_pass` | SurrealDB password |
| `data_ingestion_path` | Base path for data ingestion |
| `job_tracking_db_path` | Path to job tracking SQLite database |
| `model_output_cache_path` | Path for model cache files |
| `docs_content_dir` | Path to docs content directory |
| `allowed_origins` | Comma-separated CORS origins |
| `uvicorn_host` | Server host |
| `uvicorn_port` | Server port |

### 2. SurrealDB Connection (`surrealdb.py`)

Provides async context manager for SurrealDB connections with automatic authentication and error handling.

**Usage:**

```python
from server.config import get_surrealdb_connection

# Use as async context manager
async with get_surrealdb_connection() as db:
    # Execute queries
    result = await db.query("SELECT * FROM controls")
    print(result)

# Test connection
from server.config import test_surrealdb_connection

if await test_surrealdb_connection():
    print("SurrealDB is ready!")
```

## Environment Variables

All configuration is loaded from `server/.env`:

```env
# Azure AD Configuration
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
GRAPH_SCOPES=User.Read,GroupMember.Read.All,Group.Read.All

# Access Control Groups
GROUP_CHAT_ACCESS=group-id
GROUP_DASHBOARD_ACCESS=group-id
GROUP_PIPELINES_INGESTION_ACCESS=group-id
GROUP_PIPELINES_ADMIN_ACCESS=group-id

# SurrealDB Configuration
SURREALDB_URL=ws://127.0.0.1:4132/rpc
SURREALDB_NAMESPACE=nfr_connect
SURREALDB_DATABASE=nfr_connect_db
SURREALDB_USER=root
SURREALDB_PASS=root

# Paths (ALL REQUIRED - no dynamic creation)
DATA_INGESTION_PATH=/path/to/data_ingested
JOB_TRACKING_DB_PATH=/path/to/data_ingested/jobs/jobs.db
MODEL_OUTPUT_CACHE_PATH=/path/to/data_ingested/model_cache
DOCS_CONTENT_DIR=/path/to/docs/docs_content

# CORS & Server
ALLOWED_ORIGINS=http://localhost:3000
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
```

## Starting SurrealDB

To start SurrealDB for development:

```bash
surreal start --bind 127.0.0.1:4132 --user root --pass root memory
```

## Directory Structure

```
server/
├── settings.py           # Pydantic settings (main file)
├── .env                  # Environment variables (required)
└── config/
    ├── __init__.py       # Module exports (re-exports settings)
    ├── surrealdb.py      # SurrealDB connection manager
    └── README.md         # This file
```

## Best Practices

1. Always use `get_settings()` to access configuration (singleton)
2. Use the async context manager for SurrealDB connections
3. Never hardcode connection strings or paths - use environment variables
4. All settings must be in `.env` - no defaults in code
5. All paths must be explicit - no dynamic path creation
