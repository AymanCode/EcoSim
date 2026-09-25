"""Curated newcomer-facing metrics and the full firm list for the tick frame.

Everything here is computed fresh from the economy each tick, O(households + firms),
except Gini and the wealth percentiles, which come from get_economic_metrics()
and carry the tick they were computed on.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional

SECTORS = ("Food", "Housing", "Services", "Healthcare")
SECTOR_KEYS = {"Food": "priceFood", "Housing": "priceHousing", "Services": "priceServices", "Healthcare": "priceHealthcare"}


def firm_state(firm: Any) -> str:
    cash = float(getattr(firm, "cash_balance", 0.0) or 0.0)
    if (cash <= 0.0 or getattr(firm, "burn_mode", False) or getattr(firm, "survival_mode", False)
            or int(getattr(firm, "zero_cash_streak", 0) or 0) > 2):
        return "struggling"
    if int(getattr(firm, "planned_hires_count", 0) or 0) > 0:
        return "growing"
    return "steady"


def build_firm_list(economy: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for firm in getattr(economy, "firms", []) or []:
        rows.append({
            "id": int(firm.firm_id),
            "name": str(firm.good_name),
            "sector": str(getattr(firm, "good_category", "") or ""),
            "cash": float(firm.cash_balance),
            "staff": len(getattr(firm, "employees", []) or []),
            "price": float(getattr(firm, "price", 0.0) or 0.0),
            "lastRevenue": float(getattr(firm, "last_revenue", 0.0) or 0.0),
            "lastProfit": float(getattr(firm, "last_profit", 0.0) or 0.0),
            "state": firm_state(firm),
            "isBaseline": bool(getattr(firm, "is_baseline", False)),
        })
    rows.sort(key=lambda row: row["cash"], reverse=True)
    return rows


def sector_mean_prices(economy: Any) -> Dict[str, Optional[float]]:
    totals: Dict[str, List[float]] = {sector: [] for sector in SECTORS}
    for firm in getattr(economy, "firms", []) or []:
        sector = str(getattr(firm, "good_category", "") or "")
        if sector in totals:
            totals[sector].append(float(getattr(firm, "price", 0.0) or 0.0))
    return {sector: (sum(values) / len(values) if values else None) for sector, values in totals.items()}


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_curated_metrics(*, economy: Any, econ_metrics: Dict[str, Any], tick: int, wealth_as_of_tick: int) -> Dict[str, Any]:
    households = list(getattr(economy, "households", []) or [])
    firms = list(getattr(economy, "firms", []) or [])
    can_work = [h for h in households if getattr(h, "can_work", True)]
    unemployed = [h for h in can_work if getattr(h, "employer_id", None) is None]
    wages = [float(h.wage) for h in households if getattr(h, "employer_id", None) is not None]
    food_spend = [float(getattr(h, "last_food_spend", 0.0) or 0.0) for h in households]
    states = [firm_state(f) for f in firms]
    bank = getattr(economy, "bank", None)
    payment = econ_metrics.get("payment") if isinstance(econ_metrics.get("payment"), dict) else None
    defaults_total = payment["loans"].get("defaults_total") if payment and isinstance(payment.get("loans"), dict) else None
    health = getattr(economy, "last_health_diagnostics", None) or {}

    curated: Dict[str, Any] = {
        "householdsTotal": len(households),
        "peopleOutOfWorkPer100": (100.0 * len(unemployed) / len(can_work)) if can_work else 0.0,
        "typicalWeeklyPay": float(statistics.median(wages)) if wages else 0.0,
        "foodSpendPerHousehold": (sum(food_spend) / len(food_spend)) if food_spend else 0.0,
        "gini": _num(econ_metrics.get("gini_coefficient")),
        "wealthP10": _num(econ_metrics.get("wealth_p10")),
        "wealthP50": _num(econ_metrics.get("wealth_p50")),
        "wealthP90": _num(econ_metrics.get("wealth_p90")),
        "wealthAsOfTick": int(wealth_as_of_tick),
        "townHallCash": float(economy.government.cash_balance),
        "homelessHouseholds": _num((getattr(economy, "last_housing_diagnostics", {}) or {}).get("homeless_household_count", 0.0)),
        "careDenials": _num(health["healthcare_denied_count"]) if "healthcare_denied_count" in health else None,
        "firmsOpen": len(firms),
        "firmsStruggling": states.count("struggling"),
        "firmsGrowing": states.count("growing"),
        "firmsSteady": states.count("steady"),
        "bankActiveLoans": len(getattr(bank, "active_loans", []) or []) if bank is not None else None,
        "bankDefaultAmountThisTick": _num(getattr(bank, "last_tick_defaults", None)) if bank is not None else None,
        "bankDefaultsTotal": int(defaults_total) if defaults_total is not None else None,
        "publicWorksJobs": sum(len(getattr(f, "employees", []) or []) for f in firms
                               if str(getattr(f, "good_category", "")).lower() == "publicworks"),
    }
    for sector, price in sector_mean_prices(economy).items():
        curated[SECTOR_KEYS[sector]] = price
    return curated
