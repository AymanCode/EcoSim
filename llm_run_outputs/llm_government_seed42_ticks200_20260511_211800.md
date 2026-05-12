# EcoSim LLM Government Run

- Run ID: `20260511_211800`
- Model: `inclusionai/ring-2.6-1t:free` via `openrouter`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$42,450`
- Min gov cash: `$42,450`
- Avg GDP: `$9,702`
- Final GDP: `$6,622`
- Avg unemployment: `15.4%`
- Final unemployment: `5.9%`
- Avg health: `0.772`
- Final health: `0.732`
- Avg happiness: `0.350`
- Final happiness: `0.220`
- Median wage: `$42.1`
- Mean wage: `$44.1`
- Median firm price: `$7.0`
- Mean firm price: `$9.0`
- Housing rent / median wage: `0.65`
- Target sector price / median wage: `0.00`
- Price increases limited: `0`
- Rent increases limited: `0`
- Homeless households: `75`
- Housing unaffordable failures: `75`
- Bailout spend this tick: `$24`
- Bailout budget remaining: `$4,926`
- Bailout cycle disbursed: `$74`
- Last cycle bailout disbursed: `$1,026`
- Last cycle bailout firms assisted: `2`

## Bailout Diagnostics

- Eligible firms by sector: `{'food': 2}`
- Denied firms by reason: `{'not_distressed_enough': 3, 'policy_target_mismatch': 4, 'computed_loan_amount_zero': 1}`
- Received by firm id: `{'5': 23.8221598411094}`

## Decision Quality

- Accepted decision rate: `87.5%` (7/8)
- Rejection rate: `0.0%` (0/18)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `68.6%` (24/35)
- Evidence audit counts: `{'matched_metric': 24, 'unknown_key': 10, 'value_mismatch': 1}`

## Final Policy

- `wage_tax_rate`: `0.2`
- `profit_tax_rate`: `0.25`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `neutral`
- `unemployment_benefit_level`: `30.0`
- `public_works`: `off`
- `minimum_wage_policy`: `neutral`
- `sector_subsidy_target`: `food`
- `sector_subsidy_level`: `50`
- `infrastructure_spending`: `low`
- `technology_spending`: `none`
- `price_stabilization_target`: `none`
- `price_stabilization_level`: `off`
- `rent_stabilization_level`: `off`
- `bailout_policy`: `sector`
- `bailout_target`: `food`
- `bailout_budget`: `5000`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | CASH_CRISIS | stabilize_cash | `{'wage_tax_rate': 0.2, 'social_spending': 'low'}` | `{'wage_tax_rate': 0.2, 'social_spending': 'low'}` | `{}` | `{'wage_tax_rate': 0.2, 'social_spending': 'low'}` | none | $163,435 | $3,891 | 30.5% |
| 41 | LOW_CASH | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000, 'social_spending': 'none'}` | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000, 'social_spending': 'none'}` | `{}` | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000, 'social_spending': 'none'}` | none | $137,394 | $11,335 | 22.5% |
| 67 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10, 'social_spending': 'low'}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10, 'social_spending': 'low'}` | `{}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10, 'social_spending': 'low'}` | none | $73,242 | $13,318 | 12.5% |
| 93 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 25}` | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 25}` | `{}` | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 25}` | none | $57,172 | $9,393 | 33.3% |
| 119 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': '50', 'social_spending': 'medium'}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 50, 'social_spending': 'medium'}` | `{}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 50, 'social_spending': 'medium'}` | none | $56,202 | $10,433 | 29.7% |
| 145 | NORMAL | reduce_unemployment | `{'wage_tax_rate': 0.15, 'infrastructure_spending': 'low'}` | `{'wage_tax_rate': 0.15, 'infrastructure_spending': 'low'}` | `{}` | `{'wage_tax_rate': 0.15, 'infrastructure_spending': 'low'}` | none | $59,496 | $9,208 | 10.0% |
| 171 | NORMAL | hold | `{}` | `{}` | `{}` | `{}` | none | $49,321 | $8,076 | 2.7% |
| 197 | LOW_CASH | stabilize_cash | `{'wage_tax_rate': 0.2, 'profit_tax_rate': 0.25}` | `{'wage_tax_rate': 0.2, 'profit_tax_rate': 0.25}` | `{}` | `{'wage_tax_rate': 0.2, 'profit_tax_rate': 0.25}` | none | $42,819 | $6,428 | 4.2% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 3 | $36.0 | $5.00 | $-71,948 | $505 | $-15,917 | $-124 | -663.2 | neg_cash, neg_profit, neg_net_worth, survival, burn |
| 2 | housing | True | 11 | $36.0 | $26.91 | $172,139 | $2,949,379 | $1,343,765 | $-461 | 373.8 | neg_profit |
| 3 | services | True | 3 | $36.0 | $8.24 | $-15,385 | $7,609 | $-21,990 | $-116 | -150.3 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 4 | $20.0 | $10.91 | $340 | $247 | $3,007 | $-47 | 4.9 | neg_profit |
| 5 | food | False | 1 | $45.0 | $4.69 | $7,722 | $913 | $8,938 | $-23 | 144.1 | neg_profit |
| 6 | food | False | 1 | $45.0 | $4.25 | $8,439 | $0 | $11,749 | $3 | 152.7 | ok |
| 7 | food | False | 1 | $45.0 | $5.42 | $312 | $500 | $11,125 | $27 | 5.7 | burn |
| 8 | food | False | 37 | $45.0 | $6.98 | $77,363 | $0 | $120,416 | $1,023 | 41.5 | ok |
| 13 | services | False | 116 | $36.0 | $8.90 | $28,877 | $1,665 | $97,225 | $-1,801 | 6.5 | neg_profit |
