# Policy Forecasting V1 Results (10k Confirm)

Run summary: 6 frozen policy arms x 24 matched seeds x 80 ticks on a 10,000-household simulator. The sweep produced 11,520 per-tick rows in about 2.25 hours. The supervised forecasting frame contains 10,368 rows: 6,480 train rows and 1,728 held-out final rows. Generated 2026-05-17.

This is simulator system identification, not a real-world macroeconomic forecast. The claim rests on deterministic replay, matched seeds, leakage-safe labels, held-out seeds, held-out policy lever vectors, and baseline comparisons.

## Determinism Gate

**Passed.** Two fresh-process 10k/80-tick baseline replicates returned `hash_equal=True` and `max_abs_delta=0.0` across all per-tick metrics. EcoSim is byte-deterministic for a fixed seed and policy, so matched-seed treatment deltas are exact in this sweep. No base RNG code was modified for this result.

## Forecasting

Features use information available at or before tick `t`; labels are joined from `t+8`. The final test holds out both seeds and canonical policy lever vectors.

| Model | Target | R^2 | MAE | MAE lift vs persistence | 95% CI | Beats persistence |
|---|---|---:|---:|---:|---|---|
| **Gradient boosting** | **unemployment@t+8** | **0.924** | **0.028** | **+0.080** | **[0.056, 0.107]** | **yes** |
| ElasticNet | unemployment@t+8 | 0.277 | 0.103 | +0.006 | [-0.027, 0.041] | no |
| Gradient boosting | consumer_distress@t+8 | -0.056 | 0.029 | +0.003 | [-0.005, 0.012] | no |
| ElasticNet | consumer_distress@t+8 | -0.455 | 0.035 | -0.003 | [-0.011, 0.006] | no |

Key takeaways:

- Gradient boosting forecasts `unemployment@t+8` at `R^2=0.924` and beats the policy-aware persistence baseline by `0.080` MAE. The 95% CI clears zero.
- The unemployment result survives the no-policy-state ablation, so it is not just memorizing policy identity.
- `consumer_distress@t+8` does not beat persistence in this sweep. That negative result is useful: the distress target behaves closer to a persistence-dominated series here.
- ElasticNet does not beat persistence on either target, which points to nonlinear structure rather than a simple trend.

## Model Interpretation

For the gradient-boosting unemployment model, `gdp_ma4` dominates the SHAP ranking: mean absolute SHAP of `0.080` versus `0.007` for the next feature. The 4-tick GDP trajectory is the leading demand signal that the persistence baseline cannot see.

## Matched-Seed Policy Effects

Policy effects are paired against baseline across 24 matched seeds with Wilcoxon signed-rank tests and Holm correction. Deltas are exact because the 10k determinism gate passed with zero measured replicate noise.

| Arm | Outcome | Mean delta vs baseline | 95% CI | Holm p | dz | Verdict |
|---|---|---:|---|---:|---:|---|
| `min_wage_high` | unemployment@t+8 | -0.021 | [-0.022, -0.019] | <0.001 | -6.0 | significant |
| `min_wage_high` | distress@t+8 | -0.026 | [-0.027, -0.025] | <0.001 | -11.1 | significant |
| `benefit_high` | unemployment@t+8 | +0.073 | [0.067, 0.078] | <0.001 | 5.2 | significant |
| `benefit_high` | distress@t+8 | +0.009 | [0.006, 0.011] | <0.001 | 1.4 | significant |
| `wage_tax_high` | distress@t+8 | +0.040 | [0.039, 0.040] | <0.001 | 22.3 | significant |
| `subsidy_food_25` | distress@t+8 | -0.012 | [-0.013, -0.011] | <0.001 | -5.2 | significant |
| `profit_tax_high` | both | ~0 | n/a | 1.0 | ~0 | no detectable effect |
| `wage_tax_high` / subsidy | unemployment@t+8 | ~0 | n/a | 1.0 | ~0 | no detectable effect |

Within this simulator, higher minimum wage reduced later unemployment and distress; higher benefits increased later unemployment; higher wage tax increased distress; food subsidy reduced distress; and high profit tax showed no detectable household effect in this sweep.

## Reusable Summary

> Built a leakage-safe forecasting and matched-seed policy experiment pipeline on a deterministic 10k-agent economic simulator: gradient boosting predicts 8-tick-ahead unemployment at `R^2=0.92`, beating a policy-aware persistence baseline by `0.080` MAE on held-out seeds and unseen policy lever vectors; quantified 6 policy interventions with paired Wilcoxon tests under a byte-identical determinism gate.

## Reproduce

```bash
python -m policy_forecasting.sweep.wrapper --confirm-seeds --households 10000 --ticks 80 --processes 8 --output policy_forecasting/artifacts/confirm10k_ticks.parquet
python -m policy_forecasting.dataset policy_forecasting/artifacts/confirm10k_ticks.parquet policy_forecasting/artifacts/confirm10k_supervised.parquet
python -m policy_forecasting.determinism --arm baseline --seed 0 --households 10000 --ticks 80 --output policy_forecasting/artifacts/determinism_confirm10k.json
python -m policy_forecasting.run_pipeline policy_forecasting/artifacts/confirm10k_ticks.parquet policy_forecasting/artifacts/confirm10k_result.json --determinism-json policy_forecasting/artifacts/determinism_confirm10k.json
python -m policy_forecasting.run_explain policy_forecasting/artifacts/confirm10k_ticks.parquet policy_forecasting/artifacts/explain
```
