"""SQLite warehouse manager for EcoSim data persistence."""

import hashlib
import json
import os
import sqlite3
from collections import defaultdict
from typing import Dict, List, Optional

try:  # pragma: no cover - import fallback for standalone scripts
    from .models import (
        DecisionFeature,
        FirmSnapshot,
        HealthcareEvent,
        HouseholdSnapshot,
        LaborEvent,
        PolicyAction,
        PolicyConfig,
        RegimeEvent,
        SectorShortageDiagnostic,
        SectorTickMetrics,
        SimulationRun,
        TickDiagnostic,
        TrackedHouseholdHistory,
        TickMetrics,
    )
except ImportError:  # pragma: no cover
    from models import (  # type: ignore
        DecisionFeature,
        FirmSnapshot,
        HealthcareEvent,
        HouseholdSnapshot,
        LaborEvent,
        PolicyAction,
        PolicyConfig,
        RegimeEvent,
        SectorShortageDiagnostic,
        SectorTickMetrics,
        SimulationRun,
        TickDiagnostic,
        TrackedHouseholdHistory,
        TickMetrics,
    )


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
                run_id, status, seed, num_households, num_firms,
                config_json, code_version, schema_version, decision_feature_version,
                diagnostics_version,
                last_fully_persisted_tick, analysis_ready, termination_reason,
                description, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run.run_id,
            run.status,
            run.seed,
            run.num_households,
            run.num_firms,
            run.config_json,
            run.code_version,
            run.schema_version,
            run.decision_feature_version,
            run.diagnostics_version,
            run.last_fully_persisted_tick,
            1 if run.analysis_ready else 0,
            run.termination_reason,
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
        final_metrics: Dict = None,
        last_fully_persisted_tick: Optional[int] = None,
        analysis_ready: Optional[bool] = None,
        termination_reason: Optional[str] = None,
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
                    final_gov_balance = ?,
                    last_fully_persisted_tick = COALESCE(?, last_fully_persisted_tick),
                    analysis_ready = COALESCE(?, analysis_ready),
                    termination_reason = COALESCE(?, termination_reason)
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
                last_fully_persisted_tick,
                1 if analysis_ready is True else (0 if analysis_ready is False else None),
                termination_reason,
                run_id
            ))
        else:
            cursor.execute("""
                UPDATE simulation_runs
                SET status = ?,
                    ended_at = CURRENT_TIMESTAMP,
                    total_ticks = ?,
                    last_fully_persisted_tick = COALESCE(?, last_fully_persisted_tick),
                    analysis_ready = COALESCE(?, analysis_ready),
                    termination_reason = COALESCE(?, termination_reason)
                WHERE run_id = ?
            """, (
                status,
                total_ticks,
                last_fully_persisted_tick,
                1 if analysis_ready is True else (0 if analysis_ready is False else None),
                termination_reason,
                run_id,
            ))

        self.conn.commit()

    def _update_run_flush_metadata(self, cursor, run_id: str, last_fully_persisted_tick: int):
        """Advance the persisted watermark for a run inside an active transaction."""
        cursor.execute(
            """
            UPDATE simulation_runs
            SET last_fully_persisted_tick = MAX(COALESCE(last_fully_persisted_tick, 0), ?)
            WHERE run_id = ?
            """,
            (last_fully_persisted_tick, run_id),
        )

    @staticmethod
    def _normalize_run_row(row: sqlite3.Row) -> Dict:
        """Normalize storage-specific types before constructing SimulationRun."""
        normalized = dict(row)
        if "analysis_ready" in normalized:
            normalized["analysis_ready"] = bool(normalized["analysis_ready"])
        return normalized

    @staticmethod
    def _event_key_from_components(prefix: str, components: tuple[object, ...], occurrence: int) -> str:
        """Build a deterministic event key from event content plus duplicate ordinal."""
        payload = json.dumps(list(components), separators=(",", ":"), ensure_ascii=True)
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}:{occurrence}"

    def _normalized_labor_events(self, events: List[LaborEvent]) -> List[LaborEvent]:
        """Return labor events with deterministic idempotency keys."""
        duplicates_seen: dict[tuple[object, ...], int] = defaultdict(int)
        normalized: List[LaborEvent] = []
        for event in events:
            signature = (
                event.run_id,
                event.tick,
                event.household_id,
                event.firm_id,
                event.event_type,
                event.actual_wage,
                event.wage_offer,
                event.reservation_wage,
                event.skill_level,
            )
            occurrence = duplicates_seen[signature]
            duplicates_seen[signature] += 1
            normalized.append(
                LaborEvent(
                    run_id=event.run_id,
                    tick=event.tick,
                    household_id=event.household_id,
                    firm_id=event.firm_id,
                    event_type=event.event_type,
                    actual_wage=event.actual_wage,
                    wage_offer=event.wage_offer,
                    reservation_wage=event.reservation_wage,
                    skill_level=event.skill_level,
                    event_key=event.event_key or self._event_key_from_components("labor", signature, occurrence),
                )
            )
        return normalized

    def _normalized_healthcare_events(self, events: List[HealthcareEvent]) -> List[HealthcareEvent]:
        """Return healthcare events with deterministic idempotency keys."""
        duplicates_seen: dict[tuple[object, ...], int] = defaultdict(int)
        normalized: List[HealthcareEvent] = []
        for event in events:
            signature = (
                event.run_id,
                event.tick,
                event.household_id,
                event.firm_id,
                event.event_type,
                event.queue_wait_ticks,
                event.visit_price,
                event.household_cost,
                event.government_cost,
                event.health_before,
                event.health_after,
            )
            occurrence = duplicates_seen[signature]
            duplicates_seen[signature] += 1
            normalized.append(
                HealthcareEvent(
                    run_id=event.run_id,
                    tick=event.tick,
                    household_id=event.household_id,
                    firm_id=event.firm_id,
                    event_type=event.event_type,
                    queue_wait_ticks=event.queue_wait_ticks,
                    visit_price=event.visit_price,
                    household_cost=event.household_cost,
                    government_cost=event.government_cost,
                    health_before=event.health_before,
                    health_after=event.health_after,
                    event_key=event.event_key or self._event_key_from_components("healthcare", signature, occurrence),
                )
            )
        return normalized

    def _normalized_policy_actions(self, actions: List[PolicyAction]) -> List[PolicyAction]:
        """Return policy actions with deterministic idempotency keys."""
        duplicates_seen: dict[tuple[object, ...], int] = defaultdict(int)
        normalized: List[PolicyAction] = []
        for action in actions:
            signature = (
                action.run_id,
                action.tick,
                action.actor,
                action.action_type,
                action.payload_json,
                action.reason_summary,
            )
            occurrence = duplicates_seen[signature]
            duplicates_seen[signature] += 1
            normalized.append(
                PolicyAction(
                    run_id=action.run_id,
                    tick=action.tick,
                    actor=action.actor,
                    action_type=action.action_type,
                    payload_json=action.payload_json,
                    reason_summary=action.reason_summary,
                    event_key=action.event_key or self._event_key_from_components("policy", signature, occurrence),
                )
            )
        return normalized

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
            return SimulationRun(**self._normalize_run_row(row))
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

        return [SimulationRun(**self._normalize_run_row(row)) for row in rows]

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
        self._insert_tick_metrics_rows(cursor, metrics)
        self.conn.commit()

    def _insert_tick_metrics_rows(self, cursor, metrics: List[TickMetrics]):
        """Insert tick metric rows using an existing cursor."""
        cursor.executemany("""
            INSERT OR REPLACE INTO tick_metrics (
                run_id, tick, gdp, unemployment_rate,
                mean_wage, median_wage,
                avg_happiness, avg_health, avg_morale,
                total_net_worth, gini_coefficient,
                top10_wealth_share, bottom50_wealth_share,
                gov_cash_balance, gov_profit,
                tick_duration_ms, labor_force_participation,
                open_vacancies, total_hires, total_layoffs,
                healthcare_queue_depth,
                total_firms, struggling_firms,
                avg_food_price, avg_housing_price, avg_services_price
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                m.run_id, m.tick, m.gdp, m.unemployment_rate,
                m.mean_wage, m.median_wage,
                m.avg_happiness, m.avg_health, m.avg_morale,
                m.total_net_worth, m.gini_coefficient,
                m.top10_wealth_share, m.bottom50_wealth_share,
                m.gov_cash_balance, m.gov_profit,
                m.tick_duration_ms, m.labor_force_participation,
                m.open_vacancies, m.total_hires, m.total_layoffs,
                m.healthcare_queue_depth,
                m.total_firms, m.struggling_firms,
                m.avg_food_price, m.avg_housing_price, m.avg_services_price
            )
            for m in metrics
        ])

    def insert_sector_tick_metrics(self, metrics: List[SectorTickMetrics]):
        """
        Batch insert sector tick metrics.

        Args:
            metrics: List of SectorTickMetrics objects
        """
        if not metrics:
            return

        cursor = self.conn.cursor()
        self._insert_sector_tick_metrics_rows(cursor, metrics)
        self.conn.commit()

    def _insert_sector_tick_metrics_rows(self, cursor, metrics: List[SectorTickMetrics]):
        """Insert sector metric rows using an existing cursor."""
        cursor.executemany("""
            INSERT OR REPLACE INTO sector_tick_metrics (
                run_id, tick, sector, firm_count, employees, vacancies,
                mean_wage_offer, mean_price, mean_inventory,
                total_output, total_revenue, total_profit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                m.run_id,
                m.tick,
                m.sector,
                m.firm_count,
                m.employees,
                m.vacancies,
                m.mean_wage_offer,
                m.mean_price,
                m.mean_inventory,
                m.total_output,
                m.total_revenue,
                m.total_profit,
            )
            for m in metrics
        ])

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

    def get_sector_tick_metrics(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        sector: Optional[str] = None
    ) -> List[Dict]:
        """
        Get sector tick metrics for a run.

        Args:
            run_id: Run identifier
            tick_start: Start tick (inclusive)
            tick_end: End tick (inclusive)
            sector: Optional sector/category filter

        Returns:
            List of sector metric dictionaries
        """
        cursor = self.conn.cursor()

        query = """
            SELECT *
            FROM sector_tick_metrics
            WHERE run_id = ? AND tick >= ? AND tick <= ?
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if sector is not None:
            query += " AND sector = ?"
            params.append(sector)
        query += " ORDER BY tick, sector"

        rows = cursor.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_sector_summary(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        sector: Optional[str] = None,
    ) -> List[Dict]:
        """Get aggregated sector summary rows for a run over a tick range."""
        cursor = self.conn.cursor()
        query = """
            SELECT
                sector,
                COUNT(*) AS tick_count,
                AVG(firm_count) AS avg_firm_count,
                AVG(employees) AS avg_employees,
                AVG(vacancies) AS avg_vacancies,
                AVG(mean_wage_offer) AS avg_wage_offer,
                AVG(mean_price) AS avg_price,
                AVG(mean_inventory) AS avg_inventory,
                SUM(total_output) AS total_output,
                SUM(total_revenue) AS total_revenue,
                SUM(total_profit) AS total_profit,
                MAX(vacancies) AS peak_vacancies
            FROM sector_tick_metrics
            WHERE run_id = ? AND tick >= ? AND tick <= ?
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if sector is not None:
            query += " AND sector = ?"
            params.append(sector)
        query += " GROUP BY sector ORDER BY sector"

        rows = cursor.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_run_comparison(self, run_ids: List[str]) -> List[Dict]:
        """Get comparison rows for a set of run IDs."""
        if not run_ids:
            return []

        cursor = self.conn.cursor()
        placeholders = ", ".join(["?"] * len(run_ids))
        query = f"""
            SELECT
                rs.run_id,
                rs.created_at,
                rs.status,
                rs.seed,
                rs.total_ticks,
                rs.final_gdp,
                rs.final_unemployment,
                rs.final_gini,
                rs.ubi,
                rs.minimum_wage,
                rs.wage_tax,
                rs.profit_tax,
                ra.tick_count,
                ra.avg_gdp,
                ra.avg_unemployment,
                ra.avg_gini,
                ra.avg_happiness,
                ra.avg_tick_duration_ms,
                ra.avg_labor_force_participation,
                ra.avg_open_vacancies,
                ra.peak_gdp,
                ra.min_unemployment,
                ra.peak_gini
            FROM run_summary rs
            LEFT JOIN run_averages ra ON rs.run_id = ra.run_id
            WHERE rs.run_id IN ({placeholders})
            ORDER BY rs.created_at DESC, rs.run_id
        """
        rows = cursor.execute(query, tuple(run_ids)).fetchall()
        return [dict(row) for row in rows]

    def insert_firm_snapshots(self, snapshots: List[FirmSnapshot]):
        """Batch insert firm snapshots."""
        if not snapshots:
            return

        cursor = self.conn.cursor()
        self._insert_firm_snapshot_rows(cursor, snapshots)
        self.conn.commit()

    def _insert_firm_snapshot_rows(self, cursor, snapshots: List[FirmSnapshot]):
        """Insert firm snapshot rows using an existing cursor."""
        cursor.executemany("""
            INSERT OR REPLACE INTO firm_snapshots (
                run_id, tick, firm_id, firm_name, sector, is_baseline,
                employee_count, doctor_employee_count, medical_employee_count,
                planned_hires_count, planned_layoffs_count, actual_hires_count,
                wage_offer, price, inventory_units, output_units,
                cash_balance, revenue, profit, quality_level,
                queue_depth, visits_completed, burn_mode, zero_cash_streak
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                snapshot.run_id,
                snapshot.tick,
                snapshot.firm_id,
                snapshot.firm_name,
                snapshot.sector,
                1 if snapshot.is_baseline else 0,
                snapshot.employee_count,
                snapshot.doctor_employee_count,
                snapshot.medical_employee_count,
                snapshot.planned_hires_count,
                snapshot.planned_layoffs_count,
                snapshot.actual_hires_count,
                snapshot.wage_offer,
                snapshot.price,
                snapshot.inventory_units,
                snapshot.output_units,
                snapshot.cash_balance,
                snapshot.revenue,
                snapshot.profit,
                snapshot.quality_level,
                snapshot.queue_depth,
                snapshot.visits_completed,
                1 if snapshot.burn_mode else 0,
                snapshot.zero_cash_streak,
            )
            for snapshot in snapshots
        ])

    def get_firm_snapshots(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        firm_id: Optional[int] = None,
        sector: Optional[str] = None,
    ) -> List[Dict]:
        """Get firm snapshots for a run."""
        cursor = self.conn.cursor()

        query = """
            SELECT *
            FROM firm_snapshots
            WHERE run_id = ? AND tick >= ? AND tick <= ?
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if firm_id is not None:
            query += " AND firm_id = ?"
            params.append(firm_id)
        if sector is not None:
            query += " AND sector = ?"
            params.append(sector)
        query += " ORDER BY tick, firm_id"

        rows = cursor.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def insert_household_snapshots(self, snapshots: List[HouseholdSnapshot]):
        """Batch insert sampled household snapshots."""
        if not snapshots:
            return

        cursor = self.conn.cursor()
        self._insert_household_snapshot_rows(cursor, snapshots)
        self.conn.commit()

    def _insert_household_snapshot_rows(self, cursor, snapshots: List[HouseholdSnapshot]):
        """Insert sampled household snapshot rows using an existing cursor."""
        cursor.executemany("""
            INSERT OR REPLACE INTO household_snapshots (
                run_id, tick, household_id, state, medical_status, employer_id,
                is_employed, can_work, cash_balance, wage,
                last_wage_income, last_transfer_income, last_dividend_income,
                reservation_wage, expected_wage, skill_level,
                health, happiness, morale, food_security,
                housing_security, unemployment_duration, pending_healthcare_visits
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                snapshot.run_id,
                snapshot.tick,
                snapshot.household_id,
                snapshot.state,
                snapshot.medical_status,
                snapshot.employer_id,
                1 if snapshot.is_employed else 0,
                1 if snapshot.can_work else 0,
                snapshot.cash_balance,
                snapshot.wage,
                snapshot.last_wage_income,
                snapshot.last_transfer_income,
                snapshot.last_dividend_income,
                snapshot.reservation_wage,
                snapshot.expected_wage,
                snapshot.skill_level,
                snapshot.health,
                snapshot.happiness,
                snapshot.morale,
                snapshot.food_security,
                1 if snapshot.housing_security else 0,
                snapshot.unemployment_duration,
                snapshot.pending_healthcare_visits,
            )
            for snapshot in snapshots
        ])

    def get_household_snapshots(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        household_id: Optional[int] = None,
        state: Optional[str] = None,
    ) -> List[Dict]:
        """Get sampled household snapshots for a run."""
        cursor = self.conn.cursor()

        query = """
            SELECT *
            FROM household_snapshots
            WHERE run_id = ? AND tick >= ? AND tick <= ?
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if household_id is not None:
            query += " AND household_id = ?"
            params.append(household_id)
        if state is not None:
            query += " AND state = ?"
            params.append(state)
        query += " ORDER BY tick, household_id"

        rows = cursor.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def insert_tracked_household_history(self, history_rows: List[TrackedHouseholdHistory]):
        """Batch insert tracked-household history rows."""
        if not history_rows:
            return

        cursor = self.conn.cursor()
        self._insert_tracked_household_history_rows(cursor, history_rows)
        self.conn.commit()

    def _insert_tracked_household_history_rows(self, cursor, history_rows: List[TrackedHouseholdHistory]):
        """Insert tracked-household history rows using an existing cursor."""
        cursor.executemany("""
            INSERT OR REPLACE INTO tracked_household_history (
                run_id, tick, household_id, state, medical_status, employer_id,
                is_employed, can_work, cash_balance, wage,
                expected_wage, reservation_wage, health, happiness,
                morale, skill_level, unemployment_duration, pending_healthcare_visits
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                row.run_id,
                row.tick,
                row.household_id,
                row.state,
                row.medical_status,
                row.employer_id,
                1 if row.is_employed else 0,
                1 if row.can_work else 0,
                row.cash_balance,
                row.wage,
                row.expected_wage,
                row.reservation_wage,
                row.health,
                row.happiness,
                row.morale,
                row.skill_level,
                row.unemployment_duration,
                row.pending_healthcare_visits,
            )
            for row in history_rows
        ])

    def get_tracked_household_history(
        self,
        run_id: str,
        household_id: Optional[int] = None,
        tick_start: int = 0,
        tick_end: int = 999999,
    ) -> List[Dict]:
        """Get per-tick tracked-household history for a run."""
        cursor = self.conn.cursor()

        query = """
            SELECT *
            FROM tracked_household_history
            WHERE run_id = ? AND tick >= ? AND tick <= ?
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if household_id is not None:
            query += " AND household_id = ?"
            params.append(household_id)
        query += " ORDER BY tick, household_id"

        rows = cursor.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def insert_decision_features(self, features: List[DecisionFeature]):
        """Batch insert compact per-tick decision-context rows."""
        if not features:
            return

        cursor = self.conn.cursor()
        self._insert_decision_feature_rows(cursor, features)
        self.conn.commit()

    def _insert_decision_feature_rows(self, cursor, features: List[DecisionFeature]):
        """Insert decision-feature rows using an existing cursor."""
        cursor.executemany("""
            INSERT OR REPLACE INTO decision_features (
                run_id, tick, unemployment_short_ma, unemployment_long_ma,
                inflation_short_ma, hiring_momentum, layoff_momentum,
                vacancy_fill_ratio, wage_pressure, healthcare_pressure,
                consumer_distress_score, fiscal_stress_score,
                inequality_pressure_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                feature.run_id,
                feature.tick,
                feature.unemployment_short_ma,
                feature.unemployment_long_ma,
                feature.inflation_short_ma,
                feature.hiring_momentum,
                feature.layoff_momentum,
                feature.vacancy_fill_ratio,
                feature.wage_pressure,
                feature.healthcare_pressure,
                feature.consumer_distress_score,
                feature.fiscal_stress_score,
                feature.inequality_pressure_score,
            )
            for feature in features
        ])

    def get_decision_features(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
    ) -> List[Dict]:
        """Get ordered decision features for a run."""
        cursor = self.conn.cursor()
        rows = cursor.execute(
            """
            SELECT *
            FROM decision_features
            WHERE run_id = ? AND tick >= ? AND tick <= ?
            ORDER BY tick
            """,
            (run_id, tick_start, tick_end),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_tick_diagnostics(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
    ) -> List[Dict]:
        """Get ordered per-tick explainability diagnostics for a run."""
        cursor = self.conn.cursor()
        rows = cursor.execute(
            """
            SELECT *
            FROM tick_diagnostics
            WHERE run_id = ? AND tick >= ? AND tick <= ?
            ORDER BY tick
            """,
            (run_id, tick_start, tick_end),
        ).fetchall()
        return [dict(row) for row in rows]

    def insert_tick_diagnostics(self, diagnostics: List[TickDiagnostic]):
        """Batch insert per-tick diagnostic summary rows."""
        if not diagnostics:
            return

        cursor = self.conn.cursor()
        self._insert_tick_diagnostic_rows(cursor, diagnostics)
        self.conn.commit()

    def _insert_tick_diagnostic_rows(self, cursor, diagnostics: List[TickDiagnostic]):
        """Insert tick diagnostic rows using an existing cursor."""
        cursor.executemany("""
            INSERT OR REPLACE INTO tick_diagnostics (
                run_id, tick, unemployment_change_pp, unemployment_primary_driver,
                layoffs_count, hires_count, failed_hiring_firm_count,
                failed_hiring_roles_count, wage_mismatch_seeker_count,
                health_blocked_worker_count, inactive_work_capable_count,
                avg_health_change_pp, health_primary_driver, low_health_share,
                food_insecure_share, cash_stressed_share,
                pending_healthcare_visits_total, healthcare_queue_depth,
                healthcare_completed_count, healthcare_denied_count,
                firm_distress_primary_driver, burn_mode_firm_count,
                survival_mode_firm_count, zero_cash_firm_count,
                weak_demand_firm_count, inventory_pressure_firm_count,
                bankruptcy_count, housing_primary_driver, eviction_count,
                housing_failure_count, housing_unaffordable_count,
                housing_no_supply_count, homeless_household_count,
                shortage_active_sector_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                row.run_id,
                row.tick,
                row.unemployment_change_pp,
                row.unemployment_primary_driver,
                row.layoffs_count,
                row.hires_count,
                row.failed_hiring_firm_count,
                row.failed_hiring_roles_count,
                row.wage_mismatch_seeker_count,
                row.health_blocked_worker_count,
                row.inactive_work_capable_count,
                row.avg_health_change_pp,
                row.health_primary_driver,
                row.low_health_share,
                row.food_insecure_share,
                row.cash_stressed_share,
                row.pending_healthcare_visits_total,
                row.healthcare_queue_depth,
                row.healthcare_completed_count,
                row.healthcare_denied_count,
                row.firm_distress_primary_driver,
                row.burn_mode_firm_count,
                row.survival_mode_firm_count,
                row.zero_cash_firm_count,
                row.weak_demand_firm_count,
                row.inventory_pressure_firm_count,
                row.bankruptcy_count,
                row.housing_primary_driver,
                row.eviction_count,
                row.housing_failure_count,
                row.housing_unaffordable_count,
                row.housing_no_supply_count,
                row.homeless_household_count,
                row.shortage_active_sector_count,
            )
            for row in diagnostics
        ])

    def insert_sector_shortage_diagnostics(self, diagnostics: List[SectorShortageDiagnostic]):
        """Batch insert per-sector shortage diagnostics."""
        if not diagnostics:
            return

        cursor = self.conn.cursor()
        self._insert_sector_shortage_diagnostic_rows(cursor, diagnostics)
        self.conn.commit()

    def _insert_sector_shortage_diagnostic_rows(self, cursor, diagnostics: List[SectorShortageDiagnostic]):
        """Insert sector shortage rows using an existing cursor."""
        cursor.executemany("""
            INSERT OR REPLACE INTO sector_shortage_diagnostics (
                run_id, tick, sector, shortage_active, shortage_severity,
                primary_driver, mean_sell_through_rate, vacancy_pressure,
                inventory_pressure, price_pressure, queue_pressure,
                occupancy_pressure
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                row.run_id,
                row.tick,
                row.sector,
                1 if row.shortage_active else 0,
                row.shortage_severity,
                row.primary_driver,
                row.mean_sell_through_rate,
                row.vacancy_pressure,
                row.inventory_pressure,
                row.price_pressure,
                row.queue_pressure,
                row.occupancy_pressure,
            )
            for row in diagnostics
        ])

    def get_sector_shortage_diagnostics(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        sector: Optional[str] = None,
    ) -> List[Dict]:
        """Get ordered per-sector shortage diagnostics for a run."""
        cursor = self.conn.cursor()

        query = """
            SELECT *
            FROM sector_shortage_diagnostics
            WHERE run_id = ? AND tick >= ? AND tick <= ?
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if sector is not None:
            query += " AND sector = ?"
            params.append(sector)
        query += " ORDER BY tick, sector"

        rows = cursor.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def _normalized_regime_events(self, events: List[RegimeEvent]) -> List[RegimeEvent]:
        """Return regime events with deterministic idempotency keys."""
        duplicates_seen: dict[tuple[object, ...], int] = defaultdict(int)
        normalized: List[RegimeEvent] = []
        for event in events:
            signature = (
                event.run_id,
                event.tick,
                event.event_type,
                event.entity_type,
                event.entity_id,
                event.sector,
                event.reason_code,
                event.severity,
                event.metric_value,
                event.payload_json,
            )
            occurrence = duplicates_seen[signature]
            duplicates_seen[signature] += 1
            normalized.append(
                RegimeEvent(
                    run_id=event.run_id,
                    tick=event.tick,
                    event_type=event.event_type,
                    entity_type=event.entity_type,
                    entity_id=event.entity_id,
                    sector=event.sector,
                    reason_code=event.reason_code,
                    severity=event.severity,
                    metric_value=event.metric_value,
                    payload_json=event.payload_json,
                    event_key=event.event_key or self._event_key_from_components("regime", signature, occurrence),
                )
            )
        return normalized

    def insert_regime_events(self, events: List[RegimeEvent]):
        """Batch insert regime/state transition events."""
        if not events:
            return

        cursor = self.conn.cursor()
        self._insert_regime_event_rows(cursor, events)
        self.conn.commit()

    def _insert_regime_event_rows(self, cursor, events: List[RegimeEvent]):
        """Insert regime/state transition events using an existing cursor."""
        normalized = self._normalized_regime_events(events)
        cursor.executemany("""
            INSERT OR IGNORE INTO regime_events (
                run_id, event_key, tick, event_type, entity_type, entity_id,
                sector, reason_code, severity, metric_value, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                event.run_id,
                event.event_key,
                event.tick,
                event.event_type,
                event.entity_type,
                event.entity_id,
                event.sector,
                event.reason_code,
                event.severity,
                event.metric_value,
                event.payload_json,
            )
            for event in normalized
        ])

    def get_regime_events(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        event_type: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get ordered regime/state transition events for a run."""
        cursor = self.conn.cursor()

        query = """
            SELECT *
            FROM regime_events
            WHERE run_id = ? AND tick >= ? AND tick <= ?
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if event_type is not None:
            query += " AND event_type = ?"
            params.append(event_type)
        if entity_type is not None:
            query += " AND entity_type = ?"
            params.append(entity_type)
        query += " ORDER BY tick, event_id"

        rows = cursor.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    # =========================================================================
    # Event operations
    # =========================================================================

    def insert_labor_events(self, events: List[LaborEvent]):
        """Batch insert labor events."""
        if not events:
            return

        cursor = self.conn.cursor()
        self._insert_labor_event_rows(cursor, events)
        self.conn.commit()

    def _insert_labor_event_rows(self, cursor, events: List[LaborEvent]):
        """Insert labor events using an existing cursor."""
        normalized = self._normalized_labor_events(events)
        cursor.executemany("""
            INSERT OR IGNORE INTO labor_events (
                run_id, event_key, tick, household_id, firm_id, event_type,
                actual_wage, wage_offer, reservation_wage, skill_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                event.run_id,
                event.event_key,
                event.tick,
                event.household_id,
                event.firm_id,
                event.event_type,
                event.actual_wage,
                event.wage_offer,
                event.reservation_wage,
                event.skill_level,
            )
            for event in normalized
        ])

    def insert_healthcare_events(self, events: List[HealthcareEvent]):
        """Batch insert healthcare events."""
        if not events:
            return

        cursor = self.conn.cursor()
        self._insert_healthcare_event_rows(cursor, events)
        self.conn.commit()

    def _insert_healthcare_event_rows(self, cursor, events: List[HealthcareEvent]):
        """Insert healthcare events using an existing cursor."""
        normalized = self._normalized_healthcare_events(events)
        cursor.executemany("""
            INSERT OR IGNORE INTO healthcare_events (
                run_id, event_key, tick, household_id, firm_id, event_type,
                queue_wait_ticks, visit_price, household_cost, government_cost,
                health_before, health_after
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                event.run_id,
                event.event_key,
                event.tick,
                event.household_id,
                event.firm_id,
                event.event_type,
                event.queue_wait_ticks,
                event.visit_price,
                event.household_cost,
                event.government_cost,
                event.health_before,
                event.health_after,
            )
            for event in normalized
        ])

    def insert_policy_actions(self, actions: List[PolicyAction]):
        """Batch insert policy actions."""
        if not actions:
            return

        cursor = self.conn.cursor()
        self._insert_policy_action_rows(cursor, actions)
        self.conn.commit()

    def _insert_policy_action_rows(self, cursor, actions: List[PolicyAction]):
        """Insert policy actions using an existing cursor."""
        normalized = self._normalized_policy_actions(actions)
        cursor.executemany("""
            INSERT OR IGNORE INTO policy_actions (
                run_id, event_key, tick, actor, action_type, payload_json, reason_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                action.run_id,
                action.event_key,
                action.tick,
                action.actor,
                action.action_type,
                action.payload_json,
                action.reason_summary,
            )
            for action in normalized
        ])

    def persist_flush_bundle(
        self,
        run_id: str,
        last_fully_persisted_tick: int,
        tick_metrics: Optional[List[TickMetrics]] = None,
        sector_tick_metrics: Optional[List[SectorTickMetrics]] = None,
        decision_features: Optional[List[DecisionFeature]] = None,
        firm_snapshots: Optional[List[FirmSnapshot]] = None,
        household_snapshots: Optional[List[HouseholdSnapshot]] = None,
        tracked_household_history: Optional[List[TrackedHouseholdHistory]] = None,
        labor_events: Optional[List[LaborEvent]] = None,
        healthcare_events: Optional[List[HealthcareEvent]] = None,
        policy_actions: Optional[List[PolicyAction]] = None,
        tick_diagnostics: Optional[List[TickDiagnostic]] = None,
        sector_shortage_diagnostics: Optional[List[SectorShortageDiagnostic]] = None,
        regime_events: Optional[List[RegimeEvent]] = None,
    ) -> None:
        """Persist one buffered bundle atomically so partial flushes cannot leak."""
        cursor = self.conn.cursor()
        try:
            if tick_metrics:
                self._insert_tick_metrics_rows(cursor, tick_metrics)
            if sector_tick_metrics:
                self._insert_sector_tick_metrics_rows(cursor, sector_tick_metrics)
            if decision_features:
                self._insert_decision_feature_rows(cursor, decision_features)
            if tick_diagnostics:
                self._insert_tick_diagnostic_rows(cursor, tick_diagnostics)
            if sector_shortage_diagnostics:
                self._insert_sector_shortage_diagnostic_rows(cursor, sector_shortage_diagnostics)
            if firm_snapshots:
                self._insert_firm_snapshot_rows(cursor, firm_snapshots)
            if household_snapshots:
                self._insert_household_snapshot_rows(cursor, household_snapshots)
            if tracked_household_history:
                self._insert_tracked_household_history_rows(cursor, tracked_household_history)
            if labor_events:
                self._insert_labor_event_rows(cursor, labor_events)
            if healthcare_events:
                self._insert_healthcare_event_rows(cursor, healthcare_events)
            if policy_actions:
                self._insert_policy_action_rows(cursor, policy_actions)
            if regime_events:
                self._insert_regime_event_rows(cursor, regime_events)
            self._update_run_flush_metadata(cursor, run_id, last_fully_persisted_tick)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

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
                AVG(tick_duration_ms) as avg_tick_duration_ms,
                AVG(labor_force_participation) as avg_labor_force_participation,
                AVG(open_vacancies) as avg_open_vacancies,
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

    def get_policy_actions(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        actor: Optional[str] = None,
        action_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get ordered policy actions for a run."""
        cursor = self.conn.cursor()
        query = """
            SELECT *
            FROM policy_actions
            WHERE run_id = ? AND tick >= ? AND tick <= ?
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if actor is not None:
            query += " AND actor = ?"
            params.append(actor)
        if action_type is not None:
            query += " AND action_type = ?"
            params.append(action_type)
        query += " ORDER BY tick, action_id"

        rows = cursor.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

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

        stats['total_sector_rows'] = cursor.execute(
            "SELECT COUNT(*) FROM sector_tick_metrics"
        ).fetchone()[0]

        stats['total_firm_snapshots'] = cursor.execute(
            "SELECT COUNT(*) FROM firm_snapshots"
        ).fetchone()[0]

        stats['total_household_snapshots'] = cursor.execute(
            "SELECT COUNT(*) FROM household_snapshots"
        ).fetchone()[0]

        stats['total_tracked_household_rows'] = cursor.execute(
            "SELECT COUNT(*) FROM tracked_household_history"
        ).fetchone()[0]

        stats['total_decision_feature_rows'] = cursor.execute(
            "SELECT COUNT(*) FROM decision_features"
        ).fetchone()[0]

        stats['total_tick_diagnostic_rows'] = cursor.execute(
            "SELECT COUNT(*) FROM tick_diagnostics"
        ).fetchone()[0]

        stats['total_sector_shortage_rows'] = cursor.execute(
            "SELECT COUNT(*) FROM sector_shortage_diagnostics"
        ).fetchone()[0]

        stats['total_labor_events'] = cursor.execute(
            "SELECT COUNT(*) FROM labor_events"
        ).fetchone()[0]

        stats['total_healthcare_events'] = cursor.execute(
            "SELECT COUNT(*) FROM healthcare_events"
        ).fetchone()[0]

        stats['total_policy_actions'] = cursor.execute(
            "SELECT COUNT(*) FROM policy_actions"
        ).fetchone()[0]

        stats['total_regime_events'] = cursor.execute(
            "SELECT COUNT(*) FROM regime_events"
        ).fetchone()[0]

        # Database size
        if os.path.exists(self.db_path):
            stats['db_size_mb'] = os.path.getsize(self.db_path) / (1024 * 1024)
        else:
            stats['db_size_mb'] = 0

        return stats
