"""
Migration 014 (PostgreSQL/Timescale): add reliability and replay-manifest columns.

Logical purpose:
1. extend `simulation_runs` with flush-watermark and manifest fields
2. add `event_key` to event tables for idempotent inserts
3. backfill legacy rows enough to support uniqueness constraints

Safe to run multiple times.
"""

import os
import sys


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def run_migration():
    """Execute the Postgres reliability/manifest migration."""
    try:
        import psycopg
    except ImportError as exc:
        print("psycopg is required. Install with: pip install psycopg[binary]")
        raise SystemExit(1) from exc

    dsn = os.getenv("ECOSIM_WAREHOUSE_DSN", "postgresql://ecosim:ecosim@localhost:5432/ecosim")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 014 (Postgres Reliability + Manifest)")
    print("=" * 70)
    print()
    print(f"DSN: {dsn}")
    print()

    statements = [
        "ALTER TABLE simulation_runs ADD COLUMN IF NOT EXISTS config_json JSONB",
        "ALTER TABLE simulation_runs ADD COLUMN IF NOT EXISTS code_version TEXT",
        "ALTER TABLE simulation_runs ADD COLUMN IF NOT EXISTS schema_version TEXT",
        "ALTER TABLE simulation_runs ADD COLUMN IF NOT EXISTS decision_feature_version TEXT",
        "ALTER TABLE simulation_runs ADD COLUMN IF NOT EXISTS last_fully_persisted_tick INTEGER DEFAULT 0",
        "ALTER TABLE simulation_runs ADD COLUMN IF NOT EXISTS analysis_ready BOOLEAN DEFAULT FALSE",
        "ALTER TABLE simulation_runs ADD COLUMN IF NOT EXISTS termination_reason TEXT",
        "ALTER TABLE labor_events ADD COLUMN IF NOT EXISTS event_key TEXT",
        "UPDATE labor_events SET event_key = COALESCE(event_key, 'legacy-labor-' || event_id::text) WHERE event_key IS NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_labor_events_run_event_key ON labor_events(run_id, event_key)",
        "ALTER TABLE healthcare_events ADD COLUMN IF NOT EXISTS event_key TEXT",
        "UPDATE healthcare_events SET event_key = COALESCE(event_key, 'legacy-healthcare-' || event_id::text) WHERE event_key IS NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_healthcare_events_run_event_key ON healthcare_events(run_id, event_key)",
        "ALTER TABLE policy_actions ADD COLUMN IF NOT EXISTS event_key TEXT",
        "UPDATE policy_actions SET event_key = COALESCE(event_key, 'legacy-policy-' || id::text) WHERE event_key IS NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_policy_actions_run_event_key ON policy_actions(run_id, event_key)",
    ]

    try:
        conn = psycopg.connect(dsn)
        conn.autocommit = False
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
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
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
