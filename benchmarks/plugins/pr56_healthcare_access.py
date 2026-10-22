"""#56 household-access metrics for the #58 panel: what the clinic's price does to patients.

Read after each tick; nothing is changed. Counters are this tick's values:
``healthcare_*_this_tick`` are reset in ``Economy._reset_healthcare_tick_state``
and ``payment_care_*_this_tick`` in ``payment_sectors`` (payment sequences
only; 0 on legacy). Medical debt is ``HouseholdAgent.medical_loan_remaining``.
"""


def _f(obj, name):
    return float(getattr(obj, name, 0.0) or 0.0)


def extra_metrics(economy):
    households = list(getattr(economy, "households", []) or [])
    in_debt = [h for h in households if _f(h, "medical_loan_remaining") > 1e-9]
    clinics = [f for f in economy._healthcare_firms()] if hasattr(economy, "_healthcare_firms") else []
    prices = [_f(f, "price") for f in clinics]
    return {
        "care_requests": _f(economy, "healthcare_requests_this_tick"),
        "care_visits_completed": _f(economy, "healthcare_completed_visits_this_tick"),
        "care_refused_unaffordable_legacy": _f(economy, "healthcare_affordability_rejects_this_tick"),
        "care_funding_denials_payment": _f(economy, "payment_care_funding_denials_this_tick"),
        "care_deferrals_payment": _f(economy, "payment_care_deferrals_this_tick"),
        "households_with_medical_debt": float(len(in_debt)),
        "medical_debt_total": sum(_f(h, "medical_loan_remaining") for h in in_debt),
        "clinic_price_mean": (sum(prices) / len(prices)) if prices else 0.0,
        "clinic_cash_total": sum(_f(f, "cash_balance") for f in clinics),
    }
