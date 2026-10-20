"""Sticky posted prices. The flag defaults off.

Hold weeks must not replace the Services target markup. The weekly price cap,
at a review, compounds over the weeks since the posted price last changed.
Tests that step the economy use the real pricing rule.
"""

import math
import random

import pytest

from config import FirmBehaviorConfig, SimulationConfig, clone_config, use_config
from economy import Economy
from tests_contracts.conftest import total_money_net_of_injections
from tests_contracts.factories import make_firm, make_government, make_households


def _config():
    return use_config(clone_config())


def _enable(sticky=True, ratchet=True, compounds=True):
    from config import CONFIG

    CONFIG.firms.sticky_prices_enabled = sticky
    CONFIG.firms.services_target_markup_held = ratchet
    CONFIG.firms.sticky_price_cap_compounds = compounds
    CONFIG.time.warmup_ticks = 0


def _services_firm(**overrides):
    firm = make_firm(firm_id=1, category="Services", is_baseline=False, seed=7)
    firm.markup = 0.30
    firm.price = 20.0
    firm.min_price = 0.5
    firm.unit_cost = 5.0
    firm.wage_offer = 40.0
    firm.employees = [1, 2, 3, 4]
    firm.actual_wages = {i: 40.0 for i in firm.employees}
    firm.production_capacity_units = 8
    firm.units_per_worker = 4.0
    firm.last_units_produced = 16.0
    firm.service_infrastructure_loan_payment_per_tick = 0.0
    for key, value in overrides.items():
        setattr(firm, key, value)
    return firm


def _food_firm(**overrides):
    firm = make_firm(firm_id=2, category="Food", is_baseline=False, seed=9)
    firm.price = 8.0
    firm.min_price = 0.5
    firm.markup = 0.25
    firm.unit_cost = 4.0
    firm.price_adjustment_rate = 0.10
    firm.target_inventory_weeks = 2.0
    firm.inventory_units = 0.0
    firm.expected_sales_units = 100.0
    firm.last_units_produced = 0.0
    firm.last_units_sold = 0.0
    firm.cash_balance = 50_000.0
    for key, value in overrides.items():
        setattr(firm, key, value)
    return firm


def test_config_rejects_non_finite_and_non_bool_sticky_settings():
    bad_flags = (1, 0, "yes", None, float("nan"))
    for bad in bad_flags:
        with pytest.raises(ValueError, match="bool"):
            SimulationConfig(firms=FirmBehaviorConfig(sticky_prices_enabled=bad))
        with pytest.raises(ValueError, match="bool"):
            SimulationConfig(firms=FirmBehaviorConfig(sticky_price_cap_compounds=bad))
    for name, value in (
        ("price_review_gap_scale", float("nan")),
        ("price_review_gap_scale", float("inf")),
        ("price_review_gap_scale", 0.0),
        ("price_review_gap_scale", -0.1),
        ("price_review_inflation_knee", float("nan")),
        ("price_review_inflation_knee", float("-inf")),
        ("price_review_inflation_knee", -0.01),
        ("price_review_inflation_slope", float("inf")),
        ("price_review_inflation_slope", float("nan")),
        ("price_review_inflation_slope", -1.0),
    ):
        with pytest.raises(ValueError):
            SimulationConfig(firms=FirmBehaviorConfig(**{name: value}))
    for weeks in ((0.0, 10.0), (5.0, 4.0), (float("nan"), 10.0), (1.0, float("inf"))):
        with pytest.raises(ValueError, match="price_review_weeks_food"):
            SimulationConfig(firms=FirmBehaviorConfig(price_review_weeks_food=weeks))
    # The Services markup check is still there.
    with pytest.raises(ValueError, match="bool"):
        SimulationConfig(firms=FirmBehaviorConfig(services_target_markup_held=1))


def test_runtime_reader_rejects_a_mutated_non_bool_flag():
    with _config():
        from config import CONFIG, sticky_prices_enabled

        CONFIG.firms.sticky_prices_enabled = float("nan")
        with pytest.raises(ValueError, match="bool"):
            sticky_prices_enabled()
        CONFIG.firms.sticky_prices_enabled = False
        assert sticky_prices_enabled() is False


def test_interval_is_in_range_varies_by_firm_and_consumes_no_rng():
    with _config():
        _enable()
        food = [_food_firm(firm_id=i) for i in (3, 4, 9)]
        intervals = [firm.price_review_interval() for firm in food]
        for interval in intervals:
            assert 15.0 <= interval <= 39.0
        assert len(set(round(v, 6) for v in intervals)) > 1
        services = _services_firm()
        assert 19.0 <= services.price_review_interval() <= 34.0
        care = make_firm(firm_id=8, category="Healthcare", is_baseline=False, seed=3)
        assert 34.0 <= care.price_review_interval() <= 65.0
        random.seed(1)
        before = random.random()
        random.seed(1)
        services.price_review_interval()
        assert random.random() == before


def test_who_is_sticky():
    with _config():
        _enable()
        food = _food_firm()
        assert food.uses_sticky_prices(False) is True
        assert food.uses_sticky_prices(True) is False
        assert _services_firm().uses_sticky_prices(False) is True
        care = make_firm(firm_id=8, category="Healthcare", is_baseline=False, seed=3)
        assert care.uses_sticky_prices(False) is True
        housing = make_firm(firm_id=6, category="Housing", is_baseline=False, seed=3)
        assert housing.uses_sticky_prices(False) is False
        baseline = make_firm(firm_id=7, category="Food", is_baseline=True, seed=3)
        assert baseline.uses_sticky_prices(False) is False
        from config import CONFIG

        CONFIG.firms.sticky_prices_enabled = False
        assert food.uses_sticky_prices(False) is False


def test_hold_keeps_the_services_target_and_the_real_rule_moves_the_shadow():
    """The bug wrote markup_next from the held price. The real Services rule does not."""
    with _config():
        _enable()
        from config import CONFIG

        CONFIG.firms.price_review_weeks_services = (40.0, 40.0)
        firm = _services_firm()
        # Posted margin is 20/5 - 1 = 3. The target is 0.30. A hold must keep 0.30.
        plan = firm.plan_sticky_pricing(
            12, None, sell_through_rate=1.0, unemployment_rate=0.05, profit_tax_rate=0.20,
        )
        assert plan["price_review"] is False
        assert plan["price_next"] == pytest.approx(20.0)
        assert plan["markup_next"] == pytest.approx(0.30)
        assert plan["markup_next"] != pytest.approx(firm._markup_for_price(20.0))
        assert firm.markup == pytest.approx(0.30)
        assert firm.price_shadow != pytest.approx(20.0)
        assert math.isfinite(firm.price_shadow)
        assert firm.price_shadow >= firm.min_price
        assert firm.decision_diagnostics["price_review_inflation_term_active"] is False
        firm.apply_price_and_wage_updates(plan, {"wage_offer_next": firm.wage_offer})
        assert firm.price == pytest.approx(20.0)
        assert firm.markup == pytest.approx(0.30)


def test_inflation_term_is_disclosed_and_raises_the_hazard_only_when_measured():
    with _config():
        _enable()
        from config import CONFIG

        CONFIG.firms.price_review_weeks_food = (20.0, 20.0)
        firm = _food_firm()
        calm = firm.price_review_hazard(10.0, 10.0, None)
        hot = firm.price_review_hazard(10.0, 10.0, 0.20)
        below = firm.price_review_hazard(10.0, 10.0, 0.05)
        assert hot > calm
        assert below == pytest.approx(calm)
        # 0.20 is 0.075 above the 0.125 knee; slope 1.38.
        assert hot == pytest.approx(calm * (1.0 + 1.38 * 0.075))
        CONFIG.inflation.enabled = False
        plan = firm.plan_sticky_pricing(
            3, 0.20, sell_through_rate=1.0, unemployment_rate=0.05,
        )
        assert plan["price_review"] is False
        assert firm.decision_diagnostics["price_review_inflation_term_active"] is False
        assert firm.decision_diagnostics["price_review_inflation_annual"] is None


def test_non_finite_shadow_does_not_freeze_the_posted_price():
    with _config():
        _enable()
        from config import CONFIG

        CONFIG.firms.price_review_weeks_food = (2.0, 2.0)
        firm = _food_firm()
        firm.price_shadow = float("nan")
        firm.markup_shadow = float("inf")
        firm.price_review_pressure = float("nan")
        plan = firm.plan_sticky_pricing(
            4, None, sell_through_rate=1.0, unemployment_rate=0.05,
        )
        assert math.isfinite(plan["price_next"])
        assert math.isfinite(plan["markup_next"])
        assert plan["price_next"] >= firm.min_price
        assert math.isfinite(firm.price_shadow)
        assert firm.price_review_pressure == 0.0 or firm.price_review_pressure < 1.0


def test_food_hold_posts_the_old_price_while_the_shadow_follows_the_rule():
    with _config():
        _enable()
        from config import CONFIG

        CONFIG.firms.price_review_weeks_food = (30.0, 30.0)
        firm = _food_firm()
        plan = firm.plan_sticky_pricing(
            1, None, sell_through_rate=1.0, unemployment_rate=0.05,
        )
        assert plan["price_review"] is False
        assert plan["price_next"] == pytest.approx(8.0)
        # Sell-through 1 and empty inventory: the real Food rule raises ~5%.
        assert firm.price_shadow == pytest.approx(8.0 * 1.05)
        assert firm.markup == pytest.approx(0.25)


def _live_economy():
    government = make_government(cash_balance=50_000.0, profit_tax_rate=0.20)
    services = _services_firm()
    services.price = 8.0
    services.employees = [1, 2, 3, 4]
    food = _food_firm()
    food.inventory_units = 5_000.0
    food.price = 4.0
    households = make_households(12, start_id=1, cash_start=4_000.0, cash_step=0.0)
    for household in households:
        household.cash_balance = 4_000.0
        household.services_preference = 3.0
        household.employer_id = 1
        household.wage = 25.0
    economy = Economy(households=households, firms=[services, food], government=government)
    economy._apply_random_shocks = lambda: None
    return economy, services, food


def test_economy_step_holds_the_posted_services_price_and_the_target_markup():
    """Flag on, real Services rule, no monkeypatch. Posted price and markup."""
    with _config():
        _enable()
        from config import CONFIG

        CONFIG.firms.price_review_weeks_services = (40.0, 40.0)
        CONFIG.firms.price_review_weeks_food = (40.0, 40.0)
        economy, services, food = _live_economy()
        economy.step()
        posted = services.price
        food_posted = food.price
        assert math.isfinite(posted) and posted >= services.min_price
        assert services.markup == pytest.approx(0.30)
        assert services.decision_diagnostics["price_review_inflation_term_active"] is False
        sold = 0.0
        paid = 0.0
        food_changes = 0
        for _ in range(6):
            economy.step()
            assert services.markup == pytest.approx(0.30)
            assert services.price == pytest.approx(posted)
            assert math.isfinite(food.price) and food.price >= food.min_price
            # A Food change is a review that posts the shadow, not a weekly rewrite.
            if abs(food.price - food_posted) > 1e-9:
                food_changes += 1
                assert food.decision_diagnostics.get("price_review") is True
                assert food.price == pytest.approx(food.price_shadow)
            else:
                assert food.decision_diagnostics.get("price_review") is False
            food_posted = food.price
            sold += float(services.last_units_sold)
            paid += float(services.last_revenue)
        assert sold > 0.0
        assert paid > 0.0
        assert food_changes >= 1
        # The held price's margin is not the target. If the bug returns, markup moves.
        if services.unit_cost > 0:
            implied = services.price / services.unit_cost - 1.0
            if abs(implied - 0.30) > 0.05:
                assert services.markup != pytest.approx(implied)


def test_economy_step_posts_the_shadow_at_a_food_review():
    with _config():
        _enable()
        from config import CONFIG

        CONFIG.firms.price_review_weeks_food = (1.0, 1.0)
        CONFIG.firms.price_review_weeks_services = (40.0, 40.0)
        economy, services, food = _live_economy()
        food.inventory_units = 0.0
        food.expected_sales_units = 100.0
        food.last_units_produced = 0.0
        food.price_adjustment_rate = 0.10
        economy.last_tick_sell_through_rate[food.firm_id] = 1.0
        start = food.price
        economy.step()
        assert food.decision_diagnostics.get("price_review") is True
        assert food.price == pytest.approx(food.price_shadow)
        assert food.price == pytest.approx(start * 1.05)
        assert services.markup == pytest.approx(0.30)


def test_economy_step_compounds_the_weekly_cap_over_held_weeks():
    """A review may rise by multiplier^weeks, not by one week only."""
    with _config():
        _enable(compounds=True)
        from config import CONFIG

        CONFIG.firms.price_review_weeks_food = (30.0, 30.0)
        government = make_government(cash_balance=80_000.0)
        government.price_stabilization_target = "food"
        government.price_stabilization_level = "strict"
        food = _food_firm()
        food.price = 10.0
        household = make_households(1, cash_start=1_000.0, cash_step=0.0)[0]
        economy = Economy(households=[household], firms=[food], government=government)
        economy._apply_random_shocks = lambda: None
        economy.step()
        posted = food.price
        weeks = 6
        food.price_shadow = posted * 5.0
        food.price_review_pressure = 0.99
        food.last_units_produced = 0.0
        food.inventory_units = 0.0
        food.expected_sales_units = 100.0
        food.price_adjustment_rate = 0.10
        food.cash_balance = 50_000.0
        food.survival_mode = False
        economy.last_tick_sell_through_rate[food.firm_id] = 1.0
        food.last_posted_price_change_tick = economy.current_tick - weeks
        economy.step()
        cap = posted * (1.01 ** weeks)
        assert food.price == pytest.approx(cap, rel=1e-6)
        assert food.price < food.price_shadow
        assert food.decision_diagnostics.get("price_review") is True


def test_services_floor_does_not_reset_the_cap_clock():
    """A clearing-floor raise is a posted price change. It is not a new cap week.

    The clock stays on the pricing plan. Resetting it here made weeks stay 1,
    so compounding and a one-week cap posted the same Services price.
    """
    with _config():
        _enable(compounds=True)
        from config import CONFIG

        CONFIG.firms.price_review_weeks_services = (40.0, 40.0)
        government = make_government(cash_balance=80_000.0)
        government.price_stabilization_target = "services"
        government.price_stabilization_level = "strict"
        services = _services_firm()
        services.price = 10.0
        households = make_households(4, cash_start=5_000.0, cash_step=0.0)
        services.employees = [household.household_id for household in households]
        services.actual_wages = {household.household_id: 400.0 for household in households}
        services.wage_offer = 400.0
        for household in households:
            household.employer_id = services.firm_id
            household.wage = 400.0
        economy = Economy(households=households, firms=[services], government=government)
        economy._apply_random_shocks = lambda: None
        economy.step()
        posted = float(services.price)
        services.price_shadow = posted
        services.markup_shadow = float(services.markup)
        services.price_review_pressure = 0.0
        services.last_posted_price_change_tick = 0
        for household in households:
            household.wage = 2_000.0
        services.actual_wages = {household.household_id: 2_000.0 for household in households}
        services.wage_offer = 2_000.0
        supply = economy._estimated_firm_market_supply(services, current_tick_capacity=True)
        floor = economy._effective_market_price(services, supply)
        assert floor > posted
        economy.step()
        # Clearing can charge the floor this tick. The stored price stays on the
        # plan, and the cap clock stays on the plan's last change.
        assert services.decision_diagnostics.get("price_review") is False
        assert services.price == pytest.approx(posted)
        assert services.last_posted_price_change_tick == 0
        if services.last_units_sold > 0.0:
            assert services.last_revenue / services.last_units_sold > posted


def test_economy_step_per_review_cap_allows_only_one_week():
    with _config():
        _enable(compounds=False)
        from config import CONFIG

        CONFIG.firms.price_review_weeks_food = (30.0, 30.0)
        government = make_government(cash_balance=80_000.0)
        government.price_stabilization_target = "food"
        government.price_stabilization_level = "strict"
        food = _food_firm()
        food.price = 10.0
        household = make_households(1, cash_start=1_000.0, cash_step=0.0)[0]
        economy = Economy(households=[household], firms=[food], government=government)
        economy._apply_random_shocks = lambda: None
        economy.step()
        posted = food.price
        food.price_shadow = posted * 5.0
        food.price_review_pressure = 0.99
        food.last_units_produced = 0.0
        food.inventory_units = 0.0
        food.expected_sales_units = 100.0
        food.cash_balance = 50_000.0
        food.survival_mode = False
        economy.last_tick_sell_through_rate[food.firm_id] = 1.0
        food.last_posted_price_change_tick = economy.current_tick - 6
        economy.step()
        assert food.price == pytest.approx(posted * 1.01, rel=1e-6)


def test_turning_the_flag_off_clears_sticky_state():
    with _config():
        _enable()
        from config import CONFIG

        CONFIG.firms.price_review_weeks_services = (40.0, 40.0)
        economy, services, _food = _live_economy()
        economy.step()
        assert services.price_shadow is not None
        CONFIG.firms.sticky_prices_enabled = False
        economy.step()
        assert services.price_shadow is None
        assert services.markup_shadow is None
        assert services.price_review_pressure == 0.0
        assert services.last_posted_price_change_tick is None
        assert services.markup == pytest.approx(0.30)


def test_two_flag_on_runs_post_the_same_prices():
    def _once():
        with _config():
            _enable()
            from config import CONFIG

            CONFIG.firms.price_review_weeks_services = (40.0, 40.0)
            CONFIG.firms.price_review_weeks_food = (40.0, 40.0)
            economy, services, food = _live_economy()
            for _ in range(4):
                economy.step()
            return (
                round(services.price, 6),
                round(services.markup, 6),
                round(food.price, 6),
                round(services.last_revenue, 6),
                round(economy.government.cash_balance, 6),
            )

    assert _once() == _once()


def test_flag_on_creates_no_money_on_a_short_run():
    def _drift(sticky: bool) -> float:
        with _config():
            _enable(sticky=sticky)
            economy, _services, _food = _live_economy()
            before = total_money_net_of_injections(economy)
            for _ in range(5):
                economy.step()
            return total_money_net_of_injections(economy) - before

    off = _drift(False)
    on = _drift(True)
    assert math.isfinite(off) and math.isfinite(on)
    assert abs(off) < 0.05
    assert abs(on) < 0.05


def test_empty_firm_list_still_steps_with_the_flag_on():
    with _config():
        _enable()
        household = make_households(1, cash_start=100.0, cash_step=0.0)[0]
        economy = Economy(households=[household], firms=[], government=make_government())
        economy._apply_random_shocks = lambda: None
        economy.step()
        assert economy.current_tick == 1
        assert math.isfinite(household.cash_balance)


def test_hazard_is_finite_when_the_shadow_is_zero():
    with _config():
        firm = _food_firm()
        firm.min_price = 0.0
        hazard = firm.price_review_hazard(5.0, 0.0, None)
        assert math.isfinite(hazard) and hazard > 0.0
