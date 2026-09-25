"""Funded Housing projects pay once and open capacity only on completion."""

from types import SimpleNamespace

import pytest

from config import clone_config, use_config
from payment_projects import (can_start_housing_project, cancel_payment_projects_for_exit,
                              complete_payment_projects, distribute_payment_project_proceeds,
                              project_quote, register_funded_housing_project,
                              start_payment_mortgage_project, try_start_self_funded_project)


def _fixture():
    firm = SimpleNamespace(firm_id=3, good_category="Housing", cash_balance=3000.0,
                           current_tenants=[1], max_rental_units=1,
                           production_capacity_units=1.0, expected_sales_units=1.0,
                           property_tax_rate=0.005)
    households = [SimpleNamespace(household_id=1, renting_from_firm_id=3, cash_balance=0.0,
                                  add_ledger_flow=lambda key, amount: None),
                  SimpleNamespace(household_id=2, renting_from_firm_id=None, cash_balance=0.0,
                                  add_ledger_flow=lambda key, amount: None)]
    economy = SimpleNamespace(payment_state={}, current_tick=10, firms=[firm],
                              firm_lookup={3: firm}, households=households,
                              misc_firm_revenue=0.0, bank=None)
    economy._collect_misc_revenue = lambda amount: setattr(economy, "misc_firm_revenue", economy.misc_firm_revenue + amount)
    return economy, firm, households


def test_reachable_self_funded_project_holds_capacity_until_declared_tick():
    economy, firm, _ = _fixture()
    assert try_start_self_funded_project(economy, firm)
    assert firm.cash_balance == pytest.approx(2000.0)
    assert economy.misc_firm_revenue == pytest.approx(1000.0)
    assert firm.max_rental_units == 1
    assert not can_start_housing_project(economy, firm, 1, "self")
    economy.current_tick = 13
    assert complete_payment_projects(economy) == []
    assert firm.max_rental_units == 1
    economy.current_tick = 14
    assert len(complete_payment_projects(economy)) == 1
    assert firm.max_rental_units == 2
    assert firm.production_capacity_units == 2.0
    assert firm.property_tax_rate == pytest.approx(0.01)
    assert economy.misc_firm_revenue == pytest.approx(1000.0)
    assert complete_payment_projects(economy) == []


def test_long_term_route_reaches_equal_households_once_with_no_early_units():
    economy, firm, households = _fixture()
    assert register_funded_housing_project(economy, firm, 2, "long_term", loan_id="loan-7")
    assert firm.cash_balance == pytest.approx(1000.0)
    assert firm.max_rental_units == 1
    assert economy.misc_firm_revenue == 0.0
    assert economy.payment_state["housing_equal_distribution_hold"] == pytest.approx(2000.0)
    assert distribute_payment_project_proceeds(economy) == pytest.approx(2000.0)
    assert [h.cash_balance for h in households] == pytest.approx([1000.0, 1000.0])
    assert distribute_payment_project_proceeds(economy) == 0.0
    economy.current_tick = 14
    complete_payment_projects(economy)
    assert firm.max_rental_units == 3


def test_exit_cancels_pending_capacity_without_refund_or_synthetic_salvage():
    economy, firm, _ = _fixture()
    assert try_start_self_funded_project(economy, firm)
    before_cash = firm.cash_balance
    project = cancel_payment_projects_for_exit(economy, firm)
    assert project["paid_amount"] == 1000.0
    economy.current_tick = 99
    assert complete_payment_projects(economy) == []
    assert firm.max_rental_units == 1
    assert firm.cash_balance == before_cash


def test_quote_requires_whole_units_inside_cap():
    assert project_quote(4) == 4000.0
    with pytest.raises(ValueError):
        project_quote(5)
    with pytest.raises(ValueError):
        project_quote(1.5)


def test_housing_projects_cannot_bypass_worker_claims_or_credit_cooldown():
    economy, firm, _ = _fixture()
    firm.payment_wage_arrears = 1.0
    for route in ("self", "mortgage", "long_term"):
        assert not can_start_housing_project(economy, firm, 1, route)
    assert firm.cash_balance == 3000.0
    firm.payment_wage_arrears = 0.0
    economy.payment_state["loan_credit_cooldown_until"] = {("firm", firm.firm_id): 20}
    assert can_start_housing_project(economy, firm, 1, "self")
    assert not can_start_housing_project(economy, firm, 1, "mortgage")
    assert not can_start_housing_project(economy, firm, 1, "long_term")


def test_named_zero_lag_opens_paid_capacity_immediately():
    cfg = clone_config()
    cfg.payment_construction_lag_ticks = 0
    economy, firm, _ = _fixture()
    with use_config(cfg):
        assert try_start_self_funded_project(economy, firm)
    assert firm.max_rental_units == 2
    assert economy.payment_state["housing_projects"] == {}
    assert [row["type"] for row in economy.payment_state["housing_project_events"]] == ["funded", "completed"]


def test_mortgage_uses_exact_quote_and_preserves_full_credit_gate():
    economy, firm, _ = _fixture()
    firm.cash_balance = 0.0
    firm.price = 100.0
    firm.needs_housing_expansion_loan = False
    firm.housing_expansion_loan_amount = 0.0
    firm.housing_active_loans = []
    firm.bank_loan_principal = 0.0
    firm.bank_loan_remaining = 0.0
    firm.bank_loan_payment_per_tick = 0.0
    economy.bank = SimpleNamespace(cash_reserves=5000.0, lendable_cash=500.0,
                                   current_annual_rate=0.05, can_lend=lambda: True)
    economy._compute_housing_pmt = lambda principal, rate, term: principal / term
    assert not try_start_self_funded_project(economy, firm)
    assert firm.housing_expansion_loan_amount == 1000.0
    assert not start_payment_mortgage_project(economy, firm)
    assert firm.max_rental_units == 1
    assert not firm.housing_active_loans
    assert economy.bank.cash_reserves == 5000.0
    firm.needs_housing_expansion_loan = True
    firm.housing_expansion_loan_amount = 1000.0
    economy.bank.lendable_cash = 5000.0
    assert start_payment_mortgage_project(economy, firm)
    assert economy.bank.cash_reserves == pytest.approx(4000.0)
    assert firm.cash_balance == pytest.approx(0.0)
    assert len(firm.housing_active_loans) == 1
    assert economy.misc_firm_revenue == pytest.approx(1000.0)
    assert firm.max_rental_units == 1
