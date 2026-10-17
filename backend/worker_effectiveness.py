"""One worker-productivity rule shared by every producing firm.

Before round 1 (PR2) goods firms and Services firms scored the same worker
differently: goods used ``HouseholdAgent.get_performance_multiplier`` (morale,
health and happiness mapped onto 0.75-1.5x, with skill as a separate +0-25%
bonus) and Services used an inline weighted sum of skill, health, morale and
happiness mapped onto 1-7 units. This module is the single replacement.

The rule is a weighted score of four household states, centred at a neutral
score of 0.5, scaled by one slope, then passed through a soft (tanh)
saturation toward a floor and a ceiling::

    score = w_skill*skill + w_health*health + w_morale*morale + w_happy*happiness
    z = slope * (score - 0.5)
    effectiveness = 1 + up * tanh(z / up)      if z >= 0, up   = max - 1
                    1 - down * tanh(-z / down) if z <  0, down = 1 - min

Near the neutral worker the curve has slope 1 in ``z``, so small differences
pass through almost unchanged. Far from it the curve flattens toward the
0.8x floor and the 1.25x ceiling but never reaches them, so better workers
always produce more and nobody piles up at a hard wall.

Why each number:

- Weights 0.30/0.25/0.25/0.20: the former Services weighted sum, kept so
  Services output changes as little as possible (first-pass spec item 2).
  They sum to 1, so an all-0.5 worker scores exactly 0.5.
- Neutral score 0.5: the midpoint of the 0-1 states, so "average on every
  input" means exactly 1.0x.
- Slope 1.3: makes happiness alone move a neutral worker's output by about
  +/-12% after saturation (+11.9% / -11.4%). Oswald, Proto and Sgroi (2015,
  J. Labor Econ. 33(4)) find induced happiness raises productivity by about
  12%; Bellet, De Neve and Ward (2024, Mgmt. Sci. 70(3)) find about 13% more
  weekly sales in very happy than very unhappy weeks.
- Asymptotes 0.8x and 1.25x (spec values): the band spans 1.56x top to
  bottom for one worker's state. Firm-level spread (Syverson 2011, J. Econ.
  Lit.: p90/p10 TFP about 2x within US 4-digit industries) also comes from
  firms' own productivity, capital and experience, which multiply on top of
  this rule, so the worker-state band is set narrower than 2x. 0.8 is
  1/1.25, so floor and ceiling are symmetric in log output (+/-22.3%).
- Current happiness, not a smoothed one: round 1 PR6 (happiness v2) makes
  happiness itself move 5% per week toward its target, which is already an
  exponential average with a 20-week time constant. Smoothing it again here
  would lag it twice.
"""

from __future__ import annotations

import math
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
        Dimensionless multiplier on a worker's planned output, strictly
        between ``worker_effectiveness_min`` and ``worker_effectiveness_max``
        (default 0.8-1.25) for finite inputs. Inputs outside 0-1 are clipped
        first. The result rises strictly with each input that has a
        positive weight and approaches, but never reaches, the bounds.
    """
    if config is None:
        config = CONFIG.firms
    score = (
        config.worker_effectiveness_skill_weight * _unit(skill)
        + config.worker_effectiveness_health_weight * _unit(health)
        + config.worker_effectiveness_morale_weight * _unit(morale)
        + config.worker_effectiveness_happiness_weight * _unit(happiness)
    )
    z = config.worker_effectiveness_slope * (score - NEUTRAL_SCORE)
    if z >= 0.0:
        up = config.worker_effectiveness_max - 1.0
        return 1.0 + (up * math.tanh(z / up) if up > 0.0 else 0.0)
    down = 1.0 - config.worker_effectiveness_min
    return 1.0 - (down * math.tanh(-z / down) if down > 0.0 else 0.0)


def household_effectiveness(household: Any, *, config: Any = None) -> float:
    """``worker_effectiveness`` for a ``HouseholdAgent`` (reads its four states)."""
    return worker_effectiveness(
        household.skills_level,
        household.health,
        household.morale,
        household.happiness,
        config=config,
    )
