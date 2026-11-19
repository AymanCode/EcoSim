"""Shared government policy action-space definitions.

This module is intentionally pure: it does not import GovernmentAgent,
Economy, or provider code. Runtime callers use these constants to keep the
LLM prompt, sanitizer, and GovernmentAgent validation in sync.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
from numbers import Number
from typing import Any, Dict, Iterable, List, Tuple


TAX_MAX_STEP: float = 0.05
MAX_SUBSTANTIVE_CHANGES: int = 2

TAX_LIMITS: Dict[str, Tuple[float, float]] = {
    "wage_tax_rate": (0.0, 0.50),
    "profit_tax_rate": (0.0, 0.50),
    "investment_tax_rate": (0.0, 0.30),
}

ORDERED_LEVERS: Dict[str, List[Any]] = {
    "benefit_level": ["low", "neutral", "high", "crisis"],
    "minimum_wage_policy": ["low", "neutral", "high"],
    "sector_subsidy_level": [0, 10, 25, 50],
    "infrastructure_spending": ["none", "low", "medium", "high"],
    "technology_spending": ["none", "low", "medium", "high"],
    "social_spending": ["none", "low", "medium", "high"],
    "price_stabilization_level": ["off", "monitor", "soft", "strict"],
    "rent_stabilization_level": ["off", "monitor", "soft", "strict"],
    "bailout_policy": ["off", "sector", "all"],
    "bailout_budget": [0, 5000, 10000, 25000, 50000],
}

SIMPLE_ENUM_LEVERS: Dict[str, set] = {
    "food_credit_policy": {"off", "on"},
    "public_works": {"off", "on"},
    "surplus_distribution": {"off", "on"},
    "sector_subsidy_target": {"none", "food", "housing", "services", "healthcare"},
    "price_stabilization_target": {"none", "food", "services", "healthcare"},
    "bailout_target": {"none", "food", "housing", "services", "healthcare"},
}

SPENDING_LEVERS = {
    "food_credit_policy",
    "food_credit_weekly_budget",
    "benefit_level",
    "public_works",
    "surplus_distribution",
    "sector_subsidy_level",
    "infrastructure_spending",
    "technology_spending",
    "social_spending",
    "bailout_policy",
    "bailout_budget",
}

PROMPT_POLICY_LEVERS: Tuple[str, ...] = (
    "wage_tax_rate",
    "profit_tax_rate",
    "investment_tax_rate",
    "benefit_level",
    "public_works",
    "surplus_distribution",
    "minimum_wage_policy",
    "food_credit_policy",
    "food_credit_weekly_budget",
    "sector_subsidy_target",
    "sector_subsidy_level",
    "price_stabilization_target",
    "price_stabilization_level",
    "rent_stabilization_level",
    "infrastructure_spending",
    "technology_spending",
    "social_spending",
    "bailout_policy",
    "bailout_target",
    "bailout_budget",
)

POLICY_SCHEMA: Dict[str, Any] = {
    **{lever: {"type": "float", "min": lo, "max": hi, "max_step": TAX_MAX_STEP}
       for lever, (lo, hi) in TAX_LIMITS.items()},
    **{lever: list(values) for lever, values in ORDERED_LEVERS.items()},
    **{lever: sorted(values) for lever, values in SIMPLE_ENUM_LEVERS.items()},
    "food_credit_weekly_budget": {"type": "currency", "min": 0.0, "precision": 0.01},
}

VALID_LEVERS = set(POLICY_SCHEMA)

POLICY_GROUPS: Dict[str, Tuple[str, ...]] = {
    "price_stabilization": ("price_stabilization_target", "price_stabilization_level"),
    "rent_stabilization": ("rent_stabilization_level",),
    "bailout": ("bailout_policy", "bailout_target", "bailout_budget"),
    "sector_subsidy": ("sector_subsidy_target", "sector_subsidy_level"),
}

LEVER_TO_GROUP: Dict[str, str] = {
    lever: group
    for group, levers in POLICY_GROUPS.items()
    for lever in levers
}


def normalize_food_credit_budget(value: Any) -> float:
    """Validate a nonnegative dollar amount to cents and return its float form.

    Small floating-point arithmetic noise around an exact cent is normalized;
    actual fractions of a cent and values lost when converted to float are not.
    """

    message = "food_credit_weekly_budget must be a nonnegative finite number in whole cents"
    if isinstance(value, bool) or not isinstance(value, Number):
        raise ValueError(message)
    try:
        amount = Decimal(str(value))
        number = float(value)
    except (InvalidOperation, TypeError, ValueError, OverflowError):
        raise ValueError(message) from None
    if not amount.is_finite() or amount < 0 or not math.isfinite(number):
        raise ValueError(message)
    normalized = round(number, 2)
    if amount != Decimal(str(normalized)):
        if (not isinstance(value, float) or normalized == 0.0
                or abs(number - normalized) > 2 * math.ulp(number)):
            raise ValueError(message)
    return 0.0 if normalized == 0 else normalized


def normalize_current_policy(current_policy: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize action-space policy values from runtime or audit snapshots."""

    p = dict(current_policy or {})

    if "public_works" not in p and "public_works_toggle" in p:
        p["public_works"] = p["public_works_toggle"]

    for lever in ("sector_subsidy_level", "bailout_budget"):
        if lever in p:
            try:
                p[lever] = int(float(p[lever]))
            except (TypeError, ValueError):
                pass

    for lever in TAX_LIMITS:
        if lever in p:
            try:
                p[lever] = float(p[lever])
            except (TypeError, ValueError):
                pass

    if "food_credit_weekly_budget" in p:
        try:
            p["food_credit_weekly_budget"] = normalize_food_credit_budget(p["food_credit_weekly_budget"])
        except ValueError:
            pass

    return p


def is_ordered_increase(lever: str, current: Any, proposed: Any) -> bool:
    """Return whether an ordered lever moves upward."""

    order = ORDERED_LEVERS.get(lever)
    if not order or current not in order or proposed not in order:
        return False
    return order.index(proposed) > order.index(current)


def is_spending_increase(lever: str, current: Any, proposed: Any) -> bool:
    """Return whether a proposed lever change increases discretionary spending."""

    if lever in {"public_works", "surplus_distribution", "food_credit_policy"}:
        return current == "off" and proposed == "on"
    if lever == "food_credit_weekly_budget":
        try:
            return normalize_food_credit_budget(proposed) > normalize_food_credit_budget(current)
        except ValueError:
            return False
    if lever in ORDERED_LEVERS:
        return is_ordered_increase(lever, current, proposed)
    return False


def is_tax_decrease(lever: str, current: Any, proposed: Any) -> bool:
    """Return whether a tax lever moves downward."""

    if lever not in TAX_LIMITS:
        return False
    try:
        return float(proposed) < float(current)
    except (TypeError, ValueError):
        return False


def policy_value_set(lever: str) -> Iterable[Any]:
    """Return valid values for a discrete lever."""

    if lever in ORDERED_LEVERS:
        return ORDERED_LEVERS[lever]
    return SIMPLE_ENUM_LEVERS.get(lever, set())


def render_policy_schema_for_prompt(*, include_food_credit: bool = True) -> str:
    """Render the runtime government policy schema for the LLM prompt."""

    lines: List[str] = []
    for lever in PROMPT_POLICY_LEVERS:
        if lever in {"food_credit_policy", "food_credit_weekly_budget"} and not include_food_credit:
            continue
        schema = POLICY_SCHEMA[lever]
        if isinstance(schema, dict) and schema.get("type") == "currency":
            lines.append(f"- {lever}: nonnegative dollar amount in whole cents; no upper limit")
        elif isinstance(schema, dict) and schema.get("type") == "float":
            lines.append(
                f"- {lever}: float [{schema['min']:.2f}, {schema['max']:.2f}], "
                f"max change {schema['max_step']:.2f} per decision"
            )
        else:
            values = " | ".join(str(value) for value in schema)
            kind = "ordered enum" if lever in ORDERED_LEVERS else "enum"
            lines.append(f"- {lever}: {kind} [{values}]")
    return "\n".join(lines)
