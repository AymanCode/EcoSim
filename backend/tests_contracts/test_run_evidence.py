"""Evidence must describe runs without changing their outcomes or feature schema."""

import copy
import json
import random
from pathlib import Path

import numpy as np
import pytest

from config import clone_config, use_config
from run_evidence import RunEvidence, comparison_evidence, conditions, model_identity, write_evidence
from tools.benchmarks import run_policy_sweep as benchmark


def test_observation_is_detached_and_does_not_consume_rng(tiny_economy_factory, tmp_path):
    eco = tiny_economy_factory()
    cfg = clone_config()
    py_rng, np_rng = random.getstate(), copy.deepcopy(np.random.get_state())
    before = copy.deepcopy(conditions(eco))
    with use_config(cfg):
        evidence = RunEvidence(run_id="test", seed=42, ticks=2, factory={}, requested_policy={"wage_tax_rate": 0.4})
        evidence.observe(eco, phase="initialized")
        eco.government.set_lever("wage_tax_rate", 0.4)
        evidence.policy_applied(eco)
        assert evidence.data["conditions"][0]["policy"]["wage_tax_rate"] == before["policy"]["wage_tax_rate"]
        assert evidence.data["policy_application"]["effective_policy"]["wage_tax_rate"] == 0.4
        eco.performance_mode = True
        eco.configure_stabilizers(firms=False)
        eco.current_tick = 1
        evidence.observe(eco, phase="before_step")
        evidence.completed = 1
        evidence.finish(eco, error=RuntimeError("intentional"), phase="step")
        assert evidence.data["failure"]["attempted_tick"] == 1
        assert evidence.data["ticks_completed"] == 1
        assert evidence.data["conditions"][-1]["execution"]["performance_mode"]
        assert not evidence.data["conditions"][-1]["stabilizers"]["firm"]
        cfg.random_seed = 999
        assert evidence.data["configuration_initial"]["random_seed"] != 999
    assert random.getstate() == py_rng
    after_np = np.random.get_state()
    assert after_np[0] == np_rng[0] and np.array_equal(after_np[1], np_rng[1]) and after_np[2:] == np_rng[2:]
    payload = comparison_evidence(model={}, runs=[evidence.data], runner="test")
    path = tmp_path / "evidence.json"
    write_evidence(path, payload)
    loaded = json.loads(path.read_text())
    assert loaded["control_capabilities"]["target_inflation_rate"]["status"] == "inactive"
    assert loaded["metric_definitions"]["version"] == "ecosim.metrics.legacy.v1"


def test_source_hash_changes_for_uncommitted_engine_edits(tmp_path):
    (tmp_path / "backend").mkdir()
    path = tmp_path / "backend/economy.py"
    path.write_text("baseline")
    first = model_identity(tmp_path)
    path.write_text("candidate")
    second = model_identity(tmp_path)
    assert first["source_sha256"] != second["source_sha256"]
    assert first["commit"] is None


@pytest.mark.parametrize("where", ["initialization", "step", "policy_application"])
def test_benchmark_failure_is_persisted_with_actual_phase(tmp_path, monkeypatch, tiny_economy_factory, where):
    def broken(*args, **kwargs):
        raise RuntimeError("injected failure")

    def make(*args, **kwargs):
        eco = tiny_economy_factory()
        if where == "step":
            eco.step = broken
        return eco

    monkeypatch.setattr(benchmark, "_create_economy_quietly", broken if where == "initialization" else make)
    if where == "policy_application":
        monkeypatch.setattr(benchmark, "_apply_policy", broken)
    result = benchmark.run_policy_sweep(
        policy_groups=["baseline"],
        seeds=[42],
        households=10,
        ticks=2,
        firms_per_category=1,
        output_root=tmp_path,
        verbose=True,
    )
    assert result["rows"][0]["failed"]
    assert result["rows"][0]["final_gdp"] is None
    evidence = json.loads(result["artifacts"]["comparison_evidence"].read_text())
    assert evidence["runs"][0]["failure"]["phase"] == where


def test_forecasting_observation_keeps_rows_and_frozen_columns(monkeypatch):
    from policy_forecasting.config import FROZEN_ARMS, FEATURE_MANIFEST
    from policy_forecasting.sweep.wrapper import run_single_policy

    cfg = clone_config()
    with use_config(copy.deepcopy(cfg)):
        recorded = run_single_policy(FROZEN_ARMS[0], seed=42, households=30, ticks=4, firms_per_category=1)
    monkeypatch.setattr(RunEvidence, "observe", lambda *args, **kwargs: None)
    with use_config(copy.deepcopy(cfg)):
        unobserved = run_single_policy(FROZEN_ARMS[0], seed=42, households=30, ticks=4, firms_per_category=1)
    assert recorded == unobserved
    assert set(FEATURE_MANIFEST).issubset(recorded[0])
    assert "configuration_initial" not in recorded[0]
    assert "control_capabilities" not in recorded[0]


def test_forecasting_failure_writes_sidecar_without_publishing_dataset(tmp_path, monkeypatch):
    from policy_forecasting.sweep import wrapper
    from policy_forecasting.config import FROZEN_ARMS

    def broken(*args, **kwargs):
        raise RuntimeError("cannot initialize")

    monkeypatch.setattr(wrapper, "create_economy_quietly", broken)
    path = tmp_path / "ticks.parquet"
    with pytest.raises(RuntimeError, match="evidence saved"):
        wrapper.run_policy_sweep(
            arms=[FROZEN_ARMS[0].arm_id], seeds=[42], households=10, ticks=2, firms_per_category=1, output_path=path
        )
    data = json.loads(path.with_suffix(".evidence.json").read_text())
    assert data["runs"][0]["status"] == "failed"
    assert data["runs"][0]["failure"]["phase"] == "initialization"
    assert not path.exists()


def test_forecasting_export_failure_is_separate_from_completed_simulations(tmp_path, monkeypatch):
    import pandas as pd
    from policy_forecasting.config import FROZEN_ARMS
    from policy_forecasting.sweep import wrapper

    def broken_export(*args, **kwargs):
        raise OSError("injected disk failure")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", broken_export)
    path = tmp_path / "failed-export.parquet"
    with pytest.raises(OSError, match="disk failure"):
        wrapper.run_policy_sweep(
            arms=[FROZEN_ARMS[0].arm_id], seeds=[42], households=10, ticks=1, firms_per_category=1, output_path=path
        )
    data = json.loads(path.with_suffix(".evidence.json").read_text())
    assert data["runs"][0]["status"] == "completed"
    assert data["sweep_failures"][0]["phase"] == "parquet_export"
    assert len(data["planned_runs"]) == 1
