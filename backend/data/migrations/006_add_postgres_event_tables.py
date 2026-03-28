"""
Migration 006 (PostgreSQL/Timescale): add event tables.

Logical purpose:
1. create `labor_events`
2. create `healthcare_events`
3. create `policy_actions`
4. add indexes for analytical reads

Safe to run multiple times.
"""

import os
import sys
from pathlib import Path


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def run_migration():
    """Execute the Postgres event-table migration."""
    try:
        import psycopg
    except ImportError as exc:
        print("psycopg is required. Install with: pip install psycopg[binary]")
        raise SystemExit(1) from exc

    root_dir = Path(__file__).resolve().parent.parent
    schema_path = root_dir / "postgres_schema.sql"
    dsn = os.getenv("ECOSIM_WAREHOUSE_DSN", "postgresql://ecosim:ecosim@localhost:5432/ecosim")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 006 (Postgres Event Tables)")
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
        conn.close()

        print("Event tables ensured successfully.")
        print("Added/ensured:")
        print("  - labor_events")
        print("  - healthcare_events")
        print("  - policy_actions")
        print()
        print("=" * 70)
        print("Migration completed successfully.")
        print("=" * 70)
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
