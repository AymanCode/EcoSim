"""Contract tests for housing rental cash accounting.

Housing rent is collected in the rental-market phase, not through goods-market
sales rows. These tests exercise the current production path instead of
inlining the old ``revenue_this_tick`` finalization logic.
"""

import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from economy import Economy
from tests_contracts.factories import make_firm, make_household


def _make_housing_firm(**kwargs) -> FirmAgent:
    defaults = dict(
        firm_id=10,
        category="Housing",
        is_baseline=True,
        cash_balance=5_000.0,
        max_rental_units=10,
        price=200.0,
    )
    defaults.update(kwargs)
    return make_firm(**defaults)


def _make_rented_economy(*, rent: float = 200.0, household_cash: float = 500.0) -> tuple[Economy, HouseholdAgent, FirmAgent]:
    household = make_household(household_id=1, cash_balance=household_cash)
    household.employer_id = 99
    household.wage = 1_000.0
    household.renting_from_firm_id = 10
    household.monthly_rent = rent
    household.owns_housing = True

    firm = _make_housing_firm(price=rent)
    firm.current_tenants = [household.household_id]

    government = GovernmentAgent(cash_balance=50_000.0, unemployment_benefit_level=0.0, transfer_budget=0.0)
    economy = Economy(households=[household], firms=[firm], government=government)
    return economy, household, firm


def test_contract_existing_tenant_rent_conserves_money():
    economy, household, firm = _make_rented_economy(rent=200.0, household_cash=500.0)
    total_before = household.cash_balance + firm.cash_balance

    economy._clear_housing_rental_market()

    total_after = household.cash_balance + firm.cash_balance
    assert total_after == pytest.approx(total_before)


def test_contract_existing_tenant_rent_moves_cash_to_housing_firm():
    economy, household, firm = _make_rented_economy(rent=300.0, household_cash=500.0)
    firm_cash_before = firm.cash_balance

    economy._clear_housing_rental_market()

    assert household.cash_balance == pytest.approx(200.0)
    assert firm.cash_balance == pytest.approx(firm_cash_before + 300.0)
    assert household.renting_from_firm_id == firm.firm_id
    assert household.owns_housing is True


def test_contract_unaffordable_existing_tenant_is_evicted_without_rent_transfer():
    economy, household, firm = _make_rented_economy(rent=300.0, household_cash=50.0)
    household.wage = 0.0
    firm_cash_before = firm.cash_balance

    economy._clear_housing_rental_market()

    assert household.renting_from_firm_id is None
    assert household.monthly_rent == pytest.approx(0.0)
    assert household.household_id not in firm.current_tenants
    assert firm.cash_balance == pytest.approx(firm_cash_before)
    assert economy.last_housing_diagnostics["eviction_count"] == pytest.approx(1.0)
