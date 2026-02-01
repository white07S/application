# Configuration Module

This module provides centralized configuration management for the NFR Connect backend.

## Components

### 1. Settings (`settings.py`)

Manages all environment variables using Pydantic BaseSettings. Configuration is loaded from `.env` file.

**Usage:**

```python
from server.config import get_settings, settings

# Get settings instance (singleton)
settings = get_settings()

# Access configuration
print(settings.surrealdb_url)
print(settings.job_tracking_db_path)
print(settings.data_ingestion_path)

# Ensure job tracking directory exists
settings.ensure_job_tracking_dir()
```

**Available Settings:**

- `surrealdb_url` - SurrealDB WebSocket URL
- `surrealdb_namespace` - SurrealDB namespace
- `surrealdb_database` - SurrealDB database name
- `surrealdb_user` - SurrealDB username
- `surrealdb_pass` - SurrealDB password
- `job_tracking_db_path` - Path to job tracking SQLite database
- `data_ingestion_path` - Base path for data ingestion

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

All configuration is loaded from `/Users/preetam/Develop/application/server/.env`:

```env
# SurrealDB Configuration
SURREALDB_URL=ws://127.0.0.1:4132/rpc
SURREALDB_NAMESPACE=nfr_connect
SURREALDB_DATABASE=nfr_connect_db
SURREALDB_USER=root
SURREALDB_PASS=root

# Job Tracking SQLite
JOB_TRACKING_DB_PATH=/Users/preetam/Develop/application/data_ingested/jobs/jobs.db

# Data paths
DATA_INGESTION_PATH=/Users/preetam/Develop/application/data_ingested
```

## Starting SurrealDB

To start SurrealDB for development:

```bash
surreal start --bind 127.0.0.1:4132 --user root --pass root memory
```

## Directory Structure

```
server/config/
├── __init__.py       # Module exports
├── settings.py       # Pydantic settings configuration
├── surrealdb.py      # SurrealDB connection manager
└── README.md         # This file
```

## Best Practices

1. Always use the singleton `get_settings()` function to access configuration
2. Use the async context manager for SurrealDB connections
3. Never hardcode connection strings or paths - use environment variables
4. Call `ensure_job_tracking_dir()` before creating job tracking database
