# EcoSim LLM Government Run

- Run ID: `20260512_035405`
- Model: `llama-3.3-70b-versatile` via `groq`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$75,197`
- Min gov cash: `$64,434`
- Avg GDP: `$48,749`
- Final GDP: `$47,971`
- Avg unemployment: `20.0%`
- Final unemployment: `18.8%`
- Avg health: `0.804`
- Final health: `0.758`
- Avg happiness: `0.235`
- Final happiness: `0.045`
- Median wage: `$50.1`
- Mean wage: `$49.1`
- Median firm price: `$5.3`
- Mean firm price: `$8.2`
- Housing rent / median wage: `0.10`
- Target sector price / median wage: `0.00`
- Price increases limited: `0`
- Rent increases limited: `0`
- Homeless households: `0`
- Housing unaffordable failures: `0`
- Bailout spend this tick: `$86`
- Bailout budget remaining: `$9,742`
- Bailout cycle disbursed: `$258`
- Last cycle bailout disbursed: `$2,819`
- Last cycle bailout firms assisted: `4`

## Bailout Diagnostics

- Eligible firms by sector: `{'food': 4}`
- Denied firms by reason: `{'not_distressed_enough': 13, 'policy_target_mismatch': 13, 'computed_loan_amount_zero': 1}`
- Received by firm id: `{'7': 19.415494803434893, '5': 37.05636136452294, '6': 29.641118299363754}`

## Decision Quality

- Accepted decision rate: `100.0%` (8/8)
- Rejection rate: `0.0%` (0/17)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `86.7%` (26/30)
- Evidence audit counts: `{'matched_metric': 26, 'format_issue': 4}`

## Final Policy

- `wage_tax_rate`: `0.2`
- `profit_tax_rate`: `0.2`
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
- `bailout_target`: `food`
- `bailout_budget`: `10000`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | LOW_CASH | stabilize_cash | `{'social_spending': 'low', 'wage_tax_rate': 0.2}` | `{'social_spending': 'low', 'wage_tax_rate': 0.2}` | `{}` | `{'social_spending': 'low', 'wage_tax_rate': 0.2}` | none | $490,541 | $17,239 | 30.4% |
| 41 | LOW_CASH | stabilize_cash | `{'social_spending': 'none'}` | `{'social_spending': 'none'}` | `{}` | `{'social_spending': 'none'}` | none | $113,940 | $43,040 | 18.2% |
| 67 | NORMAL | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 5000}` | `{'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 5000}` | `{}` | `{'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 5000}` | none | $128,369 | $57,104 | 31.4% |
| 93 | LOW_CASH | stabilize_cash | `{'wage_tax_rate': 0.25, 'social_spending': 'none'}` | `{'wage_tax_rate': 0.25}` | `{}` | `{'wage_tax_rate': 0.25}` | none | $92,464 | $60,095 | 34.8% |
| 119 | NORMAL | essential_sector_support | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{}` | `{'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | none | $106,882 | $51,678 | 20.3% |
| 145 | NORMAL | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 10000}` | `{'bailout_target': 'food', 'bailout_budget': 10000}` | `{}` | `{'bailout_target': 'food', 'bailout_budget': 10000}` | none | $151,941 | $58,088 | 7.4% |
| 171 | LOW_CASH | stabilize_cash | `{'wage_tax_rate': 0.2, 'social_spending': 'low'}` | `{'wage_tax_rate': 0.2, 'social_spending': 'low'}` | `{}` | `{'wage_tax_rate': 0.2, 'social_spending': 'low'}` | none | $111,540 | $44,908 | 19.3% |
| 197 | NORMAL | essential_sector_support | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 25}` | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 25}` | `{}` | `{'sector_subsidy_target': 'services', 'sector_subsidy_level': 25}` | none | $73,073 | $47,555 | 16.8% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 3 | $36.0 | $5.00 | $-1,066,060 | $0 | $-1,049,722 | $-128 | -9493.8 | neg_cash, neg_profit, neg_net_worth, survival, burn |
| 2 | housing | True | 50 | $36.0 | $5.00 | $2,383,544 | $0 | $22,384,549 | $-2,196 | 1082.8 | neg_profit |
| 3 | services | True | 2 | $36.0 | $7.47 | $-17,158 | $9,091 | $-25,168 | $-79 | -228.0 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 20 | $20.0 | $10.80 | $-28,969 | $0 | $-27,964 | $-141 | -72.1 | neg_cash, neg_profit, neg_net_worth |
| 5 | food | False | 1 | $45.0 | $4.69 | $7,966 | $1,362 | $7,736 | $-38 | 145.4 | neg_profit |
| 6 | food | False | 1 | $45.0 | $3.99 | $8,441 | $1,164 | $8,506 | $-31 | 153.4 | neg_profit |
| 7 | food | False | 1 | $45.0 | $5.42 | $3,006 | $730 | $4,545 | $-21 | 60.5 | neg_profit |
| 8 | food | False | 1 | $45.0 | $4.38 | $11,410 | $0 | $13,961 | $12 | 221.1 | ok |
| 9 | food | False | 2 | $45.0 | $4.58 | $11,088 | $548 | $16,838 | $75 | 191.7 | ok |
| 10 | food | False | 4 | $45.0 | $4.73 | $1,392 | $1,850 | $14,102 | $384 | 8.0 | ok |
| 11 | food | False | 20 | $45.0 | $5.34 | $6,096 | $12,240 | $31,291 | $458 | 5.2 | ok |
| 12 | food | False | 6 | $45.0 | $5.14 | $1,004 | $3,023 | $15,910 | $375 | 3.5 | ok |
| 13 | food | False | 15 | $45.0 | $5.35 | $149,695 | $190 | $194,813 | $1,214 | 178.1 | ok |
| 14 | food | False | 27 | $45.0 | $5.14 | $37,082 | $0 | $80,659 | $600 | 22.6 | ok |
| 15 | food | False | 28 | $45.0 | $4.41 | $15,294 | $0 | $58,802 | $733 | 9.5 | ok |
| 16 | food | False | 38 | $45.0 | $4.06 | $34,661 | $0 | $77,988 | $920 | 16.8 | ok |
| 17 | food | False | 27 | $45.0 | $5.26 | $10,621 | $7,138 | $47,341 | $672 | 6.3 | ok |
| 18 | food | False | 29 | $45.0 | $4.50 | $16,673 | $0 | $60,050 | $830 | 10.3 | ok |
| 23 | services | False | 94 | $36.9 | $11.05 | $1,846 | $0 | $73,849 | $105 | 0.5 | survival |
| 25 | services | False | 72 | $36.0 | $11.36 | $2,910 | $0 | $68,860 | $320 | 0.8 | survival |
| 29 | services | False | 50 | $36.0 | $14.31 | $-334 | $0 | $64,020 | $88 | -0.1 | neg_cash, survival |
| 31 | services | False | 2 | $36.0 | $13.74 | $139 | $197 | $1,064 | $-79 | 1.8 | neg_profit, survival |
| 32 | services | False | 71 | $36.0 | $11.39 | $5,634 | $2,168 | $61,076 | $1 | 1.4 | survival |
| 33 | food | False | 4 | $45.0 | $6.09 | $16,476 | $1,246 | $28,214 | $286 | 75.6 | ok |
| 34 | services | False | 57 | $36.0 | $14.89 | $305 | $9,242 | $32,644 | $118 | 0.3 | survival |
| 35 | services | False | 60 | $45.0 | $12.63 | $7,735 | $17,516 | $36,270 | $437 | 2.8 | ok |
| 36 | services | False | 63 | $36.0 | $12.62 | $10,034 | $12,977 | $46,624 | $463 | 3.9 | ok |
| 37 | food | False | 1 | $45.0 | $4.97 | $20,743 | $0 | $27,130 | $183 | 405.9 | ok |
| 38 | services | False | 27 | $45.0 | $16.94 | $8,573 | $17,874 | $14,697 | $793 | 6.1 | ok |
| 39 | services | False | 16 | $36.0 | $21.60 | $18,994 | $12,945 | $25,469 | $667 | 27.9 | ok |
