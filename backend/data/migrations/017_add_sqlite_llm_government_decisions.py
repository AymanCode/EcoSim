"""Migration 017 (SQLite): add full LLM government decision persistence."""

from __future__ import annotations

import os
import sqlite3


def migrate(db_path: str) -> None:
    """Apply the latest SQLite schema to create the LLM decision table."""
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(migrations_dir)
    schema_path = os.path.join(data_dir, "schema.sql")
    schema_sql = open(schema_path, "r", encoding="utf-8").read()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    default_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ecosim.db")
    migrate(os.getenv("ECOSIM_SQLITE_PATH", default_db))
