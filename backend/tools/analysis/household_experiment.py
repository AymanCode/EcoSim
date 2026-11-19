"""Run one household-experiment arm and write weekly metrics as JSON.

Usage:
  python hh_experiment.py run --backend <repo>/backend --out <file.json> --seed 42 --ticks 312
         [--sequence income_first] [--overrides '{"households.x": true}'] [--levers '{"benefit_level": "high"}']
  python hh_experiment.py batch --backend <repo>/backend --plan <plan.json> --jobs 2

Metrics are computed from simulation state only, so the runner works on any branch.
At most 1,000 households (AGENTS.md); shocks off, as in the policy audit.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import median
from types import SimpleNamespace


def _pct(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return float(sorted_vals[idx])


def run(args):
    backend = Path(args.backend).resolve()
    sys.path.insert(0, str(backend))
    import sim_setup  # noqa: E402

    if args.households > 1000:
        raise SystemExit("AGENTS.md: at most 1,000 households")
    if args.sequence == "legacy":
        raise SystemExit("AGENTS.md: never use the legacy payment sequence; income_first is the norm")
    overrides = json.loads(args.overrides or "{}")
    levers = json.loads(args.levers or "{}")
    setup = SimpleNamespace(num_households=args.households, num_firms=5, payment_sequence=args.sequence,
                            enable_llm_government=False, disable_stabilizers=False, disabled_agents=[],
                            initial_policy={})
    economy, _ = sim_setup.build_economy_from_setup(setup, args.seed, config_overrides=overrides, extra_levers=levers)
    economy._apply_random_shocks = lambda *a, **k: None

    shop = {}
    if args.sequence != "legacy":
        from payment_sectors import PaymentGoodsMarket
        o_init, o_finish = PaymentGoodsMarket.__init__, PaymentGoodsMarket.finish

        def p_init(self, e, plans, firms):
            o_init(self, e, plans, firms)
            self._x_plans = plans

        def p_finish(self):
            r = o_finish(self)
            budget = sum(p.get("budget", 0.0) for p in self._x_plans.values())
            spent = sum(q * pr for goods in self.purchases.values() for (q, pr) in goods.values())
            shop[self.economy.current_tick] = (budget, spent)
            return r

        PaymentGoodsMarket.__init__, PaymentGoodsMarket.finish = p_init, p_finish
    else:
        from economy import Economy
        o_clear = Economy._clear_goods_market

        def c(self, plans, firms):
            purchases, sales = o_clear(self, plans, firms)
            budget = sum(p.get("budget", 0.0) for p in plans.values())
            spent = sum(q * pr for goods in purchases.values() for (q, pr) in goods.values())
            shop[self.current_tick] = (budget, spent)
            return purchases, sales

        Economy._clear_goods_market = c

    from tools.benchmarks.panel_money import total_money_with_bank
    money0 = total_money_with_bank(economy) - float(getattr(economy, "external_injection_total", 0.0))
    sick_spell = {h.household_id: 0 for h in economy.households}
    rows = []
    started = time.time()
    for _ in range(args.ticks):
        shop.clear()
        economy.step()
        t = economy.current_tick
        hh = economy.households
        n = len(hh)
        jobless = sum(1 for h in hh if h.employer_id is None)
        can = [h for h in hh if h.health >= 0.10]
        lf_jobless = sum(1 for h in can if h.employer_id is None)
        liquid = sorted(h.cash_balance + max(0.0, h.bank_deposit) for h in hh)
        hap = sorted(float(h.happiness) for h in hh)
        mor = sorted(float(h.morale) for h in hh)
        food = [f.price for f in economy.firms if (f.good_category or "").lower() == "food" and f.price > 0]
        rents = [f.price for f in economy.firms if (f.good_category or "").lower() == "housing" and f.price > 0]
        fp = median(food) if food else 0.0
        rp = median(rents) if rents else 0.0
        ess = [max(1e-6, h.min_food_per_tick * fp + (h.monthly_rent if h.renting_from_firm_id is not None else rp)) for h in hh]
        weeks = sorted((h.cash_balance + max(0.0, h.bank_deposit)) / e for h, e in zip(hh, ess))
        wages = [h.wage for h in hh if h.employer_id is not None]
        money = (sum(h.cash_balance for h in hh) + sum(f.cash_balance for f in economy.firms)
                 + economy.government.cash_balance + (economy.bank.cash_reserves if economy.bank else 0.0))
        gdp = None
        try:
            gdp = float(economy.get_economic_metrics().get("gdp_this_tick", 0.0))
        except Exception:  # metrics are optional
            gdp = None
        b, s = (shop[max(shop)] if shop else (0.0, 0.0))
        # Complete money (all pools, deposits counted once through reserves) and care pipeline.
        money_full = total_money_with_bank(economy) - float(getattr(economy, "external_injection_total", 0.0))
        hc_firms = [f for f in economy.firms if (f.good_category or "").lower() == "healthcare"]
        entries = exits = 0
        for h in hh:
            if h.health < 0.10:
                if sick_spell[h.household_id] == 0:
                    entries += 1
                sick_spell[h.household_id] += 1
            elif sick_spell[h.household_id] > 0:
                exits += 1
                sick_spell[h.household_id] = 0
        spells = [v for v in sick_spell.values() if v > 0]
        extra = {
            "money_full": money_full, "money_drift": money_full - money0,
            "care_opened": float(getattr(economy, "healthcare_requests_this_tick", 0.0)),
            "care_deferrals": float(getattr(economy, "payment_care_deferrals_this_tick", 0)),
            "care_waits": float(getattr(economy, "payment_care_physical_waits_this_tick", 0)),
            "care_denials": float(getattr(economy, "payment_care_funding_denials_this_tick", 0)),
            "care_pending_visits": float(sum(max(0, h.pending_healthcare_visits) for h in hh)),
            "care_completed": float(sum(f.last_units_sold for f in hc_firms)),
            "care_receipts": float(sum(economy.last_tick_revenue.get(f.firm_id, 0.0) for f in hc_firms)),
            "hc_cash": float(sum(f.cash_balance for f in hc_firms)),
            "hc_cash_min_firm": float(min((f.cash_balance for f in hc_firms), default=0.0)),
            "hc_firms": len(hc_firms),
            "hc_wage_arrears": float(sum(getattr(f, "payment_wage_arrears", 0.0) for f in hc_firms)),
            "illnesses": float(getattr(economy, "health_illnesses_this_tick", 0.0)),
            "sick_count": len(spells), "sick_entries": entries, "sick_exits": exits,
            "sick_mean_spell": (sum(spells) / len(spells)) if spells else 0.0,
            "health_lt_05": sum(1 for h in hh if h.health < 0.5) / n,
            "health_lt_07": sum(1 for h in hh if h.health < 0.7) / n,
            "evictions": float((getattr(economy, "last_housing_diagnostics", {}) or {}).get("eviction_count", 0.0)),
            "rent_arrears": float(sum(h.rent_arrears for h in hh)),
            "bank_new_loans": float(getattr(economy.bank, "last_tick_new_loans", 0.0)) if economy.bank else 0.0,
            "bank_defaults": float(getattr(economy.bank, "last_tick_defaults", 0.0)) if economy.bank else 0.0,
        }
        rows.append({**extra, 
            "t": t, "u": jobless / n, "u_lf": lf_jobless / max(1, len(can)),
            "liq_med": _pct(liquid, 0.5), "liq_p20": _pct(liquid, 0.2), "weeks_med": _pct(weeks, 0.5),
            "pov200": sum(1 for v in liquid if v < 200) / n, "pov13w": sum(1 for v in weeks if v < 13) / n,
            "hap_p10": _pct(hap, 0.1), "hap_med": _pct(hap, 0.5), "hap_p90": _pct(hap, 0.9),
            "hap_lo": sum(1 for v in hap if v <= 0.05) / n, "hap_hi": sum(1 for v in hap if v >= 0.95) / n,
            "mor_med": _pct(mor, 0.5), "mor_lo": sum(1 for v in mor if v <= 0.05) / n,
            "health": sum(h.health for h in hh) / n, "wage_mean": (sum(wages) / len(wages)) if wages else 0.0,
            "ess_med": median(ess), "food_price": fp, "rent": rp, "gdp": gdp, "money": money,
            "budget": b, "spent": s, "renters": sum(1 for h in hh if h.renting_from_firm_id is not None),
        })
    out = {"money_tick0": money0, "arm": args.arm, "seed": args.seed, "sequence": args.sequence, "overrides": overrides, "levers": levers,
           "households": args.households, "ticks": args.ticks, "seconds": time.time() - started, "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out))
    print(f"done {args.arm} seed {args.seed} in {out['seconds']:.0f}s", flush=True)


def batch(args):
    plan = json.loads(Path(args.plan).read_text())
    jobs = []
    for job in plan["jobs"]:
        cmd = [sys.executable, __file__, "run", "--backend", args.backend, "--out", job["out"], "--seed", str(job["seed"]),
               "--ticks", str(plan.get("ticks", 312)), "--sequence", job.get("sequence", "income_first"),
               "--arm", job["arm"], "--overrides", json.dumps(job.get("overrides", {})),
               "--levers", json.dumps(job.get("levers", {}))]
        if Path(job["out"]).exists():
            continue
        jobs.append(cmd)
    running = []
    while jobs or running:
        while jobs and len(running) < args.jobs:
            running.append(subprocess.Popen(jobs.pop(0), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
        for p in list(running):
            if p.poll() is not None:
                tail = (p.stdout.read() or "").strip().splitlines()
                print(tail[-1] if tail else f"exit {p.returncode}", flush=True)
                running.remove(p)
        time.sleep(2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "batch"])
    ap.add_argument("--backend", required=True)
    ap.add_argument("--out")
    ap.add_argument("--plan")
    ap.add_argument("--arm", default="control")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ticks", type=int, default=312)
    ap.add_argument("--households", type=int, default=1000)
    ap.add_argument("--sequence", default="income_first")
    ap.add_argument("--overrides")
    ap.add_argument("--levers")
    ap.add_argument("--jobs", type=int, default=1)  # one simulation process at a time (AGENTS.md)
    a = ap.parse_args()
    run(a) if a.mode == "run" else batch(a)
