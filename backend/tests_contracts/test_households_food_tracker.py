"""Shopping plans read the latest completed week's consumption."""

import pytest

from config import clone_config, use_config


@pytest.fixture(autouse=True)
def _income_first_sequence():
    """Every test runs on income_first; legacy is not tested here."""
    config = clone_config()
    config.payment_sequence = "income_first"
    with use_config(config):
        yield


def test_food_shortfall_changes_the_next_plan(factory):
    cfg = clone_config()
    with use_config(cfg):
        hh = factory.household(household_id=1, goods_inventory={})
        hh.food_consumed_this_tick = cfg.households.food_health_high_threshold
        hh.food_consumed_last_tick = cfg.households.food_health_high_threshold
        hh.services_consumed_this_tick = hh.min_services_per_tick
        hh.services_consumed_last_tick = hh.min_services_per_tick
        eco = factory.economy(households=[hh])
        # Complete a week with no food or services, as phase 13 does.
        eco._batch_apply_household_updates({}, {}, {}, income_already_settled=True)
        assert hh.food_consumed_last_tick == cfg.households.food_health_high_threshold
        assert hh.food_consumed_this_tick == 0.0
        fractions = {"food": 0.4, "housing": 0.3, "services": 0.3}
        observed = {}
        hh._plan_category_purchases(100, category_fraction_override=fractions, debug_category_fractions=observed)
        # No food shifts all 0.3 from services and 0.7 * 0.3 * 0.5 from housing.
        assert observed["food"] == pytest.approx(0.4 + 0.3 + 0.105)


def test_services_comfort_uses_most_recent_week(factory):
    cfg = clone_config()
    with use_config(cfg):
        hh = factory.household()
        hh.food_consumed_this_tick = cfg.households.food_health_high_threshold
        hh.food_consumed_last_tick = cfg.households.food_health_high_threshold
        hh.services_consumed_last_tick = hh.min_services_per_tick
        hh.services_consumed_this_tick = 0.0
        fractions = {"food": 0.4, "housing": 0.4, "services": 0.2}
        observed = {}
        hh._plan_category_purchases(100, category_fraction_override=fractions, debug_category_fractions=observed)
        assert observed == pytest.approx({"food": 0.4, "housing": 0.2, "services": 0.4})
