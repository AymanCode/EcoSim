# Policy Forecasting V1 Dataset Schema

**Status:** Frozen V1 contract. The implementation must match this schema exactly. This document is referenced by [POLICY_FORECASTING_V1.md](POLICY_FORECASTING_V1.md) and by the policy forecasting package.

## Row Grain

One row is written for each `(run_id, policy_canonical, seed, tick)`.

No per-household rows are persisted. That keeps the dataset small: the confirm sweep stores one economy-level row per tick instead of roughly 170 million household rows from 6 arms x 24 seeds x about 120 ticks x 10,000 households. Household state enters only through economy-level aggregates and distributional summaries.

## Column Inventory

### Identifier Columns

These columns are used only for joins, traceability, and split assignment. They are never used as features or labels:

`run_id`, `policy_canonical`, `levers_json`, `seed`, `tick`

### Feature Columns

Features are available at tick `t` only. They are drawn from existing simulator surfaces in `backend/data/models.py`, including tick metrics, sector metrics, firm snapshots, diagnostics, shortage rows, and regime events. Values are aggregated to the economy or sector level.

- **Labor:** unemployment rate, unemployment MA(4/8), hires, layoffs, vacancies, vacancy-fill ratio, wage pressure index.
- **Demand:** GDP, sector revenue, aggregate inventory, price index, and sector price.
- **Household welfare:** mean and p10/p50/p90 summaries of cash stress, health, happiness, and food insecurity; counts of households below cash-stress and food-insecurity thresholds.
- **Firm stability:** firms in burn mode, firms in survival mode, bankruptcies this tick, and weak-demand firm count.
- **Fiscal:** government cash, government profit, and fiscal-stress score.
- **Policy state:** active lever values for wage tax, profit tax, investment tax, benefit level, minimum wage, sector subsidy, price/rent stabilization, public works, and bailout policy.

### Label Columns

Labels are constructed from tick `t+8` and are never included in the feature matrix:

- `unemployment_rate__t+8` primary regression target
- `consumer_distress__t+8` secondary regression target

Labels are created with a forward join inside the same run. Rows whose `t+8` label would fall beyond the run end are dropped rather than padded.

## Leakage Rules

The feature matrix must exclude `run_id`, `policy_canonical`, `levers_json`, `seed`, `tick`, and every `*__t+8` column.

`policy_canonical` is used for splitting, not as a feature. Current policy state values at tick `t` are allowed because they are observable at that tick, but the held-out split is by canonical lever vector so the final test uses unseen lever vectors.

The package must also report a no-policy-state ablation: a second model trained with all policy-state features removed.

## Consumer Distress Formula

Per household `h` at tick `t`, distress is bounded to `[0, 1]`:

```text
distress_h,t = w_cash * cash_stress_h,t
             + w_food * food_insecurity_h,t
             + w_health * (1 - health_h,t / health_max)
             + w_happy * (1 - happiness_h,t / happiness_max)

cash_stress_h,t = clip(1 - liquid_cash_h,t / (k * essential_spend_h,t), 0, 1)
food_insecurity_h,t = (# of last F ticks with food shortfall > 0) / F

weights: w_cash=0.40, w_food=0.25, w_health=0.20, w_happy=0.15
```

Frozen constants and repo bindings:

- `k = 4`, `F = 8`, `health_max = 1.0`, and `happiness_max = 1.0`.
- `essential_spend_h,t` is `CONFIG.households.subsistence_min_cash`, default `50.0`. This means `cash_stress = 0` once liquid cash is at least `200`.
- Food shortfall per tick is `max(0.0, (min_food - food_consumed_this_tick) / max(min_food, 0.1))`, matching the existing simulator logic at `economy.py:4179`.
- `food_consumed_this_tick` is a household field exposed from `agents.py`; `min_food` is the household field `h.min_food_per_tick`.
- `food_insecurity_h,t` is the share of the last 8 ticks where the food shortfall ratio was greater than zero.

The economy-level target is the mean distress over all households. Food insecurity is included intentionally. The `t+8` aggregate is a future value, not derivable from rows available at or before `t`, so it does not create a same-tick target identity leak.

Distress components may appear as features at or before `t`; the future aggregate distress label must not.

## Frozen Policy Arms

The canonical baseline is the simulator default policy:

`wage_tax_rate=0.15`, `profit_tax_rate=0.20`, `investment_tax_rate=0.10`, `benefit_level=neutral`, `minimum_wage_policy=neutral`, `sector_subsidy_target=none`, `sector_subsidy_level=0`, `social_spending=medium`, with stabilization and bailout levers off.

Any arm whose resolved lever vector equals baseline is treated as a duplicate and dropped.

| # | Arm ID | Lever delta vs baseline |
|---|---|---|
| 1 | `baseline` | `{}` |
| 2 | `wage_tax_high` | `wage_tax_rate = 0.30` |
| 3 | `profit_tax_high` | `profit_tax_rate = 0.35` |
| 4 | `benefit_high` | `benefit_level = "high"` |
| 5 | `min_wage_high` | `minimum_wage_policy = "high"` |
| 6 | `subsidy_food_25` | `sector_subsidy_target = "food", sector_subsidy_level = 25` |

`policy_canonical` is a stable hash of the sorted, resolved lever vector. It is not the arm ID. The split protocol uses `policy_canonical` so the final test holds out lever vectors, not just names.

## Frozen Feature Manifest

The feature matrix is exactly the union below, computed per `(run_id, policy_canonical, seed, tick)`. Any additional column requires a new schema revision.

- **Labor:** `unemployment_rate`, `unemployment_ma4`, `unemployment_ma8`, `hires`, `layoffs`, `vacancies`, `vacancy_fill_ratio`, `wage_pressure_idx`
- **Demand:** `gdp`, `agg_inventory`, `price_index`, `gdp_ma4`, plus per-sector `sector_revenue[s]` and `sector_price[s]`
- **Household welfare:** mean, p10, p50, and p90 of `cash_stress` and `food_insecurity`; `mean_health`, `mean_happiness`, `n_below_cash_thresh`, `n_food_insecure`, `mean_distress`, `pct_health_below_0p7`
- **Firm stability:** `n_burn_mode`, `n_survival_mode`, `bankruptcies_tick`, `n_weak_demand`
- **Fiscal:** `gov_cash`, `gov_profit`, `fiscal_stress`
- **Policy state:** the 17 resolved levers in `policy_schema.PROMPT_POLICY_LEVERS`

## Split Protocol

Splits are disjoint by `(canonical_lever_vector, seed)`:

| Split | Purpose |
|---|---|
| Train | Subset of lever vectors x subset of seeds |
| Validation | Held-out seeds on train lever vectors, used only for model selection and tuning |
| Frozen final test | Held-out lever vectors x held-out seeds, read once for final reporting |

Confidence intervals and error estimates are blocked by run and by early/mid/late tick bands to respect autocorrelation and non-stationarity. Rows within a run are not treated as independent.

## Generalization Claim

With 6 distinct lever-vector arms, the defensible claim is held-out performance among 6 pre-registered policy interventions. This is not a broad policy-space generalization claim.
