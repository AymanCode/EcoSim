"""#58 evidence-panel metrics plugin for the food-first healthcare reserve.

extra_metrics(economy) is called after each tick. Read-only: reads household
and firm attributes only (no healthcare-quote getter, so main and the
flag-off arm emit the same columns and the panel's identity check stays
valid). Draws no random numbers. Works on main.
"""
import numpy as np

try:
    from tools.runners.run_large_simulation import _food_security_ratio
except ImportError:  # pragma: no cover
    _food_security_ratio = None


def extra_metrics(economy):
    hh = economy.households
    n = len(hh)
    queued = np.fromiter((h.queued_healthcare_firm_id is not None for h in hh), dtype=bool, count=n)
    cash = np.fromiter((h.cash_balance for h in hh), dtype=np.float64, count=n)
    served = np.fromiter((float(getattr(h, "last_healthcare_units", 0.0)) > 0 for h in hh), dtype=bool, count=n)
    loans = np.fromiter((float(getattr(h, "medical_loan_remaining", 0.0)) > 0 for h in hh), dtype=bool, count=n)
    out = {
        "queued_households": float(queued.sum()),
        "visits_served": float(served.sum()),
        "households_with_medical_loan": float(loans.sum()),
        "overdrafts_all": float((cash < -1e-9).sum()),
        "overdrafts_queued": float((cash[queued] < -1e-9).sum()),
        "overdraft_dollars_queued": float(-cash[queued][cash[queued] < 0].sum()) if queued.any() else 0.0,
    }
    if _food_security_ratio is not None:
        food = np.array([_food_security_ratio(h) for h in hh], dtype=np.float64)
        short = food < 0.999
        out["queued_short_of_min_food_share"] = float(short[queued].mean()) if queued.any() else 0.0
        out["unqueued_short_of_min_food_share"] = float(short[~queued].mean()) if (~queued).any() else 0.0
    return out
