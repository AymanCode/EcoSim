"""Legacy shopping: minimum food first, then the rest by preference (2026-10-02, item 1b).

Owner: "food and rent should come first, then budget for services." Rent is
reserved before the budget is set (item 1). Within the budget, the money for
the household's ``min_food_per_tick`` units at the mean posted Food price
(bounded by the budget and the food satiation cap) now goes to food before
the category fractions split the remainder. Payment arms are unchanged.
"""

import numpy as np
import pytest

from agents import FirmAgent
from config import CONFIG
from economy import Economy
from tools.checks.run_agent_scenarios import isolated_run, small_world


def _food_and_services_world(seed):
    economy = small_world(seed, cash=0.0)  # Food shop: firm 1, price 10
    services = FirmAgent(
        firm_id=2, good_name="Haircut", good_category="Services", cash_balance=10_000.0,
        inventory_units=0.0, price=10.0, wage_offer=40.0, expected_sales_units=40.0,
        quality_level=5.0, production_capacity_units=200.0, productivity_per_worker=12.0,
        personality="moderate", is_baseline=False,
    )
    services.age_in_ticks = 30
    economy = Economy(economy.households, economy.firms + [services], economy.government, bank=economy.bank)
    household = economy.households[0]
    household.category_weights = {"food": 0.1, "services": 0.9}  # strong services preference
    household.food_preference = household.services_preference = 1.0
    household.min_food_per_tick = 2.0
    household.services_consumed_last_tick = 10.0  # no services comfort-floor shift
    household.services_consumed_this_tick = 10.0
    household.food_consumed_this_tick = CONFIG.households.food_health_high_threshold
    return economy, household


def _plan(economy, budget):
    market = economy._build_category_market_snapshot()
    lookup = economy._build_good_category_lookup()
    plans = economy._batch_plan_consumption(
        {}, market, lookup, 0.0, 30.0, settled_income=True, budgets=np.array([budget]),
    )
    planned = plans[1]["planned_purchases"]
    return planned.get(1, 0.0), planned.get(2, 0.0)  # food units, services units (both priced 10)


def test_low_budget_services_lover_buys_minimum_food_first():
    with isolated_run(1337):
        economy, household = _food_and_services_world(1337)
        food_units, services_units = _plan(economy, 25.0)
        # Minimum food: 2 units x mean Food price 10 = 20 of the 25.
        assert food_units >= household.min_food_per_tick - 1e-9
        assert services_units * 10.0 <= 25.0 - 20.0 + 1e-9


def test_budget_below_minimum_food_goes_entirely_to_food():
    with isolated_run(1337):
        economy, _ = _food_and_services_world(1337)
        food_units, services_units = _plan(economy, 12.0)
        assert food_units * 10.0 == pytest.approx(12.0)
        assert services_units == 0.0


def test_comfortable_household_split_unchanged_beyond_minimum_food(monkeypatch):
    monkeypatch.setattr(CONFIG, "payment_sequence", "income_first")
    economy, household = _food_and_services_world(1337)
    # A healthcare reserve also activates the food floor on this payment sequence.
    economy._healthcare_food_first_ids = frozenset({household.household_id})
    food_with_floor, services_with_floor = _plan(economy, 200.0)
    economy._healthcare_food_first_ids = frozenset()
    # The food floor is 2 * $10. The split on the remaining $180 is unchanged.
    _, services_without_floor = _plan(economy, 180.0)
    assert food_with_floor >= household.min_food_per_tick
    assert services_with_floor == pytest.approx(services_without_floor)


def test_payment_arm_planner_has_no_food_floor(monkeypatch):
    """The payment-arm planner keeps the preference split."""
    monkeypatch.setattr(CONFIG, "payment_sequence", "income_first")
    economy, household = _food_and_services_world(1337)
    food_units, _ = _plan(economy, 25.0)
    assert food_units < household.min_food_per_tick


def test_cached_plan_rescale_buys_minimum_food_first():
    with isolated_run(1337):
        economy, household = _food_and_services_world(1337)
        economy.performance_mode = True
        market = economy._build_category_market_snapshot()
        lookup = economy._build_good_category_lookup()
        household.cash_balance = 400.0
        household.last_wage_income = 200.0
        economy._plan_legacy_consumption_after_income({}, market, lookup, 0, 0)  # full plan, cached
        economy.current_tick = 1
        household.cash_balance = 25.0
        household.last_wage_income = 25.0
        plans = economy._plan_legacy_consumption_after_income({}, market, lookup, 0, 0)
        assert "_purchase_scale" in plans[1]  # the rescale path, not a new plan
        purchases, _ = economy._clear_goods_market(plans, economy.firms)
        food_qty, food_price = purchases[1].get("Shop", (0.0, 0.0))
        budget = plans[1]["budget"]
        assert food_qty * food_price == pytest.approx(min(budget, household.min_food_per_tick * 10.0))
        spent = sum(q * p for q, p in purchases[1].values())
        assert spent <= budget + 1e-9
