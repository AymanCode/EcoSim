# EcoSim Policy Forecasting V1

Policy Forecasting V1 answers one narrow question: within EcoSim's frozen
10k-agent simulator, can early labor, demand, welfare, firm, fiscal, and policy
signals forecast unemployment and consumer distress eight ticks ahead under six
pre-registered interventions? The approach is deliberately external to the
simulator. This package imports `backend/` read-only, applies frozen government
lever deltas through the public `GovernmentAgent.set_lever()` API, snapshots one
per-tick economy row per `(run_id, policy_canonical, seed, tick)`, then builds a
leakage-safe supervised frame. Models are compared against policy-aware
persistence and trend baselines with blocked paired-bootstrap intervals; matched
policy effects are paired by seed and checked against a measured determinism
noise band. Result: this directory contains complete runnable code for the V1
smoke and confirm workflows, without modifying the frozen simulator or claiming
real-world macroeconomic transfer.

```
frozen backend/ Economy
        |
        v
sweep/wrapper.py -- public API only
        |
        v
per-tick parquet manifest
        |
        +--> determinism.py replicate hash/noise report
        |
        v
dataset.py t+8 labels, leakage exclusions
        |
        +--> split.py disjoint policy/seed blocks
        |
        v
models.py -> evaluate.py -> explain.py -> demo/app.py
```

## Install

From the repository root:

```powershell
py -3 -m venv policy_forecasting\.venv
policy_forecasting\.venv\Scripts\Activate.ps1
python -m pip install -r policy_forecasting\requirements.txt
```

## Run A Tiny Smoke

This stays under the allowed smoke budget:

```powershell
python -m policy_forecasting.sweep.wrapper --arms baseline,wage_tax_high --seeds 0 --households 200 --ticks 20 --output policy_forecasting\artifacts\smoke_ticks.parquet
python -m policy_forecasting.dataset policy_forecasting\artifacts\smoke_ticks.parquet policy_forecasting\artifacts\smoke_supervised.parquet
python -m policy_forecasting.determinism --arm baseline --seed 0 --households 200 --ticks 20 --output policy_forecasting\artifacts\determinism_smoke.json
```

Do not run the confirm sweep casually. The confirm command is intentionally
explicit and should be launched only when the 10k run is wanted:

```powershell
python -m policy_forecasting.sweep.wrapper --confirm-seeds --households 10000 --ticks 80 --processes 8 --output policy_forecasting\artifacts\confirm_ticks.parquet
```

## Frozen Arms

- `baseline`
- `wage_tax_high`: `wage_tax_rate = 0.30`
- `profit_tax_high`: `profit_tax_rate = 0.35`
- `benefit_high`: `benefit_level = "high"`
- `min_wage_high`: `minimum_wage_policy = "high"`
- `subsidy_food_25`: `sector_subsidy_target = "food"`, `sector_subsidy_level = 25`

`policy_canonical` is a SHA-256 hash prefix of the sorted baseline-resolved
lever vector, not the arm ID.

## Dropped Columns

None. The frozen V1 manifest is reachable from public simulator metrics,
government `to_dict()`, and public household/firm attributes. The wrapper
computes derived fields externally instead of editing the simulator.

## Notes

Consumer distress is label-only at `t+8`; same-tick `mean_distress` is allowed as
an observed welfare feature. Feature matrices always drop `run_id`,
`policy_canonical`, `levers_json`, `seed`, `tick`, and every `*__t+8` column. Use
the no-policy-state ablation in `dataset.py` when reporting model performance.
