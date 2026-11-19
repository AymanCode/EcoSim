"""Weekly cost of a household's essentials: minimum food plus rent.

Household money thresholds can be expressed as a number of weeks of this cost
(AUD-005 in PRESUMPTIONS.md) so they move with prices and with the household's
own rent instead of staying fixed in currency.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Iterable, Optional

import numpy as np


def _positive_prices(firms: Iterable, category: str) -> list[float]:
    prices = []
    for firm in firms:
        if (getattr(firm, "good_category", "") or "").lower() != category:
            continue
        price = float(getattr(firm, "price", 0.0) or 0.0)
        if price > 0.0 and math.isfinite(price):
            prices.append(price)
    return prices


def food_reference_price(economy) -> float:
    """Median posted price among Food sellers with a positive finite price (0.0 if none)."""
    prices = _positive_prices(economy.firms, "food")
    return float(median(prices)) if prices else 0.0


def rent_reference_price(economy) -> float:
    """Median posted rent among Housing firms with a positive finite price (0.0 if none)."""
    prices = _positive_prices(economy.firms, "housing")
    return float(median(prices)) if prices else 0.0


def essential_weekly_costs(economy, households: Optional[list] = None) -> np.ndarray:
    """Per-household weekly essentials: min_food_per_tick x food reference price + weekly rent.

    Rent is the household's contract rent (``monthly_rent``, a weekly amount) while it
    rents, otherwise the median posted rent. Values are floored at 1e-6 so callers can
    divide by them; a caller should treat a cost <= 1e-6 as "no price signal".
    """
    households = economy.households if households is None else households
    food = food_reference_price(economy)
    rent_ref = rent_reference_price(economy)
    costs = np.fromiter(
        (
            max(0.0, float(h.min_food_per_tick)) * food
            + (max(0.0, float(h.monthly_rent)) if h.renting_from_firm_id is not None else rent_ref)
            for h in households
        ),
        dtype=np.float64,
        count=len(households),
    )
    return np.maximum(costs, 1e-6)
