# EcoSim LLM Government Run

- Run ID: `20260511_000251`
- Model: `gemma-4-26B-A4B-it-Q4_K_M.gguf` via `lmstudio`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$55,286`
- Min gov cash: `$41,897`
- Avg GDP: `$4,276`
- Final GDP: `$4,832`
- Avg unemployment: `3.5%`
- Final unemployment: `2.6%`
- Avg health: `0.797`
- Final health: `0.777`
- Avg happiness: `0.616`
- Final happiness: `0.524`
- Median wage: `$52.0`
- Mean wage: `$51.6`
- Median firm price: `$9.0`
- Mean firm price: `$12.6`
- Housing rent / median wage: `0.37`
- Target sector price / median wage: `0.36`
- Price increases limited: `0`
- Rent increases limited: `0`
- Homeless households: `0`
- Housing unaffordable failures: `0`
- Bailout spend this tick: `$279`
- Bailout budget remaining: `$8,941`
- Bailout cycle disbursed: `$1,059`
- Last cycle bailout disbursed: `$8,538`
- Last cycle bailout firms assisted: `3`

## Bailout Diagnostics

- Eligible firms by sector: `{'services': 4}`
- Denied firms by reason: `{'policy_target_mismatch': 7, 'not_distressed_enough': 1, 'computed_loan_amount_zero': 1}`
- Received by firm id: `{'11': 130.59940515911256, '10': 147.30097437413764, '9': 0.8410174760253426}`

## Decision Quality

- Accepted decision rate: `100.0%` (8/8)
- Rejection rate: `5.0%` (1/20)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `5.0%`
- Evidence match rate: `55.2%` (16/29)
- Evidence audit counts: `{'matched_metric': 16, 'unknown_key': 12, 'format_issue': 1}`

## Final Policy

- `wage_tax_rate`: `0.15`
- `profit_tax_rate`: `0.2`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `neutral`
- `unemployment_benefit_level`: `30.0`
- `public_works`: `off`
- `minimum_wage_policy`: `neutral`
- `sector_subsidy_target`: `food`
- `sector_subsidy_level`: `10`
- `infrastructure_spending`: `none`
- `technology_spending`: `none`
- `price_stabilization_target`: `services`
- `price_stabilization_level`: `monitor`
- `rent_stabilization_level`: `off`
- `bailout_policy`: `sector`
- `bailout_target`: `services`
- `bailout_budget`: `10000`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | LOW_CASH | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': '5000'}` | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | `{}` | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | none | $95,746 | $2,870 | 13.8% |
| 41 | NORMAL | essential_sector_support | `{'bailout_target': 'food', 'bailout_budget': 10000}` | `{'bailout_budget': 10000}` | `{}` | `{'bailout_budget': 10000}` | none | $57,241 | $4,302 | 2.5% |
| 67 | NORMAL | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': '5000'}` | `{'bailout_target': 'services', 'bailout_budget': 5000}` | `{}` | `{'bailout_target': 'services', 'bailout_budget': 5000}` | none | $50,852 | $4,348 | 2.5% |
| 93 | NORMAL | essential_sector_support | `{'bailout_budget': 10000}` | `{'bailout_budget': 10000}` | `{}` | `{'bailout_budget': 10000}` | none | $52,213 | $3,973 | 2.5% |
| 119 | NORMAL | essential_sector_support | `{'bailout_policy': 'all', 'bailout_target': 'none', 'bailout_budget': 10000}` | `{'bailout_policy': 'all', 'bailout_target': 'none'}` | `{}` | `{'bailout_policy': 'all', 'bailout_target': 'none'}` | none | $53,453 | $4,104 | 1.3% |
| 145 | LOW_CASH | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 10000}` | `{'bailout_policy': 'sector', 'bailout_target': 'services'}` | `{}` | `{'bailout_policy': 'sector', 'bailout_target': 'services'}` | none | $46,172 | $3,463 | 21.5% |
| 171 | NORMAL | essential_sector_support | `{'bailout_budget': '15000', 'price_stabilization_target': 'services', 'price_stabilization_level': 'monitor'}` | `{'price_stabilization_target': 'services', 'price_stabilization_level': 'monitor'}` | `{}` | `{'price_stabilization_target': 'services', 'price_stabilization_level': 'monitor'}` | bailout=15000 (invalid_enum_value) | $53,736 | $5,448 | 0.0% |
| 197 | NORMAL | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': '10'}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | none | $55,498 | $4,584 | 2.6% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 3 | $36.0 | $5.00 | $-26,146 | $480 | $56,146 | $-120 | -252.3 | neg_cash, neg_profit, survival, burn |
| 2 | housing | True | 4 | $36.0 | $19.17 | $129,332 | $950,710 | $1,099,626 | $-168 | 766.7 | neg_profit |
| 3 | services | True | 3 | $36.0 | $6.70 | $-14,142 | $8,622 | $-21,759 | $-110 | -125.4 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 2 | $20.0 | $10.80 | $4,412 | $0 | $6,175 | $-18 | 110.8 | neg_profit |
| 5 | food | False | 1 | $45.0 | $4.69 | $7,863 | $74 | $9,107 | $-49 | 127.2 | neg_profit |
| 6 | food | False | 1 | $45.0 | $4.50 | $9,111 | $71 | $10,661 | $-43 | 138.2 | neg_profit |
| 7 | food | False | 1 | $45.0 | $5.42 | $9,027 | $51 | $12,218 | $-25 | 163.8 | neg_profit |
| 8 | food | False | 14 | $45.0 | $7.25 | $7,062 | $5,648 | $41,797 | $776 | 7.4 | ok |
| 9 | services | False | 2 | $36.0 | $19.56 | $123 | $2,055 | $8,961 | $-9 | 2.1 | neg_profit, survival |
| 10 | services | False | 3 | $36.0 | $16.00 | $139 | $6,412 | $5,195 | $-15 | 2.0 | neg_profit, survival |
| 11 | services | False | 2 | $36.0 | $39.59 | $37 | $6,084 | $-84 | $-15 | 2.0 | neg_profit, neg_net_worth, survival |
| 12 | services | False | 39 | $47.1 | $12.20 | $3,933 | $10,980 | $19,500 | $463 | 2.2 | ok |
