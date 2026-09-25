"""Read-only outcome snapshot for the versioned payment scenario.

The frame reports settled amounts and live claims from their owners.  It never
infers payments from contracts or exposes private policy state as an outcome.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def payment_snapshot(economy: Any) -> dict:
    """Return one source-derived, JSON-safe payment diagnostic frame.

    Work is bounded by the households, active registered loans, and the
    already-indexed tick records.  Calling this function does not settle cash,
    accrue interest, or change a contract.
    """
    config = getattr(economy, "config", None)
    state = getattr(economy, "payment_state", {}) or {}
    book = getattr(economy, "payment_book", None)
    parameters = dict(getattr(economy, "payment_config_snapshot", {}) or {})
    if not parameters and config is not None:
        parameters = {
            name: value for name, value in vars(config).items()
            if name.startswith("payment_") and isinstance(value, (str, int, float, bool))
        }
    sequence = getattr(economy, "payment_sequence", parameters.get("payment_sequence", "legacy"))
    care_mode = getattr(economy, "payment_care_mode", parameters.get("payment_care_mode", "patient_pay"))
    assistance = getattr(economy, "payment_assistance", parameters.get("payment_assistance", "reserve"))
    if sequence == "legacy" or book is None:
        return {
            "scenario": {"timing": sequence, "care": care_mode, "assistance": assistance},
            "parameters": parameters,
            "coverage": "legacy_sequence_no_payment_book",
        }

    paid_income = getattr(book, "paid_income", {})
    income = {
        key: sum(float(row.get(field, 0.0)) for row in paid_income.values())
        for key, field in (("ordinary_gross", "gross"), ("ordinary_net", "net"),
                           ("ordinary_tax", "tax"), ("benefits_paid", "benefit"),
                           ("ceo_paid", "ceo"))
    }
    income["benefits_denied"] = float(getattr(book, "denied_benefits", 0.0))
    income["unpaid_employed_count"] = len(getattr(book, "unpaid_employed", {}))
    income["unpaid_employed_shortfall"] = sum(
        float(row.get("shortfall", 0.0)) for row in getattr(book, "unpaid_employed", {}).values()
    )
    wage_claims = state.get("wage_claims", {})
    income["wage_claim_count"] = len(wage_claims)
    income["wage_claim_outstanding"] = sum(float(value) for value in wage_claims.values())

    rent_detail = getattr(book, "rent_detail", {})
    rent = {
        "current_paid": sum(float(row.get("current", 0.0)) for row in rent_detail.values()),
        "arrears_paid": sum(float(row.get("arrears", 0.0)) for row in rent_detail.values()),
        "relief_paid": sum(float(row.get("relief", 0.0)) for row in rent_detail.values()),
        "evictions_this_tick": int((getattr(economy, "last_housing_diagnostics", {}) or {}).get("eviction_count", 0)),
    }
    rent_arrears = 0.0
    rent_arrears_households = 0
    for household in economy.households:
        arrears = max(0.0, float(getattr(household, "rent_arrears", 0.0)))
        rent_arrears += arrears
        rent_arrears_households += arrears > 0.0
    rent["arrears_outstanding"] = rent_arrears
    rent["households_in_arrears"] = rent_arrears_households

    due_ages = getattr(economy, "payment_care_due_ages", {}) or {}
    age_bins = Counter("0_3" if age <= 3 else "4_12" if age <= 12 else "13_51" if age <= 51 else "52_plus"
                       for age in due_ages.values())
    care = {
        "completed_visits": float(getattr(economy, "healthcare_completed_visits_this_tick", 0.0)),
        "consent_or_budget_deferrals": int(getattr(economy, "payment_care_deferrals_this_tick", 0)),
        "funding_denials": int(getattr(economy, "payment_care_funding_denials_this_tick", 0)),
        "physical_waits": int(getattr(economy, "payment_care_physical_waits_this_tick", 0)),
        "due_age_buckets": {name: int(age_bins.get(name, 0)) for name in ("0_3", "4_12", "13_51", "52_plus")},
        "due_age_255_plus": int(getattr(economy, "payment_care_due_age_255_plus", 0)),
    }

    restrictions = state.get("restrictions", {})
    fiscal = {
        "restricted_cash": {str(name): float(amount) for name, amount in restrictions.items()},
        "total_restricted_cash": sum(float(amount) for amount in restrictions.values()),
    }

    loans = {"v1_active": 0, "v2_active": 0, "v1_outstanding": 0.0, "v2_outstanding": 0.0,
             "v2_missed_claims": 0, "defaults_total": int(state.get("loan_default_history_total", 0)),
             "defaults_retained": len(state.get("loan_default_history", ())),
             "cooldown_active": 0,
             "new_annual_quote_shift": float(parameters.get("payment_annual_quote_shift", 0.0))}
    bank = getattr(economy, "bank", None)
    if bank is not None:
        for loan in bank.active_loans:
            version = int(loan.get("contract_version", 1))
            if version == 2:
                balance = float(loan.get("principal_remaining", 0.0)) + float(loan.get("accrued_interest", 0.0))
            else:
                balance = float(loan.get("remaining", 0.0))
            if balance <= 0:
                continue
            loans[f"v{version}_active"] += 1
            loans[f"v{version}_outstanding"] += balance
            if version == 2 and loan.get("missed_payments", 0) > 0:
                loans["v2_missed_claims"] += 1
    tick = int(getattr(economy, "current_tick", 0))
    loans["cooldown_active"] = sum(
        int(int(until) > tick) for until in state.get("loan_credit_cooldown_until", {}).values()
    )

    housing_projects = state.get("housing_projects", {})
    service_project = state.get("services_project")
    projects = {
        "housing_active": len(housing_projects),
        "housing_by_status": dict(Counter(str(project.get("status", "active")) for project in housing_projects.values())),
        "services_active": bool(service_project and service_project.get("status") in ("authorized", "assigned")),
        "services_status": str(service_project.get("status", "none")) if service_project else "none",
        "services_payables": sum(float(value) for value in state.get("services_project_payables", {}).values()),
    }
    return {
        "scenario": {"timing": sequence, "care": care_mode, "assistance": assistance},
        "parameters": parameters,
        "coverage": "settled_tick_and_live_claims",
        "income": income, "rent": rent, "care": care, "fiscal": fiscal,
        "loans": loans, "projects": projects,
    }
