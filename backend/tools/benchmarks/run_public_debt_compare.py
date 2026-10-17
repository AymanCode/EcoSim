"""Before/after and sensitivity runs for public debt (round 1 G1).

Compare mode runs each scenario with ``public_debt_enabled`` off (main's
behavior: the treasury goes negative for free) and on, for each seed, and
prints run-level metrics plus the debt shares. Sensitivity mode re-runs the
debt-on case with one parameter at -50% and +50%.

Scenarios:
    default  levers as configured.
    stress   crisis benefits plus high infrastructure and technology spending
             until mid-run, so the treasury runs a deficit and then can repay.
    deep     the treasury starts with no cash and runs crisis benefits plus
             high infrastructure, technology and social spending all run, so
             debt builds up and the bank's lending limit can bind.

Usage (from backend/):
    python tools/benchmarks/run_public_debt_compare.py --seeds 42 1 2 3 4
    python tools/benchmarks/run_public_debt_compare.py --sensitivity --seeds 42 1 2
    python tools/benchmarks/run_public_debt_compare.py --sensitivity --sens-scenario stress --seeds 42 1 2
"""

from __future__ import annotations

import argparse
import contextlib
import io
import random
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG, clone_config, use_config  # noqa: E402
from tools.runners.run_large_simulation import create_large_economy  # noqa: E402

BURN_IN_TICKS = 13  # skip the first quarter when averaging over the run
SCENARIOS = ("default", "stress", "deep")


def run_once(households: int, firms: int, seed: int, ticks: int, debt_on: bool, scenario: str,
             override: Optional[Tuple[str, float]] = None) -> Dict[str, float]:
    """Run one seeded economy and return run-level metrics."""
    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = int(seed)
        CONFIG.government.public_debt_enabled = debt_on
        if override is not None and override[0] != "bank.base_interest_rate":
            setattr(CONFIG.government, override[0].split(".", 1)[1], override[1])
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms)
        gov, bank = economy.government, economy.bank
        if override is not None and override[0] == "bank.base_interest_rate":
            bank.base_interest_rate = override[1]
        if scenario in ("stress", "deep"):
            gov.set_lever("benefit_level", "crisis")
            gov.set_lever("infrastructure_spending", "high")
            gov.set_lever("technology_spending", "high")
        if scenario == "deep":
            gov.set_lever("social_spending", "high")
            gov.cash_balance = 0.0

        unemp: List[float] = []
        happy: List[float] = []
        gdp: List[float] = []
        debt_ticks = 0
        shortfall_ticks = 0
        bank_bound_ticks = 0
        negative_cash_ticks = 0
        peak_debt_to_gdp = 0.0
        interest_total = 0.0
        spending_total = 0.0
        bond_total = 0.0
        bank_min = float("inf")
        for tick in range(ticks):
            if scenario == "stress" and tick == ticks // 2:
                gov.set_lever("infrastructure_spending", "none")
                gov.set_lever("technology_spending", "none")
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            m = economy.get_economic_metrics()
            if tick >= BURN_IN_TICKS:
                unemp.append(float(m["unemployment_rate"]))
                happy.append(float(m["mean_happiness"]))
                gdp.append(float(m["gdp_this_tick"]))
            debt_ticks += gov.public_debt > 0.0
            borrowed, unfunded = gov.last_tick_debt_borrowed, gov.last_tick_debt_unfunded
            shortfall_ticks += (borrowed + unfunded) > 0.0
            bank_bound_ticks += unfunded > 0.0
            negative_cash_ticks += gov.cash_balance < 0.0
            peak_debt_to_gdp = max(peak_debt_to_gdp, float(m["annualized_debt_to_gdp"]))
            interest_total += gov.last_tick_debt_interest
            spending_total += gov.last_tick_spending
            bond_total += economy.last_tick_gov_bond_purchases
            if bank is not None:
                bank_min = min(bank_min, float(bank.cash_reserves))
        households_money = sum(h.cash_balance + max(0.0, h.bank_deposit) for h in economy.households)
        return {
            "unemployment_mean": statistics.fmean(unemp),
            "happiness_mean": statistics.fmean(happy),
            "gdp_mean": statistics.fmean(gdp),
            "gov_cash_end": float(gov.cash_balance),
            "public_debt_end": float(gov.public_debt),
            "unfunded_end": max(0.0, -float(gov.cash_balance)),
            "bond_buys_total": bond_total,
            "households_money_end": households_money,
            "bank_reserves_min": bank_min,
            "debt_rate_end": float(gov.last_tick_debt_rate),
            "share_ticks_in_debt": debt_ticks / ticks,
            "peak_debt_to_gdp": peak_debt_to_gdp,
            "interest_share_of_spending": interest_total / spending_total if spending_total else 0.0,
            "share_shortfall_ticks_bank_bound": bank_bound_ticks / shortfall_ticks if shortfall_ticks else 0.0,
            "shortfall_ticks": float(shortfall_ticks),
            "share_ticks_negative_cash": negative_cash_ticks / ticks,
        }


ROWS = (
    ("unemployment_mean", "unemployment, mean wk 13-end", "{:.3f}"),
    ("happiness_mean", "happiness, mean wk 13-end", "{:.3f}"),
    ("gdp_mean", "GDP / tick, mean wk 13-end", "{:,.0f}"),
    ("gov_cash_end", "gov cash at end", "{:,.0f}"),
    ("public_debt_end", "public debt at end", "{:,.0f}"),
    ("bond_buys_total", "Misc bond buys, run total", "{:,.0f}"),
    ("households_money_end", "household cash + deposits at end", "{:,.0f}"),
    ("bank_reserves_min", "min bank reserves", "{:,.0f}"),
    ("debt_rate_end", "debt rate at end (annual)", "{:.4f}"),
    ("share_ticks_in_debt", "share of ticks in debt", "{:.1%}"),
    ("peak_debt_to_gdp", "peak debt / annual GDP", "{:.3f}"),
    ("interest_share_of_spending", "interest / government spending", "{:.2%}"),
    ("shortfall_ticks", "ticks with a shortfall", "{:.0f}"),
    ("share_shortfall_ticks_bank_bound", "shortfall ticks where the bank could not lend it all", "{:.1%}"),
    ("share_ticks_negative_cash", "share of ticks ending with negative cash", "{:.1%}"),
)

SENSITIVITY = (
    ("government.public_debt_risk_premium", 0.035, 0.0175, 0.0525),
    ("government.public_debt_cash_buffer_weeks", 1.0, 0.5, 1.5),
    ("bank.base_interest_rate", 0.03, 0.015, 0.045),
)
SENS_KEYS = ("unemployment_mean", "happiness_mean", "gdp_mean", "public_debt_end", "share_ticks_in_debt",
             "peak_debt_to_gdp", "interest_share_of_spending", "share_shortfall_ticks_bank_bound")


def compare(args) -> None:
    for scenario in args.scenarios:
        per_seed = []
        for seed in args.seeds:
            before = run_once(args.households, args.firms_per_category, seed, args.ticks, False, scenario)
            after = run_once(args.households, args.firms_per_category, seed, args.ticks, True, scenario)
            per_seed.append((seed, before, after))
            print(f"\n### {scenario}, seed {seed}: {args.households} households, {args.ticks} ticks\n")
            print("| metric | debt off (main) | debt on |\n|---|---:|---:|")
            for key, label, fmt in ROWS:
                print(f"| {label} | {fmt.format(before[key])} | {fmt.format(after[key])} |", flush=True)
        if len(per_seed) > 1:
            print(f"\n### {scenario}: debt on minus debt off over seeds {args.seeds} (mean, sd)\n")
            print("| metric | mean | sd |\n|---|---:|---:|")
            for key, label, fmt in ROWS:
                deltas = [a[key] - b[key] for _, b, a in per_seed]
                print(f"| {label} | {fmt.format(statistics.fmean(deltas))} | "
                      f"{fmt.format(statistics.stdev(deltas))} |", flush=True)


def sensitivity(args) -> None:
    scenario = args.sens_scenario
    print(f"\n### sensitivity, {scenario} scenario, seeds {args.seeds}: (value) minus (default), mean over seeds\n")
    print("| parameter | value | " + " | ".join(SENS_KEYS) + " |")
    print("|---|---:|" + "---:|" * len(SENS_KEYS))
    base = {seed: run_once(args.households, args.firms_per_category, seed, args.ticks, True, scenario)
            for seed in args.seeds}
    for key, default, low, high in SENSITIVITY:
        for value in (low, high):
            runs = {seed: run_once(args.households, args.firms_per_category, seed, args.ticks, True, scenario,
                                   override=(key, value)) for seed in args.seeds}
            cells = [f"{statistics.fmean(runs[s][k] - base[s][k] for s in args.seeds):+.4g}" for k in SENS_KEYS]
            print(f"| {key} (default {default}) | {value} | " + " | ".join(cells) + " |", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--households", type=int, default=400)
    parser.add_argument("--firms-per-category", type=int, default=6)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42])
    parser.add_argument("--ticks", type=int, default=104)
    parser.add_argument("--scenarios", nargs="+", default=list(SCENARIOS), choices=SCENARIOS)
    parser.add_argument("--sensitivity", action="store_true")
    parser.add_argument("--sens-scenario", default="deep", choices=SCENARIOS)
    args = parser.parse_args()
    if args.sensitivity:
        sensitivity(args)
    else:
        compare(args)


if __name__ == "__main__":
    main()
