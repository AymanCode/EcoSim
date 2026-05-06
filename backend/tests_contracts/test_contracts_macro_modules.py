"""Contract tests for Module 1 (demand-weighted spawning) and Module 2 (Phillips Curve wages).

Module 1 invariants:
- saturated market (food_unmet == services_unmet == 0) aborts spawn entirely
- food-heavy unmet demand always spawns a Food firm
- services-only unmet demand always spawns a Services firm
- _clear_goods_market accumulates per-category unmet demand correctly

Module 2 invariants:
- labor surplus (unemployment_short_ma > NAIRU) pins wage_offer to minimum floor
- labor shortage + hire failure bumps wage 5% when affordable
- labor shortage + hire failure skips bump when new_wage / productivity >= price
"""

import pytest

from agents import FirmAgent
from config import CONFIG
from tests_contracts.factories import make_economy, make_household, make_households, make_firm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NAIRU = CONFIG.firms.nairu_threshold  # 0.05


def _spawnable_economy(food_unmet: float = 0.0, services_unmet: float = 0.0):
    """Economy out of warmup with enough room to spawn one firm."""
    # Housing firm: 20 units >= 5 households → housing priority bypassed
    housing_firm = make_firm(firm_id=1, category="Housing", is_baseline=False)
    food_firm = make_firm(firm_id=2, category="Food", is_baseline=False)
    svc_firm = make_firm(firm_id=3, category="Services", is_baseline=False)

    hhs = make_households(5)
    eco = make_economy(
        households=hhs,
        firms=[housing_firm, food_firm, svc_firm],
        baseline_firms=False,
    )
    eco.in_warmup = False
    eco.current_tick = 20
    eco.target_total_firms = 100
    eco.food_unmet_demand = food_unmet
    eco.services_unmet_demand = services_unmet
    return eco


def _plain_food_firm(*, wage_offer: float = 20.0, price: float = 100.0) -> FirmAgent:
    """Non-baseline, non-healthcare Food firm for wage tests."""
    firm = FirmAgent(
        firm_id=10,
        good_name="food",
        cash_balance=10_000.0,
        inventory_units=200.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=wage_offer,
        price=price,
        expected_sales_units=50.0,
        production_capacity_units=500.0,
        productivity_per_worker=12.0,
        personality="moderate",
        is_baseline=False,
    )
    return firm


# ---------------------------------------------------------------------------
# Module 1: Demand-Weighted Firm Spawning
# ---------------------------------------------------------------------------

def test_contract_saturated_market_aborts_spawn():
    """Zero total unmet demand → no new firm created."""
    eco = _spawnable_economy(food_unmet=0.0, services_unmet=0.0)
    before = len(eco.firms)

    eco._maybe_create_new_firms()

    assert len(eco.firms) == before  # no spawn


def test_contract_food_demand_spawns_food_firm():
    """food_unmet > 0, services_unmet == 0 → chosen_category == Food."""
    eco = _spawnable_economy(food_unmet=500.0, services_unmet=0.0)
    before = len(eco.firms)

    eco._maybe_create_new_firms()

    assert len(eco.firms) == before + 1
    assert eco.firms[-1].good_category == "Food"


def test_contract_services_demand_spawns_services_firm():
    """services_unmet > 0, food_unmet == 0 → chosen_category == Services."""
    eco = _spawnable_economy(food_unmet=0.0, services_unmet=500.0)
    before = len(eco.firms)

    eco._maybe_create_new_firms()

    assert len(eco.firms) == before + 1
    assert eco.firms[-1].good_category == "Services"


def test_contract_goods_market_records_food_shortfall():
    """_clear_goods_market increments food_unmet_demand when inventory runs out.

    Uses direct firm_id targets (the production code path).
    """
    firm = make_firm(firm_id=5, category="Food", is_baseline=False)
    firm.inventory_units = 3.0  # only 3 units available

    hhs = make_households(1)
    eco = make_economy(households=hhs, firms=[firm], baseline_firms=False)
    eco.food_unmet_demand = 0.0

    # Direct firm_id key (int) → production purchase path
    plans = {hhs[0].household_id: {"planned_purchases": {firm.firm_id: 10.0}}}
    eco._clear_goods_market(plans, [firm])

    assert eco.food_unmet_demand == pytest.approx(7.0, abs=1e-6)


def test_contract_goods_market_records_services_shortfall():
    """_clear_goods_market increments services_unmet_demand for Services firms."""
    firm = make_firm(firm_id=5, category="Services", is_baseline=False)
    firm.inventory_units = 2.0

    hhs = make_households(1)
    eco = make_economy(households=hhs, firms=[firm], baseline_firms=False)
    eco.services_unmet_demand = 0.0

    plans = {hhs[0].household_id: {"planned_purchases": {firm.firm_id: 8.0}}}
    eco._clear_goods_market(plans, [firm])

    assert eco.services_unmet_demand == pytest.approx(6.0, abs=1e-6)


def test_contract_fully_satisfied_demand_leaves_unmet_zero():
    """When supply exceeds demand, unmet trackers stay at zero."""
    firm = make_firm(firm_id=5, category="Food", is_baseline=False)
    firm.inventory_units = 100.0

    hhs = make_households(1)
    eco = make_economy(households=hhs, firms=[firm], baseline_firms=False)
    eco.food_unmet_demand = 0.0

    plans = {hhs[0].household_id: {"planned_purchases": {firm.firm_id: 5.0}}}
    eco._clear_goods_market(plans, [firm])

    assert eco.food_unmet_demand == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Module 2: Phillips Curve Wage Algorithm
# ---------------------------------------------------------------------------

def test_contract_phillips_surplus_pins_to_benefit_floor():
    """unemployment_short_ma > NAIRU → wage clamped to max(min_wage, benefit*1.5)."""
    firm = _plain_food_firm(wage_offer=50.0)
    benefit = 12.0
    plan = firm.plan_wage(
        unemployment_benefit=benefit,
        in_warmup=False,
        unemployment_short_ma=_NAIRU + 0.10,  # clearly in surplus
    )
    expected_floor = max(CONFIG.firms.minimum_wage_floor, benefit * 1.5)
    assert plan["wage_offer_next"] == pytest.approx(expected_floor, rel=1e-6)


def test_contract_phillips_shortage_bumps_wage_when_hire_failed():
    """unemployment_short_ma <= NAIRU + hire failure + affordable → 5% bump."""
    firm = _plain_food_firm(wage_offer=20.0, price=1000.0)  # price far exceeds any bump
    firm.last_tick_planned_hires = 3
    firm.last_tick_actual_hires = 1  # failed to fill 2 positions

    plan = firm.plan_wage(
        unemployment_benefit=5.0,
        in_warmup=False,
        unemployment_short_ma=_NAIRU - 0.02,  # labor shortage
    )
    assert plan["wage_offer_next"] == pytest.approx(20.0 * 1.05, rel=1e-6)


def test_contract_phillips_shortage_skips_bump_when_unaffordable():
    """unemployment_short_ma <= NAIRU + hire failure but bumped wage exceeds price → no 5% bump."""
    # bumped = wage*1.05; productivity ≈ units_per_worker(default=20) * K^0.25 ≈ 39.4
    # want bumped/productivity >= price:  (wage*1.05)/39.4 >= price
    # set wage=500, price=10: 525/39.4 ≈ 13.3 >= 10 → unaffordable
    firm = _plain_food_firm(wage_offer=500.0, price=10.0)
    firm.last_tick_planned_hires = 2
    firm.last_tick_actual_hires = 0

    plan = firm.plan_wage(
        unemployment_benefit=5.0,
        in_warmup=False,
        unemployment_short_ma=_NAIRU - 0.02,
    )
    assert plan["wage_offer_next"] != pytest.approx(500.0 * 1.05, rel=1e-4)


def test_contract_phillips_no_bump_when_hiring_succeeded():
    """No hire failure → 5% bump skipped even in tight market."""
    firm = _plain_food_firm(wage_offer=20.0, price=1000.0)
    firm.last_tick_planned_hires = 3
    firm.last_tick_actual_hires = 3  # all hires succeeded

    plan = firm.plan_wage(
        unemployment_benefit=5.0,
        in_warmup=False,
        unemployment_short_ma=_NAIRU - 0.02,
    )
    assert plan["wage_offer_next"] != pytest.approx(20.0 * 1.05, rel=1e-4)


def test_contract_phillips_warmup_bypasses_curve():
    """During warmup (in_warmup=True), Phillips Curve is NOT applied."""
    firm = _plain_food_firm(wage_offer=20.0, price=1000.0)
    firm.last_tick_planned_hires = 5
    firm.last_tick_actual_hires = 0

    plan_warmup = firm.plan_wage(
        unemployment_benefit=5.0,
        in_warmup=True,
        unemployment_short_ma=_NAIRU - 0.02,
    )
    # Warmup takes a different code path entirely; result differs from 5% bump
    assert plan_warmup["wage_offer_next"] != pytest.approx(20.0 * 1.05, rel=1e-4)
