"""Coordinator-owned checks of the composed public payment scenario.

Plans and employment are fixed in the small fixture so differences identify
settlement timing rather than a new job match or a changed demand hypothesis.
The engine's actual production, fiscal, rental, and household apply paths run.
"""

import copy
import contextlib
import io
import math
import random

import pytest
import numpy as np

from config import clone_config, use_config


def _one_worker(factory, monkeypatch, timing, performance_mode=False):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.payment_care_mode = "patient_pay"
    cfg.payment_assistance = "reserve"
    with use_config(cfg):
        worker = factory.household(
            household_id=1, employer_id=1, wage=100.0, cash_balance=0.0,
            goods_inventory={}, renting_from_firm_id=2, monthly_rent=50.0,
        )
        firm = factory.firm(
            firm_id=1, category="Food", employees=[1], actual_wages={1: 100.0},
            wage_offer=100.0, price=10.0, cash_balance=1000.0,
            inventory_units=100.0, ceo_household_id=None, owners=[],
        )
        landlord = factory.firm(
            firm_id=2, category="Housing", employees=[], actual_wages={},
            price=50.0, current_tenants=[1], cash_balance=1000.0,
            ceo_household_id=None, owners=[],
        )
        gov = factory.government(
            cash_balance=0.0, wage_tax_rate=0.0, profit_tax_rate=0.0,
            unemployment_benefit_level=0.0, transfer_budget=0.0,
        )
        economy = factory.economy(households=[worker], firms=[firm, landlord], government=gov)
    economy.current_tick = 5
    economy.warmup_ticks = 100
    economy.performance_mode = performance_mode
    economy.configure_stabilizers(households=False, firms=False, government=False)
    monkeypatch.setattr(economy, "_run_labor_matching", lambda *_: (
        {1: {"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}},
         2: {"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}}},
        {1: {"employer_id": 1, "wage": 100.0, "employer_category": "Food"}},
    ))
    monkeypatch.setattr(economy, "_batch_plan_consumption", lambda *_: {
        1: {"planned_purchases": {1: 2.0}, "budget": 20.0}
    })
    monkeypatch.setattr(economy, "_maybe_create_new_firms", lambda: 0)
    monkeypatch.setattr(economy, "_enqueue_healthcare_requests", lambda: None)
    return cfg, economy, worker, firm, landlord


@pytest.mark.parametrize("performance_mode", [False, True])
def test_public_step_income_arrives_before_rent_only_in_early_arm(factory, monkeypatch, performance_mode):
    results = {}
    for timing in ("income_first", "income_late"):
        cfg, economy, worker, firm, landlord = _one_worker(factory, monkeypatch, timing, performance_mode)
        with use_config(cfg):
            economy.step()
        ledger = worker.last_tick_ledger
        results[timing] = (ledger.get("rent", 0.0), worker.last_food_units)
        assert ledger.get("wage", 0.0) == pytest.approx(100.0)
        assert ledger.get("taxes", 0.0) == 0.0
        assert worker.last_wage_income == pytest.approx(100.0)
        assert economy.payment_book.clearing_cash == pytest.approx(0.0, abs=1e-6)
        assert not economy.payment_book.clearing_payables
        assert worker.renting_from_firm_id == landlord.firm_id  # A notice is not instant eviction.
    assert results["income_first"][0] == pytest.approx(-50.0)
    assert results["income_first"][1] == pytest.approx(2.0)
    assert results["income_late"] == pytest.approx((0.0, 0.0))


def test_invalid_withholding_cannot_partially_debit_employer(factory):
    from payments import PaymentBook

    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=80.0, cash_balance=0.0)
        firm = factory.firm(firm_id=1, employees=[1], actual_wages={1: 80.0}, cash_balance=60.0)
        gov = factory.government(cash_balance=0.0, wage_tax_rate=0.15)
        economy = factory.economy(households=[worker], firms=[firm], government=gov)
        # An invalid later input must be rejected before any payroll mutation.
        gov.wage_tax_rate = 3.0
        before = (firm.cash_balance, worker.cash_balance, gov.cash_balance, copy.deepcopy(economy.payment_state))
        book = PaymentBook(economy)
        with pytest.raises(ValueError):
            book.settle_income({1: 80.0})
        assert (firm.cash_balance, worker.cash_balance, gov.cash_balance, economy.payment_state) == before


def test_public_step_partial_wages_withholding_and_landlord_property_tax(factory, monkeypatch):
    cfg, economy, worker, firm, landlord = _one_worker(factory, monkeypatch, "income_first")
    firm.cash_balance = 60.0
    economy.government.wage_tax_rate = 0.15
    landlord.property_tax_rate = 0.01
    landlord.max_rental_units = 1
    with use_config(cfg):
        economy.step()
    paid = economy.payment_book.paid_income[worker.household_id]
    assert paid["gross"] == pytest.approx(60.0)
    assert paid["tax"] > 0
    assert paid["net"] + paid["tax"] == pytest.approx(60.0)
    assert economy.payment_state["wage_claims"][(firm.firm_id, worker.household_id)] == pytest.approx(40.0)
    # Maintenance/investment tax receipts can also change treasury cash later;
    # this fiscal receipt is the actual phase-11 wage/property tax total.
    assert economy.government.last_tick_revenue == pytest.approx(paid["tax"] + 0.5)
    assert worker.last_tick_ledger["taxes"] == pytest.approx(-paid["tax"])
    assert firm.cash_balance == pytest.approx(economy.payment_book.receipts[firm.firm_id]["revenue"])


def test_public_step_ceo_pay_is_once_and_unavailable_for_own_current_bills(factory, monkeypatch):
    from payment_sectors import PaymentGoodsMarket

    cfg, economy, worker, firm, landlord = _one_worker(factory, monkeypatch, "income_first")
    # The owner is also the worker; ordinary pay is spendable while CEO pay is held.
    firm.ceo_household_id = worker.household_id
    firm.cash_balance = 1000.0
    entering_window = []
    original_first_pass = PaymentGoodsMarket.first_pass

    def observe_window(market):
        entering_window.append(worker.cash_balance)
        return original_first_pass(market)

    monkeypatch.setattr(PaymentGoodsMarket, "first_pass", observe_window)
    with use_config(cfg):
        economy.step()
    row = economy.payment_book.paid_income[worker.household_id]
    assert row["gross"] == pytest.approx(100.0)
    assert row["ceo"] == pytest.approx(300.0)
    assert worker.last_tick_ledger["wage"] == pytest.approx(400.0)
    assert entering_window == pytest.approx([100.0])
    assert worker.cash_balance == pytest.approx(330.0 + worker.last_tick_ledger["redistribution"])
    assert not economy.payment_state["ceo_holds"]
    assert firm.cash_balance == pytest.approx(620.0)


@pytest.mark.parametrize("mode", [False, True])
@pytest.mark.parametrize("timing", ["income_first", "income_late"])
def test_multiple_public_steps_leave_no_transient_cash_and_finite_claims(factory, mode, timing):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.payment_care_mode = "patient_pay"
    cfg.payment_assistance = "mixed"
    with use_config(cfg):
        economy = factory.economy(num_households=24)
        economy.performance_mode = mode
        economy.warmup_ticks = 3
        for _ in range(16):
            economy.step()
            book = economy.payment_book
            assert book.clearing_cash == pytest.approx(0.0, abs=1e-6)
            assert not book.clearing_payables
            assert not book.late_income
            assert not economy.payment_state["ceo_holds"]
            for household in economy.households:
                assert math.isfinite(household.cash_balance)
                assert household.last_healthcare_units <= 1.0
                if household.employer_id is not None:
                    firm = economy.firm_lookup[household.employer_id]
                    assert household.wage == pytest.approx(firm.actual_wages[household.household_id])
            for amount in economy.payment_state["wage_claims"].values():
                assert math.isfinite(amount) and amount >= 0.0
            restrictions = sum(economy.payment_state["restrictions"].values())
            assert restrictions <= max(0.0, economy.government.cash_balance) + 1e-6


@pytest.mark.parametrize("mode", [False, True])
@pytest.mark.parametrize("timing", ["income_first", "income_late"])
def test_seeded_bank_economy_reconciles_each_household_and_registered_claim(mode, timing):
    """Exercise real entry, bank, deposits, care and taxes beyond the small fixture."""
    from payment_loans import preflight_loans
    from tools.runners.run_large_simulation import create_large_economy

    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.payment_assistance = "mixed"
    cfg.payment_care_mode = "covered"
    cfg.payment_services_project_enabled = True
    cfg.random_seed = 42
    random.seed(42)
    np.random.seed(42)
    with use_config(cfg), contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(100, 2)
        economy.warmup_ticks = 3
        economy.performance_mode = mode
        def total_currency():
            return (sum(h.cash_balance for h in economy.households)
                    + sum(f.cash_balance for f in economy.firms)
                    + sum(f.cash_balance for f in economy.queued_firms)
                    + economy.government.cash_balance + economy.bank.cash_reserves
                    + economy.misc_firm_revenue
                    + sum(economy.payment_state["recovery_holds"].values()))

        opening_currency = total_currency()
        for _ in range(60):
            economy.step()
            assert total_currency() == pytest.approx(opening_currency, abs=1e-5)
            for household in economy.households:
                ledger = household.last_tick_ledger
                assert ledger["net"] == pytest.approx(
                    sum(amount for category, amount in ledger.items() if category != "net"), abs=1e-5
                ), (economy.current_tick, household.household_id, ledger)
                assert math.isfinite(household.cash_balance)
            book = economy.payment_book
            assert not book.clearing_payables
            assert book.clearing_cash == pytest.approx(0.0, abs=1e-5)
            assert sum(book.medical_funding_pending.values()) == pytest.approx(0.0)
            assert sum(economy.payment_state["restrictions"].values()) <= max(0.0, economy.government.cash_balance) + 1e-5
            preflight_loans(economy)


def test_provider_exit_retains_episode_and_ownerless_cash(factory):
    from payments import PaymentBook
    from payment_sectors import requeue_payment_care_due

    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        patient = factory.household(household_id=1, cash_balance=0.0,
                                    queued_healthcare_firm_id=1, pending_healthcare_visits=1)
        patient.payment_care_due_tick = 0
        patient.payment_care_episode_id = 7
        patient.payment_care_accepted_quote = 10.0
        failed = factory.firm(firm_id=1, category="Healthcare", cash_balance=50.0,
                              zero_cash_streak=100, employees=[], owners=[], is_baseline=False)
        survivor = factory.firm(firm_id=2, category="Healthcare", price=10.0, cash_balance=100.0,
                                employees=[], owners=[], is_baseline=False)
        government = factory.government(cash_balance=0.0)
        economy = factory.economy(households=[patient], firms=[failed, survivor], government=government)
        economy.current_tick = 2
        economy.payment_book = PaymentBook(economy)
        assert economy._handle_firm_exits() == 1
        assert patient.queued_healthcare_firm_id is None
        assert patient.payment_care_due_tick == 0
        assert government.cash_balance + economy.misc_firm_revenue == pytest.approx(50.0)
        requeue_payment_care_due(economy)
        assert patient.queued_healthcare_firm_id == survivor.firm_id
        assert patient.payment_care_episode_id == 7
        assert survivor.healthcare_requests_last_tick == 0.0
