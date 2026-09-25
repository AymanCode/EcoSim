"""Cash-backed, delayed Housing capacity for named payment scenarios."""

from __future__ import annotations

import math

from agents import LoanContract
from config import CONFIG

EPS = 1e-6


def _projects(economy):
    return economy.payment_state.setdefault("housing_projects", {})


def _event(economy, kind, project):
    events = economy.payment_state.setdefault("housing_project_events", [])
    events.append({"type": kind, **project})
    if len(events) > 256:
        del events[:-256]


def project_quote(units):
    raw_units = float(units)
    if not math.isfinite(raw_units) or not raw_units.is_integer():
        raise ValueError("Housing project requires whole units")
    units = int(raw_units)
    if units < 1 or units > int(CONFIG.payment_construction_project_cap):
        raise ValueError("Housing project units outside configured cap")
    cost = float(CONFIG.payment_construction_unit_cost)
    if not math.isfinite(cost) or cost <= 0:
        raise ValueError("Housing construction cost must be finite and positive")
    return units * cost


def can_start_housing_project(economy, firm, units, route):
    if (firm.good_category or "").lower() != "housing":
        return False
    if route not in {"self", "mortgage", "long_term"}:
        return False
    if firm.firm_id in _projects(economy):
        return False
    if float(getattr(firm, "payment_wage_arrears", 0.0)) > EPS:
        return False
    if route != "self" and economy.current_tick < economy.payment_state.get(
            "loan_credit_cooldown_until", {}).get(("firm", firm.firm_id), -1):
        return False
    try:
        project_quote(units)
    except (TypeError, ValueError):
        return False
    if route == "long_term" and not economy.households:
        return False
    return True


def register_funded_housing_project(economy, firm, units, route, *, loan_id=None):
    """Commit an already funded whole project; external credit gate runs first.

    For loan routes, the caller has credited firm cash with exactly the project
    quote.  This function is the only construction debit and recipient owner.
    """
    if not can_start_housing_project(economy, firm, units, route):
        return False
    amount = project_quote(units)
    if route != "self" and not loan_id:
        raise ValueError("Funded housing loan needs a stable claim ID")
    if firm.cash_balance + EPS < amount:
        return False
    firm.cash_balance -= amount
    if route == "long_term":
        economy.payment_state["housing_equal_distribution_hold"] = (
            economy.payment_state.get("housing_equal_distribution_hold", 0.0) + amount
        )
    else:
        economy._collect_misc_revenue(amount)
    completion_tick = int(economy.current_tick) + int(CONFIG.payment_construction_lag_ticks)
    project = {"firm_id": int(firm.firm_id), "route": route, "units": int(units),
               "paid_amount": amount, "loan_id": loan_id,
               "start_tick": int(economy.current_tick), "completion_tick": completion_tick}
    _projects(economy)[firm.firm_id] = project
    _event(economy, "funded", project)
    if int(CONFIG.payment_construction_lag_ticks) == 0:
        complete_payment_projects(economy)
    return True


def try_start_self_funded_project(economy, firm):
    """Preserve the incumbent occupancy/crisis gate with a reachable quote."""
    if not can_start_housing_project(economy, firm, 1, "self"):
        return False
    occupancy = len(firm.current_tenants) / max(1, firm.max_rental_units)
    homeless = sum(h.renting_from_firm_id is None for h in economy.households)
    if occupancy < 0.85 and homeless <= 30:
        return False
    amount = project_quote(1)
    if firm.cash_balance + EPS < 2.0 * amount:
        if economy.bank is not None:
            firm.needs_housing_expansion_loan = True
            firm.housing_expansion_loan_amount = amount
        return False
    return register_funded_housing_project(economy, firm, 1, "self")


def start_payment_mortgage_project(economy, firm):
    """Keep existing DSCR/LTV/reserve gates; finance one exact whole quote."""
    if not firm.needs_housing_expansion_loan or firm.housing_expansion_loan_amount <= 0:
        return False
    def clear():
        firm.needs_housing_expansion_loan = False
        firm.housing_expansion_loan_amount = 0.0
    bank = economy.bank
    units = min(int(CONFIG.payment_construction_project_cap),
                int(CONFIG.firms.housing_max_build_per_tick),
                max(1, int(round(float(firm.housing_expansion_loan_amount) / CONFIG.payment_construction_unit_cost))))
    if not can_start_housing_project(economy, firm, units, "mortgage") or bank is None or not bank.can_lend():
        clear()
        return False
    principal = project_quote(units)
    cfg = CONFIG.firms
    assets = (firm.max_rental_units + units) * cfg.housing_unit_market_value + firm.cash_balance
    existing_debt = sum(l.principal_remaining for l in firm.housing_active_loans)
    if assets > 0 and (existing_debt + principal) / assets > cfg.housing_max_ltv:
        clear()
        return False
    pmt = economy._compute_housing_pmt(principal, bank.current_annual_rate, cfg.housing_loan_term_ticks)
    live_pmt = sum(l.pmt_per_tick for l in firm.housing_active_loans)
    occupied = len(firm.current_tenants)
    projected_revenue = firm.price * min(occupied + units, firm.max_rental_units + units) * cfg.housing_vacancy_buffer
    if live_pmt + pmt > EPS and projected_revenue / (live_pmt + pmt) < cfg.housing_min_dscr:
        clear()
        return False
    if bank.lendable_cash + EPS < principal:
        clear()
        return False
    claim_id = f"mortgage-{firm.firm_id}-{economy.current_tick}"
    bank.cash_reserves -= principal
    firm.cash_balance += principal
    contract = LoanContract(principal_remaining=principal, pmt_per_tick=pmt,
                            ticks_remaining=cfg.housing_loan_term_ticks,
                            origination_tick_rate=bank.current_annual_rate / 52.0,
                            claim_id=claim_id, contract_version=2,
                            first_due_tick=int(economy.current_tick) + 1)
    firm.housing_active_loans.append(contract)
    firm.bank_loan_principal += principal
    firm.bank_loan_remaining += principal
    firm.bank_loan_payment_per_tick += pmt
    if not register_funded_housing_project(economy, firm, units, "mortgage", loan_id=claim_id):
        raise RuntimeError("Funded mortgage could not register its housing project")
    clear()
    return True


def distribute_payment_project_proceeds(economy):
    """Preserve early long-term construction's equal-household phase-8.5 route."""
    amount = float(economy.payment_state.get("housing_equal_distribution_hold", 0.0))
    if amount <= EPS:
        return 0.0
    if not economy.households:
        raise RuntimeError("Funded equal-household construction has no recipients")
    share = amount / len(economy.households)
    for household in economy.households:
        household.cash_balance += share
        household.add_ledger_flow("other", share)
    economy.payment_state["housing_equal_distribution_hold"] = 0.0
    return amount


def complete_payment_projects(economy):
    """Open funded units before rental matching at or after completion tick."""
    completed = []
    for fid, project in list(_projects(economy).items()):
        if int(economy.current_tick) < project["completion_tick"]:
            continue
        firm = economy.firm_lookup.get(fid)
        if firm is None:
            cancel_payment_projects_for_exit(economy, fid)
            continue
        units = project["units"]
        firm.max_rental_units += units
        firm.production_capacity_units += float(units)
        firm.expected_sales_units += float(units)
        firm.property_tax_rate += 0.005 * units
        completed.append(project)
        _event(economy, "completed", project)
        del _projects(economy)[fid]
    return completed


def cancel_payment_projects_for_exit(economy, firm_or_id):
    """A provider exit loses pending units; paid construction is sunk."""
    fid = int(getattr(firm_or_id, "firm_id", firm_or_id))
    project = _projects(economy).pop(fid, None)
    if project is not None:
        _event(economy, "cancelled", project)
    return project
