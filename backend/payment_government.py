"""Optional cash-funded Services worker-slot contract (GOV-P02).

Model choice: one 1,000-currency installment buys one future Services worker
slot, after one newly hired worker spends a fully paid week installing it.
The quote and one-tick minimum delivery lag are configured per run.
"""

from __future__ import annotations

import math

from config import CONFIG

EPS = 1e-6


def _state(economy):
    return economy.payment_state


def _events(economy, kind, project):
    events = _state(economy).setdefault("services_project_events", [])
    events.append({"type": kind, **project})
    if len(events) > 256:
        del events[:-256]


def reserve_payment_services_project(economy):
    """At prior close, encumber a full quote after baseline/care/rent claims."""
    state = _state(economy)
    old = state.pop("services_project", None)
    if old is not None and old.get("status") == "authorized":
        _events(economy, "expired_unworked", old)
    if not CONFIG.payment_services_project_enabled:
        return None
    quote = float(CONFIG.payment_services_project_cost)
    if not math.isfinite(quote) or quote <= 0:
        raise ValueError("Services project quote must be finite and positive")
    if economy._payment_free_treasury_cash() + EPS < quote:
        return None
    candidates = [f for f in economy.firms if (f.good_category or "").lower() == "services"]
    if not candidates:
        return None
    unmet = getattr(economy, "last_tick_unmet_demand_by_firm", {})
    firm = min(candidates, key=lambda f: (-float(unmet.get(f.firm_id, 0.0)), f.firm_id))
    restricted = state["restrictions"]
    if restricted.get("project", 0.0) > EPS:
        raise ValueError("Previous Services project restriction was not closed")
    restricted["project"] = quote
    economy._payment_sync_restrictions()
    project = {"project_id": f"services-{economy.current_tick + 1}-{firm.firm_id}",
               "firm_id": int(firm.firm_id), "quote": quote,
               "authorized_tick": int(economy.current_tick),
               "work_tick": int(economy.current_tick) + 1,
               "expiry_tick": int(economy.current_tick) + 1,
               "worker_id": None, "paid_installments": 0.0,
               "completed_slots": 0, "status": "authorized"}
    state["services_project"] = project
    _events(economy, "authorized", project)
    return project


def assign_payment_services_project_worker(economy, hired_by_firm, baseline_hire_count=None):
    """Use one newly hired, retained worker; ordinary production excludes them."""
    project = _state(economy).get("services_project")
    if not project or project.get("status") != "authorized" or economy.current_tick != project["work_tick"]:
        return {}
    fid = project["firm_id"]
    firm = economy.firm_lookup.get(fid)
    if firm is None or (firm.good_category or "").lower() != "services":
        return {}
    hired = list(dict.fromkeys(int(hid) for hid in hired_by_firm.get(fid, ())))
    ordinary_hires = int((baseline_hire_count or {}).get(fid, len(hired)))
    if ordinary_hires < 0 or len(hired) <= ordinary_hires:
        return {}
    for hid in hired[ordinary_hires:]:
        household = economy.household_lookup.get(hid)
        if household is None or household.employer_id != fid or hid not in firm.employees:
            continue
        due = max(0.0, float(firm.actual_wages.get(hid, 0.0)))
        if due <= EPS:
            continue
        project["worker_id"] = hid
        project["frozen_wage_due"] = due
        project["status"] = "assigned"
        _events(economy, "assigned", project)
        return {fid: hid}
    return {}


def complete_payment_services_project(economy):
    """At 11.5, pay only fully funded work and schedule one future slot."""
    state = _state(economy)
    project = state.get("services_project")
    if not project or project.get("status") != "assigned":
        return False
    if economy.current_tick != project["work_tick"]:
        return False
    fid, hid = project["firm_id"], project["worker_id"]
    firm = economy.firm_lookup.get(fid)
    household = economy.household_lookup.get(hid)
    book = economy.payment_book
    paid = float(book.current_paid_by_firm_worker.get((fid, hid), 0.0))
    current_due = float(book.current_due.get(fid, {}).get(hid, 0.0))
    if (firm is None or household is None or household.employer_id != fid
            or hid not in firm.employees or current_due <= EPS
            or paid + EPS < current_due):
        project["status"] = "cancelled_unpaid_worker"
        _events(economy, "cancelled_unpaid_worker", project)
        return False
    quote = float(project["quote"])
    if state["restrictions"].get("project", 0.0) + EPS < quote:
        project["status"] = "payable_unfunded"
        state.setdefault("services_project_payables", {})[fid] = quote
        _events(economy, "payable_unfunded", project)
        return False
    economy._payment_spend_restriction("project", quote)
    firm.cash_balance += quote
    pending = state.setdefault("services_pending_receipts", {})
    pending[fid] = pending.get(fid, 0.0) + quote
    open_tick = int(economy.current_tick) + int(CONFIG.payment_services_project_lag_ticks)
    slots = state.setdefault("services_future_slots", [])
    slots.append({"firm_id": fid, "units": 1, "open_tick": open_tick,
                  "project_id": project["project_id"]})
    project["paid_installments"] = quote
    project["completed_slots"] = 1
    project["status"] = "completed"
    _events(economy, "completed", project)
    return True


def activate_payment_services_slots(economy):
    """Open paid slot no earlier than the next tick after worker installation."""
    state = _state(economy)
    pending = state.get("services_future_slots", [])
    remaining = []
    opened = 0
    for entry in pending:
        if economy.current_tick < entry["open_tick"]:
            remaining.append(entry)
            continue
        firm = economy.firm_lookup.get(entry["firm_id"])
        if firm is None or (firm.good_category or "").lower() != "services":
            continue
        firm.production_capacity_units += float(entry["units"])
        opened += entry["units"]
    state["services_future_slots"] = remaining
    return opened


def settle_payment_services_exit(economy, firm):
    """Assess the earned 11.5 receipt before the provider's exit waterfall."""
    state = _state(economy)
    fid = firm.firm_id
    pending = state.setdefault("services_pending_receipts", {})
    amount = float(pending.pop(fid, 0.0))
    tax = 0.0
    if amount > EPS:
        tax = economy._payment_collect_pending_services_exit_tax(firm, amount)
        state["services_exit_tax_convention"] = "single_snapshot"
    project = state.get("services_project")
    if project is not None and project.get("firm_id") == fid and project.get("status") in {"authorized", "assigned"}:
        project["status"] = "cancelled_provider_exit"
        _events(economy, "cancelled_provider_exit", project)
    state["services_future_slots"] = [entry for entry in state.get("services_future_slots", []) if entry["firm_id"] != fid]
    return tax
