"""Migration 018 (PostgreSQL/Timescale): add full LLM government decision persistence."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2


def migrate(dsn: str) -> None:
    """Apply the latest PostgreSQL schema to create the LLM decision table."""
    root_dir = Path(__file__).resolve().parents[1]
    schema_sql = (root_dir / "postgres_schema.sql").read_text(encoding="utf-8")
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate(os.environ["ECOSIM_WAREHOUSE_DSN"])
