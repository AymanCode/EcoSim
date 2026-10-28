"""Private work is funded before it creates output or employment history."""

import copy
import math

import pytest

from agents import BankAgent
from config import clone_config, use_config
from economy import Economy
from payment_loans import collect_firm_dues, preflight_loans
from payments import PaymentBook
from tests_contracts.factories import patch_agent_method


SEQUENCES = ("income_first", "income_late")


def _prepared(factory, timing, *, wages=(100.0, 100.0), cash=200.0,
              category="Food", baseline=False, bank_cash=None):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.government.auto_working_capital_backstop = False
    with use_config(cfg):
        workers = [factory.household(household_id=i, employer_id=1, wage=wage,
                                    cash_balance=0.0, medical_training_status="none")
                   for i, wage in enumerate(wages, 1)]
        firm = factory.firm(
            firm_id=1, category=category, is_baseline=baseline,
            cash_balance=cash, employees=[h.household_id for h in workers],
            actual_wages={h.household_id: h.wage for h in workers},
            wage_offer=min(wages, default=20.0), owners=[], ceo_household_id=None,
            production_capacity_units=5.0 if category == "Services" else 1000.0,
        )
        firm.wage_offer = min(wages, default=20.0)
        firm.trailing_revenue_12t = 10_000.0
        bank = None if bank_cash is None else BankAgent(cash_reserves=bank_cash)
        ec = Economy(households=workers, firms=[firm],
                     government=factory.government(cash_balance=50_000.0,
                                                  wage_tax_rate=0.0), bank=bank)
        ec.current_tick = 5
        ec.payment_book = PaymentBook(ec, timing=timing)
        ec.payment_state["prior_settled_firm_operating_cashflow"] = {1: 10_000.0}
        outcomes = {1: {"hired_households_ids": [], "confirmed_layoffs_ids": [],
                        "actual_wages": {}, "unfilled_vacancies": 0}}
        household_outcomes = {h.household_id: {"employer_id": 1, "wage": h.wage,
                                              "employer_category": category}
                              for h in workers}
        return cfg, ec, firm, workers, bank, outcomes, household_outcomes


def _fund(ec, outcomes, household_outcomes):
    from payment_payroll import enforce_private_payroll

    enforce_private_payroll(ec, outcomes, household_outcomes)


def _settle_current(ec):
    ec.payment_book.settle_income({h.household_id: h.wage if h.is_employed else 0.0
                                   for h in ec.households})


@pytest.mark.parametrize("timing", SEQUENCES)
def test_cash_funded_payroll_needs_no_credit_approval(factory, timing):
    cfg, ec, firm, workers, bank, outcomes, hh_outcomes = _prepared(
        factory, timing, cash=200.0, bank_cash=0.0,
    )
    bank.firm_credit_scores[1] = 0.0
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
        assert firm.employees == [1, 2]
        assert firm.cash_balance == 200.0  # Authorization is not a second payment.
        assert not bank.active_loans
        _settle_current(ec)
    assert not ec.payment_state["wage_claims"]
    assert sum(ec.payment_book.current_paid_by_firm_worker.values()) == 200.0
    assert firm.cash_balance == 0.0
    assert all(h.employer_id == 1 for h in workers)


@pytest.mark.parametrize("timing", SEQUENCES)
@pytest.mark.parametrize("wages,cash,retained", [
    ((1e12, 20.00005), 20.000025, []), ((1e16, 21.0), 20.5, []),
    ((20.000001,), 20.0, []), ((1e16, 21.0), 1e16 + 20.0, [2]),
])
def test_roundoff_cannot_authorize_an_underfunded_complete_roster(factory, timing, wages, cash, retained):
    cfg, ec, firm, workers, _, outcomes, hh_outcomes = _prepared(
        factory, timing, wages=wages, cash=cash,
    )
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
        assert firm.employees == retained
        assert all((h.employer_id == 1) == (h.household_id in retained) for h in workers)
        _settle_current(ec)
    assert not ec.payment_state["wage_claims"]
    assert firm.cash_balance == cash - math.fsum(wages[hid - 1] for hid in retained)


@pytest.mark.parametrize("timing", SEQUENCES)
def test_fully_funded_large_contracts_are_paid_without_proportional_roundoff(factory, timing):
    wages = (1e12 + 0.1,) * 10
    cfg, ec, firm, workers, _, outcomes, hh_outcomes = _prepared(
        factory, timing, wages=wages, cash=math.fsum(wages),
    )
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
        _settle_current(ec)
    assert len(firm.employees) == 10
    assert not ec.payment_state["wage_claims"]
    assert all(ec.payment_book.current_paid_by_firm_worker[(1, h.household_id)] == h.wage
               for h in workers)


@pytest.mark.parametrize("timing", SEQUENCES)
def test_later_cash_drain_cannot_silently_create_a_new_private_wage_claim(factory, timing):
    cfg, ec, firm, workers, _, outcomes, hh_outcomes = _prepared(factory, timing, cash=200.0)
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
        # A future phase violating the authorization must fail visibly, rather
        # than quietly charge the worker for an already-assigned full contract.
        firm.cash_balance = 199.0
        before = (firm.cash_balance, [h.cash_balance for h in workers],
                  ec.government.cash_balance, copy.deepcopy(ec.payment_state))
        with pytest.raises(ValueError):
            _settle_current(ec)
    assert (firm.cash_balance, [h.cash_balance for h in workers],
            ec.government.cash_balance, ec.payment_state) == before


@pytest.mark.parametrize("timing", SEQUENCES)
def test_real_bank_credit_funds_payroll_once_and_is_repaid(factory, timing):
    cfg, ec, firm, workers, bank, outcomes, hh_outcomes = _prepared(
        factory, timing, cash=150.0, bank_cash=10_000.0,
    )
    bank_before = bank.cash_reserves
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
        assert len(bank.active_loans) == 1
        loan = bank.active_loans[0]
        assert loan["principal"] == pytest.approx(50.0)
        assert loan["subtype"] == "working_capital"
        assert loan["funder"] == "bank"
        assert firm.cash_balance == pytest.approx(200.0)
        assert bank_before - bank.cash_reserves == pytest.approx(50.0)
        assert firm.bank_loan_remaining == pytest.approx(50.0)
        assert firm.bank_loan_payment_per_tick == pytest.approx(loan["payment_per_tick"])
        _settle_current(ec)
        assert not ec.payment_state["wage_claims"]
        assert firm.employees == [1, 2]
        assert firm.cash_balance == pytest.approx(0.0)
        preflight_loans(ec)

        # Add a declared test cash balance to service the real next-tick claim.
        ec.current_tick += 1
        ec.payment_book = PaymentBook(ec, timing=timing)
        firm.cash_balance = 1000.0
        before = firm.cash_balance, bank.cash_reserves
        paid = collect_firm_dues(ec)
        assert paid == pytest.approx(loan["payment_per_tick"])
        assert before[0] - firm.cash_balance == pytest.approx(paid)
        assert bank.cash_reserves - before[1] == pytest.approx(paid)
        assert loan["missed_payments"] == 0
        assert firm.bank_loan_remaining == pytest.approx(loan["remaining"])
        preflight_loans(ec)


@pytest.mark.parametrize("timing", SEQUENCES)
@pytest.mark.parametrize("denial", ("reserves", "score", "repayment", "disabled", "no_bank"))
def test_denied_bank_credit_reduces_staff_without_treasury_fallback(factory, timing, denial):
    cfg, ec, firm, workers, bank, outcomes, hh_outcomes = _prepared(
        factory, timing, cash=150.0, bank_cash=10_000.0,
    )
    if denial == "reserves":
        bank.cash_reserves = 0.0
    elif denial == "score":
        bank.firm_credit_scores[1] = 0.0
    elif denial == "repayment":
        ec.payment_state["prior_settled_firm_operating_cashflow"] = {1: 0.0}
    elif denial == "disabled":
        cfg.firms.working_capital_enabled = False
    else:
        ec.bank = None
    before = firm.cash_balance, bank.cash_reserves, ec.government.cash_balance
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
        assert len(firm.employees) == 1
        retained = firm.employees[0]
        removed = next(h for h in workers if h.household_id != retained)
        assert removed.employer_id is None and removed.wage == 0.0
        assert hh_outcomes[removed.household_id]["employer_id"] is None
        assert removed.household_id not in firm.actual_wages
        assert firm._current_wage_bill() == pytest.approx(100.0)
        assert (firm.cash_balance, bank.cash_reserves, ec.government.cash_balance) == before
        assert not bank.active_loans
        _settle_current(ec)
    assert ec.payment_state["wage_claims"] == {}
    assert ec.payment_book.paid_income[retained]["gross"] == 100.0


@pytest.mark.parametrize("timing", SEQUENCES)
def test_capped_credit_only_creates_borrowed_debt_and_affordable_contracts(factory, timing):
    cfg, ec, firm, _, bank, outcomes, hh_outcomes = _prepared(
        factory, timing, wages=(100.0, 100.0, 100.0), cash=150.0, bank_cash=10_000.0,
    )
    cfg.firms.working_capital_max_loan_per_firm = 50.0
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
        assert len(firm.employees) == 2
        assert firm._current_wage_bill() == pytest.approx(200.0)
        assert sum(loan["principal"] for loan in bank.active_loans) == pytest.approx(50.0)
        assert firm.bank_loan_remaining == pytest.approx(50.0)
        _settle_current(ec)
    assert not ec.payment_state["wage_claims"]


@pytest.mark.parametrize("cash", (-10.0, 0.0, 50.0))
def test_no_complete_contract_can_be_kept_from_insufficient_signed_cash(factory, cash):
    cfg, ec, firm, workers, _, outcomes, hh_outcomes = _prepared(
        factory, "income_first", cash=cash,
    )
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
        assert firm.employees == [] and firm.actual_wages == {}
        assert all(h.employer_id is None and h.wage == 0.0 for h in workers)
        assert firm.cash_balance == cash
        _settle_current(ec)
    assert not ec.payment_state["wage_claims"]
    assert sum(row["gross"] for row in ec.payment_book.paid_income.values()) == 0.0


@pytest.mark.parametrize("timing", SEQUENCES)
def test_cancelled_hire_preserves_incumbent_and_existing_earned_claim(factory, timing):
    cfg, ec, firm, _, _, outcomes, hh_outcomes = _prepared(factory, timing, cash=100.0)
    outcomes[1]["hired_households_ids"] = [2]
    outcomes[1]["actual_wages"] = {2: 100.0}
    firm.last_tick_planned_hires = 1
    ec.last_labor_events = [{"event_type": "hire", "firm_id": 1, "household_id": 2}]
    ec.payment_book.net_offer_diagnostics = [{"offer_id": 1, "household_id": 2}]
    ec.payment_state["wage_claims"][(1, 2)] = 20.0
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
        assert firm.employees == [1]
        assert outcomes[1]["hired_households_ids"] == []
        assert firm.last_tick_actual_hires == 0
        assert outcomes[1]["unfilled_vacancies"] >= 1
        assert not any(event.get("event_type") == "hire" and event.get("household_id") == 2
                       for event in ec.last_labor_events)
        assert not ec.payment_book.net_offer_diagnostics
        assert ec.payment_state["wage_claims"][(1, 2)] == 20.0
        _settle_current(ec)
    assert ec.payment_state["wage_claims"][(1, 2)] == 20.0
    assert ec.payment_book.paid_income[1]["gross"] == 100.0


@pytest.mark.parametrize("timing", SEQUENCES)
def test_existing_claim_is_repaid_from_real_cash_after_current_pay(factory, timing):
    cfg, ec, firm, _, _, outcomes, hh_outcomes = _prepared(factory, timing, cash=250.0)
    ec.payment_state["wage_claims"][(1, 1)] = 50.0
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
        assert ec.payment_state["wage_claims"][(1, 1)] == 50.0
        _settle_current(ec)
    assert not ec.payment_state["wage_claims"]
    assert ec.payment_book.paid_income[1]["gross"] == 150.0
    assert ec.payment_book.paid_income[2]["gross"] == 100.0
    assert firm.cash_balance == 0.0


@pytest.mark.parametrize("cash,retained_limit", ((100.0, 1), (0.0, 1)))
def test_financial_services_cut_keeps_space_and_only_one_empty_restart(factory, cash, retained_limit):
    cfg, ec, firm, _, _, outcomes, hh_outcomes = _prepared(
        factory, "income_first", category="Services", cash=cash,
    )
    firm.service_staffing_target = 5
    firm.service_staffing_recovery_streak = 2
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
    assert firm.production_capacity_units == 5.0
    assert len(firm.employees) == (1 if cash else 0)
    assert firm._service_staffing_limit() == retained_limit
    assert firm.service_staffing_recovery_streak == 0


@pytest.mark.parametrize("category,baseline,registered", (
    ("Food", True, False), ("Services", True, False), ("Food", False, True),
    ("Housing", False, False), ("Healthcare", True, False),
))
def test_baseline_and_specialist_providers_are_not_dismissed(factory, category, baseline, registered):
    cfg, ec, firm, workers, _, outcomes, hh_outcomes = _prepared(
        factory, "income_first", category=category, baseline=baseline, cash=0.0,
    )
    if category == "Healthcare":
        for hh in workers:
            hh.medical_training_status = "doctor"
    if registered:
        ec.government.register_baseline_firm(category, 1)
    before = copy.deepcopy((firm.employees, firm.actual_wages, outcomes, hh_outcomes))
    with use_config(cfg):
        _fund(ec, outcomes, hh_outcomes)
    assert (firm.employees, firm.actual_wages, outcomes, hh_outcomes) == before
    assert all(h.employer_id == 1 for h in workers)


def _fixed_public_step(factory, monkeypatch, *, timing="income_first", cash=100.0,
                       incumbent=False, current_tick=5, wage=100.0, category="Food"):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.firms.working_capital_enabled = False
    cfg.government.auto_working_capital_backstop = False
    cfg.firms.quality_research_model = "scale_only"
    cfg.households.healthcare_food_first_reserve = False
    with use_config(cfg):
        hh = factory.household(household_id=1, employer_id=1 if incumbent else None,
                               wage=wage if incumbent else 0.0, cash_balance=0.0,
                               skills_level=1.0, category_experience={category: 520},
                               last_wage_update_tick=0, job_search_cooldown=0)
        firm = factory.firm(firm_id=1, category=category, is_baseline=False,
                            employees=[1] if incumbent else [],
                            actual_wages={1: wage} if incumbent else {},
                            cash_balance=cash, inventory_units=0.0,
                            wage_offer=wage, owners=[], ceo_household_id=None,
                            production_capacity_units=5.0 if category == "Services" else 1000.0)
        firm.wage_offer = wage
        firm.expected_sales_units = 100.0
        government = factory.government(cash_balance=0.0, wage_tax_rate=0.0,
                                       profit_tax_rate=0.0, unemployment_benefit_level=0.0,
                                       transfer_budget=0.0)
        ec = factory.economy(households=[hh], firms=[firm], government=government)
    ec.current_tick, ec.warmup_ticks = current_tick, 100
    ec.configure_stabilizers(households=False, firms=False, government=False)
    monkeypatch.setattr(ec, "_maybe_create_new_firms", lambda: 0)
    monkeypatch.setattr(ec, "_enqueue_healthcare_requests", lambda: None)
    patch_agent_method(monkeypatch, firm, "plan_production_and_labor",
                       lambda *args, **kwargs: firm._stamp_labor_plan(100.0, 0 if incumbent else 1, []))
    patch_agent_method(monkeypatch, firm, "plan_wage", lambda *args, **kwargs: {"wage_offer_next": wage})
    patch_agent_method(monkeypatch, firm, "plan_capital_investment", lambda *args, **kwargs: None)
    patch_agent_method(monkeypatch, hh, "plan_labor_supply", lambda *args, **kwargs: {
        "searching_for_job": not incumbent, "job_switching": False,
        "reservation_wage": 0.0, "skills_level": 1.0, "medical_only": False,
    })
    return cfg, ec, hh, firm


@pytest.mark.parametrize("timing", SEQUENCES)
@pytest.mark.parametrize("match_mode", ("fast", "legacy"))
def test_actual_match_premium_cannot_create_unfunded_work(factory, monkeypatch, timing, match_mode):
    cfg, ec, hh, firm = _fixed_public_step(factory, monkeypatch, timing=timing, cash=110.0)
    ec.labor_match_mode = match_mode
    before_experience = hh.category_experience["Food"]
    before_work_ticks = hh.employed_ticks_since_skill_update
    with use_config(cfg):
        ec.step()
    # The real matcher adds skill and experience premiums to the 100 offer.
    assert not hh.is_employed
    assert hh.wage == 0.0 and firm.employees == [] and firm.actual_wages == {}
    assert hh.category_experience["Food"] == before_experience
    assert hh.employed_ticks_since_skill_update == before_work_ticks
    assert hh.unemployment_duration == 1
    assert firm.last_units_produced == 0.0
    assert ec.payment_book.paid_income[1]["gross"] == 0.0
    assert not ec.payment_state["wage_claims"]
    assert not any(e["event_type"] == "hire" for e in ec.last_labor_events)


def test_newly_hired_worker_budgets_from_this_weeks_funded_premium(factory, monkeypatch):
    cfg, ec, hh, firm = _fixed_public_step(factory, monkeypatch, cash=200.0)
    plans_seen = []
    original_plan = ec._batch_plan_consumption

    def observe_plan(*args, **kwargs):
        assert ec.payment_book.income_settled and ec.payment_book.benefits_settled
        plans = original_plan(*args, **kwargs)
        plans_seen.append(plans[1]["budget"])
        return plans

    monkeypatch.setattr(ec, "_batch_plan_consumption", observe_plan)
    before_experience = hh.category_experience["Food"]
    with use_config(cfg):
        ec.step()
    assert hh.employer_id == 1
    assert ec.payment_book.paid_income[1]["gross"] == pytest.approx(155.0)
    assert len(plans_seen) == 1 and 0.0 < plans_seen[0] <= 155.0
    assert hh.category_experience["Food"] == before_experience + 1
    assert firm.last_units_produced > 0.0
    assert not ec.payment_state["wage_claims"]


@pytest.mark.parametrize("timing", SEQUENCES)
def test_scheduled_raise_is_included_before_work_is_authorized(factory, monkeypatch, timing):
    cfg, ec, hh, firm = _fixed_public_step(
        factory, monkeypatch, timing=timing, incumbent=True, current_tick=50,
        wage=100.0, cash=101.0,
    )
    before_experience = hh.category_experience["Food"]
    before_work_ticks = hh.employed_ticks_since_skill_update
    with use_config(cfg):
        ec.step()
    assert not hh.is_employed
    assert hh.category_experience["Food"] == before_experience
    assert hh.employed_ticks_since_skill_update == before_work_ticks
    assert firm.last_units_produced == 0.0
    assert not ec.payment_state["wage_claims"]
    assert any(e["event_type"] == "layoff" and e["household_id"] == 1 for e in ec.last_labor_events)


@pytest.mark.parametrize("cash,funded", ((100.0, False), (225.0, True)))
def test_only_a_retained_funded_extra_project_hire_creates_public_slot(factory, monkeypatch, cash, funded):
    from payment_government import reserve_payment_services_project

    cfg, ec, firm, workers, _, _, _ = _prepared(
        factory, "income_first", category="Services", cash=cash,
    )
    current, newcomer = workers
    newcomer.employer_id, newcomer.wage = None, 0.0
    newcomer.skills_level = 1.0
    newcomer.category_experience = {}
    firm.employees, firm.actual_wages = [1], {1: 100.0}
    firm.production_capacity_units = 1.0
    firm.service_staffing_target = 1
    cfg.firms.working_capital_enabled = False
    cfg.firms.quality_research_model = "scale_only"
    cfg.payment_services_project_enabled = True
    ec.government.cash_balance = 1000.0
    ec.government.wage_tax_rate = ec.government.profit_tax_rate = 0.0
    ec.government.unemployment_benefit_level = 0.0
    ec.warmup_ticks = 100
    ec.configure_stabilizers(households=False, firms=False, government=False)
    monkeypatch.setattr(ec, "_maybe_create_new_firms", lambda: 0)
    monkeypatch.setattr(ec, "_enqueue_healthcare_requests", lambda: None)
    patch_agent_method(monkeypatch, firm, "plan_production_and_labor",
                       lambda *args, **kwargs: firm._stamp_labor_plan(100.0, 0, []))
    patch_agent_method(monkeypatch, firm, "plan_wage", lambda *args, **kwargs: {"wage_offer_next": 100.0})
    patch_agent_method(monkeypatch, firm, "plan_capital_investment", lambda *args, **kwargs: None)
    patch_agent_method(monkeypatch, current, "plan_labor_supply", lambda *args, **kwargs: {
        "searching_for_job": False, "job_switching": False,
        "reservation_wage": 0.0, "skills_level": current.skills_level, "medical_only": False,
    })
    patch_agent_method(monkeypatch, newcomer, "plan_labor_supply", lambda *args, **kwargs: {
        "searching_for_job": True, "job_switching": False,
        "reservation_wage": 0.0, "skills_level": 1.0, "medical_only": False,
    })
    matched = []
    original_match = ec._run_labor_matching

    def observe_match(*args, **kwargs):
        result = original_match(*args, **kwargs)
        matched.extend(result[0][1]["hired_households_ids"])
        return result

    monkeypatch.setattr(ec, "_run_labor_matching", observe_match)
    ec.current_tick = 4
    with use_config(cfg):
        assert reserve_payment_services_project(ec) is not None
        ec.current_tick = 5
        before_slots = firm.production_capacity_units
        ec.step()
    assert matched == [2]  # The real matcher found the additional installer.
    assert current.employer_id == 1
    assert (newcomer.employer_id == 1) is funded
    assert firm.production_capacity_units == before_slots
    assert bool(ec.payment_state.get("services_future_slots")) is funded
    assert bool(ec.payment_state.get("services_pending_receipts")) is funded
    assert not ec.payment_state["wage_claims"]
    if funded:
        assert ec.payment_project_worker_by_firm == {1: 2}
        assert ec.payment_book.current_paid_by_firm_worker[(1, 2)] == pytest.approx(125.0)
        assert firm.last_units_produced <= firm._capacity_for_workers(1) + 1e-6
    else:
        assert not ec.payment_project_worker_by_firm
        assert ec.payment_book.current_paid_by_firm_worker.get((1, 2), 0.0) == 0.0
