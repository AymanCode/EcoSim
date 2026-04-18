"""
PostgreSQL/TimescaleDB manager for EcoSim data warehouse operations.

This module mirrors the SQLite DatabaseManager API so callers can switch
backends via configuration without changing simulation logic.
"""

from __future__ import annotations

import hashlib
import json
import os
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
        "tick_duration_ms",
        "labor_force_participation",
        "open_vacancies",
        "total_hires",
        "total_layoffs",
        "healthcare_queue_depth",
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
            from psycopg.types.json import Jsonb
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required for PostgreSQL backend. Install with `pip install psycopg[binary]`."
            ) from exc

        self.psycopg = psycopg
        self.Jsonb = Jsonb
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
                    run_id, status, seed, num_households, num_firms,
                    config_json, code_version, schema_version, decision_feature_version,
                    diagnostics_version,
                    last_fully_persisted_tick, analysis_ready, termination_reason,
                    description, tags
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run.run_id,
                    run.status,
                    run.seed,
                    run.num_households,
                    run.num_firms,
                    self.Jsonb(json.loads(run.config_json)) if run.config_json else None,
                    run.code_version,
                    run.schema_version,
                    run.decision_feature_version,
                    run.diagnostics_version,
                    run.last_fully_persisted_tick,
                    run.analysis_ready,
                    run.termination_reason,
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
        last_fully_persisted_tick: Optional[int] = None,
        analysis_ready: Optional[bool] = None,
        termination_reason: Optional[str] = None,
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
                        final_gov_balance = %s,
                        last_fully_persisted_tick = COALESCE(%s, last_fully_persisted_tick),
                        analysis_ready = COALESCE(%s, analysis_ready),
                        termination_reason = COALESCE(%s, termination_reason)
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
                        last_fully_persisted_tick,
                        analysis_ready,
                        termination_reason,
                        run_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE simulation_runs
                    SET status = %s,
                        ended_at = NOW(),
                        total_ticks = %s,
                        last_fully_persisted_tick = COALESCE(%s, last_fully_persisted_tick),
                        analysis_ready = COALESCE(%s, analysis_ready),
                        termination_reason = COALESCE(%s, termination_reason)
                    WHERE run_id = %s
                    """,
                    (status, total_ticks, last_fully_persisted_tick, analysis_ready, termination_reason, run_id),
                )
        self.conn.commit()

    def _update_run_flush_metadata(self, cursor, run_id: str, last_fully_persisted_tick: int):
        """Advance the persisted watermark for a run inside an active transaction."""
        cursor.execute(
            """
            UPDATE simulation_runs
            SET last_fully_persisted_tick = GREATEST(COALESCE(last_fully_persisted_tick, 0), %s)
            WHERE run_id = %s
            """,
            (last_fully_persisted_tick, run_id),
        )

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

    @staticmethod
    def _normalize_run_row(row: Dict) -> Dict:
        """Normalize JSON/boolean storage fields before constructing dataclasses."""
        normalized = dict(row)
        if normalized.get("config_json") is not None and not isinstance(normalized["config_json"], str):
            normalized["config_json"] = json.dumps(normalized["config_json"], sort_keys=True)
        return normalized

    def get_run(self, run_id: str) -> Optional[SimulationRun]:
        """Fetch one run by ID."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM simulation_runs WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
        if row:
            return SimulationRun(**self._normalize_run_row(row))
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
        return [SimulationRun(**self._normalize_run_row(row)) for row in rows]

    # =========================================================================
    # Tick metrics operations
    # =========================================================================

    def insert_tick_metrics(self, metrics: List[TickMetrics]):
        """Batch insert tick metrics with upsert semantics."""
        if not metrics:
            return

        with self.conn.cursor() as cur:
            self._insert_tick_metrics_rows(cur, metrics)
        self.conn.commit()

    def _insert_tick_metrics_rows(self, cur, metrics: List[TickMetrics]):
        """Insert tick metrics using an existing cursor."""
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
                m.tick_duration_ms,
                m.labor_force_participation,
                m.open_vacancies,
                m.total_hires,
                m.total_layoffs,
                m.healthcare_queue_depth,
                m.total_firms,
                m.struggling_firms,
                m.avg_food_price,
                m.avg_housing_price,
                m.avg_services_price,
            )
            for m in metrics
        ]

        cur.executemany(
            """
            INSERT INTO tick_metrics (
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
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
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
                tick_duration_ms = EXCLUDED.tick_duration_ms,
                labor_force_participation = EXCLUDED.labor_force_participation,
                open_vacancies = EXCLUDED.open_vacancies,
                total_hires = EXCLUDED.total_hires,
                total_layoffs = EXCLUDED.total_layoffs,
                healthcare_queue_depth = EXCLUDED.healthcare_queue_depth,
                total_firms = EXCLUDED.total_firms,
                struggling_firms = EXCLUDED.struggling_firms,
                avg_food_price = EXCLUDED.avg_food_price,
                avg_housing_price = EXCLUDED.avg_housing_price,
                avg_services_price = EXCLUDED.avg_services_price
            """,
            rows,
        )

    def insert_sector_tick_metrics(self, metrics: List[SectorTickMetrics]):
        """Batch insert sector tick metrics with upsert semantics."""
        if not metrics:
            return

        with self.conn.cursor() as cur:
            self._insert_sector_tick_metrics_rows(cur, metrics)
        self.conn.commit()

    def _insert_sector_tick_metrics_rows(self, cur, metrics: List[SectorTickMetrics]):
        """Insert sector metrics using an existing cursor."""
        rows = [
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
        ]

        cur.executemany(
            """
            INSERT INTO sector_tick_metrics (
                run_id, tick, sector,
                firm_count, employees, vacancies,
                mean_wage_offer, mean_price, mean_inventory,
                total_output, total_revenue, total_profit
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (run_id, tick, sector) DO UPDATE SET
                firm_count = EXCLUDED.firm_count,
                employees = EXCLUDED.employees,
                vacancies = EXCLUDED.vacancies,
                mean_wage_offer = EXCLUDED.mean_wage_offer,
                mean_price = EXCLUDED.mean_price,
                mean_inventory = EXCLUDED.mean_inventory,
                total_output = EXCLUDED.total_output,
                total_revenue = EXCLUDED.total_revenue,
                total_profit = EXCLUDED.total_profit
            """,
            rows,
        )

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
                    AVG(tick_duration_ms) AS avg_tick_duration_ms,
                    AVG(labor_force_participation) AS avg_labor_force_participation,
                    AVG(open_vacancies) AS avg_open_vacancies,
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

    def get_sector_tick_metrics(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        sector: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch ordered sector tick metrics for a run."""
        query = """
            SELECT *
            FROM sector_tick_metrics
            WHERE run_id = %s AND tick >= %s AND tick <= %s
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if sector is not None:
            query += " AND sector = %s"
            params.append(sector)
        query += " ORDER BY tick, sector"

        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_sector_summary(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        sector: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch aggregated sector summary rows for a run over a tick range."""
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
            WHERE run_id = %s AND tick >= %s AND tick <= %s
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if sector is not None:
            query += " AND sector = %s"
            params.append(sector)
        query += " GROUP BY sector ORDER BY sector"

        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_run_comparison(self, run_ids: List[str]) -> List[Dict]:
        """Fetch comparison rows for a set of run IDs."""
        if not run_ids:
            return []

        placeholders = ", ".join(["%s"] * len(run_ids))
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

        with self.conn.cursor() as cur:
            cur.execute(query, tuple(run_ids))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def insert_firm_snapshots(self, snapshots: List[FirmSnapshot]):
        """Batch insert firm snapshots with upsert semantics."""
        if not snapshots:
            return

        with self.conn.cursor() as cur:
            self._insert_firm_snapshot_rows(cur, snapshots)
        self.conn.commit()

    def _insert_firm_snapshot_rows(self, cur, snapshots: List[FirmSnapshot]):
        """Insert firm snapshots using an existing cursor."""
        rows = [
            (
                snapshot.run_id,
                snapshot.tick,
                snapshot.firm_id,
                snapshot.firm_name,
                snapshot.sector,
                snapshot.is_baseline,
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
                snapshot.burn_mode,
                snapshot.zero_cash_streak,
            )
            for snapshot in snapshots
        ]

        cur.executemany(
            """
            INSERT INTO firm_snapshots (
                run_id, tick, firm_id, firm_name, sector, is_baseline,
                employee_count, doctor_employee_count, medical_employee_count,
                planned_hires_count, planned_layoffs_count, actual_hires_count,
                wage_offer, price, inventory_units, output_units,
                cash_balance, revenue, profit, quality_level,
                queue_depth, visits_completed, burn_mode, zero_cash_streak
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (run_id, tick, firm_id) DO UPDATE SET
                firm_name = EXCLUDED.firm_name,
                sector = EXCLUDED.sector,
                is_baseline = EXCLUDED.is_baseline,
                employee_count = EXCLUDED.employee_count,
                doctor_employee_count = EXCLUDED.doctor_employee_count,
                medical_employee_count = EXCLUDED.medical_employee_count,
                planned_hires_count = EXCLUDED.planned_hires_count,
                planned_layoffs_count = EXCLUDED.planned_layoffs_count,
                actual_hires_count = EXCLUDED.actual_hires_count,
                wage_offer = EXCLUDED.wage_offer,
                price = EXCLUDED.price,
                inventory_units = EXCLUDED.inventory_units,
                output_units = EXCLUDED.output_units,
                cash_balance = EXCLUDED.cash_balance,
                revenue = EXCLUDED.revenue,
                profit = EXCLUDED.profit,
                quality_level = EXCLUDED.quality_level,
                queue_depth = EXCLUDED.queue_depth,
                visits_completed = EXCLUDED.visits_completed,
                burn_mode = EXCLUDED.burn_mode,
                zero_cash_streak = EXCLUDED.zero_cash_streak
            """,
            rows,
        )

    def get_firm_snapshots(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        firm_id: Optional[int] = None,
        sector: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch ordered firm snapshots for a run."""
        query = """
            SELECT *
            FROM firm_snapshots
            WHERE run_id = %s AND tick >= %s AND tick <= %s
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if firm_id is not None:
            query += " AND firm_id = %s"
            params.append(firm_id)
        if sector is not None:
            query += " AND sector = %s"
            params.append(sector)
        query += " ORDER BY tick, firm_id"

        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def insert_household_snapshots(self, snapshots: List[HouseholdSnapshot]):
        """Batch insert sampled household snapshots with upsert semantics."""
        if not snapshots:
            return

        with self.conn.cursor() as cur:
            self._insert_household_snapshot_rows(cur, snapshots)
        self.conn.commit()

    def _insert_household_snapshot_rows(self, cur, snapshots: List[HouseholdSnapshot]):
        """Insert household snapshots using an existing cursor."""
        rows = [
            (
                snapshot.run_id,
                snapshot.tick,
                snapshot.household_id,
                snapshot.state,
                snapshot.medical_status,
                snapshot.employer_id,
                snapshot.is_employed,
                snapshot.can_work,
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
                snapshot.housing_security,
                snapshot.unemployment_duration,
                snapshot.pending_healthcare_visits,
            )
            for snapshot in snapshots
        ]

        cur.executemany(
            """
            INSERT INTO household_snapshots (
                run_id, tick, household_id, state, medical_status, employer_id,
                is_employed, can_work, cash_balance, wage,
                last_wage_income, last_transfer_income, last_dividend_income,
                reservation_wage, expected_wage, skill_level,
                health, happiness, morale, food_security,
                housing_security, unemployment_duration, pending_healthcare_visits
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (run_id, tick, household_id) DO UPDATE SET
                state = EXCLUDED.state,
                medical_status = EXCLUDED.medical_status,
                employer_id = EXCLUDED.employer_id,
                is_employed = EXCLUDED.is_employed,
                can_work = EXCLUDED.can_work,
                cash_balance = EXCLUDED.cash_balance,
                wage = EXCLUDED.wage,
                last_wage_income = EXCLUDED.last_wage_income,
                last_transfer_income = EXCLUDED.last_transfer_income,
                last_dividend_income = EXCLUDED.last_dividend_income,
                reservation_wage = EXCLUDED.reservation_wage,
                expected_wage = EXCLUDED.expected_wage,
                skill_level = EXCLUDED.skill_level,
                health = EXCLUDED.health,
                happiness = EXCLUDED.happiness,
                morale = EXCLUDED.morale,
                food_security = EXCLUDED.food_security,
                housing_security = EXCLUDED.housing_security,
                unemployment_duration = EXCLUDED.unemployment_duration,
                pending_healthcare_visits = EXCLUDED.pending_healthcare_visits
            """,
            rows,
        )

    def get_household_snapshots(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        household_id: Optional[int] = None,
        state: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch ordered sampled household snapshots for a run."""
        query = """
            SELECT *
            FROM household_snapshots
            WHERE run_id = %s AND tick >= %s AND tick <= %s
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if household_id is not None:
            query += " AND household_id = %s"
            params.append(household_id)
        if state is not None:
            query += " AND state = %s"
            params.append(state)
        query += " ORDER BY tick, household_id"

        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def insert_tracked_household_history(self, history_rows: List[TrackedHouseholdHistory]):
        """Batch insert tracked-household history rows with upsert semantics."""
        if not history_rows:
            return

        with self.conn.cursor() as cur:
            self._insert_tracked_household_history_rows(cur, history_rows)
        self.conn.commit()

    def _insert_tracked_household_history_rows(self, cur, history_rows: List[TrackedHouseholdHistory]):
        """Insert tracked-household history using an existing cursor."""
        rows = [
            (
                row.run_id,
                row.tick,
                row.household_id,
                row.state,
                row.medical_status,
                row.employer_id,
                row.is_employed,
                row.can_work,
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
        ]

        cur.executemany(
            """
            INSERT INTO tracked_household_history (
                run_id, tick, household_id, state, medical_status, employer_id,
                is_employed, can_work, cash_balance, wage,
                expected_wage, reservation_wage, health, happiness,
                morale, skill_level, unemployment_duration, pending_healthcare_visits
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (run_id, tick, household_id) DO UPDATE SET
                state = EXCLUDED.state,
                medical_status = EXCLUDED.medical_status,
                employer_id = EXCLUDED.employer_id,
                is_employed = EXCLUDED.is_employed,
                can_work = EXCLUDED.can_work,
                cash_balance = EXCLUDED.cash_balance,
                wage = EXCLUDED.wage,
                expected_wage = EXCLUDED.expected_wage,
                reservation_wage = EXCLUDED.reservation_wage,
                health = EXCLUDED.health,
                happiness = EXCLUDED.happiness,
                morale = EXCLUDED.morale,
                skill_level = EXCLUDED.skill_level,
                unemployment_duration = EXCLUDED.unemployment_duration,
                pending_healthcare_visits = EXCLUDED.pending_healthcare_visits
            """,
            rows,
        )

    def get_tracked_household_history(
        self,
        run_id: str,
        household_id: Optional[int] = None,
        tick_start: int = 0,
        tick_end: int = 999999,
    ) -> List[Dict]:
        """Fetch ordered tracked-household history for a run."""
        query = """
            SELECT *
            FROM tracked_household_history
            WHERE run_id = %s AND tick >= %s AND tick <= %s
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if household_id is not None:
            query += " AND household_id = %s"
            params.append(household_id)
        query += " ORDER BY tick, household_id"

        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def insert_decision_features(self, features: List[DecisionFeature]):
        """Batch insert compact decision-context rows with upsert semantics."""
        if not features:
            return

        with self.conn.cursor() as cur:
            self._insert_decision_feature_rows(cur, features)
        self.conn.commit()

    def _insert_decision_feature_rows(self, cur, features: List[DecisionFeature]):
        """Insert decision features using an existing cursor."""
        rows = [
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
        ]

        cur.executemany(
            """
            INSERT INTO decision_features (
                run_id, tick, unemployment_short_ma, unemployment_long_ma,
                inflation_short_ma, hiring_momentum, layoff_momentum,
                vacancy_fill_ratio, wage_pressure, healthcare_pressure,
                consumer_distress_score, fiscal_stress_score,
                inequality_pressure_score
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (run_id, tick) DO UPDATE SET
                unemployment_short_ma = EXCLUDED.unemployment_short_ma,
                unemployment_long_ma = EXCLUDED.unemployment_long_ma,
                inflation_short_ma = EXCLUDED.inflation_short_ma,
                hiring_momentum = EXCLUDED.hiring_momentum,
                layoff_momentum = EXCLUDED.layoff_momentum,
                vacancy_fill_ratio = EXCLUDED.vacancy_fill_ratio,
                wage_pressure = EXCLUDED.wage_pressure,
                healthcare_pressure = EXCLUDED.healthcare_pressure,
                consumer_distress_score = EXCLUDED.consumer_distress_score,
                fiscal_stress_score = EXCLUDED.fiscal_stress_score,
                inequality_pressure_score = EXCLUDED.inequality_pressure_score
            """,
            rows,
        )

    def get_decision_features(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
    ) -> List[Dict]:
        """Fetch ordered decision features for a run."""
        query = """
            SELECT *
            FROM decision_features
            WHERE run_id = %s AND tick >= %s AND tick <= %s
            ORDER BY tick
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (run_id, tick_start, tick_end))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_tick_diagnostics(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
    ) -> List[Dict]:
        """Fetch ordered per-tick explainability diagnostics for a run."""
        query = """
            SELECT *
            FROM tick_diagnostics
            WHERE run_id = %s AND tick >= %s AND tick <= %s
            ORDER BY tick
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (run_id, tick_start, tick_end))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def insert_tick_diagnostics(self, diagnostics: List[TickDiagnostic]):
        """Batch insert compact per-tick diagnostic rows with upsert semantics."""
        if not diagnostics:
            return

        with self.conn.cursor() as cur:
            self._insert_tick_diagnostic_rows(cur, diagnostics)
        self.conn.commit()

    def _insert_tick_diagnostic_rows(self, cur, diagnostics: List[TickDiagnostic]):
        """Insert tick diagnostics using an existing cursor."""
        rows = [
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
        ]
        cur.executemany(
            """
            INSERT INTO tick_diagnostics (
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
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (run_id, tick) DO UPDATE SET
                unemployment_change_pp = EXCLUDED.unemployment_change_pp,
                unemployment_primary_driver = EXCLUDED.unemployment_primary_driver,
                layoffs_count = EXCLUDED.layoffs_count,
                hires_count = EXCLUDED.hires_count,
                failed_hiring_firm_count = EXCLUDED.failed_hiring_firm_count,
                failed_hiring_roles_count = EXCLUDED.failed_hiring_roles_count,
                wage_mismatch_seeker_count = EXCLUDED.wage_mismatch_seeker_count,
                health_blocked_worker_count = EXCLUDED.health_blocked_worker_count,
                inactive_work_capable_count = EXCLUDED.inactive_work_capable_count,
                avg_health_change_pp = EXCLUDED.avg_health_change_pp,
                health_primary_driver = EXCLUDED.health_primary_driver,
                low_health_share = EXCLUDED.low_health_share,
                food_insecure_share = EXCLUDED.food_insecure_share,
                cash_stressed_share = EXCLUDED.cash_stressed_share,
                pending_healthcare_visits_total = EXCLUDED.pending_healthcare_visits_total,
                healthcare_queue_depth = EXCLUDED.healthcare_queue_depth,
                healthcare_completed_count = EXCLUDED.healthcare_completed_count,
                healthcare_denied_count = EXCLUDED.healthcare_denied_count,
                firm_distress_primary_driver = EXCLUDED.firm_distress_primary_driver,
                burn_mode_firm_count = EXCLUDED.burn_mode_firm_count,
                survival_mode_firm_count = EXCLUDED.survival_mode_firm_count,
                zero_cash_firm_count = EXCLUDED.zero_cash_firm_count,
                weak_demand_firm_count = EXCLUDED.weak_demand_firm_count,
                inventory_pressure_firm_count = EXCLUDED.inventory_pressure_firm_count,
                bankruptcy_count = EXCLUDED.bankruptcy_count,
                housing_primary_driver = EXCLUDED.housing_primary_driver,
                eviction_count = EXCLUDED.eviction_count,
                housing_failure_count = EXCLUDED.housing_failure_count,
                housing_unaffordable_count = EXCLUDED.housing_unaffordable_count,
                housing_no_supply_count = EXCLUDED.housing_no_supply_count,
                homeless_household_count = EXCLUDED.homeless_household_count,
                shortage_active_sector_count = EXCLUDED.shortage_active_sector_count
            """,
            rows,
        )

    def insert_sector_shortage_diagnostics(self, diagnostics: List[SectorShortageDiagnostic]):
        """Batch insert per-sector shortage diagnostic rows with upsert semantics."""
        if not diagnostics:
            return

        with self.conn.cursor() as cur:
            self._insert_sector_shortage_diagnostic_rows(cur, diagnostics)
        self.conn.commit()

    def _insert_sector_shortage_diagnostic_rows(self, cur, diagnostics: List[SectorShortageDiagnostic]):
        """Insert sector shortage diagnostics using an existing cursor."""
        rows = [
            (
                row.run_id,
                row.tick,
                row.sector,
                row.shortage_active,
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
        ]
        cur.executemany(
            """
            INSERT INTO sector_shortage_diagnostics (
                run_id, tick, sector, shortage_active, shortage_severity,
                primary_driver, mean_sell_through_rate, vacancy_pressure,
                inventory_pressure, price_pressure, queue_pressure,
                occupancy_pressure
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id, tick, sector) DO UPDATE SET
                shortage_active = EXCLUDED.shortage_active,
                shortage_severity = EXCLUDED.shortage_severity,
                primary_driver = EXCLUDED.primary_driver,
                mean_sell_through_rate = EXCLUDED.mean_sell_through_rate,
                vacancy_pressure = EXCLUDED.vacancy_pressure,
                inventory_pressure = EXCLUDED.inventory_pressure,
                price_pressure = EXCLUDED.price_pressure,
                queue_pressure = EXCLUDED.queue_pressure,
                occupancy_pressure = EXCLUDED.occupancy_pressure
            """,
            rows,
        )

    def get_sector_shortage_diagnostics(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        sector: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch ordered per-sector shortage diagnostics for a run."""
        query = """
            SELECT *
            FROM sector_shortage_diagnostics
            WHERE run_id = %s AND tick >= %s AND tick <= %s
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if sector is not None:
            query += " AND sector = %s"
            params.append(sector)
        query += " ORDER BY tick, sector"

        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
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

        with self.conn.cursor() as cur:
            self._insert_regime_event_rows(cur, events)
        self.conn.commit()

    def _insert_regime_event_rows(self, cur, events: List[RegimeEvent]):
        """Insert regime/state transition events using an existing cursor."""
        rows = [
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
                self.Jsonb(json.loads(event.payload_json)) if event.payload_json else None,
            )
            for event in self._normalized_regime_events(events)
        ]
        cur.executemany(
            """
            INSERT INTO regime_events (
                run_id, event_key, tick, event_type, entity_type, entity_id,
                sector, reason_code, severity, metric_value, payload_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id, event_key) DO NOTHING
            """,
            rows,
        )

    def get_regime_events(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        event_type: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch ordered regime/state transition events for a run."""
        query = """
            SELECT *
            FROM regime_events
            WHERE run_id = %s AND tick >= %s AND tick <= %s
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if event_type is not None:
            query += " AND event_type = %s"
            params.append(event_type)
        if entity_type is not None:
            query += " AND entity_type = %s"
            params.append(entity_type)
        query += " ORDER BY tick, event_id"

        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    # =========================================================================
    # Event operations
    # =========================================================================

    def insert_labor_events(self, events: List[LaborEvent]):
        """Batch insert labor events."""
        if not events:
            return

        with self.conn.cursor() as cur:
            self._insert_labor_event_rows(cur, events)
        self.conn.commit()

    def _insert_labor_event_rows(self, cur, events: List[LaborEvent]):
        """Insert labor events using an existing cursor."""
        rows = [
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
            for event in self._normalized_labor_events(events)
        ]
        cur.executemany(
            """
            INSERT INTO labor_events (
                run_id, event_key, tick, household_id, firm_id, event_type,
                actual_wage, wage_offer, reservation_wage, skill_level
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id, event_key) DO NOTHING
            """,
            rows,
        )

    def insert_healthcare_events(self, events: List[HealthcareEvent]):
        """Batch insert healthcare events."""
        if not events:
            return

        with self.conn.cursor() as cur:
            self._insert_healthcare_event_rows(cur, events)
        self.conn.commit()

    def _insert_healthcare_event_rows(self, cur, events: List[HealthcareEvent]):
        """Insert healthcare events using an existing cursor."""
        rows = [
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
            for event in self._normalized_healthcare_events(events)
        ]
        cur.executemany(
            """
            INSERT INTO healthcare_events (
                run_id, event_key, tick, household_id, firm_id, event_type,
                queue_wait_ticks, visit_price, household_cost, government_cost,
                health_before, health_after
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id, event_key) DO NOTHING
            """,
            rows,
        )

    def insert_policy_actions(self, actions: List[PolicyAction]):
        """Batch insert policy actions."""
        if not actions:
            return

        with self.conn.cursor() as cur:
            self._insert_policy_action_rows(cur, actions)
        self.conn.commit()

    def _insert_policy_action_rows(self, cur, actions: List[PolicyAction]):
        """Insert policy actions using an existing cursor."""
        rows = [
            (
                action.run_id,
                action.event_key,
                action.tick,
                action.actor,
                action.action_type,
                self.Jsonb(json.loads(action.payload_json)),
                action.reason_summary,
            )
            for action in self._normalized_policy_actions(actions)
        ]
        cur.executemany(
            """
            INSERT INTO policy_actions (
                run_id, event_key, tick, actor, action_type, payload_json, reason_summary
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id, event_key) DO NOTHING
            """,
            rows,
        )

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
        try:
            with self.conn.cursor() as cur:
                if tick_metrics:
                    self._insert_tick_metrics_rows(cur, tick_metrics)
                if sector_tick_metrics:
                    self._insert_sector_tick_metrics_rows(cur, sector_tick_metrics)
                if decision_features:
                    self._insert_decision_feature_rows(cur, decision_features)
                if tick_diagnostics:
                    self._insert_tick_diagnostic_rows(cur, tick_diagnostics)
                if sector_shortage_diagnostics:
                    self._insert_sector_shortage_diagnostic_rows(cur, sector_shortage_diagnostics)
                if firm_snapshots:
                    self._insert_firm_snapshot_rows(cur, firm_snapshots)
                if household_snapshots:
                    self._insert_household_snapshot_rows(cur, household_snapshots)
                if tracked_household_history:
                    self._insert_tracked_household_history_rows(cur, tracked_household_history)
                if labor_events:
                    self._insert_labor_event_rows(cur, labor_events)
                if healthcare_events:
                    self._insert_healthcare_event_rows(cur, healthcare_events)
                if policy_actions:
                    self._insert_policy_action_rows(cur, policy_actions)
                if regime_events:
                    self._insert_regime_event_rows(cur, regime_events)
                self._update_run_flush_metadata(cur, run_id, last_fully_persisted_tick)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

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

    def get_policy_actions(
        self,
        run_id: str,
        tick_start: int = 0,
        tick_end: int = 999999,
        actor: Optional[str] = None,
        action_type: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch ordered policy actions for a run."""
        query = """
            SELECT *
            FROM policy_actions
            WHERE run_id = %s AND tick >= %s AND tick <= %s
        """
        params: List[object] = [run_id, tick_start, tick_end]
        if actor is not None:
            query += " AND actor = %s"
            params.append(actor)
        if action_type is not None:
            query += " AND action_type = %s"
            params.append(action_type)
        query += " ORDER BY tick, action_id"

        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        return [dict(row) for row in rows]

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

            cur.execute("SELECT COUNT(*) AS total_sector_rows FROM sector_tick_metrics")
            total_sector_rows = cur.fetchone()["total_sector_rows"]

            cur.execute("SELECT COUNT(*) AS total_firm_snapshots FROM firm_snapshots")
            total_firm_snapshots = cur.fetchone()["total_firm_snapshots"]

            cur.execute("SELECT COUNT(*) AS total_household_snapshots FROM household_snapshots")
            total_household_snapshots = cur.fetchone()["total_household_snapshots"]

            cur.execute("SELECT COUNT(*) AS total_tracked_household_rows FROM tracked_household_history")
            total_tracked_household_rows = cur.fetchone()["total_tracked_household_rows"]

            cur.execute("SELECT COUNT(*) AS total_decision_feature_rows FROM decision_features")
            total_decision_feature_rows = cur.fetchone()["total_decision_feature_rows"]

            cur.execute("SELECT COUNT(*) AS total_labor_events FROM labor_events")
            total_labor_events = cur.fetchone()["total_labor_events"]

            cur.execute("SELECT COUNT(*) AS total_healthcare_events FROM healthcare_events")
            total_healthcare_events = cur.fetchone()["total_healthcare_events"]

            cur.execute("SELECT COUNT(*) AS total_policy_actions FROM policy_actions")
            total_policy_actions = cur.fetchone()["total_policy_actions"]

            cur.execute("SELECT pg_database_size(current_database()) AS db_size_bytes")
            db_size_bytes = cur.fetchone()["db_size_bytes"]

        return {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "total_ticks": total_ticks,
            "total_sector_rows": total_sector_rows,
            "total_firm_snapshots": total_firm_snapshots,
            "total_household_snapshots": total_household_snapshots,
            "total_tracked_household_rows": total_tracked_household_rows,
            "total_decision_feature_rows": total_decision_feature_rows,
            "total_labor_events": total_labor_events,
            "total_healthcare_events": total_healthcare_events,
            "total_policy_actions": total_policy_actions,
            "db_size_mb": float(db_size_bytes) / (1024 * 1024),
        }
