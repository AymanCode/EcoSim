"""Dividend credits are spent as income at the next computed budget only."""
import pytest

from config import HouseholdBehaviorConfig, clone_config, use_config
from economy import _TickScratch
from tests_contracts.test_households_savings_goal import _budget, _settle, _world


@pytest.fixture(autouse=True)
def _income_first_sequence():
    """Every test runs on income_first; legacy is not tested here."""
    config = clone_config()
    config.payment_sequence = "income_first"
    with use_config(config):
        yield


def test_household_experiment_defaults():
    cfg = HouseholdBehaviorConfig()
    assert cfg.wellbeing_targets is True
    assert cfg.fix_wellbeing_cash_snapshot is True
    assert cfg.fix_food_tracker_lag is True
    assert cfg.fix_dividend_timing is True
    assert cfg.money_lines_in_weeks is True
    assert cfg.job_choices is True
    assert cfg.fix_spending_leak is False
    assert cfg.savings_goal is False


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
    # fix_dividend_timing: exercise the original dividend field.
    cfg.households.fix_dividend_timing = False
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
