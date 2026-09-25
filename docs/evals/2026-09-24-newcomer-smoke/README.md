# Newcomer-scale policy smoke run (2026-09-24)

This directory holds the evidence behind section 5 ("Question cards and evidence") of [the frontend learning redesign spec](../../superpowers/specs/2026-09-24-frontend-learning-redesign-design.md). The question was practical: at the world size a newcomer gets from the dashboard, would they see a policy arm's line separate from the baseline on a five-year chart?

All outcomes describe EcoSim's synthetic economy. They are not real-world forecasts or policy recommendations. The checked-in sweep in [`policy_forecasting/RESULTS.md`](../../../policy_forecasting/RESULTS.md) (10,000 households, 24 seeds, 80 ticks) remains the statistical evidence; this run adds one or two seeds at the dashboard's default size.

## What was run

| Batch | Households | Ticks | Firms per category | Seeds | Payment sequence | Arms |
|---|---|---|---|---|---|---|
| Legacy, 1k | 1,000 | 260 | 5 | 1337, 7 | `legacy` | all seven below |
| `income_first`, 1k | 1,000 | 260 | 5 | 1337 | `income_first` | `baseline`, `benefit_high`, `min_wage_high` |
| Legacy, 5k | 5,000 | 260 | 5 | 1337 | `legacy` | `baseline` |

Five firms per category matches the dashboard `SetupConfig` default. 260 weekly ticks is five simulated years. Arms are the six frozen arms from [`policy_forecasting/config.py`](../../../policy_forecasting/config.py) plus public works:

| Arm | Lever change from baseline |
|---|---|
| `baseline` | none |
| `wage_tax_high` | `wage_tax_rate` 0.15 → 0.30 |
| `profit_tax_high` | `profit_tax_rate` 0.20 → 0.35 |
| `benefit_high` | `benefit_level` neutral → high |
| `min_wage_high` | `minimum_wage_policy` neutral → high |
| `subsidy_food_25` | `sector_subsidy_target` food, `sector_subsidy_level` 25 |
| `public_works_on` | `public_works` off → on |

Each arm builds the economy through `policy_forecasting.sweep.wrapper.create_economy_quietly`, applies its levers through `GovernmentAgent.set_lever`, and records one row per tick: the frozen manifest from `wrapper.snapshot_manifest` plus `total_firms`, `homeless_household_count`, `public_works_firms`, `public_works_jobs`, `gov_public_works_jobs_authorized`, `mean_wage` and `median_price` from `Economy.get_economic_metrics()`, and a derived `firm_distress_share`.

## Commands

The evidence was produced on 2026-09-24 by three throwaway scripts in a session scratch directory. They are not kept in the repository:

```bash
python run_arms.py                  # legacy, 1k, seed 1337, seven arms
python run_arms.py --seed7-only     # legacy, 1k, seed 7, seven arms
python run_income_first.py          # income_first, 1k, seed 1337, three arms
python run_scale5000.py             # legacy, 5k, seed 1337, baseline
```

An earlier revision of `run_arms.py` produced the seed 1337 legacy batch. It wrote `run_meta.csv`, and its console log was not kept. The scripts did not record a commit. They ran from this checkout at HEAD `4f69389` with uncommitted changes, including the payment modules.

[`backend/tools/benchmarks/run_newcomer_smoke.py`](../../../backend/tools/benchmarks/run_newcomer_smoke.py) replaces all three scripts. To reproduce the batches from the repository root:

```bash
.venv/bin/python -m backend.tools.benchmarks.run_newcomer_smoke \
  --households 1000 --ticks 260 --firms-per-category 5 --seeds 1337,7 \
  --arms baseline,min_wage_high,benefit_high,wage_tax_high,profit_tax_high,subsidy_food_25,public_works_on

.venv/bin/python -m backend.tools.benchmarks.run_newcomer_smoke \
  --seeds 1337 --arms baseline,benefit_high,min_wage_high --payment-sequence income_first

.venv/bin/python -m backend.tools.benchmarks.run_newcomer_smoke \
  --households 5000 --seeds 1337 --arms baseline
```

On an Apple Silicon laptop these took about 7.5, 2 and 3 minutes. Each command writes to `benchmarks/results/newcomer-smoke/<UTC timestamp>/`. The output has one CSV and one `_meta.json` per arm and seed, plus `run_meta.csv` and a `summary.md` containing the baseline motion and per-arm delta tables below.

Reproduction check: the tool reran the first 52 ticks at 1,000 households for `baseline`, `min_wage_high` and `public_works_on` (legacy) and `baseline` (`income_first`), all at seed 1337. All 71 shared columns matched the checked-in CSVs exactly. The full 260-tick runs were not repeated.

Tool output differs from the checked-in CSVs in three ways. It adds a `median_wage` column, uses a different `run_id` string, and writes JSON meta files. The 5k script's four-minute abort cap was not carried over.

## Results

Definitions used in every table:

- Unemployment is `unemployment_rate`. Food price is `sector_price_food`, the unweighted mean posted price across food firms. Gov cash is `gov_cash`, the town hall's cash balance in simulator dollars. Distress is `mean_distress`, the household composite from [`policy_forecasting/distress.py`](../../../policy_forecasting/distress.py). Homeless is `homeless_household_count`.
- Firm-exit ticks counts the ticks on which the active-firm count fell. Several firms can exit on one tick.
- A checkpoint is the state after that many ticks. The CSV `tick` column is the checkpoint minus 1.

### Legacy sequence, 1,000 households, seeds 1337 and 7

| Run | Unemployment min / max / final | Firms min / max / final | Firm-exit ticks | Food price start → end | Gov cash start / min / final | Distress start → final | Homeless peak |
|---|---|---|---|---|---|---|---|
| `baseline` seed 1337 | 0.0% / 48.8% / 36.7% | 4 / 31 / 30 | 6 | 5.00 → 5.17 | 2,686,822 / -357,239 / -357,239 | 0.046 → 0.397 | 22 |
| `min_wage_high` seed 1337 | 0.0% / 46.2% / 26.8% | 4 / 31 / 30 | 3 | 5.00 → 5.47 | 2,707,775 / 28,289 / 28,289 | 0.046 → 0.390 | 14 |
| `benefit_high` seed 1337 | 0.0% / 45.8% / 24.3% | 4 / 31 / 30 | 8 | 5.00 → 6.62 | 2,707,599 / -33,554 / -24,953 | 0.046 → 0.377 | 10 |
| `wage_tax_high` seed 1337 | 0.0% / 45.8% / 34.7% | 4 / 31 / 30 | 10 | 5.00 → 5.28 | 2,686,145 / -8,128 / -3,408 | 0.046 → 0.428 | 16 |
| `profit_tax_high` seed 1337 | 0.0% / 45.8% / 39.8% | 4 / 31 / 30 | 8 | 5.00 → 5.59 | 2,659,984 / -103,802 / -103,802 | 0.046 → 0.406 | 9 |
| `subsidy_food_25` seed 1337 | 0.0% / 45.8% / 43.0% | 4 / 31 / 30 | 6 | 5.00 → 5.13 | 2,704,352 / -164,244 / -164,244 | 0.046 → 0.409 | 14 |
| `public_works_on` seed 1337 | 0.0% / 41.3% / 30.8% | 5 / 32 / 30 | 4 | 5.00 → 5.04 | 2,503,211 / -140,932 / -140,932 | 0.046 → 0.402 | 25 |
| `baseline` seed 7 | 0.0% / 45.8% / 34.1% | 4 / 31 / 30 | 8 | 5.00 → 5.24 | 2,681,075 / -383,741 / -383,741 | 0.046 → 0.427 | 36 |
| `min_wage_high` seed 7 | 0.0% / 46.2% / 33.0% | 4 / 31 / 30 | 4 | 5.00 → 5.69 | 2,655,673 / 34,525 / 55,011 | 0.046 → 0.380 | 24 |
| `benefit_high` seed 7 | 0.0% / 45.8% / 19.3% | 4 / 31 / 30 | 12 | 5.00 → 7.56 | 2,678,727 / -15,315 / -3,231 | 0.046 → 0.370 | 11 |
| `wage_tax_high` seed 7 | 0.0% / 51.4% / 40.1% | 4 / 31 / 30 | 7 | 5.00 → 5.14 | 2,690,357 / -59,194 / -59,194 | 0.046 → 0.405 | 34 |
| `profit_tax_high` seed 7 | 0.0% / 45.8% / 38.6% | 4 / 31 / 29 | 8 | 5.00 → 5.72 | 2,666,841 / -106,869 / -106,869 | 0.046 → 0.396 | 24 |
| `subsidy_food_25` seed 7 | 0.0% / 45.8% / 34.1% | 4 / 31 / 30 | 8 | 5.00 → 5.32 | 2,648,842 / -126,101 / -126,101 | 0.046 → 0.387 | 26 |
| `public_works_on` seed 7 | 0.0% / 43.8% / 32.0% | 5 / 32 / 30 | 5 | 5.00 → 5.77 | 2,473,201 / -204,153 / -204,153 | 0.046 → 0.351 | 35 |

Wall-clock per arm was 31.1 to 33.0 s for seed 1337 and 31.0 to 39.2 s for seed 7. Firms stay at the 4 baseline firms until tick 9, then queued competitors enter and the count reaches 31 by tick 12. The baseline's town hall cash first falls below zero after tick 175 (seed 1337) and after tick 163 (seed 7), both in year four. Baseline homelessness is nonzero on only 1 (seed 1337) and 4 (seed 7) of 260 ticks, despite the peaks shown.

### `income_first` sequence, 1,000 households, seed 1337

| Run | Unemployment min / max / final | Firms min / max / final | Firm-exit ticks | Food price start → end | Gov cash start / min / final | Distress start → final | Homeless peak |
|---|---|---|---|---|---|---|---|
| `baseline` seed 1337 | 0.0% / 47.7% / 38.8% | 4 / 31 / 31 | 0 | 5.00 → 5.11 | 2,686,358 / 60,195 / 60,522 | 0.046 → 0.603 | 56 |
| `benefit_high` seed 1337 | 0.0% / 45.8% / 4.9% | 4 / 31 / 30 | 1 | 5.00 → 7.40 | 2,707,610 / 186,380 / 232,452 | 0.046 → 0.360 | 50 |
| `min_wage_high` seed 1337 | 0.0% / 53.0% / 0.8% | 4 / 31 / 31 | 0 | 5.00 → 5.38 | 2,689,155 / 103,622 / 247,569 | 0.046 → 0.410 | 113 |

Wall-clock per arm was 39.0 to 39.8 s. The sequence was confirmed active. `payment_sequence_effective` is `income_first`, and at the final tick `get_economic_metrics()["payment"]["coverage"]` is `settled_tick_and_live_claims` with scenario `{'timing': 'income_first', 'care': 'patient_pay', 'assistance': 'reserve'}`. Before the first step no payment book exists, so the tick-0 marker is absent (`<no coverage key>`). Under `legacy` the metrics carry no `payment` key at any tick.

Unemployment at the year-four and year-five checkpoints (after ticks 208 and 260) was 45.0% and 38.8% for the baseline, 2.7% and 4.9% for `benefit_high`, and 1.7% and 0.8% for `min_wage_high`. The `min_wage_high` homeless peak of 113 households is 11% of the town.

### Legacy sequence, 5,000 households, seed 1337 (baseline only)

| Run | Unemployment min / max / final | Firms min / max / final | Firm-exit ticks | Food price start → end | Gov cash start / min / final | Distress start → final | Homeless peak |
|---|---|---|---|---|---|---|---|
| `baseline` seed 1337, 5,000 households | 0.0% / 45.8% / 23.0% | 4 / 150 / 150 | 60 | 5.00 → 5.45 | 13,530,399 / -399,314 / -399,314 | 0.052 → 0.417 | 74 |

The step loop took 170.1 s, averaging 0.65 s per tick, and creation took 0.1 s. The run completed all 260 ticks without hitting the script's four-minute abort cap. Across those 60 firm-exit ticks the active-firm count fell by 97 in total.

### Baseline unemployment at checkpoints

| Baseline | After 52 | After 104 | After 156 | After 208 | After 260 |
|---|---|---|---|---|---|
| Legacy, 1k, seed 1337 | 19.4% | 25.9% | 19.6% | 29.8% | 36.7% |
| Legacy, 1k, seed 7 | 14.1% | 23.2% | 22.6% | 32.5% | 34.1% |
| `income_first`, 1k, seed 1337 | 26.5% | 43.5% | 24.5% | 45.0% | 38.8% |
| Legacy, 5k, seed 1337 | 13.0% | 5.5% | 12.3% | 23.4% | 23.0% |

**Every baseline ends year five with 23 to 39 percent unemployment.** None of the four baseline runs is a functioning economy at the end of five years. This is a calibration property of the backend at these scales and payment sequences, and it sets what the default "no changes" town looks like.

## Per-arm visibility against the baseline (legacy, 1k)

Each cell compares the arm with the same-seed baseline at the five checkpoints in both seeds, which gives ten comparisons. It shows the range of arm-minus-baseline differences and how many of the ten point the stated way.

| Arm | Mean wage | Unemployment (pp) | Food price | Gov cash | Distress | Verdict |
|---|---|---|---|---|---|---|
| `benefit_high` | +26% to +60%, 10 of 10 higher | −17.6 to −5.2, 10 of 10 lower | +$1.02 to +$2.31, 10 of 10 higher | +32K to +381K, 10 of 10 higher | −0.089 to −0.002, 10 of 10 lower | **Visible** |
| `min_wage_high` | +11% to +29%, 10 of 10 higher | −16.4 to +8.4, 9 of 10 lower | −0.23 to +0.45, 6 of 10 higher | +11K to +439K, 10 of 10 higher | −0.077 to −0.007, 10 of 10 lower | **Visible on pay and gov cash, marginal on unemployment** |
| `wage_tax_high` | −3% to +16%, 5 of 10 higher | −20.9 to +10.4, 5 of 10 lower | −0.30 to +0.37, 6 of 10 higher | +15K to +354K, 10 of 10 higher | −0.022 to +0.061, 9 of 10 higher | **Marginal** |
| `profit_tax_high` | −5% to +7%, 7 of 10 higher | −15.0 to +7.8, 5 of 10 lower | −0.22 to +0.65, 7 of 10 higher | −39K to +277K, 8 of 10 higher | −0.031 to +0.012, 3 of 10 higher | **None** |
| `subsidy_food_25` | −6% to +16%, 5 of 10 higher | −23.3 to +6.3, 7 of 10 lower | −0.72 to +0.38, 6 of 10 higher | −42K to +258K, 7 of 10 higher | −0.050 to +0.014, 2 of 10 higher | **None** |
| `public_works_on` | −8% to +3%, 4 of 10 higher | −9.2 to +6.0, 6 of 10 lower | −0.56 to +0.53, 5 of 10 higher | −52K to +216K, 7 of 10 higher | −0.076 to +0.018, 4 of 10 higher | **None on macro outcomes** |

Reading the verdicts:

- **`benefit_high`: visible.** Pay, unemployment, food price and town hall cash all separate in the same direction at every checkpoint in both seeds. At 1,000 households unemployment falls, which is the opposite direction from the 10,000-household, 80-tick sweep, so the effect depends on scale and horizon.
- **`min_wage_high`: visible on pay and town hall cash, marginal on unemployment.** Pay is higher at every checkpoint. It is the only arm whose town hall cash never goes negative (minimum $28K and $35K against the baseline's −$357K and −$384K). Unemployment is lower at 9 of 10 checkpoints, but the gaps sit inside the baseline's own swings, which reach 0 to 49 percent.
- **`wage_tax_high`: marginal.** Only town hall cash separates consistently. Distress is higher at 9 of 10 checkpoints, by 0.004 to 0.061, which is small against the baseline's range.
- **`profit_tax_high`: none.** Every metric stays at noise level, and signs flip between checkpoints and seeds. This matches the 10,000-household finding.
- **`subsidy_food_25`: none.** The posted food price does not move beyond the band every other arm shows. That fits the voucher mechanism, but it leaves nothing to watch.
- **`public_works_on`: none on macro outcomes.** A public-works firm appears at tick 0 in both seeds. In seed 1337 it exits at tick 246 (CSV `tick` column) and is not recreated before the run ends at tick 259. Its authorization, `gov_public_works_jobs_authorized`, drops from 200 to 0 from tick 247. In seed 7 it survives to the end.

The town hall cash column needs care. The baseline has the lowest cash at tick 260 of all seven arms in both seeds. So by year five every arm shows a large positive cash gap, including the food subsidy, which spends more: +$193K and +$258K at tick 260. A cash gap on its own is only meaningful when it clears that band. `min_wage_high` clears it by staying solvent throughout.

### Public works jobs: reported, not target

Reported public-works jobs (`public_works_jobs`, the public-works firm's employee headcount) peaked at **100** in seed 1337 and at 50 in seed 7. In seed 1337 the count was 50 at tick 0 and 100 from tick 1 to tick 9. In seed 7 it was 50 from tick 0 to tick 9. Both then fell by 5 per tick to 7 (seed 1337 by tick 28, seed 7 by tick 18) and drifted back up to 16: seed 1337 reached 16 at tick 244, two ticks before its exit, and seed 7 reached 16 at tick 246 and held it to the end.

The configured target at 1,000 households is **200**. It comes from `public_works_job_fraction = 0.2` in [`backend/config.py`](../../../backend/config.py) and `target_jobs = max(1, int(len(households) × public_works_job_fraction))` in `backend/economy.py`, and `gov_public_works_jobs_authorized` reports it. Every public-works figure in this document is reported jobs, not the target.

<details>
<summary>Full arm-minus-baseline table at checkpoints (legacy, 1k)</summary>

| Arm | Seed | After tick | Δ Unemployment (pp) | Δ Mean wage | Δ Food price | Δ Gov cash | Δ Distress | Δ Firms | Δ Homeless | Δ PW jobs |
|---|---|---|---|---|---|---|---|---|---|---|
| min_wage_high | 1337 | 52 | -4.6 | +5.58 | -0.18 | +32,971 | -0.062 | 0 | 0 | 0 |
| min_wage_high | 1337 | 104 | -1.2 | +9.22 | +0.03 | +33,818 | -0.043 | 0 | 0 | 0 |
| min_wage_high | 1337 | 156 | -10.6 | +10.51 | -0.01 | +70,401 | -0.022 | 0 | 0 | 0 |
| min_wage_high | 1337 | 208 | -10.6 | +9.14 | +0.21 | +210,429 | -0.013 | 0 | 0 | 0 |
| min_wage_high | 1337 | 260 | -9.9 | +13.20 | +0.30 | +385,528 | -0.007 | 0 | 0 | 0 |
| min_wage_high | 7 | 52 | +8.4 | +8.09 | -0.03 | +11,468 | -0.077 | 0 | 0 | 0 |
| min_wage_high | 7 | 104 | -12.1 | +7.92 | -0.23 | +114,024 | -0.034 | 0 | 0 | 0 |
| min_wage_high | 7 | 156 | -16.4 | +13.21 | +0.05 | +105,722 | -0.036 | 0 | 0 | 0 |
| min_wage_high | 7 | 208 | -9.6 | +11.70 | +0.18 | +220,717 | -0.026 | 0 | 0 | 0 |
| min_wage_high | 7 | 260 | -1.1 | +12.01 | +0.45 | +438,752 | -0.047 | 0 | 0 | 0 |
| benefit_high | 1337 | 52 | -8.6 | +14.24 | +1.18 | +31,641 | -0.063 | 0 | 0 | 0 |
| benefit_high | 1337 | 104 | -15.5 | +15.66 | +1.16 | +66,072 | -0.049 | 0 | 0 | 0 |
| benefit_high | 1337 | 156 | -13.6 | +20.85 | +2.00 | +64,358 | -0.022 | 0 | 0 | 0 |
| benefit_high | 1337 | 208 | -17.6 | +23.37 | +1.28 | +170,694 | -0.068 | 0 | 0 | 0 |
| benefit_high | 1337 | 260 | -12.4 | +27.40 | +1.45 | +332,286 | -0.020 | 0 | 0 | 0 |
| benefit_high | 7 | 52 | -5.2 | +12.87 | +1.06 | +32,744 | -0.061 | 0 | 0 | 0 |
| benefit_high | 7 | 104 | -7.8 | +13.09 | +1.31 | +82,169 | -0.002 | -1 | 0 | 0 |
| benefit_high | 7 | 156 | -6.0 | +14.39 | +1.02 | +42,044 | -0.021 | 0 | 0 | 0 |
| benefit_high | 7 | 208 | -13.0 | +23.02 | +1.94 | +146,255 | -0.089 | 0 | 0 | 0 |
| benefit_high | 7 | 260 | -14.8 | +22.13 | +2.31 | +380,510 | -0.057 | 0 | 0 | 0 |
| wage_tax_high | 1337 | 52 | +3.2 | -0.01 | +0.16 | +40,884 | +0.061 | 0 | 0 | 0 |
| wage_tax_high | 1337 | 104 | +10.4 | +0.01 | -0.10 | +15,013 | +0.049 | 0 | 0 | 0 |
| wage_tax_high | 1337 | 156 | +4.3 | +7.80 | +0.01 | +82,241 | +0.037 | 0 | 0 | 0 |
| wage_tax_high | 1337 | 208 | +6.8 | -0.66 | +0.37 | +157,707 | +0.008 | 0 | 0 | 0 |
| wage_tax_high | 1337 | 260 | -2.0 | -1.38 | +0.11 | +353,831 | +0.031 | 0 | 0 | 0 |
| wage_tax_high | 7 | 52 | -0.6 | -0.22 | -0.30 | +49,210 | +0.060 | 0 | 0 | 0 |
| wage_tax_high | 7 | 104 | -5.1 | -1.63 | -0.30 | +105,394 | +0.054 | 0 | 0 | 0 |
| wage_tax_high | 7 | 156 | -20.9 | +2.82 | +0.31 | +152,492 | +0.004 | 0 | 0 | 0 |
| wage_tax_high | 7 | 208 | -5.2 | +1.30 | +0.37 | +211,600 | +0.008 | 0 | 0 | 0 |
| wage_tax_high | 7 | 260 | +6.0 | +2.76 | -0.10 | +324,547 | -0.022 | 0 | 0 | 0 |
| profit_tax_high | 1337 | 52 | +3.0 | -0.41 | -0.16 | +49,515 | +0.012 | 0 | 0 | 0 |
| profit_tax_high | 1337 | 104 | +7.8 | +2.14 | -0.05 | -38,666 | -0.000 | 0 | 0 | 0 |
| profit_tax_high | 1337 | 156 | -5.4 | +3.42 | +0.27 | +65,008 | -0.025 | 0 | 0 | 0 |
| profit_tax_high | 1337 | 208 | -1.7 | -2.19 | +0.65 | +188,546 | -0.009 | 0 | 0 | 0 |
| profit_tax_high | 1337 | 260 | +3.1 | +0.04 | +0.42 | +253,437 | +0.009 | 0 | 0 | 0 |
| profit_tax_high | 7 | 52 | +0.0 | +0.78 | +0.27 | -6,515 | +0.005 | 0 | 0 | 0 |
| profit_tax_high | 7 | 104 | -1.9 | -0.11 | -0.22 | +65,964 | -0.004 | 0 | 0 | 0 |
| profit_tax_high | 7 | 156 | -15.0 | +2.54 | +0.09 | +101,579 | -0.003 | 0 | 0 | 0 |
| profit_tax_high | 7 | 208 | -2.8 | +0.02 | +0.37 | +169,744 | -0.005 | 0 | 0 | 0 |
| profit_tax_high | 7 | 260 | +4.5 | +2.63 | +0.48 | +276,872 | -0.031 | -1 | 0 | 0 |
| subsidy_food_25 | 1337 | 52 | +0.9 | +0.13 | +0.07 | -28,921 | -0.012 | 0 | 0 | 0 |
| subsidy_food_25 | 1337 | 104 | +2.1 | -0.14 | -0.25 | -41,899 | -0.010 | 0 | 0 | 0 |
| subsidy_food_25 | 1337 | 156 | -6.4 | +8.00 | +0.05 | +28,662 | -0.034 | 0 | 0 | 0 |
| subsidy_food_25 | 1337 | 208 | -7.6 | -2.88 | +0.13 | +145,226 | -0.017 | 0 | 0 | 0 |
| subsidy_food_25 | 1337 | 260 | +6.3 | -0.14 | -0.04 | +192,996 | +0.012 | 0 | 0 | 0 |
| subsidy_food_25 | 7 | 52 | -3.5 | +1.23 | +0.05 | -9,386 | -0.019 | 0 | 0 | 0 |
| subsidy_food_25 | 7 | 104 | -6.7 | -0.60 | -0.72 | +38,268 | +0.014 | 0 | 0 | 0 |
| subsidy_food_25 | 7 | 156 | -2.8 | +1.65 | -0.01 | +8,335 | -0.014 | 0 | 0 | 0 |
| subsidy_food_25 | 7 | 208 | -23.3 | -0.83 | +0.38 | +209,655 | -0.050 | 0 | 0 | 0 |
| subsidy_food_25 | 7 | 260 | -0.1 | +1.75 | +0.07 | +257,640 | -0.040 | 0 | 0 | 0 |
| public_works_on | 1337 | 52 | +0.8 | +0.88 | -0.11 | -51,846 | +0.006 | 0 | 0 | +8 |
| public_works_on | 1337 | 104 | +6.0 | +1.72 | +0.04 | -42,934 | -0.001 | 0 | 0 | +9 |
| public_works_on | 1337 | 156 | +1.8 | +0.52 | +0.28 | +40,808 | -0.017 | 0 | 0 | +11 |
| public_works_on | 1337 | 208 | -3.4 | -1.22 | -0.36 | +134,772 | -0.001 | 0 | 0 | +14 |
| public_works_on | 1337 | 260 | -5.8 | -0.47 | -0.13 | +216,307 | +0.005 | 0 | 0 | 0 |
| public_works_on | 7 | 52 | +6.0 | +1.07 | -0.16 | +842 | -0.007 | 0 | 0 | +8 |
| public_works_on | 7 | 104 | -1.4 | -1.44 | -0.56 | +39,902 | +0.018 | 0 | 0 | +9 |
| public_works_on | 7 | 156 | -9.2 | -3.61 | +0.34 | -21,821 | +0.018 | 0 | 0 | +11 |
| public_works_on | 7 | 208 | -0.4 | -0.89 | +0.11 | +58,173 | -0.006 | 0 | 0 | +13 |
| public_works_on | 7 | 260 | -2.2 | -0.47 | +0.53 | +179,588 | -0.076 | 0 | 0 | +16 |

</details>

<details>
<summary>Arm-minus-baseline table at checkpoints (<code>income_first</code>, 1k, seed 1337)</summary>

| Arm | Seed | After tick | Δ Unemployment (pp) | Δ Mean wage | Δ Food price | Δ Gov cash | Δ Distress | Δ Firms | Δ Homeless | Δ PW jobs |
|---|---|---|---|---|---|---|---|---|---|---|
| benefit_high | 1337 | 52 | -7.4 | +10.09 | +0.58 | +70,564 | -0.111 | 0 | -10 | 0 |
| benefit_high | 1337 | 104 | -29.1 | +7.51 | +1.34 | +105,349 | -0.046 | 0 | -4 | 0 |
| benefit_high | 1337 | 156 | -23.6 | +10.35 | +1.30 | +100,891 | -0.068 | 0 | -7 | 0 |
| benefit_high | 1337 | 208 | -42.3 | +24.41 | +0.98 | +184,678 | -0.273 | -1 | +6 | 0 |
| benefit_high | 1337 | 260 | -33.9 | +24.91 | +2.29 | +171,930 | -0.243 | -1 | -8 | 0 |
| min_wage_high | 1337 | 52 | +5.0 | +3.79 | +0.04 | -25,412 | -0.023 | 0 | +75 | 0 |
| min_wage_high | 1337 | 104 | +4.3 | +8.78 | +0.47 | +27,660 | -0.025 | 0 | -4 | 0 |
| min_wage_high | 1337 | 156 | -1.6 | +7.12 | +0.11 | +90,847 | -0.005 | 0 | -8 | 0 |
| min_wage_high | 1337 | 208 | -43.3 | +16.39 | +0.39 | +166,798 | -0.169 | 0 | -12 | 0 |
| min_wage_high | 1337 | 260 | -38.0 | +19.22 | +0.27 | +187,048 | -0.193 | 0 | -10 | 0 |

</details>

## Limitations

- One or two seeds per arm and no confidence intervals. "Visible" is a judgment about a five-year chart, not a significance test.
- The runs used a checkout with uncommitted changes. The scripts did not record a commit.
- Distress is a model composite, not an empirical welfare measure.

## Data files

All files are in [`data/`](data/). Tick CSVs are named `<arm>_seed<seed>_<payment sequence>_hh<households>.csv` and have one row per tick (`tick` 0 to 259). The meta CSVs and logs are the scratch scripts' original output. Their `out_path` column still points to the original scratch file names.

| File | Original scratch name | Contents |
|---|---|---|
| `<arm>_seed1337_legacy_hh1000.csv` (7 files) | `<arm>_seed1337.csv` | Legacy, 1k, seed 1337 |
| `<arm>_seed7_legacy_hh1000.csv` (7 files) | `<arm>_seed7.csv` | Legacy, 1k, seed 7 |
| `{baseline,benefit_high,min_wage_high}_seed1337_income_first_hh1000.csv` | `<arm>_seed1337_incomefirst.csv` | `income_first`, 1k, seed 1337 |
| `baseline_seed1337_legacy_hh5000.csv` | `baseline_seed1337_hh5000_full.csv` | Legacy, 5k, seed 1337 |
| `meta_seed1337_legacy_hh1000.csv` | `run_meta.csv` | Per-arm wall-clock and settings, legacy 1k seed 1337 |
| `meta_seed7_legacy_hh1000.csv` | `run_meta_seeds7.csv` | Per-arm wall-clock and settings, legacy 1k seed 7 |
| `meta_seed1337_income_first_hh1000.csv` | `run_meta_incomefirst.csv` | Per-arm wall-clock and payment coverage markers, `income_first` |
| `meta_seed1337_legacy_hh5000.csv` | `run_meta_hh5000.csv` | Creation and step wall-clock, abort status, legacy 5k |
| `checkpoints_seed1337_legacy_hh1000.csv` | `summary_seed1337.csv` | Hand-made checkpoint extract, legacy 1k seed 1337 |
| `log_seed7_legacy_hh1000.txt` | `seed7_run.log` | Console log, legacy 1k seed 7 |
| `log_seed1337_income_first_hh1000.txt` | `income_first_run.log` | Console log, `income_first` |
| `log_seed1337_legacy_hh5000.txt` | `scale5000_run.log` | Console log with pace checks, legacy 5k |
