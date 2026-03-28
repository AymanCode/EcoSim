"""
Migration 012 (PostgreSQL/Timescale): add decision feature table.

Logical purpose:
1. create `decision_features`
2. add the primary analytical index for per-run tick reads
3. convert the table to a hypertable when Timescale is available

Safe to run multiple times.
"""

import os
import sys
from pathlib import Path


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def run_migration():
    """Execute the Postgres decision-feature migration."""
    try:
        import psycopg
    except ImportError as exc:
        print("psycopg is required. Install with: pip install psycopg[binary]")
        raise SystemExit(1) from exc

    root_dir = Path(__file__).resolve().parent.parent
    schema_path = root_dir / "postgres_schema.sql"
    dsn = os.getenv("ECOSIM_WAREHOUSE_DSN", "postgresql://ecosim:ecosim@localhost:5432/ecosim")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 012 (Postgres Decision Features)")
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

        print("Decision feature table ensured successfully.")
        print("Added/ensured:")
        print("  - decision_features")
        print("  - idx_decision_features_run_tick")
        print("  - decision_features hypertable when Timescale is available")
        print()
        print("=" * 70)
        print("Migration completed successfully.")
        print("=" * 70)
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
