# Policy Forecasting V1 — Results (10k confirm)

Run: 6 frozen arms × 24 matched seeds × 80 ticks, 10k households. Sweep 11,520 tick rows, ~2.25 h. Pipeline: 10,368 supervised rows (train 6,480 / held-out final 1,728). Generated 2026-05-17.

## Determinism gate (binding, 10k) — PASSED

Two fresh-process baseline replicates at 10k/80 ticks: `hash_equal=True`, `max_abs_delta=0.0` across all per-tick metrics. EcoSim is byte-deterministic given seed+policy. Matched-seed treatment deltas are therefore exact (noise band = 0.0); no base RNG was modified.

## Forecasting (leakage-safe: features ≤ t, labels t+8, held-out seeds AND held-out canonical lever vectors)

| model | target | R² | MAE | ΔMAE vs persistence | 95% CI | beats persistence |
|---|---|---|---|---|---|---|
| **gradient_boosting** | **unemployment@t+8** | **0.924** | **0.028** | **+0.080** | **[0.056, 0.107]** | **YES** |
| elastic_net | unemployment@t+8 | 0.277 | 0.103 | +0.006 | [-0.027, 0.041] | no |
| gradient_boosting | consumer_distress@t+8 | -0.056 | 0.029 | +0.003 | [-0.005, 0.012] | no |
| elastic_net | consumer_distress@t+8 | -0.455 | 0.035 | -0.003 | [-0.011, 0.006] | no |

- **Headline:** gradient boosting forecasts t+8 unemployment at R²=0.92 and beats the policy-aware persistence baseline by 0.080 MAE (95% CI clears zero), on held-out seeds and held-out lever vectors. **Robust to the no-policy-state ablation** (claim still True) — not memorizing policy identity.
- **Honest null:** consumer distress at t+8 is not forecastable better than persistence here (near-random-walk); linear ElasticNet cannot beat persistence on either target → the gain is nonlinear structure, not trend.

## SHAP economic finding (GB unemployment model)

`gdp_ma4` dominates (mean|SHAP| 0.080 vs next 0.007 — ~10×), then `fiscal_stress`, `benefit_level=high`, `gov_cash`, `bankruptcies_tick`. **The 4-tick GDP trajectory foreshadows unemployment ~8 ticks ahead** — a leading demand signal persistence cannot see, which is exactly why GB beats it.

## Matched-seed policy effects (24 paired seeds, Wilcoxon signed-rank, Holm-corrected; deltas exact, determinism noise 0)

| arm | outcome | mean Δ vs baseline | 95% CI | Holm p | dz | verdict |
|---|---|---|---|---|---|---|
| min_wage_high | unemployment@t+8 | −0.021 | [−0.022,−0.019] | <0.001 | −6.0 | **significant** |
| min_wage_high | distress@t+8 | −0.026 | [−0.027,−0.025] | <0.001 | −11.1 | **significant** |
| benefit_high | unemployment@t+8 | +0.073 | [0.067, 0.078] | <0.001 | 5.2 | **significant** |
| benefit_high | distress@t+8 | +0.009 | [0.006, 0.011] | <0.001 | 1.4 | **significant** |
| wage_tax_high | distress@t+8 | +0.040 | [0.039, 0.040] | <0.001 | 22.3 | **significant** |
| subsidy_food_25 | distress@t+8 | −0.012 | [−0.013,−0.011] | <0.001 | −5.2 | **significant** |
| profit_tax_high | both | ~0 | — | 1.0 | ~0 | null (honest) |
| wage_tax_high / subsidy | unemployment@t+8 | ~0 | — | 1.0 | ~0 | null (honest) |

Mechanisms (within-simulator, not real-world causal): higher minimum wage → demand-side boost → lower unemployment & distress; higher benefits → higher t+8 unemployment; wage tax → household disposable-income loss → higher distress; food subsidy → lower distress; profit tax → no detectable household effect.

## Resume bullet (quantified)

> Built a leakage-safe forecasting + matched-seed policy-experiment pipeline on a deterministic 10k-agent economic simulator: gradient boosting predicts 8-tick-ahead unemployment at R²=0.92, beating a policy-aware persistence baseline by 0.080 MAE (95% CI [0.056, 0.107]) on held-out seeds and unseen policy lever vectors; quantified 6 policy interventions with paired Wilcoxon tests under a byte-identical determinism gate (Holm-corrected, dz up to 22).

Honest framing for interviews: simulator system identification, not real-world macro prediction. Validity rests on leakage-safe held-out splits + a passing byte-identical determinism gate, not the model choice.

## Reproduce

```
python -m policy_forecasting.sweep.wrapper --confirm-seeds --households 10000 --ticks 80 --processes 8 --output policy_forecasting/artifacts/confirm10k_ticks.parquet
python -m policy_forecasting.dataset      policy_forecasting/artifacts/confirm10k_ticks.parquet policy_forecasting/artifacts/confirm10k_supervised.parquet
python -m policy_forecasting.determinism  --arm baseline --seed 0 --households 10000 --ticks 80 --output policy_forecasting/artifacts/determinism_confirm10k.json
python -m policy_forecasting.run_pipeline policy_forecasting/artifacts/confirm10k_ticks.parquet policy_forecasting/artifacts/confirm10k_result.json --determinism-json policy_forecasting/artifacts/determinism_confirm10k.json
python -m policy_forecasting.run_explain  policy_forecasting/artifacts/confirm10k_ticks.parquet policy_forecasting/artifacts/explain
```
