import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402
from _ws import setup, until  # noqa: E402

SMALL = {"num_households": 30, "num_firms": 1, "seed": 7}


def _client(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    return TestClient(server.app), registry


def _session(ws):
    return until(ws, lambda m: m.get("type") == "SESSION")


def test_initial_policy_is_applied_before_the_first_tick_and_echoed(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        reply = setup(ws, {**SMALL, "initial_policy": {"minimum_wage_policy": "high", "benefit_level": "high",
                                                        "wage_tax_rate": 0.2}})
        assert reply["type"] == "SETUP_COMPLETE", reply
        applied = reply["config"]["applied_policy"]
        assert applied["minimum_wage_policy"] == "high" and applied["benefit_level"] == "high"
        assert abs(applied["wage_tax_rate"] - 0.2) < 1e-9
        manager = registry.get(session["sessionId"])
        assert manager.economy.government.wage_tax_rate == 0.2
        floor = float(manager.economy.government.get_minimum_wage())
        assert all(firm.wage_offer >= floor for firm in manager.economy.firms)
        assert manager.pending_config_updates == [] and manager.policy_changes == []


def test_legacy_raw_tax_keys_are_folded_into_the_vector(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        reply = setup(ws, {**SMALL, "wage_tax": 0.25, "profit_tax": 0.3})
        assert reply["type"] == "SETUP_COMPLETE"
        assert abs(reply["config"]["applied_policy"]["wage_tax_rate"] - 0.25) < 1e-9
        assert registry.get(session["sessionId"]).economy.government.profit_tax_rate == 0.3
        error = setup(ws, {**SMALL, "wage_tax": 0.9})
        assert "error" in error and "wage_tax_rate" in error["error"]


def test_invalid_initial_policy_failssetup(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        _session(ws)
        error = setup(ws, {**SMALL, "initial_policy": {"benefit_level": "generous"}})
        assert "error" in error and "benefit_level" in error["error"]


def test_config_while_paused_returns_receipt_with_applied_and_rejected(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        assert setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        ws.send_json({"command": "CONFIG", "config": {"benefitLevel": "high", "wageTax": 0.9}})
        receipt = until(ws, lambda m: m.get("type") == "CONFIG_APPLIED" or "error" in m)
        assert receipt["type"] == "CONFIG_APPLIED", receipt
        assert receipt["applied"]["benefit_level"] == "high"
        assert "wage_tax_rate" in receipt["rejected"] and "wage_tax_rate" not in receipt["applied"]
        assert receipt["effectiveTick"] == 1
        manager = registry.get(session["sessionId"])
        assert manager.economy.government.wage_tax_rate != 0.9
        assert manager.policy_changes[0]["actionId"] == receipt["actionId"]


SUBSIDY_RULE = "sector_subsidy_level above 0 needs a sector_subsidy_target other than 'none'"
ALL_TARGET_RULE = "bailout_policy 'all' covers every sector, so bailout_target must be 'none'"
ALL_BUDGET_RULE = "bailout_policy 'all' needs a bailout_budget above 0"


def _config(ws, config):
    ws.send_json({"command": "CONFIG", "config": config})
    receipt = until(ws, lambda m: m.get("type") == "CONFIG_APPLIED" or "error" in m)
    assert receipt.get("type") == "CONFIG_APPLIED", receipt
    return receipt


def test_lean_group_rule_rejects_only_the_levers_of_the_failing_group(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        assert setup(ws, {**SMALL, "frame_profile": "lean"})["type"] == "SETUP_COMPLETE"
        manager = registry.get(session["sessionId"])
        receipt = _config(ws, {"sectorSubsidyLevel": 25, "wageTax": 0.2})
        assert receipt["applied"] == {"wage_tax_rate": 0.2}
        assert receipt["rejected"] == {"sector_subsidy_level": SUBSIDY_RULE}
        assert manager.economy.government.wage_tax_rate == 0.2
        assert manager._snapshot_government_levers()["sector_subsidy_level"] == 0

        receipt = _config(ws, {"bailoutPolicy": "all", "bailoutTarget": "food", "benefitLevel": "high"})
        assert receipt["applied"] == {"benefit_level": "high"}
        assert receipt["rejected"] == {"bailout_policy": ALL_TARGET_RULE, "bailout_target": ALL_TARGET_RULE}
        assert manager._snapshot_government_levers()["bailout_policy"] == "off"

        receipt = _config(ws, {"bailoutPolicy": "all"})
        assert receipt["applied"] == {} and receipt["rejected"] == {"bailout_policy": ALL_BUDGET_RULE}

        receipt = _config(ws, {"bailoutPolicy": "all", "bailoutBudget": 5000})
        assert receipt["rejected"] == {} and receipt["applied"] == {"bailout_policy": "all", "bailout_budget": 5000}
        assert manager._snapshot_government_levers()["bailout_target"] == "none"


def test_lean_switch_from_one_sector_to_any_business_bailouts(monkeypatch):
    client, registry = _client(monkeypatch)
    sector = {"bailout_policy": "sector", "bailout_target": "food", "bailout_budget": 25000}
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        assert setup(ws, {**SMALL, "frame_profile": "lean", "initial_policy": sector})["type"] == "SETUP_COMPLETE"
        manager = registry.get(session["sessionId"])

        # "any business" alone leaves the food target behind, which the rule refuses.
        receipt = _config(ws, {"bailout_policy": "all"})
        assert receipt["applied"] == {} and receipt["rejected"] == {"bailout_policy": ALL_TARGET_RULE}
        assert manager._snapshot_government_levers()["bailout_policy"] == "sector"

        # The Town hall sends the choice with the cleared target; the budget carries over.
        receipt = _config(ws, {"bailout_policy": "all", "bailout_target": "none"})
        assert receipt["rejected"] == {}
        assert receipt["applied"] == {"bailout_policy": "all", "bailout_target": "none"}
        levers = manager._snapshot_government_levers()
        assert (levers["bailout_policy"], levers["bailout_target"], levers["bailout_budget"]) == ("all", "none", 25000)


def test_legacy_applies_levers_one_by_one_without_group_rules(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        assert setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        receipt = _config(ws, {"bailoutPolicy": "all"})
        assert receipt["applied"] == {"bailout_policy": "all"} and receipt["rejected"] == {}
        receipt = _config(ws, {"sectorSubsidyLevel": 25, "benefitLevel": "high"})
        assert receipt["applied"] == {"sector_subsidy_level": 25, "benefit_level": "high"} and receipt["rejected"] == {}
        assert registry.get(session["sessionId"]).economy.government.bailout_policy == "all"


def test_canonical_lever_names_are_strict_and_camel_case_aliases_keep_their_coercion(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        assert setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        manager = registry.get(session["sessionId"])
        for strict in ({"bailout_budget": 1000000}, {"public_works": True}, {"sector_subsidy_level": 30}):
            receipt = _config(ws, strict)
            [(lever, _)] = strict.items()
            assert receipt["applied"] == {} and lever in receipt["rejected"], receipt
        assert manager._snapshot_government_levers()["bailout_budget"] == 0
        assert manager._snapshot_government_levers()["public_works"] == "off"

        assert _config(ws, {"bailoutBudget": 1000000})["applied"] == {"bailout_budget": 50000}
        assert _config(ws, {"publicWorks": True})["applied"] == {"public_works": "on"}
        assert _config(ws, {"sectorSubsidyLevel": 30})["applied"] == {"sector_subsidy_level": 25}
        # a canonical value SETUP accepts is applied as SETUP would apply it
        assert _config(ws, {"bailout_budget": "10000"})["applied"] == {"bailout_budget": 10000}


def test_canonical_lever_names_are_accepted_for_replay(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        _session(ws)
        assert setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        ws.send_json({"command": "CONFIG", "config": {"benefit_level": "high"}})
        receipt = until(ws, lambda m: m.get("type") == "CONFIG_APPLIED" or "error" in m)
        assert receipt["applied"] == {"benefit_level": "high"}


def test_config_while_running_is_queued_then_applied_at_a_tick_boundary(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        _session(ws)
        assert setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        ws.send_json({"command": "START"})
        until(ws, lambda m: m.get("type") == "STARTED")
        ws.send_json({"command": "CONFIG", "config": {"publicWorks": True, "wageTax": 0.9}})
        queued = until(ws, lambda m: m.get("type") == "CONFIG_QUEUED")
        applied = until(ws, lambda m: m.get("type") == "CONFIG_APPLIED")
        assert applied["actionId"] == queued["actionId"]
        assert applied["applied"]["public_works"] == "on"
        assert "wage_tax_rate" in applied["rejected"] and "wage_tax_rate" not in applied["applied"]
        assert applied["effectiveTick"] >= 1
        ws.send_json({"command": "STOP"})
        until(ws, lambda m: m.get("type") == "STOPPED")


class _FakeWarehouse:
    def __init__(self):
        self.policies = []

    def create_run(self, run):
        pass

    def insert_policy_config(self, policy):
        self.policies.append(policy)


def test_persisted_taxes_match_the_applied_vector_not_the_raw_legacy_keys(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    manager = server.SimulationManager(session_id="applied-taxes")
    warehouse = _FakeWarehouse()
    manager.enable_warehouse = True
    manager.warehouse_manager = warehouse
    manager.initialize({**SMALL, "wage_tax": 0.25, "profit_tax": 0.3,
                        "initial_policy": {"wage_tax_rate": 0.2}})
    assert manager.economy.government.wage_tax_rate == 0.2
    assert manager.setup_config["applied_policy"]["wage_tax_rate"] == 0.2
    assert [(p.wage_tax, p.profit_tax) for p in warehouse.policies] == [(0.2, 0.3)]


def test_non_finite_and_overflowing_config_values_are_rejected_per_lever(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        _session(ws)
        assert setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        ws.send_json({"command": "CONFIG", "config": {"wageTax": 10**400, "bailoutBudget": "1e309",
                                                      "minimumWage": 10**400, "benefitLevel": "high"}})
        receipt = until(ws, lambda m: m.get("type") == "CONFIG_APPLIED" or "error" in m)
        assert receipt["type"] == "CONFIG_APPLIED", receipt
        assert {"wage_tax_rate", "bailout_budget"} <= set(receipt["rejected"])
        assert receipt["applied"]["benefit_level"] == "high"


def test_stop_drains_queued_config_before_replying_so_it_cannot_overwrite_later_changes(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        assert setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        manager = registry.get(session["sessionId"])
        ws.send_json({"command": "START"})
        until(ws, lambda m: m.get("type") == "STARTED")
        ws.send_json({"command": "CONFIG", "config": {"benefitLevel": "high"}})
        queued = until(ws, lambda m: m.get("type") == "CONFIG_QUEUED")
        ws.send_json({"command": "STOP"})
        before_stop = []
        until(ws, lambda m: before_stop.append(m) or m.get("type") == "STOPPED")
        assert any(m.get("type") == "CONFIG_APPLIED" and m["actionId"] == queued["actionId"] for m in before_stop)
        assert manager.pending_config_updates == []

        ws.send_json({"command": "CONFIG", "config": {"benefitLevel": "low"}})
        assert until(ws, lambda m: m.get("type") == "CONFIG_APPLIED")["applied"] == {"benefit_level": "low"}
        tick_before = manager.tick
        ws.send_json({"command": "START"})
        until(ws, lambda m: "metrics" in m and m.get("tick", 0) > tick_before)
        assert manager.economy.government.benefit_level == "low"
        ws.send_json({"command": "STOP"})
        until(ws, lambda m: m.get("type") == "STOPPED")
        assert manager.economy.government.benefit_level == "low"


def test_reset_discards_queued_config(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        assert setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        manager = registry.get(session["sessionId"])
        manager.pending_config_updates.append(("stale", {"benefitLevel": "high"}))
        ws.send_json({"command": "RESET"})
        until(ws, lambda m: m.get("type") == "RESET")
        assert manager.pending_config_updates == []
        assert manager.economy.government.benefit_level != "high"
