"""Founder influence belongs to every starting product, within the entry bounds."""

import math
import statistics

import pytest

from firm_research import sample_entry_quality


def test_later_founder_skill_changes_expected_start_without_passing_the_frontier():
    means = []
    for skill in (0.1, 0.9):
        draws = [sample_entry_quality(seed=42, identity=f"entry:{i}:100",
            peer_qualities=[1.0, 2.0, 3.0], founder_skill=skill) for i in range(1000)]
        assert all(1.5 <= q <= 2.4 for q in draws)
        means.append(statistics.fmean(draws))
    assert means[1] - means[0] > 0.03


@pytest.mark.parametrize("skill", [math.nan, math.inf, -math.inf])
def test_later_entry_does_not_ignore_invalid_founder_skill(skill):
    with pytest.raises(ValueError, match="founder skill"):
        sample_entry_quality(seed=42, identity="entry:1:100",
                             peer_qualities=[1.0, 2.0], founder_skill=skill)
