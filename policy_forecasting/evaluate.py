"""Evaluation, uncertainty, and matched-seed treatment effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from policy_forecasting.config import LABEL_COLUMNS


@dataclass(frozen=True)
class BootstrapCI:
    """Mean and percentile confidence interval."""

    mean: float
    low: float
    high: float


def regression_metrics(y_true: pd.DataFrame, y_pred: pd.DataFrame) -> pd.DataFrame:
    """Compute MAE, RMSE, and R2 by target."""
    rows = []
    for column in LABEL_COLUMNS:
        true = y_true[column].astype(float).to_numpy()
        pred = y_pred[column].astype(float).to_numpy()
        err = pred - true
        mae = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err * err)))
        denom = float(np.sum((true - true.mean()) ** 2))
        r2 = 1.0 - float(np.sum(err * err)) / denom if denom > 0.0 else np.nan
        rows.append({"target": column, "mae": mae, "rmse": rmse, "r2": r2})
    return pd.DataFrame(rows)


def _blocked_bootstrap_means(
    values: pd.Series,
    blocks: pd.Series | None,
    *,
    n_boot: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if blocks is None:
        arr = values.astype(float).to_numpy()
        return np.array([rng.choice(arr, size=len(arr), replace=True).mean() for _ in range(n_boot)])

    data = pd.DataFrame({"value": values.astype(float), "block": blocks.astype(str)})
    block_values = [part["value"].to_numpy() for _, part in data.groupby("block", sort=True)]
    if not block_values:
        return np.array([], dtype=float)
    means = []
    for _ in range(n_boot):
        sampled = [block_values[idx] for idx in rng.integers(0, len(block_values), size=len(block_values))]
        means.append(float(np.concatenate(sampled).mean()))
    return np.array(means, dtype=float)


def paired_bootstrap_delta(
    y_true: pd.Series,
    model_pred: pd.Series,
    baseline_pred: pd.Series,
    *,
    blocks: pd.Series | None = None,
    n_boot: int = 2000,
    seed: int = 0,
) -> BootstrapCI:
    """CI for baseline absolute error minus model absolute error.

    Positive values mean the model improves over the baseline.
    """
    delta = (baseline_pred.astype(float) - y_true.astype(float)).abs() - (
        model_pred.astype(float) - y_true.astype(float)
    ).abs()
    boot = _blocked_bootstrap_means(delta, blocks, n_boot=n_boot, seed=seed)
    if boot.size == 0:
        return BootstrapCI(mean=float("nan"), low=float("nan"), high=float("nan"))
    return BootstrapCI(
        mean=float(delta.mean()),
        low=float(np.percentile(boot, 2.5)),
        high=float(np.percentile(boot, 97.5)),
    )


def compare_against_baselines(
    y_true: pd.DataFrame,
    predictions: dict[str, pd.DataFrame],
    *,
    baseline_names: Iterable[str] = ("persistence", "trend"),
    blocks: pd.Series | None = None,
) -> pd.DataFrame:
    """Return metrics plus paired bootstrap deltas against required baselines."""
    rows = []
    for model_name, pred in predictions.items():
        metrics = regression_metrics(y_true, pred)
        for _, metric_row in metrics.iterrows():
            row = {"model": model_name, **metric_row.to_dict()}
            for baseline_name in baseline_names:
                if baseline_name == model_name or baseline_name not in predictions:
                    continue
                ci = paired_bootstrap_delta(
                    y_true[metric_row["target"]],
                    pred[metric_row["target"]],
                    predictions[baseline_name][metric_row["target"]],
                    blocks=blocks,
                )
                prefix = f"delta_vs_{baseline_name}"
                row[f"{prefix}_mae_mean"] = ci.mean
                row[f"{prefix}_mae_ci_low"] = ci.low
                row[f"{prefix}_mae_ci_high"] = ci.high
                row[f"{prefix}_claim"] = bool(ci.low > 0.0 or ci.high < 0.0)
            rows.append(row)
    return pd.DataFrame(rows)


def paired_bootstrap_ci(values: np.ndarray, *, n_boot: int = 5000, seed: int = 0) -> BootstrapCI:
    """Bootstrap CI for a paired-delta mean."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return BootstrapCI(mean=float("nan"), low=float("nan"), high=float("nan"))
    rng = np.random.default_rng(seed)
    boot = np.array([rng.choice(arr, size=arr.size, replace=True).mean() for _ in range(n_boot)])
    return BootstrapCI(float(arr.mean()), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)))


def _adjust_pvalues(p_values: list[float], method: str) -> list[float]:
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    order = np.argsort(p)
    adjusted = np.empty(n, dtype=float)
    if method == "holm":
        running = 0.0
        for rank, idx in enumerate(order):
            value = min(1.0, (n - rank) * p[idx])
            running = max(running, value)
            adjusted[idx] = running
    elif method == "bh":
        running = 1.0
        for rank, idx in reversed(list(enumerate(order, start=1))):
            value = min(running, p[idx] * n / rank)
            running = value
            adjusted[idx] = value
    else:
        raise ValueError("method must be 'holm' or 'bh'")
    return adjusted.tolist()


def matched_treatment_effects(
    frame: pd.DataFrame,
    *,
    baseline_arm_id: str = "baseline",
    arm_col: str = "arm_id",
    outcomes: tuple[str, ...] = ("unemployment_rate__t+8", "consumer_distress__t+8"),
    determinism_noise_band: float | None = None,
) -> pd.DataFrame:
    """Compute matched-seed policy deltas vs baseline with Wilcoxon and bootstrap CI."""
    try:
        from scipy.stats import wilcoxon
    except Exception:
        wilcoxon = None

    required = {arm_col, "seed", *outcomes}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing treatment-effect columns: {sorted(missing)}")

    grouped = frame.groupby([arm_col, "seed"], sort=True)[list(outcomes)].mean().reset_index()
    baseline = grouped[grouped[arm_col] == baseline_arm_id].set_index("seed")
    rows = []
    raw_p: list[float] = []
    raw_index: list[int] = []

    for arm in sorted(value for value in grouped[arm_col].unique() if value != baseline_arm_id):
        arm_rows = grouped[grouped[arm_col] == arm].set_index("seed")
        matched = arm_rows.join(baseline, lsuffix="_arm", rsuffix="_base", how="inner")
        for outcome in outcomes:
            delta = (
                matched[f"{outcome}_arm"].astype(float) - matched[f"{outcome}_base"].astype(float)
            ).to_numpy()
            ci = paired_bootstrap_ci(delta)
            sd = float(np.std(delta, ddof=1)) if delta.size > 1 else float("nan")
            dz = float(ci.mean / sd) if sd and np.isfinite(sd) and sd > 0.0 else float("nan")
            if wilcoxon is not None and delta.size > 0 and np.any(delta != 0):
                p_value = float(wilcoxon(delta, zero_method="wilcox", alternative="two-sided").pvalue)
            else:
                p_value = 1.0
            row = {
                "arm_id": arm,
                "outcome": outcome,
                "n_matched_seeds": int(delta.size),
                "mean_delta": ci.mean,
                "ci_low": ci.low,
                "ci_high": ci.high,
                "wilcoxon_p": p_value,
                "dz": dz,
                "exploratory_small_effect": bool(np.isfinite(dz) and abs(dz) < 0.8),
                "exceeds_determinism_noise": (
                    None
                    if determinism_noise_band is None
                    else bool(abs(ci.mean) > float(determinism_noise_band))
                ),
            }
            raw_index.append(len(rows))
            raw_p.append(p_value)
            rows.append(row)

    holm = _adjust_pvalues(raw_p, "holm") if raw_p else []
    bh = _adjust_pvalues(raw_p, "bh") if raw_p else []
    for idx, holm_p, bh_p in zip(raw_index, holm, bh):
        rows[idx]["holm_p"] = holm_p
        rows[idx]["bh_p"] = bh_p
        rows[idx]["significance_claim"] = bool(
            holm_p < 0.05
            and bh_p < 0.05
            and not rows[idx]["exploratory_small_effect"]
            and (
                rows[idx]["exceeds_determinism_noise"] is None
                or rows[idx]["exceeds_determinism_noise"]
            )
        )
    return pd.DataFrame(rows)
