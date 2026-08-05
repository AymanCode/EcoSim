import csv
import json
from pathlib import Path

from tools.benchmarks.common import (
    BenchmarkPaths,
    build_run_id,
    parse_int_list,
    percentile,
    write_json,
    write_rows_csv,
)
from tools.benchmarks.run_sim_bench import _phase_for_tick
from tools.benchmarks.reporting import (
    render_policy_sweep_summary,
    render_sim_summary,
    summarize_policy_runs,
    summarize_tick_rows,
)
from config import CONFIG
from tools.benchmarks import regression_snapshot, run_policy_sweep, run_sim_bench, run_warehouse_bench


def test_parse_int_list_rejects_empty_values():
    assert parse_int_list("1000, 5000,10000") == [1000, 5000, 10000]

    try:
        parse_int_list("1000,,5000")
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("parse_int_list should reject empty list entries")


def test_percentile_uses_sorted_nearest_rank():
    values = [40.0, 10.0, 30.0, 20.0]

    assert percentile(values, 50) == 20.0
    assert percentile(values, 95) == 40.0
    assert percentile([], 95) == 0.0


def test_summarize_tick_rows_splits_warmup_and_active_market():
    rows = [
        {"households": 1000, "tick": 0, "phase": "warmup", "tick_duration_ms": 100.0},
        {"households": 1000, "tick": 1, "phase": "warmup", "tick_duration_ms": 200.0},
        {"households": 1000, "tick": 10, "phase": "active_market", "tick_duration_ms": 400.0},
        {"households": 1000, "tick": 11, "phase": "active_market", "tick_duration_ms": 800.0},
    ]

    summary = summarize_tick_rows(rows)

    assert summary["overall"]["tick_count"] == 4
    assert summary["overall"]["p50_ms"] == 200.0
    assert summary["overall"]["p95_ms"] == 800.0
    assert summary["phases"]["warmup"]["tick_count"] == 2
    assert summary["phases"]["active_market"]["p50_ms"] == 400.0
    assert summary["households"]["1000"]["p95_ms"] == 800.0


def test_sim_phase_label_distinguishes_private_firm_ramp_from_full_market():
    assert _phase_for_tick(tick_before=9, warmup_ticks=10, private_active_count=0, queued_firm_count=296) == "warmup"
    assert (
        _phase_for_tick(tick_before=10, warmup_ticks=10, private_active_count=11, queued_firm_count=286)
        == "private_firm_ramp"
    )
    assert (
        _phase_for_tick(tick_before=40, warmup_ticks=10, private_active_count=296, queued_firm_count=0)
        == "full_private_market"
    )


def test_write_outputs_create_json_and_csv(tmp_path: Path):
    paths = BenchmarkPaths.create(tmp_path, "sim", timestamp="2026-05-16-120000")
    payload = {"kind": "sim", "rows": 2}
    rows = [{"tick": 1, "duration_ms": 12.3}, {"tick": 2, "duration_ms": 14.5}]

    json_path = write_json(paths, "raw", payload)
    csv_path = write_rows_csv(paths, "ticks", rows)

    assert json.loads(json_path.read_text()) == payload
    with csv_path.open(newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[0]["tick"] == "1"
    assert csv_rows[1]["duration_ms"] == "14.5"


def test_render_sim_summary_contains_evidence_and_context():
    metadata = {
        "commit": "abc1234",
        "python": "3.11.9",
        "platform": "Windows",
        "logical_cpu_count": 24,
    }
    summary = {
        "overall": {
            "tick_count": 4,
            "p50_ms": 200.0,
            "p95_ms": 800.0,
            "p99_ms": 800.0,
            "ticks_per_second": 2.0,
        },
        "households": {"1000": {"p95_ms": 800.0, "ticks_per_second": 2.0}},
        "phases": {"active_market": {"tick_count": 2, "p95_ms": 800.0}},
    }

    markdown = render_sim_summary(metadata=metadata, summary=summary, profile_paths=["profile.txt"])

    assert "Evidence Summary" in markdown
    assert "10k+ agents" in markdown
    assert "abc1234" in markdown
    assert "profile.txt" in markdown


def test_policy_sweep_summary_reports_best_gdp_and_variance():
    rows = [
        {"policy": "baseline", "seed": 42, "final_gdp": 100.0, "final_unemployment_rate": 0.2},
        {"policy": "baseline", "seed": 43, "final_gdp": 120.0, "final_unemployment_rate": 0.1},
        {"policy": "benefit_high", "seed": 42, "final_gdp": 90.0, "final_unemployment_rate": 0.3},
    ]

    summary = summarize_policy_runs(rows)
    markdown = render_policy_sweep_summary(metadata={"commit": "abc1234"}, summary=summary)

    assert summary["policy_count"] == 2
    assert summary["best_by_avg_gdp"]["policy"] == "baseline"
    assert summary["policies"]["baseline"]["runs"] == 2
    assert "confidence intervals" in markdown.lower()


def test_build_run_id_is_filesystem_safe():
    run_id = build_run_id("policy sweep", {"seed": 42, "tax": 0.15})

    assert " " not in run_id
    assert "/" not in run_id
    assert "policy-sweep" in run_id


def test_benchmark_modules_share_simulation_config_singleton():
    """Benchmark harnesses must mutate the same CONFIG instance used by simulations."""
    assert run_sim_bench.CONFIG is CONFIG
    assert run_policy_sweep.CONFIG is CONFIG
    assert run_warehouse_bench.CONFIG is CONFIG
    assert regression_snapshot.CONFIG is CONFIG
