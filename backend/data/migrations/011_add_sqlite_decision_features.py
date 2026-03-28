"""
Migration 011 (SQLite): add decision feature table.

Logical purpose:
1. create `decision_features`
2. add the primary analytical index for per-run tick reads

Safe to run multiple times.
"""

import os
import sqlite3
import sys


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def run_migration():
    """Execute the SQLite decision-feature migration."""
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(migrations_dir)
    schema_path = os.path.join(data_dir, "schema.sql")
    db_path = os.path.join(data_dir, "ecosim.db")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 011 (SQLite Decision Features)")
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

        print("Decision feature table ensured successfully.")
        print("Added/ensured:")
        print("  - decision_features")
        print("  - idx_decision_features_run_tick")
        print()
        print("=" * 70)
        print("Migration completed successfully.")
        print("=" * 70)
    except sqlite3.Error as exc:
        print(f"Database error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
