"""Configuration module for the application.

This module provides:
- Settings management with environment variables
- SurrealDB connection utilities
"""

from .settings import Settings, get_settings, settings
from .surrealdb import (
    get_surrealdb_connection,
    test_surrealdb_connection,
    SurrealDBConnectionError,
)

__all__ = [
    # Settings
    "Settings",
    "get_settings",
    "settings",
    # SurrealDB
    "get_surrealdb_connection",
    "test_surrealdb_connection",
    "SurrealDBConnectionError",
]
