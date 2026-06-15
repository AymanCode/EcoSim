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

    for spec in specs:
        for seed in seeds:
            if verbose:
                print(
                    f"[policy] policy={spec['name']} seed={seed} households={households} ticks={ticks}",
                    flush=True,
                )
            _set_seed(seed)
            run_id = build_run_id("policy", {"policy": spec["name"], "seed": seed, "households": households})
            economy = _create_economy_quietly(households, firms_per_category, verbose=verbose)
            _apply_policy(economy, spec["levers"])
            started = time.perf_counter()
            failed = False
            error = ""
            for tick in range(ticks):
                if verbose and (tick == 0 or tick % 20 == 0):
                    print(f"[policy] run={run_id} tick={tick}/{ticks}", flush=True)
                try:
                    economy.step()
                except Exception as exc:  # pragma: no cover - reported to output
                    failed = True
                    error = f"{type(exc).__name__}: {exc}"
                    break
            elapsed = time.perf_counter() - started
            stats = compute_household_stats(economy.households)
            metrics = economy.get_economic_metrics()
            rows.append(
                {
                    "run_id": run_id,
                    "policy": spec["name"],
                    "policy_group": ",".join(policy_groups),
                    "levers_json": spec["levers"],
                    "seed": seed,
                    "households": households,
                    "ticks_requested": ticks,
                    "ticks_completed": int(economy.current_tick),
                    "elapsed_seconds": round(elapsed, 4),
                    "ticks_per_second": round(int(economy.current_tick) / elapsed, 4) if elapsed > 0 else 0.0,
                    "final_gdp": float(metrics.get("gdp_this_tick", 0.0)),
                    "final_unemployment_rate": float(stats.get("unemployment_rate", 0.0)),
                    "final_happiness": float(stats.get("mean_happiness", 0.0)),
                    "final_health": float(stats.get("mean_health", 0.0)),
                    "final_government_cash": float(economy.government.cash_balance),
                    "failed": failed,
                    "error": error,
                }
            )
            if verbose:
                print(
                    f"[policy] completed run={run_id} ticks_completed={int(economy.current_tick)} "
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
        "artifacts": {"rows_csv": rows_csv, "summary_md": summary_md, "raw_json": raw_json},
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
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
