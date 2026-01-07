"""
Database Manager for EcoSim Data Warehouse

Handles all database operations including:
- Creating/updating simulation runs
- Batch inserting tick metrics
- Querying historical data
"""

import sqlite3
import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class SimulationRun:
    """Represents a simulation run"""
    run_id: str
    status: str = 'running'
    num_households: int = 0
    num_firms: int = 0
    total_ticks: int = 0
    created_at: Optional[str] = None
    ended_at: Optional[str] = None
    final_gdp: Optional[float] = None
    final_unemployment: Optional[float] = None
    final_gini: Optional[float] = None
    final_avg_happiness: Optional[float] = None
    final_avg_health: Optional[float] = None
    final_gov_balance: Optional[float] = None
    description: Optional[str] = None
    tags: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class TickMetrics:
    """Represents metrics for a single tick"""
    run_id: str
    tick: int
    gdp: float
    unemployment_rate: float
    mean_wage: float
    median_wage: float
    avg_happiness: float
    avg_health: float
    avg_morale: float
    total_net_worth: float
    gini_coefficient: float
    top10_wealth_share: float
    bottom50_wealth_share: float
    gov_cash_balance: float
    gov_profit: float
    total_firms: int
    struggling_firms: int
    avg_food_price: Optional[float] = None
    avg_housing_price: Optional[float] = None
    avg_services_price: Optional[float] = None


@dataclass
class PolicyConfig:
    """Represents policy configuration"""
    run_id: str
    wage_tax: float
    profit_tax: float
    wealth_tax_rate: float
    wealth_tax_threshold: float
    universal_basic_income: float
    unemployment_benefit_rate: float
    minimum_wage: float
    inflation_rate: float
    birth_rate: float
    agent_stabilizers_enabled: bool = False


class DatabaseManager:
    """Manages all database operations for the data warehouse"""

    def __init__(self, db_path: str = None):
        """
        Initialize database connection

        Args:
            db_path: Path to SQLite database file (default: backend/data/ecosim.db)
        """
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(__file__),
                'ecosim.db'
            )

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return rows as dicts

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    # =========================================================================
    # Simulation Run Operations
    # =========================================================================

    def create_run(self, run: SimulationRun) -> str:
        """
        Create a new simulation run

        Args:
            run: SimulationRun object

        Returns:
            run_id of created run
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO simulation_runs (
                run_id, status, num_households, num_firms,
                description, tags
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            run.run_id,
            run.status,
            run.num_households,
            run.num_firms,
            run.description,
            run.tags
        ))
        self.conn.commit()
        return run.run_id

    def update_run_status(
        self,
        run_id: str,
        status: str,
        total_ticks: int = None,
        final_metrics: Dict = None
    ):
        """
        Update simulation run status and final metrics

        Args:
            run_id: Run identifier
            status: New status ('completed', 'failed', 'stopped')
            total_ticks: Total ticks completed
            final_metrics: Dict with final_gdp, final_unemployment, etc.
        """
        cursor = self.conn.cursor()

        if final_metrics:
            cursor.execute("""
                UPDATE simulation_runs
                SET status = ?,
                    ended_at = CURRENT_TIMESTAMP,
                    total_ticks = ?,
                    final_gdp = ?,
                    final_unemployment = ?,
                    final_gini = ?,
                    final_avg_happiness = ?,
                    final_avg_health = ?,
                    final_gov_balance = ?
                WHERE run_id = ?
            """, (
                status,
                total_ticks,
                final_metrics.get('gdp'),
                final_metrics.get('unemployment_rate'),
                final_metrics.get('gini_coefficient'),
                final_metrics.get('avg_happiness'),
                final_metrics.get('avg_health'),
                final_metrics.get('gov_cash_balance'),
                run_id
            ))
        else:
            cursor.execute("""
                UPDATE simulation_runs
                SET status = ?,
                    ended_at = CURRENT_TIMESTAMP,
                    total_ticks = ?
                WHERE run_id = ?
            """, (status, total_ticks, run_id))

        self.conn.commit()

    def get_run(self, run_id: str) -> Optional[SimulationRun]:
        """
        Get simulation run by ID

        Args:
            run_id: Run identifier

        Returns:
            SimulationRun object or None
        """
        cursor = self.conn.cursor()
        row = cursor.execute(
            "SELECT * FROM simulation_runs WHERE run_id = ?",
            (run_id,)
        ).fetchone()

        if row:
            return SimulationRun(**dict(row))
        return None

    def get_runs(
        self,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SimulationRun]:
        """
        Get list of simulation runs

        Args:
            status: Filter by status (optional)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of SimulationRun objects
        """
        cursor = self.conn.cursor()

        if status:
            query = """
                SELECT * FROM simulation_runs
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            rows = cursor.execute(query, (status, limit, offset)).fetchall()
        else:
            query = """
                SELECT * FROM simulation_runs
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            rows = cursor.execute(query, (limit, offset)).fetchall()

        return [SimulationRun(**dict(row)) for row in rows]

    # =========================================================================
    # Tick Metrics Operations
    # =========================================================================

    def insert_tick_metrics(self, metrics: List[TickMetrics]):
        """
        Batch insert tick metrics

        Args:
            metrics: List of TickMetrics objects
        """
        if not metrics:
            return

        cursor = self.conn.cursor()
        cursor.executemany("""
            INSERT OR REPLACE INTO tick_metrics (
                run_id, tick, gdp, unemployment_rate,
                mean_wage, median_wage,
                avg_happiness, avg_health, avg_morale,
                total_net_worth, gini_coefficient,
                top10_wealth_share, bottom50_wealth_share,
                gov_cash_balance, gov_profit,
                total_firms, struggling_firms,
                avg_food_price, avg_housing_price, avg_services_price
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                m.run_id, m.tick, m.gdp, m.unemployment_rate,
                m.mean_wage, m.median_wage,
                m.avg_happiness, m.avg_health, m.avg_morale,
                m.total_net_worth, m.gini_coefficient,
                m.top10_wealth_share, m.bottom50_wealth_share,
                m.gov_cash_balance, m.gov_profit,
                m.total_firms, m.struggling_firms,
                m.avg_food_price, m.avg_housing_price, m.avg_services_price
            )
            for m in metrics
        ])
        self.conn.commit()

    def get_tick_metrics(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        columns: List[str] = None
    ) -> List[Dict]:
        """
        Get tick metrics for a run

        Args:
            run_id: Run identifier
            tick_start: Start tick (inclusive)
            tick_end: End tick (inclusive)
            columns: List of column names to return (default: all)

        Returns:
            List of metric dictionaries
        """
        cursor = self.conn.cursor()

        if columns:
            cols = ', '.join(columns)
        else:
            cols = '*'

        query = f"""
            SELECT {cols}
            FROM tick_metrics
            WHERE run_id = ? AND tick >= ? AND tick <= ?
            ORDER BY tick
        """
        rows = cursor.execute(query, (run_id, tick_start, tick_end)).fetchall()

        return [dict(row) for row in rows]

    def get_run_summary(self, run_id: str) -> Dict:
        """
        Get aggregate statistics for a run

        Args:
            run_id: Run identifier

        Returns:
            Dictionary with avg_gdp, avg_unemployment, etc.
        """
        cursor = self.conn.cursor()
        row = cursor.execute("""
            SELECT
                COUNT(*) as tick_count,
                AVG(gdp) as avg_gdp,
                AVG(unemployment_rate) as avg_unemployment,
                AVG(gini_coefficient) as avg_gini,
                AVG(avg_happiness) as avg_happiness,
                MAX(gdp) as peak_gdp,
                MIN(unemployment_rate) as min_unemployment,
                MAX(gini_coefficient) as peak_gini
            FROM tick_metrics
            WHERE run_id = ?
        """, (run_id,)).fetchone()

        return dict(row) if row else {}

    # =========================================================================
    # Policy Config Operations
    # =========================================================================

    def insert_policy_config(self, policy: PolicyConfig):
        """
        Insert policy configuration for a run

        Args:
            policy: PolicyConfig object
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO policy_config (
                run_id, wage_tax, profit_tax,
                wealth_tax_rate, wealth_tax_threshold,
                universal_basic_income, unemployment_benefit_rate,
                minimum_wage, inflation_rate, birth_rate,
                agent_stabilizers_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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
            1 if policy.agent_stabilizers_enabled else 0
        ))
        self.conn.commit()

    def get_policy_config(self, run_id: str) -> Optional[PolicyConfig]:
        """
        Get policy configuration for a run

        Args:
            run_id: Run identifier

        Returns:
            PolicyConfig object or None
        """
        cursor = self.conn.cursor()
        row = cursor.execute(
            "SELECT * FROM policy_config WHERE run_id = ?",
            (run_id,)
        ).fetchone()

        if row:
            data = dict(row)
            # Remove ID field (not in dataclass)
            data.pop('id', None)
            data['agent_stabilizers_enabled'] = bool(data['agent_stabilizers_enabled'])
            return PolicyConfig(**data)
        return None

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """
        Execute arbitrary SQL query

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        cursor = self.conn.cursor()
        if params:
            rows = cursor.execute(query, params).fetchall()
        else:
            rows = cursor.execute(query).fetchall()

        return [dict(row) for row in rows]

    def get_database_stats(self) -> Dict:
        """
        Get database statistics

        Returns:
            Dictionary with table counts and database size
        """
        cursor = self.conn.cursor()

        stats = {}

        # Count runs
        stats['total_runs'] = cursor.execute(
            "SELECT COUNT(*) FROM simulation_runs"
        ).fetchone()[0]

        stats['completed_runs'] = cursor.execute(
            "SELECT COUNT(*) FROM simulation_runs WHERE status = 'completed'"
        ).fetchone()[0]

        # Count metrics
        stats['total_ticks'] = cursor.execute(
            "SELECT COUNT(*) FROM tick_metrics"
        ).fetchone()[0]

        # Database size
        if os.path.exists(self.db_path):
            stats['db_size_mb'] = os.path.getsize(self.db_path) / (1024 * 1024)
        else:
            stats['db_size_mb'] = 0

        return stats
