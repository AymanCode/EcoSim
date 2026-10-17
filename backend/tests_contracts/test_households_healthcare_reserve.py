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


# --- Payment sequences: the reserve against settle_payment_care -------------

def _income_first_run(care_mode, ticks=52, households=200, firms=3):
    """Seeded income_first run with the reserve on and the subsidy lever at
    50% (which settle_payment_care ignores). Returns, per care sale, the
    household's reserve and the price it used at this tick's budget, and the
    price and out-of-pocket share the sale charged."""
    import contextlib
    import io
    import random

    import numpy as np

    from config import clone_config, use_config
    from payments import PaymentBook
    from tools.runners.run_large_simulation import create_large_economy

    seen = []
    with use_config(clone_config()):
        random.seed(42)
        np.random.seed(42)
        CONFIG.random_seed = 42
        CONFIG.payment_sequence = "income_first"
        CONFIG.payment_care_mode = care_mode
        CONFIG.households.healthcare_cash_reservation = True
        if care_mode == "covered":
            CONFIG.payment_assistance = "care"  # funds the covered-care budget
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms)
        economy.government.set_lever("sector_subsidy_target", "healthcare")
        economy.government.set_lever("sector_subsidy_level", 50)

        at_budget = {}
        budgets_fn = economy._household_consumption_budgets

        def recording_budgets(*args, **kwargs):
            reserves = economy._healthcare_reservations()
            for household, reserve in zip(economy.households, reserves):
                firm = economy.firm_lookup.get(household.queued_healthcare_firm_id)
                if firm is not None:
                    at_budget[household.household_id] = (economy.current_tick, float(reserve), float(firm.price))
            return budgets_fn(*args, **kwargs)

        economy._household_consumption_budgets = recording_budgets
        original = PaymentBook.commit_sale

        def recording_sale(self, household, firm, qty, price, *, public_amount=0.0, bank_amount=0.0, kind="goods"):
            ok = original(self, household, firm, qty, price, public_amount=public_amount,
                          bank_amount=bank_amount, kind=kind)
            budget = at_budget.get(household.household_id)
            if kind == "care" and ok and price > 0.0 and budget is not None and budget[0] == economy.current_tick:
                seen.append((budget[1], budget[2], float(price), (price - public_amount) / price))
            return ok

        PaymentBook.commit_sale = recording_sale
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                for _ in range(ticks):
                    economy.step()
        finally:
            PaymentBook.commit_sale = original
    return seen


@pytest.mark.parametrize("care_mode,share", [("patient_pay", 1.0), ("covered", 0.0)])
def test_income_first_reserve_matches_settle_payment_care(care_mode, share):
    seen = _income_first_run(care_mode)
    assert seen, "no care visit was charged after a budget in the same tick"
    for reserve, budget_price, price, charged_share in seen:
        assert charged_share == pytest.approx(share)  # patient_pay: full price; covered: 0
        assert reserve == pytest.approx(budget_price * share)  # full price or 0, never the lever's 50%
        if budget_price == price:
            assert reserve == pytest.approx(price * charged_share)  # equals the charge when nothing moved
