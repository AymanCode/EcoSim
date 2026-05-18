"""SHAP explanation helpers for the gradient boosting forecaster."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _feature_names(pipeline: Any, X: pd.DataFrame) -> list[str]:
    prep = pipeline.named_steps.get("prep")
    if prep is None:
        return list(X.columns)
    try:
        return prep.get_feature_names_out().tolist()
    except Exception:
        return list(X.columns)


def shap_summary(
    gradient_boosting_pipeline: Any,
    X: pd.DataFrame,
    *,
    target_index: int = 0,
    max_rows: int = 1000,
) -> pd.DataFrame:
    """Return mean absolute SHAP values for one gradient-boosting target."""
    import numpy as np
    import shap

    sample = X.head(max_rows).copy()
    prep = gradient_boosting_pipeline.named_steps["prep"]
    model = gradient_boosting_pipeline.named_steps["model"].estimators_[target_index]
    transformed = prep.transform(sample)
    feature_names = _feature_names(gradient_boosting_pipeline, sample)
    explainer = shap.TreeExplainer(model)
    values = explainer.shap_values(transformed)
    mean_abs = np.abs(values).mean(axis=0)
    return (
        pd.DataFrame({"feature": feature_names, "mean_abs_shap": mean_abs})
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )


def economic_finding(summary: pd.DataFrame, *, target_name: str) -> str:
    """Emit one compact economic finding from SHAP rankings."""
    if summary.empty:
        return f"No SHAP finding available for {target_name}."
    top = summary.iloc[0]
    feature = str(top["feature"])
    return (
        f"For {target_name}, the strongest gradient-boosting signal in this run is "
        f"{feature}, ranked by mean absolute SHAP value. Treat this as simulator "
        "system identification, not a real-world causal claim."
    )


def write_explanation(
    gradient_boosting_pipeline: Any,
    X: pd.DataFrame,
    output_dir: str | Path,
    *,
    target_index: int = 0,
    target_name: str = "unemployment_rate__t+8",
) -> dict[str, Path | str]:
    """Write SHAP summary CSV and one economic-finding text file."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = shap_summary(gradient_boosting_pipeline, X, target_index=target_index)
    csv_path = out / f"shap_{target_name}.csv"
    finding_path = out / f"economic_finding_{target_name}.txt"
    summary.to_csv(csv_path, index=False)
    finding = economic_finding(summary, target_name=target_name)
    finding_path.write_text(finding + "\n", encoding="utf-8")
    return {"summary_csv": csv_path, "finding": finding, "finding_path": finding_path}
