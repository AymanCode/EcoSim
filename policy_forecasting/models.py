"""Forecast models and baselines for t+8 stress outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from policy_forecasting.config import LABEL_COLUMNS


def _current_distress_column(frame: pd.DataFrame) -> str:
    if "mean_distress" in frame.columns:
        return "mean_distress"
    if "consumer_distress" in frame.columns:
        return "consumer_distress"
    raise ValueError("Frame needs mean_distress or consumer_distress for baseline prediction")


@dataclass
class PersistenceBaseline:
    """Policy-aware persistence baseline: t+8 equals current observed state."""

    target_columns: tuple[str, str] = LABEL_COLUMNS

    def fit(self, X: pd.DataFrame, y: pd.DataFrame | None = None) -> "PersistenceBaseline":
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        distress_col = _current_distress_column(X)
        return pd.DataFrame(
            {
                self.target_columns[0]: X["unemployment_rate"].astype(float).to_numpy(),
                self.target_columns[1]: X[distress_col].astype(float).to_numpy(),
            },
            index=X.index,
        )


@dataclass
class TrendBaseline:
    """One-step trend extrapolation within each policy-seed run."""

    lag: int = 1
    target_columns: tuple[str, str] = LABEL_COLUMNS

    def fit(self, X: pd.DataFrame, y: pd.DataFrame | None = None) -> "TrendBaseline":
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        required = {"run_id", "policy_canonical", "seed", "tick", "unemployment_rate"}
        missing = required - set(X.columns)
        if missing:
            raise ValueError(f"TrendBaseline missing columns: {sorted(missing)}")
        distress_col = _current_distress_column(X)
        ordered = X.sort_values(["run_id", "policy_canonical", "seed", "tick"]).copy()
        group_cols = ["run_id", "policy_canonical", "seed"]
        for source, target in (("unemployment_rate", self.target_columns[0]), (distress_col, self.target_columns[1])):
            diff = ordered.groupby(group_cols)[source].diff(self.lag).fillna(0.0)
            ordered[target] = (ordered[source].astype(float) + diff.astype(float)).round(12)
        return ordered.sort_index()[list(self.target_columns)]


def _preprocessor(X: pd.DataFrame) -> Any:
    """Build a sklearn column transformer for numeric and categorical features."""
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    categorical = [column for column in X.columns if X[column].dtype == "object" or str(X[column].dtype) == "category"]
    numeric = [column for column in X.columns if column not in categorical]
    try:
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        encoder = OneHotEncoder(handle_unknown="ignore", sparse=False)
    return ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]),
                numeric,
            ),
            (
                "cat",
                Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", encoder)]),
                categorical,
            ),
        ],
        remainder="drop",
    )


def make_elastic_net(X: pd.DataFrame, *, random_state: int = 0) -> Any:
    """Create an ElasticNet multi-output pipeline."""
    from sklearn.linear_model import ElasticNet
    from sklearn.multioutput import MultiOutputRegressor
    from sklearn.pipeline import Pipeline

    return Pipeline(
        [
            ("prep", _preprocessor(X)),
            (
                "model",
                MultiOutputRegressor(
                    ElasticNet(alpha=0.02, l1_ratio=0.4, max_iter=20_000, random_state=random_state)
                ),
            ),
        ]
    )


def make_gradient_boosting(X: pd.DataFrame, *, random_state: int = 0) -> Any:
    """Create a gradient boosting multi-output pipeline."""
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.multioutput import MultiOutputRegressor
    from sklearn.pipeline import Pipeline

    return Pipeline(
        [
            ("prep", _preprocessor(X)),
            (
                "model",
                MultiOutputRegressor(
                    GradientBoostingRegressor(
                        random_state=random_state,
                        n_estimators=180,
                        learning_rate=0.04,
                        max_depth=3,
                    )
                ),
            ),
        ]
    )


def fit_model_suite(
    X_train: pd.DataFrame,
    y_train: pd.DataFrame,
    *,
    random_state: int = 0,
) -> dict[str, Any]:
    """Fit baselines plus the two sklearn models."""
    models: dict[str, Any] = {
        "persistence": PersistenceBaseline().fit(X_train, y_train),
        "trend": TrendBaseline().fit(X_train, y_train),
    }
    for name, model in {
        "elastic_net": make_elastic_net(X_train, random_state=random_state),
        "gradient_boosting": make_gradient_boosting(X_train, random_state=random_state),
    }.items():
        model.fit(X_train, y_train)
        models[name] = model
    return models


def predict_frame(model: Any, X: pd.DataFrame) -> pd.DataFrame:
    """Return predictions as a labeled DataFrame."""
    pred = model.predict(X)
    if isinstance(pred, pd.DataFrame):
        return pred[list(LABEL_COLUMNS)]
    array = np.asarray(pred, dtype=float)
    return pd.DataFrame(array, columns=list(LABEL_COLUMNS), index=X.index)
