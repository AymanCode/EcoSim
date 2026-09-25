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
