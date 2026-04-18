"""
Migration 016 (PostgreSQL/Timescale): add diagnostics tables and regime events.

Logical purpose:
1. extend `simulation_runs` with `diagnostics_version`
2. add compact per-tick and per-sector diagnostics tables
3. add sparse high-value `regime_events` with deterministic event keys

Safe to run multiple times.
"""

import os
import sys


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def run_migration():
    """Execute the Postgres diagnostics/regime-event migration."""
    try:
        import psycopg
    except ImportError as exc:
        print("psycopg is required. Install with: pip install psycopg[binary]")
        raise SystemExit(1) from exc

    dsn = os.getenv("ECOSIM_WAREHOUSE_DSN", "postgresql://ecosim:ecosim@localhost:5432/ecosim")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 016 (Postgres Diagnostics + Regime Events)")
    print("=" * 70)
    print()
    print(f"DSN: {dsn}")
    print()

    statements = [
        "ALTER TABLE simulation_runs ADD COLUMN IF NOT EXISTS diagnostics_version TEXT",
        """
        CREATE TABLE IF NOT EXISTS tick_diagnostics (
            run_id TEXT NOT NULL,
            tick INTEGER NOT NULL CHECK (tick >= 0),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            unemployment_change_pp DOUBLE PRECISION NOT NULL,
            unemployment_primary_driver TEXT NOT NULL,
            layoffs_count INTEGER NOT NULL,
            hires_count INTEGER NOT NULL,
            failed_hiring_firm_count INTEGER NOT NULL,
            failed_hiring_roles_count INTEGER NOT NULL,
            wage_mismatch_seeker_count INTEGER NOT NULL,
            health_blocked_worker_count INTEGER NOT NULL,
            inactive_work_capable_count INTEGER NOT NULL,
            avg_health_change_pp DOUBLE PRECISION NOT NULL,
            health_primary_driver TEXT NOT NULL,
            low_health_share DOUBLE PRECISION NOT NULL,
            food_insecure_share DOUBLE PRECISION NOT NULL,
            cash_stressed_share DOUBLE PRECISION NOT NULL,
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
            PRIMARY KEY (run_id, tick),
            FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_tick_diagnostics_run_tick ON tick_diagnostics(run_id, tick)",
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable(
                    'tick_diagnostics',
                    'created_at',
                    if_not_exists => TRUE,
                    migrate_data => TRUE
                );
            END IF;
        END$$
        """,
        """
        CREATE TABLE IF NOT EXISTS sector_shortage_diagnostics (
            run_id TEXT NOT NULL,
            tick INTEGER NOT NULL CHECK (tick >= 0),
            sector TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            shortage_active BOOLEAN NOT NULL,
            shortage_severity DOUBLE PRECISION NOT NULL,
            primary_driver TEXT NOT NULL,
            mean_sell_through_rate DOUBLE PRECISION NOT NULL,
            vacancy_pressure DOUBLE PRECISION NOT NULL,
            inventory_pressure DOUBLE PRECISION NOT NULL,
            price_pressure DOUBLE PRECISION NOT NULL,
            queue_pressure DOUBLE PRECISION NOT NULL,
            occupancy_pressure DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (run_id, tick, sector),
            FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_sector_shortage_run_tick ON sector_shortage_diagnostics(run_id, tick)",
        "CREATE INDEX IF NOT EXISTS idx_sector_shortage_run_sector_tick ON sector_shortage_diagnostics(run_id, sector, tick)",
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable(
                    'sector_shortage_diagnostics',
                    'created_at',
                    if_not_exists => TRUE,
                    migrate_data => TRUE
                );
            END IF;
        END$$
        """,
        """
        CREATE TABLE IF NOT EXISTS regime_events (
            event_id BIGSERIAL PRIMARY KEY,
            run_id TEXT NOT NULL,
            event_key TEXT NOT NULL,
            tick INTEGER NOT NULL CHECK (tick >= 0),
            event_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            sector TEXT,
            reason_code TEXT,
            severity DOUBLE PRECISION,
            metric_value DOUBLE PRECISION,
            payload_json JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_regime_events_run_tick ON regime_events(run_id, tick)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_regime_events_run_event_key ON regime_events(run_id, event_key)",
        "CREATE INDEX IF NOT EXISTS idx_regime_events_run_type_tick ON regime_events(run_id, event_type, tick)",
        "CREATE INDEX IF NOT EXISTS idx_regime_events_run_entity_type_tick ON regime_events(run_id, entity_type, tick)",
        "CREATE INDEX IF NOT EXISTS idx_regime_events_run_entity_tick ON regime_events(run_id, entity_type, entity_id, tick)",
        "CREATE INDEX IF NOT EXISTS idx_regime_events_run_sector_tick ON regime_events(run_id, sector, tick)",
    ]

    try:
        conn = psycopg.connect(dsn)
        conn.autocommit = False
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
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
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
