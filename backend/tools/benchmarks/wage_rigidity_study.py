"""How often the PR4b wage-rigidity rules bind, on one seeded run.

Reports, over the ticks after ``--burn-in``:
- contract cuts: share of worker-weeks (same worker, same firm, consecutive
  ticks) whose contract wage fell, and the mean size of those cuts;
- offer cuts: share of firm-weeks whose posted offer fell, the mean cut, and
  the share of firm-weeks the offer-cut cap lifted the offer;
- survival: share of firm-weeks with cash runway below
  ``survival_mode_runway_weeks`` (wage cuts allowed);
- the offer-cut cap actually applied (mean over ticks).

Example (flags off, then on):
    python backend/tools/benchmarks/wage_rigidity_study.py --seed 42 --set firms.wage_rigidity_enabled=false
    python backend/tools/benchmarks/wage_rigidity_study.py --seed 42
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import random
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--firms-per-category", type=int, default=5)
    parser.add_argument("--ticks", type=int, default=156)
    parser.add_argument("--burn-in", type=int, default=26)
    parser.add_argument("--set", dest="overrides", action="append", default=[],
                        help="section.key=JSON value (repeatable)")
    args = parser.parse_args()

    sys.path.insert(0, str(BACKEND))
    import numpy as np
    import agents
    from config import CONFIG, clone_config, use_config
    from tools.runners.run_large_simulation import create_large_economy

    lifts = {"n": 0}
    original = agents.FirmAgent.capped_offer

    def counting(self, proposed, previous):
        result = original(self, proposed, previous)
        if result > proposed:
            lifts["n"] += 1
        return result

    with use_config(clone_config()):
        for item in args.overrides:
            key, value = item.split("=", 1)
            section, name = key.split(".")
            setattr(getattr(CONFIG, section), name, json.loads(value))
        random.seed(args.seed)
        np.random.seed(args.seed)
        CONFIG.random_seed = args.seed
        agents.FirmAgent.capped_offer = counting
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                economy = create_large_economy(args.households, args.firms_per_category)
                prev_wages, prev_offers = {}, {}
                stats = dict(worker_weeks=0, contract_cuts=0, contract_cut_size=0.0, firm_weeks=0,
                             offer_cuts=0, offer_cut_size=0.0, survival=0, caps=[], lifts=0)
                for tick in range(args.ticks):
                    lifts["n"] = 0
                    economy.step()
                    measured = tick >= args.burn_in
                    wages, offers = {}, {}
                    for firm in economy.firms:
                        offers[firm.firm_id] = firm.wage_offer
                        for worker_id in firm.employees:
                            wages[(firm.firm_id, worker_id)] = firm.actual_wages.get(worker_id, firm.wage_offer)
                        if measured:
                            stats["firm_weeks"] += 1
                            stats["survival"] += firm.cash_runway_ticks < firm._firm_config().survival_mode_runway_weeks
                            old = prev_offers.get(firm.firm_id)
                            if old and firm.wage_offer < old - 1e-9:
                                stats["offer_cuts"] += 1
                                stats["offer_cut_size"] += 1.0 - firm.wage_offer / old
                    if measured:
                        stats["lifts"] += lifts["n"]
                        stats["caps"].append(economy.firms[0].offer_cut_cap if economy.firms else 1.0)
                        for key, wage in wages.items():
                            old = prev_wages.get(key)
                            if old is None:
                                continue
                            stats["worker_weeks"] += 1
                            if wage < old - 1e-9:
                                stats["contract_cuts"] += 1
                                stats["contract_cut_size"] += 1.0 - wage / old
                    prev_wages, prev_offers = wages, offers
        finally:
            agents.FirmAgent.capped_offer = original

    result = {
        "seed": args.seed,
        "overrides": args.overrides,
        "contract_cut_share": stats["contract_cuts"] / max(1, stats["worker_weeks"]),
        "contract_cut_mean": stats["contract_cut_size"] / max(1, stats["contract_cuts"]),
        "offer_cut_share": stats["offer_cuts"] / max(1, stats["firm_weeks"]),
        "offer_cut_mean": stats["offer_cut_size"] / max(1, stats["offer_cuts"]),
        "offer_cap_lift_share": stats["lifts"] / max(1, stats["firm_weeks"]),
        "survival_share": stats["survival"] / max(1, stats["firm_weeks"]),
        "offer_cut_cap_mean": sum(stats["caps"]) / max(1, len(stats["caps"])),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
