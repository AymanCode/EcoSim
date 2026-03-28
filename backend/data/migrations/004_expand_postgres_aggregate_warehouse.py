"""
Migration 004 (PostgreSQL/Timescale): expand aggregate warehouse schema.

This is the PostgreSQL/Timescale companion to the SQLite aggregate expansion.

What it changes:
1. adds `seed` to `simulation_runs`
2. adds runtime and labor columns to `tick_metrics`
3. creates `sector_tick_metrics`
4. converts `sector_tick_metrics` to a hypertable when Timescale is available
5. refreshes analytical views

Safe to run multiple times.
"""

import os
import sys
from pathlib import Path


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def run_migration():
    """Execute the PostgreSQL aggregate-expansion migration."""
    try:
        import psycopg
    except ImportError as exc:
        print("psycopg is required. Install with: pip install psycopg[binary]")
        raise SystemExit(1) from exc

    root_dir = Path(__file__).resolve().parent.parent
    schema_path = root_dir / "postgres_schema.sql"
    dsn = os.getenv("ECOSIM_WAREHOUSE_DSN", "postgresql://ecosim:ecosim@localhost:5432/ecosim")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 004 (Postgres Aggregate Expansion)")
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
            # Apply latest create statements first so fresh databases work.
            cur.execute(schema_sql)

            # Existing tables need explicit ALTERs because CREATE TABLE IF NOT EXISTS
            # does not add new columns.
            cur.execute("ALTER TABLE simulation_runs ADD COLUMN IF NOT EXISTS seed INTEGER")

            cur.execute("ALTER TABLE tick_metrics ADD COLUMN IF NOT EXISTS tick_duration_ms DOUBLE PRECISION")
            cur.execute("ALTER TABLE tick_metrics ADD COLUMN IF NOT EXISTS labor_force_participation DOUBLE PRECISION")
            cur.execute("ALTER TABLE tick_metrics ADD COLUMN IF NOT EXISTS open_vacancies INTEGER")
            cur.execute("ALTER TABLE tick_metrics ADD COLUMN IF NOT EXISTS total_hires INTEGER")
            cur.execute("ALTER TABLE tick_metrics ADD COLUMN IF NOT EXISTS total_layoffs INTEGER")
            cur.execute("ALTER TABLE tick_metrics ADD COLUMN IF NOT EXISTS healthcare_queue_depth INTEGER")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sector_tick_metrics (
                    run_id TEXT NOT NULL,
                    tick INTEGER NOT NULL CHECK (tick >= 0),
                    sector TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    firm_count INTEGER,
                    employees INTEGER,
                    vacancies INTEGER,
                    mean_wage_offer DOUBLE PRECISION,
                    mean_price DOUBLE PRECISION,
                    mean_inventory DOUBLE PRECISION,
                    total_output DOUBLE PRECISION,
                    total_revenue DOUBLE PRECISION,
                    total_profit DOUBLE PRECISION,
                    PRIMARY KEY (run_id, tick, sector),
                    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_sector_metrics_run_tick ON sector_tick_metrics(run_id, tick)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_sector_metrics_run_sector_tick ON sector_tick_metrics(run_id, sector, tick)"
            )

            cur.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                        PERFORM create_hypertable(
                            'sector_tick_metrics',
                            'tick',
                            if_not_exists => TRUE,
                            migrate_data => TRUE,
                            chunk_time_interval => 1000
                        );
                    END IF;
                EXCEPTION
                    WHEN undefined_function THEN
                        NULL;
                END $$;
                """
            )

            cur.execute("DROP VIEW IF EXISTS run_summary")
            cur.execute("DROP VIEW IF EXISTS run_averages")
            cur.execute(
                """
                CREATE VIEW run_summary AS
                SELECT
                    r.run_id,
                    r.created_at,
                    r.status,
                    r.seed,
                    r.total_ticks,
                    r.final_gdp,
                    r.final_unemployment,
                    r.final_gini,
                    p.universal_basic_income AS ubi,
                    p.minimum_wage,
                    p.wage_tax,
                    p.profit_tax
                FROM simulation_runs r
                LEFT JOIN policy_config p ON r.run_id = p.run_id
                """
            )
            cur.execute(
                """
                CREATE VIEW run_averages AS
                SELECT
                    run_id,
                    COUNT(*) AS tick_count,
                    AVG(gdp) AS avg_gdp,
                    AVG(unemployment_rate) AS avg_unemployment,
                    AVG(gini_coefficient) AS avg_gini,
                    AVG(avg_happiness) AS avg_happiness,
                    AVG(tick_duration_ms) AS avg_tick_duration_ms,
                    AVG(labor_force_participation) AS avg_labor_force_participation,
                    AVG(open_vacancies) AS avg_open_vacancies,
                    MAX(gdp) AS peak_gdp,
                    MIN(unemployment_rate) AS min_unemployment,
                    MAX(gini_coefficient) AS peak_gini
                FROM tick_metrics
                GROUP BY run_id
                """
            )

        conn.commit()
        conn.close()

        print("Expanded aggregate warehouse successfully.")
        print("Added/ensured:")
        print("  - simulation_runs.seed")
        print("  - tick_metrics runtime/labor columns")
        print("  - sector_tick_metrics table + indexes")
        print("  - sector_tick_metrics hypertable when Timescale is available")
        print("  - refreshed analytical views")
        print()
        print("=" * 70)
        print("Migration completed successfully.")
        print("=" * 70)
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
