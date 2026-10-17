"""Seeded before/after run for round 1 PR3 (household flags).

Builds the same economy as ``run_large_simulation.create_large_economy`` for
each arm, runs it, and prints post-warmup household metrics. Arms:
``before`` (both flags off), ``A`` (buffer-stock consumption), ``B`` (slow
reservation decay), ``AB`` (both).

Usage (from backend/):
    python tools/analysis/run_households_pr3_compare.py --households 1000 --ticks 260
"""

import argparse
import contextlib
import io
import statistics
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
for _path in (BACKEND_ROOT, BACKEND_ROOT / "tools" / "runners"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from config import CONFIG  # noqa: E402
from run_large_simulation import create_large_economy  # noqa: E402

ARMS = {"before": (False, False), "A": (True, False), "B": (False, True), "AB": (True, True)}


def run_arm(name: str, households: int, ticks: int) -> dict:
    """Run one arm and return its post-warmup metrics.

    Completed spells are counted when an unemployed household finds a job;
    the length is the ``unemployment_duration`` it had on the tick before
    (weeks). Spells still running at the end are not in those numbers, so
    ``ongoing_mean`` reports their mean length so far.
    """
    buffer_flag, reservation_flag = ARMS[name]
    CONFIG.households.buffer_stock_consumption = buffer_flag
    CONFIG.households.slow_reservation_decay = reservation_flag
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(num_households=households, num_firms_per_category=5)
    warmup = economy.warmup_ticks
    unemployment, wages, spending_cv = [], [], []
    spells = []
    previous = {}
    for _ in range(ticks):
        with contextlib.redirect_stdout(io.StringIO()):
            economy.step()
        if economy.current_tick <= warmup:
            continue
        metrics = economy.get_economic_metrics()
        unemployment.append(metrics["unemployment_rate"])
        wages.append(metrics["mean_wage"])
        spend = [h.last_consumption_spending for h in economy.households]
        if spend and statistics.mean(spend) > 0:
            spending_cv.append(statistics.pstdev(spend) / statistics.mean(spend))
        for h in economy.households:
            was = previous.get(h.household_id, 0)
            if h.is_employed and was > 0:
                spells.append(was)
            previous[h.household_id] = 0 if h.is_employed else h.unemployment_duration
    liquid = [max(0.0, h.cash_balance) + max(0.0, h.bank_deposit) for h in economy.households]
    happy = [h.happiness for h in economy.households]
    ongoing = [h.unemployment_duration for h in economy.households if not h.is_employed and h.can_work]
    return {
        "arm": name,
        "unemp_mean": statistics.mean(unemployment),
        "unemp_last": unemployment[-1],
        "spells": len(spells),
        "spell_median": statistics.median(spells) if spells else 0.0,
        "spell_mean": statistics.mean(spells) if spells else 0.0,
        "share_gt26": sum(s > 26 for s in spells) / len(spells) if spells else 0.0,
        "ongoing_mean": statistics.mean(ongoing) if ongoing else 0.0,
        "mean_wage": statistics.mean(wages),
        "median_liquid": statistics.median(liquid),
        "happy_median": statistics.median(happy),
        "spend_cv": statistics.mean(spending_cv) if spending_cv else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--arms", default="before,A,B,AB")
    args = parser.parse_args()
    print(f"seed={CONFIG.random_seed} households={args.households} ticks={args.ticks}")
    keys = ["arm", "unemp_mean", "unemp_last", "spells", "spell_median", "spell_mean",
            "share_gt26", "ongoing_mean", "mean_wage", "median_liquid", "happy_median", "spend_cv"]
    print(" | ".join(keys))
    for name in args.arms.split(","):
        row = run_arm(name, args.households, args.ticks)
        print(" | ".join(f"{row[k]:.3f}" if isinstance(row[k], float) else str(row[k]) for k in keys),
              flush=True)


if __name__ == "__main__":
    main()
