"""Byte-exact metrics snapshot for the healthcare subsidy charge path, by tick window.

Every run is one (payment sequence, care mode, scenario, seed) in its own
Python process, seeded with ``regression_snapshot._set_seed``. Each run
hashes the full per-tick metrics JSON (no rounding) separately for ticks
1-100, 101-200 and 201+, and prints readable totals for the same windows:
mean and standard deviation (volatility) of weekly GDP, unemployment, mean
price and happiness, treasury cash mean and min, visits and visit spend.
Run it on two checkouts and compare: equal hashes per window mean the change
moved no reported number in that window. Absolute hashes depend on the
Python and numpy versions (both printed), so compare arms on one machine.

Scenarios:
  default    no levers touched (healthcare subsidy share 0).
  hc_cap     healthcare sector subsidy at 50%, treasury cut to $100k at
             tick 0 so the per-tick subsidy cap (2% of cash) binds.
  hc_crisis  healthcare sector subsidy at 50% with crisis benefits, which
             drain the treasury and close the subsidy budget for stretches.

    cd backend
    python tools/benchmarks/run_healthcare_share_snapshot.py              # default matrix
    python tools/benchmarks/run_healthcare_share_snapshot.py --seeds 42,1 --ticks 260 --jobs 8
    python tools/benchmarks/run_healthcare_share_snapshot.py --one legacy patient_pay hc_cap 42 260
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import platform
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

WINDOWS = ((1, 100), (101, 200), (201, None))
# (payment sequence, care mode, scenarios)
MATRIX = (
    ("legacy", "patient_pay", ("default", "hc_cap", "hc_crisis")),
    ("income_first", "patient_pay", ("default", "hc_cap")),
    ("income_first", "covered", ("default",)),
    ("income_late", "covered", ("default",)),
)


def run_one(sequence: str, care_mode: str, scenario: str, seed: int, ticks: int, households: int, firms: int) -> dict:
    import numpy as np

    from config import CONFIG, clone_config, use_config
    from tools.benchmarks.regression_snapshot import _set_seed
    from tools.runners.run_large_simulation import create_large_economy

    with use_config(clone_config()):
        _set_seed(seed)
        CONFIG.payment_sequence = sequence
        CONFIG.payment_care_mode = care_mode
        if care_mode == "covered":
            CONFIG.payment_assistance = "care"  # funds the covered-care budget
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms)
        gov = economy.government
        if scenario != "default":
            gov.set_lever("sector_subsidy_target", "healthcare")
            gov.set_lever("sector_subsidy_level", 50)
        if scenario == "hc_cap":
            gov.cash_balance = 100_000.0
        elif scenario == "hc_crisis":
            gov.set_lever("benefit_level", "crisis")
        rows, visits = [], []
        for _ in range(ticks):
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            rows.append(economy.get_economic_metrics())
            done = [e for e in economy.last_healthcare_events if e.get("event_type") == "visit_completed"]
            visits.append((len(done), sum(float(e.get("household_cost", 0.0)) for e in done)))

    windows = {}
    for lo, hi in WINDOWS:
        sl = slice(lo - 1, hi)
        part, vis = rows[sl], visits[sl]
        if not part:
            continue
        label = f"{lo}-{hi if hi else ticks}"
        blob = json.dumps(part, sort_keys=True, default=str).encode()
        n = len(part)
        stats = {}
        for name, key in (("gdp", "gdp_this_tick"), ("unemployment", "unemployment_rate"),
                          ("price", "mean_price"), ("happiness", "mean_happiness")):
            values = [float(r.get(key, 0.0)) for r in part]
            mean = sum(values) / n
            sd = (sum((v - mean) ** 2 for v in values) / n) ** 0.5
            stats[f"{name}_mean"] = mean
            stats[f"{name}_sd"] = sd
        windows[label] = {
            "ticks": n,
            "sha256": hashlib.sha256(blob).hexdigest()[:16],
            **stats,
            "gov_cash_mean": sum(float(r.get("government_cash", 0.0)) for r in part) / n,
            "gov_cash_min": min(float(r.get("government_cash", 0.0)) for r in part),
            "visits": sum(v[0] for v in vis),
            "household_visit_spend": sum(v[1] for v in vis),
            "subsidy_denied_by_cap": sum(float(r.get("gov_subsidy_denied_by_cap_this_tick", 0.0)) for r in part),
        }
    return {
        "sequence": sequence, "care_mode": care_mode, "scenario": scenario, "seed": seed,
        "python": platform.python_version(), "numpy": np.__version__, "windows": windows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", default="42,1,2,3,4")
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--households", type=int, default=400)
    parser.add_argument("--firms-per-category", type=int, default=6)
    parser.add_argument("--jobs", type=int, default=4, help="processes in parallel; each run is its own process")
    parser.add_argument("--one", nargs=5, metavar=("SEQ", "CARE", "SCENARIO", "SEED", "TICKS"),
                        help="run a single configuration in this process and print one JSON line")
    args = parser.parse_args()

    if args.one:
        seq, care, scenario, seed, ticks = args.one
        result = run_one(seq, care, scenario, int(seed), int(ticks), args.households, args.firms_per_category)
        print(json.dumps(result, sort_keys=True), flush=True)
        return

    jobs = [
        (seq, care, scenario, int(seed))
        for seq, care, scenarios in MATRIX
        for scenario in scenarios
        for seed in args.seeds.split(",")
    ]

    def spawn(job):
        seq, care, scenario, seed = job
        cmd = [sys.executable, __file__, "--one", seq, care, scenario, str(seed), str(args.ticks),
               "--households", str(args.households), "--firms-per-category", str(args.firms_per_category)]
        out = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=BACKEND_ROOT).stdout
        return out.strip().splitlines()[-1]

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for line in pool.map(spawn, jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
