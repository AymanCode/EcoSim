import asyncio
import json
import time

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


@pytest.mark.parametrize("bad", [0, 0.0, -1.0, float("nan"), float("inf")])
def test_summarize_rejects_a_tick_time_that_is_not_finite_and_positive(bad):
    records = [
        {"tick": 1, "bytes": 1000, "tickComputeMs": 10.0, "projectionMs": 1.0, "serializeMs": 0.0, "receivedAt": 0.0},
        {"tick": 2, "bytes": 1000, "tickComputeMs": bad, "projectionMs": 1.0, "serializeMs": 0.5, "receivedAt": 0.1},
    ]
    with pytest.raises(ValueError, match="tick 2"):
        run_frame_bench.summarize(records)


def test_summarize_rejects_an_arm_without_frames():
    with pytest.raises(ValueError):
        run_frame_bench.summarize([])


def _summary(bytes_p95, projection_share=0.01, serialize_share=0.01):
    return {
        "bytes": {"p95": bytes_p95},
        "projectionMs": {"shareOfTickP50": projection_share},
        "serializeMs": {"shareOfTickP50": serialize_share},
    }


MATCHED = {"checkpoints": [], "matches": True}


def test_gate_passes_the_phase_gate_only_with_every_arm_in_budget_and_equivalence_measured():
    verdict = run_frame_bench.gate({"Town A": _summary(1_000), "Town B": _summary(2_000)}, MATCHED, require_equivalence=True)
    assert verdict["passed"] is True and verdict["phaseGate"] is True and verdict["failingArms"] == []
    assert run_frame_bench.exit_code(verdict) == 0


def test_gate_reports_a_skipped_equivalence_as_a_matrix_run_not_a_phase_gate_pass():
    verdict = run_frame_bench.gate({"Town A": _summary(1_000), "Town B": _summary(2_000)}, None, require_equivalence=False)
    assert verdict["checks"]["equivalence"] == "skipped"
    assert verdict["passed"] is True and verdict["phaseGate"] is False
    assert run_frame_bench.exit_code(verdict) == 2


def test_gate_fails_when_a_required_equivalence_result_is_missing():
    verdict = run_frame_bench.gate({"Town A": _summary(1_000)}, None, require_equivalence=True)
    assert verdict["checks"]["equivalence"] is False
    assert verdict["passed"] is False and verdict["phaseGate"] is False
    assert run_frame_bench.exit_code(verdict) == 1


def test_gate_fails_on_an_equivalence_mismatch():
    verdict = run_frame_bench.gate({"Town A": _summary(1_000)}, {"checkpoints": [], "matches": False}, require_equivalence=True)
    assert verdict["checks"]["equivalence"] is False and run_frame_bench.exit_code(verdict) == 1


def test_gate_checks_every_arm_and_names_the_failing_ones():
    verdict = run_frame_bench.gate({"Town A": _summary(1_000), "Town B": _summary(70_000)}, MATCHED, require_equivalence=True)
    assert verdict["passed"] is False and verdict["failingArms"] == ["Town B"]
    assert verdict["checks"]["bytesP95"] is False and verdict["checks"]["overheadShare"] is True
    assert run_frame_bench.exit_code(verdict) == 1

    over_time = run_frame_bench.gate({"Town A": _summary(1_000), "Town B": _summary(1_000, 0.08, 0.05)}, None,
                                     require_equivalence=False)
    assert over_time["failingArms"] == ["Town B"] and over_time["checks"]["overheadShare"] is False
    assert run_frame_bench.exit_code(over_time) == 1


def _frame(tick, **overrides):
    frame = {"tick": tick, "metrics": {"tickComputeMs": 50.0}, "projectionMs": 0.5, "serializeMsPrev": 1.0,
             "curated": {"peopleOutOfWorkPer100": 5.0}}
    frame.update(overrides)
    return frame


class _StubSocket:
    """Scripted server: yields each message in turn, then keeps repeating `forever` or blocks like a silent server."""

    def __init__(self, script, forever=None, interval=0.0):
        self.script = list(script)
        self.forever = forever
        self.interval = interval
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, text):
        self.sent.append(json.loads(text))

    async def recv(self):
        if self.script:
            return json.dumps(self.script.pop(0))
        if self.forever is not None:
            await asyncio.sleep(self.interval)
            return json.dumps(self.forever())
        await asyncio.Event().wait()


def _run_with(monkeypatch, stub, **bounds):
    monkeypatch.setattr(run_frame_bench, "connect", lambda url, **kwargs: stub)
    return run_frame_bench.run_experiment(
        base_url="http://127.0.0.1:1", arms=[{"label": "Town A", "initial_policy": {}}],
        households=10, ticks=2, seed=1, warehouse=False, **bounds,
    )


def test_a_silent_server_fails_the_arm_within_the_quiet_bound(monkeypatch):
    started = time.monotonic()
    with pytest.raises(RuntimeError, match=r"Town A: no message within 0\.2s after tick 0"):
        _run_with(monkeypatch, _StubSocket([]), quiet_seconds=0.2, deadline_seconds=1.0)
    assert time.monotonic() - started < 1.5


def test_a_server_that_never_reaches_the_horizon_fails_the_arm_at_the_deadline(monkeypatch):
    ticks = iter(range(1, 10_000))
    stub = _StubSocket([{"type": "SESSION"}, {"type": "SETUP_COMPLETE"}], forever=lambda: _frame(next(ticks)), interval=0.05)
    started = time.monotonic()
    with pytest.raises(RuntimeError, match=r"Town A: arm deadline of 0\.6s passed after tick \d+"):
        _run_with(monkeypatch, stub, quiet_seconds=0.5, deadline_seconds=0.6)
    assert time.monotonic() - started < 1.5


def test_control_waits_are_bounded_by_message_count(monkeypatch):
    stub = _StubSocket([{"type": "SESSION"}], forever=lambda: {"type": "NOISE"})
    with pytest.raises(RuntimeError, match="Town A: no SETUP_COMPLETE within 2000 messages"):
        _run_with(monkeypatch, stub, quiet_seconds=1.0, deadline_seconds=10.0)


@pytest.mark.parametrize("error_at", ["SESSION", "SETUP_COMPLETE", "frames", "FINISHED"])
def test_an_error_message_fails_every_wait_with_its_text(monkeypatch, error_at):
    script = [{"type": "SESSION"}, {"type": "SETUP_COMPLETE"}, _frame(1), _frame(2), {"type": "HORIZON_REACHED", "tick": 2}]
    position = {"SESSION": 0, "SETUP_COMPLETE": 1, "frames": 3, "FINISHED": 5}[error_at]
    script.insert(position, {"error": f"boom at {error_at}"})
    with pytest.raises(RuntimeError, match=f"Town A: server error after tick \\d+: boom at {error_at}"):
        _run_with(monkeypatch, _StubSocket(script), quiet_seconds=1.0, deadline_seconds=5.0)


def test_a_frame_missing_telemetry_fails_the_arm_instead_of_counting_zero(monkeypatch):
    stub = _StubSocket([{"type": "SESSION"}, {"type": "SETUP_COMPLETE"}, {"tick": 1, "metrics": {}}])
    with pytest.raises(RuntimeError, match="Town A: frame at tick 1 is missing metrics.tickComputeMs"):
        _run_with(monkeypatch, stub, quiet_seconds=1.0, deadline_seconds=5.0)


@pytest.mark.parametrize("missing", ["projectionMs", "serializeMsPrev", "curated"])
def test_each_required_frame_field_is_checked(monkeypatch, missing):
    frame = _frame(1)
    del frame[missing]
    stub = _StubSocket([{"type": "SESSION"}, {"type": "SETUP_COMPLETE"}, frame])
    with pytest.raises(RuntimeError, match=f"frame at tick 1 is missing {missing}"):
        _run_with(monkeypatch, stub, quiet_seconds=1.0, deadline_seconds=5.0)


def test_a_complete_scripted_arm_returns_one_record_per_frame(monkeypatch):
    stub = _StubSocket([{"type": "SESSION"}, {"type": "SETUP_COMPLETE"}, _frame(1), _frame(2),
                        {"type": "HORIZON_REACHED", "tick": 2}, {"type": "FINISHED"}])
    results = _run_with(monkeypatch, stub, quiet_seconds=1.0, deadline_seconds=5.0)
    assert [r["tick"] for r in results["Town A"]] == [1, 2]
    assert [m["command"] for m in stub.sent] == ["SETUP", "START", "FINISH"]


def test_equivalence_requires_the_smoke_row_and_counts_a_missing_session_value_as_a_mismatch(monkeypatch):
    from backend.tools.benchmarks import run_newcomer_smoke

    rows = [{"tick": t, "unemployment_rate": 0.05} for t in range(13)]
    monkeypatch.setattr(run_newcomer_smoke, "run_arm", lambda *args, **kwargs: (rows, {}))
    result = run_frame_bench.equivalence(records_for_baseline=[], households=10, ticks=13, seed=1)
    assert result["matches"] is False and result["checkpoints"][0]["session"] is None

    monkeypatch.setattr(run_newcomer_smoke, "run_arm", lambda *args, **kwargs: (rows[:5], {}))
    with pytest.raises(RuntimeError, match="no row for tick 12"):
        run_frame_bench.equivalence(records_for_baseline=[{"tick": 13, "peopleOutOfWorkPer100": 5.0}],
                                    households=10, ticks=13, seed=1)


@pytest.mark.slow
def test_two_arms_run_concurrently_against_a_live_server_and_match_the_smoke_runner(tmp_path, monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
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


@pytest.mark.parametrize("profile", [None, "lean", "legacy"])
def test_each_arm_setup_names_the_frame_profile_lean_by_default(monkeypatch, profile):
    stub = _StubSocket([{"type": "SESSION"}, {"type": "SETUP_COMPLETE"}, _frame(1), _frame(2),
                        {"type": "HORIZON_REACHED", "tick": 2}, {"type": "FINISHED"}])
    monkeypatch.setattr(run_frame_bench, "connect", lambda url, **kwargs: stub)
    extra = {} if profile is None else {"frame_profile": profile}
    run_frame_bench.run_experiment(base_url="http://127.0.0.1:1", arms=[{"label": "Town A", "initial_policy": {}}],
                                   households=10, ticks=2, seed=1, warehouse=False, quiet_seconds=1.0,
                                   deadline_seconds=5.0, **extra)
    assert stub.sent[0]["command"] == "SETUP" and stub.sent[0]["config"]["frame_profile"] == (profile or "lean")
    assert stub.sent[0]["config"]["horizon_ticks"] == 2 and stub.sent[0]["config"]["tracked_households"] == 40
