"""Contracts for the shared evidence panel (tools/benchmarks/run_evidence_panel.py)."""

import json
import re

import pytest

from config import CONFIG, clone_config, use_config
from tools.benchmarks import run_evidence_panel as panel
from tools.benchmarks.evidence_panel_worker import apply_config_overrides


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
    assert plan["on"] == {"config_overrides": {"households.poverty_threshold": "250"}, "levers": {"wage_tax_rate": "0.3"}}
    assert plan["off"] == {"config_overrides": {}, "levers": {}}

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
    return panel.main([
        "--households", "40", "--firms-per-category", "2", "--ticks", "6",
        "--seeds", "1,2", "--sequences", "income_first,legacy", "--windows", "1-3,4-",
        "--jobs", "4", "--out", str(tmp_path), *extra,
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


def test_panel_fails_loudly_on_a_misspelled_flag(tmp_path):
    exit_code = _main(tmp_path, "--arm", "base", "--arm", "typo", "--set", "typo", "households.skills_dynamicz=True")

    assert exit_code == 1
    failures = json.loads((tmp_path / "panel.json").read_text(encoding="utf-8"))["failures"]
    assert failures and all("skills_dynamicz" in "\n".join(f["stderr_tail"]) for f in failures)
    assert not (tmp_path / "panel.md").exists()
