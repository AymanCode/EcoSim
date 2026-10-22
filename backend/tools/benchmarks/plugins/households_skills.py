"""#58 evidence-panel metrics plugin for #51 (skills wear-off with a week-1 floor).

extra_metrics(economy) is called after each tick. Read-only: it reads
household attributes and keeps its own week-1 record; it changes no model
state and draws no random numbers. Works on main (no skill_floor attribute).
"""
import numpy as np

_state = {}


def extra_metrics(economy):
    hh = economy.households
    key = id(economy)
    skills = np.fromiter((h.skills_level for h in hh), dtype=np.float64, count=len(hh))
    emp = np.fromiter((h.employer_id is not None for h in hh), dtype=bool, count=len(hh))
    st = _state.get(key)
    if st is None or len(st["start"]) != len(hh):
        start = skills.copy()
        st = _state[key] = {"start": start, "low": start < np.percentile(start, 25), "prev_emp": emp.copy()}
    start, low = st["start"], st["low"]
    hired = emp & ~st["prev_emp"]
    st["prev_emp"] = emp.copy()
    floors = np.array([np.nan if getattr(h, "skill_floor", None) is None else h.skill_floor for h in hh], dtype=np.float64)
    drift = skills - start
    out = {
        "skill_mean": float(skills.mean()),
        "skill_drift_mean": float(drift.mean()),
        "skill_drift_unemployed": float(drift[~emp].mean()) if (~emp).any() else 0.0,
        "skill_min": float(skills.min()),
        "below_week1_skill": float((skills < start - 1e-12).sum()),
        "below_floor": float(np.nansum(skills < floors - 1e-12)),
        "low_skill_employed_share": float(emp[low].mean()) if low.any() else 0.0,
        "low_skill_hires": float(hired[low].sum()),
        "jobless_over_52w_share": float(np.mean([(h.employer_id is None) and h.unemployment_duration > 52 for h in hh])),
    }
    return out
