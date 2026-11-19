"""The money lines follow each household's essentials and retain their fallbacks."""
import copy
from types import SimpleNamespace

import pytest

from agents import BankAgent
from config import clone_config, use_config
from economy import _TickScratch
from household_costs import essential_weekly_costs, food_reference_price, rent_reference_price
from tests_contracts.factories import patch_agent_method


def test_essentials_median_contract_rent_and_snapshot_refresh(factory):
    cfg = clone_config()
    cfg.households.money_lines_in_weeks = True
    with use_config(cfg):
        tenant = factory.household(household_id=1, min_food_per_tick=2, renting_from_firm_id=9, monthly_rent=20)
        other = factory.household(household_id=2, min_food_per_tick=3, renting_from_firm_id=None)
        firms = [factory.firm(firm_id=1, category="Food", price=5),
                 factory.firm(firm_id=2, category="Food", price=15),
                 factory.firm(firm_id=3, category="Housing", price=30),
                 factory.firm(firm_id=4, category="Housing", price=10)]
        ec = factory.economy(households=[tenant, other], firms=firms)
        ec.configure_stabilizers(households=False, firms=False, government=False)
        assert food_reference_price(ec) == 10
        assert rent_reference_price(ec) == 20
        assert essential_weekly_costs(ec) == pytest.approx([40, 50])
        ec._phase_pre_plan_state(_TickScratch(payment_arm=False))
        assert [tenant.essential_weekly_cost, other.essential_weekly_cost] == pytest.approx([40, 50])
        firms[0].price = float("nan")
        firms[1].price = 0
        firms[2].price = firms[3].price = 0
        other.min_food_per_tick = 0
        assert essential_weekly_costs(ec) == pytest.approx([20, 1e-6])


@pytest.mark.parametrize("cost,fee,trigger", [(40.0, 132.0, 400.0), (1e-6, 100.0, 300.0)])
def test_education_trigger_and_fee(factory, cost, fee, trigger):
    cfg = clone_config()
    cfg.households.money_lines_in_weeks = True
    with use_config(cfg):
        hh = factory.household(skills_level=0.3, employer_id=None, essential_weekly_cost=cost, cash_balance=trigger)
        assert hh.maybe_active_education() == 0
        hh.cash_balance += 1
        assert hh.maybe_active_education() == pytest.approx(fee)
        assert hh.cash_balance == pytest.approx(trigger + 1 - fee)
        assert hh.skills_level == pytest.approx(0.305)


@pytest.mark.parametrize("cost,threshold,amount", [(40.0, 40.0, 80.0), (1e-6, 50.0, 200.0)])
def test_consumption_loan_trigger_amount_and_leverage(factory, cost, threshold, amount):
    cfg = clone_config()
    cfg.households.money_lines_in_weeks = True
    with use_config(cfg):
        bank = BankAgent(cash_reserves=10000)
        hh = factory.household(employer_id=None, expected_wage=0, cash_balance=threshold,
                               essential_weekly_cost=cost)
        hh.maybe_request_consumption_loan(bank)
        assert not hh.needs_consumption_loan
        hh.cash_balance -= 1
        hh.consumption_loan_remaining = 4 * threshold - amount
        hh.maybe_request_consumption_loan(bank)
        assert hh.needs_consumption_loan and hh.consumption_loan_amount == pytest.approx(amount)
        hh.consumption_loan_remaining += 0.01
        hh.maybe_request_consumption_loan(bank)
        assert not hh.needs_consumption_loan


def test_payment_origination_receives_the_household_requested_amount(factory, monkeypatch):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.money_lines_in_weeks = True
    with use_config(cfg):
        bank = BankAgent(cash_reserves=10000)
        hh = factory.household(employer_id=1, wage=100, cash_balance=39, essential_weekly_cost=40)
        ec = factory.economy(households=[hh], firms=[factory.firm()])
        ec.bank = bank
        hh.maybe_request_consumption_loan(bank)
        calls = []

        def originate(*args, **kwargs):
            calls.append(args)
            return {}

        monkeypatch.setattr("payment_loans.originate_v2", originate)
        ec._offer_consumption_loans()
        assert calls[0][3] == pytest.approx(80)
        assert hh.cash_balance == pytest.approx(119)


@pytest.mark.parametrize("cost,cash_div,wage_div,floor", [(40.0, 532.0, 53.2, 33.2), (1e-6, 400.0, 40.0, 25.0)])
def test_affordability_dividers_and_price_cap_floor(factory, cost, cash_div, wage_div, floor):
    cfg = clone_config()
    cfg.households.money_lines_in_weeks = True
    with use_config(cfg):
        hh = factory.household(skills_level=0, cash_balance=100, wage=20,
                               essential_weekly_cost=cost, quality_lavishness=1)
        assert hh._get_affordability_score() == pytest.approx(0.35 * (100 / cash_div + 20 / wage_div))
        hh.cash_balance = hh.wage = hh.expected_wage = 0
        assert hh._get_category_price_cap("food", precomputed_prices=(10, 100, 100)) == pytest.approx(floor)


@pytest.mark.parametrize("cost,living", [(40.0, 40.0), (1e-6, 23.0)])
def test_labor_living_cost(factory, cost, living):
    cfg = clone_config()
    cfg.households.money_lines_in_weeks = True
    with use_config(cfg):
        hh = factory.household(cash_balance=30, essential_weekly_cost=cost, min_food_per_tick=2,
                               renting_from_firm_id=1, health=1, reservation_wage=100,
                               unemployment_duration=0, default_price_level=10, price_beliefs={})
        plan = hh.plan_labor_supply()
        desperation = (1 - 30 / (2 * living)) / 2
        expected = 100 * (1 - (1 - cfg.households.desperation_wage_discount) * desperation)
        assert plan["reservation_wage"] == pytest.approx(expected)


@pytest.mark.parametrize("cost,line,floor", [(40.0, 520.0, 13.2), (1e-6, 200.0, 10.0)])
def test_cash_pressure_and_wage_floor(factory, cost, line, floor):
    cfg = clone_config()
    cfg.households.money_lines_in_weeks = True
    with use_config(cfg):
        hh = factory.household(cash_balance=100, essential_weekly_cost=cost, employer_id=None,
                               expected_wage=100, health=1, unemployment_duration=0)
        hh._apply_labor_history(None)
        pressure = min(cfg.households.happiness_pressure_cap,
                       (line - 100) / max(line, 1) * cfg.households.happiness_pressure_cap)
        factor = max(cfg.households.min_decay_factor,
                     cfg.households.base_wage_decay - cfg.households.duration_pressure_rate - pressure)
        assert hh.expected_wage == pytest.approx(max(100 * factor, floor))
        hh.expected_wage = 0.1
        hh.cash_balance = 1000
        hh._apply_labor_history(None)
        assert hh.expected_wage == pytest.approx(floor)


@pytest.mark.parametrize("cash,delta", [(70, 0.0), (90, 0.02), (250, -0.03)])
def test_wellbeing_only_changes_poverty_comparisons(factory, cash, delta):
    cfg = clone_config()
    # wellbeing_targets: poverty penalties are part of the original wellbeing path.
    cfg.households.wellbeing_targets = False
    with use_config(cfg):
        original = factory.household(cash_balance=cash, essential_weekly_cost=40, happiness=0.8)
        firm = factory.firm()
        results = []
        for enabled in (False, True):
            cfg.households.money_lines_in_weeks = enabled
            hh = copy.deepcopy(original)
            ec = factory.economy(households=[hh], firms=[copy.deepcopy(firm)])
            ec._batch_update_wellbeing(1.0)
            results.append(hh.happiness)
        assert results[1] - results[0] == pytest.approx(delta)
        cfg.households.money_lines_in_weeks = True
        fallback = copy.deepcopy(original)
        fallback.essential_weekly_cost = 1e-6
        ec = factory.economy(households=[fallback], firms=[copy.deepcopy(firm)])
        ec._batch_update_wellbeing(1.0)
        assert fallback.happiness == pytest.approx(results[0])


@pytest.mark.parametrize("cost,expected", [(40.0, 45.865), (1e-6, 49.865)])
def test_desperation_budget_threshold(factory, cost, expected):
    cfg = clone_config()
    cfg.households.money_lines_in_weeks = True
    cfg.households.healthcare_food_first_reserve = False
    cfg.households.mpc_wage = 1.0
    with use_config(cfg):
        hh = factory.household(employer_id=1, wage=45, cash_balance=100, essential_weekly_cost=cost,
                               spending_tendency=1, frugality=1, savings_drawdown_rate=0.01)
        ec = factory.economy(households=[hh], firms=[factory.firm()])
        assert ec._household_consumption_budgets(0, 0)[0] == pytest.approx(expected)


@pytest.mark.parametrize("cost,deposited", [(40.0, 30.0), (1e-6, 25.0)])
def test_deposit_sweep_spending_floor(factory, monkeypatch, cost, deposited):
    cfg = clone_config()
    cfg.households.money_lines_in_weeks = True
    with use_config(cfg):
        hh = factory.household(cash_balance=100, essential_weekly_cost=cost, last_consumption_spending=0,
                               deposit_buffer_weeks=1, deposit_fraction=0.5, bank_deposit=0)
        ec = factory.economy(households=[hh], firms=[factory.firm()])
        ec.bank = BankAgent(cash_reserves=1000, deposit_rate=0.01)
        patch_agent_method(monkeypatch, ec.government, "get_minimum_wage", lambda: 0)
        ec._process_bank_deposits()
        assert hh.bank_deposit == pytest.approx(deposited)
