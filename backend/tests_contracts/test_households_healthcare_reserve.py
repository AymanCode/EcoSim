"""Households: cash held back for a queued healthcare visit.

With ``CONFIG.households.healthcare_cash_reservation`` on, a queued
household's weekly budget treats ``price * expected household share`` as
spoken for. The charge itself still happens at service, in the unchanged
``Economy._process_healthcare_services``. Run on the default (legacy) payment
path, where the healthcare subsidy pays.
"""

import pytest

from agents import FirmAgent, GovernmentAgent
from config import CONFIG
from economy import Economy
from tests_contracts.factories import make_household

PRICE = 60.0


@pytest.fixture
def reserve_on(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "healthcare_cash_reservation", True)


def _clinic(firm_id=900, price=PRICE):
    clinic = FirmAgent(
        firm_id=firm_id, good_name="Clinic", cash_balance=20_000.0, inventory_units=0.0,
        good_category="Healthcare", quality_level=6.0, wage_offer=40.0, price=price,
        expected_sales_units=100.0, production_capacity_units=500.0,
        productivity_per_worker=12.0, personality="moderate",
    )
    clinic.employees = [5001, 5002]
    clinic.healthcare_capacity_per_worker = 1.0
    return clinic


def _economy(households, *, subsidy_level=50, budget=1_000_000.0, clinic=None):
    clinic = clinic or _clinic()
    government = GovernmentAgent(cash_balance=1_000_000.0)
    if subsidy_level:
        government.set_lever("sector_subsidy_target", "healthcare")
        government.set_lever("sector_subsidy_level", subsidy_level)
    economy = Economy(households=list(households), firms=[clinic], government=government)
    economy._apply_random_shocks = lambda: None
    economy.sector_subsidy_remaining_this_tick = budget
    return economy, clinic


def _worker(hid, cash):
    household = make_household(hid, cash_balance=cash, bank_deposit=0.0)
    household.employer_id = 77
    household.wage = 400.0  # income budget far above cash, so the liquidity cap binds
    return household


def _queue(household, clinic):
    household.queued_healthcare_firm_id = clinic.firm_id
    household.healthcare_queue_enter_tick = 0
    clinic.healthcare_queue.append(household.household_id)


def _budgets(economy):
    return economy._household_consumption_budgets(0.05, 30.0)


def test_queued_household_spends_less_by_the_reserve(reserve_on):
    queued, free = _worker(1, 100.0), _worker(2, 100.0)
    economy, clinic = _economy([queued, free])
    _queue(queued, clinic)
    reserve = PRICE * economy.expected_healthcare_household_share(PRICE)
    assert reserve == pytest.approx(30.0)  # 50% subsidy, cap not binding
    budgets = _budgets(economy)
    assert budgets[1] == pytest.approx(100.0)
    assert budgets[0] == pytest.approx(100.0 - reserve)


def test_unqueued_household_is_unaffected(reserve_on, monkeypatch):
    queued, free = _worker(1, 100.0), _worker(2, 100.0)
    economy, clinic = _economy([queued, free])
    _queue(queued, clinic)
    on = _budgets(economy)
    monkeypatch.setattr(CONFIG.households, "healthcare_cash_reservation", False)
    off = _budgets(economy)
    assert on[1] == off[1]
    assert off[0] == pytest.approx(100.0)  # flag off: no reserve at all


def test_reserve_clears_when_served(reserve_on):
    queued = _worker(1, 100.0)
    economy, clinic = _economy([queued])
    _queue(queued, clinic)
    assert economy._healthcare_reservations()[0] == pytest.approx(30.0)
    economy._process_healthcare_services({})
    assert queued.queued_healthcare_firm_id is None
    assert economy._healthcare_reservations()[0] == 0.0
    assert _budgets(economy)[0] == pytest.approx(queued.cash_balance)


def test_reserve_clears_when_dropped_for_lack_of_funds(reserve_on):
    broke = make_household(1, cash_balance=5.0, bank_deposit=0.0)
    economy, clinic = _economy([broke], subsidy_level=0)
    economy.bank = None  # no medical loan possible
    _queue(broke, clinic)
    assert economy._healthcare_reservations()[0] == pytest.approx(PRICE)
    economy._process_healthcare_services({})
    assert broke.queued_healthcare_firm_id is None
    assert economy.healthcare_affordability_rejects_this_tick == 1.0
    assert economy._healthcare_reservations()[0] == 0.0


def test_reserve_lapses_when_the_provider_is_gone(reserve_on):
    queued = _worker(1, 100.0)
    economy, _clinic_firm = _economy([queued])
    queued.queued_healthcare_firm_id = 12345  # provider no longer in firm_lookup
    assert economy._healthcare_reservations()[0] == 0.0


@pytest.mark.parametrize("budget", [1_000_000.0, 10.0, 0.0])
def test_reserve_matches_the_charge_at_service_when_the_budget_is_unchanged(reserve_on, budget):
    queued = _worker(1, 500.0)
    economy, clinic = _economy([queued], budget=budget)
    _queue(queued, clinic)
    reserve = economy._healthcare_reservations()[0]
    cash_before = queued.cash_balance
    economy._process_healthcare_services({})
    assert queued.queued_healthcare_firm_id is None
    assert cash_before - queued.cash_balance == pytest.approx(reserve)
    assert reserve == pytest.approx({1_000_000.0: 30.0, 10.0: 50.0, 0.0: 60.0}[budget])


def test_no_subsidy_reserves_the_full_price(reserve_on):
    queued = _worker(1, 100.0)
    economy, clinic = _economy([queued], subsidy_level=0)
    _queue(queued, clinic)
    assert economy._healthcare_reservations()[0] == pytest.approx(PRICE)
