"""Household columns that the core panel does not already report.

Read-only: ``extra_metrics`` must not write state and must not draw random numbers.
Consumption and skill here are observed household fields, not a new model.
"""

from __future__ import annotations

from typing import Any


def extra_metrics(economy: Any) -> dict[str, float | None]:
    households = list(economy.households)
    count = len(households)
    if count == 0:
        return {
            "negative_cash_share": 0.0,
            "consumption_per_household": 0.0,
            "consumption_income_ratio": None,
            "mean_skill": 0.0,
        }
    negative_cash = 0
    consumption = 0.0
    wage_income = 0.0
    skill = 0.0
    for household in households:
        if float(household.cash_balance) < 0.0:
            negative_cash += 1
        consumption += float(getattr(household, "last_consumption_spending", 0.0) or 0.0)
        if household.is_employed:
            wage_income += float(household.wage)
        skill += float(getattr(household, "skills_level", 0.0) or 0.0)
    return {
        "negative_cash_share": negative_cash / count,
        "consumption_per_household": consumption / count,
        "consumption_income_ratio": (consumption / wage_income) if wage_income > 0.0 else None,
        "mean_skill": skill / count,
    }


# name -> (label, unit, aggregations, bounds or None). Shares are fractions; unit "%" scales them.
METRICS = {
    "negative_cash_share": ("Households with negative cash", "%", ("mean", "max"), (0.0, 1.0)),
    "consumption_per_household": ("Consumption per household", "$/wk", ("mean",), None),
    "consumption_income_ratio": ("Consumption / wage income", "ratio", ("mean",), None),
    "mean_skill": ("Mean skill", "index", ("mean",), None),
}


def summarize(runs: list[dict]) -> dict[str, Any]:
    return {"metrics": list(METRICS), "runs": len(runs)}
