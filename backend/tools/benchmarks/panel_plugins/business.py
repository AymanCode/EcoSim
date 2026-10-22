"""Business columns readable from current firm state.

Per-category debt, loan tests, and skill-weighted labour stay in the business
mechanism PRs. This file is read-only and uses no RNG.
"""

from __future__ import annotations

from typing import Any


def _count(firms: list[Any], category: str, *, private: bool) -> float:
    return float(sum(
        1 for firm in firms
        if firm.good_category == category and (not bool(getattr(firm, "is_baseline", False))) == private
    ))


def extra_metrics(economy: Any) -> dict[str, float | None]:
    firms = list(economy.firms)
    markups = [float(firm.markup) for firm in firms if not bool(getattr(firm, "is_baseline", False))]
    food_prices = [
        float(firm.price) for firm in firms
        if firm.good_category == "Food" and float(getattr(firm, "price", 0.0) or 0.0) > 0.0
    ]
    return {
        "private_food_firms": _count(firms, "Food", private=True),
        "legacy_food_firms": _count(firms, "Food", private=False),
        "private_services_firms": _count(firms, "Services", private=True),
        "legacy_services_firms": _count(firms, "Services", private=False),
        "mean_private_markup": (sum(markups) / len(markups)) if markups else None,
        "mean_food_posted_price": (sum(food_prices) / len(food_prices)) if food_prices else None,
    }


METRICS = {
    "private_food_firms": ("Private Food firms", "firms", ("mean",), None),
    "legacy_food_firms": ("Legacy Food firms", "firms", ("mean",), None),
    "private_services_firms": ("Private Services firms", "firms", ("mean",), None),
    "legacy_services_firms": ("Legacy Services firms", "firms", ("mean",), None),
    "mean_private_markup": ("Mean private markup", "fraction", ("mean",), None),
    "mean_food_posted_price": ("Mean Food posted price", "$", ("mean",), (0.0, None)),
}


def summarize(runs: list[dict]) -> dict[str, Any]:
    return {"metrics": list(METRICS), "runs": len(runs)}
