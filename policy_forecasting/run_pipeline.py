"""End-to-end analysis orchestrator: ticks parquet -> numbers JSON.

Chains the existing public module functions. No backend imports, no sweep here
(run sweep/wrapper.py first). Produces the headline persistence-beat metrics and
matched-seed treatment effects.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from policy_forecasting.config import FROZEN_ARMS, LABEL_COLUMNS
from policy_forecasting.dataset import (
    build_feature_matrix,
    build_supervised_frame,
    no_policy_state_ablation,
    read_ticks,
)
from policy_forecasting.evaluate import compare_against_baselines, matched_treatment_effects
from policy_forecasting.models import fit_model_suite, predict_frame
from policy_forecasting.split import assign_splits, split_frames

_CANON_TO_ARM = {arm.policy_canonical: arm.arm_id for arm in FROZEN_ARMS}


def attach_arm_id(supervised: pd.DataFrame) -> pd.DataFrame:
    """Map policy_canonical -> frozen arm_id (treatment-effect grouping key)."""
    frame = supervised.copy()
    frame["arm_id"] = frame["policy_canonical"].map(_CANON_TO_ARM)
    if frame["arm_id"].isna().any():
        unknown = sorted(frame.loc[frame["arm_id"].isna(), "policy_canonical"].unique())
        raise ValueError(f"Rows with unmapped policy_canonical: {unknown}")
    return frame


def _adaptive_split_sizes(supervised: pd.DataFrame) -> tuple[int, int]:
    n_seeds = supervised["seed"].nunique()
    n_policies = supervised["policy_canonical"].nunique()
    final_policy_count = 1 if n_policies >= 3 else 0
    validation_seed_count = max(1, n_seeds // 4) if n_seeds >= 2 else 0
    return final_policy_count, validation_seed_count


def _model_predictions(train: pd.DataFrame, final: pd.DataFrame, *, include_policy_state: bool) -> dict:
    from policy_forecasting.models import PersistenceBaseline, TrendBaseline

    X_train, y_train = build_feature_matrix(train, include_policy_state=include_policy_state)
    X_final, _ = build_feature_matrix(final, include_policy_state=include_policy_state)
    suite = fit_model_suite(X_train, y_train)
    predictions: dict[str, pd.DataFrame] = {
        "persistence": PersistenceBaseline().predict(final).set_axis(final.index),
        "trend": TrendBaseline().predict(final).set_axis(final.index),
    }
    for name in ("elastic_net", "gradient_boosting"):
        predictions[name] = predict_frame(suite[name], X_final).set_axis(final.index)
    return predictions


def run(ticks_parquet: Path, out_json: Path, *, determinism_json: Path | None = None) -> dict:
    rows = read_ticks(ticks_parquet)
    supervised = attach_arm_id(build_supervised_frame(rows))
    final_policy_count, validation_seed_count = _adaptive_split_sizes(supervised)
    assigned = assign_splits(
        supervised,
        final_policy_count=final_policy_count,
        validation_seed_count=validation_seed_count,
    )
    parts = split_frames(assigned)
    train = parts.get("train", assigned.iloc[0:0])
    final = parts.get("final_test", parts.get("validation", assigned.iloc[0:0]))

    result: dict = {
        "n_rows": int(len(assigned)),
        "n_train": int(len(train)),
        "n_final": int(len(final)),
        "split_sizes": {"final_policy_count": final_policy_count, "validation_seed_count": validation_seed_count},
    }

    if len(train) > 0 and len(final) > 0:
        y_true = final[list(LABEL_COLUMNS)]
        blocks = final["ci_block"] if "ci_block" in final.columns else None
        preds = _model_predictions(train, final, include_policy_state=True)
        result["headline_vs_baselines"] = compare_against_baselines(y_true, preds, blocks=blocks).to_dict("records")
        ablation_preds = _model_predictions(train, final, include_policy_state=False)
        result["no_policy_state_ablation"] = compare_against_baselines(
            y_true, ablation_preds, blocks=blocks
        ).to_dict("records")
    else:
        result["headline_vs_baselines"] = []
        result["no_policy_state_ablation"] = []
        result["warning"] = "Insufficient train/final rows for modeling (expected at tiny smoke scale)."

    noise_band = None
    if determinism_json and Path(determinism_json).exists():
        try:
            d = json.loads(Path(determinism_json).read_text(encoding="utf-8"))
            noise_band = float(d.get("max_replicate_delta", d.get("noise_band", 0.0)) or 0.0)
        except Exception:
            noise_band = None

    te = matched_treatment_effects(assigned, determinism_noise_band=noise_band)
    result["treatment_effects"] = te.to_dict("records")
    result["determinism_noise_band"] = noise_band

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the V1 analysis pipeline on a ticks parquet.")
    parser.add_argument("ticks_parquet", type=Path)
    parser.add_argument("out_json", type=Path)
    parser.add_argument("--determinism-json", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run(args.ticks_parquet, args.out_json, determinism_json=args.determinism_json)
    head = result.get("headline_vs_baselines", [])
    print(f"rows={result['n_rows']} train={result['n_train']} final={result['n_final']}")
    for row in head:
        if row.get("model") == "gradient_boosting":
            print(
                f"GB {row['target']}: MAE={row['mae']:.5f} "
                f"delta_vs_persistence_mae_mean={row.get('delta_vs_persistence_mae_mean')} "
                f"claim={row.get('delta_vs_persistence_claim')}"
            )
    print(f"Wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
