"""Dividend credits are spent as income at the next computed budget only."""
import pytest

from config import clone_config, use_config
from economy import _TickScratch
from payment_loans import prepare_household_dues
from payments import PaymentBook


@pytest.fixture(autouse=True)
def _income_first_sequence():
    """Every test runs on income_first; legacy is not tested here."""
    config = clone_config()
    config.payment_sequence = "income_first"
    with use_config(config):
        yield


def _world(factory):
    cfg = clone_config()
    cfg.households.healthcare_food_first_reserve = False
    cfg.firms.working_capital_enabled = False
    with use_config(cfg):
        household = factory.household(
            household_id=1, employer_id=None, wage=0, cash_balance=0, bank_deposit=0,
            min_food_per_tick=2, renting_from_firm_id=None, spending_tendency=1, frugality=1,
        )
        food = factory.firm(firm_id=1, category="Food", price=10, cash_balance=0)
        housing = factory.firm(firm_id=2, category="Housing", price=10)
        government = factory.government(cash_balance=0, wage_tax_rate=0, unemployment_benefit_level=0)
        economy = factory.economy(households=[household], firms=[food, housing], government=government)
        economy.government.unemployment_benefit_level = 0
        economy.current_tick = 5
        economy.payment_book = PaymentBook(economy, timing="income_first")
        prepare_household_dues(economy)
    return cfg, economy, household, food


def _settle(economy):
    economy.payment_state["restrictions"]["B"] = 0
    economy.payment_book.settle_income({h.household_id: 0 for h in economy.households})
    economy.payment_book.settle_benefits()


def _budget(economy):
    return economy._household_consumption_budgets(0, 0, settled_income=True)[0]


def test_dividends_survive_tick_reset_and_reach_one_budget(factory):
    cfg, ec, hh, firm = _world(factory)
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
    # The $100 dividend is subject to a 40% dividend MPC.
    assert first == pytest.approx(40)
    assert second == 0


def test_payment_cached_plan_does_not_consume_unplanned_dividends(factory):
    cfg, ec, hh, firm = _world(factory)
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
