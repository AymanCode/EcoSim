"""Affordable orders, from the live planner through named funded settlement."""

import copy

import pytest

from agents import BankAgent
from config import clone_config, use_config
from payment_loans import collect_household_dues, prepare_household_dues
from payment_sectors import PaymentGoodsMarket, payment_deposit_quotes, settle_payment_rent
from payments import PaymentBook


def _scenario(factory, timing, *, cash=0.0, firm_cash=100.0, deposit=0.0, stock=100.0):
    hh = factory.household(
        household_id=1, employer_id=1, wage=100.0, cash_balance=cash,
        bank_deposit=deposit, goods_inventory={}, category_weights={"food": 1.0},
        food_preference=1.0, renting_from_firm_id=None,
    )
    firm = factory.firm(
        firm_id=1, category="Food", price=10.0, inventory_units=stock,
        employees=[1], actual_wages={1: 100.0}, cash_balance=firm_cash,
        ceo_household_id=None, owners=[],
    )
    gov = factory.government(
        cash_balance=0.0, wage_tax_rate=0.0, profit_tax_rate=0.0,
        unemployment_benefit_level=0.0, transfer_budget=0.0,
    )
    economy = factory.economy(households=[hh], firms=[firm], government=gov)
    economy.payment_book = PaymentBook(economy, timing)
    prepare_household_dues(economy)
    return economy, hh, firm


def _plan(economy):
    return economy._batch_plan_consumption(
        {f.good_name: f.price for f in economy.firms},
        economy._build_category_market_snapshot(), economy._build_good_category_lookup(),
        unemployment_rate=0.0, unemployment_benefit=economy.government.get_unemployment_benefit_level(),
    )


def _clear(economy, plans):
    market = PaymentGoodsMarket(economy, plans, economy.firms)
    market.first_pass()
    market.second_pass()
    market.finish()
    return market


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
@pytest.mark.parametrize("cash,stock,bought,unmet", [(0, 10, 0, 0), (20, 10, 2, 0), (50, 2, 2, 3)])
def test_actual_cash_bounds_quote_and_capacity_signal(factory, timing, cash, stock, bought, unmet):
    cfg = clone_config()
    cfg.payment_sequence = timing
    with use_config(cfg):
        e, hh, firm = _scenario(factory, timing, cash=cash, stock=stock)
        _clear(e, {1: {"planned_purchases": {1: 5.0}}})
        assert e.payment_book.receipts[1]["units_sold"] == pytest.approx(bought)
        assert e.food_unmet_demand == pytest.approx(unmet)
        assert e.current_tick_unmet_demand_by_firm.get(1, 0.0) == pytest.approx(unmet)
        assert hh.cash_balance == pytest.approx(cash - 10 * bought)
        assert firm.inventory_units == pytest.approx(stock - bought)
        assert e.payment_book.release_firm_receipts(firm) == pytest.approx(10 * bought)
        assert e.payment_book.clearing_cash == pytest.approx(0)
        assert not e.payment_book.clearing_payables


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
@pytest.mark.parametrize("funded", [0.0, 20.0, 100.0])
def test_planner_zero_opening_cash_uses_only_income_available_at_shopping(factory, timing, funded):
    cfg = clone_config()
    cfg.payment_sequence = timing
    with use_config(cfg):
        e, hh, firm = _scenario(factory, timing, firm_cash=funded)
        plans = _plan(e)
        assert bool(plans[1]["planned_purchases"]) == (timing == "income_first")
        e.payment_book.settle_income({1: 100.0})
        e.payment_book.settle_benefits()
        _clear(e, plans)
        bought = e.payment_book.receipts[1]["units_sold"]
        assert (bought > 0) == (timing == "income_first" and funded > 0)
        assert bought * 10 <= (funded if timing == "income_first" else 0) + 1e-6
        assert e.food_unmet_demand == pytest.approx(0)
        assert e.payment_state["wage_claims"].get((1, 1), 0) == pytest.approx(100 - funded)
        assert e.payment_book.paid_income[1]["gross"] == pytest.approx(funded)
        assert firm.cash_balance == pytest.approx(0)
        cash_before_release = hh.cash_balance
        e.payment_book.release_late_income()
        assert hh.cash_balance - cash_before_release == pytest.approx(funded if timing == "income_late" else 0)
        e.payment_book.release_firm_receipts(firm)
        assert hh.cash_balance + firm.cash_balance == pytest.approx(funded)


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
@pytest.mark.parametrize("bank_cash", [0.0, 7.0, 100.0])
def test_planned_deposits_are_not_cash_until_actual_withdrawal(factory, timing, bank_cash):
    cfg = clone_config()
    cfg.payment_sequence = timing
    with use_config(cfg):
        e, hh, firm = _scenario(factory, timing, firm_cash=0, deposit=100)
        e.bank = BankAgent(cash_reserves=bank_cash, total_deposits=100)
        plans = _plan(e)
        before = plans[1]["planned_purchases"][1]
        assert before > 0
        quotes = payment_deposit_quotes(e, plans, {})
        withdrawn = min(quotes[1], 90, bank_cash)
        e._payment_withdraw_deposits(quotes)
        assert hh.cash_balance == pytest.approx(withdrawn)
        assert hh.bank_deposit == pytest.approx(100 - withdrawn)
        assert e.bank.total_deposits == pytest.approx(hh.bank_deposit)
        _clear(e, plans)
        sold = e.payment_book.receipts[1]["units_sold"]
        assert sold == pytest.approx(min(before, withdrawn / 10))
        assert e.food_unmet_demand == pytest.approx(0)
        assert hh.cash_balance + e.payment_book.clearing_cash + e.bank.cash_reserves == pytest.approx(bank_cash)


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
def test_cached_choices_recheck_cash_and_actual_quote_without_mutating_cache(factory, timing):
    cfg = clone_config()
    cfg.payment_sequence = timing
    with use_config(cfg):
        e, hh, firm = _scenario(factory, timing, cash=100, stock=0)
        plans = _plan(e)
        e._cached_consumption_plans = plans
        cached = copy.deepcopy(plans)
        hh.cash_balance = 5.0
        firm.price = 20.0  # An updated actual quote, without new seller choices.
        _clear(e, e._apply_cached_consumption_plans())
        assert e.food_unmet_demand == pytest.approx(0.25)
        assert hh.cash_balance == 5.0  # Failed orders cannot reserve or spend money.
        assert e._cached_consumption_plans == cached
        hh.cash_balance = 0
        e.food_unmet_demand = 0
        e.current_tick_unmet_demand_by_firm = {}
        _clear(e, e._apply_cached_consumption_plans())
        assert e.food_unmet_demand == 0
        assert not e.current_tick_unmet_demand_by_firm


@pytest.mark.parametrize("min_food_first", [False, True])
@pytest.mark.parametrize("budget", [0.0, 1.0, 35.0, 500.0])
def test_real_category_allocation_never_exceeds_declared_budget(factory, min_food_first, budget):
    cfg = clone_config()
    cfg.payment_sequence = "legacy"
    with use_config(cfg):
        hh = factory.household(category_weights={"food": 0.3, "services": 0.4, "housing": 0.3})
        firms = [factory.firm(firm_id=i + 1, category=cat, price=price)
                 for i, (cat, price) in enumerate([
                     ("Food", 7), ("Food", 17), ("Services", 12), ("Services", 40), ("Housing", 30)])]
        e = factory.economy(households=[hh], firms=firms)
        # Both paths use the same bounded seller allocator; settled_income selects Food-first.
        plans = e._batch_plan_consumption({}, e._build_category_market_snapshot(),
                                          budgets=[budget], settled_income=min_food_first)
        total = sum(e.firm_lookup[fid].price * qty for fid, qty in plans[hh.household_id]["planned_purchases"].items())
        assert 0 <= total <= budget + 1e-8


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
@pytest.mark.parametrize("mode", [False, True])
def test_public_step_real_planner_preserves_income_timing_and_hardship(factory, monkeypatch, timing, mode):
    cfg = clone_config()
    cfg.payment_sequence = timing
    with use_config(cfg):
        e, hh, firm = _scenario(factory, timing, firm_cash=1000)
        e.current_tick = 5
        e.warmup_ticks = 100
        e.performance_mode = mode
        e.configure_stabilizers(households=False, firms=False, government=False)
        monkeypatch.setattr(e, "_run_labor_matching", lambda *_: (
            {1: {"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}}},
            {1: {"employer_id": 1, "wage": 100.0, "employer_category": "Food"}},
        ))
        monkeypatch.setattr(e, "_maybe_create_new_firms", lambda: 0)
        monkeypatch.setattr(e, "_enqueue_healthcare_requests", lambda: None)
        health_before = hh.health
        e.step()
        assert (hh.last_food_units > 0) == (timing == "income_first")
        assert e.food_unmet_demand == pytest.approx(0)
        assert e.payment_book.paid_income[1]["gross"] == pytest.approx(100)
        assert e.payment_book.clearing_cash == pytest.approx(0, abs=1e-6)
        assert not e.payment_book.clearing_payables
        assert not e.payment_book.late_income
        if timing == "income_late" and not mode:
            assert hh.food_consumed_this_tick < hh.min_food_per_tick
            assert hh.health < health_before
        # Tick 6 reuses choices in performance mode, while money is checked
        # again. Depleting the payer cannot turn a cached intention into demand.
        hh.cash_balance = 0
        firm.cash_balance = 0
        cached = copy.deepcopy(e._cached_consumption_plans)
        e.step()
        assert hh.last_food_units == 0
        assert e.food_unmet_demand == 0
        assert not e.current_tick_unmet_demand_by_firm
        if mode:
            assert e._cached_consumption_plans == cached


def test_forecast_income_lifts_the_early_ceiling_but_is_not_drawn_as_savings(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.healthcare_food_first_reserve = False
    with use_config(cfg):
        e, hh, _ = _scenario(factory, "income_first", cash=1000)
        hh.spending_tendency = hh.frugality = 1
        hh.savings_drawdown_rate = 0.05
        budget = e._household_consumption_budgets(0, 0)[0]
        expected = 100 * max(0.70, cfg.households.mpc_wage * (1 - 0.3 * 0.05)) + 1000 * 0.05
        assert budget == pytest.approx(expected)
        pressure = e.payment_book.obligation_pressure[1]
        assert pressure["estimated_discretionary_liquidity"] == pytest.approx(1100)
        assert pressure["estimated_savings_liquidity"] == pytest.approx(1000)


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
@pytest.mark.parametrize("funded", [0, 20])
def test_planner_benefit_level_is_not_a_funded_transfer(factory, timing, funded):
    cfg = clone_config()
    cfg.payment_sequence = timing
    with use_config(cfg):
        e, hh, _ = _scenario(factory, timing, firm_cash=0)
        hh.employer_id = None
        e.firms[0].employees = []
        e.government.unemployment_benefit_level = 100
        e.government.cash_balance = funded
        e.payment_state["restrictions"]["B"] = funded
        plans = _plan(e)
        assert bool(plans[1]["planned_purchases"]) == (timing == "income_first")
        e.payment_book.settle_income({1: 0})
        e.payment_book.settle_benefits()
        _clear(e, plans)
        sold = e.payment_book.receipts[1]["units_sold"]
        assert (sold > 0) == (timing == "income_first" and funded > 0)
        assert sold * 10 <= (funded if timing == "income_first" else 0) + 1e-6
        assert e.food_unmet_demand == 0
        assert e.payment_book.paid_income[1]["benefit"] == funded
        assert e.government.cash_balance == 0


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
def test_planner_service_quote_floor_rechecks_funding_before_quantity(factory, timing):
    cfg = clone_config()
    cfg.payment_sequence = timing
    with use_config(cfg):
        e, hh, firm = _scenario(factory, timing, cash=20)
        hh.category_weights = {"services": 1.0}
        firm.good_category = "Services"
        firm.good_name = "ServicesFirm"
        firm.markup = 0.5
        firm.last_units_produced = 2
        plans = _plan(e)
        wanted = plans[1]["planned_purchases"][1]
        assert wanted > 20 / 75
        _clear(e, plans)
        assert firm.price == pytest.approx(75)  # (100 payroll / 2 current units) * 1.5
        assert hh.services_consumed_this_tick == pytest.approx(20 / 75)
        assert hh.cash_balance == pytest.approx(0)
        assert e.services_unmet_demand == 0
        assert not e.services_unmet_demand_by_firm


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
def test_real_planned_basket_shrinks_after_subsidy_and_cash_exhaustion(factory, timing):
    cfg = clone_config()
    cfg.payment_sequence = timing
    with use_config(cfg):
        e, hh, firm = _scenario(factory, timing, cash=100)
        plans = _plan(e)
        assert plans[1]["planned_purchases"][1] > 2.5
        hh.cash_balance = 20
        e.government.cash_balance = 5
        e.government.sector_subsidy_target = "food"
        e.government._sector_subsidy_rate = 0.5
        e.payment_state["restrictions"]["G"] = 5
        e.sector_subsidy_remaining_this_tick = 5
        _clear(e, plans)
        assert e.payment_book.receipts[1] == pytest.approx({"units_sold": 2.5, "revenue": 25})
        assert e.food_unmet_demand == 0
        assert hh.cash_balance == pytest.approx(0)
        assert e.government.cash_balance == pytest.approx(0)
        assert e.payment_state["restrictions"]["G"] == pytest.approx(0)
        assert e.payment_book.release_firm_receipts(firm) == pytest.approx(25)
        assert e.payment_book.clearing_cash == pytest.approx(0)


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
def test_stockout_cannot_reserve_funds_needed_for_real_rent_and_debt(factory, timing):
    cfg = clone_config()
    cfg.payment_sequence = timing
    with use_config(cfg):
        e, hh, food = _scenario(factory, timing, cash=100, stock=0)
        landlord = factory.firm(firm_id=2, category="Housing", price=40,
                                current_tenants=[1], cash_balance=0)
        e.firms.append(landlord)
        hh.renting_from_firm_id = 2
        hh.monthly_rent = 40
        e.bank = BankAgent(cash_reserves=1000)
        claim = e.bank.originate_loan("household", 1, 60, 0, 10)
        claim["subtype"] = "consumption"
        claim["payment_per_tick"] = 60
        hh.consumption_loan_remaining = 60
        e.payment_book = PaymentBook(e, timing)
        prepare_household_dues(e)
        # Pre-plan has income_first income capacity; late has no discretionary
        # cash after its indexed obligations. Neither can reserve real money.
        plans = _plan(e)
        market = PaymentGoodsMarket(e, plans, e.firms)
        market.first_pass()
        assert hh.cash_balance == 100
        settle_payment_rent(e)
        assert landlord.cash_balance == pytest.approx(40)
        assert collect_household_dues(e) == pytest.approx(60)
        assert claim["remaining"] == pytest.approx(0)
        assert hh.consumption_loan_remaining == pytest.approx(0)
        assert e.bank.cash_reserves == pytest.approx(1000)
        market.second_pass()
        market.finish()
        assert hh.cash_balance == pytest.approx(0)
        assert e.food_unmet_demand == 0
        assert e.payment_book.clearing_cash == 0
