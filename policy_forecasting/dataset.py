"""Dataset construction and leakage exclusions."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from policy_forecasting.config import (
    HORIZON_TICKS,
    IDENTIFIER_COLUMNS,
    LABEL_COLUMNS,
    POLICY_STATE_COLUMNS,
)

NON_FEATURE_METADATA: tuple[str, ...] = ("split", "time_regime", "ci_block", "arm_id")


def read_ticks(path: str | Path) -> pd.DataFrame:
    """Read per-tick parquet rows."""
    return pd.read_parquet(path)


def build_supervised_frame(rows: pd.DataFrame, horizon: int = HORIZON_TICKS) -> pd.DataFrame:
    """Join tick-t rows to labels from tick t+horizon within the same run."""
    required = {"run_id", "policy_canonical", "seed", "tick", "unemployment_rate"}
    missing = required - set(rows.columns)
    if missing:
        raise ValueError(f"Missing required columns for supervised frame: {sorted(missing)}")

    distress_source = "consumer_distress" if "consumer_distress" in rows.columns else "mean_distress"
    if distress_source not in rows.columns:
        raise ValueError("Expected either consumer_distress or mean_distress column for distress labels")

    keys = ["run_id", "policy_canonical", "seed", "tick"]
    base = rows.copy()
    labels = rows[["run_id", "policy_canonical", "seed", "tick", "unemployment_rate", distress_source]].copy()
    labels["tick"] = labels["tick"] - int(horizon)
    labels = labels.rename(
        columns={
            "unemployment_rate": "unemployment_rate__t+8",
            distress_source: "consumer_distress__t+8",
        }
    )
    supervised = base.merge(labels, on=keys, how="inner", validate="one_to_one")
    supervised = supervised.sort_values(keys).reset_index(drop=True)
    return supervised


def leakage_exclusion_columns(columns: Iterable[str]) -> set[str]:
    """Return columns that are forbidden as model features."""
    excluded = set(IDENTIFIER_COLUMNS) | set(NON_FEATURE_METADATA)
    excluded.update(column for column in columns if column.endswith("__t+8"))
    return excluded


def feature_columns(frame: pd.DataFrame, *, include_policy_state: bool = True) -> list[str]:
    """Return leakage-safe feature column names."""
    excluded = leakage_exclusion_columns(frame.columns)
    if not include_policy_state:
        excluded.update(POLICY_STATE_COLUMNS)
    return [column for column in frame.columns if column not in excluded]


def build_feature_matrix(
    supervised: pd.DataFrame,
    *,
    include_policy_state: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return X and y using only tick-t features."""
    missing_labels = set(LABEL_COLUMNS) - set(supervised.columns)
    if missing_labels:
        raise ValueError(f"Missing label columns: {sorted(missing_labels)}")
    cols = feature_columns(supervised, include_policy_state=include_policy_state)
    return supervised[cols].copy(), supervised[list(LABEL_COLUMNS)].copy()


def no_policy_state_ablation(supervised: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the mandatory no-policy-state feature matrix variant."""
    return build_feature_matrix(supervised, include_policy_state=False)


def write_supervised_parquet(rows: pd.DataFrame, output_path: str | Path) -> Path:
    """Persist a supervised frame to parquet."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(path, index=False)
    return path


def main(argv: list[str] | None = None) -> int:
    """CLI for building a supervised frame from per-tick parquet."""
    import argparse

    parser = argparse.ArgumentParser(description="Build leakage-safe t+8 supervised frame.")
    parser.add_argument("input_parquet", type=Path)
    parser.add_argument("output_parquet", type=Path)
    parser.add_argument("--horizon", type=int, default=HORIZON_TICKS)
    args = parser.parse_args(argv)

    rows = read_ticks(args.input_parquet)
    supervised = build_supervised_frame(rows, horizon=args.horizon)
    write_supervised_parquet(supervised, args.output_parquet)
    print(f"Wrote {len(supervised)} supervised rows to {args.output_parquet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
