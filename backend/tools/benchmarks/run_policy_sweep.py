"""Non-LLM policy sweep benchmark CLI."""

from __future__ import annotations

import argparse
import contextlib
import io
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG
from run_evidence import RunEvidence, comparison_evidence, model_identity, write_evidence
from tools.runners.run_large_simulation import compute_household_stats, create_large_economy

from .common import (
    BenchmarkPaths,
    build_run_id,
    collect_metadata,
    default_results_root,
    parse_int_list,
    parse_str_list,
    write_json,
    write_markdown,
    write_rows_csv,
)
from .reporting import render_policy_sweep_summary, summarize_policy_runs


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    CONFIG.random_seed = int(seed)


def _create_economy_quietly(num_households: int, firms_per_category: int, verbose: bool):
    if verbose:
        return create_large_economy(num_households, firms_per_category)
    with contextlib.redirect_stdout(io.StringIO()):
        return create_large_economy(num_households, firms_per_category)


def expand_policy_specs(policy_groups: list[str]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for group in policy_groups:
        if group == "baseline":
            specs.append({"name": "baseline", "levers": {}})
        elif group == "tax_grid":
            for wage_tax, profit_tax in ((0.10, 0.15), (0.15, 0.20), (0.25, 0.25)):
                specs.append(
                    {
                        "name": f"tax_w{int(wage_tax * 100)}_p{int(profit_tax * 100)}",
                        "levers": {"wage_tax_rate": wage_tax, "profit_tax_rate": profit_tax},
                    }
                )
        elif group == "benefit_grid":
            for benefit_level in ("low", "neutral", "high", "crisis"):
                specs.append({"name": f"benefit_{benefit_level}", "levers": {"benefit_level": benefit_level}})
        elif group == "wage_grid":
            for wage_policy in ("low", "neutral", "high"):
                specs.append({"name": f"minimum_wage_{wage_policy}", "levers": {"minimum_wage_policy": wage_policy}})
        elif group == "subsidy_grid":
            for target in ("food", "services"):
                for level in (10, 25):
                    specs.append(
                        {
                            "name": f"subsidy_{target}_{level}",
                            "levers": {"sector_subsidy_target": target, "sector_subsidy_level": level},
                        }
                    )
        else:
            raise ValueError(f"Unknown policy group '{group}'")

    unique: dict[str, dict[str, Any]] = {}
    for spec in specs:
        unique[spec["name"]] = spec
    return list(unique.values())


def _apply_policy(economy, levers: dict[str, Any]) -> None:
    for lever, value in levers.items():
        economy.government.set_lever(lever, value)


def run_policy_sweep(
    *,
    policy_groups: list[str],
    seeds: list[int],
    households: int,
    ticks: int,
    firms_per_category: int,
    output_root: Path,
    verbose: bool,
) -> dict[str, Any]:
    paths = BenchmarkPaths.create(output_root, "policy-sweep")
    specs = expand_policy_specs(policy_groups)
    rows: list[dict[str, Any]] = []
    evidence_runs = []
    model = model_identity()
    evidence_path = paths.run_dir / "comparison-evidence.json"

    def save_evidence():
        write_evidence(evidence_path, comparison_evidence(
            model=model, runs=evidence_runs, runner="backend.tools.benchmarks.run_policy_sweep",
            planned_runs=[{"policy": spec["name"], "seed": seed, "requested_policy": spec["levers"]}
                          for spec in specs for seed in seeds],
            metric_schema={"source": "run_policy_sweep.run_policy_sweep + compute_household_stats",
                "timing": "elapsed_seconds covers the step loop, including settings observations; excludes initialization, final metric collection and sidecar I/O.",
                "overrides": {"final_unemployment_rate": "1 minus mean household is_employed across all households, regardless of count_cannot_work_as_unemployed."},
                "aliases": {"final_gdp": "gdp_this_tick", "final_unemployment_rate": "unemployment_rate",
                    "final_happiness": "mean_happiness", "final_health": "mean_health",
                    "final_government_cash": "government_cash"}},
        ))

    for spec in specs:
        for seed in seeds:
            if verbose:
                print(
                    f"[policy] policy={spec['name']} seed={seed} households={households} ticks={ticks}",
                    flush=True,
                )
            _set_seed(seed)
            run_id = build_run_id("policy", {"policy": spec["name"], "seed": seed, "households": households})
            evidence = RunEvidence(run_id=run_id, seed=seed, ticks=ticks,
                factory={"households": households, "firms_per_category": firms_per_category},
                requested_policy=spec["levers"])
            evidence_runs.append(evidence.data)
            save_evidence()
            economy = None
            stats, metrics = {}, {}
            elapsed = 0.0
            failure = None
            phase = "initialization"
            try:
                economy = _create_economy_quietly(households, firms_per_category, verbose=verbose)
                evidence.observe(economy, phase="initialized")
                phase = "policy_application"
                _apply_policy(economy, spec["levers"])
                evidence.policy_applied(economy)
                phase = "step"
                started = time.perf_counter()
                try:
                    for tick in range(ticks):
                        if verbose and (tick == 0 or tick % 20 == 0):
                            print(f"[policy] run={run_id} tick={tick}/{ticks}", flush=True)
                        evidence.observe(economy, phase="before_step")
                        economy.step()
                        evidence.completed += 1
                finally:
                    elapsed = time.perf_counter() - started
                phase = "metrics"
                stats = compute_household_stats(economy.households)
                metrics = economy.get_economic_metrics()
            except Exception as exc:  # Errors remain visible in both rows and evidence.
                failure = exc
            evidence.finish(economy, error=failure, phase=phase)
            save_evidence()
            rows.append({
                "run_id": run_id, "policy": spec["name"], "policy_group": ",".join(policy_groups),
                "levers_json": spec["levers"], "seed": seed, "households": households,
                "ticks_requested": ticks, "ticks_completed": evidence.completed,
                "elapsed_seconds": round(elapsed, 4),
                "ticks_per_second": round(evidence.completed / elapsed, 4) if elapsed > 0 else 0.0,
                "final_gdp": float(metrics["gdp_this_tick"]) if metrics else None,
                "final_unemployment_rate": float(stats["unemployment_rate"]) if stats else None,
                "final_happiness": float(stats["mean_happiness"]) if stats else None,
                "final_health": float(stats["mean_health"]) if stats else None,
                "final_government_cash": float(economy.government.cash_balance) if economy is not None else None,
                "failed": failure is not None,
                "error": f"{type(failure).__name__}: {failure}" if failure else "",
            })
            if verbose:
                print(
                    f"[policy] run={run_id} status={evidence.data['status']} ticks_completed={evidence.completed} "
                    f"ticks_per_sec={rows[-1]['ticks_per_second']}",
                    flush=True,
                )

    summary = summarize_policy_runs([row for row in rows if not row.get("failed")])
    metadata = collect_metadata(
        {
            "benchmark": "policy-sweep",
            "policy_groups": policy_groups,
            "expanded_policy_count": len(specs),
            "seeds": seeds,
            "households": households,
            "ticks": ticks,
        }
    )
    markdown = render_policy_sweep_summary(metadata=metadata, summary=summary)
    rows_csv = write_rows_csv(paths, "policy_rows", rows)
    summary_md = write_markdown(paths, "summary", markdown)
    raw_json = write_json(paths, "raw", {"metadata": metadata, "summary": summary, "rows": rows})
    return {
        "paths": paths,
        "metadata": metadata,
        "summary": summary,
        "rows": rows,
        "artifacts": {"rows_csv": rows_csv, "summary_md": summary_md, "raw_json": raw_json, "comparison_evidence": evidence_path},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run non-LLM EcoSim policy sweeps.")
    parser.add_argument("--seeds", default="42,43,44", help="Comma-separated random seeds.")
    parser.add_argument(
        "--policies",
        default="baseline,tax_grid,benefit_grid",
        help="Comma-separated groups: baseline,tax_grid,benefit_grid,wage_grid,subsidy_grid.",
    )
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--ticks", type=int, default=80)
    parser.add_argument("--firms-per-category", type=int, default=10)
    parser.add_argument("--output-root", type=Path, default=default_results_root())
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_policy_sweep(
        policy_groups=parse_str_list(args.policies),
        seeds=parse_int_list(args.seeds),
        households=args.households,
        ticks=args.ticks,
        firms_per_category=args.firms_per_category,
        output_root=args.output_root,
        verbose=args.verbose,
    )
    print(f"Wrote policy sweep artifacts to {result['paths'].run_dir}")
    print(f"Best average GDP policy: {result['summary'].get('best_by_avg_gdp', {}).get('policy', 'n/a')}")
    return 1 if any(row["failed"] for row in result["rows"]) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
