"""Before/after run for the flat profit tax (round 1 G2).

Runs the same seeded economy twice: once with the cash-rank brackets
(``flat_profit_tax_enabled=False``, the old rule) and once with the flat tax
(the new default). In the flat-tax run it also prices every tick's firm
snapshots under the old brackets, so it can report which firms pay more or
less on the same profit.

Usage (from backend/):
    python tools/benchmarks/run_flat_profit_tax_compare.py --seeds 42 1 2 3 4
    python tools/benchmarks/run_flat_profit_tax_compare.py --seeds 42 1 2 3 4 --payment-sequence income_first
    python tools/benchmarks/run_flat_profit_tax_compare.py --seeds 42 1 2 --rate 0.10
"""

from __future__ import annotations

import argparse
import contextlib
import io
import random
import statistics
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG, clone_config, use_config  # noqa: E402
from tools.runners.run_large_simulation import create_large_economy  # noqa: E402

BURN_IN_TICKS = 13  # skip the first quarter when averaging over the run


def run_once(households: int, firms: int, seed: int, ticks: int, flat: bool,
             rate: float | None = None, payment_sequence: str = "legacy") -> Dict[str, float]:
    """Run one seeded economy and return run-level metrics."""
    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = int(seed)
        CONFIG.payment_sequence = payment_sequence
        CONFIG.government.flat_profit_tax_enabled = flat
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms)
        gov = economy.government
        if rate is not None:
            gov.profit_tax_rate = rate

        # Counterfactual: price the same snapshots under the old brackets.
        # _cash_rank_profit_taxes draws no random numbers, so it does not
        # change the run.
        counts = {"more": 0, "less": 0, "same": 0, "flat_rev": 0.0, "bracket_rev": 0.0}
        gov_cls = type(gov)
        original = gov_cls.plan_taxes

        def recording_plan_taxes(self, households_rows, firm_rows):
            plan = original(self, households_rows, firm_rows)
            if flat and len(firm_rows) >= 4:  # the per-tick call, not single exit-tax calls
                brackets = gov._cash_rank_profit_taxes(firm_rows)
                for firm_id, tax in plan["profit_taxes"].items():
                    old = brackets.get(firm_id, 0.0)
                    if tax <= 0.0 and old <= 0.0:
                        continue
                    if tax > old + 1e-9:
                        counts["more"] += 1
                    elif tax < old - 1e-9:
                        counts["less"] += 1
                    else:
                        counts["same"] += 1
                    counts["flat_rev"] += tax
                    counts["bracket_rev"] += old
            return plan

        # GovernmentAgent uses __slots__, so patch the class for this run only.
        gov_cls.plan_taxes = recording_plan_taxes
        try:
            return _run_ticks(economy, ticks, counts)
        finally:
            gov_cls.plan_taxes = original


def _run_ticks(economy, ticks: int, counts: Dict[str, float]) -> Dict[str, float]:
    """Step ``ticks`` times and summarize; ``counts`` fills in as taxes are planned."""
    gov = economy.government
    unemp: List[float] = []
    happy: List[float] = []
    gdp: List[float] = []
    profit_tax_total = 0.0
    for tick in range(ticks):
        with contextlib.redirect_stdout(io.StringIO()):
            economy.step()
        if tick >= BURN_IN_TICKS:
            m = economy.get_economic_metrics()
            unemp.append(float(m["unemployment_rate"]))
            happy.append(float(m["mean_happiness"]))
            gdp.append(float(m["gdp_this_tick"]))
        profit_tax_total += float(economy.last_tick_gov_profit_taxes)
    firms_alive = len([f for f in economy.firms if not getattr(f, "is_baseline", False)])
    payers = counts["more"] + counts["less"] + counts["same"]
    return {
        "unemployment_mean": statistics.fmean(unemp),
        "happiness_mean": statistics.fmean(happy),
        "gdp_mean": statistics.fmean(gdp),
        "profit_tax_per_tick": profit_tax_total / ticks,
        "gov_cash_end": float(gov.cash_balance),
        "private_firms_end": float(firms_alive),
        "share_pay_more": counts["more"] / payers if payers else 0.0,
        "share_pay_less": counts["less"] / payers if payers else 0.0,
        "static_revenue_ratio": (counts["flat_rev"] / counts["bracket_rev"]) if counts["bracket_rev"] else 0.0,
    }


ROWS = (
    ("unemployment_mean", "unemployment, mean wk 13-{t}", "{:.3f}"),
    ("happiness_mean", "happiness, mean wk 13-{t}", "{:.3f}"),
    ("gdp_mean", "GDP / tick, mean wk 13-{t}", "{:,.0f}"),
    ("profit_tax_per_tick", "profit tax / tick, run mean", "{:,.0f}"),
    ("gov_cash_end", "gov cash at end", "{:,.0f}"),
    ("private_firms_end", "private firms at end", "{:.0f}"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--households", type=int, default=400)
    parser.add_argument("--firms-per-category", type=int, default=6)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42])
    parser.add_argument("--ticks", type=int, default=104)
    parser.add_argument("--rate", type=float, default=None, help="override profit_tax_rate in both runs")
    parser.add_argument("--payment-sequence", default="legacy", choices=("legacy", "income_first", "income_late"),
                        help="legacy (the default) sends firm tax snapshots without cash, so the old "
                             "brackets put every firm in the bottom band; the other two include cash")
    args = parser.parse_args()

    results = []
    for seed in args.seeds:
        before = run_once(args.households, args.firms_per_category, seed, args.ticks, False, args.rate,
                          args.payment_sequence)
        after = run_once(args.households, args.firms_per_category, seed, args.ticks, True, args.rate,
                         args.payment_sequence)
        results.append((seed, before, after))
        print(f"\n### seed {seed}: {args.households} households, {args.ticks} ticks, {args.payment_sequence}"
              + (f", profit_tax_rate {args.rate}" if args.rate is not None else ""), flush=True)
        print("| metric | brackets (before) | flat (after) |\n|---|---:|---:|")
        for key, label, fmt in ROWS:
            print(f"| {label.format(t=args.ticks)} | {fmt.format(before[key])} | {fmt.format(after[key])} |")
        print(f"| taxpaying firm-ticks paying more / less than brackets | | "
              f"{after['share_pay_more']:.1%} / {after['share_pay_less']:.1%} |")
        print(f"| flat / bracket revenue on the same snapshots | | {after['static_revenue_ratio']:.3f} |", flush=True)

    if len(results) > 1:
        print(f"\n### after - before over seeds {args.seeds} (mean, sd)\n")
        print("| metric | mean | sd |\n|---|---:|---:|")
        for key, label, fmt in ROWS:
            deltas = [a[key] - b[key] for _, b, a in results]
            sd = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
            print(f"| {label.format(t=args.ticks)} | {fmt.format(statistics.fmean(deltas))} | {fmt.format(sd)} |")
        for key, label in (("share_pay_more", "share paying more"), ("share_pay_less", "share paying less"),
                           ("static_revenue_ratio", "flat / bracket revenue, same snapshots")):
            vals = [a[key] for _, _, a in results]
            sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
            print(f"| {label} (level) | {statistics.fmean(vals):.3f} | {sd:.3f} |")


if __name__ == "__main__":
    main()
