# Frontend Redesign Phase 1: Backend Widening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the EcoSim backend so one browser can run one to four matched "towns" as an experiment and receive, every tick, the curated metrics, full firm list, event stream, household sample and lifecycle signals the new newcomer-facing frontend needs.

**Architecture:** All work is in the FastAPI/WebSocket layer (`backend/server.py`) plus four new small pure modules it calls: `experiments.py` (server-owned experiment record, ownership, shared-world check and household cap), `policy_vectors.py` (validated policy vectors, used at SETUP and at runtime), `frame_events.py` (typed per-tick events, firm directory, closed-firm archive) and `frame_projection.py` (curated metrics computed fresh each tick, plus the full firm list). The existing tick frame keeps every old key so the current React app keeps working; new keys are added beside them under a `schemaVersion` of `frame-2`. A session recorder and a concurrent full-path benchmark close the phase.

**Tech Stack:** Python 3.11, FastAPI + Starlette `TestClient` websockets, `websockets` client and `uvicorn` for the concurrent benchmark, Pydantic v2, pytest (`.venv/bin/python -m pytest`), ruff (`select = ["E9","F63","F7","F82"]`, line length 120).

**Spec:** `docs/superpowers/specs/2026-09-24-frontend-learning-redesign-design.md` (sections 3, 6, 8, 9, 10). Build order from `docs/reviews/2026-09-24-frontend-redesign-spec-check2.md` section C. This is the second draft; the first was audited in `docs/reviews/2026-09-24-phase1-plan-audit.md` and every item in its sections A, B, D and E is addressed below. Section C deviations that remain are listed under "Accepted deviations" at the end.

## Global Constraints

- Branch `feat/frontend-redesign-phase1` already exists with the payment revamp and the design documents committed. Task 0 verifies the tree is clean before any edit.
- Run tests with `.venv/bin/python -m pytest <path> -q` from the repository root. `pyproject.toml` sets `pythonpath = ["backend"]`, so test modules import `server`, `economy`, `agents`, `policy_schema` as top-level names, exactly like `backend/tests_server/test_server_sessions.py` does. Never pipe a test or benchmark run through `tail` when its result is a gate; keep the complete output and exit status in the task notes.
- Lint with `.venv/bin/python -m ruff check .` before every commit.
- Never edit `openwiki/`. Never edit files under `frontend-react/src/` except `frontend-react/src/test/fixtures/` in Task 7.
- Keep every existing key of the tick frame (the `state = {...}` dict in `_run_loop_scoped`) unchanged in name and meaning. New keys are additive.
- Anchor every edit in `backend/server.py` on the symbol named in the step, not on a line number; line numbers in this document are approximate and have shifted.
- All mutation of `self.economy` and all `random`/`numpy.random` use inside `SimulationManager` happens under `with use_config(self.config), self._random_scope():` (the pattern of `initialize()` and the tick step). Household sampling uses its own `random.Random` instance and never the session stream.
- Every tick-frame field added by this plan has a stated unit, producer, freshness and null behaviour in its task's Interfaces block. A field with no such line is a plan defect.
- Household budget: `10_000` per experiment. Max arms: `4`. Per-arm cap: `10_000 // arm_count`. Default households per arm: `1_000`. Default horizon: `260` ticks. Tracked household sample: `40`. Max pins: `8`. Detailed events per tick: `50`. Closed-firm archive window: `52` ticks.
- Tests set `ECOSIM_ENABLE_WAREHOUSE` explicitly through `monkeypatch.setenv` (`"0"` unless the test is about the warehouse). `SimulationManager` reads it at construction, which happens when a websocket connects, so set it before `websocket_connect`.
- Tests use small economies (`num_households` 30 to 60, `num_firms` 1) so each finishes in seconds. Every websocket receive helper bounds its loop (see `_until` in Task 3) so a missing message fails instead of hanging.
- Commit after every task with the message given in the task; end commit messages with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. A failed performance gate in Task 8 blocks handoff; do not weaken a gate to pass it.

## Review Focus

1. A single-arm experiment asking for the whole budget (`arm_count=1`, `num_households=10000`) must be accepted; the cap is `10_000 // 1`. Test pinned in Task 1.
2. A CONFIG sent while running with one valid lever and one out-of-range tax must produce one `CONFIG_APPLIED` receipt listing the valid lever under `applied` and the tax under `rejected`, and the tax must be unchanged in the economy. Test pinned in Task 2.
3. EXTEND sent mid-run, before `HORIZON_REACHED`, must raise the horizon without stopping the loop and without an early `HORIZON_REACHED`. Test pinned in Task 3.
4. TRACK `follow` with a household id that does not exist must reply with an error and leave the tracked set unchanged. Test pinned in Task 4.
5. A firm that closes is reported as closed exactly once, on the tick it disappears, and never again on later ticks. Test pinned in Task 5.

---

### Task 0: Baseline

**Files:** none changed.

- [ ] **Step 1: Confirm the branch and a clean tree**

Run: `git branch --show-current && git status --short | wc -l`
Expected: `feat/frontend-redesign-phase1` and `0`. If the count is not zero, stop and report.

- [ ] **Step 2: Record the baseline test run**

Run: `.venv/bin/python -m pytest backend/tests_server backend/tests_contracts -q`
Expected: all passed (contracts were 392 passed plus one xfail at the time of writing). Record the exact counts in the task notes; every later task must keep them passing.

---

### Task 1: Experiment registry, ownership, shared world and household cap

**Files:**
- Create: `backend/experiments.py`
- Modify: `backend/server.py` (`SetupConfig`, `SimulationManager.__init__`, `_initialize_scoped`, `_open_warehouse_run`, `SessionRegistry.close_session`)
- Test: `backend/tests_server/test_experiments.py`

**Interfaces:**
- Produces: `experiments.ExperimentRegistry` with `reserve(*, experiment_id: str, arm_label: str, arm_count: int, households: int, session_id: str, owner: str | None, world_key: str) -> ArmReservation`, `release(session_id: str) -> None`, `describe(experiment_id: str) -> dict | None`, `per_arm_cap(arm_count: int) -> int`; `experiments.ExperimentError(ValueError)`; constants `HOUSEHOLD_BUDGET = 10_000`, `MAX_ARMS = 4`.
- Produces: `server.experiment_registry` module global; `SimulationManager.experiment_id`, `.arm_label`, `.arm_count`; `SetupConfig.experiment_id`, `.arm_label`, `.arm_count`, `.experiment_owner`; `SimulationManager._initialize_economy(validated, config, num_households, num_firms, seed)`; `setup_config["experiment"]` dict (`id`, `armLabel`, `armCount`, `householdCap`) or `None`, echoed in `SETUP_COMPLETE`.
- World key: `json.dumps({"seed", "num_firms", "disable_stabilizers", "disabled_agents", every SetupConfig field starting with "payment_"}, sort_keys=True)`; arms of one experiment must share it.

- [ ] **Step 1: Write the failing registry tests**

Create `backend/tests_server/test_experiments.py`:

```python
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402
from experiments import HOUSEHOLD_BUDGET, MAX_ARMS, ExperimentError, ExperimentRegistry  # noqa: E402

WORLD = '{"seed": 7}'


def _reserve(registry, **overrides):
    params = dict(experiment_id="exp-1", arm_label="Town A", arm_count=2, households=1_000, session_id="s1",
                  owner="owner-1", world_key=WORLD)
    params.update(overrides)
    return registry.reserve(**params)


def test_per_arm_cap_splits_the_budget_evenly():
    registry = ExperimentRegistry()
    assert registry.per_arm_cap(1) == HOUSEHOLD_BUDGET
    assert registry.per_arm_cap(2) == 5_000
    assert registry.per_arm_cap(3) == 3_333
    assert registry.per_arm_cap(4) == 2_500


def test_single_arm_may_take_the_whole_budget():
    registry = ExperimentRegistry()
    reservation = _reserve(registry, arm_count=1, households=HOUSEHOLD_BUDGET)
    assert reservation.households == HOUSEHOLD_BUDGET
    assert registry.describe("exp-1")["households_reserved"] == HOUSEHOLD_BUDGET


def test_arm_over_cap_is_rejected_and_nothing_is_reserved():
    registry = ExperimentRegistry()
    with pytest.raises(ExperimentError, match="cap"):
        _reserve(registry, households=5_001)
    assert registry.describe("exp-1") is None


def test_duplicate_label_full_experiment_and_arm_count_mismatch_are_rejected():
    registry = ExperimentRegistry()
    _reserve(registry)
    with pytest.raises(ExperimentError, match="label"):
        _reserve(registry, session_id="s2")
    with pytest.raises(ExperimentError, match="arm count"):
        _reserve(registry, arm_label="Town B", arm_count=3, session_id="s2")
    _reserve(registry, arm_label="Town B", session_id="s2")
    with pytest.raises(ExperimentError, match="full"):
        _reserve(registry, arm_label="Town C", session_id="s3")
    with pytest.raises(ExperimentError, match="arms"):
        _reserve(registry, experiment_id="exp-2", arm_count=MAX_ARMS + 1, households=10, session_id="s9")


def test_second_owner_and_different_world_are_rejected():
    registry = ExperimentRegistry()
    _reserve(registry)
    with pytest.raises(ExperimentError, match="owner"):
        _reserve(registry, arm_label="Town B", session_id="s2", owner="someone-else")
    with pytest.raises(ExperimentError, match="world"):
        _reserve(registry, arm_label="Town B", session_id="s2", world_key='{"seed": 8}')
    assert registry.describe("exp-1")["arms"] == {"Town A": 1_000}


def test_release_frees_the_arm_and_removes_empty_experiments():
    registry = ExperimentRegistry()
    _reserve(registry)
    registry.release("s1")
    assert registry.describe("exp-1") is None
    registry.release("s1")  # idempotent


def _connect(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=4)
    experiments = ExperimentRegistry()
    monkeypatch.setattr(server, "session_registry", registry)
    monkeypatch.setattr(server, "experiment_registry", experiments)
    return TestClient(server.app), registry, experiments


def _setup(ws, **config):
    ws.send_json({"command": "SETUP", "config": config})
    for _ in range(50):
        msg = ws.receive_json()
        if msg.get("type") == "SETUP_COMPLETE" or "error" in msg:
            return msg
    raise AssertionError("no SETUP_COMPLETE or error within 50 messages")


EXP = {"num_households": 30, "num_firms": 1, "seed": 7, "experiment_id": "exp-ws", "arm_label": "Town A",
       "arm_count": 2, "experiment_owner": "browser-1"}


def test_setup_reserves_echoes_and_a_failed_setup_leaves_nothing_runnable(monkeypatch):
    client, registry, experiments = _connect(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        reply = _setup(ws, **EXP)
        assert reply["type"] == "SETUP_COMPLETE", reply
        assert reply["config"]["experiment"] == {"id": "exp-ws", "armLabel": "Town A", "armCount": 2, "householdCap": 5_000}
        assert experiments.describe("exp-ws")["households_reserved"] == 30

        error = _setup(ws, **{**EXP, "num_households": 6_000})
        assert "error" in error and "cap" in error["error"]
        assert experiments.describe("exp-ws") is None
        manager = registry.get(session["sessionId"])
        assert manager.economy is None  # nothing runnable is left behind
        ws.send_json({"command": "START"})
        started = ws.receive_json()
        assert started.get("type") == "STARTED"  # legacy auto-initialize, no experiment fields
        assert manager.experiment_id is None
        ws.send_json({"command": "STOP"})
        while ws.receive_json().get("type") != "STOPPED":
            pass


def test_disconnect_releases_a_live_reservation(monkeypatch):
    client, _, experiments = _connect(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert _setup(ws, **EXP)["type"] == "SETUP_COMPLETE"
        assert experiments.describe("exp-ws")["households_reserved"] == 30
    assert experiments.describe("exp-ws") is None


def test_second_arm_must_share_the_world(monkeypatch):
    client, _, _ = _connect(monkeypatch)
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        first.receive_json()
        second.receive_json()
        assert _setup(first, **EXP)["type"] == "SETUP_COMPLETE"
        error = _setup(second, **{**EXP, "arm_label": "Town B", "seed": 8})
        assert "error" in error and "world" in error["error"]
        ok = _setup(second, **{**EXP, "arm_label": "Town B"})
        assert ok["type"] == "SETUP_COMPLETE"


def test_setup_without_experiment_fields_still_works(monkeypatch):
    client, _, _ = _connect(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        reply = _setup(ws, num_households=30, num_firms=1, seed=7)
        assert reply["type"] == "SETUP_COMPLETE"
        assert reply["config"]["experiment"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests_server/test_experiments.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'experiments'`.

- [ ] **Step 3: Create the registry module**

Create `backend/experiments.py`:

```python
"""Server-owned experiment records: which sessions are arms of one matched comparison.

Pure module: no FastAPI, no Economy. The registry enforces the household budget
across arms, one owner per experiment, and one shared world configuration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional

HOUSEHOLD_BUDGET = 10_000
MAX_ARMS = 4


class ExperimentError(ValueError):
    """A reservation request that the registry refuses."""


@dataclass
class ArmReservation:
    experiment_id: str
    arm_label: str
    session_id: str
    households: int


@dataclass
class ExperimentRecord:
    experiment_id: str
    arm_count: int
    owner: Optional[str]
    world_key: str
    created_at: float = field(default_factory=time.time)
    arms: Dict[str, ArmReservation] = field(default_factory=dict)  # keyed by arm_label

    @property
    def households_reserved(self) -> int:
        return sum(arm.households for arm in self.arms.values())


class ExperimentRegistry:
    def __init__(self, budget: int = HOUSEHOLD_BUDGET, max_arms: int = MAX_ARMS):
        self.budget = int(budget)
        self.max_arms = int(max_arms)
        self._experiments: Dict[str, ExperimentRecord] = {}
        self._by_session: Dict[str, ArmReservation] = {}

    def per_arm_cap(self, arm_count: int) -> int:
        return self.budget // max(1, int(arm_count))

    def reserve(
        self,
        *,
        experiment_id: str,
        arm_label: str,
        arm_count: int,
        households: int,
        session_id: str,
        owner: Optional[str],
        world_key: str,
    ) -> ArmReservation:
        experiment_id = str(experiment_id).strip()
        arm_label = str(arm_label).strip()
        if not experiment_id or not arm_label:
            raise ExperimentError("experiment_id and arm_label are required")
        if not 1 <= int(arm_count) <= self.max_arms:
            raise ExperimentError(f"arm_count must be between 1 and {self.max_arms} arms")
        cap = self.per_arm_cap(arm_count)
        if int(households) > cap:
            raise ExperimentError(f"{households} households exceeds the per-arm cap of {cap} for {arm_count} arms")
        # A session that reserves again replaces its earlier reservation.
        self.release(session_id)

        record = self._experiments.get(experiment_id)
        if record is None:
            record = ExperimentRecord(experiment_id=experiment_id, arm_count=int(arm_count), owner=owner, world_key=world_key)
        else:
            if record.arm_count != int(arm_count):
                raise ExperimentError(
                    f"experiment {experiment_id} was created with arm count {record.arm_count}, not {arm_count}"
                )
            if record.owner != owner:
                raise ExperimentError(f"experiment {experiment_id} belongs to another owner")
            if record.world_key != world_key:
                raise ExperimentError(f"experiment {experiment_id} uses a different world (seed, firms, payment rules)")
        if arm_label in record.arms:
            raise ExperimentError(f"arm label '{arm_label}' is already taken in experiment {experiment_id}")
        if len(record.arms) >= record.arm_count:
            raise ExperimentError(f"experiment {experiment_id} is full ({record.arm_count} arms)")
        if record.households_reserved + int(households) > self.budget:
            raise ExperimentError(f"experiment {experiment_id} would exceed the household budget of {self.budget}")

        reservation = ArmReservation(
            experiment_id=experiment_id, arm_label=arm_label, session_id=str(session_id), households=int(households)
        )
        record.arms[arm_label] = reservation
        self._experiments[experiment_id] = record
        self._by_session[str(session_id)] = reservation
        return reservation

    def release(self, session_id: str) -> None:
        reservation = self._by_session.pop(str(session_id), None)
        if reservation is None:
            return
        record = self._experiments.get(reservation.experiment_id)
        if record is None:
            return
        record.arms.pop(reservation.arm_label, None)
        if not record.arms:
            self._experiments.pop(reservation.experiment_id, None)

    def describe(self, experiment_id: str) -> Optional[dict]:
        record = self._experiments.get(str(experiment_id))
        if record is None:
            return None
        return {
            "experiment_id": record.experiment_id,
            "arm_count": record.arm_count,
            "owner": record.owner,
            "per_arm_cap": self.per_arm_cap(record.arm_count),
            "households_reserved": record.households_reserved,
            "arms": {label: arm.households for label, arm in record.arms.items()},
        }
```

- [ ] **Step 4: Add the SETUP fields and wire the registry into the server**

In `backend/server.py`, after the line `from policy_schema import ORDERED_LEVERS` add:

```python
from experiments import ExperimentError, ExperimentRegistry  # noqa: F401
```

In `SetupConfig`, after the `disabled_agents` field add:

```python
    experiment_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    arm_label: Optional[str] = Field(default=None, min_length=1, max_length=40)
    arm_count: int = Field(default=1, ge=1, le=4)
    experiment_owner: Optional[str] = Field(default=None, min_length=1, max_length=64)
```

and after `validate_agent_names` add:

```python
    @model_validator(mode="after")
    def validate_experiment_fields(self):
        if (self.experiment_id is None) != (self.arm_label is None):
            raise ValueError("experiment_id and arm_label must be given together")
        return self

    def world_key(self, seed: int) -> str:
        """The part of the world every arm of an experiment must share."""
        payload = {name: getattr(self, name) for name in type(self).model_fields if name.startswith("payment_")}
        payload.update({"seed": int(seed), "num_firms": self.num_firms, "disable_stabilizers": self.disable_stabilizers,
                        "disabled_agents": sorted(self.disabled_agents)})
        return json.dumps(payload, sort_keys=True, default=str)
```

Directly above `class SimulationManager:` add the module global:

```python
experiment_registry = ExperimentRegistry()
```

In `SimulationManager.__init__`, after `self.setup_config: Dict[str, Any] = {}` add:

```python
        self.experiment_registry: ExperimentRegistry = experiment_registry
        self.experiment_id: Optional[str] = None
        self.arm_label: Optional[str] = None
        self.arm_count: int = 1
```

Restructure `_initialize_scoped`. Its current body is: `if config is None: config = {}`, `self.stop_background_loop(cancel=True)`, `validated = SetupConfig(**config)`, the `for payment_field ...` loop, `self.setup_config = validated.model_dump()`, the `num_households`/`num_firms`/`seed` assignments, `self.setup_config["seed"] = seed`, then everything from `for opening_rate in ("wage_tax", "profit_tax"):` down to `logger.info("Economy initialized")`. Replace the part from `validated = SetupConfig(**config)` through `self.setup_config["seed"] = seed` with:

```python
        # SETUP replaces the run. A SETUP that fails at any point leaves nothing
        # runnable behind, so START cannot resume an unreserved economy.
        self.economy = None
        validated = SetupConfig(**config)
        num_households = validated.num_households
        num_firms = validated.num_firms
        seed = int(validated.seed if validated.seed is not None else getattr(self.config, "random_seed", 0))

        self.experiment_registry.release(self.session_id)
        self.experiment_id = None
        self.arm_label = None
        self.arm_count = int(validated.arm_count)
        if validated.experiment_id is not None:
            self.experiment_registry.reserve(
                experiment_id=validated.experiment_id,
                arm_label=validated.arm_label,
                arm_count=self.arm_count,
                households=num_households,
                session_id=self.session_id,
                owner=validated.experiment_owner,
                world_key=validated.world_key(seed),
            )
            self.experiment_id = validated.experiment_id
            self.arm_label = validated.arm_label
        try:
            self._initialize_economy(validated, config, num_households, num_firms, seed)
        except Exception:
            self.experiment_registry.release(self.session_id)
            self.experiment_id = None
            self.arm_label = None
            self.economy = None
            raise

    def _initialize_economy(self, validated: "SetupConfig", config: Dict[str, Any], num_households: int, num_firms: int, seed: int):
        """Build the economy and tracking state for a validated SETUP."""
        for payment_field in (name for name in SetupConfig.model_fields if name.startswith("payment_")):
            setattr(self.config, payment_field, getattr(validated, payment_field))
        self.setup_config = validated.model_dump()
        self.setup_config["seed"] = seed
        self.setup_config["experiment"] = (
            {
                "id": validated.experiment_id,
                "armLabel": validated.arm_label,
                "armCount": self.arm_count,
                "householdCap": self.experiment_registry.per_arm_cap(self.arm_count),
            }
            if validated.experiment_id is not None
            else None
        )
```

The remainder of the old `_initialize_scoped` body, from the line `for opening_rate in ("wage_tax", "profit_tax"):` through `logger.info("Economy initialized")`, moves verbatim into `_initialize_economy` at the same eight-space method-body indentation; nothing is dedented. Delete the original copies of the lines that now live above (`for payment_field ...` loop, `self.setup_config = validated.model_dump()`, the three assignments, `self.setup_config["seed"] = seed`).

In `_open_warehouse_run`, change the `tags=` argument of `SimulationRun(...)` to:

```python
                tags=",".join(
                    part for part in (
                        f"backend={self.warehouse_backend}",
                        f"experiment={self.experiment_id}" if self.experiment_id else "",
                        f"arm={self.arm_label}" if self.arm_label else "",
                    ) if part
                ),
```

and after `effective_config["stabilizers"] = dict(self.stabilizer_state)` add:

```python
        effective_config["experiment_id"] = self.experiment_id
        effective_config["arm_label"] = self.arm_label
        effective_config["arm_count"] = self.arm_count
```

In `SessionRegistry.close_session`, after `session_manager.active_websocket = None` add:

```python
        session_manager.experiment_registry.release(session_id)
```

`websocket_endpoint`'s SETUP branch already catches `Exception` and replies `{"error": f"SETUP failed: {e}"}`, so an `ExperimentError` surfaces with its message.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests_server/test_experiments.py backend/tests_server/test_server_sessions.py backend/tests_server/test_payment_scenarios.py -q`
Expected: all PASS.

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/python -m ruff check .
git add backend/experiments.py backend/server.py backend/tests_server/test_experiments.py
git commit -m "feat(server): experiment registry with owner, shared world and per-arm household cap on SETUP

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Initial policy on SETUP, shared validation at runtime, CONFIG receipts

**Files:**
- Create: `backend/policy_vectors.py`
- Modify: `backend/server.py` (`SetupConfig`, `_initialize_scoped`, `_initialize_economy`, `_append_policy_change_ui_record`, `_normalize_runtime_policy_updates`, `_apply_config_updates`, `update_config`, the loop's pending-config block, the `CONFIG` branch of `websocket_endpoint`), `backend/tests_server/test_payment_scenarios.py` (one assertion)
- Test: `backend/tests_contracts/test_policy_vectors.py`, `backend/tests_server/test_initial_policy_and_receipts.py`

**Interfaces:**
- Produces: `policy_vectors.validate_policy_vector(vector: dict) -> dict` returning canonical lever names and coerced values, applying the group rules; raises `policy_vectors.PolicyVectorError(ValueError)`.
- Produces: `SetupConfig.initial_policy: Dict[str, Any]` (validated); legacy raw `wage_tax`/`profit_tax` SETUP keys are folded into `initial_policy` as `wage_tax_rate`/`profit_tax_rate` before validation and no longer bypass it; `setup_config["applied_policy"]` (the lever snapshot after SETUP) echoed in `SETUP_COMPLETE`.
- Produces: `SimulationManager.update_config(config_data) -> dict` returning `{"type": "CONFIG_APPLIED", ...}` when paused or `{"type": "CONFIG_QUEUED", "actionId", "tick"}` when running; `_apply_config_updates(config_data, action_id) -> dict` returning the receipt with keys `actionId`, `requested` (canonical lever names), `applied` (canonical names, values read back from the government), `rejected` (canonical name or `"_group"` to reason text), `effectiveTick`; `SimulationManager.pending_config_updates: list[tuple[str, dict]]`, cleared on SETUP together with `policy_changes`; policy change records gain `actionId`; warehouse `policy_actions` payloads gain `action_id`.
- `_normalize_runtime_policy_updates` accepts canonical lever names as well as the camelCase aliases, so a replay can resend a receipt's `applied` dict unchanged.

- [ ] **Step 1: Write the failing validator tests**

Create `backend/tests_contracts/test_policy_vectors.py`:

```python
import pytest

from policy_vectors import PolicyVectorError, validate_policy_vector


def test_empty_vector_is_allowed():
    assert validate_policy_vector({}) == {}


def test_taxes_are_coerced_to_float_and_range_checked():
    assert validate_policy_vector({"wage_tax_rate": "0.30"}) == {"wage_tax_rate": 0.30}
    with pytest.raises(PolicyVectorError, match="wage_tax_rate"):
        validate_policy_vector({"wage_tax_rate": 0.9})


def test_ordered_and_enum_levers_must_be_known_values():
    assert validate_policy_vector({"benefit_level": "high", "public_works": "on"}) == {
        "benefit_level": "high", "public_works": "on",
    }
    with pytest.raises(PolicyVectorError, match="benefit_level"):
        validate_policy_vector({"benefit_level": "generous"})
    with pytest.raises(PolicyVectorError, match="unknown lever"):
        validate_policy_vector({"birth_rate": 0.1})


def test_integer_levers_accept_numeric_strings():
    assert validate_policy_vector({"sector_subsidy_target": "food", "sector_subsidy_level": "25"}) == {
        "sector_subsidy_target": "food", "sector_subsidy_level": 25,
    }


def test_grouped_levers_validate_together():
    with pytest.raises(PolicyVectorError, match="sector_subsidy_target"):
        validate_policy_vector({"sector_subsidy_level": 25})
    with pytest.raises(PolicyVectorError, match="bailout_budget"):
        validate_policy_vector({"bailout_policy": "all", "bailout_target": "food"})
    assert validate_policy_vector({"bailout_policy": "all", "bailout_target": "food", "bailout_budget": 5000}) == {
        "bailout_policy": "all", "bailout_target": "food", "bailout_budget": 5000,
    }
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests_contracts/test_policy_vectors.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'policy_vectors'`.

- [ ] **Step 3: Create the validator**

Create `backend/policy_vectors.py`:

```python
"""Validate a whole policy lever vector against the shared policy schema.

Used for SETUP's initial_policy and for the merged state after a runtime
CONFIG. Pure: imports only policy_schema.
"""

from __future__ import annotations

from typing import Any, Dict

from policy_schema import ORDERED_LEVERS, SIMPLE_ENUM_LEVERS, TAX_LIMITS, VALID_LEVERS


class PolicyVectorError(ValueError):
    """A lever vector that does not fit the schema."""


def _coerce_ordered(lever: str, value: Any) -> Any:
    allowed = ORDERED_LEVERS[lever]
    if all(isinstance(option, int) for option in allowed):
        try:
            value = int(float(value))
        except (TypeError, ValueError):
            raise PolicyVectorError(f"{lever} must be one of {allowed}, got {value!r}")
    if value not in allowed:
        raise PolicyVectorError(f"{lever} must be one of {allowed}, got {value!r}")
    return value


def validate_policy_vector(vector: Dict[str, Any]) -> Dict[str, Any]:
    """Return a canonical copy of *vector* or raise PolicyVectorError."""
    result: Dict[str, Any] = {}
    for lever, value in (vector or {}).items():
        if lever not in VALID_LEVERS:
            raise PolicyVectorError(f"unknown lever {lever!r}")
        if lever in TAX_LIMITS:
            low, high = TAX_LIMITS[lever]
            try:
                numeric = round(float(value), 4)
            except (TypeError, ValueError):
                raise PolicyVectorError(f"{lever} must be a number between {low} and {high}, got {value!r}")
            if not low <= numeric <= high:
                raise PolicyVectorError(f"{lever} must be between {low} and {high}, got {numeric}")
            result[lever] = numeric
        elif lever in ORDERED_LEVERS:
            result[lever] = _coerce_ordered(lever, value)
        elif lever in SIMPLE_ENUM_LEVERS:
            if value not in SIMPLE_ENUM_LEVERS[lever]:
                raise PolicyVectorError(f"{lever} must be one of {sorted(SIMPLE_ENUM_LEVERS[lever])}, got {value!r}")
            result[lever] = value

    level = result.get("sector_subsidy_level", 0)
    if level and result.get("sector_subsidy_target", "none") == "none":
        raise PolicyVectorError("sector_subsidy_level above 0 needs a sector_subsidy_target other than 'none'")
    if result.get("bailout_policy", "off") != "off":
        if result.get("bailout_target", "none") == "none":
            raise PolicyVectorError("bailout_policy needs a bailout_target other than 'none'")
        if not result.get("bailout_budget", 0):
            raise PolicyVectorError("bailout_policy needs a bailout_budget above 0")
    return result
```

- [ ] **Step 4: Run the validator tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests_contracts/test_policy_vectors.py -q`
Expected: 5 passed.

- [ ] **Step 5: Write the failing server tests**

Create `backend/tests_server/test_initial_policy_and_receipts.py`:

```python
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402

SMALL = {"num_households": 30, "num_firms": 1, "seed": 7}


def _client(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    return TestClient(server.app), registry


def _until(ws, predicate, limit=2000):
    for _ in range(limit):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError(f"no message matched within {limit} messages")


def _setup(ws, config):
    ws.send_json({"command": "SETUP", "config": config})
    return _until(ws, lambda m: m.get("type") == "SETUP_COMPLETE" or "error" in m)


def test_initial_policy_is_applied_before_the_first_tick_and_echoed(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        reply = _setup(ws, {**SMALL, "initial_policy": {"minimum_wage_policy": "high", "benefit_level": "high",
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
        session = ws.receive_json()
        reply = _setup(ws, {**SMALL, "wage_tax": 0.25, "profit_tax": 0.3})
        assert reply["type"] == "SETUP_COMPLETE"
        assert abs(reply["config"]["applied_policy"]["wage_tax_rate"] - 0.25) < 1e-9
        assert registry.get(session["sessionId"]).economy.government.profit_tax_rate == 0.3
        error = _setup(ws, {**SMALL, "wage_tax": 0.9})
        assert "error" in error and "wage_tax_rate" in error["error"]


def test_invalid_initial_policy_fails_setup(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        error = _setup(ws, {**SMALL, "initial_policy": {"benefit_level": "generous"}})
        assert "error" in error and "benefit_level" in error["error"]


def test_config_while_paused_returns_receipt_with_applied_and_rejected(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        assert _setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        ws.send_json({"command": "CONFIG", "config": {"benefitLevel": "high", "wageTax": 0.9}})
        receipt = _until(ws, lambda m: m.get("type") == "CONFIG_APPLIED" or "error" in m)
        assert receipt["type"] == "CONFIG_APPLIED", receipt
        assert receipt["applied"]["benefit_level"] == "high"
        assert "wage_tax_rate" in receipt["rejected"] and "wage_tax_rate" not in receipt["applied"]
        assert receipt["effectiveTick"] == 1
        manager = registry.get(session["sessionId"])
        assert manager.economy.government.wage_tax_rate != 0.9
        assert manager.policy_changes[0]["actionId"] == receipt["actionId"]


def test_group_rule_rejects_the_whole_lever_batch(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        assert _setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        ws.send_json({"command": "CONFIG", "config": {"sectorSubsidyLevel": 25, "benefitLevel": "high"}})
        receipt = _until(ws, lambda m: m.get("type") == "CONFIG_APPLIED" or "error" in m)
        assert receipt["applied"] == {} and "sector_subsidy_target" in receipt["rejected"]["_group"]
        manager = registry.get(session["sessionId"])
        assert manager._snapshot_government_levers().get("benefit_level") != "high"


def test_canonical_lever_names_are_accepted_for_replay(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert _setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        ws.send_json({"command": "CONFIG", "config": {"benefit_level": "high"}})
        receipt = _until(ws, lambda m: m.get("type") == "CONFIG_APPLIED" or "error" in m)
        assert receipt["applied"] == {"benefit_level": "high"}


def test_config_while_running_is_queued_then_applied_at_a_tick_boundary(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert _setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
        ws.send_json({"command": "START"})
        _until(ws, lambda m: m.get("type") == "STARTED")
        ws.send_json({"command": "CONFIG", "config": {"publicWorks": True, "wageTax": 0.9}})
        queued = _until(ws, lambda m: m.get("type") == "CONFIG_QUEUED")
        applied = _until(ws, lambda m: m.get("type") == "CONFIG_APPLIED")
        assert applied["actionId"] == queued["actionId"]
        assert applied["applied"]["public_works"] == "on"
        assert "wage_tax_rate" in applied["rejected"] and "wage_tax_rate" not in applied["applied"]
        assert applied["effectiveTick"] >= 1
        ws.send_json({"command": "STOP"})
        _until(ws, lambda m: m.get("type") == "STOPPED")
```

- [ ] **Step 6: Run them to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests_server/test_initial_policy_and_receipts.py -q`
Expected: FAIL (`applied_policy` missing from SETUP_COMPLETE; no `CONFIG_APPLIED` message).

- [ ] **Step 7: Implement initial policy, shared validation, receipts and the queue**

Imports in `backend/server.py`: change `from policy_schema import ORDERED_LEVERS` to `from policy_schema import ORDERED_LEVERS, VALID_LEVERS, normalize_current_policy` and add `from policy_vectors import PolicyVectorError, validate_policy_vector`.

In `SetupConfig`, after `experiment_owner` add:

```python
    initial_policy: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("initial_policy", mode="after")
    @classmethod
    def validate_initial_policy(cls, v):
        return validate_policy_vector(v or {})
```

In `_initialize_scoped`, before `validated = SetupConfig(**config)`, fold the legacy raw keys into the vector:

```python
        config = dict(config)
        legacy_taxes = {}
        if "wage_tax" in config:
            legacy_taxes["wage_tax_rate"] = config["wage_tax"]
        if "profit_tax" in config:
            legacy_taxes["profit_tax_rate"] = config["profit_tax"]
        config["initial_policy"] = {**legacy_taxes, **dict(config.get("initial_policy") or {})}
```

In `_initialize_economy`, delete the two raw override lines (`if "wage_tax" in config: self.economy.government.wage_tax_rate = ...` and the `profit_tax` twin) and put in their place:

```python
        # Validated initial policy vector: presets, custom arms and the legacy tax keys all start here.
        for lever, value in (validated.initial_policy or {}).items():
            self.economy.government.set_lever(lever, value)
        if "minimum_wage_policy" in (validated.initial_policy or {}):
            min_wage = float(self.economy.government.get_minimum_wage())
            for firm in self.economy.firms:
                if firm.wage_offer < min_wage:
                    firm.wage_offer = min_wage
        self.setup_config["applied_policy"] = self._snapshot_government_levers()
        self.pending_config_updates = []
        self.policy_changes = []
```

This must come before `self._open_warehouse_run(...)` so the persisted `PolicyConfig` reflects the vector. Keep the `self.setup_config[opening_rate] = config[opening_rate]` echo loop so the old client still sees `wage_tax`/`profit_tax`.

Change `_append_policy_change_ui_record` to:

```python
    def _append_policy_change_ui_record(self, policy: str, value: Any, reason: str, action_id: Optional[str] = None) -> None:
        """Maintain the small recent-policy list used by the frontend."""
        change_record = {"tick": self.tick, "policy": policy, "value": value, "reason": reason, "actionId": action_id}
        self.policy_changes.insert(0, change_record)
        if len(self.policy_changes) > 5:
            self.policy_changes.pop()
```

In `__init__`, change `self.pending_config_updates: Dict[str, Any] | None = None` to:

```python
        self.pending_config_updates: List[tuple[str, Dict[str, Any]]] = []
```

In `_normalize_runtime_policy_updates`, inside the `for key, value in config_data.items():` loop, add a final branch so canonical names pass through:

```python
            elif key in VALID_LEVERS:
                normalized[key] = value
```

Replace the head of `_apply_config_updates`:

```python
    async def _apply_config_updates(self, config_data: Dict[str, Any], action_id: Optional[str] = None) -> Dict[str, Any]:
        """Apply runtime-safe frontend config updates and return a receipt."""
        action_id = action_id or uuid.uuid4().hex[:12]
        receipt: Dict[str, Any] = {
            "type": "CONFIG_APPLIED",
            "actionId": action_id,
            "requested": {},
            "applied": {},
            "rejected": {},
            "effectiveTick": self.tick + 1,
        }
        if not self.economy or not config_data:
            return receipt
```

Keep the `enableLlmGovernment` and legacy-key blocks as they are. Replace the lever loop (from `lever_updates = self._normalize_runtime_policy_updates(config_data)` through the `await asyncio.sleep(0)` line) with:

```python
        lever_updates = self._normalize_runtime_policy_updates(config_data)
        receipt["requested"] = dict(lever_updates)
        applied_levers: Dict[str, Any] = {}
        if lever_updates:
            current = {k: v for k, v in normalize_current_policy(self._snapshot_government_levers()).items() if k in VALID_LEVERS}
            try:
                validate_policy_vector({**current, **lever_updates})
            except PolicyVectorError as exc:
                receipt["rejected"]["_group"] = str(exc)
                lever_updates = {}
        for lever, value in lever_updates.items():
            try:
                self.economy.government.set_lever(lever, value)
            except Exception as exc:
                logger.warning("Rejected runtime government lever %s=%r: %s", lever, value, exc)
                receipt["rejected"][lever] = str(exc)
                continue
            applied_levers[lever] = value
            if lever == "minimum_wage_policy":
                min_wage = float(self.economy.government.get_minimum_wage())
                for i, firm in enumerate(self.economy.firms):
                    if firm.wage_offer < min_wage:
                        firm.wage_offer = min_wage
                    if i % 100 == 0:
                        await asyncio.sleep(0)
        snapshot = self._snapshot_government_levers()
        receipt["applied"] = {lever: snapshot.get(lever, value) for lever, value in applied_levers.items()}
```

In the two "Log policy changes" loops that follow: change `for lever, value in lever_updates.items():` to `for lever, value in receipt["applied"].items():`; add `action_id=action_id` as the last argument of every `_append_policy_change_ui_record(...)` call; change every `payload={"value": value}` in `_buffer_policy_action(...)` to `payload={"value": value, "action_id": action_id}`. End the method with `return receipt`.

Replace `update_config`:

```python
    async def update_config(self, config_data) -> Dict[str, Any]:
        """Queue or apply websocket runtime configuration updates, returning a receipt.

        Paused: apply now and return CONFIG_APPLIED. Running: queue for the
        next tick boundary and return CONFIG_QUEUED with the same actionId the
        later CONFIG_APPLIED will carry.
        """
        if not self.economy:
            raise ValueError("no active simulation; send SETUP first")

        locked = {name for name in SetupConfig.model_fields if name.startswith("payment_")}
        locked.update({"paymentSequence", "paymentCareMode", "paymentAssistance"})
        if locked.intersection(config_data):
            raise ValueError("Payment scenario is fixed at SETUP; start a new run to change it")

        action_id = uuid.uuid4().hex[:12]
        if not self.is_running:
            return await self._apply_config_updates(dict(config_data), action_id)
        self.pending_config_updates.append((action_id, dict(config_data)))
        return {"type": "CONFIG_QUEUED", "actionId": action_id, "tick": self.tick}
```

In `_run_loop_scoped`, replace the pending block (`if self.pending_config_updates: ... self.pending_config_updates = None`) with:

```python
                # Apply any pending config updates from the client, one receipt each.
                while self.pending_config_updates:
                    action_id, config_data = self.pending_config_updates.pop(0)
                    receipt = await self._apply_config_updates(config_data, action_id)
                    if self.active_websocket:
                        await self.active_websocket.send_json(receipt)
```

In `websocket_endpoint`'s `CONFIG` branch:

```python
            elif command == "CONFIG":
                config_data = data.get("config", {})
                try:
                    receipt = await session_manager.update_config(config_data)
                    await websocket.send_json(receipt)
                except ValueError as exc:
                    await websocket.send_json({"error": f"CONFIG failed: {exc}"})
```

In `backend/tests_server/test_payment_scenarios.py`, the assertion `assert manager.pending_config_updates is None` becomes `assert manager.pending_config_updates == []`. That is the only change to that file.

- [ ] **Step 8: Run the server suites to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests_server backend/tests_contracts/test_policy_vectors.py -q`
Expected: all PASS, including `test_live_llm_government.py` and `test_payment_scenarios.py`.

- [ ] **Step 9: Lint and commit**

```bash
.venv/bin/python -m ruff check .
git add backend/policy_vectors.py backend/server.py backend/tests_contracts/test_policy_vectors.py backend/tests_server/test_initial_policy_and_receipts.py backend/tests_server/test_payment_scenarios.py
git commit -m "feat(server): validated initial_policy on SETUP, shared lever validation at runtime, CONFIG receipts

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Horizon, HORIZON_REACHED, FINISH and EXTEND with warehouse lifecycle

**Files:**
- Modify: `backend/server.py` (`SetupConfig`, `SimulationManager.__init__`, `_initialize_economy`, `_run_loop_scoped` loop head, `_close_warehouse_run`, new `_finalize_warehouse_run`, `_reopen_warehouse_run`, `finish`, `extend`, `websocket_endpoint`)
- Test: `backend/tests_server/test_horizon_finish_extend.py`

**Interfaces:**
- Produces: `SetupConfig.horizon_ticks: int` (default 260, 1..5200); `SimulationManager.horizon_tick: Optional[int]`, `.horizon_notified: bool`, `.run_finalized: bool`; server messages `{"type": "HORIZON_REACHED", "tick"}` (once per horizon), `{"type": "FINISHED", "tick", "analysisReady", "runId"}`, `{"type": "EXTENDED", "horizonTick", "tick", "resumed": bool}`; commands `FINISH` and `EXTEND {"ticks": int}`; `finish() -> dict`, `extend(ticks) -> dict`, `_finalize_warehouse_run() -> bool`, `_reopen_warehouse_run() -> None`.
- Semantics: FINISH stops the loop and marks the warehouse run `completed` with `analysis_ready=True`, keeping `warehouse_run_id` so EXTEND can continue the same run; a later disconnect keeps the run `completed`. EXTEND raises the horizon, reopens the run (`status="running"`, `analysis_ready=False`) if it was finalized, and resumes the loop itself; no START is needed. Known wart: `update_run_status` always writes `ended_at`, so a reopened run shows an `ended_at` until the next FINISH overwrites it.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests_server/test_horizon_finish_extend.py`:

```python
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402

SMALL = {"num_households": 30, "num_firms": 1, "seed": 7}


def _client(monkeypatch, warehouse="0"):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", warehouse)
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    return TestClient(server.app), registry


def _until(ws, predicate, limit=2000):
    """Return the first message matching predicate; fail loudly instead of hanging."""
    for _ in range(limit):
        msg = ws.receive_json()
        assert "error" not in msg, msg
        if predicate(msg):
            return msg
    raise AssertionError(f"no message matched within {limit} messages")


def _setup(ws, config):
    ws.send_json({"command": "SETUP", "config": config})
    return _until(ws, lambda m: m.get("type") == "SETUP_COMPLETE")


def test_loop_pauses_at_horizon_then_finish_and_extend_resume(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        setup = _setup(ws, {**SMALL, "horizon_ticks": 3})
        assert setup["config"]["horizon_ticks"] == 3
        ws.send_json({"command": "START"})
        reached = _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        assert reached["tick"] == 3
        manager = registry.get(session["sessionId"])
        assert manager.tick == 3 and manager.is_running is False

        ws.send_json({"command": "FINISH"})
        finished = _until(ws, lambda m: m.get("type") == "FINISHED")
        assert finished["tick"] == 3 and finished["analysisReady"] is False and finished["runId"] is None
        assert manager.economy is not None

        ws.send_json({"command": "EXTEND", "ticks": 2})
        extended = _until(ws, lambda m: m.get("type") == "EXTENDED")
        assert extended["horizonTick"] == 5 and extended["resumed"] is True
        reached = _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        assert reached["tick"] == 5


def test_extend_mid_run_raises_horizon_without_an_early_notification(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        _setup(ws, {**SMALL, "horizon_ticks": 12})
        ws.send_json({"command": "START"})
        _until(ws, lambda m: "metrics" in m and m["tick"] >= 1)
        ws.send_json({"command": "EXTEND", "ticks": 3})
        seen = []
        extended = _until(ws, lambda m: seen.append(m) or m.get("type") == "EXTENDED")
        assert extended["horizonTick"] == 15
        reached = _until(ws, lambda m: seen.append(m) or m.get("type") == "HORIZON_REACHED")
        assert reached["tick"] == 15
        assert [m for m in seen if m.get("type") == "HORIZON_REACHED"] == [reached]
        assert registry.get(session["sessionId"]).is_running is False


def test_finish_before_setup_and_extend_with_bad_ticks_are_errors(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"command": "FINISH"})
        assert "error" in ws.receive_json()
        _setup(ws, SMALL)
        ws.send_json({"command": "EXTEND", "ticks": 0})
        assert "error" in ws.receive_json()


def _runs(client):
    return client.get("/warehouse/runs?limit=5").json()["runs"]


def test_sqlite_lifecycle_finish_extend_finish_and_disconnect(monkeypatch, tmp_path):
    monkeypatch.setenv("ECOSIM_WAREHOUSE_BACKEND", "sqlite")
    monkeypatch.setenv("ECOSIM_SQLITE_PATH", str(tmp_path / "lifecycle.db"))
    client, registry = _client(monkeypatch, warehouse="1")
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        _setup(ws, {**SMALL, "horizon_ticks": 2})
        manager = registry.get(session["sessionId"])
        run_id = manager.warehouse_run_id
        assert run_id
        ws.send_json({"command": "START"})
        _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        ws.send_json({"command": "FINISH"})
        finished = _until(ws, lambda m: m.get("type") == "FINISHED")
        assert finished["analysisReady"] is True and finished["runId"] == run_id
        row = next(r for r in _runs(client) if r["run_id"] == run_id)
        assert row["status"] == "completed" and row["analysis_ready"] in (True, 1)

        ws.send_json({"command": "EXTEND", "ticks": 2})
        _until(ws, lambda m: m.get("type") == "EXTENDED")
        row = next(r for r in _runs(client) if r["run_id"] == run_id)
        assert row["status"] == "running" and row["analysis_ready"] in (False, 0)
        _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        ws.send_json({"command": "FINISH"})
        _until(ws, lambda m: m.get("type") == "FINISHED")
        assert manager.warehouse_run_id == run_id
    # disconnect after FINISH must not downgrade the completed run
    row = next(r for r in _runs(client) if r["run_id"] == run_id)
    assert row["status"] == "completed" and row["analysis_ready"] in (True, 1) and row["total_ticks"] == 4
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests_server/test_horizon_finish_extend.py -q`
Expected: FAIL (`Unknown command: FINISH`; no `HORIZON_REACHED`).

- [ ] **Step 3: Implement horizon, finish, extend and the warehouse lifecycle**

In `SetupConfig`, after `initial_policy` add:

```python
    horizon_ticks: int = Field(default=260, ge=1, le=5_200)
```

In `SimulationManager.__init__`, after `self.arm_count` add:

```python
        self.horizon_tick: Optional[int] = None
        self.horizon_notified: bool = False
        self.run_finalized: bool = False
```

In `_initialize_economy`, after `self.setup_config["seed"] = seed` add:

```python
        self.horizon_tick = int(validated.horizon_ticks)
        self.horizon_notified = False
        self.run_finalized = False
```

In `_run_loop_scoped`, at the top of the `while` body (before `start_time = ...`) add:

```python
                if self.horizon_tick is not None and self.tick >= self.horizon_tick:
                    self.is_running = False
                    if not self.horizon_notified:
                        self.horizon_notified = True
                        await self.active_websocket.send_json({"type": "HORIZON_REACHED", "tick": self.tick})
                    break
```

In `_close_warehouse_run`, directly after the early-return guard, add:

```python
        if self.run_finalized and status == "stopped":
            status = "completed"  # FINISH already happened; a later disconnect must not downgrade the run
```

Add these methods after `_close_warehouse_run`:

```python
    def _finalize_warehouse_run(self) -> bool:
        """Mark the active run completed and analysis-ready, keeping warehouse_run_id for EXTEND."""
        if not self.enable_warehouse or self.warehouse_manager is None or self.warehouse_run_id is None:
            return False
        flush_ok = self._flush_warehouse_batches()
        try:
            self.warehouse_manager.update_run_status(
                self.warehouse_run_id,
                status="completed" if flush_ok else "failed",
                total_ticks=self.tick,
                final_metrics=self._collect_final_metrics(),
                last_fully_persisted_tick=self.last_fully_persisted_tick,
                analysis_ready=bool(flush_ok),
                termination_reason="completed" if flush_ok else "warehouse_flush_failed",
            )
        except Exception as exc:
            logger.error("Failed to finalize warehouse run %s: %s", self.warehouse_run_id, exc)
            return False
        self.run_finalized = bool(flush_ok)
        return bool(flush_ok)

    def _reopen_warehouse_run(self) -> None:
        """Return a finalized run to running state before EXTEND resumes it."""
        if not self.run_finalized or self.warehouse_manager is None or self.warehouse_run_id is None:
            self.run_finalized = False
            return
        try:
            self.warehouse_manager.update_run_status(
                self.warehouse_run_id,
                status="running",
                total_ticks=self.tick,
                final_metrics=self._collect_final_metrics(),
                last_fully_persisted_tick=self.last_fully_persisted_tick,
                analysis_ready=False,
                termination_reason=None,
            )
        except Exception as exc:
            logger.error("Failed to reopen warehouse run %s: %s", self.warehouse_run_id, exc)
        self.run_finalized = False

    def finish(self) -> Dict[str, Any]:
        """Stop the loop, finalize the warehouse run, keep the session alive for reading."""
        if not self.economy:
            raise ValueError("no active simulation; send SETUP first")
        self.stop_background_loop()
        analysis_ready = self._finalize_warehouse_run()
        return {"type": "FINISHED", "tick": self.tick, "analysisReady": analysis_ready, "runId": self.warehouse_run_id}

    def extend(self, ticks: int) -> Dict[str, Any]:
        """Raise the horizon by *ticks*, reopen a finalized run, and resume the loop."""
        if not self.economy:
            raise ValueError("no active simulation; send SETUP first")
        ticks = int(ticks)
        if ticks < 1 or ticks > 5_200:
            raise ValueError("EXTEND ticks must be between 1 and 5200")
        base = self.horizon_tick if self.horizon_tick is not None else self.tick
        self.horizon_tick = base + ticks
        self.horizon_notified = False
        self._reopen_warehouse_run()
        resumed = False
        if self.active_websocket is not None:
            self.start_background_loop()
            resumed = True
        return {"type": "EXTENDED", "horizonTick": self.horizon_tick, "tick": self.tick, "resumed": resumed}
```

`start_background_loop` sets `is_running = True` and creates the task only if none is active, so calling it while the loop is still running (mid-run EXTEND) is a no-op apart from the flag, which is already true.

In `websocket_endpoint`, add `"FINISH"` and `"EXTEND"` to `VALID_COMMANDS` and two branches before `except WebSocketDisconnect:`:

```python
            elif command == "FINISH":
                try:
                    await websocket.send_json(session_manager.finish())
                except ValueError as exc:
                    await websocket.send_json({"error": f"FINISH failed: {exc}"})
            elif command == "EXTEND":
                try:
                    await websocket.send_json(session_manager.extend(data.get("ticks", 52)))
                except (TypeError, ValueError) as exc:
                    await websocket.send_json({"error": f"EXTEND failed: {exc}"})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests_server -q`
Expected: all PASS. If `/warehouse/runs` rows expose `analysis_ready` as `0`/`1`, the test already accepts both.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/python -m ruff check .
git add backend/server.py backend/tests_server/test_horizon_finish_extend.py
git commit -m "feat(server): horizon_ticks with HORIZON_REACHED, FINISH that keeps the run open, EXTEND that resumes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Household sample, TRACK command, separate sampling RNG, payment fields, protocol doc

**Files:**
- Modify: `backend/server.py` (`SetupConfig`, `SimulationManager` class constants, `__init__`, `_initialize_economy`, the tracked-subject dict in `_run_loop_scoped`, new `track()` method, `websocket_endpoint`)
- Create: `docs/WEBSOCKET_PROTOCOL.md`
- Test: `backend/tests_server/test_track.py`

**Interfaces:**
- Produces: `SetupConfig.tracked_households: int` (default 40, 1..200); `SimulationManager.tracked_household_count`, `.pinned_household_ids: List[int]`, `._sample_rng: random.Random` (seeded from `seed ^ SAMPLE_RNG_SALT`, never the session stream); `track(action, household_id) -> {"type": "TRACKED", "tracked": [ids], "pinned": [ids], "tick"}`; command `TRACK {"action": "pin"|"unpin"|"follow"|"reshuffle", "householdId"}`; `_new_subject_history() -> dict`.
- Tracked-subject fields added: `rentArrears` (currency owed in rent, from `HouseholdAgent.rent_arrears`, every tick, `0.0` under the legacy sequence), `leaseRenewalTick` (tick of the next lease renewal, from `lease_renewal_tick`, every tick, `-1` when no lease). `metrics.pinnedHouseholdIds` (list of ids, every tick).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests_server/test_track.py`:

```python
import random
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402

SMALL = {"num_households": 60, "num_firms": 1, "seed": 7, "tracked_households": 8}


def _manager(monkeypatch, name, config=SMALL):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    manager = server.SimulationManager(session_id=name)
    manager.initialize(config)
    return manager


def _step(manager, n):
    for _ in range(n):
        with server.use_config(manager.config), manager._random_scope():
            manager.economy.step()
        manager.tick += 1


def _state(manager):
    return (
        [round(h.cash_balance, 9) for h in manager.economy.households],
        [h.employer_id for h in manager.economy.households],
        [round(f.cash_balance, 9) for f in manager.economy.firms],
        round(manager.economy.government.cash_balance, 9),
        manager._python_random_state,
    )


def test_sample_size_follows_setup(monkeypatch):
    manager = _manager(monkeypatch, "a")
    assert len(manager.tracked_household_ids) == 8 == len(set(manager.tracked_household_ids))
    assert all(hid in manager.subject_histories for hid in manager.tracked_household_ids)


def test_browsing_households_never_changes_the_economy_or_the_session_rng(monkeypatch):
    quiet = _manager(monkeypatch, "quiet")
    busy = _manager(monkeypatch, "busy")
    for _ in range(6):
        _step(quiet, 1)
        _step(busy, 1)
        busy.track("reshuffle", None)
        busy.track("pin", busy.tracked_household_ids[0])
        outsider = next(h.household_id for h in busy.economy.households if h.household_id not in busy.tracked_household_ids)
        busy.track("follow", outsider)
    assert _state(quiet) == _state(busy)
    assert random.getstate() == random.getstate()  # module RNG untouched by the calls above


def test_pin_survives_reshuffle_and_follow_evicts_oldest_unpinned(monkeypatch):
    manager = _manager(monkeypatch, "a")
    first = manager.tracked_household_ids[0]
    assert manager.track("pin", first)["pinned"] == [first]
    reply = manager.track("reshuffle", None)
    assert first in reply["tracked"] and len(reply["tracked"]) == 8
    outsider = next(h.household_id for h in manager.economy.households if h.household_id not in reply["tracked"])
    oldest_unpinned = next(hid for hid in reply["tracked"] if hid != first)
    reply = manager.track("follow", outsider)
    assert outsider in reply["tracked"] and oldest_unpinned not in reply["tracked"] and len(reply["tracked"]) == 8
    assert outsider in manager.subject_histories and oldest_unpinned not in manager.subject_histories


def test_follow_unknown_household_is_an_error_and_changes_nothing(monkeypatch):
    manager = _manager(monkeypatch, "a")
    before = list(manager.tracked_household_ids)
    try:
        manager.track("follow", 999_999)
    except ValueError as exc:
        assert "999999" in str(exc)
    else:
        raise AssertionError("expected ValueError")
    assert manager.tracked_household_ids == before


def test_pin_limit_is_eight(monkeypatch):
    manager = _manager(monkeypatch, "a", {**SMALL, "tracked_households": 10})
    for hid in manager.tracked_household_ids[:8]:
        manager.track("pin", hid)
    try:
        manager.track("pin", manager.tracked_household_ids[8])
    except ValueError as exc:
        assert "8" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_track_over_websocket_and_payment_fields_in_frames(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"command": "SETUP", "config": {**SMALL, "horizon_ticks": 2}})
        for _ in range(50):
            if ws.receive_json().get("type") == "SETUP_COMPLETE":
                break
        ws.send_json({"command": "TRACK", "action": "reshuffle"})
        reply = ws.receive_json()
        assert reply["type"] == "TRACKED" and len(reply["tracked"]) == 8
        ws.send_json({"command": "TRACK", "action": "follow", "householdId": 999_999})
        assert "error" in ws.receive_json()
        ws.send_json({"command": "START"})
        frame = None
        for _ in range(200):
            msg = ws.receive_json()
            if "metrics" in msg:
                frame = msg
            if msg.get("type") == "HORIZON_REACHED":
                break
        subjects = frame["metrics"]["trackedSubjects"]
        assert len(subjects) == 8
        assert all("rentArrears" in s and "leaseRenewalTick" in s for s in subjects)
        assert frame["metrics"]["pinnedHouseholdIds"] == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests_server/test_track.py -q`
Expected: FAIL (`tracked_households` is not a SetupConfig field; `track` does not exist).

- [ ] **Step 3: Implement the sample and TRACK**

In `SetupConfig`, after `horizon_ticks` add:

```python
    tracked_households: int = Field(default=40, ge=1, le=200)
```

In `SimulationManager`, replace the class constant `TRACKED_HOUSEHOLDS_COUNT = 12` with:

```python
    DEFAULT_TRACKED_HOUSEHOLDS = 40
    MAX_PINNED_HOUSEHOLDS = 8
    SAMPLE_RNG_SALT = 0x5A17
```

In `__init__`, after `self.run_finalized` add:

```python
        self.tracked_household_count: int = self.DEFAULT_TRACKED_HOUSEHOLDS
        self.pinned_household_ids: List[int] = []
        self._sample_rng = random.Random(self.config.random_seed ^ self.SAMPLE_RNG_SALT)
```

Add a helper next to `_select_tracked_firms`:

```python
    @staticmethod
    def _new_subject_history() -> Dict[str, List[Dict[str, Any]]]:
        return {"cash": [], "wage": [], "happiness": [], "health": [], "netWorth": [], "events": []}
```

In `_initialize_economy`, replace the sampling block (from the comment `# Select random households to track` through the `self.subject_histories = {hid: {...} for hid in self.tracked_household_ids}` comprehension) with:

```python
        # Household sample: its own RNG so browsing never touches the simulation stream.
        self.tracked_household_count = int(validated.tracked_households)
        self.pinned_household_ids = []
        self._sample_rng = random.Random(seed ^ self.SAMPLE_RNG_SALT)
        if self.economy.households:
            count = min(self.tracked_household_count, len(self.economy.households))
            self.tracked_household_ids = [h.household_id for h in self._sample_rng.sample(self.economy.households, count)]
        else:
            self.tracked_household_ids = []
        self.subject_histories = {hid: self._new_subject_history() for hid in self.tracked_household_ids}
```

Add `track` after `extend`:

```python
    def track(self, action: str, household_id: Optional[int]) -> Dict[str, Any]:
        """Pin, unpin, follow or reshuffle the household sample. Never touches the session RNG."""
        if not self.economy:
            raise ValueError("no active simulation; send SETUP first")
        action = str(action or "").lower()
        tracked = list(self.tracked_household_ids)
        if action in {"pin", "unpin", "follow"}:
            if household_id is None:
                raise ValueError(f"TRACK {action} needs householdId")
            household_id = int(household_id)
            if household_id not in self.economy.household_lookup:
                raise ValueError(f"household {household_id} does not exist")
        if action == "pin":
            if household_id not in tracked:
                raise ValueError(f"household {household_id} is not in the sample; follow it first")
            if household_id not in self.pinned_household_ids:
                if len(self.pinned_household_ids) >= self.MAX_PINNED_HOUSEHOLDS:
                    raise ValueError(f"at most {self.MAX_PINNED_HOUSEHOLDS} households can be pinned")
                self.pinned_household_ids.append(household_id)
        elif action == "unpin":
            if household_id in self.pinned_household_ids:
                self.pinned_household_ids.remove(household_id)
        elif action == "follow":
            if household_id not in tracked:
                if len(tracked) >= self.tracked_household_count:
                    evictable = [hid for hid in tracked if hid not in self.pinned_household_ids]
                    if not evictable:
                        raise ValueError("every tracked household is pinned; unpin one first")
                    evicted = evictable[0]
                    tracked.remove(evicted)
                    self.subject_histories.pop(evicted, None)
                tracked.append(household_id)
                self.subject_histories[household_id] = self._new_subject_history()
        elif action == "reshuffle":
            keep = [hid for hid in tracked if hid in self.pinned_household_ids]
            candidates = [h for h in self.economy.households if h.household_id not in keep]
            need = max(0, min(self.tracked_household_count, len(self.economy.households)) - len(keep))
            fresh = [h.household_id for h in self._sample_rng.sample(candidates, min(need, len(candidates)))]
            for hid in tracked:
                if hid not in keep:
                    self.subject_histories.pop(hid, None)
            tracked = keep + fresh
            for hid in fresh:
                self.subject_histories[hid] = self._new_subject_history()
        else:
            raise ValueError(f"unknown TRACK action {action!r}")
        self.tracked_household_ids = tracked
        return {"type": "TRACKED", "tracked": list(tracked), "pinned": list(self.pinned_household_ids), "tick": self.tick}
```

In `websocket_endpoint`, add `"TRACK"` to `VALID_COMMANDS` and:

```python
            elif command == "TRACK":
                try:
                    await websocket.send_json(session_manager.track(data.get("action"), data.get("householdId")))
                except (TypeError, ValueError) as exc:
                    await websocket.send_json({"error": f"TRACK failed: {exc}"})
```

In the tracked-subject dict inside `_run_loop_scoped` (the `tracked_subjects.append({...})` call), add after `"monthlyRent": ...`:

```python
                            "rentArrears": float(getattr(h, "rent_arrears", 0.0) or 0.0),
                            "leaseRenewalTick": int(getattr(h, "lease_renewal_tick", -1)),
```

In the `state["metrics"]` dict, after `"trackedFirms": tracked_firms` add:

```python
                        "pinnedHouseholdIds": list(self.pinned_household_ids),
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests_server -q`
Expected: all PASS.

- [ ] **Step 5: Write the protocol document**

Create `docs/WEBSOCKET_PROTOCOL.md`:

```markdown
# WebSocket protocol (frame-2)

One connection is one simulation session. The first server message is
`{"type": "SESSION", "sessionId": "..."}`. Every command is a JSON object with a
`command` key. Errors are `{"error": "<text>"}`. A full server rejects the
connection at open with an error and close code 1013, before SESSION.

## Commands

| Command | Payload | Reply |
|---|---|---|
| `SETUP` | `config`: `SetupConfig` fields. New in frame-2: `experiment_id`, `arm_label`, `arm_count` (1..4), `experiment_owner`, `initial_policy` (lever vector, schema names), `horizon_ticks` (default 260), `tracked_households` (default 40). Legacy `wage_tax`/`profit_tax` are folded into `initial_policy`. | `SETUP_COMPLETE` with `config`, including `experiment` (`id`, `armLabel`, `armCount`, `householdCap`) and `applied_policy`. A failed SETUP leaves no runnable economy. |
| `START` | none | `STARTED`, then one tick frame per tick. |
| `STOP` | none | `STOPPED`. |
| `CONFIG` | `config`: camelCase aliases or canonical lever names. | Paused: `CONFIG_APPLIED`. Running: `CONFIG_QUEUED` now, `CONFIG_APPLIED` at the next tick boundary with the same `actionId`. Receipt keys: `actionId`, `requested`, `applied`, `rejected` (lever or `_group`), `effectiveTick`. Replay resends `applied` unchanged. |
| `TRACK` | `action`: `pin`, `unpin`, `follow`, `reshuffle`; `householdId` for the first three. | `TRACKED` with `tracked`, `pinned`, `tick`. Sampling uses its own RNG; the economy is unaffected. |
| `FINISH` | none | `FINISHED` with `tick`, `analysisReady`, `runId`. Stops the loop, marks the warehouse run completed, keeps the session and the run open. |
| `EXTEND` | `ticks` (1..5200) | `EXTENDED` with `horizonTick`, `resumed`. Reopens a finalized run and resumes the loop; no START needed. |
| `RESET` | none | `RESET`. Legacy: zeroes the tick without rebuilding the economy. The new client sends `SETUP` again instead. |
| `STABILIZERS` | as before | `STABILIZERS_UPDATED`. |

When the tick reaches the horizon the loop pauses and sends
`{"type": "HORIZON_REACHED", "tick": n}` once per horizon.

## Household budget

`experiment_id` groups sessions. The first arm fixes the owner (`experiment_owner`),
the arm count and the shared world (seed, firms per sector, stabilizers, payment
rules). The server rejects a `SETUP` that would take an arm above `10000 // arm_count`,
exceed 10,000 in total, duplicate an `arm_label`, add a fifth arm, come from a
different owner, or use a different world. Reservations are released on
disconnect or on the session's next `SETUP`.

## Tick frame

All keys of the previous frame are unchanged. Added: `schemaVersion` (`"frame-2"`),
`arm`, `horizonTick`, `curated`, `firms`, `firmsClosed`, `events`, `eventCounts`,
`projectionMs`, `frameBytesPrev`, `serializeMsPrev`, and inside `metrics`:
`pinnedHouseholdIds`, and per tracked household `rentArrears`, `leaseRenewalTick`.
Field lists: `backend/frame_projection.py` and `backend/frame_events.py`.
```

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/python -m ruff check .
git add backend/server.py backend/tests_server/test_track.py docs/WEBSOCKET_PROTOCOL.md
git commit -m "feat(server): 40-household sample with TRACK on a separate sampling RNG, payment fields on subjects

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Event stream, firm directory, closed-firm archive, shock events

**Files:**
- Create: `backend/frame_events.py`
- Modify: `backend/economy.py` (`_apply_random_shocks`), `backend/server.py` (`__init__`, `_initialize_economy`, `_run_loop_scoped`, the `state` dict)
- Test: `backend/tests_contracts/test_frame_events.py`, `backend/tests_contracts/test_shock_events.py`, `backend/tests_server/test_track.py` (one added test)

**Interfaces:**
- Produces: `frame_events.TickEventCollector` with `reset(economy) -> None`, `collect(*, economy, tick, tracked_household_ids: set[int], policy_changes: list[dict]) -> tuple[list[dict], dict]`, `closed_archive(current_tick: int) -> list[dict]`, `firm_name(firm_id) -> str | None`; constants `DETAIL_CAP = 50`, `ARCHIVE_WINDOW_TICKS = 52`.
- Event dict: `{"id": str, "tick": int, "type": str, "householdId": int | None, "firmId": int | None, "firmName": str | None, "sector": str | None, "value": float | None, "text": str | None}`. `type` in `firm_opened`, `firm_closed`, `policy_changed`, `loan_default`, `shock`, `regime`, `hired`, `laid_off`, `care_denied`, `care_completed`. `value`: staff for openings, lever value if numeric for policy, amount written off for defaults, magnitude for shocks, wage for hires, visit price for care. Every event is emitted exactly once: the collector remembers which policy records and default claims it has already reported and which firms were active last tick.
- Counts dict: `hired`, `laidOff`, `careDenied`, `careCompleted`, `firmsOpened`, `firmsClosed`, `loanDefaults`, `policyChanges`, `shocks`, `regime`, `detailed`, `dropped` (all ints, every tick).
- Engine: `_apply_random_shocks` appends a regime event per fired shock: `event_type` in `shock_demand`, `shock_supply`, `shock_health`; `entity_type="economy"`; `metric_value` = magnitude; `payload={"affected": n}`.
- Frame keys: `events` (list), `eventCounts` (dict), `firmsClosed` (archive rows `{"id","name","sector","closedTick","lastStaff"}` within 52 ticks), `arm`, `horizonTick`, `schemaVersion`, `projectionMs` (float ms, this tick's event collection; Task 6 adds the metric projection to the same number).
- Household-level events (`hired`, `laid_off`, `care_*`, and `loan_default` with a household borrower) are detailed only for tracked households and counted for all.

- [ ] **Step 1: Write the failing collector tests**

Create `backend/tests_contracts/test_frame_events.py`:

```python
from types import SimpleNamespace

from frame_events import ARCHIVE_WINDOW_TICKS, DETAIL_CAP, TickEventCollector


def _firm(firm_id, name, sector="Food", employees=3, cash=100.0):
    return SimpleNamespace(firm_id=firm_id, good_name=name, good_category=sector, employees=list(range(employees)), cash_balance=cash)


def _economy(firms, labor=(), care=(), regime=(), defaults=()):
    return SimpleNamespace(
        firms=list(firms),
        firm_lookup={f.firm_id: f for f in firms},
        last_labor_events=list(labor),
        last_healthcare_events=list(care),
        last_regime_events=list(regime),
        payment_state={"loan_default_history": list(defaults)},
    )


def _collect(collector, economy, tick, tracked=frozenset(), changes=()):
    return collector.collect(economy=economy, tick=tick, tracked_household_ids=set(tracked), policy_changes=list(changes))


def test_closure_is_reported_once_and_opening_comes_from_the_directory():
    collector = TickEventCollector()
    collector.reset(_economy([_firm(1, "Corner Bakery")]))
    clinic = _firm(2, "Riverside Clinic", "Healthcare")
    regime = [{"tick": 5, "event_type": "firm_bankrupt", "entity_type": "firm", "entity_id": 1, "sector": "Food",
               "reason_code": "cash_threshold"}]
    events, counts = _collect(collector, _economy([clinic], regime=regime), 5)
    assert {(e["type"], e["firmId"]) for e in events} == {("firm_closed", 1), ("firm_opened", 2)}
    closed = next(e for e in events if e["type"] == "firm_closed")
    assert closed["firmName"] == "Corner Bakery" and closed["text"] == "cash_threshold"
    assert counts["firmsClosed"] == 1 and counts["firmsOpened"] == 1
    assert collector.closed_archive(5) == [{"id": 1, "name": "Corner Bakery", "sector": "Food", "closedTick": 5, "lastStaff": 3}]
    # next tick: nothing new, no repeat
    events, counts = _collect(collector, _economy([clinic]), 6)
    assert events == [] and counts["firmsClosed"] == 0 and counts["firmsOpened"] == 0
    assert len(collector.closed_archive(6)) == 1
    assert collector.closed_archive(5 + ARCHIVE_WINDOW_TICKS + 1) == []
    assert collector.firm_name(1) == "Corner Bakery"  # names outlive the firm


def test_household_events_are_detailed_only_for_tracked_households_but_counted_for_all():
    collector = TickEventCollector()
    firm = _firm(1, "Corner Bakery")
    collector.reset(_economy([firm]))
    labor = [
        {"tick": 3, "household_id": 10, "firm_id": 1, "event_type": "hire", "actual_wage": 40.0},
        {"tick": 3, "household_id": 11, "firm_id": 1, "event_type": "layoff", "actual_wage": None},
        {"tick": 3, "household_id": 12, "firm_id": 1, "event_type": "hire", "actual_wage": 42.0},
    ]
    care = [{"tick": 3, "household_id": 10, "firm_id": 1, "event_type": "visit_denied_affordability", "visit_price": 9.0}]
    defaults = [{"tick": 2, "claim_id": "c1", "borrower_type": "household", "borrower_id": 12, "written_off": 50.0}]
    events, counts = _collect(collector, _economy([firm], labor=labor, care=care, defaults=defaults), 3, tracked={10, 11})
    assert {(e["type"], e["householdId"]) for e in events} == {("hired", 10), ("laid_off", 11), ("care_denied", 10)}
    assert counts["hired"] == 2 and counts["laidOff"] == 1 and counts["careDenied"] == 1 and counts["loanDefaults"] == 1
    assert counts["detailed"] == 3 and counts["dropped"] == 0
    hired = next(e for e in events if e["type"] == "hired")
    assert hired["firmName"] == "Corner Bakery" and hired["value"] == 40.0


def test_laid_off_keeps_firm_name_when_the_firm_closed_this_tick():
    collector = TickEventCollector()
    collector.reset(_economy([_firm(1, "Corner Bakery")]))
    labor = [{"tick": 4, "household_id": 10, "firm_id": 1, "event_type": "layoff"}]
    regime = [{"tick": 4, "event_type": "firm_bankrupt", "entity_type": "firm", "entity_id": 1, "sector": "Food"}]
    events, _ = _collect(collector, _economy([], labor=labor, regime=regime), 4, tracked={10})
    assert next(e for e in events if e["type"] == "laid_off")["firmName"] == "Corner Bakery"


def test_policy_changes_and_defaults_are_emitted_once_regardless_of_their_recorded_tick():
    collector = TickEventCollector()
    collector.reset(_economy([]))
    # server records human changes with the pre-increment tick and payment defaults with the zero-based tick,
    # so the collector must key on identity, not tick equality
    changes = [{"tick": 5, "policy": "benefit_level", "value": "high", "reason": "User", "actionId": "abc"},
               {"tick": 5, "policy": "wage_tax_rate", "value": 0.2, "reason": "User", "actionId": "abc"}]
    defaults = [{"tick": 5, "claim_id": "c1", "borrower_type": "firm", "borrower_id": 3, "written_off": 500.0}]
    events, counts = _collect(collector, _economy([], defaults=defaults), 6, changes=changes)
    assert [e["type"] for e in events] == ["policy_changed", "policy_changed", "loan_default"]
    assert {e["id"] for e in events} == {"6:policy_changed:abc:benefit_level", "6:policy_changed:abc:wage_tax_rate", "6:loan_default:c1"}
    assert events[0]["text"] == "benefit_level=high" and events[2]["value"] == 500.0
    assert counts["policyChanges"] == 2 and counts["loanDefaults"] == 1
    events, counts = _collect(collector, _economy([], defaults=defaults), 7, changes=changes)
    assert events == [] and counts["policyChanges"] == 0 and counts["loanDefaults"] == 0


def test_shock_and_other_regime_events_are_mapped():
    collector = TickEventCollector()
    collector.reset(_economy([]))
    regime = [{"tick": 9, "event_type": "shock_demand", "entity_type": "economy", "metric_value": 42.0, "payload": {"affected": 7}},
              {"tick": 9, "event_type": "sector_shortage_start", "entity_type": "sector", "sector": "Food", "severity": 0.3}]
    events, counts = _collect(collector, _economy([], regime=regime), 9)
    assert [(e["type"], e["text"]) for e in events] == [("shock", "shock_demand"), ("regime", "sector_shortage_start")]
    assert events[0]["value"] == 42.0 and events[1]["sector"] == "Food"
    assert counts["shocks"] == 1 and counts["regime"] == 1


def test_detail_cap_keeps_structural_events_first():
    collector = TickEventCollector()
    collector.reset(_economy([_firm(1, "Corner Bakery")]))
    labor = [{"tick": 1, "household_id": i, "firm_id": 1, "event_type": "hire"} for i in range(DETAIL_CAP + 10)]
    regime = [{"tick": 1, "event_type": "firm_bankrupt", "entity_type": "firm", "entity_id": 1, "sector": "Food"}]
    events, counts = _collect(collector, _economy([], labor=labor, regime=regime), 1, tracked=set(range(DETAIL_CAP + 10)))
    assert len(events) == DETAIL_CAP and events[0]["type"] == "firm_closed"
    assert counts["hired"] == DETAIL_CAP + 10 and counts["dropped"] == 11
```

Create `backend/tests_contracts/test_shock_events.py`:

```python
def test_random_shocks_emit_regime_events(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=12, num_firms_per_category=1, disable_shocks=False)
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests_contracts/test_frame_events.py backend/tests_contracts/test_shock_events.py -q`
Expected: FAIL (`No module named 'frame_events'`; shock test finds no `shock_` events).

- [ ] **Step 3: Instrument shocks in the engine**

In `backend/economy.py`, `_apply_random_shocks` builds `_rng = random.Random(CONFIG.random_seed + self.current_tick * 7_299_133)` and then has three probability branches: the demand shock (`if _rng.random() < 0.05:` choosing `affected_households` and `shock_magnitude`), the supply shock (`< 0.03`, choosing affected firms and a productivity factor) and the health shock (`< 0.02`, choosing affected households and a health delta). In each branch, immediately after the affected collection and magnitude are chosen and before they are applied, add one call using that branch's own variable names:

```python
            self._append_regime_event(
                event_type="shock_demand",  # "shock_supply" / "shock_health" in the other two branches
                entity_type="economy",
                metric_value=float(shock_magnitude),  # the branch's magnitude/factor/delta variable
                payload={"affected": int(len(affected_households))},  # or the affected firms list
            )
```

`_append_regime_event` exists (it is how `firm_bankrupt` is recorded) and appends to `self.last_regime_events`, which `step()` clears at the start of each tick. No RNG call is added, so determinism is unchanged; the extra calls must not consume `_rng`.

- [ ] **Step 4: Create the collector**

Create `backend/frame_events.py`:

```python
"""Typed per-tick events for the frontend feed, plus the firm directory and closed-firm archive.

Pure module: takes an Economy-like object and returns plain dicts. Bankrupt firms
leave economy.firms before we see them, so the collector keeps its own directory
of names from earlier ticks and the set of firms active on the previous tick.
Every event is emitted once: policy records and default claims are remembered
by identity, because their producers stamp ticks differently from the frame.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, Iterable, List, Optional, Set, Tuple

DETAIL_CAP = 50
ARCHIVE_WINDOW_TICKS = 52

_STRUCTURAL_PRIORITY = ("firm_closed", "firm_opened", "policy_changed", "loan_default", "shock", "regime")
_COUNT_KEYS = ("hired", "laidOff", "careDenied", "careCompleted", "firmsOpened", "firmsClosed",
               "loanDefaults", "policyChanges", "shocks", "regime", "detailed", "dropped")


def _event(tick: int, kind: str, key: Any, **fields: Any) -> Dict[str, Any]:
    base = {"id": f"{tick}:{kind}:{key}", "tick": int(tick), "type": kind, "householdId": None,
            "firmId": None, "firmName": None, "sector": None, "value": None, "text": None}
    base.update(fields)
    return base


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class TickEventCollector:
    def __init__(self) -> None:
        self._directory: Dict[int, Dict[str, Any]] = {}   # every firm ever seen: name, sector, last staff
        self._active_ids: Set[int] = set()                 # firms present on the previous tick
        self._closed: List[Dict[str, Any]] = []
        self._seen_policy: Deque[Tuple[Any, ...]] = deque(maxlen=64)
        self._seen_claims: Deque[Any] = deque(maxlen=4096)

    # directory -----------------------------------------------------------
    def reset(self, economy: Any) -> None:
        self._directory = {}
        self._active_ids = set()
        self._closed = []
        self._seen_policy.clear()
        self._seen_claims.clear()
        self._refresh_directory(economy)
        self._active_ids = {int(f.firm_id) for f in (getattr(economy, "firms", []) or [])}

    def _refresh_directory(self, economy: Any) -> None:
        for firm in getattr(economy, "firms", []) or []:
            self._directory[int(firm.firm_id)] = {
                "name": str(firm.good_name),
                "sector": str(firm.good_category or ""),
                "staff": len(getattr(firm, "employees", []) or []),
            }

    def firm_name(self, firm_id: Optional[int]) -> Optional[str]:
        if firm_id is None:
            return None
        entry = self._directory.get(int(firm_id))
        return entry["name"] if entry else None

    def closed_archive(self, current_tick: int) -> List[Dict[str, Any]]:
        self._closed = [row for row in self._closed if current_tick - row["closedTick"] <= ARCHIVE_WINDOW_TICKS]
        return [dict(row) for row in self._closed]

    # collection ----------------------------------------------------------
    def collect(
        self,
        *,
        economy: Any,
        tick: int,
        tracked_household_ids: Set[int],
        policy_changes: Iterable[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        counts = {key: 0 for key in _COUNT_KEYS}
        structural: List[Dict[str, Any]] = []
        household: List[Dict[str, Any]] = []

        current_ids = {int(f.firm_id) for f in (getattr(economy, "firms", []) or [])}
        reasons: Dict[int, Optional[str]] = {}
        other_regime: List[Dict[str, Any]] = []
        for event in getattr(economy, "last_regime_events", []) or []:
            etype = str(event.get("event_type", ""))
            if etype == "firm_bankrupt" and event.get("entity_id") is not None:
                reasons[int(event["entity_id"])] = event.get("reason_code")
            else:
                other_regime.append(event)

        for firm_id in sorted(self._active_ids - current_ids):
            entry = self._directory.get(firm_id, {"name": f"Firm {firm_id}", "sector": "", "staff": 0})
            counts["firmsClosed"] += 1
            self._closed.append({"id": firm_id, "name": entry["name"], "sector": entry["sector"],
                                 "closedTick": int(tick), "lastStaff": entry["staff"]})
            structural.append(_event(tick, "firm_closed", firm_id, firmId=firm_id, firmName=entry["name"],
                                     sector=entry["sector"], text=reasons.get(firm_id)))
        self._refresh_directory(economy)
        for firm_id in sorted(current_ids - self._active_ids):
            entry = self._directory[firm_id]
            counts["firmsOpened"] += 1
            structural.append(_event(tick, "firm_opened", firm_id, firmId=firm_id, firmName=entry["name"],
                                     sector=entry["sector"], value=float(entry["staff"])))
        self._active_ids = current_ids

        for change in policy_changes or []:
            key = (change.get("tick"), change.get("policy"), change.get("actionId"), repr(change.get("value")))
            if key in self._seen_policy:
                continue
            self._seen_policy.append(key)
            counts["policyChanges"] += 1
            ident = f"{change.get('actionId') or 'auto'}:{change.get('policy')}"
            value = change.get("value")
            structural.append(_event(tick, "policy_changed", ident, text=f"{change.get('policy')}={value}",
                                     value=float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None))

        history = (getattr(economy, "payment_state", {}) or {}).get("loan_default_history", ()) or ()
        for row in history:
            claim_id = row.get("claim_id")
            if claim_id in self._seen_claims:
                continue
            self._seen_claims.append(claim_id)
            counts["loanDefaults"] += 1
            borrower_type = row.get("borrower_type")
            borrower_id = row.get("borrower_id")
            event = _event(tick, "loan_default", claim_id, value=_num(row.get("written_off")))
            if borrower_type == "firm" and borrower_id is not None:
                event.update(firmId=int(borrower_id), firmName=self.firm_name(borrower_id))
                structural.append(event)
            elif borrower_type == "household" and borrower_id is not None:
                event["householdId"] = int(borrower_id)
                if int(borrower_id) in tracked_household_ids:
                    household.append(event)
            else:
                structural.append(event)

        for index, event in enumerate(other_regime):
            etype = str(event.get("event_type", ""))
            kind = "shock" if etype.startswith("shock_") else "regime"
            counts["shocks" if kind == "shock" else "regime"] += 1
            structural.append(_event(tick, kind, f"{etype}:{index}", sector=event.get("sector"), text=etype,
                                     value=_num(event.get("metric_value") if event.get("metric_value") is not None else event.get("severity"))))

        for index, event in enumerate(getattr(economy, "last_labor_events", []) or []):
            kind = "hired" if event.get("event_type") == "hire" else "laid_off"
            counts["hired" if kind == "hired" else "laidOff"] += 1
            hid = int(event["household_id"])
            if hid in tracked_household_ids:
                fid = int(event["firm_id"])
                household.append(_event(tick, kind, f"{hid}:{index}", householdId=hid, firmId=fid,
                                        firmName=self.firm_name(fid), value=_num(event.get("actual_wage"))))

        for index, event in enumerate(getattr(economy, "last_healthcare_events", []) or []):
            etype = str(event.get("event_type", ""))
            if etype.startswith("visit_denied"):
                kind = "care_denied"
                counts["careDenied"] += 1
            elif etype == "visit_completed":
                kind = "care_completed"
                counts["careCompleted"] += 1
            else:
                continue
            hid = int(event["household_id"])
            if hid in tracked_household_ids:
                fid = int(event["firm_id"])
                household.append(_event(tick, kind, f"{hid}:{index}", householdId=hid, firmId=fid,
                                        firmName=self.firm_name(fid), value=_num(event.get("visit_price")), text=etype))

        structural.sort(key=lambda e: _STRUCTURAL_PRIORITY.index(e["type"]))
        ordered = structural + household
        detailed = ordered[:DETAIL_CAP]
        counts["detailed"] = len(detailed)
        counts["dropped"] = len(ordered) - len(detailed)
        return detailed, counts
```

- [ ] **Step 5: Run the contract tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests_contracts/test_frame_events.py backend/tests_contracts/test_shock_events.py -q`
Expected: 7 passed.

- [ ] **Step 6: Wire the collector into the loop**

In `backend/server.py` imports add `from frame_events import TickEventCollector`.

In `__init__`, after `self._sample_rng = ...` add:

```python
        self.event_collector = TickEventCollector()
        self.last_events: List[Dict[str, Any]] = []
        self.last_event_counts: Dict[str, int] = {}
```

In `_initialize_economy`, after `self._select_tracked_firms()` add:

```python
        self.event_collector.reset(self.economy)
        self.last_events = []
        self.last_event_counts = {}
```

In `_run_loop_scoped`, directly after `self._buffer_simulation_events()` add:

```python
                projection_started = time.perf_counter()
                self.last_events, self.last_event_counts = self.event_collector.collect(
                    economy=self.economy,
                    tick=self.tick,
                    tracked_household_ids=set(self.tracked_household_ids),
                    policy_changes=self.policy_changes,
                )
                for event in self.last_events:
                    hid = event.get("householdId")
                    if hid in self.subject_histories:
                        bucket = self.subject_histories[hid]["events"]
                        bucket.append({"tick": event["tick"], "type": event["type"], "firmName": event.get("firmName"),
                                       "value": event.get("value")})
                        del bucket[:-20]
                projection_ms = (time.perf_counter() - projection_started) * 1000.0
```

This assignment of `projection_ms` stays; Task 6 adds to it with `+=`.

In the `state` dict, add top-level keys after `"firm_stats": firm_stats`:

```python
                    "schemaVersion": "frame-2",
                    "arm": {"experimentId": self.experiment_id, "armLabel": self.arm_label, "armCount": self.arm_count},
                    "horizonTick": self.horizon_tick,
                    "events": self.last_events,
                    "eventCounts": self.last_event_counts,
                    "firmsClosed": self.event_collector.closed_archive(self.tick),
                    "projectionMs": projection_ms,
```

- [ ] **Step 7: Add a live-path test with a forced event and run everything**

Append to `backend/tests_server/test_track.py`:

```python
def test_frames_carry_a_forced_policy_event_and_recent_events(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"command": "SETUP", "config": {**SMALL, "horizon_ticks": 3}})
        for _ in range(50):
            if ws.receive_json().get("type") == "SETUP_COMPLETE":
                break
        ws.send_json({"command": "CONFIG", "config": {"benefitLevel": "high"}})
        receipt = ws.receive_json()
        assert receipt["type"] == "CONFIG_APPLIED"
        ws.send_json({"command": "START"})
        frames = []
        for _ in range(200):
            msg = ws.receive_json()
            if "metrics" in msg:
                frames.append(msg)
            if msg.get("type") == "HORIZON_REACHED":
                break
        assert frames[0]["schemaVersion"] == "frame-2"
        policy_events = [e for f in frames for e in f["events"] if e["type"] == "policy_changed"]
        assert [e["text"] for e in policy_events] == ["benefit_level=high"]
        assert policy_events[0]["id"].endswith(f":policy_changed:{receipt['actionId']}:benefit_level")
        assert all("hired" in f["eventCounts"] and isinstance(f["firmsClosed"], list) for f in frames)
        subjects = frames[-1]["metrics"]["trackedSubjects"]
        assert len(subjects) == 8 and all(isinstance(s["recentEvents"], list) for s in subjects)
```

Run: `.venv/bin/python -m pytest backend/tests_server backend/tests_contracts -q`
Expected: all PASS.

- [ ] **Step 8: Lint and commit**

```bash
.venv/bin/python -m ruff check .
git add backend/frame_events.py backend/economy.py backend/server.py backend/tests_contracts/test_frame_events.py backend/tests_contracts/test_shock_events.py backend/tests_server/test_track.py
git commit -m "feat(server): typed per-tick event stream with firm directory, closed-firm archive and shock events

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Curated metrics, full firm list and household food spend

**Files:**
- Create: `backend/frame_projection.py`
- Modify: `backend/economy.py` (`get_economic_metrics`), `backend/server.py` (`__init__`, loop recompute block, projection block, `state` dict)
- Test: `backend/tests_contracts/test_frame_projection.py`

**Interfaces:**
- Produces: `frame_projection.build_curated_metrics(*, economy, econ_metrics: dict, tick: int, wealth_as_of_tick: int) -> dict`, `build_firm_list(economy) -> list[dict]`, `firm_state(firm) -> "growing" | "struggling" | "steady"`, `sector_mean_prices(economy) -> dict[str, float | None]`.
- Produces: `economy.get_economic_metrics()["household_food_spend_total"]` and `["household_food_spend_mean"]` (currency per tick, computed from `HouseholdAgent.last_food_spend`).
- Curated keys, every one computed fresh each tick from the economy unless noted; `None` when the producer is absent:
  - `householdsTotal` (count), `peopleOutOfWorkPer100` (working-age households without an employer per 100 who can work; `0.0` when nobody can work), `typicalWeeklyPay` (median wage of employed households, `statistics.median`; `0.0` when nobody is employed), `foodSpendPerHousehold` (mean of `last_food_spend`, currency), `priceFood`/`priceHousing`/`priceServices`/`priceHealthcare` (mean posted price of that sector's firms; `None` when the sector has no firm), `townHallCash` (currency, signed), `homelessHouseholds` (count from `last_housing_diagnostics`, `0.0` when absent), `careDenials` (count from `last_health_diagnostics`), `firmsOpen`/`firmsStruggling`/`firmsGrowing`/`firmsSteady` (counts by `firm_state`), `bankActiveLoans` (count; `None` without a bank), `bankDefaultAmountThisTick` (currency written off this tick from `bank.last_tick_defaults`; `None` without a bank), `bankDefaultsTotal` (count of defaulted claims from `metrics.payment.loans.defaults_total`; `None` under the legacy sequence), `publicWorksJobs` (count).
  - Stride-cached (`get_economic_metrics` is recomputed every `metrics_stride` ticks): `gini`, `wealthP10`, `wealthP50`, `wealthP90` with `wealthAsOfTick` naming the tick they were computed on.
- Firm row: `id`, `name` (`good_name`), `sector`, `cash`, `staff`, `price`, `lastRevenue`, `lastProfit`, `state`, `isBaseline`; list ordered by `cash` descending.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests_contracts/test_frame_projection.py`:

```python
from types import SimpleNamespace

from frame_projection import build_curated_metrics, build_firm_list, firm_state, sector_mean_prices


def _firm(firm_id, name, *, cash=100.0, employees=2, hires=0, burn=False, survival=False, baseline=False,
          sector="Food", price=4.5):
    return SimpleNamespace(firm_id=firm_id, good_name=name, good_category=sector, cash_balance=cash,
                           employees=list(range(employees)), planned_hires_count=hires, burn_mode=burn,
                           survival_mode=survival, is_baseline=baseline, price=price, last_revenue=10.0,
                           last_profit=1.0, zero_cash_streak=0)


def _household(hid, *, employer=None, wage=0.0, can_work=True, food_spend=0.0):
    return SimpleNamespace(household_id=hid, employer_id=employer, wage=wage, can_work=can_work, last_food_spend=food_spend)


def _economy(households, firms, bank=None):
    return SimpleNamespace(households=households, firms=firms, bank=bank,
                           government=SimpleNamespace(cash_balance=-357.5),
                           last_housing_diagnostics={"homeless_household_count": 3.0},
                           last_health_diagnostics={"healthcare_denied_count": 2.0})


def test_firm_state_prefers_struggling_over_growing():
    assert firm_state(_firm(1, "a", hires=2)) == "growing"
    assert firm_state(_firm(1, "a", hires=2, burn=True)) == "struggling"
    assert firm_state(_firm(1, "a", cash=0.0)) == "struggling"
    assert firm_state(_firm(1, "a")) == "steady"


def test_firm_list_is_richest_first_with_expected_keys():
    firms = [_firm(1, "Poor", cash=5.0), _firm(2, "Rich", cash=500.0, baseline=True), _firm(3, "Mid", cash=50.0)]
    rows = build_firm_list(SimpleNamespace(firms=firms))
    assert [r["name"] for r in rows] == ["Rich", "Mid", "Poor"]
    assert set(rows[0]) == {"id", "name", "sector", "cash", "staff", "price", "lastRevenue", "lastProfit", "state", "isBaseline"}
    assert rows[0]["isBaseline"] is True and rows[0]["staff"] == 2


def test_sector_mean_prices_are_per_sector_and_none_when_empty():
    firms = [_firm(1, "a", price=4.0), _firm(2, "b", price=6.0), _firm(3, "c", sector="Housing", price=100.0)]
    prices = sector_mean_prices(SimpleNamespace(firms=firms))
    assert prices == {"Food": 5.0, "Housing": 100.0, "Services": None, "Healthcare": None}


def test_curated_metrics_use_real_values_not_defaults():
    households = [_household(1, employer=1, wage=20.0, food_spend=3.0), _household(2, employer=1, wage=40.0, food_spend=5.0),
                  _household(3, food_spend=0.0), _household(4, can_work=False)]
    firms = [_firm(1, "a", price=4.0, hires=1, employees=2), _firm(2, "b", price=6.0, cash=0.0)]
    bank = SimpleNamespace(active_loans=[1, 2, 3], last_tick_defaults=125.0)
    econ = {"gini_coefficient": 0.41, "wealth_p10": 10.0, "wealth_p50": 50.0, "wealth_p90": 90.0,
            "payment": {"loans": {"defaults_total": 7}}}
    curated = build_curated_metrics(economy=_economy(households, firms, bank), econ_metrics=econ, tick=9, wealth_as_of_tick=5)
    assert curated["householdsTotal"] == 4
    assert abs(curated["peopleOutOfWorkPer100"] - 100.0 / 3.0) < 1e-9  # 1 of 3 who can work
    assert curated["typicalWeeklyPay"] == 30.0  # true median of [20, 40]
    assert curated["foodSpendPerHousehold"] == 2.0
    assert curated["priceFood"] == 5.0 and curated["priceServices"] is None
    assert curated["townHallCash"] == -357.5 and curated["homelessHouseholds"] == 3.0 and curated["careDenials"] == 2.0
    assert (curated["firmsOpen"], curated["firmsGrowing"], curated["firmsStruggling"], curated["firmsSteady"]) == (2, 1, 1, 0)
    assert curated["bankActiveLoans"] == 3 and curated["bankDefaultAmountThisTick"] == 125.0 and curated["bankDefaultsTotal"] == 7
    assert (curated["gini"], curated["wealthP50"], curated["wealthAsOfTick"]) == (0.41, 50.0, 5)


def test_curated_metrics_null_behaviour_without_bank_or_payment_book():
    curated = build_curated_metrics(economy=_economy([_household(1, can_work=False)], []), econ_metrics={}, tick=1, wealth_as_of_tick=1)
    assert curated["peopleOutOfWorkPer100"] == 0.0 and curated["typicalWeeklyPay"] == 0.0
    assert curated["bankActiveLoans"] is None and curated["bankDefaultAmountThisTick"] is None and curated["bankDefaultsTotal"] is None
    assert curated["gini"] is None and curated["priceFood"] is None


def test_food_spend_metrics_exist_and_agree_with_household_receipts(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=10, num_firms_per_category=1)
    economy.step()
    econ = economy.get_economic_metrics()
    total = sum(float(getattr(h, "last_food_spend", 0.0)) for h in economy.households)
    assert abs(econ["household_food_spend_total"] - total) < 1e-6
    assert abs(econ["household_food_spend_mean"] - total / 10) < 1e-6
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests_contracts/test_frame_projection.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'frame_projection'`.

- [ ] **Step 3: Add the food-spend metrics to the engine**

In `backend/economy.py`, inside `get_economic_metrics` and inside its `if self.households:` block, find the end of the employed/unemployed wage branch (the `if employed_households:` block that sets `metrics["mean_wage"]` and `metrics["median_wage"]`, plus its `else` if present). Insert immediately after that whole branch and before the household cash/wealth block that builds `household_cash`:

```python
            food_spend = [float(getattr(h, "last_food_spend", 0.0) or 0.0) for h in self.households]
            metrics["household_food_spend_total"] = float(sum(food_spend))
            metrics["household_food_spend_mean"] = float(sum(food_spend) / len(food_spend)) if food_spend else 0.0
```

`last_food_spend` is reset and accumulated per household every tick in the goods-purchase loop, so this is fresh each tick.

- [ ] **Step 4: Create the projection module**

Create `backend/frame_projection.py`:

```python
"""Curated newcomer-facing metrics and the full firm list for the tick frame.

Everything here is computed fresh from the economy each tick, O(households + firms),
except Gini and the wealth percentiles, which come from get_economic_metrics()
and carry the tick they were computed on.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional

SECTORS = ("Food", "Housing", "Services", "Healthcare")
SECTOR_KEYS = {"Food": "priceFood", "Housing": "priceHousing", "Services": "priceServices", "Healthcare": "priceHealthcare"}


def firm_state(firm: Any) -> str:
    cash = float(getattr(firm, "cash_balance", 0.0) or 0.0)
    if (cash <= 0.0 or getattr(firm, "burn_mode", False) or getattr(firm, "survival_mode", False)
            or int(getattr(firm, "zero_cash_streak", 0) or 0) > 2):
        return "struggling"
    if int(getattr(firm, "planned_hires_count", 0) or 0) > 0:
        return "growing"
    return "steady"


def build_firm_list(economy: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for firm in getattr(economy, "firms", []) or []:
        rows.append({
            "id": int(firm.firm_id),
            "name": str(firm.good_name),
            "sector": str(getattr(firm, "good_category", "") or ""),
            "cash": float(firm.cash_balance),
            "staff": len(getattr(firm, "employees", []) or []),
            "price": float(getattr(firm, "price", 0.0) or 0.0),
            "lastRevenue": float(getattr(firm, "last_revenue", 0.0) or 0.0),
            "lastProfit": float(getattr(firm, "last_profit", 0.0) or 0.0),
            "state": firm_state(firm),
            "isBaseline": bool(getattr(firm, "is_baseline", False)),
        })
    rows.sort(key=lambda row: row["cash"], reverse=True)
    return rows


def sector_mean_prices(economy: Any) -> Dict[str, Optional[float]]:
    totals: Dict[str, List[float]] = {sector: [] for sector in SECTORS}
    for firm in getattr(economy, "firms", []) or []:
        sector = str(getattr(firm, "good_category", "") or "")
        if sector in totals:
            totals[sector].append(float(getattr(firm, "price", 0.0) or 0.0))
    return {sector: (sum(values) / len(values) if values else None) for sector, values in totals.items()}


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_curated_metrics(*, economy: Any, econ_metrics: Dict[str, Any], tick: int, wealth_as_of_tick: int) -> Dict[str, Any]:
    households = list(getattr(economy, "households", []) or [])
    firms = list(getattr(economy, "firms", []) or [])
    can_work = [h for h in households if getattr(h, "can_work", True)]
    unemployed = [h for h in can_work if getattr(h, "employer_id", None) is None]
    wages = [float(h.wage) for h in households if getattr(h, "employer_id", None) is not None]
    food_spend = [float(getattr(h, "last_food_spend", 0.0) or 0.0) for h in households]
    states = [firm_state(f) for f in firms]
    bank = getattr(economy, "bank", None)
    payment = econ_metrics.get("payment") if isinstance(econ_metrics.get("payment"), dict) else None
    defaults_total = payment["loans"].get("defaults_total") if payment and isinstance(payment.get("loans"), dict) else None

    curated: Dict[str, Any] = {
        "householdsTotal": len(households),
        "peopleOutOfWorkPer100": (100.0 * len(unemployed) / len(can_work)) if can_work else 0.0,
        "typicalWeeklyPay": float(statistics.median(wages)) if wages else 0.0,
        "foodSpendPerHousehold": (sum(food_spend) / len(food_spend)) if food_spend else 0.0,
        "gini": _num(econ_metrics.get("gini_coefficient")),
        "wealthP10": _num(econ_metrics.get("wealth_p10")),
        "wealthP50": _num(econ_metrics.get("wealth_p50")),
        "wealthP90": _num(econ_metrics.get("wealth_p90")),
        "wealthAsOfTick": int(wealth_as_of_tick),
        "townHallCash": float(economy.government.cash_balance),
        "homelessHouseholds": _num((getattr(economy, "last_housing_diagnostics", {}) or {}).get("homeless_household_count", 0.0)),
        "careDenials": _num((getattr(economy, "last_health_diagnostics", {}) or {}).get("healthcare_denied_count", 0.0)),
        "firmsOpen": len(firms),
        "firmsStruggling": states.count("struggling"),
        "firmsGrowing": states.count("growing"),
        "firmsSteady": states.count("steady"),
        "bankActiveLoans": len(getattr(bank, "active_loans", []) or []) if bank is not None else None,
        "bankDefaultAmountThisTick": _num(getattr(bank, "last_tick_defaults", None)) if bank is not None else None,
        "bankDefaultsTotal": int(defaults_total) if defaults_total is not None else None,
        "publicWorksJobs": sum(len(getattr(f, "employees", []) or []) for f in firms
                               if str(getattr(f, "good_category", "")).lower() == "publicworks"),
    }
    for sector, price in sector_mean_prices(economy).items():
        curated[SECTOR_KEYS[sector]] = price
    return curated
```

- [ ] **Step 5: Run the projection tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests_contracts/test_frame_projection.py -q`
Expected: 6 passed.

- [ ] **Step 6: Wire the projection into the loop**

In `backend/server.py` imports add `from frame_projection import build_curated_metrics, build_firm_list`.

In `__init__`, after `self.last_event_counts` add `self.cached_econ_tick: int = 0`.

In the loop's recompute branch (`if recompute_metrics:`), after `self.cached_firm_stats = firm_stats` add `self.cached_econ_tick = self.tick`.

Just before the comment `# Update history at startup and then every history_stride ticks.` add:

```python
                projection_resumed = time.perf_counter()
                curated_metrics = build_curated_metrics(
                    economy=self.economy,
                    econ_metrics=econ_metrics,
                    tick=self.tick,
                    wealth_as_of_tick=self.cached_econ_tick,
                )
                firm_rows = build_firm_list(self.economy)
                projection_ms += (time.perf_counter() - projection_resumed) * 1000.0
```

Do not remove Task 5's `projection_ms = ...` assignment; this block adds to it.

In the `state` dict, after `"projectionMs": projection_ms,` add:

```python
                    "curated": curated_metrics,
                    "firms": firm_rows,
```

- [ ] **Step 7: Run the full backend suite**

Run: `.venv/bin/python -m pytest backend/tests_server backend/tests_contracts -q`
Expected: all PASS, at least the Task 0 counts plus the new tests.

- [ ] **Step 8: Lint and commit**

```bash
.venv/bin/python -m ruff check .
git add backend/frame_projection.py backend/economy.py backend/server.py backend/tests_contracts/test_frame_projection.py
git commit -m "feat(server): curated newcomer metrics computed fresh each tick, full firm list, household food spend

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Session recorder and frame-2 fixtures

**Files:**
- Create: `frontend-react/scripts/record_session.py`
- Create: `frontend-react/src/test/fixtures/session-compare-small.jsonl` (generated)
- Regenerate: `frontend-react/src/test/fixtures/frame.json` via the unchanged `capture_fixture.py`
- Test: `backend/tests_server/test_record_session.py`

**Interfaces:**
- Produces: `record_session.record(*, setup: dict, ticks_to_run: int | None, actions: list[dict], out_path: Path) -> dict` where `actions` are `{"atTick": int, ...command payload}` and the return is `{"frames", "bytesTotal", "bytesMax", "lastTick", "errors"}`.
- File format, JSON Lines: line 1 `{"kind": "header", "schemaVersion": "frame-2", "setup", "recordedAt"}`; then `{"kind": "sent", "seq", "message"}` for every client command and `{"kind": "message", "seq", "message"}` for every server message, in wire order; last line `{"kind": "footer", "frames", "bytesTotal", "bytesMax", "lastTick", "errors"}`. Error messages from the server are recorded and counted, not fatal; only a failed SETUP aborts.
- CLI: `python frontend-react/scripts/record_session.py --households 60 --ticks 24 --out <path> [--initial-policy '{"minimum_wage_policy":"high"}'] [--experiment exp-1 --arm "Town A" --arms 2 --owner me] [--action '{"atTick":3,"command":"CONFIG","config":{"benefitLevel":"high"}}' ...]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests_server/test_record_session.py`:

```python
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "frontend-react" / "scripts"
for path in (SCRIPTS, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import record_session  # noqa: E402


def test_recorder_writes_header_sent_messages_errors_and_footer(tmp_path, monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    out = tmp_path / "session.jsonl"
    summary = record_session.record(
        setup={"num_households": 30, "num_firms": 1, "seed": 7, "horizon_ticks": 5, "tracked_households": 4,
               "experiment_id": "exp-rec", "arm_label": "Town A", "arm_count": 1, "experiment_owner": "test"},
        ticks_to_run=None,
        actions=[{"atTick": 2, "command": "TRACK", "action": "reshuffle"},
                 {"atTick": 2, "command": "TRACK", "action": "follow", "householdId": 999_999},
                 {"atTick": 3, "command": "CONFIG", "config": {"benefitLevel": "high"}}],
        out_path=out,
    )
    lines = [json.loads(line) for line in out.read_text().splitlines()]
    assert lines[0]["kind"] == "header" and lines[0]["schemaVersion"] == "frame-2"
    assert lines[-1]["kind"] == "footer" and lines[-1]["frames"] == 5 and lines[-1]["errors"] == 1
    sent = [line["message"]["command"] for line in lines if line["kind"] == "sent"]
    assert sent[:2] == ["SETUP", "START"] and "TRACK" in sent and "CONFIG" in sent and sent[-1] == "FINISH"
    received = [line["message"] for line in lines if line["kind"] == "message"]
    types = [m.get("type") for m in received]
    assert "SETUP_COMPLETE" in types and "TRACKED" in types and "HORIZON_REACHED" in types and "FINISHED" in types
    assert any("error" in m for m in received)
    assert "CONFIG_APPLIED" in types
    frames = [m for m in received if "metrics" in m]
    assert [f["tick"] for f in frames] == [1, 2, 3, 4, 5]
    assert frames[0]["schemaVersion"] == "frame-2" and "curated" in frames[0] and "firms" in frames[0]
    assert summary["frames"] == 5 and summary["bytesMax"] > 0 and summary["errors"] == 1
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests_server/test_record_session.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'record_session'`.

- [ ] **Step 3: Create the recorder**

Create `frontend-react/scripts/record_session.py`:

```python
"""Record a whole WebSocket session (frame-2) to JSON Lines for backend-free frontend work.

Runs the FastAPI app in-process through Starlette's TestClient, sends SETUP and
START, replays scripted actions at given ticks, and writes every client command
and server message in wire order. Server errors are recorded, not fatal.

    .venv/bin/python frontend-react/scripts/record_session.py --households 60 --ticks 24 \
        --out frontend-react/src/test/fixtures/session-compare-small.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient  # noqa: E402

from backend import server  # noqa: E402


def record(*, setup: Dict[str, Any], ticks_to_run: Optional[int], actions: List[Dict[str, Any]], out_path: Path) -> Dict[str, Any]:
    pending = sorted(actions, key=lambda a: int(a["atTick"]))
    client = TestClient(server.app)
    stats = {"frames": 0, "bytesTotal": 0, "bytesMax": 0, "lastTick": 0, "errors": 0}
    seq = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        def write(kind: str, **payload: Any) -> None:
            fh.write(json.dumps({"kind": kind, **payload}) + "\n")

        def send(ws, message: Dict[str, Any]) -> None:
            nonlocal seq
            seq += 1
            write("sent", seq=seq, message=message)
            ws.send_json(message)

        def receive(ws) -> Dict[str, Any]:
            nonlocal seq
            message = ws.receive_json()
            seq += 1
            if "error" in message:
                stats["errors"] += 1
            if "metrics" in message and "tick" in message:
                encoded = json.dumps(message, separators=(",", ":"))
                stats["frames"] += 1
                stats["bytesTotal"] += len(encoded)
                stats["bytesMax"] = max(stats["bytesMax"], len(encoded))
                stats["lastTick"] = int(message["tick"])
            write("message", seq=seq, message=message)
            return message

        write("header", schemaVersion="frame-2", setup=setup, recordedAt=datetime.now(timezone.utc).isoformat())
        with client.websocket_connect("/ws") as ws:
            receive(ws)  # SESSION
            send(ws, {"command": "SETUP", "config": setup})
            msg = receive(ws)
            while msg.get("type") != "SETUP_COMPLETE":
                if "error" in msg:
                    raise RuntimeError(f"SETUP failed: {msg['error']}")
                msg = receive(ws)
            send(ws, {"command": "START"})
            done = False
            while not done:
                msg = receive(ws)
                if "metrics" in msg:
                    tick = int(msg["tick"])
                    while pending and int(pending[0]["atTick"]) <= tick:
                        action = dict(pending.pop(0))
                        action.pop("atTick", None)
                        send(ws, action)
                    if ticks_to_run is not None and tick >= ticks_to_run:
                        send(ws, {"command": "STOP"})
                if msg.get("type") in {"HORIZON_REACHED", "STOPPED"}:
                    send(ws, {"command": "FINISH"})
                if msg.get("type") == "FINISHED":
                    done = True
        write("footer", **stats)
    return dict(stats)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--households", type=int, default=60)
    parser.add_argument("--firms", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--ticks", type=int, default=24, help="horizon in ticks")
    parser.add_argument("--tracked", type=int, default=8)
    parser.add_argument("--initial-policy", default="{}", help="JSON lever vector")
    parser.add_argument("--experiment", default=None)
    parser.add_argument("--arm", default=None)
    parser.add_argument("--arms", type=int, default=1)
    parser.add_argument("--owner", default="recorder")
    parser.add_argument("--action", action="append", default=[], help='JSON like {"atTick":3,"command":"CONFIG","config":{...}}')
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    setup: Dict[str, Any] = {
        "num_households": args.households, "num_firms": args.firms, "seed": args.seed,
        "horizon_ticks": args.ticks, "tracked_households": args.tracked,
        "initial_policy": json.loads(args.initial_policy), "enable_llm_government": False,
    }
    if args.experiment:
        setup.update({"experiment_id": args.experiment, "arm_label": args.arm or "Town A", "arm_count": args.arms,
                      "experiment_owner": args.owner})
    summary = record(setup=setup, ticks_to_run=None, actions=[json.loads(a) for a in args.action], out_path=Path(args.out))
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest backend/tests_server/test_record_session.py -q`
Expected: 1 passed.

- [ ] **Step 5: Generate the checked-in fixtures and check the frontend suite**

```bash
ECOSIM_ENABLE_WAREHOUSE=0 .venv/bin/python frontend-react/scripts/record_session.py --households 60 --ticks 24 --tracked 8 \
  --experiment exp-fixture --arm "Town A" --arms 2 --owner fixture \
  --action '{"atTick":6,"command":"CONFIG","config":{"benefitLevel":"high"}}' \
  --action '{"atTick":12,"command":"TRACK","action":"reshuffle"}' \
  --out frontend-react/src/test/fixtures/session-compare-small.jsonl
ECOSIM_ENABLE_WAREHOUSE=0 .venv/bin/python frontend-react/scripts/capture_fixture.py 60
ls -la frontend-react/src/test/fixtures/
cd frontend-react && npx --yes node@22 node_modules/.bin/vitest run; cd ..
```

Expected: the JSONL is under 3 MB (if not, regenerate with `--households 40 --ticks 16`); `frame.json` is regenerated with `schemaVersion: "frame-2"`; the Vitest suite passes, since it reads only the old keys.

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/python -m ruff check .
git add frontend-react/scripts/record_session.py backend/tests_server/test_record_session.py frontend-react/src/test/fixtures/session-compare-small.jsonl frontend-react/src/test/fixtures/frame.json
git commit -m "feat(tools): record a full frame-2 session, commands and errors included, and refresh fixtures

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Concurrent full-path benchmark, equivalence check and the phase gate

**Files:**
- Modify: `backend/server.py` (frame send in `_run_loop_scoped`, `__init__`)
- Create: `backend/tools/benchmarks/run_frame_bench.py`
- Create: `docs/evals/2026-09-24-frame-bench/README.md` and `data/` (written after running)
- Modify: `docs/README.md` (one line), `CHANGELOG.md` (one entry)
- Test: `backend/tests_contracts/test_frame_bench_tool.py`

**Interfaces:**
- Frame: `frameBytesPrev` (bytes of the previous tick's encoded frame, int, `0` on the first frame) and `serializeMsPrev` (milliseconds `json.dumps` took for the previous frame, float). The loop encodes with `json.dumps(state)` and sends with `send_text`, so serialization is measured without encoding twice.
- Produces: `run_frame_bench.summarize(records) -> dict` with `frames`, `bytes` (`p50`, `p95`, `max`), `tickComputeMs` (`p50`, `p95`), `projectionMs` (`p50`, `p95`, `shareOfTickP50`), `serializeMs` (`p50`, `p95`, `shareOfTickP50`), `interFrameMs` (`p50`, `p95`); `run_frame_bench.run_experiment(*, base_url, arms: list[dict], households, ticks, seed, warehouse: bool) -> dict[str, list[dict]]` running all arms concurrently against a live server (each arm: `{"label", "initial_policy"}`), one record per frame with `tick`, `bytes`, `tickComputeMs`, `projectionMs`, `serializeMs`, `receivedAt`, `peopleOutOfWorkPer100`; `run_frame_bench.launch_server(*, warehouse: bool, sqlite_path: Path) -> (process, base_url)`; `run_frame_bench.equivalence(*, records_for_baseline, households, ticks, seed) -> dict` comparing the session path with `run_newcomer_smoke.run_arm` at shared checkpoints and returning `{"checkpoints": [...], "matches": bool}` where a checkpoint at frame tick `t` is compared with the smoke row whose `tick == t - 1` (the smoke runner stamps rows with the pre-step tick).
- Gate (spec section 8, at two towns of 1,000 households, warehouse off): `bytes.p95 <= 61_440` and `projectionMs.shareOfTickP50 + serializeMs.shareOfTickP50 <= 0.10`, and `equivalence.matches` is `True`. The CLI exits non-zero when the gate fails.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests_contracts/test_frame_bench_tool.py`:

```python
import os
from pathlib import Path

import pytest

from tools.benchmarks import run_frame_bench


def test_summarize_reports_percentiles_and_shares():
    records = [
        {"tick": 1, "bytes": 1000, "tickComputeMs": 10.0, "projectionMs": 1.0, "serializeMs": 0.5, "receivedAt": 0.0},
        {"tick": 2, "bytes": 2000, "tickComputeMs": 20.0, "projectionMs": 2.0, "serializeMs": 1.0, "receivedAt": 0.1},
        {"tick": 3, "bytes": 3000, "tickComputeMs": 30.0, "projectionMs": 3.0, "serializeMs": 1.5, "receivedAt": 0.2},
    ]
    summary = run_frame_bench.summarize(records)
    assert summary["frames"] == 3 and summary["bytes"]["max"] == 3000 and summary["bytes"]["p50"] == 2000
    assert summary["tickComputeMs"]["p50"] == 20.0
    assert abs(summary["projectionMs"]["shareOfTickP50"] - 0.1) < 1e-9
    assert abs(summary["serializeMs"]["shareOfTickP50"] - 0.05) < 1e-9
    assert summary["interFrameMs"]["p50"] > 0


@pytest.mark.slow
def test_two_arms_run_concurrently_against_a_live_server_and_match_the_smoke_runner(tmp_path):
    os.environ.setdefault("ECOSIM_ENABLE_WAREHOUSE", "0")
    process, base_url = run_frame_bench.launch_server(warehouse=False, sqlite_path=tmp_path / "bench.db")
    try:
        results = run_frame_bench.run_experiment(
            base_url=base_url,
            arms=[{"label": "Town A", "initial_policy": {}}, {"label": "Town B", "initial_policy": {"benefit_level": "high"}}],
            households=60, ticks=6, seed=7, warehouse=False,
        )
    finally:
        run_frame_bench.stop_server(process)
    assert set(results) == {"Town A", "Town B"}
    assert [r["tick"] for r in results["Town A"]] == [1, 2, 3, 4, 5, 6]
    assert all(r["bytes"] > 0 and r["serializeMs"] >= 0.0 for r in results["Town B"][1:])
    equivalence = run_frame_bench.equivalence(records_for_baseline=results["Town A"], households=60, ticks=6, seed=7)
    assert equivalence["matches"] is True, equivalence
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests_contracts/test_frame_bench_tool.py -q`
Expected: FAIL with `ImportError: cannot import name 'run_frame_bench'`.

- [ ] **Step 3: Measure serialization in the loop**

In `backend/server.py` `__init__`, after `self.cached_econ_tick` add:

```python
        self.last_frame_bytes: int = 0
        self.last_serialize_ms: float = 0.0
```

In `_initialize_economy`, next to the other resets, add `self.last_frame_bytes = 0` and `self.last_serialize_ms = 0.0`.

In the `state` dict add, after `"firms": firm_rows,`:

```python
                    "frameBytesPrev": self.last_frame_bytes,
                    "serializeMsPrev": self.last_serialize_ms,
```

Replace `await self.active_websocket.send_json(state)` with:

```python
                serialize_started = time.perf_counter()
                encoded = json.dumps(state)
                self.last_serialize_ms = (time.perf_counter() - serialize_started) * 1000.0
                self.last_frame_bytes = len(encoded)
                await self.active_websocket.send_text(encoded)
```

`send_json` uses `json.dumps` with the same defaults, so the wire content is unchanged.

- [ ] **Step 4: Create the benchmark**

Create `backend/tools/benchmarks/run_frame_bench.py`:

```python
"""Concurrent full-path frame benchmark: real uvicorn server, N websocket arms at once.

Measures per-frame bytes, tick compute time, projection time, serialization time
and inter-frame time per arm; checks the phase-1 gate; and asserts that the
session path reproduces the headless newcomer smoke runner for the same seed.

    .venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 1000 --ticks 260 --arms 2 --seed 1337
    .venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 1000 --ticks 260 --arms 2 --warehouse
    .venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 5000 --ticks 52 --arms 2
    .venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 2500 --ticks 52 --arms 4
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from websockets.asyncio.client import connect  # noqa: E402

GATE_BYTES_P95 = 61_440
GATE_OVERHEAD_SHARE = 0.10
CHECKPOINTS = (13, 26, 52, 104, 156, 208, 260)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def launch_server(*, warehouse: bool, sqlite_path: Path) -> Tuple[subprocess.Popen, str]:
    port = _free_port()
    env = dict(os.environ)
    env["ECOSIM_ENABLE_WAREHOUSE"] = "1" if warehouse else "0"
    env["ECOSIM_WAREHOUSE_BACKEND"] = "sqlite"
    env["ECOSIM_SQLITE_PATH"] = str(sqlite_path)
    env["ECOSIM_MAX_SESSIONS"] = "8"
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.server:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(REPO_ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    import urllib.request
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/health", timeout=1) as response:
                if response.status == 200:
                    return process, base_url
        except Exception:
            if process.poll() is not None:
                raise RuntimeError(f"server exited early: {process.stderr.read().decode(errors='replace')[-2000:]}")
            time.sleep(0.2)
    process.kill()
    raise RuntimeError("server did not become healthy within 30 s")


def stop_server(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


async def _run_arm(ws_url: str, *, setup: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    async with connect(ws_url, max_size=50_000_000, open_timeout=20) as ws:
        await ws.recv()  # SESSION
        await ws.send(json.dumps({"command": "SETUP", "config": setup}))
        while True:
            msg = json.loads(await ws.recv())
            if "error" in msg:
                raise RuntimeError(msg["error"])
            if msg.get("type") == "SETUP_COMPLETE":
                break
        await ws.send(json.dumps({"command": "START"}))
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if "error" in msg:
                raise RuntimeError(msg["error"])
            if "metrics" in msg:
                records.append({
                    "tick": int(msg["tick"]),
                    "bytes": len(raw),
                    "tickComputeMs": float(msg["metrics"].get("tickComputeMs", 0.0)),
                    "projectionMs": float(msg.get("projectionMs", 0.0)),
                    "serializeMs": float(msg.get("serializeMsPrev", 0.0)),
                    "receivedAt": time.perf_counter(),
                    "peopleOutOfWorkPer100": float((msg.get("curated") or {}).get("peopleOutOfWorkPer100", 0.0)),
                })
            if msg.get("type") == "HORIZON_REACHED":
                break
        await ws.send(json.dumps({"command": "FINISH"}))
        while json.loads(await ws.recv()).get("type") != "FINISHED":
            pass
    return records


def run_experiment(*, base_url: str, arms: List[Dict[str, Any]], households: int, ticks: int, seed: int,
                   warehouse: bool) -> Dict[str, List[Dict[str, Any]]]:
    ws_url = base_url.replace("http", "ws", 1) + "/ws"
    experiment_id = f"bench-{int(time.time())}"

    async def _all() -> Dict[str, List[Dict[str, Any]]]:
        tasks = []
        for arm in arms:
            setup = {
                "num_households": households, "num_firms": 5, "seed": seed, "horizon_ticks": ticks,
                "initial_policy": dict(arm.get("initial_policy") or {}), "enable_llm_government": False,
                "experiment_id": experiment_id, "arm_label": arm["label"], "arm_count": len(arms), "experiment_owner": "bench",
            }
            tasks.append(_run_arm(ws_url, setup=setup))
        results = await asyncio.gather(*tasks)
        return {arm["label"]: records for arm, records in zip(arms, results)}

    return asyncio.run(_all())


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return float(ordered[index])


def summarize(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    sizes = [float(r["bytes"]) for r in records]
    ticks_ms = [float(r["tickComputeMs"]) for r in records]
    proj_ms = [float(r["projectionMs"]) for r in records]
    ser_ms = [float(r.get("serializeMs", 0.0)) for r in records[1:]]  # first frame carries no previous value
    gaps = [(b["receivedAt"] - a["receivedAt"]) * 1000.0 for a, b in zip(records, records[1:])]
    tick_p50 = _percentile(ticks_ms, 50)
    proj_p50 = _percentile(proj_ms, 50)
    ser_p50 = _percentile(ser_ms, 50)
    return {
        "frames": len(records),
        "bytes": {"p50": _percentile(sizes, 50), "p95": _percentile(sizes, 95), "max": max(sizes) if sizes else 0.0},
        "tickComputeMs": {"p50": tick_p50, "p95": _percentile(ticks_ms, 95)},
        "projectionMs": {"p50": proj_p50, "p95": _percentile(proj_ms, 95), "shareOfTickP50": (proj_p50 / tick_p50) if tick_p50 else 0.0},
        "serializeMs": {"p50": ser_p50, "p95": _percentile(ser_ms, 95), "shareOfTickP50": (ser_p50 / tick_p50) if tick_p50 else 0.0},
        "interFrameMs": {"p50": _percentile(gaps, 50), "p95": _percentile(gaps, 95)},
    }


def equivalence(*, records_for_baseline: List[Dict[str, Any]], households: int, ticks: int, seed: int) -> Dict[str, Any]:
    """Compare the live session's unemployment with the headless smoke runner at shared checkpoints."""
    from backend.tools.benchmarks import run_newcomer_smoke

    baseline_arm = run_newcomer_smoke.resolve_arms(["baseline"])[0]
    smoke_rows, _meta = run_newcomer_smoke.run_arm(
        baseline_arm, seed=seed, households=households, ticks=ticks, firms_per_category=5, payment_sequence="legacy",
    )
    by_frame_tick = {r["tick"]: r["peopleOutOfWorkPer100"] for r in records_for_baseline}
    by_smoke_tick = {int(row["tick"]): float(row["unemployment_rate"]) * 100.0 for row in smoke_rows}
    checkpoints = [t for t in CHECKPOINTS if t <= ticks] or [ticks]
    rows = []
    for tick in checkpoints:
        session_value = by_frame_tick.get(tick)
        smoke_value = by_smoke_tick.get(tick - 1)  # smoke rows are stamped with the pre-step tick
        rows.append({"tick": tick, "session": session_value, "smoke": smoke_value,
                     "match": session_value is not None and smoke_value is not None and abs(session_value - smoke_value) < 1e-6})
    return {"checkpoints": rows, "matches": all(r["match"] for r in rows)}


def gate(summary: Dict[str, Any], equivalence_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    overhead = summary["projectionMs"]["shareOfTickP50"] + summary["serializeMs"]["shareOfTickP50"]
    checks = {
        "bytesP95": summary["bytes"]["p95"] <= GATE_BYTES_P95,
        "overheadShare": overhead <= GATE_OVERHEAD_SHARE,
        "equivalence": bool(equivalence_result["matches"]) if equivalence_result else True,
    }
    return {"checks": checks, "passed": all(checks.values()), "overheadShare": overhead}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--arms", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--warehouse", action="store_true")
    parser.add_argument("--skip-equivalence", action="store_true")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir or REPO_ROOT / "benchmarks" / "results" / "frame-bench" / stamp)
    out_dir.mkdir(parents=True, exist_ok=True)
    arms = [{"label": f"Town {chr(65 + i)}", "initial_policy": {} if i == 0 else {"benefit_level": "high"}} for i in range(args.arms)]

    process, base_url = launch_server(warehouse=args.warehouse, sqlite_path=out_dir / "bench.db")
    started = time.perf_counter()
    try:
        results = run_experiment(base_url=base_url, arms=arms, households=args.households, ticks=args.ticks,
                                 seed=args.seed, warehouse=args.warehouse)
    finally:
        stop_server(process)
    wall = time.perf_counter() - started

    per_arm = {label: summarize(records) for label, records in results.items()}
    primary = per_arm[arms[0]["label"]]
    equivalence_result = None if args.skip_equivalence else equivalence(
        records_for_baseline=results[arms[0]["label"]], households=args.households, ticks=args.ticks, seed=args.seed)
    verdict = gate(primary, equivalence_result)
    report = {"households": args.households, "ticks": args.ticks, "arms": args.arms, "seed": args.seed,
              "warehouse": args.warehouse, "wallClockSeconds": wall, "perArm": per_arm,
              "equivalence": equivalence_result, "gate": verdict}
    (out_dir / "summary.json").write_text(json.dumps(report, indent=2))
    lines = [f"# Frame bench: {args.arms} arms x {args.households} households, {args.ticks} ticks, seed {args.seed}, "
             f"warehouse {'on' if args.warehouse else 'off'}", "", f"- wall clock: {wall:.1f} s", ""]
    for label, summary in per_arm.items():
        lines += [f"## {label}",
                  f"- bytes p50 / p95 / max: {summary['bytes']['p50']:.0f} / {summary['bytes']['p95']:.0f} / {summary['bytes']['max']:.0f}",
                  f"- tick compute ms p50 / p95: {summary['tickComputeMs']['p50']:.1f} / {summary['tickComputeMs']['p95']:.1f}",
                  f"- projection ms p50 / p95: {summary['projectionMs']['p50']:.2f} / {summary['projectionMs']['p95']:.2f}",
                  f"- serialize ms p50 / p95: {summary['serializeMs']['p50']:.2f} / {summary['serializeMs']['p95']:.2f}",
                  f"- inter-frame ms p50 / p95: {summary['interFrameMs']['p50']:.1f} / {summary['interFrameMs']['p95']:.1f}", ""]
    lines += ["## Gate", f"- overhead share of tick (p50): {verdict['overheadShare']:.1%}", f"- checks: {verdict['checks']}",
              f"- passed: {verdict['passed']}"]
    if equivalence_result:
        lines += ["", "## Equivalence with the headless smoke runner",
                  "| frame tick | session | smoke (tick-1) | match |", "|---|---|---|---|"]
        lines += [f"| {r['tick']} | {r['session']} | {r['smoke']} | {r['match']} |" for r in equivalence_result["checkpoints"]]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests_contracts/test_frame_bench_tool.py -q -m "slow or not slow"`
Expected: 2 passed. If `equivalence["matches"]` is `False`, the session path and the headless runner consume the simulation RNG differently. Do not loosen the check. Diagnose by comparing `SimulationManager._reset_random_state` with `policy_forecasting.sweep.wrapper.set_run_seed` (both seed Python's `random` and NumPy from the same integer and set `config.random_seed`) and by confirming that nothing between `create_large_economy` and the first `economy.step()` draws from the session stream in the server path; fix the divergence in the server and record what it was in the task notes.

- [ ] **Step 6: Run the gate and the matrix**

Run each command in full and keep the complete output (these are gates; do not pipe through `tail`):

```bash
.venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 1000 --ticks 260 --arms 2 --seed 1337
.venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 1000 --ticks 260 --arms 2 --seed 1337 --warehouse
.venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 5000 --ticks 52 --arms 2 --seed 1337 --skip-equivalence
.venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 2500 --ticks 52 --arms 4 --seed 1337 --skip-equivalence
```

Expected: exit code `0` for the first command (the phase gate). The others are recorded; they inform phase 2 but do not gate phase 1. If the first fails on bytes, find the dominant key by loading the recorded session from Task 7 and summing `len(json.dumps(frame[key]))` per top-level key and per `metrics` key across frames; the usual suspects are the per-household `history` arrays and `firms`. Reduce the offending payload (for example send `history` only every `history_stride` ticks) and re-run. If it fails on overhead share, profile `build_curated_metrics` and `TickEventCollector.collect` with `cProfile` on a recorded run.

- [ ] **Step 7: Record the evidence**

Create `docs/evals/2026-09-24-frame-bench/README.md` with: the four commands, each run's complete `summary.md`, the gate result with exit codes, and the equivalence table with one sentence on whether the live path matched the headless runner at every checkpoint. Copy each `summary.json` into `docs/evals/2026-09-24-frame-bench/data/` as `arms<N>-hh<households>-t<ticks>-seed<seed>-wh<on|off>.json`. Add one line to the experiments table in `docs/README.md`. Add one entry to `CHANGELOG.md` under Unreleased: "Phase 1 backend widening landed: experiment registry, initial policy and receipts, horizon/finish/extend, TRACK, event stream, curated metrics, recorder, concurrent frame bench; gate: <pass/fail, bytes p95, overhead share, equivalence>."

- [ ] **Step 8: Lint, run the whole suite, commit**

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
git add backend/server.py backend/tools/benchmarks/run_frame_bench.py backend/tests_contracts/test_frame_bench_tool.py docs/evals/2026-09-24-frame-bench docs/README.md CHANGELOG.md
git commit -m "feat(bench): concurrent full-path frame benchmark with serialization timing, equivalence check and phase-1 gate

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Accepted deviations from the spec in phase 1

- Queryable experiment columns on the warehouse run row wait for the Saved phase (spec 6.1 says so); phase 1 tags runs and records the experiment in `config_json`.
- Task 3's reopened run shows an `ended_at` between EXTEND and the next FINISH because `update_run_status` always writes it; fixing that is a warehouse change outside this plan and is noted in the protocol document.
- Browser-side budgets (heap, chart re-render) are phase 2 measurements; this plan measures the backend side of section 8 only.
- LLM decision history and truth pairs are phase 3.

## Self-review notes

- Every section H item of the first audit and every item in sections A, B, D and E of the plan audit maps to a change above: registry ownership and world key (Task 1), no runnable economy after a failed SETUP (Task 1), the `pending_config_updates is None` assertion (Task 2), shared runtime validation and canonical names (Task 2), FINISH surviving disconnect and EXTEND resuming and reopening (Task 3), bounded receive helpers and a SQLite lifecycle test (Task 3), per-entity RNG equivalence (Task 4), payment wire fields (Task 4), closures reported once and identity-keyed policy and default events (Task 5), shock instrumentation and generic regime events (Task 5), tracked filtering of household defaults (Task 5), true median and amount-versus-count naming (Task 6), fresh prices and food spend (Task 6), recorder covering sent commands and errors (Task 7), concurrent benchmark with serialization timing, warehouse on and off, equivalence assertion and a real gate (Task 8).
- Names used across tasks: `experiment_registry`, `ExperimentRegistry.reserve/release/describe/per_arm_cap`, `SetupConfig.world_key`, `validate_policy_vector`, `_initialize_economy`, `_apply_config_updates(config_data, action_id)`, `update_config -> dict`, `pending_config_updates: list[tuple]`, `horizon_tick`, `run_finalized`, `finish()`, `extend()`, `_finalize_warehouse_run()`, `_reopen_warehouse_run()`, `track()`, `_new_subject_history()`, `_sample_rng`, `TickEventCollector.reset/collect/closed_archive/firm_name`, `build_curated_metrics`, `build_firm_list`, `firm_state`, `sector_mean_prices`, `record_session.record`, `run_frame_bench.launch_server/stop_server/run_experiment/summarize/equivalence/gate`. Each is defined before it is used.
