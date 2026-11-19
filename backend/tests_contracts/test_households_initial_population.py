"""Plan 2 isolated checks; every economy explicitly uses income_first."""
import hashlib
import json
import random
import statistics

import numpy as np
import pytest

from config import clone_config, use_config, validate_initial_population_settings
from tools.runners.run_large_simulation import _allocate_initial_cash, create_large_economy


def build(enabled, n=1000, seed=42):
    config = clone_config()
    config.payment_sequence = "income_first"
    config.random_seed = seed
    config.households.realistic_initial_population = enabled
    with use_config(config):
        random.seed(seed)
        np.random.seed(seed)
        economy = create_large_economy(n, 5)
        rng = (random.getstate(), np.random.get_state())
    return economy, rng


def opening_payload(economy):
    return {
        "households": [(h.household_id, h.skills_level, h.age, h.cash_balance) for h in economy.households],
        "owners": [(f.firm_id, f.owners) for f in economy.firms + economy.queued_firms],
        "queued": [f.firm_id for f in economy.queued_firms],
    }


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


@pytest.fixture(scope="module")
def pair():
    off, rng_off = build(False)
    on, rng_on = build(True)
    return off, on, rng_off, rng_on


def test_default_off_preserves_opening_vectors_and_pinned_ownership(pair):
    off = pair[0]
    assert clone_config().households.realistic_initial_population is False
    assert [(h.skills_level, h.age, h.cash_balance) for h in off.households] == [
        (min(0.95, 0.2 + (i / 1000) * 0.75), 22 + i % 40, 500.0 + i % 100 * 15.0)
        for i in range(1000)
    ]
    # SHA-256 of the full vector, ordered owner lists, and queued IDs at 5c66095.
    assert digest(opening_payload(off)) == "77bb0cb35ae0f16e9b137c9d33ab7fcf98e1850a5af9ad6f0efa9d0e866a4735"


@pytest.mark.parametrize("n", [1000, 997])
def test_water_fill_exact_total_final_mean_cap_ledger_and_outliers(n):
    total_units = 128 * sum(500 + 15 * (i % 100) for i in range(n))
    weights = [1.0] * n
    weights[:4] = [1e10, 1e8, 1e6, 1e4]
    cash = _allocate_initial_cash(weights, total_units, 5.0)
    assert sum(cash) == total_units / 128
    assert max(cash) <= 5 * (total_units / 128) / n
    assert all(value * 128 == int(value * 128) for value in cash)
    economy, _ = build(True, n)
    assert sum(h.cash_balance for h in economy.households) == total_units / 128
    assert all(h.cash_balance <= 50 * (total_units / 128) / n for h in economy.households)
    assert all(h.ledger_cash_start == h.cash_balance for h in economy.households)


def test_distribution_doctors_and_same_seed(pair):
    on = pair[1]
    skills = [h.skills_level for h in on.households]
    cash = [h.cash_balance for h in on.households]
    assert all(0.2 <= skill <= 0.95 for skill in skills)
    assert statistics.mean(skills) == pytest.approx(0.575, abs=0.02)
    assert statistics.mean(cash) / statistics.median(cash) > 4
    assert 0.15 <= sum(value < 40 for value in cash) / len(cash) <= 0.35
    rank = np.argsort(np.argsort(skills))
    assert abs(np.corrcoef(np.arange(len(skills)), rank)[0, 1]) < 0.1
    assert all(22 <= h.age <= 61 for h in on.households)
    doctor_ids = {h.household_id for h in on.households if h.medical_training_status == "doctor"}
    assert len(doctor_ids) == 20
    assert doctor_ids == {h.household_id for h in sorted(on.households, key=lambda h: h.skills_level, reverse=True)[:20]}
    repeat, _ = build(True)
    assert opening_payload(on) == opening_payload(repeat)


def test_private_stream_preserves_rng_owners_and_queued_firms_at_default_research(pair):
    off, on, rng_off, rng_on = pair
    assert rng_off[0] == rng_on[0]
    assert rng_off[1][0] == rng_on[1][0]
    assert np.array_equal(rng_off[1][1], rng_on[1][1])
    assert rng_off[1][2:] == rng_on[1][2:]
    assert [(f.firm_id, f.owners, f.quality_level) for f in off.firms + off.queued_firms] == [
        (f.firm_id, f.owners, f.quality_level) for f in on.firms + on.queued_firms]
    assert [f.firm_id for f in off.queued_firms] == [f.firm_id for f in on.queued_firms]


def test_invalid_overrides_and_infeasible_cap():
    config = clone_config()
    for name, value in [("realistic_initial_population", 1), ("initial_skill_beta", (0, 2)),
                        ("initial_skill_beta", (2, float("nan"))), ("initial_savings_sigma", -1),
                        ("initial_savings_sigma", float("inf")), ("initial_savings_cap_multiple", 0)]:
        current = getattr(config.households, name)
        setattr(config.households, name, value)
        with pytest.raises(ValueError):
            validate_initial_population_settings(config.households)
        setattr(config.households, name, current)
    with pytest.raises(ValueError, match="cannot accommodate"):
        _allocate_initial_cash([1.0] * 997, 128 * sum(500 + 15 * (i % 100) for i in range(997)), 1.0)
    config.payment_sequence = "income_first"
    config.households.realistic_initial_population = True
    config.households.initial_savings_cap_multiple = 0.9
    with use_config(config), pytest.raises(ValueError, match="cannot accommodate"):
        create_large_economy(997, 5)


def test_water_fill_caps_multiple_outliers_and_breaks_remainder_ties_by_id():
    assert _allocate_initial_cash([1000, 100, 1, 1, 1], 103, 2) == [41 / 128, 41 / 128, 7 / 128, 7 / 128, 7 / 128]
    assert _allocate_initial_cash([1, 1, 1], 11, 1.2) == [4 / 128, 4 / 128, 3 / 128]
