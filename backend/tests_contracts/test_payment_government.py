"""The optional public Services contract requires cash and a paid worker-week."""

from types import SimpleNamespace

import pytest

from config import clone_config, use_config
from payment_government import (activate_payment_services_slots,
                                assign_payment_services_project_worker,
                                complete_payment_services_project,
                                reserve_payment_services_project,
                                settle_payment_services_exit)


def _setup(cash=1000.0):
    worker = SimpleNamespace(household_id=1, employer_id=3)
    firm = SimpleNamespace(firm_id=3, good_category="Services", employees=[1],
                           actual_wages={1: 50.0}, cash_balance=50.0,
                           production_capacity_units=1.0)
    government = SimpleNamespace(cash_balance=cash)
    economy = SimpleNamespace(current_tick=4, households=[worker], firms=[firm],
                              household_lookup={1: worker}, firm_lookup={3: firm},
                              government=government, last_tick_unmet_demand_by_firm={3: 2.0},
                              payment_state={"restrictions": {"B": 0.0, "care": 0.0, "rent": 0.0, "G": 0.0,
                                                              "withholding": 0.0, "project": 0.0}})
    economy._payment_free_treasury_cash = lambda: max(0.0, government.cash_balance - sum(economy.payment_state["restrictions"].values()))
    economy._payment_sync_restrictions = lambda: None
    economy._payment_spend_restriction = lambda name, amount: _spend(economy, name, amount)
    economy.payment_book = SimpleNamespace(current_paid_by_firm_worker={}, current_due={3: {1: 50.0}})
    return economy, firm


def _spend(economy, name, amount):
    if economy.payment_state["restrictions"][name] < amount:
        raise ValueError("not funded")
    economy.payment_state["restrictions"][name] -= amount
    economy.government.cash_balance -= amount
    return amount


def _config():
    cfg = clone_config()
    cfg.payment_services_project_enabled = True
    cfg.payment_services_project_cost = 1000.0
    cfg.payment_services_project_lag_ticks = 1
    return cfg


def test_no_free_cash_or_hire_produces_no_project_or_slot():
    economy, firm = _setup(cash=500.0)
    with use_config(_config()):
        assert reserve_payment_services_project(economy) is None
    assert economy.payment_state["restrictions"]["project"] == 0.0
    assert firm.production_capacity_units == 1.0

    economy.government.cash_balance = 1000.0
    with use_config(_config()):
        assert reserve_payment_services_project(economy) is not None
        economy.current_tick = 5
        assert assign_payment_services_project_worker(economy, {}, {3: 0}) == {}
        assert not complete_payment_services_project(economy)
    assert firm.production_capacity_units == 1.0
    assert firm.cash_balance == 50.0


def test_existing_ordinary_hire_cannot_be_claimed_as_incremental_project_labor():
    economy, firm = _setup()
    with use_config(_config()):
        reserve_payment_services_project(economy)
        economy.current_tick = 5
        assert assign_payment_services_project_worker(economy, {3: [1]}, {3: 1}) == {}
        assert economy.payment_state["services_project"]["worker_id"] is None


def test_paid_incremental_worker_buys_one_next_tick_slot_and_pending_tax_receipt():
    economy, firm = _setup()
    with use_config(_config()):
        project = reserve_payment_services_project(economy)
        assert project["firm_id"] == 3
        assert economy.government.cash_balance == 1000.0  # reservation is internal
        economy.current_tick = 5
        assert assign_payment_services_project_worker(economy, {3: [1]}, {3: 0}) == {3: 1}
        economy.payment_book.current_paid_by_firm_worker[(3, 1)] = 50.0
        assert complete_payment_services_project(economy)
        assert not complete_payment_services_project(economy)
        assert firm.cash_balance == pytest.approx(1050.0)
        assert economy.government.cash_balance == pytest.approx(0.0)
        assert economy.payment_state["services_pending_receipts"][3] == pytest.approx(1000.0)
        assert firm.production_capacity_units == 1.0
        economy.current_tick = 6
        assert activate_payment_services_slots(economy) == 1
        assert activate_payment_services_slots(economy) == 0
        assert firm.production_capacity_units == 2.0


def test_unpaid_worker_denies_installment_and_provider_exit_taxes_earned_receipt_once():
    economy, firm = _setup()
    with use_config(_config()):
        reserve_payment_services_project(economy)
        economy.current_tick = 5
        assign_payment_services_project_worker(economy, {3: [1]}, {3: 0})
        economy.payment_book.current_paid_by_firm_worker[(3, 1)] = 25.0
        assert not complete_payment_services_project(economy)
        assert firm.cash_balance == 50.0
        assert economy.payment_state["services_project"]["status"] == "cancelled_unpaid_worker"
    economy.payment_state["services_pending_receipts"] = {3: 40.0}
    calls = []
    economy._payment_collect_pending_services_exit_tax = lambda provider, amount: calls.append((provider.firm_id, amount)) or 8.0
    assert settle_payment_services_exit(economy, firm) == 8.0
    assert settle_payment_services_exit(economy, firm) == 0.0
    assert calls == [(3, 40.0)]
    assert economy.payment_state["services_exit_tax_convention"] == "single_snapshot"


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
@pytest.mark.parametrize("performance_mode", [False, True])
def test_optional_project_runs_through_real_tick_without_unfunded_slot(tiny_economy_factory, timing, performance_mode):
    cfg = _config()
    cfg.payment_sequence = timing
    with use_config(cfg):
        economy = tiny_economy_factory(num_households=12, include_healthcare=False)
        economy.performance_mode = performance_mode
        for _ in range(4):
            economy.step()
            for event in economy.payment_state.get("services_project_events", []):
                if event["type"] == "completed":
                    assert event["paid_installments"] == pytest.approx(cfg.payment_services_project_cost)
                    assert event["completed_slots"] == 1
            assert sum(economy.payment_state["restrictions"].values()) <= max(0.0, economy.government.cash_balance) + 1e-6


def test_real_tick_project_hire_is_paid_and_excluded_from_current_output(factory, monkeypatch):
    cfg = _config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        current = factory.household(household_id=1, employer_id=3, wage=50.0, cash_balance=100.0)
        newcomer = factory.household(household_id=2, employer_id=None, wage=0.0, cash_balance=100.0)
        firm = factory.firm(firm_id=3, category="Services", is_baseline=True,
                            employees=[1], actual_wages={1: 50.0}, wage_offer=50.0,
                            cash_balance=5000.0, production_capacity_units=1.0,
                            price=10.0)
        government = factory.government(cash_balance=5000.0, wage_tax_rate=0.0,
                                        profit_tax_rate=0.0, unemployment_benefit_level=0.0)
        government.register_baseline_firm("Services", 3)
        economy = factory.economy(households=[current, newcomer], firms=[firm], government=government)
        economy.current_tick = 0
        reserve_payment_services_project(economy)
        economy.current_tick = 1
        economy.warmup_ticks = 100
        economy.configure_stabilizers(households=False, firms=False, government=False)
        monkeypatch.setattr(economy, "_run_labor_matching", lambda *_: (
            {3: {"hired_households_ids": [2], "confirmed_layoffs_ids": [], "actual_wages": {2: 50.0}}},
            {1: {"employer_id": 3, "wage": 50.0, "employer_category": "Services"},
             2: {"employer_id": 3, "wage": 50.0, "employer_category": "Services"}},
        ))
        monkeypatch.setattr(economy, "_batch_plan_consumption", lambda *_: {
            1: {"planned_purchases": {}, "budget": 0.0},
            2: {"planned_purchases": {}, "budget": 0.0},
        })
        monkeypatch.setattr(economy, "_maybe_create_new_firms", lambda: 0)
        economy.step()
    assert economy.payment_project_worker_by_firm == {3: 2}
    assert economy.payment_book.current_paid_by_firm_worker[(3, 2)] > 0.0
    assert any(event["type"] == "completed" and event["worker_id"] == 2
               for event in economy.payment_state["services_project_events"])
    assert firm.production_capacity_units == 1.0
    assert firm.last_units_produced <= firm._capacity_for_workers(1) + 1e-6
    assert activate_payment_services_slots(economy) == 1
    assert firm.production_capacity_units == 2.0
    firm.production_capacity_units = 100.0
    economy.payment_project_worker_by_firm = {3: 2}
    project_output = economy._calculate_experience_adjusted_production(firm, 100.0)
    economy.payment_project_worker_by_firm = {}
    ordinary_output = economy._calculate_experience_adjusted_production(firm, 100.0)
    assert project_output < ordinary_output
