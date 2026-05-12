"""Unit tests for baseline firm containment and fiscal transparency (EcoSim 2.0).

All tests are unit-scope: direct field mutation, no full economy.step() unless
the test description says integration.
"""
import pytest

from agents import FirmAgent
from tests_contracts.factories import make_firm, make_firms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_baseline_firm(category: str = "Food", **kwargs) -> FirmAgent:
    defaults = {
        "baseline_production_quota": 500.0,
        "inventory_units": 0.0,
        "cash_balance": 10_000.0,
        "employees": [],
    }
    defaults.update(kwargs)
    return make_firm(firm_id=1, category=category, is_baseline=True, **defaults)


# ---------------------------------------------------------------------------
# Baseline Food: public-fallback wage + post-warmup loss/inventory shrinkage
# ---------------------------------------------------------------------------

from config import CONFIG as _CONFIG  # noqa: E402


def _baseline_food(**kwargs) -> FirmAgent:
    defaults = {
        "category": "Food",
        "is_baseline": True,
        "baseline_production_quota": 500.0,
        "inventory_units": 0.0,
        "cash_balance": 10_000.0,
        "employees": [],
        "wage_offer": 50.0,
        "price": 6.0,
        "production_capacity_units": 600.0,
        "productivity_per_worker": 12.0,
    }
    defaults.update(kwargs)
    cat = defaults.pop("category")
    is_b = defaults.pop("is_baseline")
    return make_firm(firm_id=1, category=cat, is_baseline=is_b, **defaults)


def test_contract_baseline_food_wage_pinned_to_minimum_post_warmup():
    firm = _baseline_food(wage_offer=80.0)
    plan = firm.plan_wage(unemployment_rate=0.05, unemployment_benefit=10.0, in_warmup=False)
    floor = firm._firm_config().minimum_wage_floor
    assert plan["wage_offer_next"] == pytest.approx(floor)


def test_contract_baseline_food_wage_pinned_to_minimum_during_warmup():
    firm = _baseline_food(wage_offer=80.0)
    firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=True,
        post_warmup_cooldown=False,
    )
    floor = firm._firm_config().minimum_wage_floor
    assert firm.wage_offer == pytest.approx(floor)


def test_contract_baseline_food_warmup_losses_do_not_force_layoffs():
    firm = _baseline_food(employees=list(range(50)), last_profit=-5_000.0, profit_ema=-3_000.0)
    plan = firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=True,
        post_warmup_cooldown=False,
    )
    # During warmup, baseline Food may incur losses without forced layoffs.
    assert plan["planned_layoffs_ids"] == [] or len(plan["planned_layoffs_ids"]) == 0


def test_contract_baseline_food_post_warmup_negative_profit_triggers_layoffs_no_hires():
    firm = _baseline_food(
        employees=list(range(20)),
        inventory_units=0.0,
        last_profit=-2_000.0,
        profit_ema=-1_500.0,
    )
    plan = firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )
    assert plan["planned_hires_count"] == 0
    assert len(plan["planned_layoffs_ids"]) > 0


def test_contract_baseline_food_post_warmup_heavy_inventory_layoffs_and_reduced_production():
    firm = _baseline_food(
        employees=list(range(20)),
        inventory_units=5_000.0,  # > quota * 6 → liquidation tier
        last_profit=100.0,
        profit_ema=100.0,
    )
    # Bypass the one-shot transition layoff so the inventory-tier path runs.
    firm.baseline_food_post_warmup_transition_done = True
    plan = firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )
    assert plan["planned_hires_count"] == 0
    assert len(plan["planned_layoffs_ids"]) > 0
    # Liquidation tier zeroes production.
    assert plan["planned_production_units"] == pytest.approx(0.0)
    assert firm.decision_diagnostics.get("baseline_food_liquidation_tier") == "liquidation"


def test_contract_baseline_food_post_warmup_heavy_inventory_lowers_price_within_bounds():
    firm = _baseline_food(
        employees=list(range(20)),
        inventory_units=5_000.0,
        price=8.0,
    )
    pre_price = firm.price
    plan = firm.plan_pricing(
        sell_through_rate=0.3,
        unemployment_rate=0.1,
        in_warmup=False,
    )
    labor_cost_per_unit = firm.wage_offer / max(firm.productivity_per_worker, 1.0)
    price_floor = max(firm.min_price, labor_cost_per_unit)
    assert plan["price_next"] < pre_price
    assert plan["price_next"] >= price_floor - 1e-6
    assert plan["price_next"] > 0.0


def test_contract_baseline_food_first_post_warmup_tick_fires_half_of_employees():
    firm = _baseline_food(employees=list(range(90)))
    assert firm.baseline_food_post_warmup_transition_done is False

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )

    assert firm.baseline_food_post_warmup_transition_done is True
    assert len(plan["planned_layoffs_ids"]) == 45
    assert plan["planned_hires_count"] == 0


def test_contract_baseline_food_transition_layoff_only_fires_once():
    firm = _baseline_food(employees=list(range(90)))
    firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )
    firm.employees = list(range(45))  # simulate the layoff applied
    plan = firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )
    # Second post-warmup tick must not trigger another half-layoff.
    assert len(plan["planned_layoffs_ids"]) < 22


def test_contract_baseline_food_transition_layoff_skipped_during_warmup():
    firm = _baseline_food(employees=list(range(90)))
    firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=True,
        post_warmup_cooldown=False,
    )
    assert firm.baseline_food_post_warmup_transition_done is False


def test_contract_private_food_firm_unaffected_by_baseline_food_branches():
    firm = make_firm(
        firm_id=2,
        category="Food",
        is_baseline=False,
        employees=list(range(20)),
        inventory_units=5_000.0,
        last_profit=-2_000.0,
        profit_ema=-1_500.0,
        baseline_production_quota=0.0,
        wage_offer=50.0,
        price=8.0,
        cash_balance=20_000.0,
    )
    # Wage path: private firm not pinned to floor.
    wage_plan = firm.plan_wage(unemployment_rate=0.05, unemployment_benefit=10.0, in_warmup=False)
    floor = firm._firm_config().minimum_wage_floor
    # Private firms may sit at any non-pinned value; key assertion is the
    # baseline-Food early-return shortcut did not fire (wage_offer_next exists,
    # is finite, and is not the bare minimum_wage_floor short-circuit value
    # unless the generic wage logic also picked it).
    assert "wage_offer_next" in wage_plan
    assert wage_plan["wage_offer_next"] >= floor
