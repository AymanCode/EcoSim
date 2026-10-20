"""Public debt (G1) and the LLM government: no hard brake, full visibility.

Owner decision (Ayman, 2026-10-20): the AI government may spend while the
bank finances its deficit. It must see the debt, the interest and the true
balance, and be judged on them. So:

- the sanitizer's spending guard still reads cash (it fires for an unfunded
  overdraft, when the bank could not lend, or for debt/GDP >= 1), as on main;
- fiscal mode, the prompt, policy memory and run summaries read the net
  position (cash minus public debt), the debt trend and the interest paid.
"""

import contextlib
import io

import pytest

from agents import GovernmentAgent
from config import CONFIG, clone_config, use_config
from fiscal_guards import get_sector_subsidy_cap, public_works_affordable_budget, treasury_net_position
from tools.benchmarks.regression_snapshot import _set_seed
from tools.llm.llm_government import (
    PUBLIC_DEBT_TREND_TICKS,
    _build_recent_policy_memory,
    _build_system_prompt,
    _format_public_debt_lines,
    computed_fiscal_mode_from_state,
    sanitize_llm_government_changes,
)
from tools.runners.run_large_simulation import create_large_economy

INFRASTRUCTURE_UP = {"infrastructure_spending": "medium"}
FOOD_SUBSIDY = {"sector_subsidy_target": "food", "sector_subsidy_level": 10}
STRESS = ["spending_increase_during_fiscal_stress"]


def _deep_deficit(debt_on: bool):
    """Seeded deep-deficit run: empty treasury, crisis benefits, heavy spending."""
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = debt_on
        _set_seed(42)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(200, 3)
            gov = economy.government
            gov.set_lever("benefit_level", "crisis")
            gov.set_lever("infrastructure_spending", "low")
            gov.set_lever("technology_spending", "high")
            gov.set_lever("social_spending", "high")
            gov.cash_balance = 0.0
            for _ in range(26):
                economy.step()
                economy.append_metrics_snapshot(economy.get_economic_metrics())
    return economy


def _review(gov, change, gdp, economy=None):
    policy = {
        "infrastructure_spending": gov.infrastructure_spending,
        "sector_subsidy_target": gov.sector_subsidy_target,
        "sector_subsidy_level": gov.sector_subsidy_level,
    }
    with use_config(clone_config()):
        applied, rejected = sanitize_llm_government_changes(change, policy, gov, gdp, 0.1, economy=economy)
    return applied, [r["reason"] for r in rejected]


@pytest.fixture(scope="module")
def runs():
    return {"main": _deep_deficit(debt_on=False), "debt": _deep_deficit(debt_on=True)}


def test_deep_deficit_states(runs):
    main_gov, debt_gov = runs["main"].government, runs["debt"].government
    assert main_gov.cash_balance < 0.0 and main_gov.public_debt == 0.0
    assert debt_gov.public_debt > 0.0
    assert debt_gov.cash_balance >= 0.0  # the bank lent the shortfall
    assert treasury_net_position(debt_gov) < 0.0


@pytest.mark.parametrize("change", [INFRASTRUCTURE_UP, FOOD_SUBSIDY])
def test_flag_off_rejects_spending_increase_as_main(runs, change):
    economy = runs["main"]
    applied, reasons = _review(economy.government, change, economy.get_economic_metrics()["gdp_this_tick"], economy)
    assert applied == {} and reasons == STRESS


@pytest.mark.parametrize("change", [INFRASTRUCTURE_UP, FOOD_SUBSIDY])
def test_debt_financed_spending_is_allowed(runs, change):
    """Ayman's decision: no hard 'no spending while in debt' brake."""
    economy = runs["debt"]
    applied, reasons = _review(economy.government, change, economy.get_economic_metrics()["gdp_this_tick"], economy)
    assert reasons == [] and applied == change


def test_unfunded_overdraft_still_rejects_spending_increase():
    gov = GovernmentAgent(cash_balance=-1_000.0)  # the bank could not lend it all
    gov.public_debt = 10_000.0
    gov.set_lever("infrastructure_spending", "low")
    applied, reasons = _review(gov, INFRASTRUCTURE_UP, 1e6)
    assert applied == {} and reasons == STRESS


def test_debt_to_gdp_at_one_still_rejects_spending_increase():
    gov = GovernmentAgent(cash_balance=500.0)
    gov.public_debt = 52 * 1_000.0  # annual GDP 52,000: debt/GDP = 1.0
    gov.set_lever("infrastructure_spending", "low")
    applied, reasons = _review(gov, INFRASTRUCTURE_UP, 1_000.0)
    assert applied == {} and reasons == STRESS


def test_fiscal_mode_reads_net_position(runs):
    assert computed_fiscal_mode_from_state(runs["debt"].government, recent_gdp=10_000.0) == "CASH_CRISIS"
    assert computed_fiscal_mode_from_state(runs["main"].government, recent_gdp=10_000.0) == "CASH_CRISIS"


def test_prompt_shows_debt_service_financing_and_trend(runs):
    economy = runs["debt"]
    raw = economy.get_economic_metrics()
    raw["_metrics_history"] = list(economy.metrics_history)
    text = _format_public_debt_lines(raw)
    assert f"interest ${raw['gov_debt_interest_this_tick']:,.0f}" in text
    assert raw["gov_debt_interest_this_tick"] > 0.0
    assert "Financing this tick (not revenue): borrowed" in text
    past = economy.metrics_history[-PUBLIC_DEBT_TREND_TICKS]["metrics"]["public_debt"]
    assert raw["public_debt"] > past  # debt grew over the quarter
    assert f"Public Debt Trend: +${raw['public_debt'] - past:,.0f} over the last 13 ticks" in text


def test_prompt_trend_needs_a_quarter_of_history():
    assert "n/a (fewer than 13 ticks of history)" in _format_public_debt_lines({"public_debt": 5.0})


def test_system_prompt_states_the_debt_rule():
    prompt = _build_system_prompt("balanced", 100, 10)
    assert "Spending while borrowing is allowed" in prompt
    assert "borrowed money is not revenue" in prompt


def test_policy_memory_reports_debt_and_net_position_change():
    class FakeEconomy:
        metrics_history = [
            {"tick": 3, "metrics": {"public_debt": 10_000.0, "government_net_position": -9_000.0, "government_cash": 1_000.0}},
            {"tick": 30, "metrics": {"public_debt": 25_000.0, "government_net_position": -24_500.0, "government_cash": 500.0}},
        ]

    memory = _build_recent_policy_memory(
        [{"tick": 4, "decisions": {"benefit_level": "high"}}], FakeEconomy(), target_tick=30, lookback=3, impact_horizon=26
    )[0]
    assert memory["mature_impact"]["public_debt_delta"] == pytest.approx(15_000.0)
    assert memory["mature_impact"]["net_position_delta"] == pytest.approx(-15_500.0)
    assert memory["mature_impact"]["government_cash_delta"] == pytest.approx(-500.0)


class _Gov:
    def __init__(self, cash, debt):
        self.cash_balance = cash
        self.public_debt = debt


def test_spending_gates_read_cash_as_on_main():
    """No new gate: the subsidy cap and public-works check read cash."""
    assert treasury_net_position(_Gov(40_000.0, 100_000.0)) == -60_000.0
    assert get_sector_subsidy_cap(_Gov(100_000.0, 50_000.0), 1e9) == pytest.approx(2_000.0)
    assert get_sector_subsidy_cap(_Gov(-1.0, 0.0), 1e9) == 0.0
    assert public_works_affordable_budget(_Gov(500_000.0, 480_000.0), 1.0) == pytest.approx(450_000.0)


def test_deficit_ratio_metric_is_net_of_debt(runs):
    economy = runs["debt"]
    metrics = economy.get_economic_metrics()
    net = treasury_net_position(economy.government)
    assert metrics["government_net_position"] == pytest.approx(net)
    assert metrics["deficit_ratio"] == pytest.approx(-net / max(metrics["gdp_this_tick"], 1.0))
