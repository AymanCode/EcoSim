# EcoSim LLM Government Run

- Run ID: `20260512_035649`
- Model: `ibm-granite.granite-4.1-8b-GGUF` via `lmstudio`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$-16,885`
- Min gov cash: `$-16,885`
- Avg GDP: `$46,212`
- Final GDP: `$36,442`
- Avg unemployment: `22.6%`
- Final unemployment: `39.0%`
- Avg health: `0.805`
- Final health: `0.759`
- Avg happiness: `0.292`
- Final happiness: `0.074`
- Median wage: `$44.1`
- Mean wage: `$46.3`
- Median firm price: `$5.4`
- Mean firm price: `$7.2`
- Housing rent / median wage: `0.11`
- Target sector price / median wage: `0.00`
- Price increases limited: `0`
- Rent increases limited: `0`
- Homeless households: `0`
- Housing unaffordable failures: `0`
- Bailout spend this tick: `$0`
- Bailout budget remaining: `$50,000`
- Bailout cycle disbursed: `$0`
- Last cycle bailout disbursed: `$2,235`
- Last cycle bailout firms assisted: `3`

## Bailout Diagnostics

- Eligible firms by sector: `{}`
- Denied firms by reason: `{'government_cash_reserve_floor': 20}`
- Received by firm id: `{}`

## Decision Quality

- Accepted decision rate: `50.0%` (4/8)
- Rejection rate: `0.0%` (0/24)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `65.6%` (21/32)
- Evidence audit counts: `{'matched_metric': 21, 'unknown_key': 7, 'value_mismatch': 4}`

## Final Policy

- `wage_tax_rate`: `0.15`
- `profit_tax_rate`: `0.2`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `neutral`
- `unemployment_benefit_level`: `30.0`
- `public_works`: `off`
- `minimum_wage_policy`: `neutral`
- `sector_subsidy_target`: `none`
- `sector_subsidy_level`: `0`
- `infrastructure_spending`: `none`
- `technology_spending`: `none`
- `price_stabilization_target`: `none`
- `price_stabilization_level`: `off`
- `rent_stabilization_level`: `off`
- `bailout_policy`: `sector`
- `bailout_target`: `food`
- `bailout_budget`: `50000`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | CASH_CRISIS | stabilize_cash | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | `{}` | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | none | $490,541 | $17,239 | 30.4% |
| 41 | CASH_CRISIS | stabilize_cash | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 10000}` | `{'bailout_budget': 10000}` | `{}` | `{'bailout_budget': 10000}` | none | $97,713 | $43,672 | 18.5% |
| 67 | CASH_CRISIS | stabilize_cash | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 25000}` | `{'bailout_budget': 25000}` | `{}` | `{'bailout_budget': 25000}` | none | $105,407 | $56,153 | 30.1% |
| 93 | NORMAL | stabilize_cash | `{'bailout_budget': 50000, 'bailout_policy': 'sector', 'bailout_target': 'food'}` | `{'bailout_budget': 50000}` | `{}` | `{'bailout_budget': 50000}` | none | $59,177 | $52,258 | 32.0% |
| 119 | CASH_CRISIS | stabilize_cash | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 50000}` | `{}` | `{}` | `{}` | none | $76,125 | $52,950 | 23.2% |
| 145 | CASH_CRISIS | stabilize_cash | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 50000}` | `{}` | `{}` | `{}` | none | $99,131 | $47,197 | 20.0% |
| 171 | CASH_CRISIS | stabilize_cash | `{'bailout_budget': 50000, 'bailout_policy': 'sector', 'bailout_target': 'food'}` | `{}` | `{}` | `{}` | none | $58,347 | $45,005 | 28.7% |
| 197 | CASH_CRISIS | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 50000}` | `{}` | `{}` | `{}` | none | $-6,400 | $38,947 | 36.7% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 3 | $36.0 | $5.00 | $-1,066,040 | $0 | $-1,049,679 | $-129 | -9493.6 | neg_cash, neg_profit, neg_net_worth, survival, burn |
| 2 | housing | True | 50 | $36.0 | $5.00 | $2,493,813 | $0 | $22,494,818 | $-2,204 | 1128.6 | neg_profit |
| 3 | services | True | 2 | $36.0 | $7.40 | $-17,457 | $9,085 | $-25,462 | $-80 | -232.0 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 20 | $20.0 | $10.80 | $-28,688 | $0 | $-27,683 | $-119 | -71.4 | neg_cash, neg_profit, neg_net_worth |
| 5 | food | False | 1 | $45.0 | $4.69 | $7,625 | $1,258 | $7,492 | $-46 | 134.3 | neg_profit |
| 6 | food | False | 1 | $45.0 | $3.99 | $8,425 | $1,240 | $8,411 | $-38 | 154.7 | neg_profit |
| 7 | food | False | 1 | $45.0 | $5.42 | $2,754 | $630 | $4,382 | $-30 | 56.0 | neg_profit |
| 8 | food | False | 1 | $45.0 | $4.38 | $11,674 | $0 | $13,778 | $-7 | 226.4 | neg_profit |
| 9 | food | False | 0 | $45.0 | $3.80 | $11,667 | $0 | $16,591 | $0 | 202.0 | ok |
| 10 | food | False | 2 | $45.0 | $4.73 | $3,571 | $960 | $13,555 | $272 | 23.2 | ok |
| 11 | food | False | 14 | $45.0 | $5.12 | $2,971 | $9,759 | $28,110 | $380 | 3.4 | ok |
| 12 | food | False | 5 | $45.0 | $4.56 | $1,215 | $1,484 | $12,293 | $170 | 6.0 | ok |
| 13 | food | False | 9 | $45.0 | $5.35 | $147,384 | $91 | $189,967 | $879 | 287.3 | ok |
| 14 | food | False | 17 | $45.0 | $5.14 | $35,422 | $0 | $78,520 | $550 | 34.5 | ok |
| 15 | food | False | 20 | $45.0 | $4.04 | $11,580 | $0 | $54,807 | $505 | 9.4 | ok |
| 16 | food | False | 25 | $45.0 | $3.78 | $32,304 | $0 | $76,817 | $762 | 22.2 | ok |
| 17 | food | False | 21 | $45.0 | $4.96 | $8,231 | $5,366 | $43,370 | $384 | 6.6 | ok |
| 18 | food | False | 22 | $45.0 | $4.29 | $12,137 | $0 | $54,375 | $448 | 9.1 | ok |
| 25 | services | False | 69 | $36.0 | $11.61 | $1,493 | $0 | $84,861 | $349 | 0.4 | survival |
| 31 | services | False | 1 | $36.0 | $14.15 | $-387 | $0 | $736 | $-40 | -8.0 | neg_cash, neg_profit, survival |
| 32 | services | False | 67 | $36.0 | $11.06 | $5,599 | $0 | $77,085 | $456 | 1.9 | survival |
| 35 | services | False | 60 | $36.0 | $12.01 | $-123 | $4,848 | $46,099 | $472 | -0.0 | neg_cash, survival |
| 36 | services | False | 63 | $36.0 | $11.47 | $3,452 | $10,434 | $36,021 | $352 | 1.4 | survival |
| 37 | services | False | 58 | $36.0 | $13.17 | $11,726 | $10,616 | $47,050 | $46 | 5.0 | ok |
| 38 | food | False | 13 | $45.0 | $5.57 | $11,343 | $1,314 | $35,350 | $640 | 14.3 | ok |
| 39 | services | False | 28 | $36.0 | $16.04 | $16,263 | $8,113 | $37,605 | $664 | 14.5 | ok |
| 40 | food | False | 6 | $45.0 | $6.91 | $16,866 | $15,577 | $24,229 | $800 | 49.7 | ok |
| 41 | food | False | 11 | $45.0 | $6.03 | $24,897 | $1,522 | $42,483 | $638 | 36.2 | ok |
| 42 | food | False | 2 | $45.0 | $8.00 | $25,721 | $28,512 | $7,581 | $314 | 225.2 | ok |
| 43 | food | False | 3 | $45.0 | $8.11 | $19,903 | $20,731 | $7,018 | $540 | 368.7 | ok |
