"""Expansion funding preserves liquidity, actual claims and full project payment."""

from types import SimpleNamespace

import pytest

from agents import BankAgent
from config import clone_config, use_config
from economy import Economy
from payments import PaymentBook


@pytest.fixture(params=("income_first", "income_late"))
def world(factory, request):
    cfg = clone_config()
    cfg.payment_sequence = request.param
    with use_config(cfg):
        households = [factory.household(household_id=1, cash_balance=0.0)]
        firm = factory.firm(firm_id=90, category="Services", is_baseline=False,
                            production_capacity_units=5.0, cash_balance=100_000.0,
                            employees=list(range(1, 6)), actual_wages={hid: 20.0 for hid in range(1, 6)},
                            inventory_units=0.0, owners=[], ceo_household_id=None)
        firm.units_per_worker, firm.wage_offer, firm.price = 5.0, 20.0, 20.0
        firm.last_units_produced = firm.last_units_sold = 25.0
        firm.last_revenue = firm.revenue_ema = 1000.0
        firm.service_full_utilization_streak = 5
        firm.service_unmet_demand_window = [2.0] * 5
        firm.service_staffing_target = 5
        bank = BankAgent(cash_reserves=100_000.0)
        ec = Economy(households=households, firms=[firm], government=factory.government(), bank=bank)
        ec.current_tick = 40
        ec.payment_book = PaymentBook(ec, timing=request.param)
        ec.payment_state["prior_settled_firm_operating_cashflow"] = {90: 1000.0}
        yield ec, firm, bank


def expand(ec, firm, route):
    if route == "long_term":
        return ec._maybe_offer_long_term_capital_loan(
            firm, SimpleNamespace(sell_through_rate=1.0), .5, 100,
        )
    firm.needs_service_infrastructure_loan = True
    firm.service_infrastructure_loan_amount = 7000.0
    before = firm.production_capacity_units
    ec._offer_service_infrastructure_loans()
    return firm.production_capacity_units > before


@pytest.mark.parametrize("route,cost", (("long_term", 5000.0), ("infrastructure", 7000.0)))
@pytest.mark.parametrize("funding,cash", (("cash", 100_000.0), ("mixed", 4000.0), ("loan", 100.0)))
def test_actual_route_funds_cost_once_with_only_borrowed_principal(world, route, cost, funding, cash):
    ec, firm, bank = world
    firm.cash_balance = cash
    cash_before, bank_before = firm.cash_balance, bank.cash_reserves
    recipients_before = sum(h.cash_balance for h in ec.households)
    fiscal_before = ec.government.cash_balance + ec.misc_firm_revenue
    assert expand(ec, firm, route)
    own = cash_before - firm.cash_balance
    borrowed = bank_before - bank.cash_reserves
    assert own + borrowed == pytest.approx(cost)
    assert firm.bank_loan_remaining == pytest.approx(borrowed)
    assert sum(loan["principal"] for loan in bank.active_loans) == pytest.approx(borrowed)
    assert firm.service_staffing_target == int(firm.production_capacity_units)
    assert len(firm.employees) == 5  # An installation still needs actual recruitment.
    assert firm.service_full_utilization_streak == 0
    assert firm.service_unmet_demand_window == []
    if funding == "cash":
        assert own == cost
        assert not bank.active_loans
    elif funding == "loan":
        assert own == 0.0
        assert borrowed == cost
    else:
        assert 0.0 < own < cost
        assert 0.0 < borrowed < cost
        _, payroll, due = firm._service_pricing_costs()
        added = firm.production_capacity_units - 5
        reserve = firm._expansion_runway_gate_ticks() * (
            payroll + added * firm._effective_base_wage_cost() + due
        )
        assert firm.cash_balance >= reserve
    if route == "long_term":
        assert firm.total_long_term_loans_received == pytest.approx(borrowed)
        assert sum(row["amount"] for row in ec.payment_state["capital_routes"]) == cost
        ec._recycle_capital_investment()
        ec._recycle_capital_investment()
        assert sum(h.cash_balance for h in ec.households) - recipients_before == pytest.approx(cost)
    else:
        assert firm.service_infrastructure_loan_remaining == pytest.approx(borrowed)
        assert ec.government.cash_balance + ec.misc_firm_revenue - fiscal_before == pytest.approx(cost)


@pytest.mark.parametrize("route", ("long_term", "infrastructure"))
@pytest.mark.parametrize("denial", ("cash", "coverage", "credit"))
def test_required_loan_denial_spends_no_contribution_or_space(world, route, denial):
    ec, firm, bank = world
    firm.cash_balance = 4000.0
    if denial == "cash":
        bank.cash_reserves = 0.0
    elif denial == "coverage":
        ec.payment_state["prior_settled_firm_operating_cashflow"] = {90: 0.0}
    else:
        bank.firm_credit_scores[firm.firm_id] = 0.0
    before = firm.cash_balance, bank.cash_reserves, firm.production_capacity_units, ec.government.cash_balance, ec.misc_firm_revenue
    assert not expand(ec, firm, route)
    assert (firm.cash_balance, bank.cash_reserves, firm.production_capacity_units,
            ec.government.cash_balance, ec.misc_firm_revenue) == before
    assert not bank.active_loans
    assert not ec.payment_state.get("capital_routes")


@pytest.mark.parametrize("route", ("long_term", "infrastructure"))
def test_cash_project_does_not_need_bank_reserves_or_credit_approval(world, route):
    ec, firm, bank = world
    bank.cash_reserves = 0.0
    bank.firm_credit_scores[firm.firm_id] = 0.0
    ec.payment_state["prior_settled_firm_operating_cashflow"] = {90: 0.0}
    assert expand(ec, firm, route)
    assert bank.cash_reserves == 0.0
    assert not bank.active_loans


@pytest.mark.parametrize("route", ("long_term", "infrastructure"))
def test_fully_cash_funded_project_can_operate_without_a_bank(world, route):
    ec, firm, _ = world
    ec.bank = None
    assert expand(ec, firm, route)
    assert firm.bank_loan_remaining == 0.0


@pytest.mark.parametrize("route", ("long_term", "infrastructure"))
@pytest.mark.parametrize("failure", ("empty_slot", "no_unmet"))
def test_cash_cannot_bypass_space_or_demand_gate(world, route, failure):
    ec, firm, bank = world
    if failure == "empty_slot":
        firm.employees.pop()
    else:
        firm.service_unmet_demand_window = [0.0] * 5
    assert not expand(ec, firm, route)
    assert firm.cash_balance == 100_000.0
    assert firm.production_capacity_units == 5.0
    assert not bank.active_loans


def test_funding_reserve_counts_existing_debt_once_and_ignores_paid_off_schedule(world):
    ec, firm, _ = world
    firm.cash_balance = 4000.0
    firm.bank_loan_remaining, firm.bank_loan_payment_per_tick = 1000.0, 20.0
    firm.service_infrastructure_loan_remaining = 500.0
    firm.service_infrastructure_loan_payment_per_tick = 10.0  # Already inside bank 20.
    firm.government_loan_remaining, firm.loan_payment_per_tick = 1000.0, 30.0
    own, _ = ec._service_expansion_funding_quote(firm, 7000.0, .05, 104, 1.0)
    firm.service_infrastructure_loan_payment_per_tick = 0.0
    assert ec._service_expansion_funding_quote(firm, 7000.0, .05, 104, 1.0)[0] == own
    firm.government_loan_remaining = 0.0
    assert ec._service_expansion_funding_quote(firm, 7000.0, .05, 104, 1.0)[0] > own


def test_risk_trait_changes_cash_contribution_through_existing_runway(world):
    ec, firm, _ = world
    firm.cash_balance = 4000.0
    firm.risk_tolerance = .1
    conservative, _ = ec._service_expansion_funding_quote(firm, 7000.0, .05, 104, 1.0)
    firm.risk_tolerance = .9
    aggressive, _ = ec._service_expansion_funding_quote(firm, 7000.0, .05, 104, 1.0)
    assert 0.0 < conservative < aggressive < 7000.0


@pytest.mark.parametrize("route", ("long_term", "infrastructure"))
def test_mixed_project_survives_real_final_installment_and_reconciles_new_claim(world, route):
    from payment_loans import collect_firm_dues, originate_v2

    ec, firm, bank = world
    old = originate_v2(ec, "firm", firm.firm_id, 100.0, .05, 1, "long_term_capital")
    assert old is not None
    firm.cash_balance = 4000.0
    assert expand(ec, firm, route)
    new = next(loan for loan in bank.active_loans if loan is not old)
    assert 0.0 < new["principal"] < (5000.0 if route == "long_term" else 7000.0)
    ec.current_tick += 1
    ec.payment_book = PaymentBook(ec, timing=ec.payment_sequence)
    before = firm.cash_balance, bank.cash_reserves
    paid = collect_firm_dues(ec)
    assert old["remaining"] == pytest.approx(0.0, abs=1e-6)
    assert before[0] - firm.cash_balance == pytest.approx(paid)
    assert bank.cash_reserves - before[1] == pytest.approx(paid)
    assert firm.bank_loan_remaining == pytest.approx(new["remaining"])
    _, _, due = firm._service_pricing_costs()
    assert due == pytest.approx(new["payment_per_tick"])
