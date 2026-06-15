"""Deterministic economy snapshot harness for behavior-preserving refactors.

Runs a fixed-seed economy, snapshots aggregate + per-entity state at chosen
ticks, and either saves a golden file or compares against one.

Use it to guard internal optimizations (e.g. _clear_goods_market rewrite,
_batch_apply_household_updates refactor) that must preserve semantics.

Save golden BEFORE a refactor, compare AFTER:

    python -m backend.tools.benchmarks.regression_snapshot \
        --households 1500 --seed 42 --ticks 80 --snap-ticks 1,10,80 \
        --save benchmarks/results/golden_market.json

    python -m backend.tools.benchmarks.regression_snapshot \
        --households 1500 --seed 42 --ticks 80 --snap-ticks 1,10,80 \
        --compare benchmarks/results/golden_market.json

Exit code is non-zero on any divergence beyond --tol, with the first
mismatches printed. Wall-clock per-tick is also reported so the same run
doubles as a clean (no-cProfile) speed baseline.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
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
from tools.runners.run_large_simulation import create_large_economy

# Floats are rounded to this many decimals before hashing/compare so that
# benign last-bit noise from reordered float adds is not flagged. Set via
# --tol-decimals if a refactor legitimately changes summation order.
ROUND_DECIMALS = 6
HOUSEHOLD_SAMPLE = 120  # first N households by id


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    CONFIG.random_seed = int(seed)


def _r(x: Any, decimals: int) -> Any:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return x
    if math.isnan(v) or math.isinf(v):
        return str(v)
    return round(v, decimals)


def _ledger_snapshot(ledger: Any, decimals: int) -> dict:
    if not isinstance(ledger, dict):
        return {}
    return {str(k): _r(v, decimals) for k, v in sorted(ledger.items())}


def snapshot_economy(economy, decimals: int) -> dict:
    """Capture a deterministic, order-stable snapshot of economy state."""
    households = sorted(economy.households, key=lambda h: h.household_id)
    firms = sorted(economy.firms, key=lambda f: f.firm_id)

    total_hh_cash = sum(float(h.cash_balance) for h in households)
    total_firm_cash = sum(float(f.cash_balance) for f in firms)
    total_firm_inv = sum(float(getattr(f, "inventory_units", 0.0)) for f in firms)
    services_unmet_by_firm = getattr(economy, "services_unmet_demand_by_firm", {}) or {}
    unmet_by_firm = getattr(economy, "current_tick_unmet_demand_by_firm", {}) or {}

    agg = {
        "current_tick": int(economy.current_tick),
        "num_households": len(households),
        "num_firms": len(firms),
        "food_unmet_demand": _r(getattr(economy, "food_unmet_demand", 0.0), decimals),
        "services_unmet_demand": _r(getattr(economy, "services_unmet_demand", 0.0), decimals),
        "services_unmet_by_firm_total": _r(sum(float(v) for v in services_unmet_by_firm.values()), decimals),
        "government_cash": _r(economy.government.cash_balance, decimals),
        "total_household_cash": _r(total_hh_cash, decimals),
        "total_firm_cash": _r(total_firm_cash, decimals),
        "total_firm_inventory": _r(total_firm_inv, decimals),
    }

    firm_rows = []
    for f in firms:
        firm_rows.append({
            "firm_id": int(f.firm_id),
            "good_category": str(getattr(f, "good_category", "")),
            "cash": _r(f.cash_balance, decimals),
            "inventory_units": _r(getattr(f, "inventory_units", 0.0), decimals),
            "price": _r(getattr(f, "price", 0.0), decimals),
            "total_units_sold": _r(getattr(f, "total_units_sold", 0.0), decimals),
            "total_revenue": _r(getattr(f, "total_revenue", 0.0), decimals),
            "unmet_demand": _r(unmet_by_firm.get(int(f.firm_id), 0.0), decimals),
            "services_unmet": _r(services_unmet_by_firm.get(int(f.firm_id), 0.0), decimals),
        })

    hh_rows = []
    for h in households[:HOUSEHOLD_SAMPLE]:
        hh_rows.append({
            "household_id": int(h.household_id),
            "cash": _r(h.cash_balance, decimals),
            "ledger": _ledger_snapshot(getattr(h, "last_tick_ledger", {}), decimals),
            "goods_inventory_total": _r(
                sum(float(v) for v in (getattr(h, "goods_inventory", {}) or {}).values()),
                decimals,
            ),
            "goods_inventory_keys": sorted(str(k) for k in (getattr(h, "goods_inventory", {}) or {})),
            "price_beliefs_count": len(getattr(h, "price_beliefs", {}) or {}),
            "last_food_units": _r(getattr(h, "last_food_units", 0.0), decimals),
            "last_food_spend": _r(getattr(h, "last_food_spend", 0.0), decimals),
            "last_services_units": _r(getattr(h, "last_services_units", 0.0), decimals),
            "last_services_spend": _r(getattr(h, "last_services_spend", 0.0), decimals),
            "last_housing_units": _r(getattr(h, "last_housing_units", 0.0), decimals),
            "last_housing_spend": _r(getattr(h, "last_housing_spend", 0.0), decimals),
            "owns_housing": bool(getattr(h, "owns_housing", False)),
            "met_housing_need": bool(getattr(h, "met_housing_need", False)),
        })

    return {"aggregate": agg, "firms": firm_rows, "households_sample": hh_rows}


def run(households: int, firms_per_category: int, seed: int, ticks: int,
        snap_ticks: set[int], decimals: int) -> dict:
    _set_seed(seed)
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(households, firms_per_category)

    snapshots: dict[str, Any] = {}
    durations_ms: list[float] = []
    for _ in range(ticks):
        t0 = time.perf_counter()
        economy.step()
        durations_ms.append((time.perf_counter() - t0) * 1000.0)
        tick_now = int(economy.current_tick)
        if tick_now in snap_ticks:
            snapshots[str(tick_now)] = snapshot_economy(economy, decimals)

    durations_ms.sort()
    n = len(durations_ms)
    p50 = durations_ms[n // 2] if n else 0.0
    p95 = durations_ms[min(n - 1, int(n * 0.95))] if n else 0.0
    return {
        "meta": {
            "households": households,
            "firms_per_category": firms_per_category,
            "seed": seed,
            "ticks": ticks,
            "snap_ticks": sorted(snap_ticks),
            "round_decimals": decimals,
        },
        "wall_clock_ms": {
            "p50": round(p50, 3),
            "p95": round(p95, 3),
            "mean": round(sum(durations_ms) / n, 3) if n else 0.0,
        },
        "snapshots": snapshots,
    }


def _diff(golden: Any, current: Any, path: str, out: list[str], tol: float) -> None:
    if len(out) >= 40:
        return
    if isinstance(golden, dict) and isinstance(current, dict):
        for k in sorted(set(golden) | set(current)):
            if k not in golden:
                out.append(f"{path}/{k}: added (={current[k]!r})")
            elif k not in current:
                out.append(f"{path}/{k}: removed (was {golden[k]!r})")
            else:
                _diff(golden[k], current[k], f"{path}/{k}", out, tol)
    elif isinstance(golden, list) and isinstance(current, list):
        if len(golden) != len(current):
            out.append(f"{path}: list len {len(golden)} -> {len(current)}")
        for i, (g, c) in enumerate(zip(golden, current)):
            _diff(g, c, f"{path}[{i}]", out, tol)
    else:
        if isinstance(golden, (int, float)) and isinstance(current, (int, float)):
            if abs(float(golden) - float(current)) > tol:
                out.append(f"{path}: {golden!r} -> {current!r} (Δ={float(current) - float(golden):+.6g})")
        elif golden != current:
            out.append(f"{path}: {golden!r} -> {current!r}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deterministic economy regression snapshot.")
    p.add_argument("--households", type=int, default=1500)
    p.add_argument("--firms-per-category", type=int, default=10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--ticks", type=int, default=80)
    p.add_argument("--snap-ticks", default="1,10,80", help="Comma-separated ticks to snapshot.")
    p.add_argument("--tol-decimals", type=int, default=ROUND_DECIMALS,
                   help="Decimals to round floats before compare/save.")
    p.add_argument("--tol", type=float, default=1e-6,
                   help="Absolute numeric tolerance in compare mode.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--save", type=Path, help="Write golden snapshot JSON to this path.")
    g.add_argument("--compare", type=Path, help="Compare against this golden snapshot JSON.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snap_ticks = {int(x) for x in str(args.snap_ticks).split(",") if x.strip()}

    result = run(
        households=args.households,
        firms_per_category=args.firms_per_category,
        seed=args.seed,
        ticks=args.ticks,
        snap_ticks=snap_ticks,
        decimals=args.tol_decimals,
    )
    wc = result["wall_clock_ms"]
    print(f"wall-clock/tick ms: p50={wc['p50']} p95={wc['p95']} mean={wc['mean']} "
          f"({args.households} hh, seed {args.seed}, {args.ticks} ticks)")

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(result["snapshots"], indent=2, sort_keys=True), encoding="utf-8")
        print(f"golden saved -> {args.save}")
        return 0

    golden = json.loads(Path(args.compare).read_text(encoding="utf-8"))
    out: list[str] = []
    _diff(golden, result["snapshots"], "", out, args.tol)
    if not out:
        print(f"MATCH: snapshots identical within tol={args.tol} vs {args.compare}")
        return 0
    print(f"MISMATCH vs {args.compare} ({len(out)}+ diffs, first shown):")
    for line in out:
        print(f"  {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
