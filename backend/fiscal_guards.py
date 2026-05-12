"""Fiscal guard helpers for government policy execution.

Helpers in this module are deliberately economy-agnostic: they inspect object
attributes but do not import Economy or GovernmentAgent.
"""

from __future__ import annotations

from typing import Any, Iterable

from config import CONFIG


GDP_KEYS = ("gdp", "gdp_this_tick", "market_gdp", "market_gdp_this_tick")


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def trailing_gdp(economy: Any) -> float:
    """Return a recent GDP estimate with population-scaled fallback."""

    for row in reversed(list(getattr(economy, "metrics_history", []) or [])):
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        for key in GDP_KEYS:
            value = _to_float(metrics.get(key), 0.0)
            if value > 0.0:
                return value

    last_revenue = sum(_to_float(v, 0.0) for v in getattr(economy, "last_tick_revenue", {}).values())
    if last_revenue > 0.0:
        return float(last_revenue)

    households = len(getattr(economy, "households", []) or [])
    return max(1.0, households * 25.0)


def annualized_debt_to_gdp(government: Any, recent_gdp: float) -> float:
    """Debt/GDP using annualized tick GDP and public_debt when available."""

    public_debt = _to_float(getattr(government, "public_debt", 0.0), 0.0)
    ticks_per_year = max(1, int(getattr(CONFIG.time, "ticks_per_year", 52)))
    annualized_gdp = max(1.0, _to_float(recent_gdp, 0.0) * ticks_per_year)
    return public_debt / annualized_gdp


def fiscal_reserve_floor(recent_gdp: float) -> float:
    """Treasury reserve required after major discretionary startup spending."""

    return max(50_000.0, 5.0 * max(_to_float(recent_gdp, 0.0), 1.0))


def has_public_works_firm(firms: Iterable[Any]) -> bool:
    """Return True when a PublicWorks firm already exists."""

    return any((getattr(firm, "good_category", "") or "") == "PublicWorks" for firm in (firms or []))


def public_works_full_startup_cost() -> float:
    """Configured startup capitalization for creating the first PublicWorks firm."""

    return float(CONFIG.government.public_works_job_fraction) * 1_000_000.0


def projected_public_works_startup_cost(firms: Iterable[Any]) -> float:
    """Startup cost still needed before public works can operate."""

    if has_public_works_firm(firms):
        return 0.0
    return public_works_full_startup_cost()


def public_works_affordable_budget(government: Any, recent_gdp: float) -> float:
    """Cash available above the reserve floor for public works startup."""

    cash = _to_float(getattr(government, "cash_balance", 0.0), 0.0)
    return max(0.0, cash - fiscal_reserve_floor(recent_gdp))


def can_fund_public_works_startup(government: Any, recent_gdp: float, firms: Iterable[Any]) -> bool:
    """Return whether the treasury can fund startup and keep the reserve floor."""

    startup_cost = projected_public_works_startup_cost(firms)
    return public_works_affordable_budget(government, recent_gdp) >= startup_cost


def get_sector_subsidy_cap(government: Any, recent_gdp: float) -> float:
    """Maximum government subsidy payout allowed for one tick."""

    cash = _to_float(getattr(government, "cash_balance", 0.0), 0.0)
    if cash <= 0.0:
        return 0.0
    return min(0.05 * max(_to_float(recent_gdp, 0.0), 1.0), 0.02 * max(cash, 0.0))
