"""The classic dashboard receives the complete grocery ledger each displayed week."""
import asyncio
import json

import pytest

from server import SetupConfig, SimulationManager


def test_live_grocery_policy_cap_closure_and_reopening(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    manager = SimulationManager(session_id="food-credit-policy")
    manager.initialize({"seed": 7, "num_households": 10, "tracked_households": 10, "num_firms": 1,
                        "payment_sequence": "income_first", "horizon_ticks": 5})
    changes = {
        1: {"food_credit_policy": "on", "food_credit_weekly_budget": 3},
        2: {"food_credit_weekly_budget": 0},
        3: {"food_credit_policy": "off", "food_credit_weekly_budget": 1.40},
        4: {"food_credit_policy": "on"},
    }
    # Food is unavailable in displayed weeks 2 and 3. The card must still work when the store reopens.
    economy = manager.economy
    supply = economy._estimated_firm_market_supply

    def available(firm, current_tick_capacity=False):
        if economy.current_tick in (1, 2) and firm.good_category.lower() == "food":
            return 0
        return supply(firm, current_tick_capacity)

    monkeypatch.setattr(economy, "_estimated_firm_market_supply", available)
    frames, messages = [], []

    class Socket:
        async def send_text(self, data):
            frame = json.loads(data)
            frames.append(frame["metrics"])
            if frame["tick"] in changes:
                receipt = await manager.update_config(changes[frame["tick"]])
                assert receipt["type"] == "CONFIG_QUEUED"

        async def send_json(self, data):
            messages.append(data)

    async def run():
        manager.active_websocket = Socket()
        manager.start_background_loop()
        await asyncio.wait_for(manager.run_task, timeout=30)

    asyncio.run(run())
    receipts = [m for m in messages if m.get("type") == "CONFIG_APPLIED"]
    assert len(receipts) == 4
    for week, receipt in enumerate(receipts, 1):
        assert receipt["applied"] == changes[week]
        assert receipt["effectiveTick"] == week + 1
    policies = [frame["governmentPolicy"] for frame in frames]
    assert [p["food_credit_policy"] for p in policies] == ["off", "on", "on", "off", "on"]
    assert [p["food_credit_weekly_budget"] for p in policies] == [5.0, 3.0, 0.0, 1.4, 1.4]
    assert "food_credit" not in frames[0]["payment"]["fiscal"]
    settlements = [frame["payment"]["fiscal"]["food_credit"] for frame in frames[1:]]
    assert [s["issued"] for s in settlements] == pytest.approx([3.0, 0.0, 0.0, 1.4])
    for frame in frames[1:3]:
        balances = sorted(p["groceryCardBalance"] for p in frame["trackedSubjects"])
        assert balances == [0.0] * 8 + [1.5, 1.5]
    assert settlements[2]["redeemed"] > 0
    opening = 0.0
    for s in settlements:
        assert s["outstanding"] == pytest.approx(opening + s["issued"] - s["redeemed"])
        opening = s["outstanding"]


def test_unsupported_timing_rejects_grocery_program_and_budget(monkeypatch):
    sequence = "income_late"
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    manager = SimulationManager(session_id="food-credit-timing")
    manager.initialize({"num_households": 5, "payment_sequence": sequence})
    changes = {"food_credit_policy": "on", "food_credit_weekly_budget": 3.2}
    receipt = asyncio.run(manager.update_config(changes))
    assert receipt["applied"] == {}
    assert set(receipt["rejected"]) == set(changes)
    assert manager.economy.government.food_credit_policy == "off"
    assert manager.economy.government.food_credit_weekly_budget == 0
    with pytest.raises(ValueError, match="requires income_first"):
        SetupConfig(payment_sequence=sequence, initial_policy=changes)


def test_opening_flag_and_explicit_budget_work_in_matched_worlds(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    base = {"seed": 9, "num_households": 15, "payment_sequence": "income_first"}
    start_closed = {**base, "payment_food_credit_enabled": True, "initial_policy": {
        "food_credit_policy": "off", "food_credit_weekly_budget": 0}}
    assert SetupConfig(**start_closed).world_key(9) == SetupConfig(**base).world_key(9)
    manager = SimulationManager(session_id="opening-budget")
    manager.initialize(start_closed)
    opening = manager.setup_config["applied_policy"]
    assert (opening["food_credit_policy"], opening["food_credit_weekly_budget"]) == ("off", 0)
    result = asyncio.run(manager.update_config({"foodCreditWeeklyBudget": 6.25}))
    assert result["applied"] == {"food_credit_weekly_budget": 6.25}
    assert manager.economy.government.food_credit_policy == "off"
    manager.initialize({**base, "initial_policy": {"food_credit_policy": "on"}})
    opening = manager.setup_config["applied_policy"]
    assert (opening["food_credit_policy"], opening["food_credit_weekly_budget"]) == ("on", 7.5)


def test_household_balances_and_redemptions_reconcile_to_fiscal_frame(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    manager = SimulationManager(session_id="food-credit-frame")
    manager.initialize({"seed": 7, "num_households": 5, "tracked_households": 5,
                        "num_firms": 1, "payment_sequence": "income_first",
                        "payment_food_credit_enabled": True, "horizon_ticks": 4})
    frames = []
    messages = []

    class Socket:
        async def send_text(self, data):
            frames.append(json.loads(data))

        async def send_json(self, data):
            messages.append(data)

    async def run():
        manager.active_websocket = Socket()
        manager.start_background_loop()
        await asyncio.wait_for(manager.run_task, timeout=30)

    asyncio.run(run())
    assert not [msg for msg in messages if "error" in msg], messages
    assert [frame["tick"] for frame in frames] == [1, 2, 3, 4]
    previous = 0
    for frame in frames:
        metrics = frame["metrics"]
        fiscal = metrics["payment"]["fiscal"]["food_credit"]
        people = metrics["trackedSubjects"]
        assert len(people) == 5
        assert fiscal["issued"] == 2.5
        assert sum(p["groceryCardSpent"] for p in people) == pytest.approx(fiscal["redeemed"])
        assert sum(p["groceryCardBalance"] for p in people) == pytest.approx(fiscal["outstanding"])
        assert fiscal["outstanding"] == pytest.approx(previous + fiscal["issued"] - fiscal["redeemed"])
        previous = fiscal["outstanding"]
