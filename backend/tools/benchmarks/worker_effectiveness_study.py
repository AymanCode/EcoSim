"""Seeded study of how worker effectiveness reaches labor demand (round 1 PR2).

Answers two review questions with real runs instead of reasoning:

1. Labor demand: with higher worker effectiveness, do firms hire fewer
   workers for the same output? Reports headcount per firm, employment,
   unfilled vacancies, output per worker, mean wage, profit tax and GDP.
2. Low-happiness trap: after a household cash shock, do the workers in the
   bottom happiness quintile get stuck unemployed? Reports their unemployment
   rate, spell lengths and happiness recovery against everyone else.

Like ``business_ab_metrics.py`` it reads only public attributes, so
``--backend`` can point at an older checkout for the "before" column::

    python backend/tools/benchmarks/worker_effectiveness_study.py --seed 42
    python backend/tools/benchmarks/worker_effectiveness_study.py --seed 42 \
        --backend /tmp/ecosim-main/backend
    python backend/tools/benchmarks/worker_effectiveness_study.py --seed 42 \
        --set firms.worker_effectiveness_slope=0.65

The shock (``--shock-week``, ``--shock-cash-loss``) removes a share of every
household's cash at the start of that week. It is an outside intervention
for the scenario, not a model mechanism; set ``--shock-cash-loss 0`` to run
without it.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import random
import sys
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parent))
from business_ab_metrics import DEFAULT_BACKEND, _apply_override, _parse_override  # noqa: E402


def _ceiling(config) -> float:
    """Upper bound of the per-worker multiplier on this checkout."""
    firms = config.firms
    if hasattr(firms, "worker_effectiveness_max"):
        return float(firms.worker_effectiveness_max)
    return float(config.households.performance_max_multiplier)


def run(backend: Path, households: int, firms_per_category: int, seed: int, ticks: int,
        burn_in: int, shock_week: int, shock_cash_loss: float, overrides) -> dict:
    """Run one seeded economy; return labor-demand and shock-scenario metrics."""
    sys.path.insert(0, str(backend))
    import numpy as np
    from config import CONFIG, clone_config, use_config
    from tools.runners.run_large_simulation import create_large_economy

    profit_tax = [0.0]
    rows = []
    near_cap = []
    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = int(seed)
        for path, value in overrides:
            _apply_override(CONFIG, path, value)
        ceiling = _ceiling(CONFIG)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms_per_category)
            # GovernmentAgent uses __slots__, so record profit tax by wrapping
            # the class method for this run and restoring it afterwards.
            gov_cls = type(economy.government)
            original = gov_cls.apply_fiscal_results

            def recording(self, total_wage_taxes, total_profit_taxes, *args, **kwargs):
                if int(economy.current_tick) > burn_in:
                    profit_tax[0] += float(total_profit_taxes)
                return original(self, total_wage_taxes, total_profit_taxes, *args, **kwargs)

            gov_cls.apply_fiscal_results = recording

            cohort: set[int] = set()
            h_at_shock: dict[int, float] = {}
            spell: dict[int, int] = {}
            spells_done: list[int] = []
            unemp_weeks = {"low": 0, "rest": 0}
            lf_weeks = {"low": 0, "rest": 0}
            h_track = {"low": {}, "rest": {}}
            for _ in range(ticks):
                week = int(economy.current_tick) + 1
                if shock_cash_loss > 0 and week == shock_week:
                    labor = [h for h in economy.households if h.can_work]
                    hs = sorted(labor, key=lambda h: (h.happiness, h.household_id))
                    cohort = {h.household_id for h in hs[: max(1, len(hs) // 5)]}
                    h_at_shock = {h.household_id: float(h.happiness) for h in labor}
                    for h in economy.households:
                        h.cash_balance *= 1.0 - shock_cash_loss
                economy.step()
                tick = int(economy.current_tick)
                if tick <= burn_in:
                    continue
                employed = [h for h in economy.households if h.is_employed]
                private = [f for f in economy.firms if not f.is_baseline]
                food = [f for f in private if (f.good_category or "").lower() == "food"]
                food_workers = sum(len(f.employees) for f in food)
                ceil_hits = [h.get_performance_multiplier() >= ceiling - 0.02 * (ceiling - 1.0) - 1e-12 for h in employed]
                near_cap.append(sum(ceil_hits) / len(employed) if employed else 0.0)
                rows.append({
                    "employment": len(employed),
                    "headcount_per_private_firm": mean(len(f.employees) for f in private) if private else 0.0,
                    "unfilled_vacancies": sum(max(0, int(f.last_tick_planned_hires) - int(f.last_tick_actual_hires))
                                              for f in economy.firms),
                    "food_output_per_worker": (sum(float(f.last_units_produced) for f in food) / food_workers
                                               if food_workers else 0.0),
                    "mean_wage": mean(float(h.wage) for h in employed) if employed else 0.0,
                    "gdp": float(economy.get_economic_metrics().get("gdp_this_tick", 0.0) or 0.0),
                })
                if cohort and tick >= shock_week and tick < shock_week + 52:
                    for h in economy.households:
                        hid = h.household_id
                        if hid not in h_at_shock:
                            continue
                        group = "low" if hid in cohort else "rest"
                        lf_weeks[group] += 1
                        if not h.is_employed:
                            unemp_weeks[group] += 1
                            spell[hid] = spell.get(hid, 0) + 1
                        elif hid in spell:
                            spells_done.append((group, spell.pop(hid)))
                        offset = tick - shock_week
                        if offset in (0, 26, 51):
                            h_track[group].setdefault(offset, []).append(float(h.happiness))
            gov_cls.apply_fiscal_results = original
    sys.path.remove(str(backend))

    def avg(key):
        return float(mean(r[key] for r in rows))

    out = {
        "seed": seed, "households": households, "ticks": ticks, "burn_in": burn_in,
        "overrides": {".".join(p): v for p, v in overrides},
        "employment_mean": avg("employment"),
        "headcount_per_private_firm_mean": avg("headcount_per_private_firm"),
        "unfilled_vacancies_mean": avg("unfilled_vacancies"),
        "food_output_per_worker_mean": avg("food_output_per_worker"),
        "mean_wage_mean": avg("mean_wage"),
        "gdp_per_tick_mean": avg("gdp"),
        "profit_tax_total": profit_tax[0],
        "share_within_2pct_of_ceiling_mean": float(mean(near_cap)) if near_cap else 0.0,
        "ceiling": ceiling,
    }
    if h_at_shock:
        open_spells = [("low" if hid in cohort else "rest", n) for hid, n in spell.items()]
        for group in ("low", "rest"):
            done = [n for g, n in spells_done if g == group]
            censored = [n for g, n in open_spells if g == group]
            out[f"shock_{group}_unemployment_rate"] = unemp_weeks[group] / max(lf_weeks[group], 1)
            out[f"shock_{group}_spell_median_completed"] = float(median(done)) if done else 0.0
            out[f"shock_{group}_spells_open_at_end"] = len(censored)
            out[f"shock_{group}_happiness_at_shock"] = float(mean(
                v for hid, v in h_at_shock.items() if (hid in cohort) == (group == "low")))
            for offset, values in sorted(h_track[group].items()):
                out[f"shock_{group}_happiness_week_{offset}"] = float(mean(values))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backend", type=Path, default=DEFAULT_BACKEND)
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--firms-per-category", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=156)
    parser.add_argument("--burn-in", type=int, default=26)
    parser.add_argument("--shock-week", type=int, default=52)
    parser.add_argument("--shock-cash-loss", type=float, default=0.5,
                        help="share of every household's cash removed at --shock-week (0 disables)")
    parser.add_argument("--set", dest="overrides", type=_parse_override, action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(run(args.backend.resolve(), args.households, args.firms_per_category, args.seed,
                         args.ticks, args.burn_in, args.shock_week, args.shock_cash_loss, args.overrides),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
