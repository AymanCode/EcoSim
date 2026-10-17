"""Round 1 PR3: buffer-stock consumption.

These tests check behavior through public entry points: the per-household
traits and the budget the engine computes. The flag defaults off; tests that
cover the new budget turn it on.
"""

import numpy as np
import pytest

from config import CONFIG
from tests_contracts.factories import make_economy, make_household


@pytest.fixture
def buffer_on(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "buffer_stock_consumption", True)


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
    for name in ("buffer_target_weeks", "buffer_adjust_speed", "risk_aversion"):
        values = [getattr(h, name) for h in first]
        assert len(set(values)) == len(values), name
        assert values == [getattr(h, name) for h in again], name


def test_savers_hold_bigger_buffers_and_adjust_slower():
    households = [make_household(i) for i in range(1, 401)]
    saving = np.array([h.saving_tendency for h in households])
    assert np.corrcoef(saving, [h.buffer_target_weeks for h in households])[0, 1] > 0.8
    assert np.corrcoef(saving, [h.buffer_adjust_speed for h in households])[0, 1] < 0
    assert np.corrcoef(saving, [h.risk_aversion for h in households])[0, 1] > 0.3


def test_constructor_values_win():
    household = make_household(1, buffer_target_weeks=3.0, buffer_adjust_speed=0.5, risk_aversion=0.9)
    assert (household.buffer_target_weeks, household.buffer_adjust_speed,
            household.risk_aversion) == (3.0, 0.5, 0.9)


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


def test_buffer_target_rises_with_unemployment_and_risk_aversion():
    cautious = make_household(1, buffer_target_weeks=4.0, risk_aversion=1.4)
    relaxed = make_household(2, buffer_target_weeks=4.0, risk_aversion=0.6)
    assert cautious.buffer_target(100.0, 0.05, 30.0) > relaxed.buffer_target(100.0, 0.05, 30.0)
    assert cautious.buffer_target(100.0, 0.08, 30.0) > cautious.buffer_target(100.0, 0.05, 30.0)


def test_unemployment_term_is_capped_at_the_sourced_range():
    household = make_household(1, buffer_target_weeks=4.0, risk_aversion=1.0)
    at_cap = household.buffer_target(100.0, CONFIG.households.buffer_unemployment_cap, 30.0)
    assert household.buffer_target(100.0, 0.35, 30.0) == pytest.approx(at_cap)
    assert at_cap == pytest.approx(4.0 * 1.2 * 100.0)


def test_income_floor_is_the_live_benefit():
    household = make_household(1, buffer_target_weeks=4.0, risk_aversion=1.0)
    assert household.buffer_target(0.0, 0.0, 30.0) == pytest.approx(120.0)
    assert household.buffer_target(0.0, 0.0, 45.0) == pytest.approx(180.0)  # moves with policy


def _saving(cash, spending_tendency=1.0):
    # frugality 1.0 and spending_tendency 1.0 = neutral personality (multiplier 1);
    # spending_tendency 0.85 = a saver (multiplier 0.85).
    household = _employed(1, cash=cash, buffer_target_weeks=4.0, buffer_adjust_speed=0.01, risk_aversion=1.0,
                          spending_tendency=spending_tendency, frugality=1.0)
    budget = _budgets([household], unemployment_rate=0.05)[0]
    return household.wage - budget


@pytest.mark.parametrize("spending_tendency", [1.0, 0.85])
def test_savers_keep_saving_past_the_target_at_a_smaller_rate(buffer_on, spending_tendency):
    target = 4.0 * 1.0 * (1 + 2.0 * 0.05) * 100.0  # 440
    half, at_target, above = (_saving(c, spending_tendency) for c in (0.5 * target, target, 1.25 * target))
    assert half > at_target > above > 0.0  # still saves above the target, but less
    # No hard stop: a small step past the target changes saving only a little.
    assert _saving(1.01 * target, spending_tendency) == pytest.approx(at_target, rel=0.05)
