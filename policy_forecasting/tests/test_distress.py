from types import SimpleNamespace

import pytest

from policy_forecasting.distress import (
    DistressHistory,
    consumer_distress,
    food_shortfall_ratio,
    household_distress,
)


def test_food_shortfall_uses_frozen_formula():
    assert food_shortfall_ratio(min_food=2.0, consumed=1.0) == 0.5
    assert food_shortfall_ratio(min_food=2.0, consumed=3.0) == 0.0
    assert food_shortfall_ratio(min_food=0.0, consumed=0.0) == 0.0


def test_household_distress_matches_frozen_weights():
    household = SimpleNamespace(
        household_id=1,
        cash_balance=0.0,
        health=0.75,
        happiness=0.50,
        min_food_per_tick=2.0,
        food_consumed_this_tick=2.0,
    )
    history = [1.0, 0.5, 0.1, 0.2, 0.0, 0.0, 0.0, 0.0]

    result = household_distress(household, history)

    assert result == pytest.approx(0.65)


def test_consumer_distress_averages_households_and_updates_history():
    histories = DistressHistory(window=8)
    households = [
        SimpleNamespace(
            household_id=1,
            cash_balance=200.0,
            health=1.0,
            happiness=1.0,
            min_food_per_tick=2.0,
            food_consumed_this_tick=2.0,
        ),
        SimpleNamespace(
            household_id=2,
            cash_balance=0.0,
            health=1.0,
            happiness=1.0,
            min_food_per_tick=2.0,
            food_consumed_this_tick=0.0,
        ),
    ]

    first = consumer_distress(households, histories)
    second = consumer_distress(households, histories)

    assert first == pytest.approx((0.0 + (0.40 + 0.25 / 8.0)) / 2.0)
    assert second > first
