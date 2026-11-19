"""Dividend credits are spent as income at the next computed budget only."""
import pytest

from config import HouseholdBehaviorConfig, clone_config, use_config
from economy import _TickScratch
from tests_contracts.test_households_savings_goal import _budget, _settle, _world


def test_new_flags_default_off():
    cfg = HouseholdBehaviorConfig()
    assert not cfg.money_lines_in_weeks
    assert not cfg.savings_goal
    assert not cfg.fix_dividend_timing


@pytest.mark.parametrize("mode", ["fix_dividend_timing", "savings_goal"])
def test_dividends_survive_tick_reset_and_reach_one_budget(factory, mode):
    cfg, ec, hh, firm = _world(factory, cash=0, funded=0, employed=False)
    cfg.households.savings_goal = mode == "savings_goal"
    cfg.households.fix_dividend_timing = mode == "fix_dividend_timing"
    hh.savings_drawdown_rate = 0
    with use_config(cfg):
        assert firm._credit_dividend_income([1], {1: hh}, 20) == 20
        assert firm._credit_dividend_income([1], {1: hh}, 80) == 80
        hh.reset_tick_ledger()
        assert hh.last_dividend_income == 0 and hh.dividends_since_last_plan == 100
        assert "dividends_since_last_plan" not in hh.to_dict()
        _settle(ec)
        first = _budget(ec)
        assert hh.dividends_since_last_plan == 0
        second = _budget(ec)
    if mode == "fix_dividend_timing":
        assert first == pytest.approx(40)
        assert second == 0
    else:
        assert first == pytest.approx(100)
        assert second == pytest.approx(20)  # minimum-food floor, no second dividend


def test_disabled_flag_does_not_read_or_clear_pending_dividends(factory):
    cfg, ec, hh, firm = _world(factory, cash=0, funded=0, employed=False)
    cfg.households.savings_goal = False
    hh.savings_drawdown_rate = 0
    with use_config(cfg):
        firm._credit_dividend_income([1], {1: hh}, 100)
        hh.reset_tick_ledger()
        _settle(ec)
        assert _budget(ec) == 0
        assert hh.dividends_since_last_plan == 100


def test_payment_cached_plan_does_not_consume_unplanned_dividends(factory):
    cfg, ec, hh, firm = _world(factory, cash=0, funded=0, employed=False)
    cfg.households.savings_goal = False
    cfg.households.fix_dividend_timing = True
    hh.savings_drawdown_rate = 0
    with use_config(cfg):
        firm._credit_dividend_income([1], {1: hh}, 100)
        hh.reset_tick_ledger()
        _settle(ec)
        lookup, snapshot, _, _ = ec._build_firm_market_views()
        tick = _TickScratch(payment_arm=True, good_category_lookup=lookup,
                            category_market_snapshot=snapshot, unemployment_rate=0, gov_benefit=0)
        ec.performance_mode = True
        ec._cached_consumption_plans = {1: {"budget": 0, "planned_purchases": {}}}
        ec.current_tick = 4
        ec._plan_payment_consumption(tick, settled_income=True)
        assert hh.dividends_since_last_plan == 100
        ec.current_tick = 5
        ec._plan_payment_consumption(tick, settled_income=True)
        assert tick.household_consumption_plans[1]["budget"] == pytest.approx(40)
        assert hh.dividends_since_last_plan == 0


def test_legacy_cached_basket_refreshes_budget_and_consumes_dividend(factory):
    cfg = clone_config()
    cfg.payment_sequence = "legacy"
    cfg.households.fix_dividend_timing = True
    cfg.households.healthcare_food_first_reserve = False
    with use_config(cfg):
        hh = factory.household(household_id=1, employer_id=None, cash_balance=0,
                               spending_tendency=1, frugality=1)
        hh.savings_drawdown_rate = 0
        firm = factory.firm(firm_id=1, category="Food", price=10)
        ec = factory.economy(households=[hh], firms=[firm])
        firm._credit_dividend_income([1], {1: hh}, 100)
        hh.reset_tick_ledger()
        lookup, snapshot, _, _ = ec._build_firm_market_views()
        ec.performance_mode = True
        ec.current_tick = 1
        ec._cached_consumption_plans = {1: {"budget": 40, "planned_purchases": {1: 1}}}
        plans = ec._plan_legacy_consumption_after_income({}, snapshot, lookup, 0, 0)
        assert plans[1]["budget"] == pytest.approx(40)
        assert hh.dividends_since_last_plan == 0
        plans = ec._plan_legacy_consumption_after_income({}, snapshot, lookup, 0, 0)
        assert plans[1]["budget"] == 0
