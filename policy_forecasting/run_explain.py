"""SHAP economic-finding runner for the winning GB unemployment forecaster.

Reuses the frozen split, fits the model suite on train, writes SHAP summary +
one economic finding for unemployment_rate__t+8 (the claim=True target).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from policy_forecasting.dataset import build_feature_matrix, build_supervised_frame, read_ticks
from policy_forecasting.explain import write_explanation
from policy_forecasting.models import fit_model_suite
from policy_forecasting.run_pipeline import _adaptive_split_sizes, attach_arm_id
from policy_forecasting.split import assign_splits, split_frames


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write SHAP economic finding for the GB unemployment model.")
    parser.add_argument("ticks_parquet", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args(argv)

    supervised = attach_arm_id(build_supervised_frame(read_ticks(args.ticks_parquet)))
    fp, vs = _adaptive_split_sizes(supervised)
    assigned = assign_splits(supervised, final_policy_count=fp, validation_seed_count=vs)
    parts = split_frames(assigned)
    train = parts.get("train", assigned.iloc[0:0])
    final = parts.get("final_test", parts.get("validation", assigned.iloc[0:0]))
    if len(train) == 0 or len(final) == 0:
        print("Insufficient train/final rows for SHAP.")
        return 1

    X_train, y_train = build_feature_matrix(train, include_policy_state=True)
    X_final, _ = build_feature_matrix(final, include_policy_state=True)
    suite = fit_model_suite(X_train, y_train)
    result = write_explanation(
        suite["gradient_boosting"],
        X_final,
        args.out_dir,
        target_index=0,
        target_name="unemployment_rate__t+8",
    )
    print(result["finding"])
    print(f"SHAP summary: {result['summary_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
