# Policy Stress Testing and Forecasting V1

**Status:** V1 is implemented. This document records the design rationale, scope, validation rules, and caveats behind the confirm results in [policy_forecasting/RESULTS.md](../policy_forecasting/RESULTS.md). The frozen dataset contract is [POLICY_FORECASTING_SCHEMA.md](POLICY_FORECASTING_SCHEMA.md).

## One-Line Story

Build one deterministic 10,000-household policy-sweep dataset and use it for two linked deliverables: matched-seed policy-effect analysis and leakage-safe forecasting of future unemployment and consumer distress.

The guiding question:

> Can early labor, firm, household, fiscal, and policy signals forecast future economic stress under controlled policy interventions in a 10k-agent simulator?

## Scope

| Component | V1 decision |
|---|---|
| Dataset | One 10k-agent matched-seed sweep with per-tick economy, sector, firm, fiscal, policy, and household-aggregate features |
| Sweep harness | External `policy_forecasting/` package that imports `backend/` read-only and drives the simulator through public surfaces |
| Policies | 6 distinct lever-vector arms: baseline, high wage tax, high profit tax, high benefits, high minimum wage, and food subsidy |
| Seeds | 24 matched seeds for the confirm run |
| Horizon | `t+8` ticks |
| Forecast targets | `unemployment_rate__t+8` primary, `consumer_distress__t+8` secondary |
| Models | Policy-aware persistence, trend baseline, ElasticNet, and gradient boosting |
| Validation | Held-out canonical lever vectors, held-out seeds, features available at or before `t`, frozen final test |
| Explainability | SHAP summary for the best unemployment model |
| Demo | Small Streamlit surface for loading saved predictions and comparing deltas against baseline |

Out of scope for V1: LLM-in-the-loop policy selection, broad policy-space generalization, real-world macroeconomic forecasting, multi-horizon targets, and turning the forecaster into an autonomous policy advisor.

## Why This Design

The forecasting package lives outside the simulator core on purpose. It treats EcoSim as a frozen system under test, imports `backend/` read-only, and records one per-tick row per `(run_id, policy_canonical, seed, tick)`. That keeps the experiment focused on measured simulator behavior rather than model changes made to support the experiment.

Matched seeds are the main variance-control mechanism. A treatment run and baseline run with the same seed share initial household setup, firm setup, and stochastic sequence. That makes treatment-vs-baseline deltas much easier to interpret inside the simulator. This is still simulation treatment analysis, not real-world causality.

The forecast split holds out both seeds and canonical policy lever vectors. Policy state at tick `t` can be used as a feature because it is observable at that tick, but `policy_canonical`, `seed`, `tick`, `run_id`, and all `*__t+8` labels are excluded from the feature matrix. A no-policy-state ablation checks whether the unemployment result survives without current lever values.

The model set is deliberately modest. The dataset is tabular, small, and experiment-controlled, so persistence/trend baselines, ElasticNet, and gradient boosting are enough to test whether there is usable nonlinear structure without adding deep-learning complexity.

## Determinism Rule

Determinism is measured, not assumed. The confirm gate runs fresh-process baseline replicates with fixed environment settings and hashes the full per-tick manifest series.

Interpretation:

- If the replicate hashes match, matched-seed deltas are exact for the sweep.
- If they do not match, treatment effects must be interpreted against the measured replicate noise band.

The 10k confirm gate is binding. Smaller 2k runs are only smoke tests for the pipeline.

## Dataset Contract

The frozen schema is in [POLICY_FORECASTING_SCHEMA.md](POLICY_FORECASTING_SCHEMA.md). Key rules:

- One row per `(run_id, policy_canonical, seed, tick)`.
- No per-household rows are persisted; household state is represented by aggregates and distributional summaries.
- Labels are forward joins from `t+8`.
- Feature matrices exclude run identifiers, split identifiers, seed/tick identifiers, and future labels.
- `consumer_distress__t+8` uses a frozen formula with cash stress, food insecurity, health, and happiness components.

This keeps the dataset around tens of thousands of rows instead of hundreds of millions of household-level rows. Simulation CPU is the primary cost, not storage.

## Runtime Plan

| Stage | Purpose |
|---|---|
| 2k smoke | Validate the pipeline, schema conformance, leakage checks, and determinism harness quickly |
| 10k confirm | Produce headline numbers with 6 arms, 24 matched seeds, at least 80 ticks, and parallel execution across policy/seed runs |

The confirm run is the only source for published V1 metrics. The result file reports the final numbers and reproduction commands.

## Result Summary

The 10k confirm run passed the determinism gate with `hash_equal=True` and `max_abs_delta=0.0`.

Gradient boosting forecasted `unemployment@t+8` at `R^2=0.924` and beat the policy-aware persistence baseline by `0.080` MAE on held-out seeds and unseen policy lever vectors. The `consumer_distress@t+8` target did not beat persistence, which is reported as a negative result rather than tuned away.

Within the simulator, matched-seed policy effects showed that high minimum wage reduced later unemployment and distress, high benefits increased later unemployment, high wage tax increased distress, food subsidy reduced distress, and high profit tax showed no detectable household effect in this sweep.

## Caveats

- This is simulator system identification, not a real-world macro forecast.
- The generalization claim is narrow: held-out performance among 6 pre-registered policy interventions.
- Matched-seed treatment deltas isolate simulator policy effects, not real-world causal effects.
- The distress target is useful as a welfare proxy, but it did not beat persistence in V1.
- Results should be rerun if the base simulator behavior, policy schema, or feature contract changes.

## Result Summary

> Built a leakage-safe forecasting and matched-seed policy experiment pipeline on a deterministic 10k-agent economic simulator: gradient boosting predicts 8-tick-ahead unemployment at `R^2=0.92`, beating a policy-aware persistence baseline by `0.080` MAE on held-out seeds and unseen policy lever vectors; quantified 6 policy interventions with paired Wilcoxon tests under a byte-identical determinism gate.
