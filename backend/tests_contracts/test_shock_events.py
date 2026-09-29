def test_random_shocks_emit_regime_events(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=30, num_firms_per_category=1, disable_shocks=False)
    economy.in_warmup = False
    seen = set()
    for tick in range(1, 400):
        economy.current_tick = tick
        economy.last_regime_events = []
        economy._apply_random_shocks()
        for event in economy.last_regime_events:
            if event["event_type"].startswith("shock_"):
                seen.add(event["event_type"])
                assert event["entity_type"] == "economy"
                assert isinstance(event["metric_value"], float)
                assert isinstance(event["payload"]["affected"], int) and event["payload"]["affected"] >= 1
        if {"shock_demand", "shock_supply", "shock_health"} <= seen:
            break
    assert {"shock_demand", "shock_supply", "shock_health"} <= seen


def test_supply_shock_is_a_decaying_productivity_multiplier(tiny_economy_factory):
    """B26: a supply shock changes what the firm produces, then fades.

    Before the fix the shock scaled `firm.last_units_produced` (and truncated it
    to an int), a record that production overwrites the same tick, so it had no
    productivity effect and corrupted the planners' view of last output instead.
    """
    import pytest
    from config import CONFIG

    economy = tiny_economy_factory(num_households=30, num_firms_per_category=1, disable_shocks=False)
    economy.in_warmup = False
    for firm in economy.firms:
        firm.last_units_produced = 100.5
    shocked = None
    for tick in range(1, 400):
        economy.current_tick = tick
        economy.last_regime_events = []
        economy._apply_random_shocks()
        event = next((e for e in economy.last_regime_events if e["event_type"] == "shock_supply"), None)
        if event is not None:
            shocked = event
            break
    assert shocked is not None
    change = shocked["metric_value"]
    hit = [f for f in economy.firms if getattr(f, "supply_shock_multiplier", 1.0) != 1.0]
    assert len(hit) == shocked["payload"]["affected"]
    assert all(f.supply_shock_multiplier == pytest.approx(change) for f in hit)
    # The planners' record of last output is left alone.
    assert all(f.last_units_produced == 100.5 for f in economy.firms)

    # The multiplier fades back toward 1.0 by the configured share each tick.
    decay = CONFIG.firms.supply_shock_decay_per_tick
    firm = hit[0]
    economy.current_tick += 1
    economy._apply_random_shocks()
    expected = 1.0 + (change - 1.0) * (1.0 - decay)
    if firm.supply_shock_multiplier != pytest.approx(change):  # not re-shocked this tick
        assert firm.supply_shock_multiplier == pytest.approx(expected)


def test_supply_shock_multiplier_scales_goods_production(tiny_economy_factory):
    """B26: production reads the firm's supply-shock multiplier."""
    import pytest

    economy = tiny_economy_factory(num_households=10, include_housing=False, include_services=False,
                                   include_healthcare=False)
    food = economy.firms[0]
    food.employees = [h.household_id for h in economy.households[:5]]
    base = economy._calculate_experience_adjusted_production(food, 10.0)
    assert 0.0 < base < food.production_capacity_units
    food.supply_shock_multiplier = 0.8
    assert economy._calculate_experience_adjusted_production(food, 10.0) == pytest.approx(base * 0.8)
