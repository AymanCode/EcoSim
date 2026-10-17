"""Before/after run for the public works headcount fix (bug 8).

Runs the same seeded economy with the ``public_works`` lever on under three
settings and once with the lever off, then prints a markdown table:

- ``before``: both fix flags off (pre-fix behavior).
- ``headcount only``: ``public_works_headcount_planning_enabled`` on,
  ``public_works_payroll_funding_enabled`` off.
- ``after``: both flags on (the defaults).
- ``lever off``: control; the fix flags have no effect when the lever is off.

Usage (from backend/):
    python tools/benchmarks/run_public_works_compare.py --seed 42 --ticks 104

Sensitivity runs override a government config key, e.g.
    python tools/benchmarks/run_public_works_compare.py --seed 42 \\
        --scenarios after --set public_works_jobless_share=0.5
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
from tools.runners.run_large_simulation import create_large_economy  # noqa: E402

SCENARIOS = {
    "before": {"lever": "on", "headcount": False, "funding": False},
    "headcount only": {"lever": "on", "headcount": True, "funding": False},
    "after": {"lever": "on", "headcount": True, "funding": True},
    "lever off": {"lever": "off", "headcount": True, "funding": True},
}

# (key, label, format). Means are over ticks 13..end, after the warm-up
# transition at tick 11, matching the PR7 investigation's u_post column.
REPORT = (
    ("pw_jobs_end", "public works jobs, final tick", "{:.0f}"),
    ("pw_jobs_mean", "public works jobs, mean t13+", "{:.1f}"),
    ("pw_authorized_mean", "jobs authorized, mean t13+", "{:.1f}"),
    ("pw_exits", "public works firm bankruptcies", "{:.0f}"),
    ("u_mean", "unemployment, mean t13+", "{:.3f}"),
    ("u_end", "unemployment, final tick", "{:.3f}"),
    ("h_median", "median happiness, final", "{:.3f}"),
    ("h_mean", "mean happiness, final", "{:.3f}"),
    ("cpi", "CPI, final", "{:.1f}"),
    ("mean_wage", "mean wage, final", "{:.1f}"),
    ("gdp_mean", "GDP / tick, mean t13+", "{:,.0f}"),
    ("pw_spend", "public works spending, cumulative", "{:,.0f}"),
    ("gov_cash", "government cash, final", "{:,.0f}"),
    ("gov_cash_min", "government cash, min", "{:,.0f}"),
)


def run(seed: int, ticks: int, households: int, firms: int, scenario: str, overrides: dict) -> dict:
    """Run one seeded economy and return the REPORT metrics."""
    spec = SCENARIOS[scenario]
    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = int(seed)
        CONFIG.government.public_works_headcount_planning_enabled = spec["headcount"]
        CONFIG.government.public_works_payroll_funding_enabled = spec["funding"]
        for key, value in overrides.items():
            current = getattr(CONFIG.government, key)
            setattr(CONFIG.government, key, type(current)(value))
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms)
        economy.government.set_lever("public_works", spec["lever"])
        rows = []
        pw_spend = 0.0
        gov_cash_min = float("inf")
        pw_ids_seen: set[int] = set()
        for _ in range(ticks):
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            m = economy.get_economic_metrics()
            pw_ids_seen.update(f.firm_id for f in economy.firms if f.good_category == "PublicWorks")
            pw_spend += economy.last_tick_gov_public_works_capitalization
            pw_spend += getattr(economy, "last_tick_gov_public_works_payroll_funding", 0.0)
            gov_cash_min = min(gov_cash_min, float(economy.government.cash_balance))
            rows.append(m)
        post = rows[12:]
        live_pw = {f.firm_id for f in economy.firms if f.good_category == "PublicWorks"}
        happiness = [h.happiness for h in economy.households]
        return {
            "pw_jobs_end": rows[-1]["public_works_jobs"],
            "pw_jobs_mean": statistics.fmean(r["public_works_jobs"] for r in post),
            "pw_authorized_mean": statistics.fmean(r["gov_public_works_jobs_authorized"] for r in post),
            "pw_exits": len(pw_ids_seen - live_pw),
            "u_mean": statistics.fmean(r["unemployment_rate"] for r in post),
            "u_end": rows[-1]["unemployment_rate"],
            "h_median": float(np.median(happiness)),
            "h_mean": float(np.mean(happiness)),
            "cpi": rows[-1]["consumer_price_index"],
            "mean_wage": rows[-1]["mean_wage"],
            "gdp_mean": statistics.fmean(r["gdp_this_tick"] for r in post),
            "pw_spend": pw_spend,
            "gov_cash": float(economy.government.cash_balance),
            "gov_cash_min": gov_cash_min,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=104)
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--firms-per-category", type=int, default=10)
    parser.add_argument("--scenarios", default=",".join(SCENARIOS), help="comma-separated subset of: " + ", ".join(SCENARIOS))
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override a CONFIG.government key")
    args = parser.parse_args()
    overrides = dict(item.split("=", 1) for item in args.set)
    names = [s.strip() for s in args.scenarios.split(",") if s.strip()]

    results = {name: run(args.seed, args.ticks, args.households, args.firms_per_category, name, overrides) for name in names}
    suffix = f", overrides {overrides}" if overrides else ""
    print(f"\n### seed {args.seed}, {args.households} households, {args.ticks} ticks{suffix}\n")
    print("| metric | " + " | ".join(names) + " |")
    print("|---|" + "---:|" * len(names))
    for key, label, fmt in REPORT:
        print(f"| {label} | " + " | ".join(fmt.format(float(results[n][key])) for n in names) + " |")


if __name__ == "__main__":
    main()
