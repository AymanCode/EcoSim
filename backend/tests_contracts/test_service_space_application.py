"""Isolated checkout, observation and funding checks for the Services screen."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents import BankAgent, ServiceSpaceObservation
from config import clone_config, use_config
from economy import Economy
from payment_loans import can_underwrite, originate_v2, prepare_household_dues, quoted_annual_rate, v2_payment
from payment_sectors import PaymentGoodsMarket
from payments import PaymentBook


@pytest.fixture
def config():
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.firms.expected_skill_premium = 0.0
    with use_config(cfg):
        yield cfg


@pytest.fixture
def world(factory, config):
    hh = factory.household(household_id=1)
    firm = factory.firm(
        firm_id=90, category="Services", is_baseline=False, production_capacity_units=4.5,
        last_units_produced=20.0, last_units_sold=20.0, employees=[1, 2, 3, 4],
        wage_offer=20.0, price=10.0, cash_balance=100.0,
        last_revenue=1000.0, revenue_ema=1000.0,
    )
    firm.units_per_worker = 5.0
    ec = Economy(households=[hh], firms=[firm], government=factory.government(),
                 bank=BankAgent(cash_reserves=100_000))
    ec.current_tick = 40
    ec.payment_book = PaymentBook(ec, timing="income_first")
    firm.service_full_utilization_streak = 5
    firm.service_unmet_demand_window = [5, 5, 5, 2, 0]
    firm.service_space_history = [
        ServiceSpaceObservation(tick, 4, 20, 20, inbound, lost, price, 1)
        for tick, inbound, lost, price in zip(
            range(36, 41), (0, 0, 0, 5, 5), firm.service_unmet_demand_window, (15, 15, 15, 5, 5),
        )
    ]
    return ec, firm


def test_fractional_quote_materiality_refill_and_break_even(world, config):
    ec, firm = world
    screen = ec._screen_service_space_application
    result = screen(firm, "service_infrastructure", 7000, 0.5)
    apply, trace = result
    assert apply and trace["k"] == 1 and trace["phase"] == "late"
    assert trace["observation_ticks"] == [36, 37, 38, 39, 40]
    assert trace["qualification_after_removal"] is False
    assert trace["weekly_contributions"] == [0, 0, 0, -25, -25]
    assert trace["median_contribution"] == 0
    assert trace["rows"][3]["X"] == 5
    assert trace["rows"][3]["F"] == 2
    assert trace["rows"][3]["adjusted_sales"] == 17
    assert trace["rows"][3]["adjusted_lost_orders"] == 0
    assert screen(deepcopy(firm), "service_infrastructure", 7000, 0.5) == result
    assert screen(firm, "service_infrastructure", 7000, 0.49)[1]["k"] == 0
    ec.current_tick += 1
    assert screen(firm, "long_term_capital", 5000, 0.5)[1]["weekly_contributions"] == trace["weekly_contributions"]
    assert screen(firm, "service_infrastructure", 7000, 0.5)[1]["reason"] == "stale_or_nonconsecutive_history"
    config.firms.expected_skill_premium = 0.2
    firm.policy_minimum_wage = 25
    apply, trace = screen(firm, "long_term_capital", 5000, 0.5)
    assert not apply and trace["w"] == 30 and trace["median_contribution"] == -10


@pytest.mark.parametrize("inbound", [0, 4])
def test_steady_books_keep_ordinary_path(world, inbound):
    ec, firm = world
    firm.service_space_history = [replace(row, R=inbound) for row in firm.service_space_history]
    apply, trace = ec._screen_service_space_application(firm, "service_infrastructure", 7000, 1)
    assert apply and trace["qualification_after_removal"] is True
    assert trace["weekly_contributions"] is None
    assert all(row["X"] == 0 for row in trace["rows"])


def test_refill_can_remove_lost_order_qualification_at_95_percent(world):
    ec, firm = world
    firm.service_space_history = [
        replace(row, R=inbound, L=lost)
        for row, inbound, lost in zip(firm.service_space_history, (0, 0, 0, 0, 5), (5, 0, 0, 0, 4))
    ]
    apply, trace = ec._screen_service_space_application(firm, "service_infrastructure", 7000, 1)
    assert all(row["adjusted_sales"] / row["Q"] >= 0.95 for row in trace["rows"])
    assert trace["qualification_after_removal"] is False
    assert not apply


@pytest.mark.parametrize(("change", "reason"), [
    ("baseline_flag", "baseline_firm"),
    ("baseline_registry", "baseline_firm"),
    ("other_sector", "outside_generic_services"),
    ("other_places", "installed_places_changed"),
    ("excess_inbound", "invalid_history"),
    ("gap", "stale_or_nonconsecutive_history"),
    ("missing", "insufficient_history"),
])
def test_unusable_evidence_preserves_ordinary_decision(world, change, reason):
    ec, firm = world
    if change == "baseline_flag":
        firm.is_baseline = True
    elif change == "baseline_registry":
        ec.government.register_baseline_firm("services", firm.firm_id)
    elif change == "other_sector":
        firm.good_category = "Food"
    elif change == "other_places":
        firm.service_space_history[1] = replace(firm.service_space_history[1], installed_places=5)
    elif change == "excess_inbound":
        firm.service_space_history[1] = replace(firm.service_space_history[1], R=21)
    elif change == "gap":
        firm.service_space_history[1] = replace(firm.service_space_history[1], tick=35)
    else:
        del firm.service_space_history
    apply, trace = ec._screen_service_space_application(firm, "service_infrastructure", 7000, 1)
    assert apply and trace["reason"] == reason


def test_observation_dedup_gap_install_and_unqualified_resets(world):
    ec, firm = world
    firm.last_tick_operating_cash_cost_nonwage = 10

    def observe(sold=20):
        firm.consider_service_infrastructure_upgrade(
            ec, sold, current_paid_inbound_units=0, current_net_goods_revenue=100,
        )

    for tick in (41, 42, 44):
        ec.current_tick = tick
        firm.age_in_ticks += 1
        observe()
        observe()
    assert firm.service_space_history == [ServiceSpaceObservation(44, 4, 20, 20, 0, 0, 5, 0.5)]
    for cause in ("understaffed", "no_output", "low_sell_through", "installation"):
        ec.current_tick += 1
        firm.age_in_ticks += 1
        if cause == "understaffed":
            firm.employees.pop()
        elif cause == "no_output":
            firm.last_units_produced = 0
        elif cause == "installation":
            firm._add_service_worker_slots(0.5)
            assert firm.service_unmet_demand_window == []
        if cause != "installation":
            observe(18 if cause == "low_sell_through" else 20)
        assert firm.service_space_history == []
        if cause == "installation":
            break
        firm.employees = [1, 2, 3, 4]
        firm.last_units_produced = 20
        ec.current_tick += 1
        firm.age_in_ticks += 1
        observe()
        assert [row.tick for row in firm.service_space_history] == [ec.current_tick]


@pytest.mark.parametrize("over_ceiling", [False, True])
def test_checkout_observation_prices_only_goods_receipts_at_the_levy_rate(world, config, over_ceiling):
    ec, firm = world
    hh = ec.households[0]
    hh.cash_balance = 5000
    firm.price = config.market.price_ceiling + over_ceiling
    firm.last_tick_operating_cash_cost_nonwage = 10
    firm.service_full_utilization_streak = 0
    firm.service_unmet_demand_window.clear()
    firm.service_space_history.clear()
    ec.payment_book.rent_receipts[firm.firm_id] = 100
    ec.payment_state["services_pending_receipts"] = {firm.firm_id: 200}
    prepare_household_dues(ec)
    market = PaymentGoodsMarket(ec, {hh.household_id: {"planned_purchases": {firm.firm_id: 20}}}, ec.firms)
    market.first_pass()
    tick = SimpleNamespace(payment_arm=True, goods_market=market, per_firm_sales=market.sales)
    ec._phase_misc_and_healthcare(tick)
    [row] = firm.service_space_history
    levy = config.market.price_ceiling_tax_rate if over_ceiling else 0
    assert row.p == pytest.approx(firm.price * (1 - levy))
    assert (row.Q, row.S, row.R, row.L, row.c) == (20, 20, 0, 0, 0.5)
    [fiscal] = ec._build_firm_tax_snapshots(tick.per_firm_sales)
    assert fiscal["price_ceiling_tax"] == pytest.approx(20 * firm.price * levy)


@pytest.mark.parametrize("route", ["long_term_capital", "service_infrastructure"])
def test_wait_keeps_evidence_and_skips_funding(world, monkeypatch, route):
    ec, firm = world
    firm.service_space_history = [replace(row, c=2) for row in firm.service_space_history]
    before_history, before_cooldown = deepcopy(firm.service_space_history), firm.last_long_term_loan_tick
    ordinary_screen = ec._screen_service_space_application
    decisions = []

    def capture(*args):
        decision = ordinary_screen(*args)
        decisions.append(decision)
        return decision

    monkeypatch.setattr(ec, "_screen_service_space_application", capture)
    monkeypatch.setattr(ec, "_fund_service_expansion", lambda *args: pytest.fail("wait reached funding"))
    if route == "long_term_capital":
        ec.current_tick += 1
        assert not ec._maybe_offer_long_term_capital_loan(firm, SimpleNamespace(sell_through_rate=1), 0.5, 100)
    else:
        firm.needs_service_infrastructure_loan = True
        firm.service_infrastructure_loan_amount = 7000
        ec._offer_service_infrastructure_loans()
        assert not firm.needs_service_infrastructure_loan
        assert firm.service_infrastructure_loan_amount == 0
    [(apply, trace)] = decisions
    assert not apply and trace["route"] == route and trace["median_contribution"] < 0
    assert firm.service_space_history == before_history
    assert firm.last_long_term_loan_tick == before_cooldown
    assert firm.production_capacity_units == 4.5


def test_pass_can_still_fail_combined_ordinary_coverage(world, config):
    ec, firm = world
    ec.current_tick += 1
    firm.service_space_history = [replace(row, R=0) for row in firm.service_space_history]
    prior = ec.payment_state["prior_settled_firm_operating_cashflow"] = {firm.firm_id: 1000}
    claim = originate_v2(ec, "firm", firm.firm_id, 7000, 0.05, 104, "service_infrastructure")
    assert claim is not None
    cfg = config.firms
    score = ec.bank.get_firm_credit_score(firm.firm_id)
    rate = quoted_annual_rate(ec, cfg.long_term_capital_annual_rate + (1 - score) * 0.02)
    due = v2_payment(cfg.long_term_capital_min_amount, rate, cfg.long_term_capital_term_ticks,
                     config.time.ticks_per_year)
    prior[firm.firm_id] = max(due, claim["payment_per_tick"]) / config.payment_debt_service_share
    assert due <= prior[firm.firm_id] * config.payment_debt_service_share + 1e-9
    assert not can_underwrite(ec, "firm", firm.firm_id, due)
    before = firm.cash_balance, ec.bank.cash_reserves, firm.production_capacity_units, firm.last_long_term_loan_tick
    assert not ec._maybe_offer_long_term_capital_loan(firm, SimpleNamespace(sell_through_rate=1), 0.5, 100)
    assert (firm.cash_balance, ec.bank.cash_reserves, firm.production_capacity_units,
            firm.last_long_term_loan_tick) == before
    assert len(ec.bank.active_loans) == 1
    assert not ec.payment_state.get("capital_routes")
