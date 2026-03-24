"""
Warehouse manager factory.

Selects storage backend from environment:
- sqlite (default): local embedded DB
- postgres / timescale: PostgreSQL-compatible warehouse
"""

import os

from .db_manager import DatabaseManager


def create_warehouse_manager():
    """Create a configured warehouse manager instance."""
    backend = os.getenv("ECOSIM_WAREHOUSE_BACKEND", "sqlite").strip().lower()

    if backend == "sqlite":
        sqlite_path = os.getenv("ECOSIM_SQLITE_PATH")
        return DatabaseManager(db_path=sqlite_path) if sqlite_path else DatabaseManager()

    if backend in {"postgres", "postgresql", "timescale", "timescaledb"}:
        from .postgres_manager import PostgresDatabaseManager

        dsn = os.getenv("ECOSIM_WAREHOUSE_DSN")
        return PostgresDatabaseManager(dsn=dsn)

    raise ValueError(
        f"Unsupported ECOSIM_WAREHOUSE_BACKEND='{backend}'. "
        "Use one of: sqlite, postgres, timescale."
    )
