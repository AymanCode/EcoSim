"""Contracts for re-offering an unfilled firm order to the sector's baseline firm."""

import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from economy import Economy


def _food_firm(firm_id: int, *, inventory: float, price: float, is_baseline: bool) -> FirmAgent:
    return FirmAgent(
        firm_id=firm_id,
        good_name=("BaselineFood" if is_baseline else f"FoodCo{firm_id}"),
        cash_balance=10_000.0,
        inventory_units=inventory,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=price,
        expected_sales_units=100.0,
        production_capacity_units=500.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=is_baseline,
    )


def _economy(firms):
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=10_000.0)
    government = GovernmentAgent(cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0)
    return Economy(households=[household], firms=firms, government=government)


def test_contract_sold_out_private_food_order_is_filled_by_baseline():
    """A private Food firm sells out; the rest of the order goes to the baseline firm."""
    private = _food_firm(1, inventory=10.0, price=5.0, is_baseline=False)
    baseline = _food_firm(2, inventory=100.0, price=5.0, is_baseline=True)
    economy = _economy([private, baseline])
    plans = {1: {"planned_purchases": {private.firm_id: 30.0}}}

    purchases, sales = economy._clear_goods_market(plans, [private, baseline])

    assert sales[private.firm_id]["units_sold"] == pytest.approx(10.0)
    assert sales[baseline.firm_id]["units_sold"] == pytest.approx(20.0)
    assert purchases[1][baseline.good_name] == pytest.approx((20.0, 5.0))
    assert economy.food_unmet_demand == pytest.approx(0.0)
    # The private firm still sees the sale it lost, so its demand signal is unchanged.
    assert economy.current_tick_unmet_demand_by_firm[private.firm_id] == pytest.approx(20.0)


def test_contract_spillover_spends_no_more_than_the_unfilled_order():
    """The leftover money, not the leftover units, moves to the baseline price."""
    private = _food_firm(1, inventory=0.0, price=4.0, is_baseline=False)
    baseline = _food_firm(2, inventory=100.0, price=8.0, is_baseline=True)
    economy = _economy([private, baseline])
    plans = {1: {"planned_purchases": {private.firm_id: 10.0}}}

    purchases, sales = economy._clear_goods_market(plans, [private, baseline])

    # 10 units x $4 = $40 unspent; at $8 that buys 5 baseline units.
    assert sales[baseline.firm_id]["revenue"] == pytest.approx(40.0)
    assert purchases[1][baseline.good_name] == pytest.approx((5.0, 8.0))
    assert economy.food_unmet_demand == pytest.approx(0.0)


def test_contract_spillover_unmet_is_what_the_baseline_could_not_cover():
    """When the baseline runs short too, only the uncovered part counts as unmet."""
    private = _food_firm(1, inventory=0.0, price=5.0, is_baseline=False)
    baseline = _food_firm(2, inventory=4.0, price=5.0, is_baseline=True)
    economy = _economy([private, baseline])
    plans = {1: {"planned_purchases": {private.firm_id: 10.0}}}

    _, sales = economy._clear_goods_market(plans, [private, baseline])

    assert sales[baseline.firm_id]["units_sold"] == pytest.approx(4.0)
    assert economy.food_unmet_demand == pytest.approx(6.0)


def test_contract_cheaper_baseline_fills_the_same_units_not_more():
    """A cheaper baseline fills the missing units; the saved money is not spent on extra food."""
    private = _food_firm(1, inventory=0.0, price=8.0, is_baseline=False)
    baseline = _food_firm(2, inventory=100.0, price=4.0, is_baseline=True)
    economy = _economy([private, baseline])
    plans = {1: {"planned_purchases": {private.firm_id: 10.0}}}

    _, sales = economy._clear_goods_market(plans, [private, baseline])

    assert sales[baseline.firm_id]["units_sold"] == pytest.approx(10.0)
    assert sales[baseline.firm_id]["revenue"] == pytest.approx(40.0)


def test_contract_baseline_order_that_runs_short_is_not_respilled():
    """An order placed at the baseline itself has no fallback and stays unmet."""
    private = _food_firm(1, inventory=100.0, price=5.0, is_baseline=False)
    baseline = _food_firm(2, inventory=3.0, price=5.0, is_baseline=True)
    economy = _economy([private, baseline])
    plans = {1: {"planned_purchases": {baseline.firm_id: 10.0}}}

    _, sales = economy._clear_goods_market(plans, [private, baseline])

    assert sales[baseline.firm_id]["units_sold"] == pytest.approx(3.0)
    assert sales[private.firm_id]["units_sold"] == pytest.approx(0.0)
    assert economy.food_unmet_demand == pytest.approx(7.0)
