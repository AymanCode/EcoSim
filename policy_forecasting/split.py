"""Train, validation, and frozen final-test split protocol."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SplitSpec:
    """Deterministic split sizes over sorted policies and seeds."""

    final_policy_count: int = 1
    validation_seed_count: int = 4


def _tail(values: list, count: int) -> set:
    if count <= 0:
        return set()
    if count >= len(values):
        return set(values)
    return set(values[-count:])


def _time_regimes(frame: pd.DataFrame) -> pd.Series:
    """Per-run early/mid/late regime by tick position fraction, aligned to frame.index."""
    if frame.empty:
        return pd.Series([], index=frame.index, dtype=object)
    order = frame.sort_values(["run_id", "tick"])
    pos = order.groupby("run_id", sort=False).cumcount()
    size = order.groupby("run_id", sort=False)["tick"].transform("size")
    frac = pos / size.where(size > 0, 1)
    regime = pd.cut(
        frac,
        bins=[-0.1, 1.0 / 3.0, 2.0 / 3.0, 1.1],
        labels=["early", "mid", "late"],
        right=False,
    ).astype(str)
    regime.index = order.index
    return regime.reindex(frame.index)


def assign_splits(
    frame: pd.DataFrame,
    *,
    final_policy_count: int = 1,
    validation_seed_count: int = 4,
) -> pd.DataFrame:
    """Assign disjoint train, validation, and frozen final-test blocks.

    Final-test policies are held out as lever vectors. Validation uses held-out
    seeds only on non-final policies, so no `(policy_canonical, seed)` block is
    shared across splits.
    """
    required = {"policy_canonical", "seed", "run_id", "tick"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing split columns: {sorted(missing)}")

    result = frame.copy()
    policies = sorted(result["policy_canonical"].dropna().unique().tolist())
    seeds = sorted(result["seed"].dropna().unique().tolist())
    final_policies = _tail(policies, final_policy_count)
    validation_seeds = _tail(seeds, validation_seed_count)

    result["split"] = "train"
    final_mask = result["policy_canonical"].isin(final_policies)
    validation_mask = (~final_mask) & result["seed"].isin(validation_seeds)
    result.loc[validation_mask, "split"] = "validation"
    result.loc[final_mask, "split"] = "final_test"

    result["time_regime"] = _time_regimes(result)
    result["ci_block"] = result["run_id"].astype(str) + ":" + result["time_regime"].astype(str)
    return result


def split_frames(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return split name to frame mapping."""
    if "split" not in frame.columns:
        raise ValueError("Expected a split column. Call assign_splits first.")
    return {name: part.copy() for name, part in frame.groupby("split", sort=True)}
