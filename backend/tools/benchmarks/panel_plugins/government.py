"""Government columns readable from the current treasury.

Public debt, interest, and approved-versus-spent program totals land with the
government mechanism PRs. Bond buys stay on the core K06 column. Read-only, no RNG.
"""

from __future__ import annotations

from typing import Any


def extra_metrics(economy: Any) -> dict[str, float | None]:
    government = economy.government
    return {
        "gov_last_revenue": float(getattr(government, "last_tick_revenue", 0.0) or 0.0),
        "gov_last_spending": float(getattr(government, "last_tick_spending", 0.0) or 0.0),
        "fiscal_pressure": float(getattr(government, "fiscal_pressure", 0.0) or 0.0),
        "unemployment_benefit": float(government.unemployment_benefit_level),
        "misc_pool": float(getattr(economy, "misc_firm_revenue", 0.0) or 0.0),
    }


METRICS = {
    "gov_last_revenue": ("Government revenue last tick", "$/wk", ("mean", "min"), None),
    "gov_last_spending": ("Government spending last tick", "$/wk", ("mean", "min"), None),
    "fiscal_pressure": ("Fiscal pressure", "index", ("mean",), None),
    "unemployment_benefit": ("Unemployment benefit", "$/wk", ("mean",), None),
    "misc_pool": ("Misc pool balance (K06 stock)", "$", ("mean", "min"), None),
}


def summarize(runs: list[dict]) -> dict[str, Any]:
    return {"metrics": list(METRICS), "runs": len(runs)}
