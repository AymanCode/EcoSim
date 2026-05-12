# EcoSim LLM Government Run

- Run ID: `20260511_004841`
- Model: `llama-3.3-70b-versatile` via `groq`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$58,727`
- Min gov cash: `$55,834`
- Avg GDP: `$4,067`
- Final GDP: `$3,660`
- Avg unemployment: `2.6%`
- Final unemployment: `1.3%`
- Avg health: `0.791`
- Final health: `0.757`
- Avg happiness: `0.525`
- Final happiness: `0.356`
- Median wage: `$44.0`
- Mean wage: `$47.4`
- Median firm price: `$8.0`
- Mean firm price: `$9.8`
- Housing rent / median wage: `0.44`
- Target sector price / median wage: `0.00`
- Price increases limited: `0`
- Rent increases limited: `0`
- Homeless households: `4`
- Housing unaffordable failures: `4`
- Bailout spend this tick: `$1,132`
- Bailout budget remaining: `$21,893`
- Bailout cycle disbursed: `$3,107`
- Last cycle bailout disbursed: `$22,044`
- Last cycle bailout firms assisted: `4`

## Bailout Diagnostics

- Eligible firms by sector: `{'services': 4}`
- Denied firms by reason: `{'policy_target_mismatch': 7, 'not_distressed_enough': 1}`
- Received by firm id: `{'13': 460.723715147236, '9': 64.245679566261, '12': 550.3760475228621, '10': 56.72689964482956}`

## Decision Quality

- Accepted decision rate: `100.0%` (8/8)
- Rejection rate: `0.0%` (0/14)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `96.0%` (24/25)
- Evidence audit counts: `{'matched_metric': 24, 'format_issue': 1}`

## Final Policy

- `wage_tax_rate`: `0.15`
- `profit_tax_rate`: `0.25`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `neutral`
- `unemployment_benefit_level`: `30.0`
- `public_works`: `off`
- `minimum_wage_policy`: `neutral`
- `sector_subsidy_target`: `services`
- `sector_subsidy_level`: `25`
- `infrastructure_spending`: `none`
- `technology_spending`: `none`
- `price_stabilization_target`: `none`
- `price_stabilization_level`: `off`
- `rent_stabilization_level`: `off`
- `bailout_policy`: `sector`
- `bailout_target`: `services`
- `bailout_budget`: `25000`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | LOW_CASH | stabilize_cash | `{'social_spending': 'low', 'profit_tax_rate': '0.25'}` | `{'social_spending': 'low', 'profit_tax_rate': 0.25}` | `{}` | `{'social_spending': 'low', 'profit_tax_rate': 0.25}` | none | $95,746 | $2,870 | 13.8% |
| 41 | NORMAL | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | none | $59,371 | $4,274 | 2.5% |
| 67 | NORMAL | essential_sector_support | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 10}` | `{'sector_subsidy_target': 'services'}` | `{}` | `{'sector_subsidy_target': 'services'}` | none | $59,433 | $4,761 | 1.2% |
| 93 | STRONG_SURPLUS | essential_sector_support | `{'sector_subsidy_level': '25', 'sector_subsidy_target': 'services'}` | `{'sector_subsidy_level': 25}` | `{}` | `{'sector_subsidy_level': 25}` | none | $59,823 | $4,769 | 1.3% |
| 119 | NORMAL | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 5000}` | `{'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 5000}` | `{}` | `{'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 5000}` | none | $59,251 | $4,376 | 1.3% |
| 145 | NORMAL | essential_sector_support | `{'bailout_budget': 10000}` | `{'bailout_budget': 10000}` | `{}` | `{'bailout_budget': 10000}` | none | $59,176 | $4,471 | 0.0% |
| 171 | NORMAL | essential_sector_support | `{'bailout_budget': 25000}` | `{'bailout_budget': 25000}` | `{}` | `{'bailout_budget': 25000}` | none | $59,187 | $3,583 | 1.3% |
| 197 | LOW_CASH | stabilize_cash | `{'social_spending': 'none'}` | `{'social_spending': 'none'}` | `{}` | `{'social_spending': 'none'}` | none | $58,333 | $3,728 | 1.3% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 2 | $36.0 | $5.00 | $-22,608 | $480 | $59,700 | $-79 | -329.1 | neg_cash, neg_profit, survival, burn |
| 2 | housing | True | 3 | $36.0 | $18.71 | $135,191 | $950,710 | $1,105,486 | $-128 | 1052.6 | neg_profit |
| 3 | services | True | 3 | $36.0 | $7.72 | $-13,761 | $8,622 | $-21,378 | $-103 | -122.1 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 2 | $20.0 | $10.91 | $4,493 | $0 | $6,256 | $-7 | 112.5 | neg_profit |
| 5 | food | False | 2 | $45.0 | $5.06 | $1,232 | $0 | $2,546 | $-101 | 11.9 | neg_profit |
| 6 | food | False | 2 | $45.0 | $4.70 | $3,304 | $0 | $4,918 | $-90 | 30.6 | neg_profit |
| 7 | food | False | 1 | $45.0 | $5.42 | $10,242 | $0 | $12,752 | $-26 | 185.8 | neg_profit |
| 8 | food | False | 14 | $45.0 | $7.05 | $2,120 | $5,378 | $35,222 | $721 | 2.5 | ok |
| 9 | services | False | 3 | $36.0 | $18.74 | $193 | $1,858 | $983 | $-30 | 2.0 | neg_profit, survival |
| 10 | services | False | 3 | $36.0 | $16.61 | $241 | $2,617 | $1,111 | $0 | 2.0 | survival |
| 12 | services | False | 26 | $45.0 | $9.20 | $1,762 | $8,233 | $1,336 | $-162 | 2.0 | neg_profit, survival |
| 13 | services | False | 14 | $36.0 | $8.35 | $683 | $13,621 | $-8,801 | $-122 | 2.0 | neg_profit, neg_net_worth, survival |
