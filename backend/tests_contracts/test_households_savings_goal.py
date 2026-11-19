"""Savings goals use funded income, liquid savings, and observed job risk."""
import numpy as np
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


def _world(factory, *, cash=0, funded=100, employed=True, benefit=0, timing="income_first"):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.households.savings_goal = True
    cfg.households.healthcare_food_first_reserve = False
    cfg.firms.working_capital_enabled = False
    with use_config(cfg):
        hh = factory.household(household_id=1, employer_id=1 if employed else None,
                               wage=100 if employed else 0, cash_balance=cash, bank_deposit=0,
                               min_food_per_tick=2, saving_tendency=0.5, renting_from_firm_id=None,
                               spending_tendency=1, frugality=1)
        food = factory.firm(firm_id=1, category="Food", price=10, cash_balance=funded,
                            employees=[1] if employed else [], actual_wages={1: 100} if employed else {})
        housing = factory.firm(firm_id=2, category="Housing", price=10)
        gov = factory.government(cash_balance=benefit, wage_tax_rate=0, unemployment_benefit_level=benefit)
        ec = factory.economy(households=[hh], firms=[food, housing], government=gov)
        ec.government.unemployment_benefit_level = benefit
        ec.current_tick = 5
        ec.savings_goal_unemployment_ema = 0.05
        ec.payment_book = PaymentBook(ec, timing=timing)
        prepare_household_dues(ec)
    return cfg, ec, hh, food


def _settle(ec, *, benefit=0):
    ec.payment_state["restrictions"]["B"] = benefit
    ec.payment_book.settle_income({h.household_id: h.wage if h.is_employed else 0 for h in ec.households})
    ec.payment_book.settle_benefits()


def _budget(ec):
    return ec._household_consumption_budgets(0, 0, settled_income=True)[0]


@pytest.mark.parametrize("opening,expected", [(300, 102.4), (100, 98.4)])
def test_employed_above_and_below_savings_target(factory, opening, expected):
    cfg, ec, _, _ = _world(factory, cash=opening)
    with use_config(cfg):
        _settle(ec)
        # E=2*10+10=30; target=6*(0.5+0.5)*30=180.
        assert _budget(ec) == pytest.approx(expected)


def test_unemployed_draws_cushion_without_rebuilding(factory):
    cfg, ec, _, _ = _world(factory, cash=100, funded=0, employed=False, benefit=100)
    with use_config(cfg):
        _settle(ec, benefit=100)
        assert _budget(ec) == pytest.approx(102)


@pytest.mark.parametrize("cash,rate,expected", [(100, 0.02, 20), (10, 0.02, 10), (10, 2, 10)])
def test_food_floor_and_liquidity_bounds(factory, cash, rate, expected):
    cfg, ec, _, _ = _world(factory, cash=cash, funded=0, employed=(rate != 2))
    cfg.households.savings_goal_adjust_rate = rate
    with use_config(cfg):
        _settle(ec)
        assert _budget(ec) == pytest.approx(expected)


def test_food_first_healthcare_reserve_remains_the_final_cap(factory, monkeypatch):
    cfg, ec, _, _ = _world(factory, cash=0, funded=100)
    cfg.households.healthcare_food_first_reserve = True
    monkeypatch.setattr(ec, "_healthcare_food_first_reserves", lambda liquidity: np.array([80.0]))
    with use_config(cfg):
        _settle(ec)
        assert _budget(ec) == pytest.approx(20)


def test_payment_late_does_not_treat_unpaid_wages_as_income(factory):
    cfg, ec, _, _ = _world(factory, cash=100, timing="income_late")
    with use_config(cfg):
        assert ec._household_consumption_budgets(0, 0)[0] == pytest.approx(20)


def test_rent_comes_out_of_income_not_two_percent_of_savings(factory):
    cfg, ec, hh, _ = _world(factory, cash=300)
    with use_config(cfg):
        hh.renting_from_firm_id = 2
        hh.monthly_rent = 30
        _settle(ec)
        # E=2*10+30=50, T=6*(0.5+0.5)*50=300, cushion before rent = 300:
        # budget = 100 income - 30 rent + 0.02*(300-300) = 70, so spending
        # including rent equals income at the target.
        assert _budget(ec) == pytest.approx(70)


def test_unemployment_ema_updates_once_per_tick_and_risk_is_capped(factory):
    cfg = clone_config()
    cfg.households.savings_goal = True
    cfg.firms.working_capital_enabled = False
    with use_config(cfg):
        h1 = factory.household(household_id=1, employer_id=1)
        h2 = factory.household(household_id=2, employer_id=None)
        ec = factory.economy(households=[h1, h2], firms=[factory.firm()])
        ec.configure_stabilizers(households=False, firms=False, government=False)
        ec.current_tick = 1
        ec._phase_pre_plan_state(_TickScratch(payment_arm=False))
        assert ec.savings_goal_unemployment_ema == pytest.approx(0.5)
        h1.employer_id = None
        ec.current_tick = 2
        ec._phase_pre_plan_state(_TickScratch(payment_arm=False))
        assert ec.savings_goal_unemployment_ema == pytest.approx(0.5 * 12 / 14 + 2 / 14)
        ec._phase_pre_plan_state(_TickScratch(payment_arm=False))
        assert ec.savings_goal_unemployment_ema == pytest.approx(0.5 * 12 / 14 + 2 / 14)

    cfg, ec, _, _ = _world(factory, cash=0)
    with use_config(cfg):
        ec.savings_goal_unemployment_ema = 0.10
        _settle(ec)
        assert _budget(ec) == pytest.approx(96.04)
        ec.savings_goal_unemployment_ema = 1.0  # uncapped multiplier would exceed 2
        assert _budget(ec) == pytest.approx(92.8)


def test_spend_down_rate_applies_only_above_target(factory):
    cfg, ec, _, _ = _world(factory, cash=300)
    cfg.households.savings_goal_spend_down_rate = 0.05
    with use_config(cfg):
        _settle(ec)
        # E=30, T=180; cushion 300 is 120 above target: budget = 100 + 0.05 * 120.
        assert _budget(ec) == pytest.approx(106.0)
    cfg, ec, _, _ = _world(factory, cash=100)
    cfg.households.savings_goal_spend_down_rate = 0.05
    with use_config(cfg):
        _settle(ec)
        # Below target the rebuild rate (0.02) still applies: 100 + 0.02 * (100 - 180).
        assert _budget(ec) == pytest.approx(98.4)


def test_spend_down_rate_inherits_the_adjust_rate_when_unset(factory):
    # Compatibility: a caller that sets only savings_goal_adjust_rate gets it on both sides.
    cfg, ec, _, _ = _world(factory, cash=300)
    assert cfg.households.savings_goal_spend_down_rate is None
    cfg.households.savings_goal_adjust_rate = 0.05
    with use_config(cfg):
        _settle(ec)
        # E=30, T=180; 120 above target: 100 + 0.05 * 120.
        assert _budget(ec) == pytest.approx(106.0)
    cfg, ec, _, _ = _world(factory, cash=100)
    cfg.households.savings_goal_adjust_rate = 0.05
    with use_config(cfg):
        _settle(ec)
        # 80 below target: 100 + 0.05 * (100 - 180).
        assert _budget(ec) == pytest.approx(96.0)
