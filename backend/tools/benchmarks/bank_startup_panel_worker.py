"""Frozen-root startup panel worker. One process, one case; no simulator imports until root selection."""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
spec_worker = importlib.util.spec_from_file_location("common_evidence_worker", HERE / "evidence_panel_worker.py")
worker = importlib.util.module_from_spec(spec_worker)
spec_worker.loader.exec_module(worker)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=True).encode()).hexdigest()


def profile(agent):
    # The full dataclass fields, including initialized traits and ownership. Remove
    # only new startup fields from the paired projection; preserve them separately.
    return {f.name: worker._plain(getattr(agent, f.name)) for f in dataclasses.fields(agent)
            if f.name not in {"startup_loan_entitled", "startup_loan_originated"}}


def main(spec_path, out_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    sys.path.insert(0, str(Path(spec["root"]).resolve() / "backend"))
    from config import CONFIG, clone_config, get_config, use_config
    from payments import PaymentBook
    from tools.runners.run_large_simulation import compute_household_stats
    import payment_loans

    seed = spec["seed"]
    events = []
    benefit = {}
    old_benefit = PaymentBook.settle_benefits
    def benefits(book):
        eligible = [h.household_id for h in book.economy.households if h.employer_id is None]
        requested = len(eligible) * book.economy.government.get_unemployment_benefit_level()
        old_benefit(book)
        benefit.clear()
        benefit.update(eligible=len(eligible), recipients=len(book.benefits), paid=sum(book.benefits.values()),
                       denied=book.denied_benefits, requested=requested)
    PaymentBook.settle_benefits = benefits
    old_payment = payment_loans._post_payment
    def observe_payment(e, claim, amount):
        principal = claim.get("principal_remaining", 0.0)
        paid = old_payment(e, claim, amount)
        if claim.get("subtype") == "startup":
            reduction = principal - claim.get("principal_remaining", 0.0)
            events.append({"tick": e.current_tick + 1, "type": "bank_startup_payment", "claim_id": claim["claim_id"], "paid": paid,
                           "principal": reduction, "interest": paid - reduction})
        return paid
    payment_loans._post_payment = observe_payment
    old_writeoff = payment_loans._write_off
    def observe_writeoff(e, claim):
        amount = payment_loans._remaining(claim)
        principal = claim.get("principal_remaining", 0.0)
        interest = claim.get("accrued_interest", 0.0)
        old_writeoff(e, claim)
        if claim.get("subtype") == "startup" and amount > 0:
            events.append({"tick": e.current_tick + 1, "type": "bank_startup_writeoff", "claim_id": claim["claim_id"],
                           "amount": amount, "principal": principal, "interest": interest})
    payment_loans._write_off = observe_writeoff

    started = time.perf_counter()
    with use_config(clone_config()), contextlib.redirect_stdout(io.StringIO()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = seed
        if hasattr(CONFIG, "payment_bank_startup_loans_enabled"):
            CONFIG.payment_bank_startup_loans_enabled = spec["enabled"]
        economy = worker._construct({**spec, "levers": {"benefit_level": spec["benefit"]}}, seed)
        # Save resolved setup immediately, before any simulation step or observer.
        initial_config = dataclasses.asdict(get_config())
        initial_hh = [profile(h) for h in economy.households]
        initial_firms = [{"queued": queued, "profile": profile(f)}
                         for queued, fs in ((False, economy.firms), (True, economy.queued_firms)) for f in fs]
        py_rng = random.getstate()
        np_rng = np.random.get_state()
        initial_rng = {"python": py_rng, "numpy": [np_rng[0], np_rng[1].tolist(), *np_rng[2:]]}
        nonworking = {h.household_id for h in economy.households if h.employer_id is None}
        ranked_cash = sorted((h.cash_balance + max(0.0, h.bank_deposit), h.household_id)
                             for h in economy.households)
        lowcash = {hid for _, hid in ranked_cash[:len(ranked_cash) // 4]}
        initial = {"config": initial_config, "households": initial_hh, "firms": initial_firms,
                   "rng": initial_rng, "initial_nonworking_ids": sorted(nonworking),
                   "initial_lowcash_ids": sorted(lowcash), "lowcash_definition": "lowest initial liquid-wealth quartile, ties by ID",
                   "components": worker.state_components(economy),
                   "startup_markers": [{"id": f.firm_id, "originated": getattr(f, "startup_loan_originated", False),
                                        "entitled": getattr(f, "startup_loan_entitled", False)}
                                       for f in [*economy.firms, *economy.queued_firms]]}
        initial["profile_rng_digest"] = digest([initial_hh, initial_firms, initial_rng])
        # Track the legacy direct-Treasury pool, without pretending later loans
        # in the same mirror can be attributed to startup principal alone.
        treasury_startup_ids = set()
        treasury_pooled_paid = {}
        original_collect_direct = economy._payment_collect_direct_firm_loans
        def observe_direct():
            before = {f.firm_id: f.government_loan_remaining for f in economy.firms
                      if f.firm_id in treasury_startup_ids}
            result = original_collect_direct()
            paid = sum(before[f.firm_id] - f.government_loan_remaining for f in economy.firms
                       if f.firm_id in before)
            treasury_pooled_paid[economy.current_tick + 1] = paid
            return result
        economy._payment_collect_direct_firm_loans = observe_direct
        # Observe the existing entry decision once, from outside; never re-run it.
        entry = economy._maybe_create_new_firms
        def observe_entry():
            before_ids = {f.firm_id for f in economy.firms}
            treasury_before = economy.government.cash_balance
            entry()
            for f in economy.firms:
                if f.firm_id not in before_ids:
                    if f.government_loan_principal > 0:
                        treasury_startup_ids.add(f.firm_id)
                    events.append({"tick": economy.current_tick + 1, "type": "entrant", "id": f.firm_id,
                                   "cash": f.cash_balance, "owners": list(f.owners),
                                   "treasury_principal": f.government_loan_principal,
                                   "treasury_delta": economy.government.cash_balance - treasury_before})
        economy._maybe_create_new_firms = observe_entry
        queued = economy._activate_queued_firms
        def observe_queue():
            prior = {f.firm_id for f in economy.queued_firms}
            cash = {f.firm_id: f.cash_balance for f in economy.queued_firms}
            treasury = economy.government.cash_balance
            queued()
            activated = [f for f in economy.firms if f.firm_id in prior]
            for f in activated:
                if f.government_loan_principal > 0:
                    treasury_startup_ids.add(f.firm_id)
                events.append({"tick": economy.current_tick + 1, "type": "activation", "id": f.firm_id,
                               "cash_change": f.cash_balance - cash[f.firm_id],
                               "treasury_debt": f.government_loan_principal})
            if activated:
                events.append({"tick": economy.current_tick + 1, "type": "activation_treasury_delta",
                               "amount": economy.government.cash_balance - treasury})
        economy._activate_queued_firms = observe_queue
        if hasattr(economy, "_fund_private_startup"):
            fund = economy._fund_private_startup
            def observe_fund(firm, amount, term):
                reserves = economy.bank.cash_reserves if economy.bank else 0.0
                cash = firm.cash_balance
                previous_count = len(economy.bank.active_loans) if economy.bank else 0
                success = fund(firm, amount, term)
                after = economy.bank.cash_reserves if economy.bank else 0.0
                claims = economy.bank.active_loans[previous_count:] if economy.bank else []
                claim = claims[0] if len(claims) == 1 else {}
                events.append({"tick": economy.current_tick + 1, "type": "bank_startup_request", "id": firm.firm_id,
                               "amount": amount, "term": term, "approved": success,
                               "bank_debit": reserves - after, "firm_credit": firm.cash_balance - cash,
                               "claim_count": len(claims), "claim_id": claim.get("claim_id"),
                               "claim_principal": claim.get("principal", 0.0),
                               "residual": (reserves - after) - (firm.cash_balance - cash)})
                return success
            economy._fund_private_startup = observe_fund
        rows, states, times, money = [], [], [], [worker.total_money_net_of_injections(economy)]
        prev_unemployed, prev_legacy = worker._labour_force_unemployed(economy), worker._legacy_ids(economy)
        prior_ids = {f.firm_id for f in economy.firms}
        for week in range(1, spec["ticks"] + 1):
            benefit.clear()
            start_tick = time.perf_counter()
            economy.step()
            times.append(time.perf_counter() - start_tick)
            metrics = economy.get_economic_metrics()
            stats = compute_household_stats(economy.households)
            flows = worker._labour_flows(economy, prev_unemployed)
            legacy_now = worker._legacy_ids(economy)
            flows["legacy_exits"] = len(prev_legacy - legacy_now)
            row = worker.panel_row(economy, metrics, stats, CONFIG, np, flows)
            row.pop("real_gdp", None)  # no price-adjusted-output claim
            bank = economy.bank
            row.update({"benefit_eligible": benefit.get("eligible", 0), "benefit_recipients": benefit.get("recipients", 0),
                        "benefit_paid": benefit.get("paid", 0), "benefit_denied": benefit.get("denied", 0),
                        "benefit_requested": benefit.get("requested", 0),
                        "benefit_paid_per_eligible": benefit.get("paid", 0) / benefit["eligible"] if benefit.get("eligible") else None,
                        "morale": float(np.mean([h.morale for h in economy.households])),
                        "household_cash": sum(h.cash_balance for h in economy.households),
                        "household_deposits": sum(h.bank_deposit for h in economy.households),
                        "work_capable": sum(bool(h.can_work) for h in economy.households),
                        "employed": sum(h.employer_id is not None for h in economy.households),
                        "wage_total": sum(h.wage for h in economy.households if h.employer_id is not None),
                        "housing_met": sum(bool(h.met_housing_need) for h in economy.households),
                        "food_consumed": sum(h.food_consumed_this_tick for h in economy.households),
                        "services_consumed": sum(h.services_consumed_this_tick for h in economy.households),
                        "care_visits": sum(h.last_healthcare_units for h in economy.households),
                        "active_firms": len(economy.firms), "queued_firms": len(economy.queued_firms),
                        "active_firm_ids": sorted(f.firm_id for f in economy.firms),
                        "queued_firm_ids": sorted(f.firm_id for f in economy.queued_firms),
                        "treasury_startup_pooled_repayments": treasury_pooled_paid.get(week, 0.0),
                        "treasury_startup_pooled_outstanding": sum(f.government_loan_remaining for f in economy.firms if f.firm_id in treasury_startup_ids),
                        "firm_exits": len(prior_ids - {f.firm_id for f in economy.firms}),
                        "treasury_net_debt": economy.government.cash_balance - getattr(economy.government, "public_debt", 0),
                        "misc_pool": economy.misc_firm_revenue,
                        "misc_redistribution": sum(h.last_tick_ledger.get("redistribution", 0.0) for h in economy.households),
                        "welcome_stimulus": economy.last_tick_gov_post_warmup_stimulus,
                        "government_revenue": economy.government.last_tick_revenue,
                        "government_spending": economy.government.last_tick_spending,
                        "clearing_cash": economy.payment_book.clearing_cash,
                        "bank_reserves": bank.cash_reserves if bank else 0,
                        "bank_required_reserves": bank.required_reserves if bank else 0,
                        "bank_lendable": bank.lendable_cash if bank else 0,
                        "bank_equity": bank.equity if bank else 0,
                        "bank_new_loans": bank.last_tick_new_loans if bank else 0,
                        "bank_repayments": bank.last_tick_repayments if bank else 0,
                        "bank_defaults": bank.last_tick_defaults if bank else 0,
                        "bank_startup_principal": sum(l.get("principal_remaining", 0) for l in bank.active_loans if l.get("subtype") == "startup") if bank else 0,
                        "bank_startup_accrued_interest": sum(l.get("accrued_interest", 0) for l in bank.active_loans if l.get("subtype") == "startup") if bank else 0})
            for name, ids in (("initial_nonworking", nonworking), ("initial_lowcash", lowcash)):
                subset = [h for h in economy.households if h.household_id in ids]
                if subset:
                    row.update({f"{name}_happiness": float(np.mean([h.happiness for h in subset])),
                                f"{name}_health": float(np.mean([h.health for h in subset])),
                                f"{name}_morale": float(np.mean([h.morale for h in subset])),
                                f"{name}_liquid": float(np.mean([h.cash_balance + max(0, h.bank_deposit) for h in subset])),
                                f"{name}_housing_met": sum(bool(h.met_housing_need) for h in subset) / len(subset),
                                f"{name}_employed": sum(h.employer_id is not None for h in subset) / len(subset),
                                f"{name}_food": float(np.mean([h.food_consumed_this_tick for h in subset])),
                                f"{name}_services": float(np.mean([h.services_consumed_this_tick for h in subset]))})
            rows.append(row)
            states.append(worker.state_components(economy))
            money.append(worker.total_money_net_of_injections(economy))
            prev_unemployed, prev_legacy = worker._labour_force_unemployed(economy), legacy_now
            prior_ids = {f.firm_id for f in economy.firms}
    out = {"spec": spec, "initial": initial, "rows": rows, "states": states, "events": events,
           "final_loan_book": worker._loan_book(economy),
           "money_drift": [x - money[0] for x in money],
           "tick_median_seconds": float(np.median(times)), "tick_p95_seconds": float(np.percentile(times, 95)),
           "elapsed_seconds": time.perf_counter() - started, "python": sys.version,
           "numpy": np.__version__, "pythonhashseed": os.getenv("PYTHONHASHSEED")}
    path = Path(out_path)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(out, sort_keys=True, allow_nan=True), encoding="utf-8")
    temp.replace(path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
