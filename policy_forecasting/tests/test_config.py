from policy_forecasting.config import (
    BASELINE_LEVERS,
    FROZEN_ARMS,
    canonical_policy_hash,
    resolve_levers,
)


def test_frozen_arms_are_six_distinct_canonical_vectors():
    canonicals = [canonical_policy_hash(resolve_levers(arm.levers)) for arm in FROZEN_ARMS]

    assert [arm.arm_id for arm in FROZEN_ARMS] == [
        "baseline",
        "wage_tax_high",
        "profit_tax_high",
        "benefit_high",
        "min_wage_high",
        "subsidy_food_25",
    ]
    assert len(set(canonicals)) == 6


def test_baseline_and_policy_deltas_match_schema():
    assert BASELINE_LEVERS["wage_tax_rate"] == 0.15
    assert BASELINE_LEVERS["profit_tax_rate"] == 0.20
    assert BASELINE_LEVERS["investment_tax_rate"] == 0.10
    assert BASELINE_LEVERS["benefit_level"] == "neutral"
    assert resolve_levers({"wage_tax_rate": 0.30})["wage_tax_rate"] == 0.30
    assert resolve_levers({"profit_tax_rate": 0.35})["profit_tax_rate"] == 0.35
    assert resolve_levers({"benefit_level": "high"})["benefit_level"] == "high"
    assert resolve_levers({"minimum_wage_policy": "high"})["minimum_wage_policy"] == "high"
    assert resolve_levers(
        {"sector_subsidy_target": "food", "sector_subsidy_level": 25}
    )["sector_subsidy_level"] == 25


def test_canonical_hash_uses_resolved_sorted_lever_vector_not_arm_id():
    from_delta = canonical_policy_hash({"wage_tax_rate": 0.30})
    from_resolved = canonical_policy_hash(resolve_levers({"wage_tax_rate": 0.30}))
    reordered = canonical_policy_hash(
        {"profit_tax_rate": 0.20, "wage_tax_rate": 0.30, "benefit_level": "neutral"}
    )

    assert from_delta == from_resolved
    assert from_delta == reordered
