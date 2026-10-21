"""Effective labour for firm capacity. Used only when the flag is on.

``CONFIG.firms.effective_labor_enabled`` defaults to false. The flag-off
production path never calls this module.

A worker's weight is their multiplier divided by the multiplier of the run's
reference worker, so a reference worker counts as 1.0 labour unit. Tick 1
uses ``worker_reference_skill``. After tick 1 the economy stores the week-1
employed Food and Services mean skill and later ticks use that. Capacity
then uses that sum in place of a headcount. Hiring counts skill and category
experience only: mood and health are not known at hire (R06). This week's
output still uses the current roster's health and mood, because those people
are already employed.

Health on the flag-on path defaults to ``main_weight`` (option C): main's
performance multiplier, divided by its value at a frozen employed state, so
turning the flag on does not drop the health channel. Absence and
presenteeism are switchable and are not the default.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Pay-side skill slope. Hellerstein, Neumark and Troske (1999, J. Labor
# Econ.) find that the productivity premium lines up with the wage premium
# for most groups. The 0.25 itself is the slope already paid at hire
# (economy.py), not a new estimate.
SKILL_SLOPE = 0.25

# Category experience on the flag-on path uses the pay premium, not main's
# 5%/year productivity bonus (cap 50%). Pay is 3%/year, cap 30%.
EXPERIENCE_PER_YEAR = 0.03
EXPERIENCE_CAP = 0.30

# Week-1 skill initializer is min(0.95, 0.2 + (i / N) * 0.75). At N=1000 the
# median is 0.574625 (seeds 42-44, main f86f140, tick 1, all identical).
REFERENCE_SKILL = 0.574625

# Employed workers, main f86f140, seeds 42-44, weeks 27-156, pooled.
# Mood is (morale + happiness) / 2. Frozen here; not re-read from a live run.
# p90 of mood was 1.0 on every seed; the mean of the three p10s is 0.82436,
# so half the p10-p90 gap is 0.08782. Effort ±12% spans that gap.
REFERENCE_MOOD = 0.9104069292879677
MOOD_HALF_SPAN = 0.08782101586267449
REFERENCE_MORALE = 0.9481115092248019
REFERENCE_HAPPINESS = 0.8727023493511338
REFERENCE_PERFORMANCE_HEALTH = 0.7687005387114373

# Absence is anchored at full health, the household's starting health, not at
# main's employed equilibrium (0.77), which moves when health dynamics change.
ABSENCE_REFERENCE_HEALTH = 1.0

HEALTH_MODES = ("main_weight", "absence", "presenteeism")


@dataclass(frozen=True)
class EffectivenessSpec:
    """One read of the firm config for a tick. Passed into the worker loop."""

    health_mode: str
    effort_range: float
    reference_mood: float
    mood_half_span: float
    absence_reference_rate: float
    absence_reference_health: float
    absence_sick_ratio: float
    presenteeism_multiple: float
    reference_skill: float
    morale_weight: float
    health_weight: float
    happiness_weight: float
    performance_min: float
    performance_max: float
    performance_reference: float


def experience_premium(years: float) -> float:
    """Pay-aligned experience premium: 3% per year, cap 30%."""
    if not math.isfinite(years) or years <= 0.0:
        return 0.0
    return min(years * EXPERIENCE_PER_YEAR, EXPERIENCE_CAP)


def _clip01(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number


def performance_multiplier(
    morale: float,
    health: float,
    happiness: float,
    spec: EffectivenessSpec,
) -> float:
    """Main's wellbeing map, [performance_min, performance_max]."""
    score = (
        morale * spec.morale_weight
        + health * spec.health_weight
        + happiness * spec.happiness_weight
    )
    span = spec.performance_max - spec.performance_min
    return spec.performance_min + score * span


def effort(morale: float, happiness: float, spec: EffectivenessSpec) -> float:
    """1.0 at the frozen employed mood. ±effort_range spans the p10-p90 gap.

    Happiness studies (Oswald, Proto and Sgroi 2015; Bellet, De Neve and Ward
    2024) are about a 12% output shift. Centering on 0.5 put employed workers
    near 1.10, because their mood sits near 0.91. The half-span is the frozen
    p10-p90 gap, so ±12% covers that range and the mean worker is 1.0.
    """
    mood = (morale + happiness) / 2.0
    raw = 1.0 + spec.effort_range * (mood - spec.reference_mood) / spec.mood_half_span
    if not math.isfinite(raw):
        return 0.0
    return max(0.0, raw)


def absence_rate(health: float, spec: EffectivenessSpec) -> float:
    """Share of hours lost. Equals the reference rate at the reference health.

    BLS CPS Table 47: full-time workers lose 1.1% of hours to their own
    illness or injury. Halford et al. 2012 (BMC Public Health): sick leave
    falls linearly with self-rated health, and the lowest group takes about
    2.2 times the days of the highest (2.3 for women, 2.0 for men). The 1.1%
    is applied at health 1.0, the scale's starting health, not at a health
    level measured from a finished run.
    """
    ref = spec.absence_reference_health
    if ref <= 0.0:
        raw = spec.absence_reference_rate
    else:
        raw = spec.absence_reference_rate * (
            1.0 + (spec.absence_sick_ratio - 1.0) * ((ref - health) / ref)
        )
    if not math.isfinite(raw):
        return 1.0
    return min(1.0, max(0.0, raw))


def hours_present(health: float, spec: EffectivenessSpec, *, presenteeism: bool) -> float:
    """Hours on the job, clamped to [0, 1]. Presenteeism scales the absence."""
    lost = absence_rate(health, spec)
    if presenteeism:
        # Stewart et al. 2003 JAMA: 76.6% of pain-related lost productive time
        # is reduced performance at work, about 3.3 times the absence share
        # (0.766 / 0.234). The multiple is config, default 3.3.
        lost *= 1.0 + spec.presenteeism_multiple
    if not math.isfinite(lost):
        return 0.0
    return min(1.0, max(0.0, 1.0 - lost))


def _health_factor(morale: float, health: float, happiness: float, spec: EffectivenessSpec) -> float:
    if spec.health_mode == "main_weight":
        ref = spec.performance_reference
        if ref <= 0.0 or not math.isfinite(ref):
            return 0.0
        return performance_multiplier(morale, health, happiness, spec) / ref
    presenteeism = spec.health_mode == "presenteeism"
    ref_hours = hours_present(
        spec.absence_reference_health, spec, presenteeism=presenteeism,
    )
    if ref_hours <= 0.0:
        return 0.0
    return (
        effort(morale, happiness, spec)
        * hours_present(health, spec, presenteeism=presenteeism)
        / ref_hours
    )


def worker_weights(household: object, category: str, spec: EffectivenessSpec) -> tuple[float, float]:
    """Return (observable, full) labour units for one worker.

    Observable is skill and category experience, for hiring. Full also
    includes the health channel. A missing record or a non-finite input is
    0, not 1: an unknown worker does not fill a slot. Zero workers therefore
    produce zero.
    """
    if household is None:
        return (0.0, 0.0)
    skill = _clip01(getattr(household, "skills_level", None))
    morale = _clip01(getattr(household, "morale", None))
    happiness = _clip01(getattr(household, "happiness", None))
    health = _clip01(getattr(household, "health", None))
    if skill is None or morale is None or happiness is None or health is None:
        return (0.0, 0.0)
    experience = getattr(household, "category_experience", None)
    ticks = 0.0
    if isinstance(experience, dict):
        try:
            ticks = float(experience.get(category, 0) or 0.0)
        except (TypeError, ValueError):
            return (0.0, 0.0)
        if not math.isfinite(ticks):
            return (0.0, 0.0)
    premium = experience_premium(ticks / 52.0)
    ref = 1.0 + SKILL_SLOPE * spec.reference_skill
    if ref <= 0.0:
        return (0.0, 0.0)
    observable = (1.0 + SKILL_SLOPE * skill + premium) / ref
    full = observable * _health_factor(morale, health, happiness, spec)
    if not math.isfinite(observable) or not math.isfinite(full):
        return (0.0, 0.0)
    observable = max(0.0, observable)
    full = max(0.0, full)
    return (observable, full)


def load_spec(firms: object, households: object) -> EffectivenessSpec:
    """Read the firm and household config once."""
    mode = str(getattr(firms, "effective_labor_health"))
    spec = EffectivenessSpec(
        health_mode=mode,
        effort_range=float(getattr(firms, "worker_effort_range")),
        reference_mood=float(getattr(firms, "worker_effort_reference_mood")),
        mood_half_span=float(getattr(firms, "worker_effort_mood_half_span")),
        absence_reference_rate=float(getattr(firms, "worker_absence_reference_rate")),
        absence_reference_health=float(getattr(firms, "worker_absence_reference_health")),
        absence_sick_ratio=float(getattr(firms, "worker_absence_sick_ratio")),
        presenteeism_multiple=float(getattr(firms, "worker_presenteeism_multiple")),
        reference_skill=float(getattr(firms, "worker_reference_skill")),
        morale_weight=float(getattr(households, "performance_morale_weight")),
        health_weight=float(getattr(households, "performance_health_weight")),
        happiness_weight=float(getattr(households, "performance_happiness_weight")),
        performance_min=float(getattr(households, "performance_min_multiplier")),
        performance_max=float(getattr(households, "performance_max_multiplier")),
        performance_reference=0.0,
    )
    ref = performance_multiplier(
        REFERENCE_MORALE, REFERENCE_PERFORMANCE_HEALTH, REFERENCE_HAPPINESS, spec,
    )
    return EffectivenessSpec(
        health_mode=spec.health_mode,
        effort_range=spec.effort_range,
        reference_mood=spec.reference_mood,
        mood_half_span=spec.mood_half_span,
        absence_reference_rate=spec.absence_reference_rate,
        absence_reference_health=spec.absence_reference_health,
        absence_sick_ratio=spec.absence_sick_ratio,
        presenteeism_multiple=spec.presenteeism_multiple,
        reference_skill=spec.reference_skill,
        morale_weight=spec.morale_weight,
        health_weight=spec.health_weight,
        happiness_weight=spec.happiness_weight,
        performance_min=spec.performance_min,
        performance_max=spec.performance_max,
        performance_reference=ref,
    )


def _max_absence(firms: object) -> float:
    """Absence share at health 0, the high end of the linear schedule."""
    rate = float(getattr(firms, "worker_absence_reference_rate"))
    ratio = float(getattr(firms, "worker_absence_sick_ratio"))
    return rate * ratio


def validate_effective_labor_config(firms: object) -> None:
    """Reject non-finite values and an absence schedule that exceeds 100%."""
    enabled = getattr(firms, "effective_labor_enabled")
    if not isinstance(enabled, bool):
        raise ValueError("effective_labor_enabled must be a bool")
    mode = getattr(firms, "effective_labor_health")
    if mode not in HEALTH_MODES:
        raise ValueError(
            "effective_labor_health must be main_weight, absence, or presenteeism"
        )
    numeric = (
        "worker_effort_range",
        "worker_effort_reference_mood",
        "worker_effort_mood_half_span",
        "worker_absence_reference_rate",
        "worker_absence_reference_health",
        "worker_absence_sick_ratio",
        "worker_presenteeism_multiple",
        "worker_reference_skill",
    )
    for name in numeric:
        value = float(getattr(firms, name))
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if float(getattr(firms, "worker_effort_range")) < 0.0:
        raise ValueError("worker_effort_range must be >= 0")
    mood = float(getattr(firms, "worker_effort_reference_mood"))
    if not 0.0 <= mood <= 1.0:
        raise ValueError("worker_effort_reference_mood must be in [0, 1]")
    if float(getattr(firms, "worker_effort_mood_half_span")) <= 0.0:
        raise ValueError("worker_effort_mood_half_span must be > 0")
    rate = float(getattr(firms, "worker_absence_reference_rate"))
    if rate < 0.0:
        raise ValueError("worker_absence_reference_rate must be >= 0")
    ref_health = float(getattr(firms, "worker_absence_reference_health"))
    if not 0.0 <= ref_health <= 1.0:
        raise ValueError("worker_absence_reference_health must be in [0, 1]")
    sick = float(getattr(firms, "worker_absence_sick_ratio"))
    if sick < 0.0:
        raise ValueError("worker_absence_sick_ratio must be >= 0")
    if _max_absence(firms) > 1.0:
        raise ValueError("absence at health 0 must be <= 1 (rate x sick ratio)")
    multiple = float(getattr(firms, "worker_presenteeism_multiple"))
    if multiple < 0.0:
        raise ValueError("worker_presenteeism_multiple must be >= 0")
    if _max_absence(firms) * (1.0 + multiple) > 1.0:
        raise ValueError("presenteeism lost time at health 0 must be <= 1")
    skill = float(getattr(firms, "worker_reference_skill"))
    if not 0.0 <= skill <= 1.0:
        raise ValueError("worker_reference_skill must be in [0, 1]")


# Labor-force unemployed whose current spell began at this tick or earlier.
# At seed 42, tick 120, on main f86f140, this group is 176 of 353.
NEVER_REHIRED_START_TICK = 15


def spell_snapshot(households: list, tick: int) -> dict[str, float]:
    """Spell stats for the labor force (healthy enough to work, not employed).

    ``unemp_gt26`` and ``unemp_gt52`` are shares of that group. ``median_spell``
    is the median ongoing spell in weeks. ``never_rehired_n`` counts people
    whose spell started at tick <= 15, and ``never_rehired_skill`` is their
    median skill (0 when the group is empty).
    """
    unemployed = [
        h for h in households
        if h.employer_id is None and h.can_work
    ]
    count = len(unemployed)
    if count == 0:
        return {
            "unemp_gt26": 0.0,
            "unemp_gt52": 0.0,
            "median_spell": 0.0,
            "never_rehired_n": 0.0,
            "never_rehired_skill": 0.0,
        }
    durations = [int(h.unemployment_duration) for h in unemployed]
    ordered = sorted(durations)
    mid = count // 2
    if count % 2:
        median_spell = float(ordered[mid])
    else:
        median_spell = (ordered[mid - 1] + ordered[mid]) / 2.0
    never = [
        h for h in unemployed
        if tick - int(h.unemployment_duration) + 1 <= NEVER_REHIRED_START_TICK
    ]
    if never:
        skills = sorted(float(h.skills_level) for h in never)
        n = len(skills)
        skill_mid = n // 2
        if n % 2:
            never_skill = skills[skill_mid]
        else:
            never_skill = (skills[skill_mid - 1] + skills[skill_mid]) / 2.0
    else:
        never_skill = 0.0
    return {
        "unemp_gt26": sum(d > 26 for d in durations) / count,
        "unemp_gt52": sum(d > 52 for d in durations) / count,
        "median_spell": median_spell,
        "never_rehired_n": float(len(never)),
        "never_rehired_skill": float(never_skill),
    }
