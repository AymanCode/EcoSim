"""Before/after run for the infrastructure productivity fix.

Runs the same seeded economy three times and prints a markdown table:

- ``none``: ``infrastructure_spending`` lever at "none" (control; the
  multiplier stays 1.0, so the fix flag has no effect).
- ``high, before``: lever "high", ``infrastructure_raises_firm_capacity_enabled``
  off (the multiplier only scales realized goods output, then gets clamped).
- ``high, after``: lever "high", flag on (the default).

Usage (from backend/):
    python tools/benchmarks/run_infrastructure_compare.py --seed 42 --ticks 104

``--budget`` replaces the "high" lever's 2,000/tick infrastructure budget in
the two "high" scenarios (sensitivity runs: 1000 and 3000 are -/+50%).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import random
import statistics
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG, clone_config, use_config  # noqa: E402
from economy import Economy  # noqa: E402
from tools.runners.run_large_simulation import create_large_economy  # noqa: E402

SCENARIOS = {
    "none": ("none", True),
    "high, before": ("high", False),
    "high, after": ("high", True),
}

# Means are over ticks 13..end, after the warm-up transition at tick 11.
REPORT = (
    ("infra_mean", "infrastructure multiplier, mean t13+", "{:.3f}"),
    ("food_units", "Food produced, total t13+", "{:,.0f}"),
    ("services_units", "Services produced, total t13+", "{:,.0f}"),
    ("food_workers", "Food workers, mean t13+", "{:.1f}"),
    ("services_price", "Services mean price, final", "{:.2f}"),
    ("food_price", "Food mean price, final", "{:.2f}"),
    ("cpi", "CPI, final", "{:.1f}"),
    ("real_wage", "mean real wage, final", "{:.2f}"),
    ("u_mean", "unemployment, mean t13+", "{:.3f}"),
    ("u_end", "unemployment, final", "{:.3f}"),
    ("h_median", "median happiness, final", "{:.3f}"),
    ("h_mean", "mean happiness, final", "{:.3f}"),
    ("gdp_mean", "GDP / tick, mean t13+", "{:,.0f}"),
    ("gov_cash", "government cash, final", "{:,.0f}"),
)


def run(seed: int, ticks: int, households: int, firms: int, scenario: str, budget: float | None = None) -> dict:
    """Run one seeded economy and return the REPORT metrics."""
    lever, flag = SCENARIOS[scenario]
    produced = {"Food": 0.0, "Services": 0.0}
    original = Economy._calculate_experience_adjusted_production

    def counting(self, firm, planned):
        units = original(self, firm, planned)
        if self.current_tick >= 12 and firm.good_category in produced:
            produced[firm.good_category] += units
        return units

    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = int(seed)
        CONFIG.government.infrastructure_raises_firm_capacity_enabled = flag
        Economy._calculate_experience_adjusted_production = counting
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                economy = create_large_economy(households, firms)
            economy.government.set_lever("infrastructure_spending", lever)
            if budget is not None and lever == "high":
                economy.government.infrastructure_investment_budget = float(budget)
            rows, food_workers = [], []
            for tick in range(ticks):
                with contextlib.redirect_stdout(io.StringIO()):
                    economy.step()
                rows.append(economy.get_economic_metrics())
                if tick >= 12:
                    food_workers.append(sum(len(f.employees) for f in economy.firms if f.good_category == "Food"))
        finally:
            Economy._calculate_experience_adjusted_production = original
    post = rows[12:]

    def mean_price(category: str) -> float:
        prices = [f.price for f in economy.firms if f.good_category == category]
        return statistics.fmean(prices) if prices else 0.0

    happiness = [h.happiness for h in economy.households]
    return {
        "infra_mean": statistics.fmean(r["infrastructure_productivity"] for r in post),
        "food_units": produced["Food"],
        "services_units": produced["Services"],
        "food_workers": statistics.fmean(food_workers),
        "services_price": mean_price("Services"),
        "food_price": mean_price("Food"),
        "cpi": rows[-1]["consumer_price_index"],
        "real_wage": rows[-1]["mean_real_wage"],
        "u_mean": statistics.fmean(r["unemployment_rate"] for r in post),
        "u_end": rows[-1]["unemployment_rate"],
        "h_median": float(np.median(happiness)),
        "h_mean": float(np.mean(happiness)),
        "gdp_mean": statistics.fmean(r["gdp_this_tick"] for r in post),
        "gov_cash": float(economy.government.cash_balance),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=104)
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--firms-per-category", type=int, default=10)
    parser.add_argument("--budget", type=float, default=None, help="infrastructure budget per tick for the 'high' scenarios")
    args = parser.parse_args()

    results = {
        name: run(args.seed, args.ticks, args.households, args.firms_per_category, name, args.budget)
        for name in SCENARIOS
    }
    suffix = f", high budget {args.budget:,.0f}/tick" if args.budget is not None else ""
    print(f"\n### seed {args.seed}, {args.households} households, {args.ticks} ticks{suffix}\n")
    print("| metric | " + " | ".join(SCENARIOS) + " |")
    print("|---|" + "---:|" * len(SCENARIOS))
    for key, label, fmt in REPORT:
        print(f"| {label} | " + " | ".join(fmt.format(float(results[n][key])) for n in SCENARIOS) + " |")


if __name__ == "__main__":
    main()
