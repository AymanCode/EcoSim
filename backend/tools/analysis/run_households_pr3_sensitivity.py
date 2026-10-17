"""+/-50% sensitivity of the PR3 buffer-stock parameters (flag on).

For each parameter, runs the seeded A arm of ``run_households_pr3_compare``
with the parameter scaled by 0.5 and 1.5 and prints post-warmup mean
unemployment, median completed spell, and mean weekly consumption per
household. Ranges scale both ends, except ``risk_aversion_range``, which
scales its half-width around 1 so the mean stays 1.

Usage (from backend/):
    PYTHONHASHSEED=0 python tools/analysis/run_households_pr3_sensitivity.py --jobs 4
"""

import argparse
import copy
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_households_pr3_compare import CONFIG, run_arm  # noqa: E402

PARAMS = [
    "buffer_target_weeks_range", "buffer_adjust_speed_range", "risk_aversion_range",
    "buffer_unemployment_slope", "buffer_income_floor",
]


def scaled(name: str, value, factor: float):
    """Return ``value`` scaled by ``factor`` under the rules in the module docstring."""
    if name == "risk_aversion_range":
        return tuple(1.0 + (v - 1.0) * factor for v in value)
    if isinstance(value, tuple):
        return tuple(v * factor for v in value)
    return value * factor


def one(job):
    name, factor, households, ticks = job
    if name is not None:
        setattr(CONFIG.households, name, scaled(name, copy.copy(getattr(CONFIG.households, name)), factor))
    row = run_arm("A", households, ticks)
    value = getattr(CONFIG.households, name) if name else None
    return name, factor, value, row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    jobs = [(None, 1.0, args.households, args.ticks), (None, 1.0, args.households, args.ticks)]
    jobs += [(p, f, args.households, args.ticks) for p in PARAMS for f in (0.5, 1.5)]
    print("param | factor | value | unemp_mean | spell_median | consumption_mean")
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for name, factor, value, row in pool.map(one, jobs):
            print(f"{name or 'baseline'} | {factor} | {value} | {row['unemp_mean']:.4f} | "
                  f"{row['spell_median']} | {row['consumption_mean']:.2f}", flush=True)


if __name__ == "__main__":
    main()
