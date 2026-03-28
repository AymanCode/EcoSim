import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server
from data.db_manager import DatabaseManager
from data.models import DecisionFeature, SectorTickMetrics, SimulationRun, TickMetrics


def _apply_sqlite_schema(db_path: Path) -> None:
    schema_path = BACKEND_ROOT / "data" / "schema.sql"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def test_live_decision_context_endpoint_returns_recent_window(monkeypatch):
    test_manager = server.SimulationManager()
    test_manager.tick = 7
    test_manager.live_decision_context_history.extend(
        [
            {"tick": 4, "consumerDistressScore": 12.0, "source": "approx"},
            {"tick": 5, "consumerDistressScore": 14.0, "source": "approx"},
            {"tick": 6, "consumerDistressScore": 18.0, "source": "approx"},
        ]
    )
    test_manager.latest_decision_context = {"tick": 6, "consumerDistressScore": 18.0, "source": "approx"}

    monkeypatch.setattr(server, "manager", test_manager)
    client = TestClient(server.app)

    response = client.get("/decision-context/live", params={"window": 2})
    assert response.status_code == 200
    payload = response.json()

    assert payload["tick"] == 7
    assert payload["windowSize"] == 2
    assert payload["historyCount"] == 2
    assert [row["tick"] for row in payload["history"]] == [5, 6]
    assert payload["latest"]["tick"] == 6


def test_warehouse_history_endpoints_return_tick_and_decision_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "server_api_warehouse.db"
    _apply_sqlite_schema(db_path)

    db = DatabaseManager(str(db_path))
    try:
        run = SimulationRun(run_id="run_api_test", status="completed", total_ticks=2)
        db.create_run(run)
        db.create_run(SimulationRun(run_id="run_api_compare_b", status="completed", total_ticks=2))
        db.insert_tick_metrics(
            [
                TickMetrics(
                    run_id="run_api_test",
                    tick=1,
                    gdp=1000.0,
                    unemployment_rate=12.0,
                    mean_wage=40.0,
                    median_wage=39.0,
                    avg_happiness=72.0,
                    avg_health=84.0,
                    avg_morale=69.0,
                    total_net_worth=100000.0,
                    gini_coefficient=0.31,
                    top10_wealth_share=38.0,
                    bottom50_wealth_share=17.0,
                    gov_cash_balance=5000.0,
                    gov_profit=200.0,
                    total_firms=12,
                    struggling_firms=1,
                    tick_duration_ms=1800.0,
                    labor_force_participation=66.0,
                    open_vacancies=25,
                    total_hires=18,
                    total_layoffs=3,
                    healthcare_queue_depth=4,
                    avg_food_price=6.0,
                    avg_housing_price=12.0,
                    avg_services_price=9.0,
                ),
                TickMetrics(
                    run_id="run_api_test",
                    tick=2,
                    gdp=1025.0,
                    unemployment_rate=11.5,
                    mean_wage=40.5,
                    median_wage=39.5,
                    avg_happiness=72.5,
                    avg_health=84.1,
                    avg_morale=69.2,
                    total_net_worth=100500.0,
                    gini_coefficient=0.315,
                    top10_wealth_share=38.2,
                    bottom50_wealth_share=16.8,
                    gov_cash_balance=5100.0,
                    gov_profit=100.0,
                    total_firms=12,
                    struggling_firms=1,
                    tick_duration_ms=1750.0,
                    labor_force_participation=66.4,
                    open_vacancies=22,
                    total_hires=20,
                    total_layoffs=2,
                    healthcare_queue_depth=3,
                    avg_food_price=6.1,
                    avg_housing_price=12.0,
                    avg_services_price=9.1,
                ),
                TickMetrics(
                    run_id="run_api_compare_b",
                    tick=1,
                    gdp=900.0,
                    unemployment_rate=14.0,
                    mean_wage=37.5,
                    median_wage=36.0,
                    avg_happiness=69.0,
                    avg_health=82.0,
                    avg_morale=66.0,
                    total_net_worth=85000.0,
                    gini_coefficient=0.34,
                    top10_wealth_share=40.0,
                    bottom50_wealth_share=15.0,
                    gov_cash_balance=4200.0,
                    gov_profit=150.0,
                    total_firms=10,
                    struggling_firms=2,
                    tick_duration_ms=1900.0,
                    labor_force_participation=64.0,
                    open_vacancies=18,
                    total_hires=12,
                    total_layoffs=4,
                    healthcare_queue_depth=6,
                    avg_food_price=5.8,
                    avg_housing_price=11.4,
                    avg_services_price=8.7,
                ),
                TickMetrics(
                    run_id="run_api_compare_b",
                    tick=2,
                    gdp=920.0,
                    unemployment_rate=13.5,
                    mean_wage=38.0,
                    median_wage=36.5,
                    avg_happiness=69.5,
                    avg_health=82.2,
                    avg_morale=66.2,
                    total_net_worth=86000.0,
                    gini_coefficient=0.342,
                    top10_wealth_share=40.2,
                    bottom50_wealth_share=14.9,
                    gov_cash_balance=4300.0,
                    gov_profit=100.0,
                    total_firms=10,
                    struggling_firms=2,
                    tick_duration_ms=1880.0,
                    labor_force_participation=64.5,
                    open_vacancies=16,
                    total_hires=13,
                    total_layoffs=3,
                    healthcare_queue_depth=5,
                    avg_food_price=5.9,
                    avg_housing_price=11.5,
                    avg_services_price=8.8,
                ),
            ]
        )
        db.insert_sector_tick_metrics(
            [
                SectorTickMetrics(
                    run_id="run_api_test",
                    tick=1,
                    sector="Food",
                    firm_count=4,
                    employees=30,
                    vacancies=7,
                    mean_wage_offer=38.0,
                    mean_price=6.0,
                    mean_inventory=120.0,
                    total_output=180.0,
                    total_revenue=1200.0,
                    total_profit=180.0,
                ),
                SectorTickMetrics(
                    run_id="run_api_test",
                    tick=2,
                    sector="Food",
                    firm_count=4,
                    employees=32,
                    vacancies=5,
                    mean_wage_offer=38.5,
                    mean_price=6.1,
                    mean_inventory=110.0,
                    total_output=190.0,
                    total_revenue=1260.0,
                    total_profit=190.0,
                ),
                SectorTickMetrics(
                    run_id="run_api_test",
                    tick=2,
                    sector="Services",
                    firm_count=3,
                    employees=21,
                    vacancies=4,
                    mean_wage_offer=41.0,
                    mean_price=9.1,
                    mean_inventory=70.0,
                    total_output=130.0,
                    total_revenue=980.0,
                    total_profit=150.0,
                ),
            ]
        )
        db.insert_decision_features(
            [
                DecisionFeature(
                    run_id="run_api_test",
                    tick=1,
                    unemployment_short_ma=12.0,
                    unemployment_long_ma=12.0,
                    inflation_short_ma=0.0,
                    hiring_momentum=0.0,
                    layoff_momentum=0.0,
                    vacancy_fill_ratio=0.72,
                    wage_pressure=7.0,
                    healthcare_pressure=0.5,
                    consumer_distress_score=16.0,
                    fiscal_stress_score=0.0,
                    inequality_pressure_score=33.0,
                ),
                DecisionFeature(
                    run_id="run_api_test",
                    tick=2,
                    unemployment_short_ma=11.75,
                    unemployment_long_ma=11.75,
                    inflation_short_ma=1.1,
                    hiring_momentum=0.2,
                    layoff_momentum=-0.1,
                    vacancy_fill_ratio=0.90,
                    wage_pressure=6.5,
                    healthcare_pressure=0.3,
                    consumer_distress_score=15.5,
                    fiscal_stress_score=0.0,
                    inequality_pressure_score=33.4,
                ),
            ]
        )
    finally:
        db.close()

    monkeypatch.setenv("ECOSIM_WAREHOUSE_BACKEND", "sqlite")
    monkeypatch.setenv("ECOSIM_SQLITE_PATH", str(db_path))
    monkeypatch.setattr(server, "manager", server.SimulationManager())
    client = TestClient(server.app)

    runs_response = client.get("/warehouse/runs")
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["count"] == 2
    assert {row["run_id"] for row in runs_payload["runs"]} == {"run_api_test", "run_api_compare_b"}

    tick_response = client.get("/warehouse/runs/run_api_test/tick-metrics", params={"tick_start": 1, "tick_end": 2})
    assert tick_response.status_code == 200
    tick_payload = tick_response.json()
    assert tick_payload["count"] == 2
    assert tick_payload["tickMetrics"][1]["tick"] == 2
    assert tick_payload["tickMetrics"][1]["open_vacancies"] == 22

    decision_response = client.get(
        "/warehouse/runs/run_api_test/decision-features",
        params={"tick_start": 1, "tick_end": 2},
    )
    assert decision_response.status_code == 200
    decision_payload = decision_response.json()
    assert decision_payload["count"] == 2
    assert decision_payload["decisionFeatures"][1]["tick"] == 2
    assert decision_payload["decisionFeatures"][1]["vacancy_fill_ratio"] == 0.9

    summary_response = client.get("/warehouse/runs/run_api_test/summary")
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["summary"]["tick_count"] == 2
    assert summary_payload["summary"]["avg_open_vacancies"] == 23.5

    sector_response = client.get(
        "/warehouse/runs/run_api_test/sector-metrics",
        params={"tick_start": 1, "tick_end": 2, "sector": "Food"},
    )
    assert sector_response.status_code == 200
    sector_payload = sector_response.json()
    assert sector_payload["count"] == 2
    assert sector_payload["sectorMetrics"][0]["sector"] == "Food"
    assert sector_payload["summary"][0]["sector"] == "Food"
    assert sector_payload["summary"][0]["avg_employees"] == 31.0

    compare_response = client.get(
        "/warehouse/compare",
        params=[("run_ids", "run_api_test"), ("run_ids", "run_api_compare_b")],
    )
    assert compare_response.status_code == 200
    compare_payload = compare_response.json()
    assert compare_payload["count"] == 2
    compare_ids = {row["run_id"] for row in compare_payload["comparison"]}
    assert compare_ids == {"run_api_test", "run_api_compare_b"}
