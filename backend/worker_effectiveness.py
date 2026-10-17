"""Worker output per unit of planned labor, from three concrete mechanisms.

One rule for every producing firm (goods and Services)::

    output per worker = units per worker            (the firm's technology)
                      x skill_factor(skill)         (human capital)
                      x effort(morale, happiness)   (efficiency-wage effort)
                      x hours_present(health)       (sickness absence)

``units per worker`` belongs to the firm (planned production for goods,
``FirmAgent._service_units_per_worker()`` for Services) and is applied by
``Economy._calculate_experience_adjusted_production``. This module supplies
the other three factors. They multiply, so no factor can make up for another:
a sick worker's skill does not bring back the hours they were absent.

skill_factor = 1 + SKILL_PREMIUM * skill (+ the goods experience bonus)
    Kept from main's goods path, not newly sourced. The size, +25% at skill
    1.0, is the same premium firms pay for skill at hire
    (``Economy`` labor matching, ``skill_premium = skills_level * 0.25``), so
    a worker's productivity premium equals their pay premium. That equality
    is what Hellerstein, Neumark and Troske (1999, J. Labor Econ. 17(3))
    find for most worker groups in matched plant data. The 0.25 itself is a
    legacy number with no external source.

effort = 1 + effort_range * (morale + happiness - 1)
    Akerlof and Yellen (1990, QJE 105(2)): effort rises with how fairly a
    worker feels treated. EcoSim's morale is that state: it rises when
    employed and paid at least the expected wage and falls with the wage
    gap, unemployment and homelessness. Happiness is the broader mood the
    productivity studies manipulate. The two share drivers (employment and
    "wage >= expected" feed both), so they are two readings of one
    job-wellbeing state, not two independent effects. With no evidence on
    their relative loading, each gets half: effort reads their mean,
    ``(morale + happiness) / 2``, centred at the scale midpoint 0.5. Adding
    two separate +/-12% terms would count the wage-fairness channel twice.
    Size: the mean moving from 0 to 1 moves effort from 0.88 to 1.12.
    Oswald, Proto and Sgroi (2015, J. Labor Econ. 33(4)) find about 12%
    higher output after a happiness induction; Bellet, De Neve and Ward
    (2024, Mgmt. Sci. 70(3)) find about 13% more weekly sales in a call
    centre's happiest weeks. Both are short-run treatment-vs-control shifts,
    so applying 12% to the full 0-1 range is an upper end, not a midpoint.
    One state alone moves effort by +/-6%.

hours_present = 1 - absence(health)
    absence(h) = ref_rate * (1 + (ratio - 1) * (1 - h))
                          / (1 + (ratio - 1) * (1 - ref_health))
    Level: BLS CPS annual averages, Table 47 (2023-2025), full-time wage and
    salary workers lose 1.1% of usual hours to their own illness, injury or
    medical problems (1.7% for all absence reasons). The US average worker
    is mapped to EcoSim's average employed worker, health 0.77 on main
    (seeds 42-44, weeks 27-156). Shape: Halford et al. (2012, BMC Public
    Health 12:1103), Swedish register data, find sick-leave days fall
    linearly with self-rated health (no squared or cubic term was
    significant); the lowest health group takes 2.3x (women) and 2.0x (men)
    the sick days of the highest, so ``ratio`` is 2.2. Result: hours present
    run from about 98.1% (health 0) to 99.1% (health 1). Health below 0.10
    already keeps a worker out of the labor market (``can_work``). Working
    while sick at lower speed (presenteeism) is not modeled here.
"""

from __future__ import annotations

from typing import Any

from config import CONFIG

# Productivity premium at skill 1.0. Mirrors the hire-time pay premium in
# Economy labor matching (skill_premium = skills_level * 0.25); see above.
SKILL_PREMIUM = 0.25


def _unit(value: float) -> float:
    """Clip a household state to [0, 1]; non-finite input counts as 0."""
    v = float(value)
    if v != v:  # NaN
        return 0.0
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def skill_factor(skill: float, experience_bonus: float = 0.0) -> float:
    """Human-capital factor: ``1 + 0.25 * skill + experience_bonus``.

    ``experience_bonus`` is the goods firms' category-experience bonus (5% a
    year, capped at 50%), passed in by the caller; Services firms pass 0, as
    on main.
    """
    return 1.0 + SKILL_PREMIUM * _unit(skill) + max(0.0, float(experience_bonus))


def effort(morale: float, happiness: float, *, config: Any = None) -> float:
    """Efficiency-wage effort from the mean of morale and happiness.

    Returns ``1 + effort_range * (morale + happiness - 1)``: 1.0 at a mean of
    0.5, ``1 +/- effort_range`` at the ends (0.88-1.12 by default).
    """
    if config is None:
        config = CONFIG.firms
    return 1.0 + config.worker_effort_range * (_unit(morale) + _unit(happiness) - 1.0)


def absence_rate(health: float, *, config: Any = None) -> float:
    """Share of usual hours lost to sickness at this health level (0-1).

    Linear in health, equal to ``worker_absence_reference_rate`` at
    ``worker_absence_reference_health`` and ``worker_absence_sick_ratio``
    times higher at health 0 than at health 1.
    """
    if config is None:
        config = CONFIG.firms
    slope = config.worker_absence_sick_ratio - 1.0
    reference = 1.0 + slope * (1.0 - _unit(config.worker_absence_reference_health))
    rate = config.worker_absence_reference_rate * (1.0 + slope * (1.0 - _unit(health))) / reference
    return min(1.0, max(0.0, rate))


def hours_present(health: float, *, config: Any = None) -> float:
    """Share of usual hours actually worked: ``1 - absence_rate(health)``."""
    return 1.0 - absence_rate(health, config=config)


def worker_effectiveness(
    skill: float,
    health: float,
    morale: float,
    happiness: float,
    *,
    experience_bonus: float = 0.0,
    config: Any = None,
) -> float:
    """Return a worker's output multiplier on the firm's units per worker.

    ``skill_factor * effort * hours_present``. Pure: reads only its
    arguments and the firm config, mutates nothing, uses no randomness.
    Called once per employed worker per tick by
    ``Economy._calculate_experience_adjusted_production``.

    Args:
        skill: ``HouseholdAgent.skills_level``, 0-1.
        health: ``HouseholdAgent.health``, 0-1.
        morale: ``HouseholdAgent.morale``, 0-1.
        happiness: ``HouseholdAgent.happiness``, 0-1.
        experience_bonus: goods-only category-experience bonus (0-0.5).
        config: object with the ``worker_effort_*`` and ``worker_absence_*``
            fields of ``FirmBehaviorConfig``; defaults to ``CONFIG.firms``.

    Returns:
        Dimensionless multiplier. With defaults and no experience it lies in
        about 0.86 (skill, health, morale and happiness all 0) to 1.39 (all
        1). Inputs outside 0-1 are clipped first. It rises with each input.
    """
    return (
        skill_factor(skill, experience_bonus)
        * effort(morale, happiness, config=config)
        * hours_present(health, config=config)
    )


def household_effectiveness(
    household: Any, *, experience_bonus: float = 0.0, config: Any = None
) -> float:
    """``worker_effectiveness`` for a ``HouseholdAgent`` (reads its four states)."""
    return worker_effectiveness(
        household.skills_level,
        household.health,
        household.morale,
        household.happiness,
        experience_bonus=experience_bonus,
        config=config,
    )
