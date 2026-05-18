"""Frozen V1 policy forecasting configuration.

This module is intentionally self-contained. It mirrors the frozen schema
without importing or modifying backend code. Runtime drivers may use these
values to call the simulator's public government lever API.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


K_CASH_STRESS: int = 4
FOOD_INSECURITY_WINDOW: int = 8
HORIZON_TICKS: int = 8
CONFIRM_SEEDS: tuple[int, ...] = tuple(range(24))
SMOKE_SEEDS_2K: tuple[int, ...] = tuple(range(4))

POLICY_STATE_COLUMNS: tuple[str, ...] = (
    "wage_tax_rate",
    "profit_tax_rate",
    "investment_tax_rate",
    "benefit_level",
    "public_works",
    "minimum_wage_policy",
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

CATEGORICAL_POLICY_COLUMNS: tuple[str, ...] = (
    "benefit_level",
    "public_works",
    "minimum_wage_policy",
    "sector_subsidy_target",
    "price_stabilization_target",
    "price_stabilization_level",
    "rent_stabilization_level",
    "infrastructure_spending",
    "technology_spending",
    "social_spending",
    "bailout_policy",
    "bailout_target",
)

NUMERIC_POLICY_COLUMNS: tuple[str, ...] = tuple(
    column for column in POLICY_STATE_COLUMNS if column not in CATEGORICAL_POLICY_COLUMNS
)

BASELINE_LEVERS: dict[str, Any] = {
    "wage_tax_rate": 0.15,
    "profit_tax_rate": 0.20,
    "investment_tax_rate": 0.10,
    "benefit_level": "neutral",
    "public_works": "off",
    "minimum_wage_policy": "neutral",
    "sector_subsidy_target": "none",
    "sector_subsidy_level": 0,
    "price_stabilization_target": "none",
    "price_stabilization_level": "off",
    "rent_stabilization_level": "off",
    "infrastructure_spending": "none",
    "technology_spending": "none",
    "social_spending": "medium",
    "bailout_policy": "off",
    "bailout_target": "none",
    "bailout_budget": 0,
}

FROZEN_SECTORS: tuple[str, ...] = ("food", "housing", "services", "healthcare")


@dataclass(frozen=True)
class PolicyArm:
    """One pre-registered policy arm."""

    arm_id: str
    levers: Mapping[str, Any]

    @property
    def resolved_levers(self) -> dict[str, Any]:
        """Return the baseline-resolved lever vector."""
        return resolve_levers(self.levers)

    @property
    def policy_canonical(self) -> str:
        """Return the stable canonical hash for this arm."""
        return canonical_policy_hash(self.levers)


FROZEN_ARMS: tuple[PolicyArm, ...] = (
    PolicyArm("baseline", {}),
    PolicyArm("wage_tax_high", {"wage_tax_rate": 0.30}),
    PolicyArm("profit_tax_high", {"profit_tax_rate": 0.35}),
    PolicyArm("benefit_high", {"benefit_level": "high"}),
    PolicyArm("min_wage_high", {"minimum_wage_policy": "high"}),
    PolicyArm("subsidy_food_25", {"sector_subsidy_target": "food", "sector_subsidy_level": 25}),
)

LABOR_FEATURES: tuple[str, ...] = (
    "unemployment_rate",
    "unemployment_ma4",
    "unemployment_ma8",
    "hires",
    "layoffs",
    "vacancies",
    "vacancy_fill_ratio",
    "wage_pressure_idx",
)

DEMAND_FEATURES_BASE: tuple[str, ...] = ("gdp", "agg_inventory", "price_index", "gdp_ma4")
DEMAND_FEATURES_SECTOR: tuple[str, ...] = tuple(
    item
    for sector in FROZEN_SECTORS
    for item in (f"sector_revenue_{sector}", f"sector_price_{sector}")
)

HOUSEHOLD_WELFARE_FEATURES: tuple[str, ...] = (
    "cash_stress_mean",
    "cash_stress_p10",
    "cash_stress_p50",
    "cash_stress_p90",
    "food_insecurity_mean",
    "food_insecurity_p10",
    "food_insecurity_p50",
    "food_insecurity_p90",
    "mean_health",
    "mean_happiness",
    "n_below_cash_thresh",
    "n_food_insecure",
    "mean_distress",
    "pct_health_below_0p7",
)

FIRM_STABILITY_FEATURES: tuple[str, ...] = (
    "n_burn_mode",
    "n_survival_mode",
    "bankruptcies_tick",
    "n_weak_demand",
)

FISCAL_FEATURES: tuple[str, ...] = ("gov_cash", "gov_profit", "fiscal_stress")

FEATURE_MANIFEST: tuple[str, ...] = (
    *LABOR_FEATURES,
    *DEMAND_FEATURES_BASE,
    *DEMAND_FEATURES_SECTOR,
    *HOUSEHOLD_WELFARE_FEATURES,
    *FIRM_STABILITY_FEATURES,
    *FISCAL_FEATURES,
    *POLICY_STATE_COLUMNS,
)

IDENTIFIER_COLUMNS: tuple[str, ...] = (
    "run_id",
    "policy_canonical",
    "levers_json",
    "seed",
    "tick",
)

LABEL_COLUMNS: tuple[str, ...] = ("unemployment_rate__t+8", "consumer_distress__t+8")

DROPPED_MANIFEST_COLUMNS: tuple[str, ...] = ()


def _normalise_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 10)
    if isinstance(value, Mapping):
        return {str(k): _normalise_value(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalise_value(v) for v in value]
    return value


def resolve_levers(levers: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge a policy delta onto the frozen baseline lever vector."""
    resolved = dict(BASELINE_LEVERS)
    for key, value in (levers or {}).items():
        if key not in BASELINE_LEVERS:
            raise ValueError(f"Unknown frozen policy lever: {key}")
        resolved[key] = _normalise_value(value)
    return resolved


def canonical_lever_json(levers: Mapping[str, Any] | None) -> str:
    """Return sorted, baseline-resolved JSON for a policy lever vector."""
    resolved = resolve_levers(levers)
    ordered = {key: resolved[key] for key in sorted(resolved)}
    return json.dumps(ordered, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_policy_hash(levers: Mapping[str, Any] | None) -> str:
    """Return a stable hash of the sorted resolved lever vector."""
    digest = hashlib.sha256(canonical_lever_json(levers).encode("utf-8")).hexdigest()
    return digest[:16]


def arm_by_id(arm_id: str) -> PolicyArm:
    """Look up a frozen policy arm by ID."""
    for arm in FROZEN_ARMS:
        if arm.arm_id == arm_id:
            return arm
    valid = ", ".join(arm.arm_id for arm in FROZEN_ARMS)
    raise KeyError(f"Unknown policy arm '{arm_id}'. Valid arms: {valid}")
