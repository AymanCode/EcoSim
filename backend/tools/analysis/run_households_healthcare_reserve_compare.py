"""Seeded before/after run for the healthcare cash reservation (households).

Arms: ``before`` (``healthcare_cash_reservation`` off, as on main) and ``R``
(on). Scenarios (levers set once at tick 0, as in
``tools/benchmarks/run_healthcare_share_snapshot.py``):
  default     no levers touched; the healthcare subsidy share is 0, so the
              reserve is the full visit price.
  hc_subsidy  healthcare sector subsidy at 50%; the cap rarely binds.
  hc_cap      healthcare sector subsidy at 50% with the treasury cut to
              $100k, so the per-tick subsidy cap binds.

Prints post-warmup metrics: mean weekly consumption per household, median
liquid wealth (cash + deposits), share of visit attempts dropped from the
queue for lack of funds (rejects / (rejects + completed)), medical loans
issued, median happiness and mean health. ``queued_share`` and
``reserve_mean`` are read at budget time (after the week's enqueue): the
share of households holding a reserve and its mean size, which the before
arm reports as the reserve it would have held.

Usage (from backend/):
    PYTHONHASHSEED=0 python tools/analysis/run_households_healthcare_reserve_compare.py
    PYTHONHASHSEED=0 python tools/analysis/run_households_healthcare_reserve_compare.py \
        --payment-sequence income_first --scenarios hc_subsidy
"""

import argparse
import contextlib
import io
import random
import statistics
import sys
import time
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
for _path in (BACKEND_ROOT, BACKEND_ROOT / "tools" / "runners"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from config import CONFIG, clone_config, use_config  # noqa: E402
from run_large_simulation import create_large_economy  # noqa: E402

KEYS = ["scenario", "arm", "consumption_mean", "liquid_median", "drop_share", "visits_completed",
        "medical_loans", "happiness_median", "health_mean", "queued_share", "reserve_mean", "runtime_s"]


def run_arm(scenario, arm, households, ticks, seed, payment_sequence):
    """Run one scenario and arm; return the post-warmup metrics row."""
    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = seed
        CONFIG.payment_sequence = payment_sequence
        CONFIG.households.healthcare_cash_reservation = arm == "R"
        started = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(num_households=households, num_firms_per_category=5)
        gov = economy.government
        if scenario != "default":
            gov.set_lever("sector_subsidy_target", "healthcare")
            gov.set_lever("sector_subsidy_level", 50)
        if scenario == "hc_cap":
            gov.cash_balance = 100_000.0
        loans = {"count": 0}
        issue = economy._issue_medical_loan

        def counting_issue(household, amount):
            issued = issue(household, amount)
            if issued and economy.current_tick > economy.warmup_ticks:
                loans["count"] += 1
            return issued

        economy._issue_medical_loan = counting_issue
        consumption, liquid, happiness, health, queued, reserves = [], [], [], [], [], []
        budgets_fn = economy._household_consumption_budgets

        def observed_budgets(*a, **kw):
            # At budget time (after this week's enqueue): who is queued and the
            # reserve they hold (or would hold, in the before arm). Read-only.
            if economy.current_tick > economy.warmup_ticks:
                values = economy._healthcare_reservations()
                queued.append(float((values > 0).mean()))
                if (values > 0).any():
                    reserves.append(float(values[values > 0].mean()))
            return budgets_fn(*a, **kw)

        economy._household_consumption_budgets = observed_budgets
        rejects = completed = 0.0
        for _ in range(ticks):
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            if economy.current_tick <= economy.warmup_ticks:
                continue
            hhs = economy.households
            consumption.append(statistics.mean(h.last_consumption_spending for h in hhs))
            liquid.append(statistics.median(h.cash_balance + max(0.0, h.bank_deposit) for h in hhs))
            happiness.append(statistics.median(h.happiness for h in hhs))
            health.append(statistics.mean(h.health for h in hhs))
            rejects += economy.healthcare_affordability_rejects_this_tick
            completed += economy.healthcare_completed_visits_this_tick
        return {
            "scenario": scenario,
            "arm": arm,
            "consumption_mean": statistics.mean(consumption),
            "liquid_median": statistics.mean(liquid),
            "drop_share": rejects / (rejects + completed) if rejects + completed else 0.0,
            "visits_completed": completed,
            "medical_loans": loans["count"],
            "happiness_median": statistics.mean(happiness),
            "health_mean": statistics.mean(health),
            "queued_share": statistics.mean(queued),
            "reserve_mean": statistics.mean(reserves) if reserves else 0.0,
            "runtime_s": time.perf_counter() - started,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--payment-sequence", default="legacy")
    parser.add_argument("--scenarios", default="default,hc_subsidy,hc_cap")
    parser.add_argument("--arms", default="before,R")
    args = parser.parse_args()
    print(f"seed={args.seed} households={args.households} ticks={args.ticks} "
          f"payment_sequence={args.payment_sequence}")
    print(" | ".join(KEYS))
    for scenario in args.scenarios.split(","):
        for arm in args.arms.split(","):
            row = run_arm(scenario, arm, args.households, args.ticks, args.seed, args.payment_sequence)
            print(" | ".join(f"{row[k]:.4f}" if isinstance(row[k], float) else str(row[k]) for k in KEYS),
                  flush=True)


if __name__ == "__main__":
    main()
