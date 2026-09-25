"""Validate a whole policy lever vector against the shared policy schema.

Used for SETUP's initial_policy and, in the lean frame profile, for the merged
state after a runtime CONFIG. Pure: imports only policy_schema.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from policy_schema import ORDERED_LEVERS, SIMPLE_ENUM_LEVERS, TAX_LIMITS, VALID_LEVERS

BAILOUT_SECTORS = frozenset(SIMPLE_ENUM_LEVERS["bailout_target"]) - {"none"}


class PolicyVectorError(ValueError):
    """A lever vector that does not fit the schema; ``group`` names a broken group rule (see POLICY_GROUPS)."""

    def __init__(self, message: str, *, group: Optional[str] = None) -> None:
        super().__init__(message)
        self.group = group


def _coerce_ordered(lever: str, value: Any) -> Any:
    allowed = ORDERED_LEVERS[lever]
    if all(isinstance(option, int) for option in allowed):
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            raise PolicyVectorError(f"{lever} must be one of {allowed}, got {value!r}")
        if not math.isfinite(numeric):
            raise PolicyVectorError(f"{lever} must be one of {allowed}, got {value!r}")
        value = int(numeric)
    if value not in allowed:
        raise PolicyVectorError(f"{lever} must be one of {allowed}, got {value!r}")
    return value


def validate_lever_value(lever: str, value: Any) -> Any:
    """Return the canonical value of one lever, ignoring group rules, or raise PolicyVectorError."""
    if lever not in VALID_LEVERS:
        raise PolicyVectorError(f"unknown lever {lever!r}")
    if lever in TAX_LIMITS:
        low, high = TAX_LIMITS[lever]
        try:
            numeric = round(float(value), 4)
        except (TypeError, ValueError, OverflowError):
            raise PolicyVectorError(f"{lever} must be a number between {low} and {high}, got {value!r}")
        if not math.isfinite(numeric) or not low <= numeric <= high:
            raise PolicyVectorError(f"{lever} must be between {low} and {high}, got {numeric}")
        return numeric
    if lever in ORDERED_LEVERS:
        return _coerce_ordered(lever, value)
    if not isinstance(value, str) or value not in SIMPLE_ENUM_LEVERS[lever]:
        raise PolicyVectorError(f"{lever} must be one of {sorted(SIMPLE_ENUM_LEVERS[lever])}, got {value!r}")
    return value


def policy_group_errors(vector: Dict[str, Any]) -> Dict[str, str]:
    """Return ``{group: rule text}`` for every group rule a canonical *vector* breaks, in checking order."""
    errors: Dict[str, str] = {}
    level = vector.get("sector_subsidy_level", 0)
    if level and vector.get("sector_subsidy_target", "none") == "none":
        errors["sector_subsidy"] = "sector_subsidy_level above 0 needs a sector_subsidy_target other than 'none'"
    # The AI mayor's rule (llm_government.py CONSISTENCY RULES): off lends nothing, sector names
    # one sector, all names none; sector and all need a budget. Target rule first, then budget.
    bailout_policy = vector.get("bailout_policy", "off")
    bailout_target = vector.get("bailout_target", "none")
    bailout_budget = vector.get("bailout_budget", 0)
    if bailout_policy == "off":
        if bailout_target != "none":
            errors["bailout"] = "bailout_policy 'off' lends nothing, so bailout_target must be 'none'"
        elif bailout_budget:
            errors["bailout"] = "bailout_policy 'off' lends nothing, so bailout_budget must be 0"
    elif bailout_policy == "sector":
        if bailout_target not in BAILOUT_SECTORS:
            errors["bailout"] = "bailout_policy 'sector' needs a bailout_target of food, housing, services or healthcare"
        elif not bailout_budget:
            errors["bailout"] = "bailout_policy 'sector' needs a bailout_budget above 0"
    elif bailout_policy == "all":
        if bailout_target != "none":
            errors["bailout"] = "bailout_policy 'all' covers every sector, so bailout_target must be 'none'"
        elif not bailout_budget:
            errors["bailout"] = "bailout_policy 'all' needs a bailout_budget above 0"
    return errors


def validate_policy_vector(vector: Dict[str, Any]) -> Dict[str, Any]:
    """Return a canonical copy of *vector* or raise PolicyVectorError (with ``group`` set for a group rule)."""
    result = {lever: validate_lever_value(lever, value) for lever, value in (vector or {}).items()}
    errors = policy_group_errors(result)
    if errors:
        group, rule = next(iter(errors.items()))
        raise PolicyVectorError(rule, group=group)
    return result
