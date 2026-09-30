"""Price changes, annual decisions and money settlement are distinct mechanisms.

Ported onto the remediation code on 2026-09-29 (originally written against
17d5c0b). The tests after ``# --- remediation port`` are new: the on/off switch
(``CONFIG.inflation.enabled``), the B19 policy minimum wage, the wage-bill
cache, the B22 planner-diagnostics clear and config validation.
"""

import copy
import dataclasses
from types import SimpleNamespace

import pytest

from config import CONFIG, InflationConfig, SimulationConfig
from inflation import ConsumerPriceIndex, WageReview
from tests_contracts.factories import patch_agent_method


def quote(fid=1, category="Food", price=10.0):
    return SimpleNamespace(firm_id=fid, good_category=category, price=price)


def test_broad_prices_and_fixed_category_weights():
    index = ConsumerPriceIndex({"food": .4, "housing": .6})
    index.observe(0, [quote(), quote(2, "Housing", 20)])
    index.observe(1, [quote(price=11), quote(2, "Housing", 20)])
    assert index.level == pytest.approx(104)
    assert index.weekly_rate == pytest.approx(.04)
    assert index.annual_rate is None
    assert index.coverage == 1


def test_entry_exit_and_seller_count_do_not_create_inflation():
    index = ConsumerPriceIndex({"food": 1})
    index.observe(0, [quote()])
    index.observe(1, [quote(), quote(2, price=1000)])
    assert index.level == 100
    index.observe(2, [quote(2, price=1000)])
    assert index.level == 100
    index.observe(3, [quote(2, price=1100)])
    assert index.level == pytest.approx(110)


def test_missing_category_is_carried_and_coverage_disclosed():
    index = ConsumerPriceIndex({"food": .5, "housing": .5})
    index.observe(0, [quote(), quote(2, "Housing", 20)])
    index.observe(1, [quote(price=12)])
    assert index.level == pytest.approx(110)
    assert index.coverage == .5
    index.observe(2, [quote(price=12), quote(2, "Housing", 100)])
    assert index.level == pytest.approx(110)  # Re-entry cannot be a price comparison.
    assert index.coverage == .5


@pytest.mark.parametrize("annual", [0, .02, -.1])
def test_year_on_year_is_compounded_and_history_is_bounded(annual):
    index = ConsumerPriceIndex({"food": 1})
    for tick in range(105):
        index.observe(tick, [quote(price=10 * (1 + annual) ** (tick / 52))])
        if tick < 52:
            assert index.annual_rate is None
        else:
            assert index.annual_rate == pytest.approx(annual, abs=1e-12)
    assert len(index.history) == 53


def test_observation_is_idempotent_and_missing_weeks_are_not_annualized():
    index = ConsumerPriceIndex({"food": 1})
    index.observe(0, [quote()])
    index.observe(0, [quote(price=20)])
    assert index.level == 100
    index.observe(52, [quote(price=20)])
    assert index.weekly_rate is None and index.annual_rate is None
    with pytest.raises(ValueError):
        index.observe(1, [quote()])


@pytest.mark.parametrize("weights,year", [({}, 52), ({"food": 0}, 52), ({"food": -1}, 52),
                                            ({"food": float("nan")}, 52), ({"food": 1}, 0)])
def test_invalid_index_configuration(weights, year):
    with pytest.raises(ValueError):
        ConsumerPriceIndex(weights, year)


def firm_for_review(factory, *, cash=10000, revenue=1000):
    return factory.firm(firm_id=1, category="Food", is_baseline=False, wage_offer=40,
                        employees=[1], actual_wages={1: 40}, cash_balance=cash,
                        last_revenue=revenue, last_profit=100)


def test_annual_review_uses_observed_prices_and_preserves_cash(factory):
    firm = firm_for_review(factory)
    index = ConsumerPriceIndex({"food": 1})
    review = WageReview(0, 100, -52)
    config = InflationConfig()
    for tick in range(53):
        index.observe(tick, [quote(price=10 * 1.05 ** (tick / 52))])
        plan = review.plan(firm, index, tick, config, 36)
        assert plan["contract_factor"] == pytest.approx(1.05 if tick == 52 else 1)
    assert plan["wage_offer_next"] == pytest.approx(42)
    assert firm.cash_balance == 10000
    assert firm.actual_wages == {1: 40}  # Planning does not settle the contract.


@pytest.mark.parametrize("cash,change,expected", [(10000, -.1, 1), (320, .05, 1),
                                                   (326.4, .05, 1.02), (10000, .50, 1.1)])
def test_raise_is_bounded_by_prices_cash_and_cap(factory, cash, change, expected):
    firm = firm_for_review(factory, cash=cash)
    index = ConsumerPriceIndex({"food": 1})
    index.level = 100 * (1 + change)
    plan = WageReview(0, 100, -52).plan(firm, index, 52, InflationConfig(), 36)
    assert plan["contract_factor"] == pytest.approx(expected)


def test_revenue_and_planned_hires_can_block_a_cash_rich_raise(factory):
    firm = firm_for_review(factory, revenue=1)
    index = ConsumerPriceIndex({"food": 1})
    index.level = 110
    assert WageReview(0, 100, -52).plan(firm, index, 52, InflationConfig(), 36)["contract_factor"] == 1
    firm.last_revenue = 1000
    assert WageReview(0, 100, -52).plan(firm, index, 52, InflationConfig(), 36, planned_hires=100)["contract_factor"] == 1


def test_distress_cut_requires_persistence_and_annual_cooldown(factory):
    firm = firm_for_review(factory, cash=0, revenue=0)
    firm.last_profit = -40
    index = ConsumerPriceIndex({"food": 1})
    review = WageReview(0, 100, -52)
    cuts = []
    for tick in range(105):
        plan = review.plan(firm, index, tick, InflationConfig(), 36)
        if plan["contract_factor"] < 1:
            cuts.append(tick)
    assert cuts == [7, 59]


@pytest.mark.parametrize("performance_mode", [False, True])
def test_complete_step_review_changes_next_payday_once(factory, monkeypatch, performance_mode):
    household = factory.household(household_id=1, employer_id=1, wage=40, cash_balance=10000)
    firm = firm_for_review(factory)
    economy = factory.economy(households=[household], firms=[firm])
    economy.government.unemployment_benefit_level = 0
    economy.warmup_ticks = 0
    economy.in_warmup = False
    economy.performance_mode = performance_mode
    economy.consumer_prices = ConsumerPriceIndex({"food": 1})
    for tick in range(52):
        economy.consumer_prices.observe(tick, [quote(price=10)])
    economy.current_tick = 52
    economy.wage_reviews[1] = WageReview(0, 100, -52)
    firm.price = 10.5
    monkeypatch.setattr(economy, "_apply_random_shocks", lambda: None)
    # FirmAgent uses __slots__ on the remediation code: patch through the class.
    patch_agent_method(monkeypatch, firm, "plan_capital_investment", lambda **kw: None)
    patch_agent_method(monkeypatch, firm, "plan_production_and_labor", lambda *a, **kw: {
        "planned_production_units": 1, "planned_hires_count": 0, "planned_layoffs_ids": [],
        "updated_expected_sales": 1})
    monkeypatch.setattr(economy, "_run_labor_matching", lambda *a: (
        {1: {"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}}},
        {1: {"employer_id": 1, "wage": household.wage, "employer_category": "Food"}}))
    before_cash = household.cash_balance
    economy.step()
    assert household.last_wage_income == 40
    assert household.wage == pytest.approx(42)
    assert firm.actual_wages[1] == pytest.approx(household.wage)
    # The contract write invalidates the wage-bill cache (remediation port).
    assert firm._current_wage_bill() == sum(firm.actual_wages.get(e, firm.wage_offer) for e in firm.employees)
    assert before_cash != household.cash_balance  # Real step, with ordinary settlement.
    assert economy.get_economic_metrics()["consumer_price_index"] == pytest.approx(105)
    economy.step()
    assert household.last_wage_income == pytest.approx(42)
    assert household.wage == pytest.approx(42)


def test_price_measurement_does_not_mutate_agents(factory):
    firm = firm_for_review(factory)
    # FirmAgent uses __slots__ on the remediation code, so compare declared fields.
    def state():
        return {f.name: copy.deepcopy(getattr(firm, f.name)) for f in dataclasses.fields(firm)}
    before = state()
    index = ConsumerPriceIndex({"food": 1})
    index.observe(0, [firm])
    index.observe(1, [firm])
    assert state() == before


def test_disabling_firm_stabilizers_does_not_impose_weekly_inflation(factory):
    firm = firm_for_review(factory)
    firm.stabilization_disabled = True
    assert firm.plan_pricing(.99, unemployment_rate=0)["price_next"] == firm.price


def test_private_review_retains_existing_benefit_wage_floor(factory):
    firm = firm_for_review(factory)
    economy = factory.economy(firms=[firm])
    economy.warmup_ticks = 0
    economy.in_warmup = False
    economy.current_tick = 17
    economy.government.unemployment_benefit_level = 30
    economy.step()
    assert firm.wage_offer >= 45


def test_inflation_public_scenarios_and_temporary_supply_shock(tmp_path):
    from backend.tools.checks import run_inflation_scenarios as scenarios
    assert scenarios.main(["--seed", "7", "--output-dir", str(tmp_path)]) == 0
    import json
    result = json.loads((tmp_path / "results.json").read_text())
    control, demand, supply = result["market_experiments"]
    assert control["rows"][:12] == supply["rows"][:12]
    assert control["rows"][:12] == demand["rows"][:12]
    assert supply["rows"][12]["productive_capacity"] < control["rows"][12]["productive_capacity"]
    assert demand["rows"][12]["demand"] == 2 * control["rows"][12]["demand"]
    assert demand["rows"][20]["demand"] == control["rows"][20]["demand"]
    assert len(supply["rows"]) == 105


def test_supply_shock_restores_the_production_parameter():
    from tools.checks import run_business_scenarios as business
    from tools.checks.run_agent_scenarios import isolated_run
    with isolated_run(1337):
        settings = business.Settings(supply_shock_start=2, supply_shock_weeks=2, supply_multiplier=.5)
        economy = business.make_world(settings)
        original = economy.firms[0].units_per_worker
        values = []
        for tick in range(17, 21):
            economy.current_tick = tick
            economy._apply_random_shocks()
            values.append(economy.firms[0].units_per_worker)
        assert values == [original, original * .5, original * .5, original]


def test_exit_removes_price_and_review_state_before_id_can_be_reused(factory):
    from tools.checks.run_agent_scenarios import isolated_run, small_world
    with isolated_run(1337):
        economy = small_world(1337)
        firm = economy.firms[0]
        economy.consumer_prices = ConsumerPriceIndex({"food": 1})
        economy.consumer_prices.observe(0, [firm])
        economy.wage_reviews[firm.firm_id] = WageReview(0, 100, -52)
        firm.cash_balance = -1e9
        economy._handle_firm_exits()
        assert firm not in economy.firms
        assert firm.firm_id not in economy.wage_reviews
        assert (firm.firm_id, "food") not in economy.consumer_prices.previous_quotes
        replacement = quote(firm.firm_id, price=1000)
        economy.consumer_prices.observe(1, [replacement])
        assert economy.consumer_prices.level == 100


# --- remediation port (2026-09-29) -------------------------------------------


def test_switch_defaults_on_and_is_validated():
    assert InflationConfig().enabled is True
    with pytest.raises(ValueError):
        SimulationConfig(inflation=InflationConfig(enabled="yes"))
    with pytest.raises(ValueError):
        SimulationConfig(inflation=InflationConfig(annual_wage_raise_cap=1.5))
    with pytest.raises(ValueError):
        SimulationConfig(inflation=InflationConfig(distress_weeks=0))
    with pytest.raises(ValueError):
        SimulationConfig(inflation=InflationConfig(basket_weights={"food": -1.0}))


def test_switch_off_restores_weekly_wage_rules_and_price_escalator(factory, monkeypatch):
    monkeypatch.setattr(CONFIG.inflation, "enabled", False)
    firm = firm_for_review(factory)
    firm.stabilization_disabled = True
    assert firm.plan_pricing(.99, unemployment_rate=0)["price_next"] == pytest.approx(firm.price * 1.02)
    firm.stabilization_disabled = False
    economy = factory.economy(firms=[firm])
    economy.warmup_ticks = 0
    economy.in_warmup = False
    economy.current_tick = 17
    economy.step()
    assert firm.annual_wage_control is False
    assert economy.wage_reviews == {}
    assert economy.consumer_prices.last_tick is None
    assert not any(k.startswith("wage_review_") for k in firm.decision_diagnostics)
    metrics = economy.get_economic_metrics()
    assert metrics["consumer_price_index"] == 100 and metrics["inflation_observed"] == 0


def test_switch_on_puts_private_food_under_annual_review(factory):
    firm = firm_for_review(factory)
    economy = factory.economy(firms=[firm])
    economy.warmup_ticks = 0
    economy.in_warmup = False
    economy.current_tick = 17
    economy.step()
    assert firm.annual_wage_control is True
    assert firm.firm_id in economy.wage_reviews
    assert economy.consumer_prices.last_tick == 17
    assert firm.decision_diagnostics["wage_review_reason"] == "annual_review_not_due"


def test_review_respects_policy_minimum_wage(factory):
    """B19: the policy minimum wage (not only the config floor) binds reviewed offers and contracts."""
    household = factory.household(household_id=1, employer_id=1, wage=40, cash_balance=10000)
    firm = firm_for_review(factory)
    economy = factory.economy(households=[household], firms=[firm])
    economy.government.unemployment_benefit_level = 0
    economy.government._minimum_wage_floor = 55.0
    economy.warmup_ticks = 0
    economy.in_warmup = False
    economy.consumer_prices = ConsumerPriceIndex({"food": 1})
    for tick in range(52):
        economy.consumer_prices.observe(tick, [quote(price=10)])
    economy.current_tick = 52
    economy.wage_reviews[1] = WageReview(0, 100, -52)
    firm.price = 10.5
    economy.step()
    assert firm.wage_offer >= 55.0
    assert firm.actual_wages[1] >= 55.0
    assert household.wage == pytest.approx(firm.actual_wages[1])


def test_wage_review_diagnostics_are_planner_owned(factory):
    """B22: a firm that leaves annual control does not keep stale review keys."""
    firm = firm_for_review(factory)
    firm.decision_diagnostics.update({"wage_review_reason": "annual_inflation_raise", "wage_review_factor": 1.05})
    firm.clear_planner_diagnostics()
    assert not any(k.startswith("wage_review_") for k in firm.decision_diagnostics)


def test_continuing_worker_raise_and_revenue_cut_skip_reviewed_firms(factory):
    household = factory.household(household_id=1, employer_id=1, wage=40, cash_balance=10000)
    firm = firm_for_review(factory)
    economy = factory.economy(households=[household], firms=[firm])
    household.last_wage_update_tick = -100
    economy.current_tick = 60
    firm.annual_wage_control = True
    economy._update_continuing_employee_wages()
    assert firm.actual_wages[1] == 40
    firm.last_revenue = 1.0
    firm.cash_runway_ticks = 0.0
    firm.smoothed_profit_margin = -1.0
    firm.adjust_wages_to_revenue_ratio(1.0)
    assert firm.actual_wages[1] == 40 and firm.wage_offer == 40
    firm.annual_wage_control = False
    economy._update_continuing_employee_wages()
    assert firm.actual_wages[1] > 40
