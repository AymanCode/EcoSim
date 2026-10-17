"""Existing tenants pay the landlord's current posted rent (legacy payment path).

Before this fix a tenant paid the rent written at signing forever: every
household in a seeded run paid the starting 20/wk while the Housing firm
posted 5/wk. These tests drive ``Economy._clear_housing_rental_market`` and
``Economy._legacy_obligations_due`` (the two places the legacy tick reads the
rent a tenant owes) and check what tenants and the landlord can observe:
cash moved, the contract rent, and the rent reserved before shopping.
"""

import pytest

from agents import GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy
from tests_contracts.factories import make_firm, make_household


SIGNED_RENT = 20.0
POSTED_RENT = 5.0


def _economy_with_tenant(*, signed: float, posted: float, cash: float = 500.0):
    household: HouseholdAgent = make_household(household_id=1, cash_balance=cash)
    household.employer_id = 99
    household.wage = 1_000.0
    household.renting_from_firm_id = 10
    household.monthly_rent = signed
    household.owns_housing = True

    firm = make_firm(
        firm_id=10,
        category="Housing",
        is_baseline=True,
        cash_balance=5_000.0,
        max_rental_units=10,
        price=posted,
    )
    firm.current_tenants = [household.household_id]
    government = GovernmentAgent(cash_balance=50_000.0, unemployment_benefit_level=0.0, transfer_budget=0.0)
    economy = Economy(households=[household], firms=[firm], government=government)
    return economy, household, firm


@pytest.fixture
def tracking(monkeypatch):
    monkeypatch.setattr(CONFIG.labor_market, "rent_tracks_posted_price", True, raising=False)


def test_existing_tenant_pays_posted_rent_when_it_fell(tracking):
    economy, household, firm = _economy_with_tenant(signed=SIGNED_RENT, posted=POSTED_RENT)
    firm_cash = firm.cash_balance

    economy._clear_housing_rental_market()

    assert household.cash_balance == pytest.approx(500.0 - POSTED_RENT)
    assert firm.cash_balance == pytest.approx(firm_cash + POSTED_RENT)
    assert household.monthly_rent == pytest.approx(POSTED_RENT)


def test_existing_tenant_pays_posted_rent_when_it_rose(tracking):
    economy, household, firm = _economy_with_tenant(signed=10.0, posted=12.0)

    economy._clear_housing_rental_market()

    assert household.cash_balance == pytest.approx(500.0 - 12.0)
    assert household.monthly_rent == pytest.approx(12.0)


def test_rent_follows_posted_price_week_to_week(tracking):
    economy, household, firm = _economy_with_tenant(signed=SIGNED_RENT, posted=POSTED_RENT)
    paid = []
    for posted in (5.0, 5.75, 6.6):
        firm.price = posted
        before = household.cash_balance
        economy._clear_housing_rental_market()
        paid.append(before - household.cash_balance)
        # The occupancy rule inside the clearing call may move firm.price; the
        # next week's posted price is set explicitly above.
    assert paid == pytest.approx([5.0, 5.75, 6.6])


def test_tracked_rent_is_what_planning_reserves(tracking):
    economy, household, firm = _economy_with_tenant(signed=SIGNED_RENT, posted=POSTED_RENT)

    due = economy._legacy_obligations_due()

    assert due[0] == pytest.approx(POSTED_RENT)


def test_rise_above_affordability_evicts_without_payment(tracking):
    economy, household, firm = _economy_with_tenant(signed=5.0, posted=400.0, cash=300.0)
    household.wage = 100.0  # 30% of income is 30, plus 25% of cash (75) = 105 < 400
    firm_cash = firm.cash_balance

    economy._clear_housing_rental_market()

    assert household.renting_from_firm_id is None
    assert firm.cash_balance == pytest.approx(firm_cash)
    assert household.cash_balance == pytest.approx(300.0)


def test_flag_off_keeps_signed_rent(monkeypatch):
    monkeypatch.setattr(CONFIG.labor_market, "rent_tracks_posted_price", False, raising=False)
    economy, household, firm = _economy_with_tenant(signed=SIGNED_RENT, posted=POSTED_RENT)

    economy._clear_housing_rental_market()

    assert household.cash_balance == pytest.approx(500.0 - SIGNED_RENT)
    assert household.monthly_rent == pytest.approx(SIGNED_RENT)
    assert economy._legacy_obligations_due()[0] == pytest.approx(SIGNED_RENT)


def test_default_is_tracking():
    assert CONFIG.labor_market.rent_tracks_posted_price is True
