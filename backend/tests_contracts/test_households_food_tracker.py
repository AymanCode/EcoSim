"""The optional tracker fix reads the latest completed week's consumption."""

import pytest

from config import clone_config, use_config


@pytest.mark.parametrize("timing", ["income_first", "income_late", "legacy"])
def test_food_shortfall_changes_the_next_plan(factory, timing):
    cfg = clone_config()
    cfg.payment_sequence = timing
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
        old, fixed = {}, {}
        hh._plan_category_purchases(100, category_fraction_override=fractions, debug_category_fractions=old)
        cfg.households.fix_food_tracker_lag = True
        hh._plan_category_purchases(100, category_fraction_override=fractions, debug_category_fractions=fixed)
        assert old["food"] == pytest.approx(0.4)
        assert fixed["food"] > old["food"]


def test_services_comfort_uses_most_recent_week(factory):
    cfg = clone_config()
    cfg.households.fix_food_tracker_lag = True
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
