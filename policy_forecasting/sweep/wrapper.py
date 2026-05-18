"""External policy-sweep driver for the frozen EcoSim base."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import multiprocessing as mp
import random
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from policy_forecasting.config import (
    CONFIRM_SEEDS,
    DROPPED_MANIFEST_COLUMNS,
    FEATURE_MANIFEST,
    FROZEN_ARMS,
    FROZEN_SECTORS,
    HORIZON_TICKS,
    POLICY_STATE_COLUMNS,
    SMOKE_SEEDS_2K,
    PolicyArm,
    arm_by_id,
    canonical_lever_json,
)
from policy_forecasting.distress import DistressHistory, compute_household_welfare


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (REPO_ROOT, BACKEND_ROOT, BACKEND_ROOT / "tools", BACKEND_ROOT / "tools" / "runners"):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)


def _backend_imports() -> tuple[Any, Any]:
    from backend.tools.runners.run_large_simulation import create_large_economy
    from config import CONFIG

    return create_large_economy, CONFIG


def set_run_seed(seed: int) -> None:
    """Seed wrapper-controlled RNG surfaces used by the simulator factory."""
    _, config = _backend_imports()
    random.seed(seed)
    np.random.seed(seed)
    config.random_seed = int(seed)


def create_economy_quietly(num_households: int, firms_per_category: int, *, verbose: bool = False) -> Any:
    """Create an Economy via the existing public factory."""
    create_large_economy, _ = _backend_imports()
    if verbose:
        return create_large_economy(num_households, firms_per_category)
    with contextlib.redirect_stdout(io.StringIO()):
        return create_large_economy(num_households, firms_per_category)


def apply_policy(economy: Any, arm: PolicyArm) -> None:
    """Apply an arm's lever deltas through GovernmentAgent.set_lever."""
    for lever, value in arm.levers.items():
        economy.government.set_lever(lever, value)


def _normalise_sector(name: Any) -> str:
    value = str(name or "").strip().lower()
    return value if value else "unknown"


def sector_rollups(firms: list[Any]) -> dict[str, dict[str, float]]:
    """Aggregate firm revenue and price by frozen sector."""
    rollups: dict[str, dict[str, float]] = {
        sector: {"revenue": 0.0, "price_sum": 0.0, "count": 0.0} for sector in FROZEN_SECTORS
    }
    for firm in firms:
        data = firm.to_dict() if hasattr(firm, "to_dict") else {}
        sector = _normalise_sector(data.get("good_category", getattr(firm, "good_category", "")))
        if sector not in rollups:
            continue
        rollups[sector]["revenue"] += float(data.get("last_revenue", getattr(firm, "last_revenue", 0.0)) or 0.0)
        rollups[sector]["price_sum"] += float(data.get("price", getattr(firm, "price", 0.0)) or 0.0)
        rollups[sector]["count"] += 1.0
    return rollups


def _policy_state(government: Any) -> dict[str, Any]:
    gov = government.to_dict() if hasattr(government, "to_dict") else {}
    return {column: gov.get(column, None) for column in POLICY_STATE_COLUMNS}


def snapshot_manifest(
    economy: Any,
    *,
    run_id: str,
    policy_canonical: str,
    levers_json: str,
    seed: int,
    tick: int,
    distress_history: DistressHistory,
    unemployment_history: deque[float],
    gdp_history: deque[float],
    essential_spend: float,
) -> dict[str, Any]:
    """Snapshot one frozen per-tick manifest row from public simulator surfaces."""
    metrics = economy.get_economic_metrics()
    welfare = compute_household_welfare(
        economy.households,
        distress_history,
        update_history=True,
        essential_spend=essential_spend,
    )
    unemployment = float(metrics.get("unemployment_rate", 0.0) or 0.0)
    gdp = float(metrics.get("gdp_this_tick", metrics.get("gdp", 0.0)) or 0.0)
    unemployment_history.append(unemployment)
    gdp_history.append(gdp)

    firms = list(economy.firms)
    hires = float(sum(max(0, int(getattr(firm, "last_tick_actual_hires", 0) or 0)) for firm in firms))
    layoffs = float(sum(len(getattr(firm, "planned_layoffs_ids", []) or []) for firm in firms))
    vacancies = float(sum(max(0, int(getattr(firm, "planned_hires_count", 0) or 0)) for firm in firms))
    wage_offers = [float(getattr(firm, "wage_offer", 0.0) or 0.0) for firm in firms]
    median_wage = float(metrics.get("median_wage", 0.0) or 0.0)
    wage_pressure = (float(np.mean(wage_offers)) / median_wage - 1.0) if median_wage > 0.0 and wage_offers else 0.0

    row: dict[str, Any] = {
        "run_id": run_id,
        "policy_canonical": policy_canonical,
        "levers_json": levers_json,
        "seed": int(seed),
        "tick": int(tick),
        "unemployment_rate": unemployment,
        "unemployment_ma4": float(np.mean(list(unemployment_history)[-4:])),
        "unemployment_ma8": float(np.mean(list(unemployment_history)[-8:])),
        "hires": hires,
        "layoffs": layoffs,
        "vacancies": vacancies,
        "vacancy_fill_ratio": float(hires / vacancies) if vacancies > 0.0 else 1.0,
        "wage_pressure_idx": float(wage_pressure),
        "gdp": gdp,
        "agg_inventory": float(metrics.get("total_firm_inventory", 0.0) or 0.0),
        "price_index": float(metrics.get("mean_price", 0.0) or 0.0),
        "gdp_ma4": float(np.mean(list(gdp_history)[-4:])),
        **welfare,
        "n_burn_mode": float(metrics.get("burn_mode_firm_count", 0.0) or 0.0),
        "n_survival_mode": float(metrics.get("survival_mode_firm_count", 0.0) or 0.0),
        "bankruptcies_tick": float(metrics.get("bankruptcy_count", 0.0) or 0.0),
        "n_weak_demand": float(metrics.get("weak_demand_firm_count", 0.0) or 0.0),
        "gov_cash": float(getattr(economy.government, "cash_balance", 0.0) or 0.0),
        "gov_profit": float(
            getattr(economy.government, "last_tick_revenue", 0.0)
            - getattr(economy.government, "last_tick_spending", 0.0)
        ),
        "fiscal_stress": float(metrics.get("fiscal_pressure", 0.0) or 0.0),
    }

    for sector, data in sector_rollups(firms).items():
        count = max(1.0, data["count"])
        row[f"sector_revenue_{sector}"] = float(data["revenue"])
        row[f"sector_price_{sector}"] = float(data["price_sum"] / count)

    row.update(_policy_state(economy.government))
    for column in FEATURE_MANIFEST:
        row.setdefault(column, 0.0)
    row["consumer_distress"] = row["mean_distress"]
    return row


def build_run_id(arm_id: str, seed: int, households: int) -> str:
    """Stable run ID for a policy-seed-household combination."""
    return f"policy-{arm_id}-seed{int(seed)}-hh{int(households)}"


def run_single_policy(
    arm: PolicyArm,
    *,
    seed: int,
    households: int,
    ticks: int,
    firms_per_category: int,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """Run one policy/seed pair and return per-tick manifest rows."""
    set_run_seed(seed)
    _, config = _backend_imports()
    households_cfg = getattr(config, "households", config)
    essential_spend = float(getattr(households_cfg, "subsistence_min_cash", 50.0))
    economy = create_economy_quietly(households, firms_per_category, verbose=verbose)
    apply_policy(economy, arm)
    run_id = build_run_id(arm.arm_id, seed, households)
    canonical = arm.policy_canonical
    levers_json = canonical_lever_json(arm.levers)
    distress_history = DistressHistory()
    unemployment_history: deque[float] = deque(maxlen=8)
    gdp_history: deque[float] = deque(maxlen=4)
    rows: list[dict[str, Any]] = []
    for _ in range(ticks):
        economy.step()
        tick = int(economy.current_tick) - 1
        rows.append(
            snapshot_manifest(
                economy,
                run_id=run_id,
                policy_canonical=canonical,
                levers_json=levers_json,
                seed=seed,
                tick=tick,
                distress_history=distress_history,
                unemployment_history=unemployment_history,
                gdp_history=gdp_history,
                essential_spend=essential_spend,
            )
        )
    return rows


def _worker(task: tuple[str, int, int, int, int, bool]) -> list[dict[str, Any]]:
    arm_id, seed, households, ticks, firms_per_category, verbose = task
    return run_single_policy(
        arm_by_id(arm_id),
        seed=seed,
        households=households,
        ticks=ticks,
        firms_per_category=firms_per_category,
        verbose=verbose,
    )


def run_policy_sweep(
    *,
    arms: list[str],
    seeds: list[int],
    households: int,
    ticks: int,
    firms_per_category: int,
    output_path: Path,
    processes: int = 1,
    verbose: bool = False,
) -> pd.DataFrame:
    """Run policy/seed tasks in parallel and persist rows to parquet."""
    tasks = [(arm_id, seed, households, ticks, firms_per_category, verbose) for arm_id in arms for seed in seeds]
    started = time.perf_counter()
    if processes > 1 and len(tasks) > 1:
        with mp.get_context("spawn").Pool(processes=processes) as pool:
            chunks = pool.map(_worker, tasks)
    else:
        chunks = [_worker(task) for task in tasks]
    rows = [row for chunk in chunks for row in chunk]
    frame = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False)
    metadata_path = output_path.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "arms": arms,
                "seeds": seeds,
                "households": households,
                "ticks": ticks,
                "firms_per_category": firms_per_category,
                "rows": len(frame),
                "elapsed_seconds": round(time.perf_counter() - started, 4),
                "horizon": HORIZON_TICKS,
                "dropped_manifest_columns": list(DROPPED_MANIFEST_COLUMNS),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return frame


def parse_csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run V1 policy forecasting sweep.")
    parser.add_argument("--arms", default=",".join(arm.arm_id for arm in FROZEN_ARMS))
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in SMOKE_SEEDS_2K))
    parser.add_argument("--confirm-seeds", action="store_true", help="Use the 24 confirm seeds.")
    parser.add_argument("--households", type=int, default=2000)
    parser.add_argument("--ticks", type=int, default=80)
    parser.add_argument("--firms-per-category", type=int, default=10)
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("policy_forecasting") / "artifacts" / "ticks.parquet")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    seeds = list(CONFIRM_SEEDS) if args.confirm_seeds else parse_csv_ints(args.seeds)
    frame = run_policy_sweep(
        arms=parse_csv_strings(args.arms),
        seeds=seeds,
        households=args.households,
        ticks=args.ticks,
        firms_per_category=args.firms_per_category,
        output_path=args.output,
        processes=max(1, int(args.processes)),
        verbose=args.verbose,
    )
    print(f"Wrote {len(frame)} rows to {args.output}")
    if DROPPED_MANIFEST_COLUMNS:
        print("Dropped manifest columns: " + ", ".join(DROPPED_MANIFEST_COLUMNS))
    else:
        print("Dropped manifest columns: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
