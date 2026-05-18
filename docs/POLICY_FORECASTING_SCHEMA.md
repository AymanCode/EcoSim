# POLICY_FORECASTING — Frozen Dataset Schema (v1)

**Status:** Frozen contract for V1. Implementation must match this exactly. Referenced as the blocking artifact by `POLICY_FORECASTING_V1.md` (B1, B2, M5).

## Row grain

One row per `(run_id, policy_canonical, seed, tick)`. **No per-household rows persisted** (kills the ~170M-row blowout from 6 arms × 24 seeds × ~120 ticks × 10k households). Household state enters only as economy-level aggregates and distributional summaries (below).

## Column inventory

### Identifier columns (NEVER features, NEVER labels)
`run_id`, `policy_canonical`, `levers_json`, `seed`, `tick`. Used only for joins and split assignment. Hard-excluded from the feature matrix.

### Feature columns (available at tick t only)
Drawn from existing surfaces in `backend/data/models.py` (tick metrics, sector metrics, firm snapshots, diagnostics, shortage rows, regime events), aggregated to economy/sector level:

- **Labor:** unemployment rate, unemployment MA(4/8), hires, layoffs, vacancies, vacancy-fill ratio, wage pressure index.
- **Demand:** GDP, sector revenue (per sector), aggregate inventory, price index, sector price (per sector).
- **Household welfare (aggregates + distributional summaries):** mean + decile summary (p10/p50/p90) of cash-stress, health, happiness, food-insecurity. Counts: households below cash-stress threshold, food-insecure households.
- **Firm stability:** count in burn mode, count in survival mode, bankruptcies this tick, weak-demand firm count.
- **Fiscal:** government cash, government profit, fiscal-stress score.
- **Policy state:** the active lever values (wage tax, profit tax, investment tax, benefit level, minimum wage, sector subsidy vector, price/rent stabilization flags, public works, bailout flag).

### Label columns (constructed at t+8, NEVER features)
- `unemployment_rate__t+8` (primary regression target)
- `consumer_distress__t+8` (secondary regression target, formula below)

Labels are a forward join: for row at tick t in a run, label = metric at tick t+8 of the *same run*. Rows with t+8 beyond run end are dropped (no padding).

## Leakage exclusion list (hard rules)

Excluded from feature matrix entirely: `run_id`, `policy_canonical`, `levers_json`, `seed`, `tick`, and every `*__t+8` column. The **canonical lever vector is used for the split, NOT as a feature** (resolves B2: model cannot memorize policy identity). Policy *state* values (current lever settings at t) ARE allowed as features — they are observable at t — but the held-out split is by canonical lever vector so test arms are unseen lever vectors. Mandatory `no-policy-state ablation`: a second model trained with all policy-state features removed; report both.

## Consumer distress formula (frozen — resolves M5)

Per household h at tick t, bounded [0,1]:

```
distress_h,t = w_cash * cash_stress_h,t
             + w_food * food_insecurity_h,t
             + w_health * (1 - health_h,t / health_max)
             + w_happy * (1 - happiness_h,t / happiness_max)

cash_stress_h,t   = clip(1 - liquid_cash_h,t / (k * essential_spend_h,t), 0, 1)
food_insecurity_h,t = (# of last F ticks with food shortfall > 0) / F
weights: w_cash=0.40, w_food=0.25, w_health=0.20, w_happy=0.15  (sum = 1.0)
```

**Frozen constants + exact repo field bindings (NOT tuned post-hoc):**
- `k = 4`, `F = 8`. `health_max = 1.0`, `happiness_max = 1.0` (repo: `agents.py:157` happiness 0–1; health on 0–1 `agents.py:2010`).
- `essential_spend_h,t` := **`CONFIG.households.subsistence_min_cash`** (default `50.0`; repo: `backend/config.py:52`, also used `economy.py:850`). So `cash_stress = clip(1 - liquid_cash / (4 * subsistence_min_cash), 0, 1)` → cash_stress=0 once cash ≥ 200.
- `food shortfall (per tick)` := **`max(0.0, (min_food - food_consumed_this_tick) / max(min_food, 0.1))`** — exact existing sim logic at `economy.py:4179`. `food_consumed_this_tick` is a real household field (`agents.py:224`, exposed `agents.py:1185`); `min_food` := household field `h.min_food_per_tick` (`economy.py:4119`).
- `food_insecurity_h,t` := (# of last `F=8` ticks where the above shortfall ratio > 0) / 8.

All four bindings reference concrete repo fields with line citations — nothing deferred to implementation (closes Codex rev4 M5).

Economy-level target = mean over all households of `distress_h,t`. **Food insecurity is included** (Codex M5 — current repo formula omitted it; this spec overrides). The t+8 aggregate is a future value, not derivable from ≤ t rows → no same-tick target identity leak. Distress *components* may appear as ≤ t welfare features; the t+8 *aggregate distress* must not.

## Frozen policy arms (6 — exact canonical lever vectors)

Canonical **baseline** = the sim defaults (`agents.py:6197-6213`): `wage_tax_rate=0.15, profit_tax_rate=0.20, investment_tax_rate=0.10, benefit_level=neutral, minimum_wage_policy=neutral, sector_subsidy_target=none, sector_subsidy_level=0, social_spending=medium`, all stabilization/bailout `off`. Any arm whose lever vector equals this is a duplicate and is **dropped** (kills `tax_w15_p20`, `benefit_neutral`, `minimum_wage_neutral` — Codex B2).

The 6 frozen arms (each canonical vector distinct, each ≠ baseline except #1):

| # | arm id | lever delta vs baseline |
|---|---|---|
| 1 | `baseline` | `{}` (defaults above) |
| 2 | `wage_tax_high` | `wage_tax_rate = 0.30` |
| 3 | `profit_tax_high` | `profit_tax_rate = 0.35` |
| 4 | `benefit_high` | `benefit_level = "high"` |
| 5 | `min_wage_high` | `minimum_wage_policy = "high"` |
| 6 | `subsidy_food_25` | `sector_subsidy_target = "food", sector_subsidy_level = 25` |

`policy_canonical` = a stable hash of the sorted resolved lever vector (NOT the arm id). Split is by `policy_canonical` (resolves B2). This table is frozen pre-sweep; no arm added/changed after the confirm run.

## Frozen feature manifest (the contract — resolves B1 "not truly frozen")

Feature matrix columns are EXACTLY the union below, computed per `(run_id, policy_canonical, seed, tick)` from `backend/data/models.py` surfaces. Nothing else enters the model. Frozen pre-implementation:

- **Labor (8):** `unemployment_rate`, `unemployment_ma4`, `unemployment_ma8`, `hires`, `layoffs`, `vacancies`, `vacancy_fill_ratio`, `wage_pressure_idx`
- **Demand (4 + per-sector):** `gdp`, `agg_inventory`, `price_index`, `gdp_ma4`; per sector s: `sector_revenue[s]`, `sector_price[s]`
- **Household welfare (12):** mean+p10+p50+p90 of {`cash_stress`,`food_insecurity`}; `mean_health`, `mean_happiness`, `n_below_cash_thresh`, `n_food_insecure`, `mean_distress`(t only), `pct_health_below_0p7`
- **Firm stability (4):** `n_burn_mode`, `n_survival_mode`, `bankruptcies_tick`, `n_weak_demand`
- **Fiscal (3):** `gov_cash`, `gov_profit`, `fiscal_stress`
- **Policy state (resolved levers at t):** the 17 levers in `policy_schema.PROMPT_POLICY_LEVERS`

Any column not in this manifest is out of V1. Adding a column = a new frozen revision, not an ad-hoc change.

## Split protocol (resolves B2, M8, NEW non-stationarity)

Disjoint blocks by `(canonical_lever_vector, seed)`:
- **Train:** subset of lever vectors × subset of seeds
- **Validation:** held-out seeds on train lever vectors (model selection/tuning only)
- **Frozen final test:** held-out lever vectors × held-out seeds (touched once)

Additionally, CI/error estimation blocks by run AND time-regime (early/mid/late tick bands) to respect autocorrelation + non-stationarity from long runs (Codex NEW-c). Rows within a run are not treated as independent.

## Generalization claim (resolves B2/M10 overclaim, Codex NEW-d)

With 6 distinct lever-vector arms, the defensible claim is **held-out performance among 6 pre-registered policy interventions**, NOT broad policy-space generalization. All wording in spec/bullets/README must use the narrow phrasing.
