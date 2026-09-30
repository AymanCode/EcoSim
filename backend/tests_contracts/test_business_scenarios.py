"""Controlled demand must reach real business decisions without fabricating sales."""

import dataclasses
import json
import random

import numpy as np
import pytest

from config import get_config
from tools.checks import run_business_scenarios as business


@pytest.fixture(scope="module")
def suite():
    return {name: business.run_experiment(name, settings)
            for group in business.presets().values() for name, settings in group}


def test_all_default_runs_reconcile_receipts_supply_payroll_and_employment(suite):
    assert len(suite) == 19
    assert all(c["passed"] for experiment in suite.values() for c in experiment["checks"])
    funded = suite["services_expansion_funded"]
    assert any(t["registered_firm_loans"] for t in funded["traces"])


def test_demand_is_an_order_not_guaranteed_sales_or_a_future_planning_signal():
    base = business.Settings(ticks=2, initial_demand=30)
    empty = business.run_experiment("empty", dataclasses.replace(base, demand=(0, 0)))
    flood = business.run_experiment("flood", dataclasses.replace(base, demand=(10000, 0)))
    assert empty["traces"][0]["production_plan"] == flood["traces"][0]["production_plan"]
    assert empty["rows"][0]["sold"] == 0
    assert flood["rows"][0]["sold"] > 0
    assert flood["rows"][0]["sold"] < 10000
    assert empty["traces"][1]["production_plan"]["updated_expected_sales"] < flood["traces"][1]["production_plan"]["updated_expected_sales"]


def test_opening_demand_changes_the_first_plan_without_creating_opening_cash():
    base = business.Settings(ticks=1, demand=(30,))
    low = business.run_experiment("low", dataclasses.replace(base, initial_demand=0))
    high = business.run_experiment("high", dataclasses.replace(base, initial_demand=120))
    assert low["initial"]["cash"] == high["initial"]["cash"] == base.cash
    assert low["traces"][0]["production_plan"]["updated_expected_sales"] < high["traces"][0]["production_plan"]["updated_expected_sales"]


@pytest.mark.parametrize("buyer_cash", [0, 5])
def test_external_customer_has_a_real_finite_budget(buyer_cash):
    result = business.run_experiment("buyer_limit", business.Settings(ticks=2, demand=(1000,), buyer_cash=buyer_cash))
    paid = sum(t["market"]["buyer_paid"] for t in result["traces"])
    assert paid <= buyer_cash + 1e-8
    assert all(c["passed"] for c in result["checks"])
    assert all(t["market"]["funded_order_units"] < t["market"]["requested_units"] for t in result["traces"])
    if buyer_cash == 0:
        assert paid == 0


def test_cash_scarcity_and_worker_availability_remain_visible(suite):
    broke = suite["cash_0"]["traces"][0]
    rich = suite["cash_10000"]["traces"][0]
    assert broke["market"]["cash_before_sales"] < 0
    assert rich["after"]["capital"] > broke["after"]["capital"]
    assert sum(r["hired"] for r in suite["hiring_available"]["rows"]) > 0
    assert sum(r["hires_planned"] for r in suite["hiring_no_applicants"]["rows"]) > 0
    assert sum(r["hired"] for r in suite["hiring_no_applicants"]["rows"]) == 0


def test_hiring_pressure_waits_for_annual_review_and_payroll_stays_paired(suite):
    competitive = suite["wages_competing_for_workers"]
    offers = [competitive["initial"]["wage_offer"], *[r["wage_offer_after"] for r in competitive["rows"]]]
    assert set(offers) == {40}
    assert any(t["failed_hiring_reason"] == "reservation_above_wage_offer" for t in competitive["traces"])
    first = suite["cash_0"]["traces"][0]
    assert first["after"]["wage_offer"] == first["before"]["wage_offer"]
    assert first["after"]["worker_contracts"] == first["before"]["worker_contracts"]
    assert first["wages_paid"] == pytest.approx(sum(first["before"]["worker_contracts"].values()))


def test_weak_services_sales_do_not_cut_pay_with_adequate_cash(suite):
    weak = suite["services_weak_sales_wages"]
    offers = [r["wage_offer_after"] for r in weak["rows"]]
    assert offers[0] == 60
    assert set(offers) == {60}
    assert all(t["diagnostics"]["wage_review_reason"] == "annual_review_not_due" for t in weak["traces"])


# Written against 17d5c0b as a strict xfail (identical weak-demand observations
# were deduplicated). The remediation fixed it (CHANGELOG B16: the streak counts
# once per tick), so on this code it is an ordinary passing test.
def test_repeated_zero_sales_advances_services_weak_demand_counter(suite):
    traces = suite["services_no_sales"]["traces"]
    assert max(t["diagnostics"].get("service_weak_demand_streak", 0) for t in traces) >= 2


def test_capacity_expansion_is_distinct_from_hiring_capital_and_sales(suite):
    funded, unfunded = suite["services_expansion_funded"], suite["services_expansion_no_bank"]
    assert funded["rows"][-1]["capacity_limit"] > funded["initial"]["capacity_limit"]
    assert unfunded["rows"][-1]["capacity_limit"] == unfunded["initial"]["capacity_limit"]
    assert funded["rows"][-1]["production"] > unfunded["rows"][-1]["production"]
    food = suite["food_expansion"]
    assert food["rows"][-1]["capital"] > food["initial"]["capital"]
    assert food["rows"][-1]["productive_capacity"] > food["initial"]["productive_capacity"]
    assert food["rows"][-1]["capacity_limit"] == food["initial"]["capacity_limit"]


def test_low_demand_produces_a_multi_week_adjustment_and_cash_can_run_out(suite):
    rich, broke = suite["no_sales"], suite["no_sales_no_cash"]
    assert all(r["sold"] == 0 for r in rich["rows"] + broke["rows"])
    assert rich["rows"][-1]["production"] < rich["rows"][0]["production"]
    assert rich["rows"][-1]["firm_open"]
    assert not broke["rows"][-1]["firm_open"]
    assert all(h["employer"] is None for h in broke["traces"][-1]["worker_receipts"].values())
    recovered = suite["demand_crash_then_recovery"]
    assert all(r["sold"] == 0 for r in recovered["rows"][3:8])
    assert any(r["sold"] > 0 for r in recovered["rows"][8:])


def test_scenarios_restore_rng_config_and_repeat_after_other_work():
    before = dataclasses.asdict(get_config())
    py, np_state = random.getstate(), np.random.get_state()
    settings = business.Settings(ticks=3, demand=(30, 0, 120))
    first = business.run_experiment("repeat", settings, seed=7)
    assert random.getstate() == py
    np.testing.assert_equal(np.random.get_state(), np_state)
    assert dataclasses.asdict(get_config()) == before
    random.random()
    np.random.random(10)
    assert first == business.run_experiment("repeat", settings, seed=7)


def test_custom_cli_uses_inputs_and_repeats_last_demand(tmp_path):
    assert business.main(["--cash", "100", "--initial-demand", "10", "--demand", "0,80", "--ticks", "4",
                          "--output-dir", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "results.json").read_text())
    assert len(data["experiments"]) == 1
    custom = data["experiments"][0]
    assert custom["name"] == "custom"
    assert custom["initial"]["cash"] == 100
    assert [r["demand"] for r in custom["rows"]] == [0, 80, 80, 80]
    report = (tmp_path / "report.md").read_text()
    assert "Summary" in report and "Hiring and pay" in report and "Production and capacity" in report
    assert data["metadata"]["source_sha256"]["backend/economy.py"]


def test_startup_with_no_workers_has_valid_json_and_real_hiring(tmp_path):
    assert business.main(["--workers", "0", "--cash", "0", "--demand", "100", "--ticks", "2",
                          "--output-dir", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "results.json").read_text())
    experiment = data["experiments"][0]
    assert experiment["initial"]["workers"] == 0
    assert experiment["rows"][0]["hired"] > 0
    assert experiment["traces"][0]["health_snapshot"]["cash_runway_ticks"] == "Infinity"


@pytest.mark.parametrize("args", [
    ["--ticks", "0"], ["--demand", "nan"], ["--demand", "-1"], ["--demand", "1e308"],
    ["--cash", "-1"], ["--workers", "13"], ["--job-seekers", "20"],
    ["--category", "Services", "--capacity", "1.5"], ["--demand", "1,2", "--ticks", "1"],
    ["--case", "cash", "--demand", "100"], ["--seed", "-1"],
])
def test_invalid_or_silently_ignored_inputs_are_rejected(args, tmp_path):
    with pytest.raises(SystemExit) as exc:
        business.main([*args, "--output-dir", str(tmp_path)])
    assert exc.value.code == 2
    assert not (tmp_path / "results.json").exists()


def test_failed_check_returns_nonzero_and_preserves_evidence(monkeypatch, tmp_path):
    run = business.run_experiment
    def fail(*args, **kwargs):
        result = run(*args, **kwargs)
        result["checks"][0]["passed"] = False
        return result
    monkeypatch.setattr(business, "run_experiment", fail)
    assert business.main(["--case", "custom", "--ticks", "1", "--output-dir", str(tmp_path)]) == 1
    assert "FAIL:" in (tmp_path / "report.md").read_text()
