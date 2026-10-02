"""fix_preference_applied_once on by default, household variety preserved (2026-10-02, item 5).

Before, the batch planner applied each category preference twice (budget
shares followed preference squared). With the fix on, shares follow
preference once, which narrowed the spread of budget shares. The
preference ranges were widened so that, with the fix on, the 10th/50th/90th
percentiles of each category's static budget fraction across 1,500 default
households stay close to the old (flag off, old ranges) distribution.
"""

import dataclasses

import numpy as np
import pytest

from agents import HouseholdAgent
from config import CONFIG, clone_config, use_config

CATS = ("food", "housing", "services")
OLD_RANGES = {"food": (0.8, 1.2), "housing": (0.4, 1.4), "services": (0.8, 1.2)}
# Flag off, old ranges, households 0..1499 at the default seed (measured 2026-10-02).
OLD_PERCENTILES = {"food": (0.248, 0.357, 0.486), "housing": (0.110, 0.289, 0.461),
                   "services": (0.244, 0.344, 0.461)}


def _households(n=1500, ranges=None):
    cfg = clone_config()
    if ranges:
        for cat, rng in ranges.items():
            setattr(cfg.households, f"{cat}_preference_range", rng)
    with use_config(cfg):
        return [HouseholdAgent(household_id=i, skills_level=0.5, age=30, cash_balance=100.0) for i in range(n)]


def test_preference_applied_once_is_default():
    assert CONFIG.households.fix_preference_applied_once is True


def test_budget_share_spread_matches_old_distribution():
    households = _households()
    # With the fix on the static fraction is category_weights as stored.
    shares = np.array([[h.category_weights[c] for c in CATS] for h in households])
    for j, cat in enumerate(CATS):
        p10, p50, p90 = np.percentile(shares[:, j], [10, 50, 90])
        old = OLD_PERCENTILES[cat]
        assert (p10, p50, p90) == pytest.approx(old, abs=0.03), cat
        assert p90 - p10 >= 0.9 * (old[2] - old[0]), cat  # spread kept


def test_wider_ranges_do_not_change_other_draws():
    new, old = _households(50), _households(50, OLD_RANGES)
    changed = {"food_preference", "housing_preference", "services_preference", "category_weights"}
    for a, b in zip(new, old):
        for field in dataclasses.fields(HouseholdAgent):
            if field.name not in changed:
                assert getattr(a, field.name) == getattr(b, field.name), field.name
