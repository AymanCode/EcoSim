"""Before/after run for round 1 PR5 (government G1/G2/G3 + price-cap hold).

Runs the same seeded economy twice, once with every PR5 flag off (pre-PR5
behavior) and once with the defaults, and prints a metrics table. A second
scenario forces deficits (crisis benefits, high infrastructure/technology
spending, then funding stops at tick 52) so the debt and decay paths run.

Usage (from backend/):
    python tools/benchmarks/run_pr5_government_compare.py \\
        --households 400 --firms-per-category 6 --seed 42 --ticks 104
"""

from __future__ import annotations

import argparse
import contextlib
import io
import random
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG, clone_config, use_config  # noqa: E402
from tools.runners.run_large_simulation import create_large_economy  # noqa: E402

PR5_FLAGS = (
    "public_debt_enabled",
    "flat_profit_tax_enabled",
    "public_capital_decay_enabled",
    "public_works_purchases_enabled",
    "price_cap_hold_enabled",
)

REPORT_KEYS = (
    ("unemployment_rate", "unemployment rate", "{:.3f}"),
    ("mean_happiness", "mean happiness", "{:.3f}"),
    ("gdp_this_tick", "GDP / tick", "{:,.0f}"),
    ("government_cash", "gov cash", "{:,.0f}"),
    ("public_debt", "public debt", "{:,.0f}"),
    ("annualized_debt_to_gdp", "debt / annual GDP", "{:.3f}"),
    ("gov_debt_interest_this_tick", "debt interest / tick", "{:,.1f}"),
    ("gov_profit_taxes_this_tick", "profit tax / tick", "{:,.0f}"),
    ("technology_quality", "tech multiplier", "{:.4f}"),
    ("infrastructure_productivity", "infra multiplier", "{:.4f}"),
    ("benefit_replacement_rate", "benefit replacement", "{:.3f}"),
    ("health_coverage", "health coverage", "{:.3f}"),
)


def _run(households: int, firms: int, seed: int, ticks: int, pr5_on: bool, stress: bool) -> dict:
    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = int(seed)
        for flag in PR5_FLAGS:
            setattr(CONFIG.government, flag, pr5_on)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms)
        gov = economy.government
        if stress:
            gov.set_lever("benefit_level", "crisis")
            gov.set_lever("infrastructure_spending", "high")
            gov.set_lever("technology_spending", "high")
        bank_reserves_min = float("inf")
        for tick in range(ticks):
            if stress and tick == ticks // 2:
                gov.set_lever("infrastructure_spending", "none")
                gov.set_lever("technology_spending", "none")
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            if economy.bank is not None:
                bank_reserves_min = min(bank_reserves_min, float(economy.bank.cash_reserves))
        metrics = economy.get_economic_metrics()
        metrics["government_cash"] = float(gov.cash_balance)
        metrics["gov_profit_taxes_this_tick"] = float(economy.last_tick_gov_profit_taxes)
        metrics["bank_reserves_min"] = bank_reserves_min
        return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--households", type=int, default=400)
    parser.add_argument("--firms-per-category", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=104)
    args = parser.parse_args()

    for stress in (False, True):
        before = _run(args.households, args.firms_per_category, args.seed, args.ticks, False, stress)
        after = _run(args.households, args.firms_per_category, args.seed, args.ticks, True, stress)
        title = "stress (crisis benefits, high infra+tech, funding stops at mid-run)" if stress else "default levers"
        print(f"\n### {title}: seed {args.seed}, {args.households} households, tick {args.ticks}\n")
        print("| metric | before (flags off) | after (PR5 defaults) |")
        print("|---|---:|---:|")
        for key, label, fmt in REPORT_KEYS + (("bank_reserves_min", "min bank reserves", "{:,.0f}"),):
            b, a = before.get(key, 0.0), after.get(key, 0.0)
            print(f"| {label} | {fmt.format(float(b or 0.0))} | {fmt.format(float(a or 0.0))} |")


if __name__ == "__main__":
    main()
