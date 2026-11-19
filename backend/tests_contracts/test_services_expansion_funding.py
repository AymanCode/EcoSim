"""Expansion funding preserves liquidity, actual claims and full project payment."""

from types import SimpleNamespace

import pytest

from agents import BankAgent
from config import clone_config, use_config
from economy import Economy
from payment_loans import prepare_household_dues
from payment_sectors import PaymentGoodsMarket
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


@pytest.fixture
def reroute_market(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    cfg.households.stockout_substitution_share = 1.0
    with use_config(cfg):
        household = factory.household(household_id=1)
        origin = factory.firm(firm_id=89, category="Services", good_name="Origin",
                              last_units_produced=0.0, price=20.0)
        receiver = factory.firm(
            firm_id=90, category="Services", good_name="Receiver", is_baseline=False,
            production_capacity_units=5.0, units_per_worker=4.0, wage_offer=20.0,
            employees=list(range(1, 6)), actual_wages={hid: 20.0 for hid in range(1, 6)},
            last_units_produced=20.0, price=20.0, service_staffing_target=5,
            owners=[], ceo_household_id=None,
        )
        # Hold the late infrastructure route at its existing active-loan gate
        # so five settlements reach the opening long-term decision.
        receiver.service_infrastructure_loan_remaining = 1.0
        bank = BankAgent(cash_reserves=100_000.0)
        ec = Economy(households=[household], firms=[origin, receiver],
                     government=factory.government(), bank=bank)
        ec.payment_state["prior_settled_firm_operating_cashflow"] = {90: 1000.0}

        def settle(tick, *, inbound=0.0, cash=900.0):
            ec.current_tick = receiver.age_in_ticks = tick
            ec.services_unmet_demand_by_firm.clear()
            household.cash_balance = cash
            ec.payment_book = PaymentBook(ec, timing="income_first")
            orders = {origin.firm_id: inbound, receiver.firm_id: 25.0}
            market = PaymentGoodsMarket(ec, {1: {"planned_purchases": orders}}, ec.firms)
            market.first_pass()
            prepare_household_dues(ec)
            ec._phase_misc_and_healthcare(SimpleNamespace(
                payment_arm=True, goods_market=market, per_firm_sales=market.sales,
            ))
            for firm in ec.firms:
                ec.payment_book.release_firm_receipts(firm)
            return receiver.service_demand_observation

        yield ec, receiver, bank, settle


@pytest.mark.parametrize(
    "inbound,buyer_cash,firm_cash,bank_cash,lost,expected_cost,funding",
    [
        (20, 900, 100_000, 100_000, 25, 5000, "cash"),
        (20, 780, 100_000, 100_000, 19, 5000, "cash"),  # Exactly 95%.
        (10, 580, 100_000, 100_000, 9, 5000, "cash"),  # Direct sales plus lost orders reach 95%.
        (0, 900, 100_000, 100_000, 5, 5000, "cash"),  # Latest active week has zero reroutes.
        (20, 480, 100_000, 100_000, 4, 500, "cash"),
        (20, 480, 850, 100_000, 4, 500, "mixed"),
        (20, 480, 100, 100_000, 4, 500, "loan"),
        (20, 480, 100, 1000, 4, 500, "loan"),  # Only the smaller project fits the bank's reserves.
        (20, 780, 100, 1000, 19, 5000, "denied"),
        (20, 480, 850, 0, 4, 500, "denied"),
    ],
)
def test_opening_quote_uses_settled_funded_orders_and_books_actual_cost(
    reroute_market, inbound, buyer_cash, firm_cash, bank_cash, lost, expected_cost, funding,
):
    ec, firm, bank, settle = reroute_market
    for tick in range(35, 39):
        settle(tick)
    observation = settle(39, inbound=inbound, cash=buyer_cash)
    assert observation.tick == 39
    assert observation.sold_units == observation.output_capacity == 20
    assert observation.funded_lost_units == pytest.approx(lost)
    assert observation.rerouted_units_window == pytest.approx((0, 0, 0, 0, inbound))
    ec.current_tick = 40
    firm.cash_balance, bank.cash_reserves = firm_cash, bank_cash
    before_slots, before_stock = firm.production_capacity_units, firm.capital_stock
    before_cooldown = firm.last_long_term_loan_tick
    household = ec.households[0]
    before_household_cash = household.cash_balance
    granted = expand(ec, firm, "long_term")
    assert granted is (funding != "denied")
    quote = firm.decision_diagnostics["service_long_term_quote"]
    assert (quote["tick"], quote["ordinary_cost"], quote["project_cost"], quote["funded"]) == (
        40, 5000, expected_cost, granted,
    )
    assert quote["observation"]["tick"] == 39
    own, loan = firm_cash - firm.cash_balance, bank_cash - bank.cash_reserves
    if funding == "denied":
        assert (own, loan, firm.bank_loan_remaining) == (0, 0, 0)
        assert (firm.production_capacity_units, firm.capital_stock) == (before_slots, before_stock)
        assert firm.last_long_term_loan_tick == before_cooldown
        assert not bank.active_loans
        assert not ec.payment_state.get("capital_routes")
        assert firm.capital_investment_this_tick == 0
        return
    assert own + loan == pytest.approx(expected_cost)
    if funding == "cash":
        assert loan == 0
    elif funding == "mixed":
        assert 0 < own < expected_cost
        assert 0 < loan < expected_cost
    else:
        assert own == 0
    assert sum(claim["principal"] for claim in bank.active_loans) == pytest.approx(loan)
    assert firm.bank_loan_remaining == pytest.approx(loan)
    assert firm.total_long_term_loans_received == pytest.approx(loan)
    assert firm.production_capacity_units - before_slots == pytest.approx(expected_cost / 500)
    assert firm.capital_stock - before_stock == pytest.approx(expected_cost / 500)
    assert firm.last_long_term_loan_tick == 40
    assert sum(row["amount"] for row in ec.payment_state["capital_routes"]) == expected_cost
    ec._recycle_capital_investment()
    ec._recycle_capital_investment()
    assert household.cash_balance - before_household_cash == pytest.approx(expected_cost)


@pytest.mark.parametrize("timing", ["entrant", "gap", "stale", "fallback_off"])
def test_long_term_quote_requires_complete_active_prior_window(reroute_market, timing):
    ec, firm, _, settle = reroute_market
    for tick in range(35, 39):
        settle(tick)
    if timing == "entrant":
        del firm.service_demand_observation  # Simulate a snapshot without the new slot.
    final_tick = 40 if timing == "gap" else 39
    observation = settle(final_tick, inbound=20, cash=480)
    ec._record_service_demand_observation(firm, sold_units=0)
    assert firm.service_demand_observation is observation
    assert len(observation.rerouted_units_window) == (1 if timing in {"entrant", "gap"} else 5)
    if timing == "fallback_off":
        ec.config.households.stockout_substitution_share = 0
    ec.current_tick = final_tick + (2 if timing == "stale" else 1)
    firm.cash_balance = 100_000
    assert expand(ec, firm, "long_term")
    quote = firm.decision_diagnostics["service_long_term_quote"]
    assert quote["project_cost"] == quote["ordinary_cost"] == 5000
    if timing in {"stale", "fallback_off"}:
        assert quote["observation"] is None
    if timing == "fallback_off":
        assert settle(40) is None
        ec.config.households.stockout_substitution_share = 1.0
        assert settle(41).rerouted_units_window == (0.0,)


@pytest.mark.parametrize("steady_inbound,cost", [(5, 5000), (20, 5000), (4, 500)])
def test_typical_reroutes_support_the_ordinary_project(reroute_market, steady_inbound, cost):
    ec, firm, _, settle = reroute_market
    for tick in range(35, 39):
        settle(tick, inbound=steady_inbound)
    # No direct sales, but 14 funded lost orders plus typical reroutes.
    settle(39, inbound=20, cash=680)
    ec.current_tick = 40
    firm.cash_balance = 100_000
    assert expand(ec, firm, "long_term")
    assert firm.decision_diagnostics["service_long_term_quote"]["project_cost"] == cost
