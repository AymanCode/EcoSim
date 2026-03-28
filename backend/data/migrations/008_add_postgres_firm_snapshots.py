"""
Migration 008 (PostgreSQL/Timescale): add firm snapshot table.

Logical purpose:
1. create `firm_snapshots`
2. add indexes for analytical reads
3. convert the table to a hypertable when Timescale is available

Safe to run multiple times.
"""

import os
import sys
from pathlib import Path


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def run_migration():
    """Execute the Postgres firm-snapshot migration."""
    try:
        import psycopg
    except ImportError as exc:
        print("psycopg is required. Install with: pip install psycopg[binary]")
        raise SystemExit(1) from exc

    root_dir = Path(__file__).resolve().parent.parent
    schema_path = root_dir / "postgres_schema.sql"
    dsn = os.getenv("ECOSIM_WAREHOUSE_DSN", "postgresql://ecosim:ecosim@localhost:5432/ecosim")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 008 (Postgres Firm Snapshots)")
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

        print("Firm snapshot table ensured successfully.")
        print("Added/ensured:")
        print("  - firm_snapshots")
        print("  - idx_firm_snapshots_run_tick")
        print("  - idx_firm_snapshots_run_firm_tick")
        print("  - idx_firm_snapshots_run_sector_tick")
        print("  - firm_snapshots hypertable when Timescale is available")
        print()
        print("=" * 70)
        print("Migration completed successfully.")
        print("=" * 70)
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
