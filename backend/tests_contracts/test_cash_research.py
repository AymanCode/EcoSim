"""Actual post-payment cash funds a slow, uncertain research commitment."""

import copy
import random

import pytest

from agents import BankAgent
from config import FirmBehaviorConfig, SimulationConfig, clone_config, use_config
from firm_research import ResearchProject
from tests_contracts.factories import patch_agent_method
from tests_contracts.test_research_integration import research_world
from tools.benchmarks.panel_money import total_money_net_of_injections


@pytest.fixture
def cash_config():
    cfg = clone_config()
    cfg.random_seed = 42
    cfg.firms.quality_research_model = "project_cash"
    with use_config(cfg):
        yield cfg


def cash_firm(factory, **overrides):
    values = dict(firm_id=1, is_baseline=False, quality_level=0.6,
                  cash_balance=10_600.0, last_tick_total_costs=100.0, owners=[])
    values.update(overrides)
    return factory.firm(**values)


@pytest.mark.parametrize("category", ["Food", "Services"])
@pytest.mark.parametrize("generation", [-1000.0, 0.0, 1000.0])
def test_saved_cash_funds_a_quoted_program_despite_low_or_negative_earnings(
    factory, cash_config, category, generation,
):
    firm = cash_firm(factory, category=category)
    assert firm.advance_research(tick=0, operating_cash_generation=generation) == 250.0
    assert firm.cash_balance == 10_350.0
    project = firm.research_state.project
    assert project.installment * project.required_ticks == 10_000.0
    assert project.funded_ticks == 1
    assert firm.quality_level == 0.6
    firm.cash_balance += 5000.0
    assert firm.advance_research(tick=1, operating_cash_generation=generation) == 250.0
    assert firm.research_state.project.installment == 250.0


@pytest.mark.parametrize("cash", [-1.0, 0.0, 600.0, 1799.99])
def test_new_program_requires_the_existing_minimum_above_reserves(factory, cash_config, cash):
    firm = cash_firm(factory, cash_balance=cash)
    assert firm.advance_research(tick=0, operating_cash_generation=100_000.0) == 0.0
    assert firm.research_state.project is None
    assert firm.cash_balance == cash


def test_quote_and_payments_respect_the_restricted_available_cash_ceiling(factory, cash_config):
    firm = cash_firm(factory, cash_balance=100_000.0)
    assert firm.advance_research(tick=0, operating_cash_generation=100_000.0,
                                 available_cash=1800.0) == 30.0
    assert firm.research_state.project.installment == 30.0
    assert firm.advance_research(tick=1, operating_cash_generation=100_000.0,
                                 available_cash=629.0) == 0.0
    assert firm.research_state.project.status == "paused"
    assert firm.research_state.project.funded_ticks == 1


@pytest.mark.parametrize("budget", [1200.0, 10_000.0, 10_000.123456, 999_999.99, 1_469_988_653.927944])
def test_a_fully_backed_program_finishes_without_any_further_receipts(factory, cash_config, budget):
    firm = cash_firm(factory, cash_balance=600.0 + budget)
    for tick in range(40):
        assert firm.advance_research(tick=tick, operating_cash_generation=0.0) > 0.0
        assert firm.cash_balance >= 600.0
        if tick < 39:
            assert firm.quality_level == 0.6
    assert firm.research_state.completed == 1
    assert firm.research_state.project is None
    assert firm.accumulated_rd_investment == pytest.approx(budget, rel=1e-12, abs=1e-6)
    assert firm.cash_balance == pytest.approx(600.0, rel=0, abs=1e-6)
    reference = ResearchProject.quote("project_outcome", 0.6, 0, 1)
    gain, failed = reference.outcome(seed=42, identity="initial:1")
    assert firm.quality_level == pytest.approx(0.6 + gain)
    assert firm.research_state.failed == int(failed)


@pytest.mark.parametrize("budget,shortage", [(10_000.0, 2.0), (1_469_988_653.927944, 0.01)])
def test_final_rounding_tolerance_does_not_forgive_a_real_cash_shortage(
    factory, cash_config, budget, shortage,
):
    firm = cash_firm(factory, cash_balance=600.0 + budget)
    for tick in range(39):
        firm.advance_research(tick=tick, operating_cash_generation=0.0)
    installment = firm.research_state.project.installment
    firm.cash_balance = 600.0 + installment - shortage
    assert firm.advance_research(tick=39, operating_cash_generation=0.0) == 0.0
    assert firm.research_state.project.funded_ticks == 39
    assert firm.research_state.project.status == "paused"
    assert firm.quality_level == 0.6


def test_cash_shortage_pauses_then_resumes_the_same_commitment(factory, cash_config):
    firm = cash_firm(factory)
    firm.advance_research(tick=0, operating_cash_generation=0.0)
    project = firm.research_state.project
    firm.cash_balance = 849.0
    assert firm.advance_research(tick=1, operating_cash_generation=1_000_000.0) == 0.0
    assert project.status == "paused" and project.funded_ticks == 1
    firm.cash_balance = 850.0
    assert firm.advance_research(tick=2, operating_cash_generation=-1000.0) == 250.0
    assert project.status == "active" and project.funded_ticks == 2
    assert firm.cash_balance == 600.0


def test_fresh_cash_can_override_stale_survival_but_not_unpaid_obligations(factory, cash_config):
    firm = cash_firm(factory)
    firm.survival_mode = True
    assert firm.advance_research(tick=0, operating_cash_generation=-1000.0) == 250.0
    assert firm.survival_mode
    assert firm.advance_research(tick=1, operating_cash_generation=1000.0, blocked=True) == 0.0
    firm.payment_wage_arrears = 1.0
    assert firm.advance_research(tick=2, operating_cash_generation=1000.0) == 0.0
    assert firm.research_state.project.funded_ticks == 1


def test_switching_the_selector_does_not_rewrite_an_active_funding_policy(factory, cash_config):
    firm = cash_firm(factory)
    firm.advance_research(tick=0, operating_cash_generation=0.0)
    cash_config.firms.quality_research_model = "project_outcome"
    firm.survival_mode = True
    assert firm.advance_research(tick=1, operating_cash_generation=-1_000_000.0) == 250.0
    assert firm.research_state.project.variant == "project_cash"
    other = cash_firm(factory)
    assert other.advance_research(tick=0, operating_cash_generation=1000.0) == 30.0
    cash_config.firms.quality_research_model = "project_cash"
    assert other.advance_research(tick=1, operating_cash_generation=-1_000_000.0) == 0.0
    assert other.research_state.project.variant == "project_outcome"


def test_repeated_tick_cannot_spend_a_second_installment(factory, cash_config):
    firm = cash_firm(factory)
    firm.advance_research(tick=0, operating_cash_generation=0.0)
    before = copy.deepcopy(firm.research_state)
    cash = firm.cash_balance
    assert firm.advance_research(tick=0, operating_cash_generation=100_000.0) == 0.0
    assert firm.research_state == before and firm.cash_balance == cash


def test_cash_selector_is_validated_without_changing_the_default():
    assert SimulationConfig().firms.quality_research_model == "instant"
    assert SimulationConfig(firms=FirmBehaviorConfig(
        quality_research_model="project_cash")).firms.quality_research_model == "project_cash"


@pytest.mark.parametrize("amount", [None, -1.0, 0.0, 1199.99, float("nan"), float("inf")])
def test_invalid_or_underfunded_quotes_cannot_create_a_cash_program(amount):
    with pytest.raises(ValueError):
        ResearchProject.quote("project_cash", 0.6, 0, 1, cash_budget=amount)


@pytest.mark.parametrize("start", [0.11, 4.99, 9.0])
def test_more_spending_cannot_buy_faster_or_unbounded_quality(
    factory, cash_config, monkeypatch, start,
):
    monkeypatch.setattr(ResearchProject, "outcome", lambda project, **_: (
        1.05 * (1.0 - project.start_quality / 10.0) ** 1.5, False))
    firm = cash_firm(factory, quality_level=start)
    history = []
    for tick in range(520):
        firm.cash_balance += 1_000_000.0
        firm.advance_research(tick=tick, operating_cash_generation=1_000_000.0)
        if firm.research_state.last_gain:
            history.append((tick, firm.research_state.last_gain))
        assert len(firm.research_state.gains) <= 2
        assert sum(gain for at, gain in history if tick - 52 < at <= tick) <= 1.0 + 1e-12
        if start < 5 and tick < 500:
            assert firm.quality_level < 8.0
    assert firm.research_state.completed == 13


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
def test_real_tick_funds_loss_making_firm_from_cash_after_ordinary_payroll(
    factory, monkeypatch, sequence,
):
    cfg, ec, firm, _, _ = research_world(factory, monkeypatch, sequence, "project_cash",
                                        price=20.0, worker=True)
    opening = total_money_net_of_injections(ec)
    with use_config(cfg):
        ec.step()
    assert firm.net_profit < 0.0
    assert firm.accumulated_rd_investment > 30.0
    assert firm.research_state.project.funded_ticks == 1
    assert ec.payment_book.funded_wages_by_firm[1] == 100.0
    assert firm.cash_balance >= firm.last_tick_total_costs * 6.0
    assert total_money_net_of_injections(ec) == pytest.approx(opening, rel=0, abs=1e-6)


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
@pytest.mark.parametrize("route", ["bank", "direct_treasury"])
def test_actual_final_payment_leaves_no_research_budget(factory, monkeypatch, sequence, route):
    cfg, ec, firm, _, _ = research_world(factory, monkeypatch, sequence, "project_cash",
                                        price=20.0, worker=True)
    firm.cash_balance = 500.0
    with use_config(cfg):
        if route == "bank":
            ec.bank = BankAgent(cash_reserves=20_000.0)
            loan = ec.bank.originate_loan("firm", 1, 3000.0, 0.0, 1)
            firm.cash_balance += 3000.0
            firm.bank_loan_remaining = loan["remaining"]
            firm.bank_loan_payment_per_tick = 3000.0
        else:
            firm.cash_balance += 3000.0
            firm.government_loan_remaining = 3000.0
            firm.loan_payment_per_tick = 3000.0
        opening = total_money_net_of_injections(ec)
        ec.step()
    assert firm.bank_loan_remaining == pytest.approx(0.0)
    assert firm.government_loan_remaining == pytest.approx(0.0)
    assert firm.accumulated_rd_investment == 0.0
    assert firm.research_state.project is None
    assert ec.payment_book.funded_wages_by_firm[1] == 100.0
    assert total_money_net_of_injections(ec) == pytest.approx(opening, rel=0, abs=1e-6)


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
def test_paid_old_wages_reduce_cash_but_are_not_six_more_future_payrolls(factory, monkeypatch, sequence):
    cfg, ec, firm, _, _ = research_world(factory, monkeypatch, sequence, "project_cash",
                                        price=20.0, worker=True)
    firm.cash_balance = 3000.0
    ec.payment_state["wage_claims"][(1, 1)] = 300.0
    observed = []
    original = firm.advance_research

    def record(**kwargs):
        observed.append(kwargs)
        return original(**kwargs)

    patch_agent_method(monkeypatch, firm, "advance_research", record)
    opening = total_money_net_of_injections(ec)
    with use_config(cfg):
        ec.step()
    assert ec.payment_book.funded_wages_by_firm[1] == 400.0
    assert firm.payment_wage_arrears == 0.0
    assert observed[0]["operating_costs"] == 100.0
    assert observed[0]["operating_cash_generation"] < 0.0
    assert firm.accumulated_rd_investment > 0.0
    assert total_money_net_of_injections(ec) == pytest.approx(opening, rel=0, abs=1e-6)


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
def test_paid_ceo_remains_an_ongoing_operating_reserve(factory, monkeypatch, sequence):
    cfg, ec, firm, _, _ = research_world(factory, monkeypatch, sequence, "project_cash",
                                        price=20.0, worker=True, ceo=True)
    firm.cash_balance = 3000.0
    opening = total_money_net_of_injections(ec)
    with use_config(cfg):
        ec.step()
    assert ec.payment_book.funded_ceo[1] == 300.0
    assert firm.accumulated_rd_investment == 0.0
    assert firm.research_state.project is None
    assert total_money_net_of_injections(ec) == pytest.approx(opening, rel=0, abs=1e-6)


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
def test_late_restricted_receipt_cannot_enlarge_the_cash_program(factory, monkeypatch, sequence):
    import payment_government

    cfg, ec, firm, _, gov = research_world(factory, monkeypatch, sequence, "project_cash",
                                          price=20.0, worker=True)
    cfg.payment_services_project_enabled = True
    firm.cash_balance = 1000.0
    gov.cash_balance = 100_000.0
    patch_agent_method(monkeypatch, gov, "make_investments", lambda: {})

    def late_receipt(_economy):
        gov.cash_balance -= 100_000.0
        firm.cash_balance += 100_000.0

    monkeypatch.setattr(payment_government, "complete_payment_services_project", late_receipt)
    opening = total_money_net_of_injections(ec)
    with use_config(cfg):
        ec.step()
    assert firm.cash_balance > 100_000.0
    assert firm.accumulated_rd_investment == 0.0
    assert firm.research_state.project is None
    assert total_money_net_of_injections(ec) == pytest.approx(opening, rel=0, abs=1e-6)


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
def test_cash_program_finishes_through_real_ticks_with_exact_tax_and_pool_recipients(
    factory, monkeypatch, sequence,
):
    cfg, ec, firm, _, gov = research_world(factory, monkeypatch, sequence, "project_cash",
                                         worker=True)
    calls, closes = [], []
    original = firm.advance_research
    original_close = ec._phase_institutional_close

    def record(**kwargs):
        before = firm.cash_balance
        paid = original(**kwargs)
        calls.append((ec.current_tick, paid))
        assert firm.cash_balance == pytest.approx(before - paid)
        assert firm.cash_balance >= kwargs["operating_costs"] * 6.0
        return paid

    def close(tick):
        before = (gov.cash_balance, ec.misc_firm_revenue)
        original_close(tick)
        closes.append((gov.cash_balance - before[0], ec.misc_firm_revenue - before[1]))

    patch_agent_method(monkeypatch, firm, "advance_research", record)
    monkeypatch.setattr(ec, "_phase_institutional_close", close)
    opening = total_money_net_of_injections(ec)
    with use_config(cfg):
        for tick in range(45):
            ec.step()
            at, paid = calls[-1]
            tax = paid * gov.investment_tax_rate
            remainder = paid - tax
            skim = random.Random(cfg.random_seed + at * 2_038_073 + int(remainder * 100)).uniform(0, .2)
            assert closes[-1] == pytest.approx((tax + remainder * skim,
                                              remainder * (1.0 - skim)), abs=1e-8)
            if tick < 39:
                assert firm.quality_level == 0.6
            assert total_money_net_of_injections(ec) == pytest.approx(opening, rel=0, abs=1e-6)
            assert ec.payment_book.clearing_cash == pytest.approx(0.0, abs=1e-8)
    assert firm.research_state.completed == 1
    assert sum(paid for _, paid in calls) > 1200.0
