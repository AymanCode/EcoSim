# EcoSim LLM Government Run

- Run ID: `20260511_213704`
- Model: `inclusionai/ring-2.6-1t:free` via `openrouter`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$60,033`
- Min gov cash: `$58,633`
- Avg GDP: `$10,963`
- Final GDP: `$10,913`
- Avg unemployment: `13.8%`
- Final unemployment: `0.0%`
- Avg health: `0.770`
- Final health: `0.731`
- Avg happiness: `0.383`
- Final happiness: `0.251`
- Median wage: `$43.5`
- Mean wage: `$47.1`
- Median firm price: `$7.9`
- Mean firm price: `$11.2`
- Housing rent / median wage: `0.80`
- Target sector price / median wage: `0.13`
- Price increases limited: `1`
- Rent increases limited: `0`
- Homeless households: `88`
- Housing unaffordable failures: `88`
- Bailout spend this tick: `$0`
- Bailout budget remaining: `$5,000`
- Bailout cycle disbursed: `$0`
- Last cycle bailout disbursed: `$0`
- Last cycle bailout firms assisted: `0`

## Bailout Diagnostics

- Eligible firms by sector: `{}`
- Denied firms by reason: `{'policy_target_mismatch': 6, 'not_distressed_enough': 2}`
- Received by firm id: `{}`

## Decision Quality

- Accepted decision rate: `100.0%` (8/8)
- Rejection rate: `0.0%` (0/21)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `92.5%` (37/40)
- Evidence audit counts: `{'matched_metric': 37, 'format_issue': 2, 'unknown_key': 1}`

## Final Policy

- `wage_tax_rate`: `0.25`
- `profit_tax_rate`: `0.2`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `neutral`
- `unemployment_benefit_level`: `30.0`
- `public_works`: `off`
- `minimum_wage_policy`: `low`
- `sector_subsidy_target`: `housing`
- `sector_subsidy_level`: `25`
- `infrastructure_spending`: `none`
- `technology_spending`: `none`
- `price_stabilization_target`: `food`
- `price_stabilization_level`: `soft`
- `rent_stabilization_level`: `monitor`
- `bailout_policy`: `sector`
- `bailout_target`: `services`
- `bailout_budget`: `5000`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | CASH_CRISIS | reduce_unemployment | `{'wage_tax_rate': 0.1, 'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | `{'wage_tax_rate': 0.1, 'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | `{}` | `{'wage_tax_rate': 0.1, 'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | none | $163,435 | $3,891 | 30.5% |
| 41 | LOW_CASH | stabilize_cash | `{'wage_tax_rate': 0.15, 'social_spending': 'low'}` | `{'wage_tax_rate': 0.15, 'social_spending': 'low'}` | `{}` | `{'wage_tax_rate': 0.15, 'social_spending': 'low'}` | none | $130,336 | $11,349 | 22.5% |
| 67 | LOW_CASH | essential_sector_support | `{'bailout_target': 'services', 'price_stabilization_target': 'food', 'price_stabilization_level': 'monitor'}` | `{'bailout_target': 'services', 'price_stabilization_target': 'food', 'price_stabilization_level': 'monitor'}` | `{}` | `{'bailout_target': 'services', 'price_stabilization_target': 'food', 'price_stabilization_level': 'monitor'}` | none | $65,914 | $12,302 | 7.0% |
| 93 | LOW_CASH | stabilize_cash | `{'wage_tax_rate': 0.2, 'price_stabilization_level': 'soft'}` | `{'wage_tax_rate': 0.2, 'price_stabilization_level': 'soft'}` | `{}` | `{'wage_tax_rate': 0.2, 'price_stabilization_level': 'soft'}` | none | $62,383 | $11,152 | 32.3% |
| 119 | LOW_CASH | reduce_unemployment | `{'minimum_wage_policy': 'low', 'sector_subsidy_target': 'food', 'sector_subsidy_level': '10'}` | `{'minimum_wage_policy': 'low', 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{}` | `{'minimum_wage_policy': 'low', 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | none | $59,830 | $12,768 | 30.9% |
| 145 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'housing', 'sector_subsidy_level': 10, 'social_spending': 'medium'}` | `{'sector_subsidy_target': 'housing', 'social_spending': 'medium'}` | `{}` | `{'sector_subsidy_target': 'housing', 'social_spending': 'medium'}` | none | $63,583 | $11,728 | 15.8% |
| 171 | LOW_CASH | essential_sector_support | `{'sector_subsidy_level': 25, 'social_spending': 'high'}` | `{'sector_subsidy_level': 25, 'social_spending': 'high'}` | `{}` | `{'sector_subsidy_level': 25, 'social_spending': 'high'}` | none | $63,735 | $11,637 | 0.0% |
| 197 | LOW_CASH | stabilize_cash | `{'wage_tax_rate': 0.25, 'rent_stabilization_level': 'monitor'}` | `{'wage_tax_rate': 0.25, 'rent_stabilization_level': 'monitor'}` | `{}` | `{'wage_tax_rate': 0.25, 'rent_stabilization_level': 'monitor'}` | none | $59,405 | $11,238 | 0.0% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 3 | $25.0 | $5.00 | $-71,577 | $505 | $-15,551 | $-121 | -678.3 | neg_cash, neg_profit, neg_net_worth, survival, burn |
| 2 | housing | True | 9 | $36.0 | $34.94 | $27,444 | $4,072,845 | $115,604 | $-388 | 73.3 | neg_profit |
| 3 | services | True | 3 | $36.0 | $8.46 | $-15,630 | $7,525 | $-22,151 | $-118 | -145.2 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 4 | $20.0 | $10.80 | $2,581 | $0 | $4,337 | $-48 | 32.9 | neg_profit |
| 5 | food | False | 3 | $45.0 | $5.67 | $3,749 | $0 | $5,885 | $-124 | 25.2 | neg_profit |
| 6 | food | False | 3 | $45.0 | $5.44 | $5,614 | $0 | $8,430 | $-98 | 37.6 | neg_profit |
| 8 | food | False | 42 | $45.0 | $7.32 | $91,081 | $0 | $134,135 | $1,330 | 38.5 | ok |
| 13 | services | False | 119 | $46.8 | $11.93 | $155,119 | $1,665 | $218,508 | $1,133 | 28.6 | ok |
