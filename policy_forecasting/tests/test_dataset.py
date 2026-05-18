import pandas as pd

from policy_forecasting.dataset import (
    IDENTIFIER_COLUMNS,
    build_supervised_frame,
    feature_columns,
)


def test_build_supervised_frame_joins_t_plus_horizon_and_drops_tail():
    rows = []
    for tick in range(10):
        rows.append(
            {
                "run_id": "run-a",
                "policy_canonical": "policy-a",
                "levers_json": "{}",
                "seed": 1,
                "tick": tick,
                "unemployment_rate": tick / 100.0,
                "mean_distress": tick / 10.0,
                "wage_tax_rate": 0.15,
            }
        )

    supervised = build_supervised_frame(pd.DataFrame(rows), horizon=3)

    assert supervised["tick"].tolist() == list(range(7))
    assert supervised.loc[0, "unemployment_rate__t+8"] == 0.03
    assert supervised.loc[0, "consumer_distress__t+8"] == 0.3


def test_feature_columns_enforce_leakage_exclusions_and_ablation():
    frame = pd.DataFrame(
        [
            {
                "run_id": "run-a",
                "policy_canonical": "policy-a",
                "levers_json": "{}",
                "seed": 1,
                "tick": 0,
                "unemployment_rate": 0.1,
                "unemployment_rate__t+8": 0.2,
                "consumer_distress__t+8": 0.3,
                "wage_tax_rate": 0.15,
                "sector_subsidy_target": "none",
                "sector_revenue_food": 10.0,
            }
        ]
    )

    with_policy = feature_columns(frame)
    no_policy = feature_columns(frame, include_policy_state=False)

    assert not set(IDENTIFIER_COLUMNS).intersection(with_policy)
    assert "unemployment_rate__t+8" not in with_policy
    assert "consumer_distress__t+8" not in with_policy
    assert "wage_tax_rate" in with_policy
    assert "sector_subsidy_target" in with_policy
    assert "wage_tax_rate" not in no_policy
    assert "sector_subsidy_target" not in no_policy
    assert "sector_revenue_food" in no_policy
