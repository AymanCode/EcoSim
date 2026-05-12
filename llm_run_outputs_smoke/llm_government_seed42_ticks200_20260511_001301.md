# EcoSim LLM Government Run

- Run ID: `20260511_001301`
- Model: `ibm-granite.granite-4.1-8b.f16.gguf.Q4_K_M.gguf` via `lmstudio`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$36,678`
- Min gov cash: `$20,678`
- Avg GDP: `$5,061`
- Final GDP: `$6,333`
- Avg unemployment: `6.3%`
- Final unemployment: `0.0%`
- Avg health: `0.794`
- Final health: `0.760`
- Avg happiness: `0.679`
- Final happiness: `0.697`
- Median wage: `$54.6`
- Mean wage: `$55.5`
- Median firm price: `$7.2`
- Mean firm price: `$11.6`
- Housing rent / median wage: `0.35`
- Target sector price / median wage: `0.00`
- Price increases limited: `0`
- Rent increases limited: `0`
- Homeless households: `0`
- Housing unaffordable failures: `0`
- Bailout spend this tick: `$0`
- Bailout budget remaining: `$0`
- Bailout cycle disbursed: `$0`
- Last cycle bailout disbursed: `$0`
- Last cycle bailout firms assisted: `0`

## Bailout Diagnostics

- Eligible firms by sector: `{}`
- Denied firms by reason: `{'policy_off': 8}`
- Received by firm id: `{}`

## Decision Quality

- Accepted decision rate: `25.0%` (2/8)
- Rejection rate: `0.0%` (0/16)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `75.7%` (28/37)
- Evidence audit counts: `{'matched_metric': 19, 'unknown_key': 9, 'matched_policy': 9}`

## Final Policy

- `wage_tax_rate`: `0.15`
- `profit_tax_rate`: `0.2`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `neutral`
- `unemployment_benefit_level`: `30.0`
- `public_works`: `off`
- `minimum_wage_policy`: `neutral`
- `sector_subsidy_target`: `food`
- `sector_subsidy_level`: `25`
- `infrastructure_spending`: `none`
- `technology_spending`: `none`
- `price_stabilization_target`: `none`
- `price_stabilization_level`: `off`
- `rent_stabilization_level`: `off`
- `bailout_policy`: `off`
- `bailout_target`: `none`
- `bailout_budget`: `0`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | none | $95,746 | $2,870 | 13.8% |
| 41 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 25}` | `{'sector_subsidy_level': 25}` | `{}` | `{'sector_subsidy_level': 25}` | none | $55,651 | $4,354 | 3.8% |
| 67 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 25}` | `{}` | `{}` | `{}` | none | $42,566 | $4,018 | 3.8% |
| 93 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 25}` | `{}` | `{}` | `{}` | none | $40,487 | $4,069 | 3.8% |
| 119 | CASH_CRISIS | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 25}` | `{}` | `{}` | `{}` | none | $22,560 | $5,260 | 5.1% |
| 145 | LOW_CASH | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 25}` | `{}` | `{}` | `{}` | none | $31,764 | $6,866 | 7.6% |
| 171 | NORMAL | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 25}` | `{}` | `{}` | `{}` | none | $37,089 | $6,697 | 1.3% |
| 197 | NORMAL | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 25}` | `{}` | `{}` | `{}` | none | $36,607 | $6,338 | 0.0% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 2 | $36.0 | $5.00 | $-22,384 | $480 | $59,890 | $-81 | -316.9 | neg_cash, neg_profit, survival, burn |
| 2 | housing | True | 4 | $36.0 | $19.31 | $136,767 | $950,710 | $1,107,062 | $-180 | 755.5 | neg_profit |
| 3 | services | True | 2 | $36.0 | $6.87 | $-9,212 | $8,627 | $-16,834 | $-78 | -122.6 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 2 | $20.0 | $10.80 | $4,405 | $0 | $6,168 | $-18 | 110.6 | neg_profit |
| 6 | food | False | 3 | $45.0 | $4.56 | $5,338 | $0 | $6,958 | $-137 | 35.1 | neg_profit |
| 7 | food | False | 1 | $45.0 | $5.42 | $12,012 | $0 | $14,502 | $-21 | 239.4 | neg_profit |
| 8 | food | False | 16 | $50.5 | $7.47 | $10,374 | $3,691 | $48,074 | $771 | 10.5 | ok |
| 10 | services | False | 46 | $52.9 | $33.42 | $20,024 | $28,288 | $27,396 | $1,359 | 7.7 | ok |
