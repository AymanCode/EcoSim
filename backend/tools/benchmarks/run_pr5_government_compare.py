"""Before/after and sensitivity runs for round 1 PR5 (government).

Compare mode (default) runs each scenario twice, once with every PR5 flag
off (pre-PR5 behavior) and once with the defaults, and prints a table.
Sensitivity mode re-runs the PR5 defaults with each PR5 parameter at -50%
and +50% and prints the metric deltas against the defaults.

Scenarios:
    default       levers as configured.
    stress        crisis benefits and high infrastructure/technology spending,
                  which stops at mid-run, so the debt and decay paths run.
    public_works  public works on and high infrastructure/technology spending;
                  the treasury gets +$2M at tick 0 so the startup is affordable,
                  so purchases reach the PublicWorks firm.
    social_high   sensitivity only: default levers with social_spending
                  "high", the one setting where social_max_multiplier binds
                  (at "medium" the multiplier settles near 1.05).

Usage (from backend/):
    python tools/benchmarks/run_pr5_government_compare.py \\
        --households 400 --firms-per-category 6 --seed 42 --ticks 104
    python tools/benchmarks/run_pr5_government_compare.py --sensitivity \\
        --households 400 --firms-per-category 6 --seed 42 --ticks 104
"""

from __future__ import annotations

import argparse
import contextlib
import io
import random
import sys
from pathlib import Path
from typing import Dict, Optional

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG, clone_config, use_config  # noqa: E402
from tools.runners.run_large_simulation import create_large_economy  # noqa: E402

PR5_FLAGS = (
    "public_debt_enabled",
    "flat_profit_tax_enabled",
    "public_capital_decay_enabled",
    "public_works_purchases_enabled",
    "price_cap_hold_enabled",
)

SCENARIOS = ("default", "stress", "public_works")

REPORT_KEYS = (
    ("unemployment_rate", "unemployment rate", "{:.3f}"),
    ("mean_happiness", "mean happiness", "{:.3f}"),
    ("gdp_this_tick", "GDP / tick", "{:,.0f}"),
    ("government_cash", "gov cash", "{:,.0f}"),
    ("public_debt", "public debt", "{:,.0f}"),
    ("annualized_debt_to_gdp", "debt / annual GDP", "{:.3f}"),
    ("gov_debt_rate_annual", "debt rate (annual)", "{:.4f}"),
    ("gov_debt_interest_this_tick", "debt interest / tick", "{:,.1f}"),
    ("gov_profit_taxes_this_tick", "profit tax / tick", "{:,.0f}"),
    ("technology_quality", "tech multiplier", "{:.4f}"),
    ("infrastructure_productivity", "infra multiplier", "{:.4f}"),
    ("public_works_workers", "public works workers", "{:.0f}"),
    ("benefit_replacement_rate", "benefit replacement", "{:.3f}"),
    ("health_coverage", "health coverage", "{:.3f}"),
    ("bank_reserves_min", "min bank reserves", "{:,.0f}"),
)

# (override key, default value, -50% value, +50% value, scenarios to run)
# Multiplier caps vary their excess over 1.0 (+/-50% of 0.15), since
# halving the cap itself (0.575) is meaningless.
SENSITIVITY = (
    ("gov.profit_tax_rate", 0.20, 0.10, 0.30, ("default", "stress")),
    ("bank.base_interest_rate", 0.03, 0.015, 0.045, ("stress",)),
    ("government.public_debt_risk_premium", 0.035, 0.0175, 0.0525, ("stress",)),
    ("government.surplus_debt_paydown_share", 0.5, 0.25, 0.75, ("default", "stress")),
    ("government.surplus_reserve_gdp_weeks", 1.5, 0.75, 2.25, ("default", "stress")),
    ("government.surplus_trigger_share_of_reserve", 0.20, 0.10, 0.30, ("default", "stress")),
    ("government.surplus_use_rate", 0.12, 0.06, 0.18, ("default", "stress")),
    ("government.public_capital_decay_per_tick", 0.05, 0.025, 0.075, ("stress",)),
    # Caps are tested where they can bind: public_works keeps infra/tech
    # funding on all run (multipliers near 1.146 at tick 104); stress stops
    # funding at mid-run, so by tick 104 the stock has decayed below any cap.
    ("government.public_capital_max_multiplier", 1.15, 1.075, 1.225, ("public_works",)),
    ("government.social_max_multiplier", 1.15, 1.075, 1.225, ("social_high",)),
    ("government.public_works_purchase_markup", 0.05, 0.025, 0.075, ("public_works",)),
    ("llm.government_rolling_windows_ticks", 13, 6, 20, ("default",)),
    ("llm.government_approval_stress_weeks_of_wage", 1.0, 0.5, 1.5, ("default",)),
)

SENSITIVITY_KEYS = (
    ("unemployment_rate", "u", "{:+.3f}"),
    ("mean_happiness", "H", "{:+.3f}"),
    ("gdp_this_tick", "GDP", "{:+,.0f}"),
    ("public_debt", "debt", "{:+,.0f}"),
    ("technology_quality", "tech", "{:+.4f}"),
    ("social_multiplier", "social", "{:+.4f}"),
    ("public_works_workers", "PW workers", "{:+.0f}"),
    ("approval_happiness_change", "approval dH", "{:+.4f}"),
    ("approval_financial_stress_share", "stress share", "{:+.3f}"),
)


def _apply_override(key: str, value: float, gov, bank) -> None:
    scope, name = key.split(".", 1)
    if scope == "gov":
        setattr(gov, name, value)
    elif scope == "bank":
        if bank is not None:
            setattr(bank, name, value)
    elif scope == "llm" and name == "government_rolling_windows_ticks":
        CONFIG.llm.government_rolling_windows_ticks = (int(value), 26, 52)
    else:
        setattr(getattr(CONFIG, scope), name, value)


def run_once(households: int, firms: int, seed: int, ticks: int, pr5_on: bool, scenario: str,
             override: Optional[tuple] = None, approval: bool = False) -> Dict[str, float]:
    """Run one seeded economy and return its tick-``ticks`` metrics."""
    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = int(seed)
        for flag in PR5_FLAGS:
            setattr(CONFIG.government, flag, pr5_on)
        CONFIG.llm.government_approval_observation_enabled = approval
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms)
        gov = economy.government
        if override is not None:
            _apply_override(override[0], override[1], gov, economy.bank)
        if scenario in ("stress", "public_works"):
            gov.set_lever("infrastructure_spending", "high")
            gov.set_lever("technology_spending", "high")
        if scenario == "stress":
            gov.set_lever("benefit_level", "crisis")
        if scenario == "social_high":
            gov.set_lever("social_spending", "high")
        if scenario == "public_works":
            gov.set_lever("public_works", "on")
            gov.cash_balance += 2_000_000.0
        bank_reserves_min = float("inf")
        for tick in range(ticks):
            if scenario == "stress" and tick == ticks // 2:
                gov.set_lever("infrastructure_spending", "none")
                gov.set_lever("technology_spending", "none")
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            if approval:
                # The server and LLM runners record a snapshot every tick; the
                # approval window reads this history.
                economy.append_metrics_snapshot(economy.get_economic_metrics(), tick=economy.current_tick)
            if economy.bank is not None:
                bank_reserves_min = min(bank_reserves_min, float(economy.bank.cash_reserves))
        metrics = economy.get_economic_metrics()
        metrics["government_cash"] = float(gov.cash_balance)
        metrics["gov_profit_taxes_this_tick"] = float(economy.last_tick_gov_profit_taxes)
        metrics["bank_reserves_min"] = bank_reserves_min
        metrics["social_multiplier"] = float(gov.social_happiness_multiplier)
        metrics["public_works_workers"] = float(sum(
            len(f.employees) for f in economy.firms if f.good_category == "PublicWorks"
        ))
        return metrics


def compare(args) -> None:
    for scenario in SCENARIOS:
        before = run_once(args.households, args.firms_per_category, args.seed, args.ticks, False, scenario)
        after = run_once(args.households, args.firms_per_category, args.seed, args.ticks, True, scenario)
        print(f"\n### {scenario}: seed {args.seed}, {args.households} households, tick {args.ticks}\n")
        print("| metric | before (flags off) | after (PR5 defaults) |")
        print("|---|---:|---:|")
        for key, label, fmt in REPORT_KEYS:
            b, a = before.get(key, 0.0), after.get(key, 0.0)
            print(f"| {label} | {fmt.format(float(b or 0.0))} | {fmt.format(float(a or 0.0))} |")


def sensitivity(args) -> None:
    base: Dict[tuple, Dict[str, float]] = {}
    print(f"\n### sensitivity: seed {args.seed}, {args.households} households, tick {args.ticks}")
    print("Deltas are (run at -50% or +50%) minus (PR5 defaults), same scenario.\n")
    print("| parameter | scenario | value | " + " | ".join(lbl for _, lbl, _ in SENSITIVITY_KEYS) + " |")
    print("|---|---|---:|" + "---:|" * len(SENSITIVITY_KEYS))
    for key, default, low, high, scenarios in SENSITIVITY:
        approval = key.startswith("llm.")
        for scenario in scenarios:
            bkey = (scenario, approval)
            if bkey not in base:
                base[bkey] = run_once(args.households, args.firms_per_category, args.seed, args.ticks,
                                      True, scenario, approval=approval)
            for value in (low, high):
                m = run_once(args.households, args.firms_per_category, args.seed, args.ticks, True,
                             scenario, override=(key, value), approval=approval)
                cells = []
                for mk, _, fmt in SENSITIVITY_KEYS:
                    if mk.startswith("approval") and not approval:
                        cells.append("n/a")
                        continue
                    cells.append(fmt.format(float(m.get(mk, 0.0) or 0.0) - float(base[bkey].get(mk, 0.0) or 0.0)))
                print(f"| {key} (default {default}) | {scenario} | {value} | " + " | ".join(cells) + " |",
                      flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--households", type=int, default=400)
    parser.add_argument("--firms-per-category", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=104)
    parser.add_argument("--sensitivity", action="store_true")
    args = parser.parse_args()
    if args.sensitivity:
        sensitivity(args)
    else:
        compare(args)


if __name__ == "__main__":
    main()
