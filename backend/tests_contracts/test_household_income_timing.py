"""New funds reach the same week's legacy shopping decision, paid once.

Ported onto the remediation code on 2026-09-29 from the 2026-09-28 session
written against 17d5c0b (docs/reviews/2026-09-28-household-income-timing.md).
``isolated_run`` and ``small_world`` are copies of that session's
``tools/checks/run_agent_scenarios.py`` fixtures, kept here until that runner
is ported.
"""

import contextlib
import random

import numpy as np
import pytest

from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG, clone_config, use_config
from economy import Economy
from tests_contracts.factories import patch_agent_method


@contextlib.contextmanager
def isolated_run(seed):
    """Restore both global RNG streams and the context-local configuration."""
    python_state, numpy_state = random.getstate(), np.random.get_state()
    config = clone_config()
    config.random_seed = seed
    config.payment_sequence = "legacy"
    random.seed(seed)
    np.random.seed(seed)
    try:
        with use_config(config):
            yield
    finally:
        random.setstate(python_state)
        np.random.set_state(numpy_state)


def small_world(seed, *, cash=100.0, deposits=0.0, category="Food", workers=1):
    """Explicit fixtures, not a calibrated town. Each variant starts afresh."""
    random.seed(seed)
    np.random.seed(seed)
    households = [HouseholdAgent(i + 1, skills_level=0.5, age=30, cash_balance=cash)
                  for i in range(workers)]
    firm = FirmAgent(
        firm_id=1, good_name="Shop", good_category=category, cash_balance=10_000.0,
        inventory_units=10.0 if category == "Food" else 0.0, price=10.0,
        wage_offer=40.0, expected_sales_units=40.0, quality_level=5.0,
        production_capacity_units=200.0, productivity_per_worker=12.0,
        personality="moderate", is_baseline=False,
        max_rental_units=1 if category == "Housing" else 0,
    )
    bank = BankAgent(cash_reserves=10_000.0)
    government = GovernmentAgent(cash_balance=20_000.0, unemployment_benefit_level=30.0,
                                 transfer_budget=0.0, wage_tax_rate=0.15, profit_tax_rate=0.20)
    for household in households:
        household.employer_id = firm.firm_id
        household.wage = household.expected_wage = 40.0
        household.health = 0.8
        household.spending_tendency = household.frugality = 1.0
        household.savings_drawdown_rate = 0.02
        household.subsistence_min_cash = 50.0
        household.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
        household.bank_deposit = deposits
        bank.accept_deposit(household.household_id, deposits)
        firm.employees.append(household.household_id)
        firm.actual_wages[household.household_id] = household.wage
    firm.age_in_ticks = 30
    firm.last_revenue = 400.0
    firm.last_profit = 100.0
    firm.last_units_sold = firm.sales_velocity_ema = 40.0
    return Economy(households, [firm], government, bank=bank)


@pytest.mark.parametrize("performance_mode", [False])
@pytest.mark.parametrize("funding", ["wage", "loan", "benefit"])
def test_zero_cash_household_buys_food_in_week_funds_arrive(monkeypatch, performance_mode, funding):
    with isolated_run(1337):
        economy = small_world(1337, cash=0)
        economy.performance_mode = performance_mode
        economy.current_tick = 17  # An intermediate cache tick, beyond warmup/stimulus.
        # Port adaptation: in_warmup was computed at construction (tick 0), so
        # without this the step crosses the warm-up boundary and pays the
        # post-warm-up stimulus before planning, funding every variant.
        economy.in_warmup = False
        household = economy.households[0]
        if funding != "wage":
            household.health = 0.05  # Real eligibility rule prevents a job in this fixture.
            household.employer_id = None
            household.wage = 0.0
            economy.firms[0].employees = []
            economy.firms[0].actual_wages = {}
        if funding != "loan":
            economy.bank = None
        if funding != "benefit":
            economy.government.unemployment_benefit_level = 0
        # Isolate the requested funding source, using the existing investment rule.
        economy.firms[0].cash_balance = 0  # Prevent self-funded capital investment.
        economy.config.firms.capital_cost_per_unit = 1_000_000  # Make new capital unprofitable.
        observations, tax_payments = [], []
        plan = economy._batch_plan_consumption
        fiscal = economy.government.apply_fiscal_results

        def record_plan(*args, **kwargs):
            observations.append((household.cash_balance, household.last_wage_income, household.last_transfer_income))
            return plan(*args, **kwargs)

        def record_fiscal(wage_tax, profit_tax, transfers, property_tax=0):
            tax_payments.append((wage_tax, transfers))
            return fiscal(wage_tax, profit_tax, transfers, property_tax)

        monkeypatch.setattr(economy, "_batch_plan_consumption", record_plan)
        patch_agent_method(monkeypatch, economy.government, "apply_fiscal_results", record_fiscal)
        economy.step()

        assert len(observations) == 1
        assert observations[0][0] > 0
        assert household.last_consumption_spending > 0
        assert household.food_consumed_this_tick > 0
        assert household.last_tick_ledger["wage"] == pytest.approx(household.last_wage_income)
        assert sum(x[0] for x in tax_payments) == pytest.approx(-household.last_tick_ledger["taxes"])
        assert sum(x[1] for x in tax_payments) == pytest.approx(household.last_transfer_income)
        assert all(firm.capital_investment_this_tick == 0 for firm in economy.firms)
        if funding != "wage":
            assert household.last_wage_income == 0
        if funding != "benefit":
            assert household.last_transfer_income == 0
        if funding != "loan":
            assert household.consumption_loan_remaining == 0
        if funding == "wage":
            assert household.last_wage_income > 0
        elif funding == "benefit":
            assert household.last_transfer_income == 30
        else:
            assert household.consumption_loan_remaining > 0


def test_income_settlement_and_receipts_do_not_pay_wages_twice():
    with isolated_run(1337):
        economy = small_world(1337, cash=0)
        household, firm = economy.households[0], economy.firms[0]
        before_total = household.cash_balance + firm.cash_balance + economy.government.cash_balance
        firm.apply_production_and_costs({"realized_production_units": 0})
        economy._apply_household_income({1: 10}, {1: 4}, {1: 40})
        economy.government.apply_fiscal_results(4, 0, 10)
        assert household.cash_balance == 46
        economy._batch_apply_household_updates({1: 10}, {1: 4}, {}, frozen_wages={1: 40}, income_already_settled=True)
        assert household.cash_balance == 46
        assert household.last_tick_ledger["wage"] == 40
        assert household.cash_balance + firm.cash_balance + economy.government.cash_balance == pytest.approx(before_total)


def test_settled_budget_uses_paid_wage_instead_of_future_contract():
    with isolated_run(1337):
        economy = small_world(1337, cash=100)
        household = economy.households[0]
        household.last_wage_income = 40
        household.last_other_income = -4
        before = economy._household_consumption_budgets(0, 0, settled_income=True)
        household.wage = 400
        after = economy._household_consumption_budgets(0, 0, settled_income=True)
        assert after == pytest.approx(before)
