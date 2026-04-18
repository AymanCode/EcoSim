"""
Migration 015 (SQLite): add diagnostics tables and regime-transition events.

Logical purpose:
1. extend `simulation_runs` with `diagnostics_version`
2. add compact per-tick and per-sector diagnostics tables
3. add sparse high-value `regime_events` with deterministic event keys

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
    """Execute the SQLite diagnostics/regime-event migration."""
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(migrations_dir)
    db_path = os.path.join(data_dir, "ecosim.db")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 015 (SQLite Diagnostics + Regime Events)")
    print("=" * 70)
    print()
    print(f"Database: {db_path}")
    print()

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        _ensure_column(conn, "simulation_runs", "diagnostics_version", "diagnostics_version TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tick_diagnostics (
                run_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                unemployment_change_pp REAL NOT NULL,
                unemployment_primary_driver TEXT NOT NULL,
                layoffs_count INTEGER NOT NULL,
                hires_count INTEGER NOT NULL,
                failed_hiring_firm_count INTEGER NOT NULL,
                failed_hiring_roles_count INTEGER NOT NULL,
                wage_mismatch_seeker_count INTEGER NOT NULL,
                health_blocked_worker_count INTEGER NOT NULL,
                inactive_work_capable_count INTEGER NOT NULL,
                avg_health_change_pp REAL NOT NULL,
                health_primary_driver TEXT NOT NULL,
                low_health_share REAL NOT NULL,
                food_insecure_share REAL NOT NULL,
                cash_stressed_share REAL NOT NULL,
                pending_healthcare_visits_total INTEGER NOT NULL,
                healthcare_queue_depth INTEGER NOT NULL,
                healthcare_completed_count INTEGER NOT NULL,
                healthcare_denied_count INTEGER NOT NULL,
                firm_distress_primary_driver TEXT NOT NULL,
                burn_mode_firm_count INTEGER NOT NULL,
                survival_mode_firm_count INTEGER NOT NULL,
                zero_cash_firm_count INTEGER NOT NULL,
                weak_demand_firm_count INTEGER NOT NULL,
                inventory_pressure_firm_count INTEGER NOT NULL,
                bankruptcy_count INTEGER NOT NULL,
                housing_primary_driver TEXT NOT NULL,
                eviction_count INTEGER NOT NULL,
                housing_failure_count INTEGER NOT NULL,
                housing_unaffordable_count INTEGER NOT NULL,
                housing_no_supply_count INTEGER NOT NULL,
                homeless_household_count INTEGER NOT NULL,
                shortage_active_sector_count INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, tick),
                FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tick_diagnostics_run_tick ON tick_diagnostics(run_id, tick)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sector_shortage_diagnostics (
                run_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                sector TEXT NOT NULL,
                shortage_active BOOLEAN NOT NULL,
                shortage_severity REAL NOT NULL,
                primary_driver TEXT NOT NULL,
                mean_sell_through_rate REAL NOT NULL,
                vacancy_pressure REAL NOT NULL,
                inventory_pressure REAL NOT NULL,
                price_pressure REAL NOT NULL,
                queue_pressure REAL NOT NULL,
                occupancy_pressure REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, tick, sector),
                FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sector_shortage_run_tick ON sector_shortage_diagnostics(run_id, tick)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sector_shortage_run_sector_tick ON sector_shortage_diagnostics(run_id, sector, tick)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS regime_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_key TEXT NOT NULL,
                tick INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                sector TEXT,
                reason_code TEXT,
                severity REAL,
                metric_value REAL,
                payload_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_regime_events_run_tick ON regime_events(run_id, tick)")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_regime_events_run_event_key ON regime_events(run_id, event_key)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_regime_events_run_type_tick ON regime_events(run_id, event_type, tick)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_regime_events_run_entity_type_tick ON regime_events(run_id, entity_type, tick)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_regime_events_run_entity_tick ON regime_events(run_id, entity_type, entity_id, tick)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_regime_events_run_sector_tick ON regime_events(run_id, sector, tick)"
        )

        conn.commit()
        conn.close()

        print("Diagnostics/regime-event tables ensured successfully.")
        print("Added/ensured:")
        print("  - simulation_runs.diagnostics_version")
        print("  - tick_diagnostics")
        print("  - sector_shortage_diagnostics")
        print("  - regime_events with deterministic event-key uniqueness")
        print()
        print("=" * 70)
        print("Migration completed successfully.")
        print("=" * 70)
    except sqlite3.Error as exc:
        print(f"Database error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
