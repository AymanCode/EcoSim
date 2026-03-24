"""
Migration 002: Create PostgreSQL + TimescaleDB warehouse schema.

Usage:
    set ECOSIM_WAREHOUSE_DSN=postgresql://ecosim:ecosim@localhost:5432/ecosim
    python backend/data/migrations/002_create_timescale_warehouse.py
"""

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def run_migration():
    """Execute PostgreSQL/Timescale schema migration."""
    try:
        import psycopg
    except ImportError as exc:
        print("psycopg is required. Install with: pip install psycopg[binary]")
        raise SystemExit(1) from exc

    root_dir = Path(__file__).resolve().parent.parent
    schema_path = root_dir / "postgres_schema.sql"
    dsn = os.getenv("ECOSIM_WAREHOUSE_DSN", "postgresql://ecosim:ecosim@localhost:5432/ecosim")

    print("=" * 70)
    print("EcoSim PostgreSQL + Timescale Migration 002")
    print("=" * 70)
    print()
    print(f"DSN: {dsn}")
    print(f"Schema: {schema_path}")
    print()

    if not schema_path.exists():
        print(f"Schema file not found: {schema_path}")
        raise SystemExit(1)

    schema_sql = schema_path.read_text(encoding="utf-8")

    try:
        conn = psycopg.connect(dsn)
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('simulation_runs', 'tick_metrics', 'policy_config')
                ORDER BY table_name
                """
            )
            tables = [row[0] for row in cur.fetchall()]

            cur.execute(
                """
                SELECT extname
                FROM pg_extension
                WHERE extname = 'timescaledb'
                """
            )
            has_timescale = cur.fetchone() is not None

        print("Schema applied successfully.")
        print(f"Core tables present: {tables}")
        print(f"Timescale extension enabled: {has_timescale}")
        print()
        print("=" * 70)
        print("Migration completed successfully.")
        print("=" * 70)
        conn.close()
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
