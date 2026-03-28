"""
Migration 013 (SQLite): add reliability and replay-manifest columns.

Logical purpose:
1. extend `simulation_runs` with flush-watermark and manifest fields
2. add `event_key` to event tables for idempotent inserts
3. backfill legacy rows enough to support uniqueness constraints

Safe to run multiple times.
"""

import os
import sqlite3
import sys


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def _column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
    if column_name not in _column_names(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


def run_migration():
    """Execute the SQLite reliability/manifest migration."""
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(migrations_dir)
    db_path = os.path.join(data_dir, "ecosim.db")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 013 (SQLite Reliability + Manifest)")
    print("=" * 70)
    print()
    print(f"Database: {db_path}")
    print()

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        _ensure_column(conn, "simulation_runs", "config_json", "config_json TEXT")
        _ensure_column(conn, "simulation_runs", "code_version", "code_version TEXT")
        _ensure_column(conn, "simulation_runs", "schema_version", "schema_version TEXT")
        _ensure_column(conn, "simulation_runs", "decision_feature_version", "decision_feature_version TEXT")
        _ensure_column(
            conn,
            "simulation_runs",
            "last_fully_persisted_tick",
            "last_fully_persisted_tick INTEGER DEFAULT 0",
        )
        _ensure_column(conn, "simulation_runs", "analysis_ready", "analysis_ready BOOLEAN DEFAULT 0")
        _ensure_column(conn, "simulation_runs", "termination_reason", "termination_reason TEXT")

        _ensure_column(conn, "labor_events", "event_key", "event_key TEXT")
        conn.execute(
            """
            UPDATE labor_events
            SET event_key = COALESCE(event_key, 'legacy-labor-' || event_id)
            WHERE event_key IS NULL
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_labor_events_run_event_key ON labor_events(run_id, event_key)"
        )

        _ensure_column(conn, "healthcare_events", "event_key", "event_key TEXT")
        conn.execute(
            """
            UPDATE healthcare_events
            SET event_key = COALESCE(event_key, 'legacy-healthcare-' || event_id)
            WHERE event_key IS NULL
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_healthcare_events_run_event_key ON healthcare_events(run_id, event_key)"
        )

        _ensure_column(conn, "policy_actions", "event_key", "event_key TEXT")
        conn.execute(
            """
            UPDATE policy_actions
            SET event_key = COALESCE(event_key, 'legacy-policy-' || id)
            WHERE event_key IS NULL
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_policy_actions_run_event_key ON policy_actions(run_id, event_key)"
        )

        conn.commit()
        conn.close()

        print("Reliability/manifest columns ensured successfully.")
        print("Added/ensured:")
        print("  - simulation_runs manifest + watermark fields")
        print("  - event_key on labor_events / healthcare_events / policy_actions")
        print("  - unique indexes on (run_id, event_key)")
        print()
        print("=" * 70)
        print("Migration completed successfully.")
        print("=" * 70)
    except sqlite3.Error as exc:
        print(f"Database error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
