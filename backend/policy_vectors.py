"""Validate a whole policy lever vector against the shared policy schema.

Used for SETUP's initial_policy and for the merged state after a runtime
CONFIG. Pure: imports only policy_schema.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from policy_schema import ORDERED_LEVERS, SIMPLE_ENUM_LEVERS, TAX_LIMITS, VALID_LEVERS


class PolicyVectorError(ValueError):
    """A lever vector that does not fit the schema."""


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


def validate_policy_vector(vector: Dict[str, Any]) -> Dict[str, Any]:
    """Return a canonical copy of *vector* or raise PolicyVectorError."""
    result = {lever: validate_lever_value(lever, value) for lever, value in (vector or {}).items()}

    level = result.get("sector_subsidy_level", 0)
    if level and result.get("sector_subsidy_target", "none") == "none":
        raise PolicyVectorError("sector_subsidy_level above 0 needs a sector_subsidy_target other than 'none'")
    if result.get("bailout_policy", "off") != "off":
        if result.get("bailout_target", "none") == "none":
            raise PolicyVectorError("bailout_policy needs a bailout_target other than 'none'")
        if not result.get("bailout_budget", 0):
            raise PolicyVectorError("bailout_policy needs a bailout_budget above 0")
    return result
