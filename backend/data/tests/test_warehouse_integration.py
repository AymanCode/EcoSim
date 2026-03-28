import random
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data.db_manager import DatabaseManager
from server import SimulationManager


def _apply_sqlite_schema(db_path: Path) -> None:
    """Create the current SQLite warehouse schema in a temporary database."""
    schema_path = BACKEND_ROOT / "data" / "schema.sql"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def _run_ticks_and_persist(manager: SimulationManager, num_ticks: int) -> tuple[int, int, int, int, int, int, int, int]:
    """Drive the same warehouse write path used by the live server loop."""
    expected_sector_rows = 0
    expected_decision_features = 0
    expected_tick_diagnostics = 0
    expected_sector_shortage_rows = 0
    expected_firm_snapshots = 0
    expected_household_snapshots = 0
    expected_tracked_household_rows = 0
    expected_regime_events = 0

    for _ in range(num_ticks):
        tick_start = time.perf_counter()
        policy_before = manager._snapshot_government_policy()
        manager.economy.step()
        manager.tick += 1
        manager._record_automatic_policy_changes(
            policy_before=policy_before,
            policy_after=manager._snapshot_government_policy(),
        )
        manager._buffer_simulation_events()
        expected_regime_events += len(getattr(manager.economy, "last_regime_events", []) or [])

        gdp = float(sum(manager.economy.last_tick_revenue.values()))
        current_gov_cash = float(manager.economy.government.cash_balance)
        if not hasattr(manager, "prev_gov_cash"):
            manager.prev_gov_cash = current_gov_cash
        fiscal_balance = float(current_gov_cash - manager.prev_gov_cash)
        manager.prev_gov_cash = current_gov_cash

        tick_compute_ms = (time.perf_counter() - tick_start) * 1000.0
        tick_metric, sector_metrics = manager._build_exact_warehouse_aggregates(
            tick_duration_ms=tick_compute_ms,
            gdp=gdp,
            current_gov_cash=current_gov_cash,
            fiscal_balance=fiscal_balance,
        )
        if tick_metric is not None:
            manager.tick_metrics_batch.append(tick_metric)
            decision_feature = manager._build_decision_feature_row(tick_metric)
            if decision_feature is not None:
                manager.decision_features_batch.append(decision_feature)
                expected_decision_features += 1
            tick_diagnostic = manager._build_tick_diagnostic_row(tick_metric)
            if tick_diagnostic is not None:
                manager.tick_diagnostics_batch.append(tick_diagnostic)
                expected_tick_diagnostics += 1
        if sector_metrics:
            manager.sector_tick_metrics_batch.extend(sector_metrics)
            expected_sector_rows += len(sector_metrics)
        sector_shortage_rows = manager._build_sector_shortage_diagnostic_rows()
        if sector_shortage_rows:
            manager.sector_shortage_diagnostics_batch.extend(sector_shortage_rows)
            expected_sector_shortage_rows += len(sector_shortage_rows)

        firm_snapshots = manager._build_firm_snapshot_rows()
        manager.firm_snapshots_batch.extend(firm_snapshots)
        expected_firm_snapshots += len(firm_snapshots)

        tracked_history_rows = manager._build_tracked_household_history_rows()
        manager.tracked_household_history_batch.extend(tracked_history_rows)
        expected_tracked_household_rows += len(tracked_history_rows)

        if manager.tick == 1 or manager.tick % manager.household_snapshot_stride == 0:
            household_snapshots = manager._build_household_snapshot_rows()
            manager.household_snapshots_batch.extend(household_snapshots)
            expected_household_snapshots += len(household_snapshots)

    manager._flush_warehouse_batches()
    return (
        expected_sector_rows,
        expected_decision_features,
        expected_tick_diagnostics,
        expected_sector_shortage_rows,
        expected_firm_snapshots,
        expected_household_snapshots,
        expected_tracked_household_rows,
        expected_regime_events,
    )


def test_sqlite_warehouse_server_path_persists_aggregates_events_and_snapshots(tmp_path, monkeypatch):
    """Server-side warehouse batching should write a complete SQLite run."""
    random.seed(20260323)
    np.random.seed(20260323)

    db_path = tmp_path / "warehouse_integration.db"
    _apply_sqlite_schema(db_path)

    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "1")
    monkeypatch.setenv("ECOSIM_WAREHOUSE_BACKEND", "sqlite")
    monkeypatch.setenv("ECOSIM_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    manager = SimulationManager()
    manager.initialize({"num_households": 120, "num_firms": 2})
    run_id = manager.warehouse_run_id
    assert run_id is not None

    (
        expected_sector_rows,
        expected_decision_features,
        expected_tick_diagnostics,
        expected_sector_shortage_rows,
        expected_firm_snapshots,
        expected_household_snapshots,
        expected_tracked_household_rows,
        expected_regime_events,
    ) = _run_ticks_and_persist(manager, num_ticks=5)
    final_active_firm_ids = {firm.firm_id for firm in manager.economy.firms}
    tracked_household_ids = set(manager.tracked_household_ids)

    manager._close_warehouse_run("completed")
    if manager.warehouse_manager is not None:
        manager.warehouse_manager.close()

    db = DatabaseManager(str(db_path))
    try:
        stats = db.get_database_stats()
        run = db.get_run(run_id)
        tick_metrics = db.get_tick_metrics(run_id)
        sector_metrics = db.get_sector_tick_metrics(run_id, tick_start=1, tick_end=5)
        decision_features = db.get_decision_features(run_id, tick_start=1, tick_end=5)
        final_tick_firm_snapshots = db.get_firm_snapshots(run_id, tick_start=5, tick_end=5)
        household_snapshots = db.get_household_snapshots(run_id, tick_start=1, tick_end=5)
        tracked_household_history = db.get_tracked_household_history(run_id, tick_start=1, tick_end=5)
        run_summary = db.get_run_summary(run_id)
        tick_diagnostics = db.execute_query(
            "SELECT * FROM tick_diagnostics WHERE run_id = ? ORDER BY tick",
            (run_id,),
        )
        sector_shortage_diagnostics = db.execute_query(
            "SELECT * FROM sector_shortage_diagnostics WHERE run_id = ? ORDER BY tick, sector",
            (run_id,),
        )
        regime_events = db.execute_query(
            "SELECT * FROM regime_events WHERE run_id = ? ORDER BY tick, event_id",
            (run_id,),
        )

        assert stats["total_runs"] == 1
        assert stats["completed_runs"] == 1
        assert stats["total_ticks"] == 5
        assert stats["total_sector_rows"] == expected_sector_rows
        assert stats["total_decision_feature_rows"] == expected_decision_features
        assert stats["total_firm_snapshots"] == expected_firm_snapshots
        assert stats["total_household_snapshots"] == expected_household_snapshots
        assert stats["total_tracked_household_rows"] == expected_tracked_household_rows
        assert stats["total_tick_diagnostic_rows"] == expected_tick_diagnostics
        assert stats["total_sector_shortage_rows"] == expected_sector_shortage_rows
        assert stats["total_labor_events"] > 0
        assert stats["total_healthcare_events"] >= 0
        assert stats["total_policy_actions"] == 0
        assert stats["total_regime_events"] == expected_regime_events

        assert run is not None
        assert run.status == "completed"
        assert run.total_ticks == 5
        assert run.analysis_ready is True
        assert run.last_fully_persisted_tick == 5
        assert run.termination_reason == "completed"
        assert run.config_json is not None
        assert run.schema_version is not None
        assert run.decision_feature_version is not None

        assert len(tick_metrics) == 5
        assert tick_metrics[-1]["tick"] == 5
        assert tick_metrics[-1]["open_vacancies"] >= 0
        assert tick_metrics[-1]["tick_duration_ms"] is not None

        assert len(sector_metrics) == expected_sector_rows
        assert len(decision_features) == expected_decision_features
        assert len(tick_diagnostics) == expected_tick_diagnostics
        assert len(sector_shortage_diagnostics) == expected_sector_shortage_rows
        assert len(regime_events) == expected_regime_events
        assert decision_features[-1]["consumer_distress_score"] >= 0.0
        assert tick_diagnostics[-1]["unemployment_primary_driver"] is not None
        assert tick_diagnostics[-1]["health_primary_driver"] is not None
        assert tick_diagnostics[-1]["firm_distress_primary_driver"] is not None
        assert tick_diagnostics[-1]["housing_primary_driver"] is not None
        assert any(row["sector"] == "Housing" for row in sector_shortage_diagnostics)
        assert len(final_tick_firm_snapshots) == len(final_active_firm_ids)
        assert {row["firm_id"] for row in final_tick_firm_snapshots} == final_active_firm_ids
        assert len(household_snapshots) == expected_household_snapshots
        assert len(tracked_household_history) == expected_tracked_household_rows

        healthcare_rows = [row for row in final_tick_firm_snapshots if row["sector"] == "Healthcare"]
        assert healthcare_rows, "expected active healthcare firm snapshot"
        assert healthcare_rows[0]["queue_depth"] >= 0
        assert healthcare_rows[0]["medical_employee_count"] >= healthcare_rows[0]["doctor_employee_count"]

        sampled_ticks = {row["tick"] for row in household_snapshots}
        assert sampled_ticks == {1, 5}

        tracked_ids_seen = {row["household_id"] for row in tracked_household_history}
        assert tracked_ids_seen == tracked_household_ids

        assert run_summary["tick_count"] == 5
        assert run_summary["avg_tick_duration_ms"] is not None
        assert run_summary["avg_open_vacancies"] is not None

        labor_events = db.execute_query(
            "SELECT event_key FROM labor_events WHERE run_id = ? ORDER BY event_id",
            (run_id,),
        )
        assert labor_events
        assert all(row["event_key"] for row in labor_events)
        assert all(row["event_key"] for row in regime_events)
    finally:
        db.close()
