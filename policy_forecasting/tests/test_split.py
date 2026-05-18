import pandas as pd

from policy_forecasting.split import assign_splits


def test_assign_splits_are_disjoint_by_policy_seed_blocks():
    rows = []
    for policy in ["p0", "p1", "p2", "p3", "p4", "p5"]:
        for seed in [0, 1, 2, 3, 4, 5]:
            for tick in [0, 1]:
                rows.append({"policy_canonical": policy, "seed": seed, "tick": tick, "run_id": f"{policy}-{seed}"})

    split = assign_splits(pd.DataFrame(rows), final_policy_count=2, validation_seed_count=2)

    train_blocks = set(
        map(tuple, split[split["split"] == "train"][["policy_canonical", "seed"]].drop_duplicates().values)
    )
    validation_blocks = set(
        map(tuple, split[split["split"] == "validation"][["policy_canonical", "seed"]].drop_duplicates().values)
    )
    test_blocks = set(
        map(tuple, split[split["split"] == "final_test"][["policy_canonical", "seed"]].drop_duplicates().values)
    )

    assert train_blocks.isdisjoint(validation_blocks)
    assert train_blocks.isdisjoint(test_blocks)
    assert validation_blocks.isdisjoint(test_blocks)
    assert set(split[split["split"] == "final_test"]["policy_canonical"]) == {"p4", "p5"}
    assert set(split[split["split"] == "validation"]["seed"]) == {4, 5}


def test_time_regime_blocks_cover_early_mid_late_per_run():
    frame = pd.DataFrame(
        {
            "policy_canonical": ["p0"] * 9,
            "seed": [1] * 9,
            "run_id": ["r0"] * 9,
            "tick": list(range(9)),
        }
    )

    split = assign_splits(frame, final_policy_count=0, validation_seed_count=0)

    assert split["time_regime"].tolist() == [
        "early",
        "early",
        "early",
        "mid",
        "mid",
        "mid",
        "late",
        "late",
        "late",
    ]
    assert split["ci_block"].nunique() == 3
