"""Seeded by-window panel for one arm of a households comparison.

Runs ONE arm in this process (run each arm and seed in its own process), seeded
exactly like ``tools/benchmarks/regression_snapshot._set_seed``, and writes the
weekly panel the EcoSim PR checklist asks for to a JSON file. Summarize several
runs with ``summarize_household_window_panel.py``.

Usage (from backend/):
    python tools/analysis/run_household_window_panel.py --seed 42 --ticks 260 \
        --set households.skills_dynamics=True --probe skills --out on_42.json

``--set`` takes ``section.field=<python literal>`` and is applied to a private
config copy (``clone_config``/``use_config``), never to a shared one.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
for _path in (BACKEND_ROOT, BACKEND_ROOT / "tools" / "runners", BACKEND_ROOT / "tools" / "benchmarks"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from config import CONFIG, clone_config, use_config  # noqa: E402
try:  # households 29a's shared helper, when present
    from household_liquidity import liquid_wealth  # noqa: E402
except ImportError:  # same definition as main's wellbeing read (#32)
    def liquid_wealth(cash: float, deposit: float) -> float:
        return cash + max(0.0, deposit)
from regression_snapshot import _set_seed  # noqa: E402
from run_large_simulation import create_large_economy  # noqa: E402


def _apply_sets(cfg, sets):
    for item in sets:
        path, raw = item.split("=", 1)
        target = cfg
        parts = path.split(".")
        for part in parts[:-1]:
            target = getattr(target, part)
        if not hasattr(target, parts[-1]):
            raise SystemExit(f"unknown config field {path}")
        setattr(target, parts[-1], ast.literal_eval(raw))


class SkillsProbe:
    """Skill level, floor and hiring of the week-1 bottom quartile."""

    def __init__(self, economy):
        self.start = np.array([h.skills_level for h in economy.households])
        self.low = self.start < np.percentile(self.start, 25)
        self.prev_emp = np.array([h.is_employed for h in economy.households])

    def row(self, economy):
        hh = economy.households
        s = np.array([h.skills_level for h in hh])
        emp = np.array([h.is_employed for h in hh])
        hired = emp & ~self.prev_emp
        self.prev_emp = emp
        dur = np.array([h.unemployment_duration for h in hh])
        floors = np.array([h.skill_floor if h.skill_floor is not None else np.nan for h in hh])
        return {
            "skill_mean": float(s.mean()), "skill_min": float(s.min()),
            "skill_unemployed": float(s[~emp].mean()) if (~emp).any() else None,
            "below_week1": float((s < self.start - 1e-12).mean()),
            "below_floor": int(np.nansum(s < floors - 1e-12)),
            "low_skill_hires": int(hired[self.low].sum()), "low_skill_employed": float(emp[self.low].mean()),
            "jobless_52w": float(((~emp) & (dur > 52)).mean()),
        }


class HealthcareProbe:
    """Queued households at budget time and their food, cash and loans."""

    def __init__(self, economy):
        self.state = {}
        self.loans = 0
        original = economy._household_consumption_budgets
        payment = economy.payment_sequence != "legacy"

        def observed(*args, **kwargs):
            budgets = original(*args, **kwargs)
            if kwargs.get("settled_income") or payment:
                self.state["queued"] = np.array(
                    [h.queued_healthcare_firm_id is not None for h in economy.households])
                self.state["budget"] = np.asarray(budgets, dtype=np.float64).copy()
            return budgets

        economy._household_consumption_budgets = observed
        issue = economy._issue_medical_loan

        def counting_issue(household, amount):
            issued = issue(household, amount)
            if issued:
                self.loans += 1
            return issued

        economy._issue_medical_loan = counting_issue
        try:
            import payment_loans
            fund = payment_loans.fund_medical_loan

            def counting_fund(*args, **kwargs):
                result = fund(*args, **kwargs)
                if result:
                    self.loans += 1
                return result

            payment_loans.fund_medical_loan = counting_fund
        except (ImportError, AttributeError):
            pass

    def row(self, economy):
        hh = economy.households
        queued = self.state.get("queued", np.zeros(len(hh), dtype=bool))
        budget = self.state.get("budget", np.ones(len(hh)))
        food = np.array([h.food_consumed_this_tick for h in hh])
        need = np.array([h.min_food_per_tick for h in hh])
        cash = np.array([h.cash_balance for h in hh])
        row = {
            "queued": int(queued.sum()),
            "queued_short_food": int((queued & (food < need - 1e-9)).sum()),
            "queued_zero_budget": int((queued & (budget <= 1e-9)).sum()),
            "queued_negative_cash": int((queued & (cash < -1e-9)).sum()),
            "negative_cash": int((cash < -1e-9).sum()),
            "medical_loans_cum": int(self.loans),
        }
        self.state.clear()
        return row


PROBES = {"skills": SkillsProbe, "healthcare": HealthcareProbe}


def run(args) -> dict:
    cfg = clone_config()
    cfg.payment_sequence = args.payment_sequence
    _apply_sets(cfg, args.set)
    with use_config(cfg):
        _set_seed(args.seed)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(num_households=args.households,
                                           num_firms_per_category=args.firms_per_category)
        probe = PROBES[args.probe](economy) if args.probe else None
        poverty_line = CONFIG.households.poverty_threshold
        rows = []
        for _ in range(args.ticks):
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            m = economy.get_economic_metrics()
            hh = economy.households
            liquid = np.array([liquid_wealth(h.cash_balance, h.bank_deposit) for h in hh])
            food = np.array([h.food_consumed_this_tick for h in hh])
            need = np.array([h.min_food_per_tick for h in hh])
            happy = np.array([h.happiness for h in hh])
            row = {
                "t": int(economy.current_tick),
                "gdp": float(m.get("gdp_this_tick", 0.0)),
                "unemployment": float(m["unemployment_rate"]),
                "lf_unemployment": float(m.get("labor_force_unemployment_rate", m["unemployment_rate"])),
                "price": float(m.get("mean_price", 0.0)),
                "gov_balance": float(economy.government.cash_balance),
                "firm_profit": float(sum(getattr(f, "last_profit", 0.0) for f in economy.firms)),
                "poverty_cash": float(m.get("households_below_poverty", 0)) / len(hh),
                "poverty_liquid": float((liquid < poverty_line).mean()),
                "food_sufficient": float((food >= need - 1e-9).mean()),
                "liquid_deciles": [float(v) for v in np.percentile(liquid, [10, 20, 30, 40, 50, 60, 70, 80, 90])],
                "happiness_mean": float(happy.mean()),
                "happiness_median": float(np.median(happy)),
                "health_mean": float(np.mean([h.health for h in hh])),
            }
            if probe is not None:
                row.update(probe.row(economy))
            rows.append(row)
    return {"seed": args.seed, "arm": args.arm, "sets": args.set, "payment_sequence": args.payment_sequence,
            "households": args.households, "ticks": args.ticks, "rows": rows}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--arm", default="arm")
    p.add_argument("--ticks", type=int, default=260)
    p.add_argument("--households", type=int, default=1000)
    p.add_argument("--firms-per-category", type=int, default=5)
    p.add_argument("--payment-sequence", default="legacy", choices=("legacy", "income_first", "income_late"))
    p.add_argument("--set", action="append", default=[])
    p.add_argument("--probe", choices=sorted(PROBES), default=None)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    args.out.write_text(json.dumps(run(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
