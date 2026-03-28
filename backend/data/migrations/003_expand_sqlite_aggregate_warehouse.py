"""
Migration 003 (SQLite): expand aggregate warehouse schema.

This upgrades the original SQLite warehouse from the minimal Phase 1 schema to
the richer aggregate model used for historical trend analysis.

What it changes:
1. adds `seed` to `simulation_runs`
2. adds runtime and labor columns to `tick_metrics`
3. creates `sector_tick_metrics`
4. refreshes the analytical views so they expose the new aggregate fields

Safe to run multiple times.
"""

import os
import sqlite3
import sys


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_sql: str):
    if _column_exists(conn, table_name, column_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def run_migration():
    """Execute the SQLite aggregate-expansion migration."""
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(migrations_dir)
    schema_path = os.path.join(data_dir, "schema.sql")
    db_path = os.path.join(data_dir, "ecosim.db")

    print("=" * 70)
    print("EcoSim Data Warehouse Migration 003 (SQLite Aggregate Expansion)")
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
        print("Connected to database")

        # Apply latest base schema first so fresh databases also work.
        conn.executescript(schema_sql)

        # Existing SQLite tables need explicit ALTERs because CREATE TABLE IF NOT EXISTS
        # does not backfill new columns.
        _ensure_column(conn, "simulation_runs", "seed", "INTEGER")

        tick_columns = {
            "tick_duration_ms": "REAL",
            "labor_force_participation": "REAL",
            "open_vacancies": "INTEGER",
            "total_hires": "INTEGER",
            "total_layoffs": "INTEGER",
            "healthcare_queue_depth": "INTEGER",
        }
        for column_name, column_sql in tick_columns.items():
            _ensure_column(conn, "tick_metrics", column_name, column_sql)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sector_tick_metrics (
                run_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                sector TEXT NOT NULL,
                firm_count INTEGER,
                employees INTEGER,
                vacancies INTEGER,
                mean_wage_offer REAL,
                mean_price REAL,
                mean_inventory REAL,
                total_output REAL,
                total_revenue REAL,
                total_profit REAL,
                PRIMARY KEY (run_id, tick, sector),
                FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sector_metrics_run_tick ON sector_tick_metrics(run_id, tick)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sector_metrics_run_sector_tick ON sector_tick_metrics(run_id, sector, tick)"
        )

        # Refresh views so new fields are visible from analytical helpers.
        conn.execute("DROP VIEW IF EXISTS run_summary")
        conn.execute("DROP VIEW IF EXISTS run_averages")
        conn.execute(
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
        conn.execute(
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

        print("Expanded aggregate warehouse successfully.")
        print("Added/ensured:")
        print("  - simulation_runs.seed")
        print("  - tick_metrics runtime/labor columns")
        print("  - sector_tick_metrics table + indexes")
        print("  - refreshed analytical views")
        print()
        print("=" * 70)
        print("Migration completed successfully.")
        print("=" * 70)
        conn.close()
    except sqlite3.Error as exc:
        print(f"Database error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_migration()
