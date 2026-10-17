"""One worker-productivity rule shared by every producing firm.

Before round 1 (PR2) goods firms and Services firms scored the same worker
differently: goods used ``HouseholdAgent.get_performance_multiplier`` (morale,
health and happiness mapped onto 0.75-1.5x, with skill as a separate +0-25%
bonus) and Services used an inline weighted sum of skill, health, morale and
happiness mapped onto 1-7 units. This module is the single replacement.

The rule is a weighted score of four household states, centred at a neutral
score of 0.5 and scaled by one slope::

    score = w_skill*skill + w_health*health + w_morale*morale + w_happy*happiness
    effectiveness = clamp(1 + slope * (score - 0.5), lo, hi)

With the defaults (weights 0.30/0.25/0.25/0.20 from the old Services sum,
slope 1.2) happiness on its own can move a worker's output by at most
``slope * w_happy * 0.5 = 0.12`` (+/-12%), and the whole result is clamped to
0.8-1.25x. An average worker (every input 0.5) is exactly 1.0x.

Evidence for the size of the happiness effect: Oswald, Proto and Sgroi (2015,
J. Labor Econ. 33(4)) find that induced happiness raises lab productivity by
about 12%; Bellet, De Neve and Ward (2024, Mgmt. Sci. 70(3)) find about 13%
more weekly sales in a call centre's very happy weeks than its very unhappy
ones. The full 0-1 happiness range here spans 24% (0.88x-1.12x), so it sits
at the top of that evidence. The clamp keeps a burned-out or a star worker
within a band that firms' capacity plans can absorb.
"""

from __future__ import annotations

from typing import Any

from config import CONFIG

NEUTRAL_SCORE = 0.5


def _unit(value: float) -> float:
    """Clip a household state to [0, 1]; non-finite input counts as 0."""
    v = float(value)
    if v != v:  # NaN
        return 0.0
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def worker_effectiveness(
    skill: float,
    health: float,
    morale: float,
    happiness: float,
    *,
    config: Any = None,
) -> float:
    """Return a worker's output multiplier from their current state.

    Pure: reads only its arguments and the firm config, mutates nothing, uses
    no randomness. Called once per employed worker per tick by
    ``Economy._calculate_experience_adjusted_production``.

    Args:
        skill: ``HouseholdAgent.skills_level``, 0-1.
        health: ``HouseholdAgent.health``, 0-1.
        morale: ``HouseholdAgent.morale``, 0-1.
        happiness: ``HouseholdAgent.happiness``, 0-1.
        config: object with the ``worker_effectiveness_*`` fields of
            ``FirmBehaviorConfig``; defaults to the live ``CONFIG.firms``.

    Returns:
        Dimensionless multiplier on a worker's planned output, in
        ``[worker_effectiveness_min, worker_effectiveness_max]``
        (default 0.8-1.25). Inputs outside 0-1 are clipped first, so the
        result is non-decreasing in each input and never leaves the band.
    """
    if config is None:
        config = CONFIG.firms
    score = (
        config.worker_effectiveness_skill_weight * _unit(skill)
        + config.worker_effectiveness_health_weight * _unit(health)
        + config.worker_effectiveness_morale_weight * _unit(morale)
        + config.worker_effectiveness_happiness_weight * _unit(happiness)
    )
    raw = 1.0 + config.worker_effectiveness_slope * (score - NEUTRAL_SCORE)
    return min(config.worker_effectiveness_max, max(config.worker_effectiveness_min, raw))


def household_effectiveness(household: Any, *, config: Any = None) -> float:
    """``worker_effectiveness`` for a ``HouseholdAgent`` (reads its four states)."""
    return worker_effectiveness(
        household.skills_level,
        household.health,
        household.morale,
        household.happiness,
        config=config,
    )
