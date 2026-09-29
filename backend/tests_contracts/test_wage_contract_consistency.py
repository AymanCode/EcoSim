"""Wage contracts and this tick's ordinary earnings stay distinct at settlement."""

import pytest

from tests_contracts.factories import patch_agent_method


@pytest.mark.parametrize("performance_mode", [False, True])
def test_step_uses_employer_floor_for_payroll_tax_and_receipt_then_keeps_late_cut(
    factory, monkeypatch, performance_mode
):
    household = factory.household(household_id=1, employer_id=1, wage=70.0, cash_balance=10_000.0)
    firm = factory.firm(
        firm_id=1, category="Food", is_baseline=True, wage_offer=100.0,
        employees=[1], actual_wages={1: 70.0}, cash_balance=40_000.0,
    )
    government = factory.government(transfer_budget=0.0)
    economy = factory.economy(households=[household], firms=[firm], government=government)
    economy.performance_mode = performance_mode
    economy.current_tick = 1  # Avoid the separate 50-tick continuing-worker raise.
    economy.warmup_ticks = 0
    economy.in_warmup = False

    # The outcome carries the household's old wage. FirmAgent's real labor apply
    # enforces its incumbent offer floor; Economy must pass that rate to the HH.
    def keep_job(*_args):
        return (
            {1: {"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}}},
            {1: {"employer_id": 1, "wage": 70.0, "employer_category": "Food"}},
        )

    monkeypatch.setattr(economy, "_run_labor_matching", keep_job)
    # A low separately planned future offer allows the phase-9 cut to persist
    # at the next phase-4 boundary rather than intentionally re-flooring it.
    patch_agent_method(monkeypatch, firm, "plan_wage", lambda *args, **kwargs: {"wage_offer_next": 20.0})

    payroll = []
    original_production = firm.apply_production_and_costs

    def record_production(result):
        wage_bill = firm._current_wage_bill()
        cash_before = firm.cash_balance
        original_production(result)
        payroll.append((wage_bill, cash_before - firm.cash_balance))

    patch_agent_method(monkeypatch, firm, "apply_production_and_costs", record_production)

    tax_records = []
    original_taxes = government.plan_taxes

    def record_taxes(households, firms):
        plan = original_taxes(households, firms)
        tax_records.append((households[0]["wage_income"], plan["wage_taxes"][1]))
        return plan

    patch_agent_method(monkeypatch, government, "plan_taxes", record_taxes)

    original_sales = firm.apply_sales_and_profit
    sales_calls = 0

    def cut_after_first_payday(result):
        nonlocal sales_calls
        original_sales(result)
        if sales_calls == 0:
            # Execute the existing phase-9 wage-cut writer with a weak receipt.
            firm.adjust_wages_to_revenue_ratio(1.0)
        sales_calls += 1

    patch_agent_method(monkeypatch, firm, "apply_sales_and_profit", cut_after_first_payday)

    economy.step()
    first_contract = firm.actual_wages[1]
    assert payroll[0] == pytest.approx((100.0, 100.0))
    assert tax_records[0][0] == pytest.approx(100.0)
    assert household.last_wage_income == pytest.approx(100.0)
    assert household.last_tick_ledger["wage"] == pytest.approx(100.0)
    assert household.last_tick_ledger["taxes"] == pytest.approx(-tax_records[0][1])
    assert 0 < first_contract < 100.0
    assert household.wage == pytest.approx(first_contract)

    economy.step()
    assert payroll[1] == pytest.approx((first_contract, first_contract))
    assert tax_records[1][0] == pytest.approx(first_contract)
    assert household.last_wage_income == pytest.approx(first_contract)
    assert household.last_tick_ledger["wage"] == pytest.approx(first_contract)
    assert household.last_tick_ledger["taxes"] == pytest.approx(-tax_records[1][1])
    assert household.wage == pytest.approx(firm.actual_wages[1])


@pytest.mark.parametrize("performance_mode", [False, True])
@pytest.mark.parametrize("match_mode", ["fast", "legacy"])
def test_real_matching_keeps_contract_mirrors_across_two_ticks(
    factory, performance_mode, match_mode
):
    households = factory.households(12)
    firm = factory.firm(firm_id=1, category="Food", is_baseline=True)
    economy = factory.economy(households=households, firms=[firm])
    economy.performance_mode = performance_mode
    economy.labor_match_mode = match_mode
    economy.warmup_ticks = 100

    for _ in range(2):
        economy.step()
        for household in households:
            if household.employer_id == firm.firm_id:
                assert household.household_id in firm.employees
                assert household.wage == pytest.approx(firm.actual_wages[household.household_id])
            else:
                assert household.wage == 0.0


def test_sync_fallback_layoff_and_switch_use_only_actual_employer(factory):
    worker = factory.household(household_id=1, employer_id=2, wage=0.0)
    old_firm = factory.firm(firm_id=1, employees=[1], actual_wages={1: 500.0})
    new_firm = factory.firm(firm_id=2, employees=[], actual_wages={1: 85.0})
    economy = factory.economy(households=[worker], firms=[old_firm, new_firm])

    economy._sync_firm_employee_rosters()
    assert worker.wage == pytest.approx(85.0)
    assert old_firm.employees == [] and old_firm.actual_wages == {}
    assert new_firm.actual_wages[1] == pytest.approx(worker.wage)

    worker.wage = 0.0
    new_firm.actual_wages.clear()
    economy._sync_firm_employee_rosters()
    assert worker.wage == pytest.approx(new_firm.wage_offer)
    assert new_firm.actual_wages[1] == pytest.approx(worker.wage)

    worker.employer_id = None
    economy._sync_firm_employee_rosters()
    assert worker.wage == 0.0
    assert new_firm.employees == [] and new_firm.actual_wages == {}


def test_seeded_raise_skips_stale_former_employer_and_preserves_timestamp(factory):
    worker = factory.household(
        household_id=1, employer_id=2, wage=90.0, last_wage_update_tick=0
    )
    old_firm = factory.firm(firm_id=1, employees=[1], actual_wages={1: 500.0})
    new_firm = factory.firm(firm_id=2, employees=[1], actual_wages={1: 90.0})
    economy = factory.economy(households=[worker], firms=[old_firm, new_firm])
    economy.current_tick = 50

    new_firm.employees = []
    economy._update_continuing_employee_wages()
    assert worker.last_wage_update_tick == 0
    assert old_firm.actual_wages[1] == 500.0
    new_firm.employees = [1]
    economy._update_continuing_employee_wages()
    assert old_firm.actual_wages[1] == 500.0
    assert 90.0 * 1.02 <= worker.wage <= 90.0 * 1.03
    assert new_firm.actual_wages[1] == pytest.approx(worker.wage)
    assert worker.last_wage_update_tick == 50
    economy._sync_firm_employee_rosters()
    assert new_firm.actual_wages[1] == pytest.approx(worker.wage)


def test_warmup_living_cost_floor_updates_actual_employer(factory):
    worker = factory.household(household_id=1, employer_id=1, wage=20.0)
    worker.price_beliefs["housing"] = 300.0
    worker.price_beliefs["food"] = 20.0
    firm = factory.firm(firm_id=1, employees=[1], actual_wages={1: 20.0})
    economy = factory.economy(households=[worker], firms=[firm])

    economy._reset_post_warmup_expectations()
    assert worker.wage > 20.0
    assert firm.actual_wages[1] == pytest.approx(worker.wage)


@pytest.mark.parametrize("reset_path", ["profit", "price"])
def test_healthcare_resets_keep_this_payday_and_mirror_future_contract(
    factory, monkeypatch, reset_path
):
    doctor = factory.household(
        household_id=1, employer_id=1, wage=80.0,
        medical_training_status="doctor", cash_balance=10_000.0,
    )
    firm = factory.firm(
        firm_id=1, category="Healthcare", is_baseline=True,
        wage_offer=80.0, employees=[1], actual_wages={1: 80.0},
    )
    economy = factory.economy(households=[doctor], firms=[firm])
    economy.current_tick = 1
    economy.warmup_ticks = 0
    economy.in_warmup = False
    # Healthcare base wages reset to the binding policy minimum (audit B19),
    # which is above the config floor at the default policy.
    minimum = max(firm._firm_config().minimum_wage_floor, economy.government.get_minimum_wage())
    assert 80.0 > minimum

    monkeypatch.setattr(
        economy, "_run_labor_matching",
        lambda *_args: (
            {1: {"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}}},
            {1: {"employer_id": 1, "wage": 80.0, "employer_category": "Healthcare"}},
        ),
    )
    if reset_path == "profit":
        original_sales = firm.apply_sales_and_profit

        def profit_reset(result):
            original_sales({**result, "revenue": max(1.0, result["revenue"])})
            assert firm.actual_wages[1] == pytest.approx(minimum)

        patch_agent_method(monkeypatch, firm, "apply_sales_and_profit", profit_reset)
        patch_agent_method(monkeypatch, firm, "apply_price_and_wage_updates", lambda *_args: None)

    economy.step()
    assert doctor.last_wage_income == pytest.approx(80.0)
    assert doctor.wage == pytest.approx(minimum)
    assert firm.actual_wages[1] == pytest.approx(minimum)


def test_direct_tax_and_receipt_calls_preserve_contract_wage_fallback(factory):
    worker = factory.household(household_id=1, employer_id=1, wage=72.0)
    firm = factory.firm(firm_id=1, employees=[1], actual_wages={1: 72.0})
    economy = factory.economy(households=[worker], firms=[firm])

    assert economy._build_household_tax_snapshots() == [
        {"household_id": 1, "wage_income": 72.0}
    ]
    economy._batch_apply_household_updates({}, {1: 0.0}, {}, {})
    assert worker.last_wage_income == pytest.approx(72.0)
