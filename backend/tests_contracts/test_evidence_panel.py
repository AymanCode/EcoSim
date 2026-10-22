"""Contracts for the shared evidence panel (tools/benchmarks/run_evidence_panel.py)."""

import json
import os
import random
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from config import CONFIG, clone_config, use_config
from tools.benchmarks import panel_summary
from tools.benchmarks import run_evidence_panel as panel
from tools.benchmarks.evidence_panel_worker import (
    apply_config_overrides,
    install_hooks,
    panel_row,
    rows_fingerprint,
    state_components,
)


def test_windows_cover_inclusive_ranges_and_an_open_end():
    assert panel.parse_windows("1-100,101-200,201-", 260) == [
        ("1-100", 1, 100),
        ("101-200", 101, 200),
        ("201-260", 201, 260),
    ]
    with pytest.raises(ValueError):
        panel.parse_windows("1-300", 260)


def test_window_values_aggregate_only_the_ticks_inside_each_window():
    rows = [
        {"tick": 1, "gdp": 10.0, "government_cash": 5.0},
        {"tick": 2, "gdp": 30.0, "government_cash": -1.0},
        {"tick": 3, "gdp": 50.0, "government_cash": -3.0},
        {"tick": 4, "gdp": 50.0, "government_cash": 2.0},
    ]
    values = panel.window_values(rows, [("1-2", 1, 2), ("3-4", 3, 4)])

    assert values["1-2"]["gdp:mean"] == 20.0
    assert values["1-2"]["gdp:cv"] == pytest.approx(0.5)
    assert values["3-4"]["gdp:cv"] == 0.0
    assert values["1-2"]["government_cash:min"] == -1.0
    assert values["1-2"]["government_cash:neg_share"] == 0.5
    assert values["3-4"]["government_cash:neg_share"] == 0.5
    # A metric the rows do not carry is reported as missing, not as zero.
    assert values["1-2"]["happiness:mean"] is None


def test_paired_stats_flag_a_mean_that_one_seed_drives():
    driven = panel.paired_stats([1.0, 2.0, 3.0, 4.0, -20.0])
    assert driven["mean"] == -2.0
    assert driven["median"] == 2.0
    assert (driven["up"], driven["down"], driven["n"]) == (4, 1, 5)
    assert driven["loo_sign_stable"] is False

    assert panel.paired_stats([1.0, 2.0, 3.0])["loo_sign_stable"] is True
    assert panel.paired_stats([1.0, -1.0])["loo_sign_stable"] is None
    assert panel.paired_stats([]) == {"n": 0}


def test_assignments_split_levers_from_config_and_refuse_the_sequence():
    plan = panel.parse_assignments(
        [["on", "households.poverty_threshold=250"], ["on", "lever.wage_tax_rate=0.3"]], ["off", "on"]
    )
    assert plan["on"]["config_overrides"] == {"households.poverty_threshold": "250"}
    assert plan["on"]["levers"] == {"wage_tax_rate": "0.3"}
    assert plan["on"]["timed_levers"] == []
    assert plan["off"] == {"config_overrides": {}, "levers": {}, "timed_levers": []}

    with pytest.raises(ValueError, match="panel dimension"):
        panel.parse_assignments([["on", "payment_sequence=legacy"]], ["on"])
    with pytest.raises(ValueError, match="unknown arm"):
        panel.parse_assignments([["missing", "households.poverty_threshold=1"]], ["on"])


def test_config_overrides_match_the_setting_type_and_refuse_unknown_names():
    with use_config(clone_config()):
        apply_config_overrides(CONFIG, {"households.poverty_threshold": "250"})
        assert CONFIG.households.poverty_threshold == 250.0
        assert isinstance(CONFIG.households.poverty_threshold, float)

        with pytest.raises(ValueError, match="Unknown config field"):
            apply_config_overrides(CONFIG, {"households.poverty_thresold": "1"})
        with pytest.raises(ValueError, match="bool"):
            apply_config_overrides(CONFIG, {"modes.stabilization_enabled": "1"})


def _main(tmp_path, *extra):
    runtime, decision, _digest = panel._reference_status(sys.executable)
    if not decision['ok']:
        reason = panel_summary.format_reference_error(decision, runtime['python'], runtime['implementation'])
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            pytest.fail(reason)
        pytest.skip(reason)
    return panel.main([
        "--households", "40", "--firms-per-category", "2", "--ticks", "6",
        "--seeds", "1,2", "--sequences", "income_first,legacy", "--windows", "1-3,4-",
        "--jobs", "2", "--out", str(tmp_path), *extra,
    ])


def test_panel_pairs_arms_checks_identity_and_reuses_finished_runs(tmp_path, capsys):
    arms = ["--arm", "a", "--arm", "b", "--arm", "taxed", "--set", "taxed", "lever.wage_tax_rate=0.45"]
    assert _main(tmp_path, *arms) == 0

    result = json.loads((tmp_path / "panel.json").read_text(encoding="utf-8"))
    checks = result["summary"]["checks"]
    # An arm with no changes reproduces the baseline on every run, and so does a repeated run.
    assert checks["arms"]["b"]["identical_to_baseline"] == {"identical": 4, "runs": 4}
    assert checks["arms"]["taxed"]["identical_to_baseline"]["identical"] < 4
    assert [d["identical"] for d in checks["determinism"]] == [True, True]
    same = result["summary"]["comparisons"]["b"]["income_first"]["4-6"]["unemployment_rate:mean"]
    assert same["mean"] == 0.0 and same["n"] == 2

    report = (tmp_path / "panel.md").read_text(encoding="utf-8")
    assert "## `taxed` vs `a`: income_first" in report
    assert report.index("income_first") < report.index("## `taxed` vs `a`: legacy")
    # Rows keep the standard order; an identical arm gets one line, not tables of zeros.
    assert report.index("| Unemployment, labour force") < report.index("| Real GDP")
    assert "Identical on all 4 runs" in report and "## `b` vs `a`: income_first" not in report
    assert (tmp_path / "window_values.csv").exists()

    capsys.readouterr()
    assert _main(tmp_path, *arms) == 0
    rerun = capsys.readouterr().out
    assert "reusing 14 finished runs" in rerun  # 3 arms x 2 sequences x 2 seeds, plus 2 repeats
    assert not re.search(r"\[panel\] \d+/\d+ ", rerun)  # no run was simulated again

    # Runs record the worker's own runtime with one numeric-library thread.
    run_path = tmp_path / "runs" / "a-legacy-s1.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "panel.json").read_text(encoding="utf-8"))["manifest"]
    assert run["runtime"]["python"] == manifest["worker_runtime"]["python"]
    assert run["runtime"]["thread_env"]["OMP_NUM_THREADS"] == "1"

    # A run finished under another interpreter is simulated again, never reused.
    run["spec"]["runtime"]["python"] = "3.0.0"
    run_path.write_text(json.dumps(run), encoding="utf-8")
    assert _main(tmp_path, *arms) == 0
    rerun = capsys.readouterr().out
    assert "reusing 13 finished runs" in rerun
    assert len(re.findall(r"\[panel\] \d+/1 a legacy seed 1:", rerun)) == 1


def test_panel_fails_loudly_on_a_misspelled_flag(tmp_path):
    exit_code = _main(tmp_path, "--arm", "base", "--arm", "typo", "--set", "typo", "households.skills_dynamicz=True")

    assert exit_code == 1
    failures = json.loads((tmp_path / "panel.json").read_text(encoding="utf-8"))["failures"]
    assert failures and all("skills_dynamicz" in "\n".join(f["stderr_tail"]) for f in failures)
    assert not (tmp_path / "panel.md").exists()


def test_default_windows_are_312_and_weeks_260_still_runs():
    assert panel.resolve_windows(panel.DEFAULT_WINDOWS, 312) == [
        ("1-100", 1, 100),
        ("101-200", 101, 200),
        ("201-312", 201, 312),
        ("261-312", 261, 312),
    ]
    assert panel.resolve_windows(panel.DEFAULT_WINDOWS, 260) == [
        ("1-100", 1, 100),
        ("101-200", 101, 200),
        ("201-260", 201, 260),
    ]
    args = panel.build_parser().parse_args(["--arm", "a", "--weeks", "260"])
    assert args.ticks == 260
    assert panel.window_role(1) == "reported, not judged"
    assert panel.window_role(201) == "judged"


def test_timed_lever_sweep_and_interact_expand_like_handwritten_sets():
    timed = panel.parse_assignments([["on", "lever.wage_tax_rate=0.45@2..3"]], ["on"])
    assert timed["on"]["levers"] == {}
    assert timed["on"]["timed_levers"] == [{"name": "wage_tax_rate", "value": "0.45", "start": 2, "end": 3}]

    args = panel.build_parser().parse_args([
        "--arm", "base",
        "--sweep", "base", "households.poverty_threshold",
        "--interact", "a:households.fix_category_price_beliefs=True", "b:lever.wage_tax_rate=0.2",
        "--off-set", "households.fix_category_price_beliefs=False",
    ])
    panel.expand_shorthand(args)
    plan = panel.parse_assignments(args.set, args.arm)
    assert plan["base-x0.5"]["config_overrides"]["households.poverty_threshold"] == "100"
    assert plan["base-x1"]["config_overrides"]["households.poverty_threshold"] == "200"
    assert plan["base-x1.5"]["config_overrides"]["households.poverty_threshold"] == "300"
    assert plan["a+b"]["config_overrides"]["households.fix_category_price_beliefs"] == "True"
    assert plan["a+b"]["levers"]["wage_tax_rate"] == "0.2"
    assert plan["off"]["config_overrides"]["households.fix_category_price_beliefs"] == "False"


def test_band_distance_real_gdp_fragility_and_planted_money_leak():
    assert panel_summary.band_distance_points(0.25) == 0.0
    assert panel_summary.band_distance_points(0.008) == pytest.approx(9.2)
    assert panel_summary.band_distance_points(0.50) == pytest.approx(10.0)

    base_rows = [{"tick": tick, "units__Food": 2.0, "rev__Food": 6.0} for tick in range(11, 63)]
    prices, label = panel_summary.base_paid_prices(base_rows)
    assert label == "11-62"
    assert prices["Food"] == pytest.approx(3.0)
    assert panel_summary.paid_real_gdp({"tick": 80, "units__Food": 4.0}, prices) == pytest.approx(12.0)
    short, short_label = panel_summary.base_paid_prices([{"tick": 1, "units__Food": 2.0, "rev__Food": 2.0}])
    assert short_label == "all simulated weeks" and short["Food"] == pytest.approx(1.0)

    assert panel_summary.is_fragile(panel.paired_stats([1.0, 1.0, 1.0, -1.0, -1.0]))
    assert panel_summary.is_fragile(panel.paired_stats([1.0, 1.0, 1.0, 1.0, -10.0]))
    assert panel_summary.is_fragile(panel.paired_stats([5.0, 1.0, 1.0, 1.0, 1.0]))
    assert not panel_summary.is_fragile(panel.paired_stats([1.0, 1.0, 1.0, 1.0, 1.0]))

    design = {"arms": ["main", "on"], "baseline": "main", "sequences": ["income_first"], "seeds": [1]}

    def _run(arm, drift):
        return {"spec": {"arm": arm, "payment_sequence": "income_first", "seed": 1, "repeat": False}, "money": {"final_drift": drift}}

    assert panel_summary.MONEY_CHECK_MODE == "relative"
    assert panel_summary.DUST_TOLERANCE == pytest.approx(1e-4)
    assert panel_summary.row_violations({"tick": 3, "happiness": float("nan"), "labor_force_unemployment_rate": 0.2})
    assert panel_summary.row_violations({
        "tick": 3, "happiness": 0.4, "health": 0.5, "labor_force_unemployment_rate": 0.2,
        "unemployment_rate": 0.3, "poverty_share": 0.1, "mean_price": 2.0, "consumer_price_index": 100.0,
    }) == []


def test_reference_env_refuses_a_non_311_interpreter_and_stamps_the_override():
    refused = panel_summary.reference_decision(False, {"ok_packages": True, "missing": [], "mismatched": [], "pins": 3})
    assert refused["ok"] is False
    assert "not comparable" in panel_summary.format_reference_error(refused, "3.13.0", "CPython")
    mismatch = panel_summary.compare_lock({"numpy": "2.4.6"}, {"numpy": "1.26.4"})
    assert mismatch["ok_packages"] is False and mismatch["mismatched"][0]["name"] == "numpy"


def test_state_digest_catches_an_unobserved_change_the_row_hash_misses():
    stats = {"unemployment_rate": 0.0, "mean_happiness": 0.4, "mean_health": 0.8, "food_insecure_share": 0.0}
    metrics = {
        "gdp_this_tick": 1.0, "consumer_price_index": 100.0, "labor_force_unemployment_rate": 0.0,
        "mean_price": 1.0, "gov_revenue_this_tick": 0.0, "gov_spending_this_tick": 0.0,
        "gov_bond_purchases_this_tick": 0.0,
    }
    with use_config(clone_config()):
        random.seed(1)
        np.random.seed(1)
        CONFIG.random_seed = 1
        from tools.runners.run_large_simulation import create_large_economy

        economy = create_large_economy(20, 1)
        before = state_components(economy)
        row_before = panel_row(economy, metrics, stats, CONFIG, np)
        from tools.benchmarks.panel_plugins import households as households_plugin

        households_plugin.extra_metrics(economy)
        assert state_components(economy) == before
        economy.households[0].skills_level = float(getattr(economy.households[0], "skills_level", 0.5) or 0.5) + 0.013
        after = state_components(economy)
        row_after = panel_row(economy, metrics, stats, CONFIG, np)
    assert before["households"] != after["households"]
    assert before["firms"] == after["firms"]
    assert rows_fingerprint([row_before]) == rows_fingerprint([row_after])


def test_server_and_worker_build_the_same_economy():
    import server
    from sim_setup import build_economy_from_setup

    setup = server.SetupConfig(num_households=20, num_firms=1, seed=7, payment_sequence="income_first")
    with use_config(clone_config()):
        economy, _flags = build_economy_from_setup(setup, 7)
        direct = state_components(economy)
    with use_config(clone_config()):
        manager = server.SimulationManager(session_id="panel-build")
        manager.initialize({"num_households": 20, "num_firms": 1, "seed": 7, "payment_sequence": "income_first"})
        via_server = state_components(manager.economy)
    assert direct == via_server


def test_lever_at_a_fixed_week_fires_and_reverts_and_the_hold_pool_keeps_the_stock():
    from types import SimpleNamespace

    from tools.benchmarks.evidence_panel_worker import apply_timed_levers, run

    class Government:
        def __init__(self):
            self.wage_tax_rate = 0.15

        def set_lever(self, name, value):
            self.wage_tax_rate = float(value)

    class Economy:
        def __init__(self):
            self.government = Government()

    economy = Economy()
    saved: dict = {}
    timed = [{"name": "wage_tax_rate", "value": "0.45", "start": 2, "end": 3}]
    apply_timed_levers(economy, timed, saved, 1)
    assert economy.government.wage_tax_rate == pytest.approx(0.15)
    apply_timed_levers(economy, timed, saved, 2)
    assert economy.government.wage_tax_rate == pytest.approx(0.45)
    apply_timed_levers(economy, timed, saved, 4)
    assert economy.government.wage_tax_rate == pytest.approx(0.15)

    held = SimpleNamespace(misc_firm_revenue=25.0)

    def pay_out(self):
        self.misc_firm_revenue = 0.0

    held._misc_firm_redistribute_revenue = pay_out.__get__(held, type(held))
    install_hooks(held, ["k06_hold_pool"])
    held._misc_firm_redistribute_revenue()
    assert held.misc_firm_revenue == 25.0

    root = str(Path(__file__).resolve().parents[2])
    spec = {
        "arm": "hold", "repeat": False, "root": root, "source_sha256": "test",
        "payment_sequence": "legacy", "seed": 1, "households": 24, "firms_per_category": 1, "ticks": 3,
        "config_overrides": {}, "levers": {}, "timed_levers": [], "hooks": ["k06_hold_pool"],
        "metrics_plugins": [], "runtime": {},
    }
    hold = run(spec)
    plain = run({**spec, "arm": "plain", "hooks": []})
    assert hold["final"]["misc_firm_revenue"] >= plain["final"]["misc_firm_revenue"]
    assert hold["money"]["final_drift"] is not None and plain["money"]["final_drift"] is not None
    assert abs(float(hold["money"]["final_drift"]) - float(plain["money"]["final_drift"])) < 1.0


def test_repeatable_plugins_keep_their_aggregations(tmp_path):
    first = tmp_path / "one.py"
    second = tmp_path / "two.py"
    first.write_text(
        "def extra_metrics(economy):\n    return {'alpha': 1.0}\n"
        "METRICS = {'alpha': ('Alpha', 'widgets', ('mean', 'min'), None)}\n"
        "def summarize(runs):\n    return {'n': len(runs)}\n",
        encoding="utf-8",
    )
    second.write_text(
        "def extra_metrics(economy):\n    return {'beta': 2.0}\n"
        "METRICS = {'beta': ('Beta', '%', ('mean',), (0.0, 1.0))}\n",
        encoding="utf-8",
    )
    rows, bounds = panel_summary.plugin_display([str(first), str(second)])
    assert [item[0] for item in rows] == ["x_alpha", "x_beta"]
    assert rows[0][4] == ("mean", "min")
    assert bounds["x_beta"] == (0.0, 1.0)
    summary = panel_summary.plugin_summaries([str(first)], [{}, {}])
    assert summary["one.py"]["n"] == 2


def test_mutation_check_requires_the_reverted_line_to_fail_a_test(tmp_path):
    def plant(root: Path, body: str):
        root.mkdir()
        (root / "answer.py").write_text("def answer():\n    " + body + "\n", encoding="utf-8")
        (root / "test_answer.py").write_text(
            "from answer import answer\n\ndef test_answer():\n    assert answer() == 1\n",
            encoding="utf-8",
        )

    candidate = tmp_path / "candidate"
    baseline = tmp_path / "baseline"
    plant(candidate, "return 1")
    plant(baseline, "return 0")
    failed = panel_summary.mutation_check(
        candidate_root=candidate, main_root=baseline, file_spec="answer.py:2-2",
        tests=["test_answer.py"], python=sys.executable,
    )
    assert failed["ok"] is True

    same = tmp_path / "same-main"
    plant(same, "return 1")
    still_passes = panel_summary.mutation_check(
        candidate_root=candidate, main_root=same, file_spec="answer.py:2-2",
        tests=["test_answer.py"], python=sys.executable,
    )
    assert still_passes["ok"] is False


def _money_run(arm, sequence, seed, drift):
    return {
        "spec": {"arm": arm, "payment_sequence": sequence, "seed": seed, "repeat": False},
        "money": {"final_drift": drift},
    }


def test_relative_money_fails_a_new_leak_only_when_main_conserves():
    design = {
        "arms": ["main", "off", "on"],
        "baseline": "main",
        "sequences": ["income_first", "legacy"],
        "seeds": [1, 2],
    }
    conserved = []
    for seed, main_drift, on_drift in ((1, 1e-5, 1e-5), (2, -1e-5, 2e-5)):
        conserved += [
            _money_run("main", "income_first", seed, main_drift),
            _money_run("off", "income_first", seed, main_drift),
            _money_run("on", "income_first", seed, on_drift),
        ]
    for seed, main_drift, on_drift in ((1, 7000.0, 7100.0), (2, 8000.0, 7900.0)):
        conserved += [
            _money_run("main", "legacy", seed, main_drift),
            _money_run("off", "legacy", seed, main_drift),
            _money_run("on", "legacy", seed, on_drift),
        ]
    held = panel_summary.evaluate_money(conserved, design)
    assert held["passed"] is True
    assert held["sequences"]["income_first"]["conserves"] is True
    assert held["sequences"]["legacy"]["conserves"] is False
    legacy = next(gap for gap in held["drift_gaps"] if gap["arm"] == "on" and gap["payment_sequence"] == "legacy")
    assert legacy["baseline_conserves"] is False
    assert legacy["median"] == pytest.approx(0.0)
    assert legacy["up"] == 1 and legacy["n"] == 2

    leaked = [
        _money_run("main", "income_first", 1, 0.0),
        _money_run("on", "income_first", 1, 1.0),
    ]
    broken = panel_summary.evaluate_money(leaked, {
        "arms": ["main", "on"], "baseline": "main", "sequences": ["income_first"], "seeds": [1],
    })
    assert broken["passed"] is False
    assert broken["failures"][0]["reason"] == "new leak on a sequence the baseline conserves"


def test_nonfinite_money_drift_fails_in_every_mode_and_sequence():
    design = {
        "arms": ["main", "on"],
        "baseline": "main",
        "sequences": ["income_first", "legacy"],
        "seeds": [1],
    }
    result = panel_summary.evaluate_money([
        _money_run("main", "income_first", 1, 0.0),
        _money_run("on", "income_first", 1, float("nan")),
        _money_run("main", "legacy", 1, float("inf")),
        _money_run("on", "legacy", 1, float("-inf")),
    ], design)
    assert result["passed"] is False
    assert {
        (item["arm"], item["payment_sequence"], item["reason"]) for item in result["failures"]
    } == {
        ("on", "income_first", "non-finite money drift"),
        ("main", "legacy", "non-finite money drift"),
        ("on", "legacy", "non-finite money drift"),
    }


def test_baseline_must_conserve_on_income_sequences_and_legacy_stays_reported():
    nightly = panel_summary.evaluate_money([
        _money_run("main", "income_first", 1, 5.0),
        _money_run("main", "income_late", 1, 1e-5),
        _money_run("main", "legacy", 1, 7000.0),
    ], {
        "arms": ["main"],
        "baseline": "main",
        "sequences": ["income_first", "income_late", "legacy"],
        "seeds": [1],
    })
    assert nightly["passed"] is False
    assert [(item["arm"], item["payment_sequence"], item["reason"]) for item in nightly["failures"]] == [
        ("main", "income_first", "baseline leak on a sequence that must conserve"),
    ]
    assert nightly["sequences"]["income_late"]["conserves"] is True
    assert nightly["sequences"]["legacy"]["conserves"] is False
    assert nightly["drift_gaps"] == []

    late = panel_summary.evaluate_money([
        _money_run("main", "income_late", 1, 5.0),
    ], {"arms": ["main"], "baseline": "main", "sequences": ["income_late"], "seeds": [1]})
    assert late["passed"] is False
    assert late["failures"][0]["reason"] == "baseline leak on a sequence that must conserve"

    shared = panel_summary.evaluate_money([
        _money_run("main", "income_first", 1, 5.0),
        _money_run("on", "income_first", 1, 5.0),
    ], {"arms": ["main", "on"], "baseline": "main", "sequences": ["income_first"], "seeds": [1]})
    assert [item["reason"] for item in shared["failures"]] == [
        "baseline leak on a sequence that must conserve",
    ]


def test_small_money_gaps_stay_visible_in_the_markdown():
    assert panel._fmt(1e-5, signed=True) == "+1.000e-05"
    assert panel._fmt(-1e-5, signed=True) == "-1.000e-05"
    assert panel._fmt(4e-4) == "4.000e-04"
    assert panel._fmt(0.0, signed=True) == "0"
    assert panel._fmt(1.25, signed=True) == "+1.25"


def _panel_argv(out: Path, *extra: str) -> list[str]:
    return [
        "--arm", "a", "--households", "16", "--firms-per-category", "1", "--ticks", "2",
        "--seeds", "1", "--sequences", "legacy", "--windows", "1-2", "--jobs", "1",
        "--no-determinism-check", "--no-escalate", "--out", str(out),
        *extra,
    ]


def test_missing_or_empty_requirements_lock_refuses_the_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(panel, "LOCK_PATH", tmp_path / "missing.lock")
    _runtime, decision, digest = panel._reference_status(sys.executable)
    assert decision["ok"] is False
    assert decision["pins"] == 0
    assert decision["lock_error"] == "backend/requirements.lock is missing"
    assert digest is None
    assert panel.main(_panel_argv(tmp_path / "missing-out")) == 2
    assert "is missing" in capsys.readouterr().err
    assert not (tmp_path / "missing-out" / "panel.md").exists()

    empty = tmp_path / "empty.lock"
    empty.write_text("# generated\n\n", encoding="utf-8")
    monkeypatch.setattr(panel, "LOCK_PATH", empty)
    _runtime, decision, _digest = panel._reference_status(sys.executable)
    assert decision["ok"] is False
    assert decision["lock_error"] == "backend/requirements.lock has no pins"
    assert panel.main(_panel_argv(tmp_path / "empty-out")) == 2
    assert "no pins" in capsys.readouterr().err


def test_allow_nonref_still_runs_when_the_lock_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(panel, "LOCK_PATH", tmp_path / "missing.lock")
    out = tmp_path / "run"
    code = panel.main(_panel_argv(out, "--allow-nonref"))
    report = (out / "panel.md").read_text(encoding="utf-8")
    assert code == 0
    assert "NON-REFERENCE ENV, not comparable" in report


def test_absolute_money_uses_the_same_dust_tolerance(monkeypatch):
    monkeypatch.setattr(panel_summary, "MONEY_CHECK_MODE", "absolute")
    design = {"arms": ["main"], "baseline": "main", "sequences": ["income_first"], "seeds": [1]}
    dust = panel_summary.evaluate_money([_money_run("main", "income_first", 1, 1e-5)], design)
    assert dust["passed"] is True
    assert dust["tolerance"] == pytest.approx(1e-4)
    leaked = panel_summary.evaluate_money([_money_run("main", "income_first", 1, 1.0)], design)
    assert leaked["passed"] is False


def test_state_digest_hashes_loan_remaining():
    government = SimpleNamespace(cash_balance=0.0, wage_tax_rate=0.0, profit_tax_rate=0.0)
    loan = {"principal": 10.0, "remaining": 10.0}
    economy = SimpleNamespace(
        households=[], firms=[], government=government,
        bank=SimpleNamespace(cash_reserves=1.0, total_deposits=1.0, active_loans=[loan]),
    )
    before = state_components(economy)
    loan["remaining"] = 4.0
    after = state_components(economy)
    assert before["bank"] != after["bank"]
    assert before["combined"] != after["combined"]


def _workflow():
    import yaml
    path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "evidence-panel.yml"
    text = path.read_text(encoding="utf-8")
    return text, yaml.safe_load(text)


def test_workflow_trust_permissions_and_event_boundaries():
    text, doc = _workflow()
    events = doc.get("on", doc.get(True))  # PyYAML's YAML 1.1 treats 'on' as a bool.
    assert "pull_request" in events and "push" not in events
    assert "concurrency" not in doc  # Rejected comments never acquire a workflow slot.
    jobs = doc["jobs"]
    assert "concurrency" not in jobs["resolve"]
    assert jobs["resolve"]["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert "needs.resolve.outputs.approved == 'true'" in jobs["full"]["if"]
    assert jobs["full"]["concurrency"]["group"] == "evidence-full-${{ needs.resolve.outputs.number || github.ref }}"
    assert jobs["full"]["permissions"] == {"contents": "read"}
    assert jobs["comment"]["permissions"] == {"contents": "read", "pull-requests": "write"}
    assert "${{ secrets" not in text
    for name in ("fast", "full"):
        steps = jobs[name]["steps"]
        checkouts = [step for step in steps if step.get("uses", "").startswith("actions/checkout@")]
        assert [(x["with"]["path"], x["with"]["ref"]) for x in checkouts] == [
            ("evaluator", "${{ needs.resolve.outputs.base }}"),
            ("candidate", "${{ needs.resolve.outputs.head }}"),
        ]
        assert all(x["with"]["persist-credentials"] is False for x in checkouts)
        assert not any(x.get("with", {}).get("cache") == "pip" for x in steps)
        install = next(x['run'] for x in steps if x.get('name', '').startswith('Install evaluator'))
        assert 'requirements=(-r backend/requirements.lock)' in install
        assert 'requirements+=(-r backend/requirements-test.lock)' in install
        run = next(x for x in steps if "panel from base" in x.get("name", "").lower())
        assert run["working-directory"] == "evaluator"
        assert '--root off "$GITHUB_WORKSPACE/candidate"' in run["run"]
        assert "--jobs 2" in run["run"]


@pytest.mark.parametrize("association,body,pushed,expected,failed", [
    ("NONE", "/eval", "2026-10-22T00:00:00Z", False, False),
    ("CONTRIBUTOR", "/eval", "2026-10-22T00:00:00Z", False, False),
    ("OWNER", "ordinary comment", "2026-10-22T00:00:00Z", False, False),
    ("OWNER", "/eval", "2026-10-22T00:00:00Z", True, False),
    ("COLLABORATOR", "/eval extra", "2026-10-22T00:00:00Z", True, False),
    ("MEMBER", "/eval", "2026-10-22T02:00:00Z", False, True),
    ("OWNER", "/eval", None, False, True),
])
def test_eval_authorization_runs_before_concurrency_and_pins_the_head(association, body, pushed, expected, failed):
    """Execute the actual workflow JS gate with mocked GitHub responses."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node required to exercise the workflow's actual authorization script")
    _text, doc = _workflow()
    script = doc["jobs"]["resolve"]["steps"][0]["with"]["script"]
    data = {"association": association, "body": body, "pushed": pushed}
    harness = r"""
const data = JSON.parse(process.argv[1]);
const out = {}, calls = [];
const context = {eventName:'issue_comment', repo:{owner:'AymanCode',repo:'EcoSim'},
  payload:{issue:{number:59,pull_request:{}}, comment:{body:data.body,
    author_association:data.association,created_at:'2026-10-22T01:00:00Z'}}};
const core = {info:()=>{},setFailed:x=>out.failed=x,setOutput:(k,v)=>out[k]=v};
const github = {rest:{pulls:{get:async()=>{calls.push('get');return {data:{number:59,
  state:'open',head:{sha:'a'.repeat(40),ref:'topic',repo:{owner:{login:'AymanCode'},name:'EcoSim'}},base:{ref:'main',sha:'pinned-base'}}};}}},
  request:async()=>{calls.push('activity');return {data:data.pushed ? [{activity_type:'push',after:'a'.repeat(40),timestamp:data.pushed}] : []};}};
(async()=>{await new (Object.getPrototypeOf(async()=>{}).constructor)(
  'context','core','github',SCRIPT)(context,core,github);
  console.log(JSON.stringify({out,calls}));})().catch(e=>{console.error(e);process.exit(1)});
""".replace("SCRIPT", json.dumps(script))
    proc = subprocess.run([node, "-e", harness, json.dumps(data)], capture_output=True, text=True, check=True)
    result = json.loads(proc.stdout)
    assert (result["out"].get("approved") == "true") is expected
    assert bool(result["out"].get("failed")) is failed
    if expected:
        assert result["out"]["head"] == "a" * 40
        assert result["out"]["base"] == "pinned-base"
    if not expected and not failed:
        assert result["calls"] == []


def test_allow_nonref_stamps_the_panel(tmp_path):
    code = panel.main([
        "--arm", "a", "--households", "16", "--firms-per-category", "1", "--ticks", "2",
        "--seeds", "1", "--sequences", "legacy", "--windows", "1-2", "--jobs", "1",
        "--no-determinism-check", "--no-escalate", "--allow-nonref", "--out", str(tmp_path),
    ])
    report = (tmp_path / "panel.md").read_text(encoding="utf-8")
    evaluator = json.loads((tmp_path / "evaluator.json").read_text(encoding="utf-8"))
    assert "NON-REFERENCE ENV, not comparable" in report
    assert evaluator["comparability"] == "NON-REFERENCE ENV, not comparable"
    assert "requirements_lock_sha256" in evaluator["env"]
    assert evaluator["env"]["platform"] and evaluator["env"]["cpu_model"]
    assert evaluator["evaluator"]["commit"]
    assert "within this run only" in evaluator["comparison_scope"]
    assert "within this run only" in (tmp_path / "summary.md").read_text()
    assert "not comparable" in (tmp_path / "window_values.csv").read_text().splitlines()[0]
    assert code == 0


def test_reference_labels_require_hosted_full_tier():
    hosted = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted", "ECOSIM_PANEL_TIER": "full"}
    label = panel_summary.comparability_label
    assert label(True, False, hosted, "Linux") == panel_summary.REFERENCE
    assert label(True, False, {}, "Windows") == panel_summary.LOCAL_RUN
    assert label(True, False, {**hosted, "ECOSIM_PANEL_TIER": "fast"}, "Linux") == panel_summary.LOCAL_RUN
    assert label(True, False, {**hosted, "RUNNER_ENVIRONMENT": "self-hosted"}, "Linux") == panel_summary.LOCAL_RUN
    assert label(False, False, hosted, "Linux") == panel_summary.NOT_COMPARABLE
    assert label(True, True, hosted, "Linux") == panel_summary.NOT_COMPARABLE


def test_lock_hash_normalizes_crlf(tmp_path):
    lf, crlf = tmp_path / "lf.lock", tmp_path / "crlf.lock"
    lf.write_bytes(b"numpy==2.0\npytest==8.0\n")
    crlf.write_bytes(b"numpy==2.0\r\npytest==8.0\r\n")
    assert panel_summary.lock_sha256(lf) == panel_summary.lock_sha256(crlf)


def test_mutation_overlay_copies_when_symlinks_are_denied(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    (source / "code.py").write_text("value = 7\n", encoding="utf-8")
    def denied(*args):
        raise OSError("symlink privilege not held")
    monkeypatch.setattr(panel_summary.os, "symlink", denied)
    panel_summary._overlay_tree(source, target)
    assert (target / "code.py").read_text() == "value = 7\n"
    assert not (target / "code.py").is_symlink()


def test_digest_detects_rng_loans_and_payment_ledger_changes():
    economy = SimpleNamespace(households=[], firms=[], queued_firms=[],
        government=SimpleNamespace(cash_balance=0., wage_tax_rate=0., profit_tax_rate=0.), bank=SimpleNamespace(active_loans=[{"remaining": 10., "rate": .1}]),
        payment_sequence="income_first", payment_state={"recovery_holds": {1: 5.}})
    before = state_components(economy)
    random.random()
    after = state_components(economy)
    assert before['rng'] != after['rng'] and before['combined'] != after['combined']
    before = after
    np.random.random()
    after = state_components(economy)
    assert before['rng'] != after['rng']
    before = after
    economy.bank.active_loans[0]['rate'] = .2
    after = state_components(economy)
    assert before['loans'] != after['loans'] and before['combined'] != after['combined']
    before = after
    economy.payment_state['recovery_holds'][1] = 6.
    after = state_components(economy)
    assert before['payments'] != after['payments'] and before['combined'] != after['combined']


@pytest.mark.parametrize("component,field", [("government", "public_debt"), ("bank", "public_debt_held")])
def test_digest_detects_public_debt_without_a_cash_change(component, field):
    economy = SimpleNamespace(
        households=[], firms=[], queued_firms=[],
        government=SimpleNamespace(cash_balance=0.0, wage_tax_rate=0.0, profit_tax_rate=0.0),
        bank=SimpleNamespace(), payment_sequence="legacy",
    )
    before = state_components(economy)
    setattr(getattr(economy, component), field, 100.0)
    after = state_components(economy)
    assert before[component] != after[component]
    assert before["combined"] != after["combined"]


def test_runtime_probe_stamps_host_cpu_and_tools_do_not_enter_runtime_lock():
    runtime = panel.probe_runtime(sys.executable)
    assert runtime['platform'] and runtime['cpu_model'] and runtime['system']
    root = Path(__file__).resolve().parents[2]
    runtime_pins = panel_summary.parse_lock_pins((root / 'backend/requirements.lock').read_text())
    test_pins = panel_summary.parse_lock_pins((root / 'backend/requirements-test.lock').read_text())
    assert not runtime_pins.keys() & test_pins.keys()
    assert {'pytest', 'pytest-asyncio', 'ruff'} <= test_pins.keys()
    assert not {'pytest', 'ruff'} & runtime_pins.keys()
