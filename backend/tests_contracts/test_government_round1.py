"""Round 1 PR5 government behavior: hooks, public debt, flat profit tax,
decaying public capital and the price-cap hold rule.

Tests call the public agent/economy methods and assert observable outcomes
(cash, debt, tax owed, multipliers, prices), not internal call order.
"""

import pytest

from agents import GovernmentAgent, HouseholdAgent
from economy import Economy


def _household(household_id: int, wage: float = 0.0, employed: bool = False) -> HouseholdAgent:
    hh = HouseholdAgent(household_id=household_id, skills_level=0.5, age=30, cash_balance=1_000.0)
    if employed:
        hh.employer_id = 99
        hh.wage = wage
    return hh


# ── get_benefit_replacement_rate ─────────────────────────────────────

def test_benefit_replacement_rate_is_benefit_over_mean_employed_wage():
    gov = GovernmentAgent(cash_balance=10_000.0)
    gov.unemployment_benefit_level = 30.0
    assert gov.get_benefit_replacement_rate(60.0) == pytest.approx(0.5)


@pytest.mark.parametrize("wage, expected", [(0.0, 0.0), (-5.0, 0.0), (10.0, 1.0)])
def test_benefit_replacement_rate_clamps_to_unit_interval(wage, expected):
    gov = GovernmentAgent(cash_balance=10_000.0)
    gov.unemployment_benefit_level = 30.0
    assert gov.get_benefit_replacement_rate(wage) == expected


def test_economy_replacement_rate_ignores_unemployed_households():
    households = [_household(1, 40.0, True), _household(2, 80.0, True), _household(3)]
    gov = GovernmentAgent(cash_balance=10_000.0)
    economy = Economy(households=households, firms=[], government=gov)
    gov.unemployment_benefit_level = 30.0
    assert economy.mean_employed_wage() == pytest.approx(60.0)
    assert economy.get_benefit_replacement_rate() == pytest.approx(0.5)


# ── get_health_coverage ──────────────────────────────────────────────

def test_health_coverage_is_zero_without_visits():
    assert GovernmentAgent(cash_balance=1.0).get_health_coverage() == 0.0


def test_health_coverage_reads_last_ticks_completed_visits_only():
    gov = GovernmentAgent(cash_balance=10_000.0)
    economy = Economy(households=[_household(1)], firms=[], government=gov)
    economy.last_healthcare_events = [
        {"event_type": "visit_completed", "visit_price": 20.0, "government_cost": 15.0},
        {"event_type": "visit_completed", "visit_price": 20.0, "government_cost": 5.0},
        # Denied visits are not healthcare spending and must not count.
        {"event_type": "visit_denied_affordability", "visit_price": 20.0, "government_cost": 0.0},
    ]
    economy._reset_healthcare_tick_state()
    assert economy.get_health_coverage() == pytest.approx(0.5)
    # The next tick's reset rolls an empty event list: coverage drops to 0.
    economy._reset_healthcare_tick_state()
    assert economy.get_health_coverage() == 0.0


# ── G1 public debt ───────────────────────────────────────────────────

from agents import BankAgent  # noqa: E402
from config import CONFIG  # noqa: E402


def test_shortfall_moves_to_debt_and_bank_funds_it():
    gov = GovernmentAgent(cash_balance=-1_000.0)
    bank = BankAgent(cash_reserves=10_000.0)
    out = gov.settle_public_debt(bank)
    assert out["borrowed"] == pytest.approx(1_000.0)
    assert gov.cash_balance == pytest.approx(0.0)
    assert gov.public_debt == pytest.approx(1_000.0)
    assert bank.cash_reserves == pytest.approx(9_000.0)


def test_weekly_interest_at_bank_rate_goes_to_bank():
    gov = GovernmentAgent(cash_balance=10_000.0)
    gov.public_debt = 52_000.0
    bank = BankAgent(cash_reserves=0.0, base_interest_rate=0.05)
    before = gov.cash_balance + bank.cash_reserves
    out = gov.settle_public_debt(bank)
    assert out["interest"] == pytest.approx(52_000.0 * 0.05 / CONFIG.time.ticks_per_year)
    assert gov.cash_balance + bank.cash_reserves == pytest.approx(before)  # conserved


def test_unpaid_interest_is_capitalized():
    gov = GovernmentAgent(cash_balance=0.0)
    gov.public_debt = 52_000.0
    bank = BankAgent(cash_reserves=0.0, base_interest_rate=0.05)
    gov.settle_public_debt(bank)
    assert gov.cash_balance == pytest.approx(0.0)
    assert gov.public_debt == pytest.approx(52_000.0 * (1 + 0.05 / CONFIG.time.ticks_per_year))


def test_surplus_splits_between_paydown_and_bond_buy():
    reserve = CONFIG.government.surplus_reserve
    gov = GovernmentAgent(cash_balance=reserve + 100_000.0)
    gov.public_debt = 1_000_000.0
    bank = BankAgent(cash_reserves=0.0, base_interest_rate=0.0)
    out = gov.settle_public_debt(bank)
    bonds = gov.make_investments()["bonds"]
    use = 100_000.0 * CONFIG.government.surplus_use_rate
    share = CONFIG.government.surplus_debt_paydown_share
    assert out["repaid"] == pytest.approx(use * share)
    assert bonds == pytest.approx(use * (1 - share))


def test_no_debt_means_full_bond_buy_like_before():
    reserve = CONFIG.government.surplus_reserve
    gov = GovernmentAgent(cash_balance=reserve + 100_000.0)
    gov.settle_public_debt(BankAgent(cash_reserves=0.0))
    assert gov.make_investments()["bonds"] == pytest.approx(100_000.0 * CONFIG.government.surplus_use_rate)


def test_debt_flag_off_keeps_negative_cash(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_debt_enabled", False)
    gov = GovernmentAgent(cash_balance=-1_000.0)
    gov.settle_public_debt(BankAgent(cash_reserves=10_000.0))
    assert gov.cash_balance == -1_000.0 and gov.public_debt == 0.0


# ── G2 flat profit tax ───────────────────────────────────────────────

def _firm_snapshots():
    # Same profit, very different cash: the flat tax must ignore cash.
    return [
        {"firm_id": i, "profit_before_tax": 1_000.0, "cash_balance": cash}
        for i, cash in enumerate([100.0, 5_000.0, 50_000.0, 500_000.0, 5_000_000.0])
    ] + [{"firm_id": 9, "profit_before_tax": -2_000.0, "cash_balance": 1_000.0}]


def test_flat_profit_tax_is_rate_times_positive_profit():
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    taxes = gov.plan_taxes([], _firm_snapshots())["profit_taxes"]
    assert all(taxes[i] == pytest.approx(200.0) for i in range(5))
    assert taxes[9] == 0.0  # loss pays nothing, no credit carried


def test_legacy_brackets_still_available_behind_flag(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "flat_profit_tax_enabled", False)
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    taxes = gov.plan_taxes([], _firm_snapshots())["profit_taxes"]
    assert taxes[4] > taxes[0]  # cash-rich firm pays more on the same profit


# ── G3 decaying public capital ───────────────────────────────────────

def test_technology_gain_fades_when_funding_stops():
    gov = GovernmentAgent(cash_balance=1_000_000.0)
    gov.technology_quality_multiplier = 1.10
    gov.technology_investment_budget = 0.0
    for _ in range(52):
        gov.invest_in_technology()
    rate = CONFIG.government.public_capital_decay_per_tick
    assert gov.technology_quality_multiplier == pytest.approx(1.0 + 0.10 * (1 - rate) ** 52)
    assert gov.technology_quality_multiplier < 1.01


def test_technology_never_decayed_before_pr5(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_capital_decay_enabled", False)
    gov = GovernmentAgent(cash_balance=0.0)
    gov.technology_quality_multiplier = 1.10
    gov.invest_in_technology()
    assert gov.technology_quality_multiplier == pytest.approx(1.10)


def test_steady_funding_reaches_a_stock_below_the_cap():
    gov = GovernmentAgent(cash_balance=10_000_000.0)
    gov.infrastructure_investment_budget = 500.0  # +0.25%/tick at full efficiency
    for _ in range(300):
        gov.invest_in_infrastructure()
    # Steady state of decay-then-add: e = e*(1-d) + g, so e = g/d (0.0025/0.05 = 5%).
    d = CONFIG.government.public_capital_decay_per_tick
    g = 0.0025 * gov.spending_efficiency
    assert gov.infrastructure_productivity_multiplier == pytest.approx(1.0 + g / d, rel=0.05)


def test_public_capital_purchase_is_paid_to_public_works_firm():
    from agents import FirmAgent

    pw = FirmAgent(firm_id=7, good_name="PublicWorks7", cash_balance=0.0, inventory_units=0.0,
                   good_category="PublicWorks", quality_level=1.0, wage_offer=45.0, price=1.0,
                   expected_sales_units=0.0, production_capacity_units=0.0, productivity_per_worker=1.0)
    gov = GovernmentAgent(cash_balance=0.0)
    economy = Economy(households=[_household(1)], firms=[pw], government=gov)
    misc_before = economy.misc_firm_revenue
    economy._book_public_capital_purchase(1_000.0)
    assert pw.cash_balance == pytest.approx(1_000.0)
    assert economy.misc_firm_revenue == misc_before


# ── Price-cap hold ───────────────────────────────────────────────────

def _capped_food_economy():
    from agents import FirmAgent

    firm = FirmAgent(firm_id=3, good_name="Food3", cash_balance=50_000.0, inventory_units=10.0,
                     good_category="Food", quality_level=5.0, wage_offer=40.0, price=10.0,
                     expected_sales_units=10.0, production_capacity_units=100.0, productivity_per_worker=5.0)
    gov = GovernmentAgent(cash_balance=0.0)
    gov.price_stabilization_target = "food"
    gov.price_stabilization_level = "strict"
    economy = Economy(households=[_household(1)], firms=[firm], government=gov)
    return economy, firm


def test_capped_price_holds_between_reviews(monkeypatch):
    economy, firm = _capped_food_economy()
    plan = {"price_next": 12.0}
    economy._apply_price_stabilization_to_plan(firm, plan)  # review: cap binds
    capped = plan["price_next"]
    assert capped < 12.0 and firm.price_cap_held
    firm.price = capped
    # FirmAgent gets next_price_review_tick in PR4; stand in for "between reviews".
    monkeypatch.setattr(economy, "_price_review_due", lambda _firm: False)
    plan = {"price_next": 12.0}
    economy._apply_price_stabilization_to_plan(firm, plan)
    assert plan["price_next"] == pytest.approx(capped)  # no creep between reviews


def test_next_review_reprices_from_held_price_without_catch_up():
    economy, firm = _capped_food_economy()
    firm.price_cap_held = True
    economy.government.price_stabilization_level = "off"  # cap lifted
    plan = {"price_next": 10.5}
    economy._apply_price_stabilization_to_plan(firm, plan)
    assert plan["price_next"] == 10.5  # firm's own plan, nothing added for blocked raises
    assert not firm.price_cap_held


# ── Approval observation (off by default) ────────────────────────────

def test_approval_line_is_off_by_default():
    from tools.llm.llm_government import _format_approval

    assert CONFIG.llm.government_approval_observation_enabled is False
    assert _format_approval({"approval_mean_happiness": 0.6}) == ""


def test_approval_observation_reports_change_and_stress(monkeypatch):
    from tools.llm.llm_government import _format_approval

    monkeypatch.setattr(CONFIG.llm, "government_approval_observation_enabled", True)
    poor, rich = _household(1), _household(2)
    poor.cash_balance, rich.cash_balance = 0.0, 10_000.0
    poor.happiness = rich.happiness = 0.6
    gov = GovernmentAgent(cash_balance=0.0)
    economy = Economy(households=[poor, rich], firms=[], government=gov)
    economy.current_tick = 20
    economy.append_metrics_snapshot({"mean_happiness": 0.5}, tick=5)
    obs = economy.approval_observation()
    assert obs["approval_happiness_change"] == pytest.approx(0.1)
    assert obs["approval_financial_stress_share"] == pytest.approx(0.5)
    assert "Approval" in _format_approval(obs)
