"""
Migration 007 (SQLite): add firm snapshot table.

Logical purpose:
1. create `firm_snapshots`
2. add indexes for common analytical reads
3. keep firm state queryable without storing full household snapshots yet

Safe to run multiple times.
"""

import os
import sqlite3
import sys


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def run_migration():
    """Execute the SQLite firm-snapshot migration."""
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(migrations_dir)
    schema_path = os.path.join(data_dir, "schema.sql")
    db_path = os.path.join(data_dir, "ecosim.db")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 007 (SQLite Firm Snapshots)")
    print("=" * 70)
    print()
    print(f"Database: {db_path}")
    print(f"Schema: {schema_path}")
    print()

    if not os.path.exists(schema_path):
        print(f"Schema file not found: {schema_path}")
        raise SystemExit(1)

    schema_sql = open(schema_path, "r", encoding="utf-8").read()

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema_sql)
        conn.commit()
        conn.close()

        print("Firm snapshot table ensured successfully.")
        print("Added/ensured:")
        print("  - firm_snapshots")
        print("  - idx_firm_snapshots_run_tick")
        print("  - idx_firm_snapshots_run_firm_tick")
        print("  - idx_firm_snapshots_run_sector_tick")
        print()
        print("=" * 70)
        print("Migration completed successfully.")
        print("=" * 70)
    except sqlite3.Error as exc:
        print(f"Database error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
