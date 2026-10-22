"""Public debt (G1) and the LLM government: no hard brake, full visibility.

Owner decision (Ayman, 2026-10-20): the AI government may spend while the
bank finances its deficit. It must see the debt, the interest and the true
balance, and be judged on them. So:

- the sanitizer's spending guard still reads cash (it fires for an unfunded
  overdraft, when the bank could not lend, or for debt/GDP >= 1), as on main;
- fiscal mode, the prompt, policy memory and run summaries read the net
  position (cash minus public debt), the debt trend and the interest paid;
- tax cuts stop once annualized debt/GDP reaches public_debt_tax_cut_cap.
  The stress panel sets that cap at 1.0, the same line as the spending
  brake, so a funded borrow below 1.0 does not block them;
- with the flag off and no debt owed, the prompt is main's: no debt lines.
"""

import contextlib
import io

import pytest

from agents import GovernmentAgent
from config import CONFIG, SimulationConfig, clone_config, use_config
from fiscal_guards import get_sector_subsidy_cap, public_works_affordable_budget, treasury_net_position
from tools.benchmarks.regression_snapshot import _set_seed
from tools.llm.llm_government import (
    PUBLIC_DEBT_TREND_TICKS,
    _build_data_seen_snapshot,
    _build_recent_policy_memory,
    _build_system_prompt,
    _build_user_prompt,
    _format_fiscal_context,
    _format_public_debt_lines,
    _format_recent_policy_memory,
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
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = True
        prompt = _build_system_prompt("balanced", 100, 10)
    assert "Spending increases and tax cuts while borrowing are allowed" in prompt
    assert "judged on the net position" in prompt
    assert "debt trend" in prompt
    assert "interest paid" in prompt
    assert "borrowed money is not revenue" in prompt
    assert "tax cuts are not accepted" not in prompt


def test_system_prompt_keeps_the_debt_rule_while_debt_is_owed_with_the_flag_off():
    """Flag off mid-run: the debt rule stays while public_debt > 0, and matches main at 0."""
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = False
        owed = _build_system_prompt("balanced", 100, 10, {"public_debt": 1_000.0})
        clear = _build_system_prompt("balanced", 100, 10, {"public_debt": 0.0})
        main = _build_system_prompt("balanced", 100, 10)
    assert "PUBLIC DEBT:" in owed
    assert "Spending increases and tax cuts while borrowing are allowed" in owed
    assert "sustainable treasury net position" in owed
    assert clear == main
    assert "PUBLIC DEBT:" not in clear
    assert "sustainable government cash balance" in clear


DEBT_MARKERS = ("public debt", "Public Debt Trend", "Net Position", "Net position", "net_position",
                "borrow", "Debt Service", "Financing this tick")


def _prompt_texts(economy):
    raw = economy.get_economic_metrics()
    raw["_metrics_history"] = list(economy.metrics_history)
    memory = _build_recent_policy_memory(
        [{"tick": 4, "decisions": {"benefit_level": "high"}, "data_seen": _build_data_seen_snapshot(raw)}],
        economy, target_tick=30, lookback=3, impact_horizon=26,
    )
    return {
        "system": _build_system_prompt("balanced", 100, 10, raw),
        "user": _build_user_prompt(raw, {}, tick=26, recent_policy_memory=memory),
        "fiscal": _format_fiscal_context(raw, {}),
        "memory": _format_recent_policy_memory(memory),
    }


def test_flag_off_prompt_has_no_public_debt_lines(runs):
    """Flag off, nothing owed: every prompt section reads as on main."""
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = False
        texts = _prompt_texts(runs["main"])
    assert "maintaining a sustainable government cash balance" in texts["system"]
    for name, text in texts.items():
        for marker in DEBT_MARKERS:
            assert marker not in text, (name, marker)


def test_flag_on_prompt_shows_public_debt_lines(runs):
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = True
        texts = _prompt_texts(runs["debt"])
    assert "Treasury Net Position (cash minus public debt)" in texts["user"]
    assert "Public Debt Trend" in texts["user"]
    assert "Net position (cash minus public debt)" in texts["fiscal"]
    assert "public_debt=" in texts["memory"] and "net_position=" in texts["memory"]


def _review_tax_cut(gov, gdp, economy=None):
    policy = {"wage_tax_rate": gov.wage_tax_rate, "profit_tax_rate": gov.profit_tax_rate}
    change = {"wage_tax_rate": round(gov.wage_tax_rate - 0.05, 4)}
    with use_config(clone_config()):
        applied, rejected = sanitize_llm_government_changes(change, policy, gov, gdp, 0.1, economy=economy)
    return applied, [r["reason"] for r in rejected]


def _review_profit_tax_cut(gov, gdp):
    policy = {"wage_tax_rate": gov.wage_tax_rate, "profit_tax_rate": gov.profit_tax_rate}
    change = {"profit_tax_rate": round(gov.profit_tax_rate - 0.05, 4)}
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = True
        applied, rejected = sanitize_llm_government_changes(change, policy, gov, gdp, 0.1)
    return applied, [r["reason"] for r in rejected]


def _three_moves(gov, gdp):
    """A 0.05 wage-tax cut, a 0.05 profit-tax cut, and an infrastructure step up."""
    gov.set_lever("infrastructure_spending", "low")
    wage, wage_reasons = _review_tax_cut(gov, gdp)
    profit, profit_reasons = _review_profit_tax_cut(gov, gdp)
    spending, spending_reasons = _review(gov, INFRASTRUCTURE_UP, gdp)
    return (wage, wage_reasons), (profit, profit_reasons), (spending, spending_reasons)


def _debt_for_ratio(ratio: float, gdp: float = 1_000.0) -> float:
    """Public debt that annualized_debt_to_gdp reports as ``ratio`` at this weekly GDP."""
    return ratio * gdp * CONFIG.time.ticks_per_year


def _configured_tax_cut_cap() -> float:
    return float(CONFIG.government.public_debt_tax_cut_cap)


def test_tax_cut_accepted_below_the_debt_cap():
    """Cash >= 0 and debt/GDP just under the configured cap: the tax cut is accepted."""
    gdp = 1_000.0
    gov = GovernmentAgent(cash_balance=1_000.0)
    gov.public_debt = _debt_for_ratio(_configured_tax_cut_cap() - 0.01, gdp)
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = True
        applied, reasons = _review_tax_cut(gov, gdp)
    assert reasons == [] and applied["wage_tax_rate"] == pytest.approx(gov.wage_tax_rate - 0.05)


def test_tax_cut_rejected_over_the_debt_cap():
    """Cash >= 0 and debt/GDP just over the configured cap: the tax cut is rejected.

    At the stress-panel cap of 1.0 that line is also the spending brake, so the
    reason is fiscal stress. A cap set below 1.0 uses tax_cut_over_debt_cap.
    """
    gdp = 1_000.0
    ratio = _configured_tax_cut_cap() + 0.01
    gov = GovernmentAgent(cash_balance=1_000.0)
    gov.public_debt = _debt_for_ratio(ratio, gdp)
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = True
        applied, reasons = _review_tax_cut(gov, gdp)
    expected = "tax_cut_during_fiscal_stress" if ratio >= 1.0 else "tax_cut_over_debt_cap"
    assert applied == {} and reasons == [expected]


def test_spending_increase_follows_the_one_point_brake():
    """A spending increase just over the tax-cut cap is rejected only when that cap is 1.0.

    The spending brake stays at debt/GDP >= 1. The stress-panel cap equals that
    brake, so the same ratio blocks the spending increase.
    """
    gdp = 1_000.0
    ratio = _configured_tax_cut_cap() + 0.01
    gov = GovernmentAgent(cash_balance=1_000.0)
    gov.public_debt = _debt_for_ratio(ratio, gdp)
    gov.set_lever("infrastructure_spending", "low")
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = True
        applied, reasons = _review(gov, INFRASTRUCTURE_UP, gdp)
    if ratio >= 1.0:
        assert applied == {} and reasons == ["spending_increase_during_fiscal_stress"]
    else:
        assert reasons == [] and applied == INFRASTRUCTURE_UP


def test_a_lower_cap_blocks_the_tax_cut_and_still_allows_spending():
    """Below the spending brake, only the tax cut stops, and the reason is the cap."""
    gdp = 1_000.0
    gov = GovernmentAgent(cash_balance=1_000.0)
    gov.set_lever("infrastructure_spending", "low")
    with use_config(clone_config()):
        CONFIG.government.public_debt_tax_cut_cap = 0.50
        gov.public_debt = _debt_for_ratio(0.51, gdp)
        applied, reasons = _review_tax_cut(gov, gdp)
        spending, spending_reasons = _review(gov, INFRASTRUCTURE_UP, gdp)
    assert applied == {} and reasons == ["tax_cut_over_debt_cap"]
    assert spending_reasons == [] and spending == INFRASTRUCTURE_UP


def test_system_prompt_states_the_tax_cut_cap_when_debt_is_on():
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = True
        cap = _configured_tax_cut_cap()
        prompt = _build_system_prompt("balanced", 100, 10)
    assert cap == 1.0
    assert f"tax cuts are blocked once annualized debt/GDP reaches {cap:.2f}" in prompt
    assert "spending increases are blocked at 1.00" in prompt


def test_funded_borrowing_accepts_tax_cuts_and_infrastructure():
    """Cash 0 after financing, debt $178k, debt/GDP < 1: all three are accepted."""
    gov = GovernmentAgent(cash_balance=0.0)
    gov.public_debt = 178_000.0
    gdp = 1_000_000.0  # annualized debt/GDP is about 0.003
    (wage, wage_reasons), (profit, profit_reasons), (spending, spending_reasons) = _three_moves(gov, gdp)
    assert wage_reasons == [] and wage["wage_tax_rate"] == pytest.approx(gov.wage_tax_rate - 0.05)
    assert profit_reasons == [] and profit["profit_tax_rate"] == pytest.approx(gov.profit_tax_rate - 0.05)
    assert spending_reasons == [] and spending == INFRASTRUCTURE_UP


@pytest.mark.parametrize(
    "cash,debt,gdp",
    [
        (-1.0, 178_000.0, 1_000_000.0),  # unfunded overdraft
        (0.0, 52 * 10_000.0, 10_000.0),  # debt/GDP = 1
    ],
)
def test_unfunded_or_high_debt_rejects_tax_cuts_and_infrastructure(cash, debt, gdp):
    gov = GovernmentAgent(cash_balance=cash)
    gov.public_debt = debt
    (wage, wage_reasons), (profit, profit_reasons), (spending, spending_reasons) = _three_moves(gov, gdp)
    assert wage == {} and wage_reasons == ["tax_cut_during_fiscal_stress"]
    assert profit == {} and profit_reasons == ["tax_cut_during_fiscal_stress"]
    assert spending == {} and spending_reasons == ["spending_increase_during_fiscal_stress"]


def test_tax_cut_allowed_with_positive_net_position():
    gov = GovernmentAgent(cash_balance=50_000.0)
    gov.public_debt = 20_000.0
    applied, reasons = _review_tax_cut(gov, 1e6)
    assert reasons == [] and "wage_tax_rate" in applied


def test_flag_off_seeded_run_rejects_tax_cut_as_main_does(runs):
    """Flag off leaves the guard on cash, so a negative-cash run still rejects a tax cut."""
    economy = runs["main"]
    applied, reasons = _review_tax_cut(economy.government, economy.get_economic_metrics()["gdp_this_tick"], economy)
    assert economy.government.cash_balance < 0.0
    assert applied == {} and reasons == ["tax_cut_during_fiscal_stress"]


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


# sha256 of the flag-off prompt bundle below, computed on main at 09810f5 with the
# same code (seed 42, 100 households, 3 firms per category, tick 20). If main's
# prompt text changes, recompute it on main; it must still equal this branch's flag-off bundle.
MAIN_FLAG_OFF_PROMPT_SHA256 = "e3ae0f513ef5a30e4d7ec069405ef0ed7adb623f92a13fa4a63886b1d2c66762"


def _prompt_bundle(economy, tick):
    """System and user prompts, fiscal context and policy memory at ``tick``, under the active CONFIG."""
    from tools.llm.llm_government import _format_policy_impact_memory

    raw = economy.get_economic_metrics()
    raw["_metrics_history"] = list(economy.metrics_history)
    memory = _build_recent_policy_memory(
        [{"tick": 4, "decisions": {"benefit_level": "high"}, "data_seen": _build_data_seen_snapshot(raw)}],
        economy, target_tick=tick, lookback=3, impact_horizon=13,
    )
    return "\n=====\n".join([
        _build_system_prompt("balanced", 100, 10),
        _build_user_prompt(raw, {}, tick=tick, recent_policy_memory=memory),
        _format_fiscal_context(raw, {}),
        _format_recent_policy_memory(memory),
        _format_policy_impact_memory(memory),
    ])


def _seeded_economy(ticks):
    _set_seed(42)
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(100, 3)
        for _ in range(ticks):
            economy.step()
            economy.append_metrics_snapshot(economy.get_economic_metrics())
    return economy


def test_flag_off_prompt_bundle_matches_main_byte_for_byte():
    import hashlib

    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = False
        economy = _seeded_economy(20)
        text = _prompt_bundle(economy, 20)
    assert hashlib.sha256(text.encode()).hexdigest() == MAIN_FLAG_OFF_PROMPT_SHA256


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
def test_flag_on_prompt_is_the_flag_off_prompt_where_the_treasury_cannot_borrow(sequence):
    """income_first and income_late ration outlays to cash and never borrow.

    There, turning debt on must change nothing the AI government reads: the
    prompts, fiscal context, policy memory and data-seen snapshot are the
    flag-off bundle byte for byte. On legacy, from the same state, the flag
    adds the debt lines.
    """
    import json

    def bundle():
        raw = economy.get_economic_metrics()
        return _prompt_bundle(economy, 20) + "\n=====\n" + json.dumps(
            _build_data_seen_snapshot(raw), sort_keys=True, default=str
        )

    with use_config(clone_config()):
        CONFIG.payment_sequence = sequence
        CONFIG.government.public_debt_enabled = True
        economy = _seeded_economy(20)
        assert economy.payment_sequence == sequence
        assert economy.government.public_debt == 0.0
        flag_on = bundle()
        CONFIG.government.public_debt_enabled = False
        flag_off = bundle()
        CONFIG.payment_sequence = "legacy"
        CONFIG.government.public_debt_enabled = True
        legacy_on = bundle()
    assert flag_on == flag_off
    assert "PUBLIC DEBT" not in flag_on
    assert legacy_on != flag_off
    assert "\n8. PUBLIC DEBT:" in legacy_on


def test_interest_moves_money_to_the_bank_without_destroying_it(runs):
    """Interest is a transfer from treasury cash to bank reserves: total money is unchanged."""
    import copy

    economy = copy.deepcopy(runs["debt"])
    gov, bank = economy.government, economy.bank
    before = gov.cash_balance + bank.cash_reserves
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = True
        interest = gov.pay_public_debt_interest(bank, economy.get_economic_metrics()["gdp_this_tick"])
    assert interest > 0.0
    assert abs((gov.cash_balance + bank.cash_reserves) - before) < 1e-6


def _infrastructure_spent_after_approval(borrow_target, monkeypatch):
    """Deep deficit, debt on; infrastructure approved at week 40; spend over the next 10 weeks."""
    spent = []
    original = GovernmentAgent.invest_in_infrastructure

    def record(self):
        value = original(self)
        spent.append(value)
        return value

    monkeypatch.setattr(GovernmentAgent, "invest_in_infrastructure", record)
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = True
        CONFIG.government.public_debt_borrow_target = borrow_target
        _set_seed(42)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(200, 3)
            gov = economy.government
            gov.set_lever("benefit_level", "crisis")
            gov.set_lever("technology_spending", "high")
            gov.set_lever("social_spending", "high")
            gov.cash_balance = 0.0
            for _ in range(40):
                economy.step()
            gov.set_lever("infrastructure_spending", "high")
            spent.clear()
            for _ in range(10):
                economy.step()
    return spent


def test_zero_target_approved_infrastructure_is_never_spent(monkeypatch):
    """Q2: under 'zero', borrowing returns cash to ~$0 after the cash-gated programs run, so they spend $0."""
    spent = _infrastructure_spent_after_approval("zero", monkeypatch)
    assert len(spent) == 10 and sum(spent) == 0.0


def test_buffer_target_approved_infrastructure_is_spent(monkeypatch):
    spent = _infrastructure_spent_after_approval("buffer", monkeypatch)
    assert sum(spent) > 0.0


def test_default_buffer_approved_infrastructure_spends_within_10_ticks(monkeypatch):
    """Cash 0 and crisis levers, borrow target left at the default: spend within 10 ticks of approval.

    50 ticks to establish a deficit, then infrastructure is approved, then 10 ticks (60 in all).
    """
    assert SimulationConfig().government.public_debt_borrow_target == "buffer"
    spent = []
    original = GovernmentAgent.invest_in_infrastructure

    def record(self):
        value = original(self)
        spent.append(value)
        return value

    monkeypatch.setattr(GovernmentAgent, "invest_in_infrastructure", record)
    with use_config(clone_config()):
        assert CONFIG.government.public_debt_enabled is True
        assert CONFIG.government.public_debt_borrow_target == "buffer"
        _set_seed(42)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(200, 3)
            gov = economy.government
            gov.set_lever("benefit_level", "crisis")
            gov.set_lever("technology_spending", "high")
            gov.set_lever("social_spending", "high")
            gov.cash_balance = 0.0
            for _ in range(50):
                economy.step()
            gov.set_lever("infrastructure_spending", "high")
            spent.clear()
            for _ in range(10):
                economy.step()
    assert len(spent) == 10 and sum(spent) > 0.0


def _conservative_reason(cash, debt):
    from tools.llm.run_government_control_compare import _apply_conservative_policy

    with use_config(clone_config()):
        _set_seed(42)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(100, 3)
        gov = economy.government
        gov.cash_balance, gov.public_debt = cash, debt
        result = _apply_conservative_policy(economy, {"government_cash": cash, "unemployment_rate": 0.05,
                                                      "gdp_this_tick": 10_000.0})
    return result["reason"], gov


def test_comparison_government_reads_net_position():
    """Cash $0 with $100k of public debt is a deficit: austerity, not the low-cash tax cap."""
    reason, gov = _conservative_reason(0.0, 100_000.0)
    assert reason == "cash_negative_austerity"
    assert gov.benefit_level == "low"


def test_comparison_government_without_debt_is_main():
    assert _conservative_reason(-5.0, 0.0)[0] == "cash_negative_austerity"
    assert _conservative_reason(5_000.0, 0.0)[0] == "low_cash_hold"
