"""
PostgreSQL/TimescaleDB manager for EcoSim data warehouse operations.

This module mirrors the SQLite DatabaseManager API so callers can switch
backends via configuration without changing simulation logic.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from .db_manager import PolicyConfig, SimulationRun, TickMetrics


class PostgresDatabaseManager:
    """Manage simulation warehouse operations on PostgreSQL/TimescaleDB."""

    ALLOWED_TICK_COLUMNS = {
        "run_id",
        "tick",
        "created_at",
        "gdp",
        "unemployment_rate",
        "mean_wage",
        "median_wage",
        "avg_happiness",
        "avg_health",
        "avg_morale",
        "total_net_worth",
        "gini_coefficient",
        "top10_wealth_share",
        "bottom50_wealth_share",
        "gov_cash_balance",
        "gov_profit",
        "total_firms",
        "struggling_firms",
        "avg_food_price",
        "avg_housing_price",
        "avg_services_price",
    }

    def __init__(self, dsn: Optional[str] = None):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required for PostgreSQL backend. Install with `pip install psycopg[binary]`."
            ) from exc

        self.psycopg = psycopg
        self.db_path = dsn or os.getenv("ECOSIM_WAREHOUSE_DSN")
        if not self.db_path:
            raise ValueError(
                "Missing PostgreSQL DSN. Set ECOSIM_WAREHOUSE_DSN, "
                "e.g. postgresql://ecosim:ecosim@localhost:5432/ecosim"
            )

        self.conn = psycopg.connect(self.db_path, row_factory=dict_row)
        self.conn.autocommit = False

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    # =========================================================================
    # Migration helper
    # =========================================================================

    def apply_schema(self, schema_path: Optional[str] = None):
        """Apply the PostgreSQL/Timescale schema SQL script."""
        if schema_path is None:
            schema_path = os.path.join(os.path.dirname(__file__), "postgres_schema.sql")

        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        with self.conn.cursor() as cur:
            cur.execute(schema_sql)
        self.conn.commit()

    # =========================================================================
    # Simulation run operations
    # =========================================================================

    def create_run(self, run: SimulationRun) -> str:
        """Create a new simulation run row."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO simulation_runs (
                    run_id, status, num_households, num_firms,
                    description, tags
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    run.run_id,
                    run.status,
                    run.num_households,
                    run.num_firms,
                    run.description,
                    run.tags,
                ),
            )
        self.conn.commit()
        return run.run_id

    def update_run_status(
        self,
        run_id: str,
        status: str,
        total_ticks: Optional[int] = None,
        final_metrics: Optional[Dict] = None,
    ):
        """Update run status and optionally final metrics."""
        with self.conn.cursor() as cur:
            if final_metrics:
                cur.execute(
                    """
                    UPDATE simulation_runs
                    SET status = %s,
                        ended_at = NOW(),
                        total_ticks = %s,
                        final_gdp = %s,
                        final_unemployment = %s,
                        final_gini = %s,
                        final_avg_happiness = %s,
                        final_avg_health = %s,
                        final_gov_balance = %s
                    WHERE run_id = %s
                    """,
                    (
                        status,
                        total_ticks,
                        final_metrics.get("gdp"),
                        final_metrics.get("unemployment_rate"),
                        final_metrics.get("gini_coefficient"),
                        final_metrics.get("avg_happiness"),
                        final_metrics.get("avg_health"),
                        final_metrics.get("gov_cash_balance"),
                        run_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE simulation_runs
                    SET status = %s,
                        ended_at = NOW(),
                        total_ticks = %s
                    WHERE run_id = %s
                    """,
                    (status, total_ticks, run_id),
                )
        self.conn.commit()

    def get_run(self, run_id: str) -> Optional[SimulationRun]:
        """Fetch one run by ID."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM simulation_runs WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
        if row:
            return SimulationRun(**dict(row))
        return None

    def get_runs(self, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[SimulationRun]:
        """Fetch run list with optional status filter."""
        with self.conn.cursor() as cur:
            if status:
                cur.execute(
                    """
                    SELECT * FROM simulation_runs
                    WHERE status = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (status, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM simulation_runs
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
        return [SimulationRun(**dict(row)) for row in rows]

    # =========================================================================
    # Tick metrics operations
    # =========================================================================

    def insert_tick_metrics(self, metrics: List[TickMetrics]):
        """Batch insert tick metrics with upsert semantics."""
        if not metrics:
            return

        rows = [
            (
                m.run_id,
                m.tick,
                m.gdp,
                m.unemployment_rate,
                m.mean_wage,
                m.median_wage,
                m.avg_happiness,
                m.avg_health,
                m.avg_morale,
                m.total_net_worth,
                m.gini_coefficient,
                m.top10_wealth_share,
                m.bottom50_wealth_share,
                m.gov_cash_balance,
                m.gov_profit,
                m.total_firms,
                m.struggling_firms,
                m.avg_food_price,
                m.avg_housing_price,
                m.avg_services_price,
            )
            for m in metrics
        ]

        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO tick_metrics (
                    run_id, tick, gdp, unemployment_rate,
                    mean_wage, median_wage,
                    avg_happiness, avg_health, avg_morale,
                    total_net_worth, gini_coefficient,
                    top10_wealth_share, bottom50_wealth_share,
                    gov_cash_balance, gov_profit,
                    total_firms, struggling_firms,
                    avg_food_price, avg_housing_price, avg_services_price
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (run_id, tick) DO UPDATE SET
                    gdp = EXCLUDED.gdp,
                    unemployment_rate = EXCLUDED.unemployment_rate,
                    mean_wage = EXCLUDED.mean_wage,
                    median_wage = EXCLUDED.median_wage,
                    avg_happiness = EXCLUDED.avg_happiness,
                    avg_health = EXCLUDED.avg_health,
                    avg_morale = EXCLUDED.avg_morale,
                    total_net_worth = EXCLUDED.total_net_worth,
                    gini_coefficient = EXCLUDED.gini_coefficient,
                    top10_wealth_share = EXCLUDED.top10_wealth_share,
                    bottom50_wealth_share = EXCLUDED.bottom50_wealth_share,
                    gov_cash_balance = EXCLUDED.gov_cash_balance,
                    gov_profit = EXCLUDED.gov_profit,
                    total_firms = EXCLUDED.total_firms,
                    struggling_firms = EXCLUDED.struggling_firms,
                    avg_food_price = EXCLUDED.avg_food_price,
                    avg_housing_price = EXCLUDED.avg_housing_price,
                    avg_services_price = EXCLUDED.avg_services_price
                """,
                rows,
            )
        self.conn.commit()

    def get_tick_metrics(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        columns: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Fetch ordered tick metrics for a run."""
        if columns:
            invalid_columns = [c for c in columns if c not in self.ALLOWED_TICK_COLUMNS]
            if invalid_columns:
                raise ValueError(f"Invalid tick metric columns requested: {invalid_columns}")
            cols = ", ".join(columns)
        else:
            cols = "*"

        query = f"""
            SELECT {cols}
            FROM tick_metrics
            WHERE run_id = %s AND tick >= %s AND tick <= %s
            ORDER BY tick
        """

        with self.conn.cursor() as cur:
            cur.execute(query, (run_id, tick_start, tick_end))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_run_summary(self, run_id: str) -> Dict:
        """Fetch aggregate summary stats for one run."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS tick_count,
                    AVG(gdp) AS avg_gdp,
                    AVG(unemployment_rate) AS avg_unemployment,
                    AVG(gini_coefficient) AS avg_gini,
                    AVG(avg_happiness) AS avg_happiness,
                    MAX(gdp) AS peak_gdp,
                    MIN(unemployment_rate) AS min_unemployment,
                    MAX(gini_coefficient) AS peak_gini
                FROM tick_metrics
                WHERE run_id = %s
                """,
                (run_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else {}

    # =========================================================================
    # Policy configuration operations
    # =========================================================================

    def insert_policy_config(self, policy: PolicyConfig):
        """Insert or update policy config for a run."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO policy_config (
                    run_id, wage_tax, profit_tax,
                    wealth_tax_rate, wealth_tax_threshold,
                    universal_basic_income, unemployment_benefit_rate,
                    minimum_wage, inflation_rate, birth_rate,
                    agent_stabilizers_enabled
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    wage_tax = EXCLUDED.wage_tax,
                    profit_tax = EXCLUDED.profit_tax,
                    wealth_tax_rate = EXCLUDED.wealth_tax_rate,
                    wealth_tax_threshold = EXCLUDED.wealth_tax_threshold,
                    universal_basic_income = EXCLUDED.universal_basic_income,
                    unemployment_benefit_rate = EXCLUDED.unemployment_benefit_rate,
                    minimum_wage = EXCLUDED.minimum_wage,
                    inflation_rate = EXCLUDED.inflation_rate,
                    birth_rate = EXCLUDED.birth_rate,
                    agent_stabilizers_enabled = EXCLUDED.agent_stabilizers_enabled
                """,
                (
                    policy.run_id,
                    policy.wage_tax,
                    policy.profit_tax,
                    policy.wealth_tax_rate,
                    policy.wealth_tax_threshold,
                    policy.universal_basic_income,
                    policy.unemployment_benefit_rate,
                    policy.minimum_wage,
                    policy.inflation_rate,
                    policy.birth_rate,
                    policy.agent_stabilizers_enabled,
                ),
            )
        self.conn.commit()

    def get_policy_config(self, run_id: str) -> Optional[PolicyConfig]:
        """Fetch one policy config by run ID."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM policy_config WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
        if not row:
            return None
        data = dict(row)
        data.pop("id", None)
        return PolicyConfig(**data)

    # =========================================================================
    # Utility operations
    # =========================================================================

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Execute arbitrary SQL query."""
        with self.conn.cursor() as cur:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_database_stats(self) -> Dict:
        """Return basic warehouse stats for monitoring."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total_runs FROM simulation_runs")
            total_runs = cur.fetchone()["total_runs"]

            cur.execute("SELECT COUNT(*) AS completed_runs FROM simulation_runs WHERE status = 'completed'")
            completed_runs = cur.fetchone()["completed_runs"]

            cur.execute("SELECT COUNT(*) AS total_ticks FROM tick_metrics")
            total_ticks = cur.fetchone()["total_ticks"]

            cur.execute("SELECT pg_database_size(current_database()) AS db_size_bytes")
            db_size_bytes = cur.fetchone()["db_size_bytes"]

        return {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "total_ticks": total_ticks,
            "db_size_mb": float(db_size_bytes) / (1024 * 1024),
        }
