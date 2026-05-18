"""Thin Streamlit demo for saved policy forecasts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from policy_forecasting.config import FROZEN_ARMS


DEFAULT_PREDICTIONS = Path("policy_forecasting") / "artifacts" / "demo_predictions.parquet"


def _load_predictions(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    rows = []
    for idx, arm in enumerate(FROZEN_ARMS):
        rows.append(
            {
                "arm_id": arm.arm_id,
                "unemployment_rate__t+8": 0.0,
                "consumer_distress__t+8": 0.0,
                "delta_unemployment_vs_baseline": 0.0 if idx == 0 else None,
                "delta_distress_vs_baseline": 0.0 if idx == 0 else None,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="Policy Forecasting", layout="centered")
    st.title("Policy Forecasting")
    prediction_path = Path(
        st.sidebar.text_input("Predictions parquet", value=str(DEFAULT_PREDICTIONS))
    )
    predictions = _load_predictions(prediction_path)
    arm_ids = [arm.arm_id for arm in FROZEN_ARMS]
    selected = st.selectbox("Policy arm", arm_ids)
    row = predictions[predictions["arm_id"] == selected]
    if row.empty:
        st.error("Selected arm is missing from the predictions file.")
        return
    record = row.iloc[0]
    baseline = predictions[predictions["arm_id"] == "baseline"].iloc[0]
    unemployment = float(record["unemployment_rate__t+8"])
    distress = float(record["consumer_distress__t+8"])
    delta_unemployment = unemployment - float(baseline["unemployment_rate__t+8"])
    delta_distress = distress - float(baseline["consumer_distress__t+8"])
    c1, c2 = st.columns(2)
    c1.metric("t+8 unemployment", f"{unemployment:.3f}", f"{delta_unemployment:+.3f}")
    c2.metric("t+8 consumer distress", f"{distress:.3f}", f"{delta_distress:+.3f}")
    st.dataframe(predictions, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
