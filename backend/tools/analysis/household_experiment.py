"""Run one household-experiment arm and write weekly metrics as JSON.

Usage:
  python hh_experiment.py run --backend <repo>/backend --out <file.json> --seed 42 --ticks 312
         [--sequence income_first] [--overrides '{"households.x": true}'] [--levers '{"benefit_level": "high"}']
  python hh_experiment.py batch --backend <repo>/backend --plan <plan.json> --jobs 1

Metrics are computed from simulation state only, so the runner works on any branch.
At most 1,000 households (AGENTS.md); shocks off, as in the policy audit.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from statistics import correlation, median
from types import SimpleNamespace

SCHEMA_VERSION = 1


def _pct(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return float(sorted_vals[idx])


def hand_to_mouth_counts(households, paid_income, unpaid_dues):
    """Week-26 proxy, based on each household's actual closing resources."""
    result = {"hand_to_mouth": 0, "not_hand_to_mouth": 0, "zero_income": 0}
    for h in households:
        income = paid_income.get(h.household_id, {})
        received = float(income.get("net", 0.0)) + float(income.get("benefit", 0.0))
        if received <= 0:
            result["zero_income"] += 1
        elif h.cash_balance + h.bank_deposit - unpaid_dues.get(h.household_id, 0.0) < received:
            result["hand_to_mouth"] += 1
        else:
            result["not_hand_to_mouth"] += 1
    return result


def id_skill_spearman(households):
    """Pearson correlation of household IDs and averaged skill ranks."""
    ordered = sorted(households, key=lambda h: (h.skills_level, h.household_id))
    ranks = {}
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end].skills_level == ordered[start].skills_level:
            end += 1
        rank = (start + end - 1) / 2
        ranks.update({h.household_id: rank for h in ordered[start:end]})
        start = end
    if len(ordered) < 2 or len(set(ranks.values())) < 2:
        return None
    return correlation([h.household_id for h in households], [ranks[h.household_id] for h in households])


def run(args):
    backend = Path(args.backend).resolve()
    sys.path.insert(0, str(backend))
    import sim_setup  # noqa: E402

    if args.households > 1000:
        raise SystemExit("AGENTS.md: at most 1,000 households")
    if args.sequence != "income_first" or args.seed not in (42, 43):
        raise SystemExit("Household plan requires income_first and seed 42 or 43")
    overrides = json.loads(args.overrides or "{}")
    levers = json.loads(args.levers or "{}")
    setup = SimpleNamespace(num_households=args.households, num_firms=5, payment_sequence=args.sequence,
                            enable_llm_government=False, disable_stabilizers=False, disabled_agents=[],
                            initial_policy={})
    economy, _ = sim_setup.build_economy_from_setup(setup, args.seed, config_overrides=overrides, extra_levers=levers)
    economy._apply_random_shocks = lambda *a, **k: None

    shop = {}
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

    from tools.benchmarks.panel_money import total_money_net_of_injections
    assert economy.external_injection_total == 0.0, "unexpected opening injection"
    money0 = total_money_net_of_injections(economy)
    opening_cash = sorted(h.cash_balance for h in economy.households)
    total_cash = sum(opening_cash)
    n0 = len(opening_cash)
    opening = {
        "household_cash_total": total_cash,
        "cash_gini": (2 * sum((i + 1) * value for i, value in enumerate(opening_cash))
                      / (n0 * total_cash) - (n0 + 1) / n0) if total_cash else 0.0,
        "cash_median": median(opening_cash),
        "cash_below_40_share": sum(value < 40 for value in opening_cash) / n0,
        "id_skill_spearman": id_skill_spearman(economy.households),
        "doctor_opening_capacity": sum(h.medical_visit_capacity() for h in economy.households
                                       if h.medical_training_status == "doctor"),
        "healthcare_firms": {str(f.firm_id): {"cash": float(f.cash_balance),
                             "wage_arrears": float(f.payment_wage_arrears)}
                             for f in economy.firms if (f.good_category or "").lower() == "healthcare"},
    }
    tracked_hc = {f.firm_id: f for f in economy.firms if (f.good_category or "").lower() == "healthcare"}
    open_spells = {}
    completed_spells = []

    def begin_spell(h, week):
        return {"household_id": h.household_id,
                "deprived_at_onset": bool(h.food_consumed_this_tick < h.min_food_per_tick or not h.met_housing_need),
                "entry_week": week, "exit_week": None, "censored": False, "censored_at_week": None}

    for h in economy.households:
        if h.health < 0.10:
            open_spells[h.household_id] = begin_spell(h, 0)
    hand_to_mouth_week_26 = None
    rows = []
    started = time.time()
    for _ in range(args.ticks):
        shop.clear()
        PaymentGoodsMarket.__init__, PaymentGoodsMarket.finish = p_init, p_finish
        try:
            economy.step()
        finally:
            PaymentGoodsMarket.__init__, PaymentGoodsMarket.finish = o_init, o_finish
        assert economy.external_injection_total == 0.0, "unexpected external injection"
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
        money_full = total_money_net_of_injections(economy)
        hc_firms = [f for f in economy.firms if (f.good_category or "").lower() == "healthcare"]
        tracked_hc.update({f.firm_id: f for f in hc_firms})
        entries = exits = 0
        for h in hh:
            if h.health < 0.10:
                if h.household_id not in open_spells:
                    entries += 1
                    open_spells[h.household_id] = begin_spell(h, t)
            elif h.household_id in open_spells:
                exits += 1
                spell = open_spells.pop(h.household_id)
                spell["exit_week"] = t
                completed_spells.append(spell)
        spells = [t - spell["entry_week"] + 1 for spell in open_spells.values()]
        if t == 26:
            hand_to_mouth_week_26 = hand_to_mouth_counts(
                hh, economy.payment_book.paid_income, economy.household_unpaid_dues_this_tick)
        hc_by_firm = {}
        live_hc = {f.firm_id for f in hc_firms}
        for firm in tracked_hc.values():
            support = economy.healthcare_support_this_tick.get(firm.firm_id, {})
            hc_by_firm[str(firm.firm_id)] = {
                "cash": float(firm.cash_balance), "wage_arrears": float(firm.payment_wage_arrears),
                "active": firm.firm_id in live_hc,
                "payroll": float(economy.payment_book.funded_wages_by_firm.get(firm.firm_id, 0.0)),
                **{key: float(support.get(key, 0.0)) for key in
                   ("bank_loans", "government_loans", "bailouts", "subsidies")},
            }
        extra = {
            "money_full": money_full, "money_drift": money_full - money0,
            "care_episodes_opened": economy.care_episodes_opened_this_tick,
            "care_visits_scheduled": economy.care_visits_scheduled_this_tick,
            "care_queue_admissions_new": float(economy.healthcare_requests_this_tick),
            "care_queue_admissions_retry": economy.care_queue_admissions_retry_this_tick,
            "care_deferrals": float(getattr(economy, "payment_care_deferrals_this_tick", 0)),
            "care_waits": float(getattr(economy, "payment_care_physical_waits_this_tick", 0)),
            "care_denials": float(getattr(economy, "payment_care_funding_denials_this_tick", 0)),
            "care_pending_visits": float(sum(max(0, h.pending_healthcare_visits) for h in hh)),
            "care_completed": float(economy.healthcare_completed_visits_this_tick),
            "care_visit_slots": economy.care_visit_slots_this_tick,
            "care_receipts": float(sum(economy.payment_book.receipts.get(fid, {}).get("revenue", 0.0) for fid in tracked_hc)),
            "hc_cash": float(sum(f.cash_balance for f in hc_firms)),
            "hc_cash_min_firm": float(min((f.cash_balance for f in hc_firms), default=0.0)),
            "hc_firms": len(hc_firms),
            "hc_wage_arrears": float(sum(getattr(f, "payment_wage_arrears", 0.0) for f in hc_firms)),
            "hc_payroll": float(sum(economy.payment_book.funded_wages_by_firm.get(fid, 0.0) for fid in tracked_hc)),
            "healthcare_firms": hc_by_firm,
            "sick_count": len(spells), "sick_entries": entries, "sick_exits": exits,
            "sick_mean_spell": (sum(spells) / len(spells)) if spells else 0.0,
            "health_lt_01": len(spells) / n,
            "health_lt_05": sum(1 for h in hh if h.health < 0.5) / n,
            "health_lt_07": sum(1 for h in hh if h.health < 0.7) / n,
            "evictions": float((getattr(economy, "last_housing_diagnostics", {}) or {}).get("eviction_count", 0.0)),
            "evicted_household_ids": list(economy.evicted_household_ids_this_tick),
            "household_loan_writeoffs": dict(economy.household_loan_writeoffs_this_tick),
            "household_unpaid_dues": {str(h.household_id): float(economy.household_unpaid_dues_this_tick.get(h.household_id, 0.0)) for h in hh},
            "external_injection_total": float(economy.external_injection_total),
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
    for spell in open_spells.values():
        spell["censored"] = True
        spell["censored_at_week"] = economy.current_tick
    out = {"schema_version": SCHEMA_VERSION, "opening": opening,
           "health_spells": completed_spells + list(open_spells.values()),
           "hand_to_mouth_week_26": hand_to_mouth_week_26,
           "money_tick0": money0, "arm": args.arm, "seed": args.seed, "sequence": args.sequence, "overrides": overrides, "levers": levers,
           "households": args.households, "ticks": args.ticks, "seconds": time.time() - started, "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out))
    print(f"done {args.arm} seed {args.seed} in {out['seconds']:.0f}s", flush=True)


def _cache_valid(path, *, ticks, households, job):
    try:
        from .household_experiment_summary import read_run
    except ImportError:  # Direct script execution.
        from household_experiment_summary import read_run
    try:
        run_data = read_run(path, expected_ticks=ticks)
        return (run_data["seed"] == job["seed"]
                and run_data["households"] == households
                and run_data["sequence"] == job.get("sequence", "income_first")
                and run_data["arm"] == job["arm"]
                and run_data["overrides"] == job.get("overrides", {})
                and run_data["levers"] == job.get("levers", {}))
    except (OSError, ValueError, TypeError, KeyError):
        return False


def batch(args):
    if args.jobs != 1:
        raise SystemExit("Household plan permits only one simulation process at a time")
    plan = json.loads(Path(args.plan).read_text())
    jobs = []
    for job in plan["jobs"]:
        if job.get("sequence", "income_first") != "income_first" or job["seed"] not in (42, 43):
            raise ValueError("Household plan requires income_first and seed 42 or 43")
        cmd = [sys.executable, __file__, "run", "--backend", args.backend, "--out", job["out"], "--seed", str(job["seed"]),
               "--households", str(args.households),
               "--ticks", str(plan.get("ticks", 312)), "--sequence", job.get("sequence", "income_first"),
               "--arm", job["arm"], "--overrides", json.dumps(job.get("overrides", {})),
               "--levers", json.dumps(job.get("levers", {}))]
        if Path(job["out"]).exists() and _cache_valid(job["out"], ticks=plan.get("ticks", 312), households=args.households, job=job):
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
                if p.returncode:
                    raise RuntimeError(f"household experiment exited with status {p.returncode}")
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
