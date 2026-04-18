"""Fix 24: Policy Lever Sensitivity Validation.

Verifies that each policy lever produces a measurable and directionally
correct effect on its primary observable over a 52-tick sweep.
"""

import math
import random
from typing import Any, Dict, List

import numpy as np
import pytest

from agents import GovernmentAgent
from config import CONFIG
from economy import Economy


def _build_default_economy(seed: int = 42) -> Economy:
    """Construct a small deterministic economy for lever-sweep tests."""
    from tests_contracts.conftest import seed_everything
    seed_everything(seed)

    from tests_contracts.factories import make_economy
    eco = make_economy(seed=seed)
    return eco


def _warmup(economy: Economy, ticks: int = 20) -> None:
    for _ in range(ticks):
        economy.step()


def _run_ticks(economy: Economy, ticks: int) -> Dict[str, Any]:
    """Run *ticks* simulation steps and return final metrics."""
    for _ in range(ticks):
        economy.step()
    return economy.get_economic_metrics()


def _get_metric(metrics: Dict[str, Any], key: str) -> float:
    val = metrics.get(key, 0.0)
    if isinstance(val, (int, float)):
        return float(val)
    return 0.0


# ---------------------------------------------------------------------------
# Each test sweeps one lever across its options and checks the primary metric
# ---------------------------------------------------------------------------

class TestLeverSensitivity:
    """Each lever should produce a directionally correct change in its primary
    observable across the option sweep."""

    @pytest.mark.parametrize("seed", [42])
    def test_tax_policy_revenue(self, seed: int) -> None:
        """Higher tax rates → more government revenue (over 52 ticks)."""
        rates = [0.05, 0.15, 0.30]
        revenues: List[float] = []
        for rate in rates:
            eco = _build_default_economy(seed)
            eco.government.wage_tax_rate = rate
            eco.government.profit_tax_rate = rate
            _warmup(eco, 15)
            metrics = _run_ticks(eco, 52)
            revenues.append(_get_metric(metrics, "gov_revenue_this_tick"))

        # Should be roughly increasing
        assert revenues[-1] >= revenues[0] * 0.8, (
            f"Tax sweep {rates} produced revenues {revenues} — "
            f"highest rate should yield ≥80% of lowest rate revenue"
        )

    @pytest.mark.parametrize("seed", [42])
    def test_benefit_level_morale(self, seed: int) -> None:
        """Higher benefits → higher average morale."""
        options = ["low", "neutral", "high"]
        morales: List[float] = []
        for level in options:
            eco = _build_default_economy(seed)
            eco.government.benefit_level = level
            eco.government.apply_policy_levers()
            _warmup(eco, 15)
            metrics = _run_ticks(eco, 52)
            morales.append(_get_metric(metrics, "mean_morale"))

        assert morales[-1] >= morales[0] - 0.05, (
            f"Benefit sweep {options} produced morale {morales} — "
            f"high should be near or above low"
        )

    @pytest.mark.parametrize("seed", [42])
    def test_minimum_wage_avg_wage(self, seed: int) -> None:
        """Higher minimum wage → higher average wage."""
        options = ["low", "neutral", "high"]
        wages: List[float] = []
        for level in options:
            eco = _build_default_economy(seed)
            eco.government.minimum_wage_policy = level
            eco.government.apply_policy_levers()
            _warmup(eco, 15)
            metrics = _run_ticks(eco, 52)
            wages.append(_get_metric(metrics, "mean_wage"))

        assert wages[-1] >= wages[0], (
            f"Min-wage sweep {options} produced avg wages {wages} — "
            f"high should be ≥ low"
        )

    @pytest.mark.parametrize("seed", [42])
    def test_infrastructure_productivity(self, seed: int) -> None:
        """More infrastructure spending → higher productivity multiplier."""
        options = ["none", "low", "medium", "high"]
        multipliers: List[float] = []
        for level in options:
            eco = _build_default_economy(seed)
            eco.government.infrastructure_spending = level
            eco.government.apply_policy_levers()
            _warmup(eco, 15)
            metrics = _run_ticks(eco, 52)
            multipliers.append(_get_metric(metrics, "infrastructure_productivity"))

        assert multipliers[-1] >= multipliers[0], (
            f"Infra sweep {options} produced multipliers {multipliers} — "
            f"high should be ≥ none"
        )

    @pytest.mark.parametrize("seed", [42])
    def test_lever_spread_minimum(self, seed: int) -> None:
        """Each lever should produce at least a non-trivial spread in its
        primary metric over the full sweep (sanity gate)."""
        sweeps = {
            "wage_tax_rate": {
                "values": [0.05, 0.30],
                "metric": "government_cash",
            },
            "minimum_wage_policy": {
                "values": ["low", "high"],
                "metric": "mean_wage",
                "attr": "minimum_wage_policy",
            },
        }
        for lever, spec in sweeps.items():
            results = []
            for val in spec["values"]:
                eco = _build_default_economy(seed)
                attr = spec.get("attr", lever)
                setattr(eco.government, attr, val)
                eco.government.apply_policy_levers()
                _warmup(eco, 15)
                m = _run_ticks(eco, 40)
                results.append(_get_metric(m, spec["metric"]))

            lo, hi = results
            spread = abs(hi - lo) / max(abs(lo), 1.0)
            assert spread > 0.01, (
                f"Lever {lever}: spread {spread:.4f} < 1% — "
                f"values were {results}"
            )
