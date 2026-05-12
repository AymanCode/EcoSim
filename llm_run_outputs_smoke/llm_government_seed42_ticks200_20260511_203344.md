# EcoSim LLM Government Run

- Run ID: `20260511_203344`
- Model: `openai/gpt-oss-120b` via `groq`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$4,077`
- Min gov cash: `$133`
- Avg GDP: `$4,286`
- Final GDP: `$4,091`
- Avg unemployment: `3.1%`
- Final unemployment: `9.1%`
- Avg health: `0.791`
- Final health: `0.762`
- Avg happiness: `0.640`
- Final happiness: `0.525`
- Median wage: `$50.0`
- Mean wage: `$49.3`
- Median firm price: `$8.8`
- Mean firm price: `$10.8`
- Housing rent / median wage: `0.40`
- Target sector price / median wage: `0.28`
- Price increases limited: `1`
- Rent increases limited: `0`
- Homeless households: `3`
- Housing unaffordable failures: `3`
- Bailout spend this tick: `$0`
- Bailout budget remaining: `$0`
- Bailout cycle disbursed: `$0`
- Last cycle bailout disbursed: `$0`
- Last cycle bailout firms assisted: `0`

## Bailout Diagnostics

- Eligible firms by sector: `{}`
- Denied firms by reason: `{'policy_off': 10}`
- Received by firm id: `{}`

## Decision Quality

- Accepted decision rate: `100.0%` (8/8)
- Rejection rate: `0.0%` (0/27)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `94.6%` (35/37)
- Evidence audit counts: `{'matched_metric': 31, 'matched_policy': 4, 'format_issue': 2}`

## Final Policy

- `wage_tax_rate`: `0.15`
- `profit_tax_rate`: `0.1`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `neutral`
- `unemployment_benefit_level`: `30.0`
- `public_works`: `off`
- `minimum_wage_policy`: `neutral`
- `sector_subsidy_target`: `food`
- `sector_subsidy_level`: `25`
- `infrastructure_spending`: `low`
- `technology_spending`: `none`
- `price_stabilization_target`: `services`
- `price_stabilization_level`: `strict`
- `rent_stabilization_level`: `off`
- `bailout_policy`: `off`
- `bailout_target`: `none`
- `bailout_budget`: `0`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | NORMAL | support_growth | `{'profit_tax_rate': '0.15', 'infrastructure_spending': 'low'}` | `{'profit_tax_rate': 0.15, 'infrastructure_spending': 'low'}` | `{}` | `{'profit_tax_rate': 0.15, 'infrastructure_spending': 'low'}` | none | $95,746 | $2,870 | 13.8% |
| 41 | LOW_CASH | support_growth | `{'profit_tax_rate': '0.1', 'sector_subsidy_target': 'food', 'sector_subsidy_level': '10'}` | `{'profit_tax_rate': 0.1, 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{}` | `{'profit_tax_rate': 0.1, 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | none | $50,715 | $4,384 | 3.8% |
| 67 | LOW_CASH | support_growth | `{'sector_subsidy_level': '25', 'price_stabilization_target': 'services', 'price_stabilization_level': 'monitor'}` | `{'sector_subsidy_level': 25, 'price_stabilization_target': 'services', 'price_stabilization_level': 'monitor'}` | `{}` | `{'sector_subsidy_level': 25, 'price_stabilization_target': 'services', 'price_stabilization_level': 'monitor'}` | none | $23,115 | $4,014 | 2.5% |
| 93 | LOW_CASH | essential_sector_support | `{'price_stabilization_target': 'services', 'price_stabilization_level': 'soft', 'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 5000}` | `{'price_stabilization_level': 'soft', 'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 5000}` | `{}` | `{'price_stabilization_level': 'soft', 'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 5000}` | none | $5,294 | $4,671 | 0.0% |
| 119 | LOW_CASH | hold | `{'social_spending': 'low', 'bailout_policy': 'off', 'bailout_target': 'none', 'bailout_budget': 0}` | `{'social_spending': 'low', 'bailout_policy': 'off', 'bailout_target': 'none', 'bailout_budget': 0}` | `{}` | `{'social_spending': 'low', 'bailout_policy': 'off', 'bailout_target': 'none', 'bailout_budget': 0}` | none | $139 | $4,824 | 0.0% |
| 145 | NORMAL | essential_sector_support | `{'profit_tax_rate': 0.15, 'sector_subsidy_target': 'housing', 'sector_subsidy_level': 25}` | `{'profit_tax_rate': 0.15, 'sector_subsidy_target': 'housing'}` | `{}` | `{'profit_tax_rate': 0.15, 'sector_subsidy_target': 'housing'}` | none | $4,298 | $4,539 | 0.0% |
| 171 | NORMAL | essential_sector_support | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 25, 'price_stabilization_target': 'services', 'price_stabilization_level': 'strict'}` | `{'sector_subsidy_target': 'services', 'price_stabilization_level': 'strict'}` | `{}` | `{'sector_subsidy_target': 'services', 'price_stabilization_level': 'strict'}` | none | $7,981 | $4,876 | 0.0% |
| 197 | NORMAL | support_growth | `{'profit_tax_rate': '0.1', 'sector_subsidy_target': 'food', 'sector_subsidy_level': '25'}` | `{'profit_tax_rate': 0.1, 'sector_subsidy_target': 'food'}` | `{}` | `{'profit_tax_rate': 0.1, 'sector_subsidy_target': 'food'}` | none | $5,111 | $3,648 | 5.2% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 2 | $36.0 | $5.00 | $-19,454 | $480 | $62,838 | $-86 | -259.3 | neg_cash, neg_profit, survival, burn |
| 2 | housing | True | 5 | $36.0 | $19.59 | $132,374 | $950,710 | $1,102,669 | $-205 | 642.6 | neg_profit |
| 3 | services | True | 3 | $36.0 | $7.19 | $-13,074 | $8,630 | $-20,699 | $-105 | -115.9 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 2 | $20.0 | $10.61 | $2,421 | $0 | $5,768 | $-19 | 61.0 | neg_profit |
| 6 | food | False | 1 | $45.0 | $3.99 | $11,525 | $0 | $13,145 | $-30 | 219.8 | neg_profit |
| 7 | food | False | 1 | $45.0 | $5.42 | $12,896 | $0 | $15,460 | $-19 | 264.9 | neg_profit |
| 8 | food | False | 15 | $45.0 | $8.05 | $15,710 | $79 | $54,026 | $790 | 17.4 | ok |
| 9 | services | False | 1 | $36.0 | $29.45 | $0 | $1,375 | $1,026 | $43 | 0.0 | survival |
| 12 | services | False | 31 | $47.0 | $9.48 | $60 | $0 | $24,890 | $111 | 0.0 | survival |
| 13 | services | False | 9 | $36.0 | $9.66 | $-89 | $4,535 | $10,412 | $58 | -0.4 | neg_cash, survival |
