"""Summary and Markdown rendering for EcoSim benchmarks."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from .common import confidence_interval_95, mean, percentile, sample_stdev


def summarize_duration_values(values: Sequence[float]) -> dict[str, float | int]:
    durations = [float(value) for value in values]
    tick_count = len(durations)
    total_seconds = sum(durations) / 1000.0
    ticks_per_second = tick_count / total_seconds if total_seconds > 0 else 0.0
    return {
        "tick_count": tick_count,
        "mean_ms": round(mean(durations), 3),
        "p50_ms": round(percentile(durations, 50), 3),
        "p95_ms": round(percentile(durations, 95), 3),
        "p99_ms": round(percentile(durations, 99), 3),
        "min_ms": round(min(durations), 3) if durations else 0.0,
        "max_ms": round(max(durations), 3) if durations else 0.0,
        "ticks_per_second": round(ticks_per_second, 4),
        "simulated_weeks_per_minute": round(ticks_per_second * 60.0, 2),
    }


def summarize_tick_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    durations = [float(row["tick_duration_ms"]) for row in rows]
    summary: dict[str, Any] = {
        "overall": summarize_duration_values(durations),
        "phases": {},
        "households": {},
        "seeds": {},
        "failure_count": sum(1 for row in rows if row.get("error")),
    }

    phase_groups: dict[str, list[float]] = defaultdict(list)
    household_groups: dict[str, list[float]] = defaultdict(list)
    seed_groups: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        duration = float(row["tick_duration_ms"])
        phase_groups[str(row.get("phase", "unknown"))].append(duration)
        household_groups[str(row.get("households", "unknown"))].append(duration)
        seed_groups[str(row.get("seed", "unknown"))].append(duration)

    summary["phases"] = {key: summarize_duration_values(values) for key, values in sorted(phase_groups.items())}
    summary["households"] = {
        key: summarize_duration_values(values)
        for key, values in sorted(household_groups.items(), key=lambda item: int(item[0]) if item[0].isdigit() else 0)
    }
    summary["seeds"] = {key: summarize_duration_values(values) for key, values in sorted(seed_groups.items())}
    return summary


def summarize_warehouse_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"run_count": 0, "total_rows_written": 0, "overall_rows_per_second": 0.0, "runs": []}

    total_rows = sum(int(row.get("rows_written", 0)) for row in rows)
    total_insert_seconds = sum(float(row.get("insert_seconds", 0.0)) for row in rows)
    query_latencies = [float(row.get("summary_query_ms", 0.0)) for row in rows]
    query_suite_latencies = [float(row.get("p95_query_suite_ms", 0.0)) for row in rows]
    flush_p95s = [float(row.get("p95_flush_ms", 0.0)) for row in rows]
    overheads = [float(row.get("write_overhead_pct", 0.0)) for row in rows]
    db_sizes = [float(row.get("database_size_mb", 0.0) or 0.0) for row in rows]
    wal_sizes = [float(row.get("wal_size_mb", 0.0) or 0.0) for row in rows]
    return {
        "run_count": len(rows),
        "total_rows_written": total_rows,
        "overall_rows_per_second": round(total_rows / total_insert_seconds, 2) if total_insert_seconds > 0 else 0.0,
        "p95_summary_query_ms": round(percentile(query_latencies, 95), 3),
        "p95_query_suite_ms": round(percentile(query_suite_latencies, 95), 3),
        "p95_flush_ms": round(percentile(flush_p95s, 95), 3),
        "mean_write_overhead_pct": round(mean(overheads), 3),
        "max_database_size_mb": round(max(db_sizes), 3) if db_sizes else 0.0,
        "max_wal_size_mb": round(max(wal_sizes), 3) if wal_sizes else 0.0,
        "runs": list(rows),
    }


def summarize_policy_runs(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    policy_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        policy_groups[str(row["policy"])].append(row)

    policies: dict[str, Any] = {}
    for policy, group in sorted(policy_groups.items()):
        gdps = [float(row.get("final_gdp", 0.0)) for row in group]
        unemployment = [float(row.get("final_unemployment_rate", 0.0)) for row in group]
        happiness = [float(row.get("final_happiness", 0.0)) for row in group]
        gov_cash = [float(row.get("final_government_cash", 0.0)) for row in group]
        policies[policy] = {
            "runs": len(group),
            "avg_gdp": round(mean(gdps), 3),
            "gdp_stdev": round(sample_stdev(gdps), 3),
            "gdp_ci95": round(confidence_interval_95(gdps), 3),
            "avg_unemployment_rate": round(mean(unemployment), 5),
            "unemployment_ci95": round(confidence_interval_95(unemployment), 5),
            "avg_happiness": round(mean(happiness), 5),
            "avg_government_cash": round(mean(gov_cash), 3),
        }

    best_by_avg_gdp = max(policies.items(), key=lambda item: item[1]["avg_gdp"], default=("", {}))
    best_by_unemployment = min(
        policies.items(),
        key=lambda item: item[1]["avg_unemployment_rate"],
        default=("", {}),
    )
    return {
        "policy_count": len(policies),
        "run_count": len(rows),
        "policies": policies,
        "best_by_avg_gdp": {"policy": best_by_avg_gdp[0], **best_by_avg_gdp[1]} if best_by_avg_gdp[0] else {},
        "best_by_unemployment": (
            {"policy": best_by_unemployment[0], **best_by_unemployment[1]} if best_by_unemployment[0] else {}
        ),
    }


def _metadata_lines(metadata: Mapping[str, Any]) -> list[str]:
    return [
        f"- Commit: `{metadata.get('commit', 'unknown')}`",
        f"- Python: `{metadata.get('python', 'unknown')}`",
        f"- Platform: `{metadata.get('platform', 'unknown')}`",
        f"- Logical CPUs: `{metadata.get('logical_cpu_count', 'unknown')}`",
    ]


def _summary_table(title: str, rows: Mapping[str, Mapping[str, Any]]) -> list[str]:
    lines = [f"## {title}", "", "| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |", "|---|---:|---:|---:|---:|---:|---:|"]
    for group, values in rows.items():
        lines.append(
            "| {group} | {ticks} | {p50} | {p95} | {p99} | {tps} | {wpm} |".format(
                group=group,
                ticks=values.get("tick_count", 0),
                p50=values.get("p50_ms", 0.0),
                p95=values.get("p95_ms", 0.0),
                p99=values.get("p99_ms", 0.0),
                tps=values.get("ticks_per_second", 0.0),
                wpm=values.get("simulated_weeks_per_minute", 0.0),
            )
        )
    return lines


def render_sim_summary(
    *,
    metadata: Mapping[str, Any],
    summary: Mapping[str, Any],
    profile_paths: Sequence[str] | None = None,
) -> str:
    overall = summary.get("overall", {})
    p95 = overall.get("p95_ms", 0.0)
    weeks_per_minute = overall.get("simulated_weeks_per_minute", 0.0)
    household_keys = [int(key) for key in summary.get("households", {}).keys() if str(key).isdigit()]
    max_households = max(household_keys, default=0)
    scale_phrase = (
        "at 10k+ agents"
        if max_households >= 10_000
        else f"toward the 10k+ agents target at `{max_households}` households"
    )
    lines = [
        "# EcoSim Simulation Throughput Benchmark",
        "",
        "## Runtime Context",
        "",
        *_metadata_lines(metadata),
        "",
        "## Overall",
        "",
        f"- Ticks measured: `{overall.get('tick_count', 0)}`",
        f"- p50 tick latency: `{overall.get('p50_ms', 0.0)} ms`",
        f"- p95 tick latency: `{p95} ms`",
        f"- p99 tick latency: `{overall.get('p99_ms', 0.0)} ms`",
        f"- Throughput: `{overall.get('ticks_per_second', 0.0)} ticks/sec`",
        "",
        *_summary_table("By Household Scale", summary.get("households", {})),
        "",
        *_summary_table("By Tick Phase", summary.get("phases", {})),
        "",
        "## Evidence Summary",
        "",
        (
            f"- The Python agent-based simulator was measured {scale_phrase}, "
            f"with p50/p95/p99 tick latency and `{weeks_per_minute}` simulated weeks/minute "
            f"at `{p95} ms` p95 tick latency on the recorded local environment."
        ),
        (
            "- The harness records commit/runtime metadata, CSV/JSON outputs, and optional profiles "
            "so results can be compared and reproduced."
        ),
    ]
    if profile_paths:
        lines.extend(["", "## Profile Artifacts", ""])
        lines.extend(f"- `{path}`" for path in profile_paths)
    return "\n".join(lines)


def render_warehouse_summary(*, metadata: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    lines = [
        "# EcoSim Warehouse Ingest Benchmark",
        "",
        "## Runtime Context",
        "",
        *_metadata_lines(metadata),
        "",
        "## Results",
        "",
        f"- Runs measured: `{summary.get('run_count', 0)}`",
        f"- Rows written: `{summary.get('total_rows_written', 0)}`",
        f"- Aggregate ingest throughput: `{summary.get('overall_rows_per_second', 0.0)} rows/sec`",
        f"- p95 summary query latency: `{summary.get('p95_summary_query_ms', 0.0)} ms`",
        f"- p95 query-suite latency: `{summary.get('p95_query_suite_ms', 0.0)} ms`",
        f"- p95 flush latency: `{summary.get('p95_flush_ms', 0.0)} ms`",
        f"- Mean write overhead: `{summary.get('mean_write_overhead_pct', 0.0)}%`",
        f"- Max SQLite DB size: `{summary.get('max_database_size_mb', 0.0)} MB`",
        f"- Max SQLite WAL size: `{summary.get('max_wal_size_mb', 0.0)} MB`",
        "",
        "## Evidence Summary",
        "",
        (
            "- The SQLite/PostgreSQL-compatible warehouse benchmark wrote "
            f"`{summary.get('total_rows_written', 0)}` analytical rows at "
            f"`{summary.get('overall_rows_per_second', 0.0)} rows/sec` with "
            f"`{summary.get('p95_summary_query_ms', 0.0)} ms` p95 summary-query latency."
        ),
    ]
    return "\n".join(lines)


def render_policy_sweep_summary(*, metadata: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    lines = [
        "# EcoSim Policy Sweep Benchmark",
        "",
        "## Runtime Context",
        "",
        *_metadata_lines(metadata),
        "",
        "## Results",
        "",
        f"- Policies measured: `{summary.get('policy_count', 0)}`",
        f"- Runs measured: `{summary.get('run_count', 0)}`",
        f"- Best average GDP policy: `{summary.get('best_by_avg_gdp', {}).get('policy', 'n/a')}`",
        f"- Best unemployment policy: `{summary.get('best_by_unemployment', {}).get('policy', 'n/a')}`",
        "",
        "| Policy | Runs | Avg GDP | GDP 95% CI | Avg Unemployment | Unemployment 95% CI | Avg Happiness |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for policy, values in summary.get("policies", {}).items():
        lines.append(
            f"| {policy} | {values['runs']} | {values['avg_gdp']} | {values['gdp_ci95']} | "
            f"{values['avg_unemployment_rate']} | {values['unemployment_ci95']} | {values['avg_happiness']} |"
        )
    lines.extend(
        [
            "",
            "## Evidence Summary",
            "",
            (
                "- Reproducible policy sweeps report confidence intervals "
                "for GDP, unemployment, and welfare outcomes across multiple seeds."
            ),
        ]
    )
    return "\n".join(lines)
