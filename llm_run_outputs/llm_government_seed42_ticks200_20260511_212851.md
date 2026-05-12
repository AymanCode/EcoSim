# EcoSim LLM Government Run

- Run ID: `20260511_212851`
- Model: `inclusionai/ring-2.6-1t:free` via `openrouter`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$65,775`
- Min gov cash: `$56,992`
- Avg GDP: `$11,625`
- Final GDP: `$15,695`
- Avg unemployment: `15.6%`
- Final unemployment: `1.1%`
- Avg health: `0.775`
- Final health: `0.747`
- Avg happiness: `0.330`
- Final happiness: `0.180`
- Median wage: `$54.3`
- Mean wage: `$50.7`
- Median firm price: `$9.1`
- Mean firm price: `$12.2`
- Housing rent / median wage: `0.65`
- Target sector price / median wage: `0.28`
- Price increases limited: `0`
- Rent increases limited: `0`
- Homeless households: `90`
- Housing unaffordable failures: `90`
- Bailout spend this tick: `$360`
- Bailout budget remaining: `$3,560`
- Bailout cycle disbursed: `$1,440`
- Last cycle bailout disbursed: `$5,000`
- Last cycle bailout firms assisted: `3`

## Bailout Diagnostics

- Eligible firms by sector: `{'food': 3}`
- Denied firms by reason: `{'not_distressed_enough': 2, 'policy_target_mismatch': 4}`
- Received by firm id: `{'7': 102.54614528167593, '5': 171.7727905418824, '6': 86.07445074007889}`

## Decision Quality

- Accepted decision rate: `100.0%` (8/8)
- Rejection rate: `0.0%` (0/23)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `65.0%` (26/40)
- Evidence audit counts: `{'matched_metric': 26, 'unknown_key': 13, 'value_mismatch': 1}`

## Final Policy

- `wage_tax_rate`: `0.2`
- `profit_tax_rate`: `0.2`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `neutral`
- `unemployment_benefit_level`: `30.0`
- `public_works`: `off`
- `minimum_wage_policy`: `neutral`
- `sector_subsidy_target`: `housing`
- `sector_subsidy_level`: `10`
- `infrastructure_spending`: `none`
- `technology_spending`: `none`
- `price_stabilization_target`: `services`
- `price_stabilization_level`: `soft`
- `rent_stabilization_level`: `monitor`
- `bailout_policy`: `sector`
- `bailout_target`: `food`
- `bailout_budget`: `5000`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | CASH_CRISIS | stabilize_cash | `{'social_spending': 'low', 'price_stabilization_target': 'food', 'price_stabilization_level': 'monitor'}` | `{'social_spending': 'low', 'price_stabilization_target': 'food', 'price_stabilization_level': 'monitor'}` | `{}` | `{'social_spending': 'low', 'price_stabilization_target': 'food', 'price_stabilization_level': 'monitor'}` | none | $163,435 | $3,891 | 30.5% |
| 41 | LOW_CASH | stabilize_cash | `{'wage_tax_rate': 0.2, 'social_spending': 'none'}` | `{'wage_tax_rate': 0.2, 'social_spending': 'none'}` | `{}` | `{'wage_tax_rate': 0.2, 'social_spending': 'none'}` | none | $135,277 | $11,377 | 22.5% |
| 67 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 10}` | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 10}` | `{}` | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 10}` | none | $70,142 | $12,398 | 13.5% |
| 93 | LOW_CASH | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000, 'price_stabilization_target': 'food', 'price_stabilization_level': 'soft'}` | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000, 'price_stabilization_level': 'soft'}` | `{}` | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000, 'price_stabilization_level': 'soft'}` | none | $64,431 | $11,843 | 27.3% |
| 119 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 25}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 25}` | `{}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 25}` | none | $59,312 | $14,767 | 35.9% |
| 145 | LOW_CASH | support_growth | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 25, 'social_spending': 'low'}` | `{'sector_subsidy_target': 'services', 'social_spending': 'low'}` | `{}` | `{'sector_subsidy_target': 'services', 'social_spending': 'low'}` | none | $65,589 | $13,611 | 9.9% |
| 171 | LOW_CASH | essential_sector_support | `{'social_spending': 'medium', 'price_stabilization_target': 'services', 'price_stabilization_level': 'soft'}` | `{'social_spending': 'medium', 'price_stabilization_target': 'services'}` | `{}` | `{'social_spending': 'medium', 'price_stabilization_target': 'services'}` | none | $63,018 | $12,499 | 0.0% |
| 197 | NORMAL | essential_sector_support | `{'rent_stabilization_level': 'monitor', 'sector_subsidy_target': 'housing', 'sector_subsidy_level': 10}` | `{'rent_stabilization_level': 'monitor', 'sector_subsidy_target': 'housing', 'sector_subsidy_level': 10}` | `{}` | `{'rent_stabilization_level': 'monitor', 'sector_subsidy_target': 'housing', 'sector_subsidy_level': 10}` | none | $64,405 | $15,953 | 0.5% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 3 | $36.0 | $5.00 | $-72,164 | $505 | $-16,164 | $-125 | -656.3 | neg_cash, neg_profit, neg_net_worth, survival, burn |
| 2 | housing | True | 11 | $36.0 | $35.32 | $39,950 | $4,079,362 | $121,592 | $-459 | 89.6 | neg_profit |
| 3 | services | True | 1 | $36.0 | $10.15 | $-9,791 | $7,643 | $-16,428 | $-17 | -261.3 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 4 | $20.0 | $10.80 | $2,507 | $0 | $4,161 | $-37 | 31.8 | neg_profit |
| 5 | food | False | 5 | $45.0 | $6.26 | $5,049 | $3,873 | $3,318 | $-228 | 25.1 | neg_profit |
| 6 | food | False | 3 | $45.0 | $5.26 | $7,212 | $1,568 | $8,492 | $-93 | 45.2 | neg_profit |
| 7 | food | False | 5 | $45.0 | $8.45 | $656 | $2,543 | $4,566 | $-167 | 4.2 | neg_profit |
| 8 | food | False | 41 | $45.0 | $9.13 | $102,104 | $0 | $145,157 | $2,007 | 45.1 | ok |
| 13 | services | False | 115 | $50.3 | $19.74 | $230,357 | $1,665 | $299,689 | $3,882 | 39.0 | ok |
