"""Shopping budgets distinguish received income, savings and held payments."""

import copy

import pytest

from agents import BankAgent
from config import clone_config, use_config
from payment_behavior import planning_inputs
from payment_loans import prepare_household_dues
from payments import PaymentBook
from tests_contracts.factories import patch_agent_method


def _world(factory, *, timing="income_first", opening_cash=0.0, funded=80.0,
           deposit=0.0, employed=True, benefit=0.0, treasury=0.0):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.households.healthcare_food_first_reserve = False
    cfg.households.mpc_wage = 0.8
    cfg.households.mpc_benefit = 0.7
    with use_config(cfg):
        hh = factory.household(
            household_id=1, employer_id=1 if employed else None,
            wage=100.0 if employed else 0.0, cash_balance=opening_cash,
            bank_deposit=deposit, category_weights={"food": 1.0},
            spending_tendency=1.0, frugality=1.0, savings_drawdown_rate=0.05,
            goods_inventory={}, renting_from_firm_id=None,
        )
        firm = factory.firm(firm_id=1, category="Food", is_baseline=True,
                            employees=[1] if employed else [],
                            actual_wages={1: 100.0} if employed else {},
                            cash_balance=funded, wage_offer=100.0, price=10.0,
                            inventory_units=100.0, owners=[], ceo_household_id=None)
        government = factory.government(cash_balance=treasury, wage_tax_rate=0.0,
                                        profit_tax_rate=0.0, unemployment_benefit_level=benefit,
                                        transfer_budget=0.0)
        ec = factory.economy(households=[hh], firms=[firm], government=government)
        # Economy initializes the benefit policy; fix the announced test value
        # afterward so 100 is actually the policy being compared with funding.
        ec.government.unemployment_benefit_level = benefit
        if deposit:
            ec.bank = BankAgent(cash_reserves=10_000.0, total_deposits=deposit)
        ec.current_tick = 5
        ec.payment_book = PaymentBook(ec, timing=timing)
        prepare_household_dues(ec)
        return cfg, ec, hh, firm


def _settle(ec, *, benefit_funds=0.0):
    ec.payment_state["restrictions"]["B"] = benefit_funds
    ec.payment_book.settle_income({h.household_id: h.wage if h.is_employed else 0.0
                                   for h in ec.households})
    ec.payment_book.settle_benefits()


def _budget(ec):
    return ec._household_consumption_budgets(
        0.0, ec.government.get_unemployment_benefit_level(), settled_income=True,
    )[0]


@pytest.mark.parametrize("funded", (0.0, 20.0, 80.0, 100.0))
def test_settled_budget_uses_received_pay_instead_of_the_contract(factory, funded):
    cfg, ec, hh, _ = _world(factory, funded=funded)
    with use_config(cfg):
        assert planning_inputs(ec)[0] == [100.0]
        _settle(ec)
        wage_inputs, liquidity, pressure = planning_inputs(ec, settled_income=True)
        budget = _budget(ec)
    assert hh.wage == 100.0  # A baseline provider can still miss its base pay.
    assert wage_inputs == pytest.approx([funded])
    assert liquidity == pytest.approx([funded])
    assert pressure[1]["estimated_savings_liquidity"] == 0.0
    assert budget <= funded + 1e-8
    assert (budget > 0) == (funded > 0)
    assert ec.payment_state["wage_claims"].get((1, 1), 0.0) == pytest.approx(100.0 - funded)


def test_received_income_is_not_added_to_cash_or_drawn_down_twice(factory):
    cfg, ec, hh, _ = _world(factory, opening_cash=1000.0, funded=100.0)
    with use_config(cfg):
        _settle(ec)
        wage_inputs, liquidity, pressure = planning_inputs(ec, settled_income=True)
        budget = _budget(ec)
    assert hh.cash_balance == 1100.0
    assert wage_inputs == [100.0]
    assert liquidity == [1100.0]
    assert pressure[1]["estimated_savings_liquidity"] == 1000.0
    wage_mpc = max(0.70, cfg.households.mpc_wage * (1.0 - 0.3 * 0.05))
    assert budget == pytest.approx(100.0 * wage_mpc + 1000.0 * 0.05)


def test_signed_cash_deposits_and_known_bills_remain_separate(factory):
    cfg, ec, hh, _ = _world(factory, opening_cash=-40.0, funded=80.0, deposit=100.0)
    hh.renting_from_firm_id, hh.monthly_rent = 99, 30.0
    ec.payment_book.loan_state["household_due_totals"] = {1: 20.0}
    with use_config(cfg):
        _settle(ec)
        _, liquidity, pressure = planning_inputs(ec, settled_income=True)
        budget = _budget(ec)
    assert hh.cash_balance == 40.0
    assert liquidity == pytest.approx([80.0])  # 40 cash + 90 deposits - 50 bills.
    assert pressure[1]["estimated_savings_liquidity"] == 0.0
    assert pressure[1]["rent_due"] == 30.0 and pressure[1]["loan_due"] == 20.0
    assert 0.0 < budget <= 80.0
    assert hh.bank_deposit == ec.bank.total_deposits == 100.0  # Planning does not withdraw.


@pytest.mark.parametrize("funded", (0.0, 20.0, 100.0))
def test_announced_benefit_cannot_replace_the_actual_funded_transfer(factory, funded):
    cfg, ec, hh, _ = _world(factory, employed=False, funded=0.0,
                             benefit=100.0, treasury=funded)
    with use_config(cfg):
        _settle(ec, benefit_funds=funded)
        _, liquidity, pressure = planning_inputs(ec, settled_income=True)
        budget = _budget(ec)
    assert hh.cash_balance == funded
    assert liquidity == [funded]
    assert pressure[1]["estimated_savings_liquidity"] == 0.0
    assert budget == pytest.approx(funded * cfg.households.mpc_benefit)
    assert ec.payment_book.paid_income[1]["benefit"] == funded
    assert ec.government.cash_balance == 0.0


def test_paid_old_wages_are_received_income_not_an_unfunded_claim(factory):
    cfg, ec, hh, _ = _world(factory, funded=150.0)
    ec.payment_state["wage_claims"][(1, 1)] = 50.0
    with use_config(cfg):
        _settle(ec)
        wages, liquidity, pressure = planning_inputs(ec, settled_income=True)
        budget = _budget(ec)
    assert hh.cash_balance == 150.0
    assert wages == [150.0] and liquidity == [150.0]
    assert pressure[1]["estimated_savings_liquidity"] == 0.0
    assert not ec.payment_state["wage_claims"]
    assert 100.0 < budget < 150.0


def test_held_ceo_pay_cannot_enter_the_current_shopping_budget(factory):
    cfg, ec, hh, firm = _world(factory, funded=400.0)
    firm.ceo_household_id = hh.household_id
    with use_config(cfg):
        _settle(ec)
        wages, liquidity, _ = planning_inputs(ec, settled_income=True)
        budget = _budget(ec)
    assert hh.cash_balance == 100.0
    assert ec.payment_state["ceo_holds"][1] == 300.0
    assert wages == [100.0] and liquidity == [100.0]
    assert 0.0 < budget <= 100.0


def test_received_input_requires_both_income_and_benefit_settlement(factory):
    cfg, ec, _, _ = _world(factory)
    with use_config(cfg):
        with pytest.raises(ValueError):
            planning_inputs(ec, settled_income=True)
        ec.payment_book.settle_income({1: 100.0})
        with pytest.raises(ValueError):
            planning_inputs(ec, settled_income=True)
        ec.payment_book.settle_benefits()
        assert planning_inputs(ec, settled_income=True)[0] == [80.0]


def test_previous_ticks_paid_income_cannot_be_reused_as_a_new_receipt(factory):
    cfg, ec, _, _ = _world(factory)
    with use_config(cfg):
        _settle(ec)
        ec.current_tick += 1
        ec.payment_book.loan_state["household_due_tick"] = ec.current_tick
        with pytest.raises(ValueError):
            planning_inputs(ec, settled_income=True)


def test_later_pay_still_cannot_fund_current_purchases(factory):
    cfg, ec, hh, _ = _world(factory, timing="income_late", funded=80.0)
    with use_config(cfg):
        _settle(ec)
        _, liquidity, _ = planning_inputs(ec)
        budget = ec._household_consumption_budgets(0.0, 0.0)[0]
        assert liquidity == [0.0] and budget == 0.0
        assert hh.cash_balance == 0.0
        ec.payment_book.release_late_income()
    assert hh.cash_balance == 80.0


def _live_budget_world(factory, monkeypatch, *, performance=False):
    cfg, ec, hh, firm = _world(factory, funded=80.0)
    cfg.firms.quality_research_model = "scale_only"
    cfg.firms.working_capital_enabled = False
    ec.warmup_ticks = 100
    ec.performance_mode = performance
    ec.configure_stabilizers(households=False, firms=False, government=False)
    patch_agent_method(monkeypatch, firm, "plan_production_and_labor",
                       lambda *args, **kwargs: firm._stamp_labor_plan(20.0, 0, []))
    patch_agent_method(monkeypatch, firm, "plan_wage", lambda *args, **kwargs: {"wage_offer_next": 100.0})
    patch_agent_method(monkeypatch, firm, "plan_capital_investment", lambda *args, **kwargs: None)
    monkeypatch.setattr(ec, "_run_labor_matching", lambda *_: (
        {1: {"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}}},
        {1: {"employer_id": 1, "wage": 100.0, "employer_category": "Food"}},
    ))
    monkeypatch.setattr(ec, "_maybe_create_new_firms", lambda: 0)
    monkeypatch.setattr(ec, "_enqueue_healthcare_requests", lambda: None)
    return cfg, ec, hh, firm


@pytest.mark.parametrize("performance", (False, True))
def test_live_planner_runs_after_received_pay_and_keeps_its_refresh_cadence(factory, monkeypatch, performance):
    cfg, ec, hh, firm = _live_budget_world(factory, monkeypatch, performance=performance)
    calls = []
    original = ec._batch_plan_consumption

    def observe(*args, **kwargs):
        assert ec.payment_book.income_settled and ec.payment_book.benefits_settled
        plans = original(*args, **kwargs)
        calls.append((ec.current_tick, ec.payment_book.paid_income[1]["net"], plans[1]["budget"]))
        return plans

    monkeypatch.setattr(ec, "_batch_plan_consumption", observe)
    with use_config(cfg):
        ec.step()
        assert len(calls) == 1
        assert calls[0][1] == 80.0 and 0.0 < calls[0][2] <= 80.0
        hh.cash_balance, firm.cash_balance = 0.0, 0.0
        cached = copy.deepcopy(ec._cached_consumption_plans)
        ec.step()
    assert len(calls) == (1 if performance else 2)
    if performance:
        assert ec._cached_consumption_plans == cached
    else:
        assert calls[-1][1:] == (0.0, 0.0)
    assert hh.last_food_units == 0.0
    assert ec.food_unmet_demand == 0.0
    assert ec.payment_book.clearing_cash == pytest.approx(0.0, abs=1e-6)
