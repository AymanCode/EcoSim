"""Household care, rent and loan settlement contracts."""

import pytest

from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent
from config import clone_config, use_config
from economy import Economy
from payment_loans import collect_household_dues, originate_v2, prepare_household_dues
from payment_sectors import enqueue_payment_care_requests, settle_payment_care, settle_payment_rent
from payments import PaymentBook


@pytest.fixture(autouse=True)
def income_first():
    config = clone_config()
    config.payment_sequence = "income_first"
    config.payment_care_request_slope = 1.0
    with use_config(config):
        yield config


def make_economy(households, firms, bank=True):
    gov = GovernmentAgent(cash_balance=1_000_000.0)
    eco = Economy(households, firms, gov, bank=BankAgent(cash_reserves=10_000.0) if bank else None)
    eco.payment_book = PaymentBook(eco, "income_first")
    return eco


def household(hid, cash=0):
    return HouseholdAgent(household_id=hid, skills_level=0.6, age=30, cash_balance=cash)


def firm(fid, category, cash=0, price=10):
    return FirmAgent(firm_id=fid, good_name=category, good_category=category,
                     cash_balance=cash, inventory_units=0, price=price)


def test_opened_care_episode_defers_then_queues_on_retry(monkeypatch):
    patient = household(1)
    patient.health = 0.8
    clinic = firm(8, "Healthcare", price=100)
    eco = make_economy([patient], [clinic])
    monkeypatch.setattr(eco, "_choose_healthcare_provider", lambda h, firms: clinic)
    monkeypatch.setattr(HouseholdAgent, "_deterministic_unit_random", lambda self, tick, salt: 0.0 if salt == 17 else 0.99)
    before = (patient.cash_balance, clinic.cash_balance, eco.bank.cash_reserves, eco.government.cash_balance)
    enqueue_payment_care_requests(eco)
    visits = patient.pending_healthcare_visits
    assert visits > 0
    assert eco.payment_care_deferrals_this_tick == 1
    assert eco.healthcare_requests_this_tick == 0
    assert not clinic.healthcare_queue
    assert (patient.cash_balance, clinic.cash_balance, eco.bank.cash_reserves, eco.government.cash_balance) == before

    # A due retry queues care without opening a new episode.
    patient.payment_care_due_retry = True
    patient.payment_care_accepted_quote = 100.0
    enqueue_payment_care_requests(eco)
    assert clinic.healthcare_queue == [1]
    assert patient.pending_healthcare_visits == visits
    assert eco.healthcare_requests_this_tick == 0
    assert (patient.cash_balance, clinic.cash_balance, eco.bank.cash_reserves, eco.government.cash_balance) == before


def test_completed_visit_uses_covered_care_funds(monkeypatch):
    patient = household(1)
    patient.health = 0.5
    patient.pending_healthcare_visits = 1
    patient.pending_visit_heal_delta = 0.2
    patient.payment_care_due_tick = 0
    patient.payment_care_accepted_quote = 25.0
    patient.queued_healthcare_firm_id = 8
    clinic = firm(8, "Healthcare", price=25)
    clinic.healthcare_queue = [1]
    eco = make_economy([patient], [clinic])
    eco.payment_care_mode = "covered"
    eco.payment_care_remaining = 25
    eco.payment_state["restrictions"]["care"] = 25
    monkeypatch.setattr("payment_sectors._qualified_capacity", lambda e, f: 1.0)
    monkeypatch.setattr(eco, "_prioritize_healthcare_queue", lambda f: None)
    before = eco.government.cash_balance
    settle_payment_care(eco, eco.payment_book.receipts)
    assert eco.healthcare_completed_visits_this_tick == 1
    assert patient.pending_healthcare_visits == 0
    assert patient.health == pytest.approx(0.7)
    assert eco.government.cash_balance == before - 25
    assert eco.payment_book.clearing_cash == 25
    assert patient.cash_balance == clinic.cash_balance == 0


def test_new_care_admission_enters_queue(monkeypatch):
    patient = household(1)
    patient.health = 0.2
    clinic = firm(8, "Healthcare", price=25)
    eco = make_economy([patient], [clinic])
    monkeypatch.setattr(eco, "_choose_healthcare_provider", lambda h, firms: clinic)
    monkeypatch.setattr(HouseholdAgent, "_deterministic_unit_random", lambda *args, **kwargs: 0.0)
    enqueue_payment_care_requests(eco)
    assert eco.healthcare_requests_this_tick == 1
    assert clinic.healthcare_queue == [1]


def test_missing_landlord_and_expired_notice_evict_without_moving_cash():
    missing, notice = household(1), household(2)
    missing.renting_from_firm_id, missing.monthly_rent = 999, 10
    notice.renting_from_firm_id, notice.monthly_rent = 2, 10
    notice.rent_arrears, notice.rent_notice_remaining = 5, 1
    landlord = firm(2, "Housing", cash=50)
    landlord.max_rental_units = 2
    landlord.current_tenants = [2]
    eco = make_economy([missing, notice], [landlord])
    before = (missing.cash_balance, notice.cash_balance, landlord.cash_balance, eco.government.cash_balance)
    settle_payment_rent(eco)
    assert eco.last_housing_diagnostics["eviction_count"] == 2
    assert all(h.renting_from_firm_id is None and h.rent_arrears == 0 for h in (missing, notice))
    assert landlord.current_tenants == []
    assert (missing.cash_balance, notice.cash_balance, landlord.cash_balance, eco.government.cash_balance) == before


def test_partial_collection_and_default_leave_correct_loan_balances(monkeypatch):
    partial, default, medical = household(1, 4), household(2, 1), household(3, 0)
    eco = make_economy([partial, default, medical], [])
    monkeypatch.setattr("payment_loans.can_underwrite", lambda *a, **kw: True)
    for h, subtype in ((partial, "consumption"), (default, "consumption"), (medical, "medical")):
        claim = originate_v2(eco, "household", h.household_id, 100, 0, 10, subtype)
        assert claim is not None
        if h is not partial:
            claim["missed_payments"] = 7
    eco.current_tick = 1
    eco.payment_book = PaymentBook(eco, "income_first")
    assert prepare_household_dues(eco) == {1: 10, 2: 10, 3: 10}
    before = eco.bank.cash_reserves
    assert collect_household_dues(eco) == 5
    assert eco.bank.cash_reserves == before + 5
    assert [h.cash_balance for h in (partial, default, medical)] == [0, 0, 0]
    # The partial payment reduces principal by $4. Both defaulted loans close.
    assert partial.consumption_loan_remaining == pytest.approx(96)
    assert default.consumption_loan_remaining == 0
    assert medical.medical_loan_remaining == 0


def test_healthcare_financing_at_bank_government_and_bailout_credits(monkeypatch):
    h, clinic = household(1), firm(8, "Healthcare")
    eco = make_economy([h], [clinic])
    monkeypatch.setattr("payment_loans.can_underwrite", lambda *a, **kw: True)
    monkeypatch.setattr(BankAgent, "_max_firm_borrowable", lambda *a: 1000)
    before_bank = eco.bank.cash_reserves
    assert eco._issue_firm_loan(clinic, 10, 52, 0.03) == 10
    assert (eco.bank.cash_reserves, clinic.cash_balance) == (before_bank - 10, 10)
    monkeypatch.setattr(BankAgent, "can_lend", lambda self: False)
    before_gov = eco.government.cash_balance
    assert eco._issue_firm_loan(clinic, 20, 52, 0.03) == 20
    assert (eco.government.cash_balance, clinic.cash_balance) == (before_gov - 20, 30)
    eco.government.bailout_policy = "all"
    eco.government.bailout_budget_remaining = 1000
    monkeypatch.setattr(eco, "_is_bailout_candidate", lambda f: True)
    monkeypatch.setattr(eco, "_bailout_need_amount", lambda f: 30)
    eco._execute_bailouts()
    assert clinic.cash_balance == 60
    assert eco.government.cash_balance == before_gov - 50
