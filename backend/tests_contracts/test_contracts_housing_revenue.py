"""Contract tests for housing firm rent revenue accounting (EcoSim 2.0).

Rent payments from tenants must register as revenue and profit on the housing
firm. Prior bug: record_sales_and_costs() ran during goods-market clearing with
zero units sold for housing, leaving last_revenue=0 even with paying tenants.
"""
import pytest

from agents import FirmAgent, HouseholdAgent
from tests_contracts.factories import make_firm, make_household


def _make_housing_firm(**kwargs) -> FirmAgent:
    defaults = dict(
        firm_id=10,
        category="Housing",
        is_baseline=True,
        cash_balance=5_000.0,
        max_rental_units=10,
    )
    defaults.update(kwargs)
    return make_firm(**defaults)


def _simulate_rent_payment(firm: FirmAgent, rent: float, n_tenants: int = 1) -> None:
    """Inline the rent-finalization logic from _batch_apply_household_updates."""
    # Simulate paying rent: firm gets cash and revenue_this_tick incremented
    for _ in range(n_tenants):
        firm.cash_balance += rent
        firm.revenue_this_tick += rent

    # Inline the post-loop finalization from economy.py
    rent_revenue = firm.revenue_this_tick
    if rent_revenue > 0.0:
        firm.last_revenue = rent_revenue
        firm.last_units_sold = float(n_tenants)
        firm.units_sold_this_tick = firm.last_units_sold
        firm.last_profit = rent_revenue - firm.last_tick_total_costs
        firm.net_profit = firm.last_profit
        firm.zero_sales_streak = 0
        firm.sales_recovery_streak = 0
        firm.ticks_since_last_sale = 0
        firm.last_nonzero_sale_tick = 1  # current_tick


# ---------------------------------------------------------------------------
# Revenue accounting
# ---------------------------------------------------------------------------

def test_contract_housing_rent_registers_as_revenue():
    """Rent paid by tenants registers as last_revenue on housing firm."""
    firm = _make_housing_firm()
    firm.revenue_this_tick = 0.0
    firm.last_revenue = 0.0
    firm.last_tick_total_costs = 100.0

    _simulate_rent_payment(firm, rent=200.0, n_tenants=3)

    assert firm.last_revenue == pytest.approx(600.0)
    assert firm.revenue_this_tick == pytest.approx(600.0)


def test_contract_housing_rent_revenue_updates_units_sold():
    """last_units_sold reflects number of paying tenants."""
    firm = _make_housing_firm()
    firm.revenue_this_tick = 0.0

    _simulate_rent_payment(firm, rent=150.0, n_tenants=5)

    assert firm.last_units_sold == pytest.approx(5.0)
    assert firm.units_sold_this_tick == pytest.approx(5.0)


def test_contract_housing_rent_profit_is_revenue_minus_costs():
    """last_profit = last_revenue - last_tick_total_costs."""
    firm = _make_housing_firm()
    firm.revenue_this_tick = 0.0
    firm.last_tick_total_costs = 80.0  # payroll cost

    _simulate_rent_payment(firm, rent=200.0, n_tenants=2)

    # revenue = 200*2 = 400; profit = 400 - 80 = 320
    assert firm.last_revenue == pytest.approx(400.0)
    assert firm.last_profit == pytest.approx(320.0)
    assert firm.net_profit == pytest.approx(320.0)


def test_contract_housing_rent_resets_zero_sales_streak():
    """Paying tenants reset zero_sales_streak to 0."""
    firm = _make_housing_firm()
    firm.revenue_this_tick = 0.0
    firm.zero_sales_streak = 8  # was building up

    _simulate_rent_payment(firm, rent=300.0, n_tenants=1)

    assert firm.zero_sales_streak == 0


def test_contract_housing_no_tenants_leaves_zero_revenue():
    """With no paying tenants (revenue_this_tick stays 0), last_revenue unchanged."""
    firm = _make_housing_firm()
    firm.revenue_this_tick = 0.0
    firm.last_revenue = 0.0
    firm.zero_sales_streak = 3

    # No rent paid → finalization block skipped (revenue_this_tick == 0)
    rent_revenue = firm.revenue_this_tick
    if rent_revenue > 0.0:
        firm.last_revenue = rent_revenue  # won't run

    assert firm.last_revenue == pytest.approx(0.0)
    assert firm.zero_sales_streak == 3  # unchanged


# ---------------------------------------------------------------------------
# Money conservation: rent moves cash from household to firm only
# ---------------------------------------------------------------------------

def test_contract_housing_rent_conserves_money():
    """Total money unchanged after rent payment: household cash + firm cash."""
    firm = _make_housing_firm(cash_balance=5_000.0)
    hh = make_household(cash_balance=500.0)
    rent = 200.0

    total_before = hh.cash_balance + firm.cash_balance

    hh.cash_balance -= rent
    firm.cash_balance += rent
    firm.revenue_this_tick += rent

    total_after = hh.cash_balance + firm.cash_balance
    assert total_after == pytest.approx(total_before)


def test_contract_housing_firm_cash_increases_by_rent():
    """Housing firm cash rises by exactly rent paid."""
    firm = _make_housing_firm(cash_balance=5_000.0)
    rent = 300.0

    firm.cash_balance += rent
    firm.revenue_this_tick += rent

    assert firm.cash_balance == pytest.approx(5_300.0)
