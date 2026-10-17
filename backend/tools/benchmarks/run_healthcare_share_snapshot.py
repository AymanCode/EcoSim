"""Byte-exact metrics snapshot for the healthcare subsidy charge path.

Runs seeded economies and hashes the full per-tick metrics JSON (no
rounding). Run it on two checkouts and compare the hashes: identical hashes
mean the change did not move any reported number.

Scenarios:
  default        no levers touched (healthcare subsidy share 0).
  hc_cap         healthcare sector subsidy at 50%, treasury cut to $100k at
                 tick 0 so the per-tick subsidy cap (2% of cash) binds.
  hc_crisis      healthcare sector subsidy at 50% with crisis benefits, which
                 drain the treasury and close the subsidy budget for stretches.

    cd backend
    python tools/benchmarks/run_healthcare_share_snapshot.py
    python tools/benchmarks/run_healthcare_share_snapshot.py --seeds 42,7 --ticks 104
    python tools/benchmarks/run_healthcare_share_snapshot.py \
        --payment-sequences income_first,income_late --payment-care-mode covered

Columns: sha256 of the metrics JSON, its size, subsidy $ denied by the cap
(sum of gov_subsidy_denied_by_cap_this_tick) and $ the treasury paid for
completed visits.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import random
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG, clone_config, use_config  # noqa: E402
from tools.runners.run_large_simulation import create_large_economy  # noqa: E402

SCENARIOS = ("default", "hc_cap", "hc_crisis")


def run(
    seed: int,
    ticks: int,
    scenario: str,
    payment_sequence: str,
    households: int,
    firms: int,
    care_mode: str = "patient_pay",
):
    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = seed
        CONFIG.payment_sequence = payment_sequence
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
        rows, denied, paid = [], 0.0, 0.0
        for _ in range(ticks):
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            metrics = economy.get_economic_metrics()
            denied += float(metrics.get("gov_subsidy_denied_by_cap_this_tick", 0.0))
            paid += sum(
                float(event.get("government_cost", 0.0))
                for event in economy.last_healthcare_events
                if event.get("event_type") == "visit_completed"
            )
            rows.append(metrics)
    blob = json.dumps(rows, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest(), len(blob), denied, paid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", default="42,7")
    parser.add_argument("--ticks", type=int, default=104)
    parser.add_argument("--households", type=int, default=400)
    parser.add_argument("--firms-per-category", type=int, default=6)
    parser.add_argument("--scenarios", default=",".join(SCENARIOS))
    parser.add_argument("--payment-sequences", default="legacy,income_first")
    parser.add_argument(
        "--payment-care-mode",
        default="patient_pay",
        choices=("patient_pay", "covered"),
        help="payment sequences only; covered also sets payment_assistance=care",
    )
    args = parser.parse_args()
    for seq in args.payment_sequences.split(","):
        for scenario in args.scenarios.split(","):
            for seed in (int(s) for s in args.seeds.split(",")):
                digest, size, denied, paid = run(
                    seed,
                    args.ticks,
                    scenario,
                    seq,
                    args.households,
                    args.firms_per_category,
                    args.payment_care_mode,
                )
                print(
                    f"seq={seq} care={args.payment_care_mode} scenario={scenario} seed={seed} sha256={digest} bytes={size} "
                    f"denied_by_cap=${denied:,.0f} hc_gov_paid=${paid:,.0f}",
                    flush=True,
                )


if __name__ == "__main__":
    main()
