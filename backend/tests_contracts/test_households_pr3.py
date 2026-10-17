"""Round 1 PR3: buffer-stock consumption and slow reservation-wage decay.

These tests check behavior through public entry points: the per-household
budget the engine computes, the labor plan a household returns, and its
reservation wage after weeks of unemployment. Both flags default off; each
test turns on only the flag it covers.
"""

import numpy as np
import pytest

from config import CONFIG
from tests_contracts.factories import make_economy, make_household


@pytest.fixture
def buffer_on(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "buffer_stock_consumption", True)


@pytest.fixture
def reservation_on(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "slow_reservation_decay", True)


def _employed(hid, *, wage=100.0, cash=0.0, **traits):
    household = make_household(hid, cash_balance=cash, **traits)
    household.employer_id = 1
    household.wage = wage
    return household


def _budgets(households, unemployment_rate=0.05, benefit=30.0):
    economy = make_economy(households=households)
    return economy._household_consumption_budgets(unemployment_rate, benefit)


# --- heterogeneity ---------------------------------------------------------

def test_traits_differ_across_households_and_repeat_for_same_id():
    first = [make_household(i) for i in range(1, 201)]
    again = [make_household(i) for i in range(1, 201)]
    for name in ("buffer_target_weeks", "buffer_adjust_speed", "reservation_decay_rate", "risk_aversion"):
        values = [getattr(h, name) for h in first]
        assert len(set(values)) == len(values), name
        assert values == [getattr(h, name) for h in again], name
    rates = np.array([h.reservation_decay_rate for h in first])
    assert 0.0010 < rates.mean() < 0.0018  # centred on 0.14%/week


def test_savers_hold_bigger_buffers_and_adjust_slower():
    households = [make_household(i) for i in range(1, 401)]
    saving = np.array([h.saving_tendency for h in households])
    assert np.corrcoef(saving, [h.buffer_target_weeks for h in households])[0, 1] > 0.8
    assert np.corrcoef(saving, [h.buffer_adjust_speed for h in households])[0, 1] < 0
    assert np.corrcoef(saving, [h.risk_aversion for h in households])[0, 1] > 0.3


def test_constructor_values_win():
    household = make_household(1, buffer_target_weeks=3.0, buffer_adjust_speed=0.5,
                               reservation_decay_rate=0.01, risk_aversion=0.9)
    assert (household.buffer_target_weeks, household.buffer_adjust_speed,
            household.reservation_decay_rate, household.risk_aversion) == (3.0, 0.5, 0.01, 0.9)


# --- A: buffer-stock consumption -------------------------------------------

def test_cash_above_target_is_spent_down_and_below_target_is_rebuilt(buffer_on):
    traits = dict(buffer_target_weeks=4.0, buffer_adjust_speed=0.1, risk_aversion=1.0)
    rich = _employed(1, cash=2_000.0, **traits)   # target ~440, gap ~+1560
    poor = _employed(2, cash=150.0, **traits)     # gap -250
    budgets = _budgets([rich, poor])
    assert budgets[0] > 100.0      # spends more than its whole wage
    assert budgets[1] < budgets[0] - 150.0  # k * gap difference, 0.1 * 1850 = 185
    assert budgets[1] <= 150.0


def test_spender_draws_down_faster_than_saver_with_same_money(buffer_on):
    saver = _employed(1, cash=2_000.0, buffer_target_weeks=8.0, buffer_adjust_speed=0.02, risk_aversion=1.0)
    spender = _employed(2, cash=2_000.0, buffer_target_weeks=2.0, buffer_adjust_speed=0.10, risk_aversion=1.0)
    budgets = _budgets([saver, spender])
    assert budgets[1] > budgets[0]


def test_budget_bounded_by_liquidity_and_keeps_subsistence(buffer_on):
    broke = _employed(1, wage=0.0, cash=30.0, buffer_target_weeks=8.0, buffer_adjust_speed=0.1)
    flush = _employed(2, cash=500.0, buffer_target_weeks=0.5, buffer_adjust_speed=1.0)
    budgets = _budgets([broke, flush])
    assert budgets[0] == pytest.approx(30.0)  # min(subsistence 50, liquidity 30)
    assert budgets[1] <= 500.0 + 1e-9


# --- B: reservation wage -----------------------------------------------------

def _unemployed(hid=1, **kw):
    household = make_household(hid, **kw)
    household.employer_id = None
    household.wage = 0.0
    return household


def _unemployed_weeks(household, weeks):
    for tick in range(weeks):
        household.apply_labor_outcome({"employer_id": None, "wage": 0.0}, current_tick=tick)


def test_reservation_falls_slowly_and_speeds_up_with_spell_length(reservation_on):
    household = _unemployed(cash_balance=0.0, reservation_decay_rate=0.0014)
    household.reservation_wage = 50.0
    _unemployed_weeks(household, 10)
    # Broke: 1.5x the base rate, plus at most +19% for a 10-week spell.
    assert 50.0 * (1 - 0.0014 * 1.5 * 1.2) ** 10 < household.reservation_wage < 50.0 * (1 - 0.0014) ** 10
    before = household.reservation_wage
    _unemployed_weeks(household, 1)
    early_drop = before - household.reservation_wage
    household.unemployment_duration = 60
    before = household.reservation_wage
    _unemployed_weeks(household, 1)
    assert before - household.reservation_wage > 1.5 * early_drop


def test_buffer_target_rises_with_unemployment_and_risk_aversion():
    cautious = make_household(1, buffer_target_weeks=4.0, risk_aversion=1.4)
    relaxed = make_household(2, buffer_target_weeks=4.0, risk_aversion=0.6)
    assert cautious.buffer_target(100.0, 0.05) > relaxed.buffer_target(100.0, 0.05)
    assert cautious.buffer_target(100.0, 0.20) > cautious.buffer_target(100.0, 0.05)


def test_savings_slow_the_decay(reservation_on):
    broke = _unemployed(1, cash_balance=0.0, reservation_decay_rate=0.002)
    saver = _unemployed(2, cash_balance=1e6, reservation_decay_rate=0.002)
    broke.reservation_wage = saver.reservation_wage = 50.0
    _unemployed_weeks(broke, 20)
    _unemployed_weeks(saver, 20)
    assert broke.reservation_wage < saver.reservation_wage < 50.0


def test_legacy_decay_is_much_faster_without_flag():
    household = _unemployed(cash_balance=0.0)
    household.reservation_wage = 50.0
    _unemployed_weeks(household, 10)
    assert household.reservation_wage < 50.0 * 0.95


def test_live_floor_replaces_one_dollar_floor(reservation_on):
    household = _unemployed(cash_balance=0.0)
    household.reservation_wage = 0.5
    prices = {"housing": 10.0, "food": 10.0}
    living = household.living_cost_per_tick(prices)
    low = household.plan_labor_supply(20.0, category_expected_prices=prices)["reservation_wage"]
    assert low == pytest.approx(min(20.0 + living, 30.0))
    high = household.plan_labor_supply(40.0, category_expected_prices=prices)["reservation_wage"]
    assert high == pytest.approx(min(40.0 + living, 60.0))
    none = household.plan_labor_supply(0.0, category_expected_prices=prices)["reservation_wage"]
    assert none < 1.0  # no benefit: no floor, and the old $1 floor is gone
