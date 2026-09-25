"""Smoke test for the newcomer-scale policy-arm benchmark tool."""

import csv

import pytest

from config import CONFIG
from tools.benchmarks import run_newcomer_smoke as smoke


def test_baseline_arm_writes_tick_csv_and_summary(tmp_path):
    sequence_before = CONFIG.payment_sequence
    seed_before = CONFIG.random_seed

    exit_code = smoke.main([
        "--households", "200",
        "--ticks", "6",
        "--firms-per-category", "2",
        "--arms", "baseline",
        "--output-dir", str(tmp_path),
    ])

    assert exit_code == 0
    tick_csv = tmp_path / "baseline_seed1337_legacy_hh200.csv"
    with tick_csv.open(newline="", encoding="utf-8") as handle:
        lines = list(csv.reader(handle))
    assert len(lines) == 7  # header plus one row per tick
    header = lines[0]
    for column in ("unemployment_rate", "mean_wage", "median_wage", "sector_price_food", "gov_cash",
                   "total_firms", "mean_distress", "homeless_household_count", "public_works_jobs"):
        assert column in header
    assert (tmp_path / "summary.md").exists()
    assert (tmp_path / "baseline_seed1337_legacy_hh200_meta.json").exists()
    # The run happens in a cloned config context and must not leak into the process default.
    assert CONFIG.payment_sequence == sequence_before
    assert CONFIG.random_seed == seed_before


def test_public_works_arm_validates_against_policy_schema():
    arms = smoke.resolve_arms(["public_works_on"])
    assert dict(arms[0].levers) == {"public_works": "on"}
    with pytest.raises(ValueError):
        smoke.validate_levers({"public_works": "maybe"})
    with pytest.raises(ValueError):
        smoke.resolve_arms(["not_an_arm"])
