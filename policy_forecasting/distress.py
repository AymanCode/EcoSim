"""Frozen consumer distress formula for labels and same-tick welfare features."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from policy_forecasting.config import FOOD_INSECURITY_WINDOW, K_CASH_STRESS


ESSENTIAL_SPEND_DEFAULT: float = 50.0
HEALTH_MAX: float = 1.0
HAPPINESS_MAX: float = 1.0
WEIGHTS: dict[str, float] = {
    "cash": 0.40,
    "food": 0.25,
    "health": 0.20,
    "happy": 0.15,
}


def clip01(value: float) -> float:
    """Clamp a float to [0, 1]."""
    return max(0.0, min(1.0, float(value)))


def _field(obj: Any, name: str, default: Any = 0.0) -> Any:
    if hasattr(obj, "to_dict"):
        try:
            data = obj.to_dict()
            if name in data:
                return data[name]
        except Exception:
            pass
    return getattr(obj, name, default)


def food_shortfall_ratio(min_food: float, consumed: float) -> float:
    """Return max(0, (min_food - consumed) / max(min_food, 0.1))."""
    min_food_value = float(min_food)
    consumed_value = float(consumed)
    return max(0.0, (min_food_value - consumed_value) / max(min_food_value, 0.1))


def cash_stress(liquid_cash: float, essential_spend: float = ESSENTIAL_SPEND_DEFAULT) -> float:
    """Return the frozen cash stress component."""
    denominator = K_CASH_STRESS * max(float(essential_spend), 1e-9)
    return clip01(1.0 - float(liquid_cash) / denominator)


def food_insecurity(shortfall_history: Sequence[float], window: int = FOOD_INSECURITY_WINDOW) -> float:
    """Return fraction of the last F ticks with positive food shortfall."""
    positives = sum(1 for value in shortfall_history[-window:] if float(value) > 0.0)
    return clip01(positives / float(window))


def household_distress(
    household: Any,
    shortfall_history: Sequence[float],
    *,
    essential_spend: float = ESSENTIAL_SPEND_DEFAULT,
) -> float:
    """Compute one household's bounded distress score using the frozen weights."""
    liquid_cash = float(_field(household, "cash_balance", 0.0))
    health = clip01(float(_field(household, "health", HEALTH_MAX)))
    happiness = clip01(float(_field(household, "happiness", HAPPINESS_MAX)))

    value = (
        WEIGHTS["cash"] * cash_stress(liquid_cash, essential_spend)
        + WEIGHTS["food"] * food_insecurity(shortfall_history)
        + WEIGHTS["health"] * clip01(1.0 - health / HEALTH_MAX)
        + WEIGHTS["happy"] * clip01(1.0 - happiness / HAPPINESS_MAX)
    )
    return clip01(value)


@dataclass
class DistressHistory:
    """Per-household rolling food-shortfall histories."""

    window: int = FOOD_INSECURITY_WINDOW
    _history: dict[int, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def record(self, household: Any) -> list[float]:
        """Record this tick's shortfall for one household and return its history."""
        household_id = int(_field(household, "household_id", id(household)))
        history = self._history[household_id]
        if history.maxlen is None:
            replacement = deque(history, maxlen=self.window)
            self._history[household_id] = replacement
            history = replacement
        min_food = float(_field(household, "min_food_per_tick", 0.0))
        consumed = float(_field(household, "food_consumed_this_tick", 0.0))
        history.append(food_shortfall_ratio(min_food, consumed))
        return list(history)

    def get(self, household: Any) -> list[float]:
        """Return the existing history for one household without mutating it."""
        household_id = int(_field(household, "household_id", id(household)))
        return list(self._history.get(household_id, ()))


def household_components(
    household: Any,
    history: Sequence[float],
    *,
    essential_spend: float = ESSENTIAL_SPEND_DEFAULT,
) -> dict[str, float]:
    """Return component scores for a household at the current tick."""
    liquid_cash = float(_field(household, "cash_balance", 0.0))
    health = clip01(float(_field(household, "health", HEALTH_MAX)))
    happiness = clip01(float(_field(household, "happiness", HAPPINESS_MAX)))
    food_score = food_insecurity(history)
    return {
        "cash_stress": cash_stress(liquid_cash, essential_spend),
        "food_insecurity": food_score,
        "health": health,
        "happiness": happiness,
        "distress": household_distress(household, history, essential_spend=essential_spend),
    }


def compute_household_welfare(
    households: Iterable[Any],
    histories: DistressHistory | None = None,
    *,
    update_history: bool = True,
    essential_spend: float = ESSENTIAL_SPEND_DEFAULT,
) -> dict[str, float]:
    """Compute all frozen household welfare aggregate features."""
    history_store = histories or DistressHistory()
    components: list[dict[str, float]] = []
    for household in households:
        history = history_store.record(household) if update_history else history_store.get(household)
        components.append(household_components(household, history, essential_spend=essential_spend))

    if not components:
        return {
            "cash_stress_mean": 0.0,
            "cash_stress_p10": 0.0,
            "cash_stress_p50": 0.0,
            "cash_stress_p90": 0.0,
            "food_insecurity_mean": 0.0,
            "food_insecurity_p10": 0.0,
            "food_insecurity_p50": 0.0,
            "food_insecurity_p90": 0.0,
            "mean_health": 0.0,
            "mean_happiness": 0.0,
            "n_below_cash_thresh": 0.0,
            "n_food_insecure": 0.0,
            "mean_distress": 0.0,
            "pct_health_below_0p7": 0.0,
        }

    cash = np.array([item["cash_stress"] for item in components], dtype=float)
    food = np.array([item["food_insecurity"] for item in components], dtype=float)
    health = np.array([item["health"] for item in components], dtype=float)
    happiness = np.array([item["happiness"] for item in components], dtype=float)
    distress = np.array([item["distress"] for item in components], dtype=float)
    cash_p10, cash_p50, cash_p90 = np.percentile(cash, [10, 50, 90])
    food_p10, food_p50, food_p90 = np.percentile(food, [10, 50, 90])
    return {
        "cash_stress_mean": float(cash.mean()),
        "cash_stress_p10": float(cash_p10),
        "cash_stress_p50": float(cash_p50),
        "cash_stress_p90": float(cash_p90),
        "food_insecurity_mean": float(food.mean()),
        "food_insecurity_p10": float(food_p10),
        "food_insecurity_p50": float(food_p50),
        "food_insecurity_p90": float(food_p90),
        "mean_health": float(health.mean()),
        "mean_happiness": float(happiness.mean()),
        "n_below_cash_thresh": float((cash > 0.0).sum()),
        "n_food_insecure": float((food > 0.0).sum()),
        "mean_distress": float(distress.mean()),
        "pct_health_below_0p7": float((health < 0.7).mean()),
    }


def consumer_distress(
    households: Iterable[Any],
    histories: DistressHistory | None = None,
    *,
    essential_spend: float = ESSENTIAL_SPEND_DEFAULT,
) -> float:
    """Return economy-level consumer distress as the household mean."""
    welfare = compute_household_welfare(
        households,
        histories,
        update_history=True,
        essential_spend=essential_spend,
    )
    return float(welfare["mean_distress"])
