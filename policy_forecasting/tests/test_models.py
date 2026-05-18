import pandas as pd

from policy_forecasting.models import PersistenceBaseline, TrendBaseline


def test_persistence_baseline_predicts_current_observed_targets():
    frame = pd.DataFrame(
        {
            "unemployment_rate": [0.1, 0.2],
            "mean_distress": [0.3, 0.4],
        }
    )

    preds = PersistenceBaseline().fit(frame, frame).predict(frame)

    assert preds["unemployment_rate__t+8"].tolist() == [0.1, 0.2]
    assert preds["consumer_distress__t+8"].tolist() == [0.3, 0.4]


def test_trend_baseline_extrapolates_within_run_policy_seed_order():
    frame = pd.DataFrame(
        {
            "run_id": ["r0", "r0", "r0"],
            "policy_canonical": ["p0", "p0", "p0"],
            "seed": [1, 1, 1],
            "tick": [0, 1, 2],
            "unemployment_rate": [0.10, 0.20, 0.25],
            "mean_distress": [0.30, 0.40, 0.45],
        }
    )

    preds = TrendBaseline(lag=1).fit(frame, frame).predict(frame)

    assert preds["unemployment_rate__t+8"].tolist() == [0.10, 0.30, 0.30]
    assert preds["consumer_distress__t+8"].tolist() == [0.30, 0.50, 0.50]
