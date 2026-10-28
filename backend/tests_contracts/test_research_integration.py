"""Research must survive the real debt, income and recipient boundaries."""

import random

import pytest

from agents import BankAgent
from config import clone_config, use_config
from tests_contracts.factories import patch_agent_method
from tools.benchmarks.panel_money import total_money_net_of_injections


def research_world(factory, monkeypatch, sequence, model, *, price=1000.0,
                   worker=False, ceo=False):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    cfg.firms.quality_research_model = model
    with use_config(cfg):
        buyer = factory.household(household_id=2, cash_balance=1_000_000.0,
                                  goods_inventory={})
        households = [buyer]
        employees = []
        wages = {}
        if worker:
            employee = factory.household(household_id=1, cash_balance=1000.0,
                                        employer_id=1, wage=100.0, goods_inventory={})
            households.append(employee)
            employees = [1]
            wages = {1: 100.0}
        firm = factory.firm(firm_id=1, category="Food", is_baseline=False,
            cash_balance=20_000.0, inventory_units=1_000_000.0, price=price,
            quality_level=0.6, employees=employees, actual_wages=wages,
            ceo_household_id=2 if ceo else None, owners=[])
        firm.risk_tolerance = 0.5
        gov = factory.government(cash_balance=0.0, wage_tax_rate=0.0,
            profit_tax_rate=0.0, unemployment_benefit_level=0.0,
            transfer_budget=0.0, infrastructure_spending=0.0,
            technology_spending=0.0, social_spending=0.0,
            investment_tax_rate=0.1)
        ec = factory.economy(households=households, firms=[firm], government=gov)
    ec.current_tick = 5
    ec.warmup_ticks = 100
    ec.configure_stabilizers(households=False, firms=False, government=False)
    ec.misc_firm_beneficiaries = [2]
    monkeypatch.setattr(ec, "_run_labor_matching", lambda *_: (
        {1: {"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}}},
        {h.household_id: {"employer_id": 1 if h.household_id == 1 else None,
                          "wage": 100.0 if h.household_id == 1 else 0.0,
                          "employer_category": "Food"} for h in households}))
    monkeypatch.setattr(ec, "_batch_plan_consumption", lambda *_, **__: {
        h.household_id: {"planned_purchases": {1: 2.0} if h.household_id == 2 else {},
                        "budget": price * 2 if h.household_id == 2 else 0.0}
        for h in households})
    monkeypatch.setattr(ec, "_maybe_create_new_firms", lambda: 0)
    monkeypatch.setattr(ec, "_enqueue_healthcare_requests", lambda: None)
    patch_agent_method(monkeypatch, firm, "plan_pricing",
                       lambda *_a, **_k: {"price_next": price, "markup_next": firm.markup})
    return cfg, ec, firm, buyer, gov


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
@pytest.mark.parametrize("model", ["project_outcome", "project_cost"])
def test_step_research_installs_only_at_completion_and_pays_real_recipients(
    factory, monkeypatch, sequence, model,
):
    cfg, ec, firm, buyer, gov = research_world(factory, monkeypatch, sequence, model)
    calls = []
    original = firm.advance_research

    def observe(**kwargs):
        before = (firm.cash_balance, firm.quality_level, firm.accumulated_rd_investment)
        spent = original(**kwargs)
        calls.append((before, kwargs, spent, firm.quality_level,
                      firm.research_state.project is None))
        assert firm.cash_balance == pytest.approx(before[0] - spent)
        assert firm.accumulated_rd_investment == pytest.approx(before[2] + spent)
        return spent

    patch_agent_method(monkeypatch, firm, "advance_research", observe)
    closes = []
    original_close = ec._phase_institutional_close

    def close(tick):
        before = (gov.cash_balance, ec.misc_firm_revenue)
        original_close(tick)
        closes.append((gov.cash_balance - before[0], ec.misc_firm_revenue - before[1]))

    monkeypatch.setattr(ec, "_phase_institutional_close", close)
    opening = total_money_net_of_injections(ec)
    with use_config(cfg):
        for _ in range(45):
            current = ec.current_tick
            ec.step()
            before, _, spent, quality, completed = calls[-1]
            assert ec.last_tick_research_gain == pytest.approx(quality - before[1])
            if not completed:
                assert quality == before[1]
            tax = spent * gov.investment_tax_rate
            remainder = spent - tax
            skim = random.Random(cfg.random_seed + current * 2_038_073 + int(remainder * 100)).uniform(0, .2)
            assert closes[-1] == pytest.approx((tax + remainder * skim,
                                               remainder * (1 - skim)), abs=1e-8)
            assert total_money_net_of_injections(ec) == pytest.approx(opening, rel=0, abs=1e-6)
            assert ec.payment_book.clearing_cash == pytest.approx(0, abs=1e-8)
    assert len(calls) == 45
    assert sum(c[2] for c in calls) > 1000
    assert sum(c[4] for c in calls) == 1
    completion = next(i for i, c in enumerate(calls) if c[4])
    assert 35 <= completion <= 40
    assert buyer.last_tick_ledger.get("redistribution", 0) >= 0


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
@pytest.mark.parametrize("model", ["project_outcome", "project_cost"])
@pytest.mark.parametrize("route", ["bank", "direct_treasury"])
def test_final_actual_debt_payment_reduces_research_budget_after_mirror_is_zero(
    factory, monkeypatch, sequence, model, route,
):
    cfg, ec, firm, _, gov = research_world(factory, monkeypatch, sequence, model)
    bank_collections = []
    original_settlement = ec._phase_household_and_fiscal_settlement

    def observe_settlement(tick):
        before = ec.bank.cash_reserves if ec.bank else 0.0
        original_settlement(tick)
        bank_collections.append((ec.bank.cash_reserves if ec.bank else 0.0) - before)

    monkeypatch.setattr(ec, "_phase_household_and_fiscal_settlement", observe_settlement)
    with use_config(cfg):
        assert firm.advance_research(tick=4, operating_cash_generation=1020.0) > 0
        progress = firm.research_state.project.funded_ticks
        if route == "bank":
            ec.bank = BankAgent(cash_reserves=20_000.0)
            loan = ec.bank.originate_loan("firm", 1, 3000.0, 0.0, 1)
            firm.cash_balance += 3000.0
            firm.bank_loan_remaining = loan["remaining"]
            firm.bank_loan_payment_per_tick = 3000.0
        else:
            firm.government_loan_remaining = 3000.0
            firm.loan_payment_per_tick = 3000.0
        spent = firm.accumulated_rd_investment
        opening = total_money_net_of_injections(ec)
        ec.step()
    assert firm.bank_loan_remaining == pytest.approx(0.0)
    assert firm.government_loan_remaining == pytest.approx(0.0)
    assert firm.accumulated_rd_investment == spent
    assert firm.research_state.project.funded_ticks == progress
    assert firm.research_state.project.status == "paused"
    assert total_money_net_of_injections(ec) == pytest.approx(opening, rel=0, abs=1e-6)
    if route == "bank":
        assert bank_collections == pytest.approx([3000.0])
    else:
        assert gov.cash_balance >= 3000.0


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
@pytest.mark.parametrize("model", ["project_outcome", "project_cost"])
@pytest.mark.parametrize("extra_payment", ["ceo", "old_wages"])
def test_paid_ceo_or_old_wages_cannot_be_reused_as_research_earnings(
    factory, monkeypatch, sequence, model, extra_payment,
):
    cfg, ec, firm, _, _ = research_world(factory, monkeypatch, sequence, model,
        price=100.0, worker=True, ceo=extra_payment == "ceo")
    generation = []
    original_advance = firm.advance_research

    def observe_earnings(**kwargs):
        generation.append(kwargs["operating_cash_generation"])
        return original_advance(**kwargs)

    with use_config(cfg):
        assert firm.advance_research(tick=4, operating_cash_generation=1020.0) > 0
        patch_agent_method(monkeypatch, firm, "advance_research", observe_earnings)
        progress = firm.research_state.project.funded_ticks
        if extra_payment == "old_wages":
            ec.payment_state["wage_claims"][(1, 1)] = 300.0
        before = firm.accumulated_rd_investment
        ec.step()
    assert firm.net_profit > 0.0
    assert generation == pytest.approx([firm.net_profit - 300.0])
    assert firm.payment_wage_arrears == pytest.approx(0.0)
    assert firm.accumulated_rd_investment == before
    assert firm.research_state.project.funded_ticks == progress
    assert firm.research_state.project.status == "paused"
    if extra_payment == "ceo":
        assert ec.payment_book.funded_ceo[1] == pytest.approx(300.0)
    else:
        assert ec.payment_book.funded_wages_by_firm[1] == pytest.approx(400.0)


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
@pytest.mark.parametrize("model", ["project_outcome", "project_cost"])
def test_zero_sale_ticks_still_process_and_eventually_pause_existing_research(
    factory, monkeypatch, sequence, model,
):
    cfg, ec, firm, _, _ = research_world(factory, monkeypatch, sequence, model)
    monkeypatch.setattr(ec, "_batch_plan_consumption", lambda *_, **__: {
        2: {"planned_purchases": {}, "budget": 0.0}})
    with use_config(cfg):
        assert firm.advance_research(tick=4, operating_cash_generation=1020.0) > 0
        progress = firm.research_state.project.funded_ticks
        for _ in range(10):
            ec.step()
    assert firm.research_state.project.funded_ticks >= progress
    assert firm.research_state.project.status == "paused"
    assert firm.quality_level == 0.6
    assert firm.last_revenue == 0.0
