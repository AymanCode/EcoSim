# EcoSim LLM Government Run

- Run ID: `20260512_032357`
- Model: `inclusionai/ring-2.6-1t:free` via `openrouter`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$58,844`
- Min gov cash: `$58,163`
- Avg GDP: `$51,097`
- Final GDP: `$47,252`
- Avg unemployment: `18.3%`
- Final unemployment: `11.1%`
- Avg health: `0.806`
- Final health: `0.763`
- Avg happiness: `0.300`
- Final happiness: `0.144`
- Median wage: `$52.8`
- Mean wage: `$51.2`
- Median firm price: `$5.4`
- Mean firm price: `$6.8`
- Housing rent / median wage: `0.10`
- Target sector price / median wage: `0.00`
- Price increases limited: `0`
- Rent increases limited: `0`
- Homeless households: `0`
- Housing unaffordable failures: `0`
- Bailout spend this tick: `$265`
- Bailout budget remaining: `$23,374`
- Bailout cycle disbursed: `$1,626`
- Last cycle bailout disbursed: `$0`
- Last cycle bailout firms assisted: `0`

## Bailout Diagnostics

- Eligible firms by sector: `{'food': 5}`
- Denied firms by reason: `{'not_distressed_enough': 15, 'policy_target_mismatch': 10, 'computed_loan_amount_zero': 1}`
- Received by firm id: `{'7': 94.7746085534867, '6': 82.54990094133814, '8': 53.15836003730524, '5': 34.758557072844674}`

## Decision Quality

- Accepted decision rate: `100.0%` (8/8)
- Rejection rate: `0.0%` (0/21)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `82.5%` (33/40)
- Evidence audit counts: `{'matched_metric': 33, 'unknown_key': 7}`

## Final Policy

- `wage_tax_rate`: `0.1`
- `profit_tax_rate`: `0.15`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `neutral`
- `unemployment_benefit_level`: `30.0`
- `public_works`: `on`
- `minimum_wage_policy`: `low`
- `sector_subsidy_target`: `food`
- `sector_subsidy_level`: `50`
- `infrastructure_spending`: `low`
- `technology_spending`: `none`
- `price_stabilization_target`: `none`
- `price_stabilization_level`: `off`
- `rent_stabilization_level`: `off`
- `bailout_policy`: `sector`
- `bailout_target`: `food`
- `bailout_budget`: `25000`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | LOW_CASH | reduce_unemployment | `{'public_works': 'on', 'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | `{'public_works': 'on', 'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | `{}` | `{'public_works': 'on', 'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | none | $490,541 | $17,239 | 30.4% |
| 41 | LOW_CASH | stabilize_cash | `{'public_works': 'off', 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{'public_works': 'off', 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{}` | `{'public_works': 'off', 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | none | $88,439 | $43,532 | 18.4% |
| 67 | LOW_CASH | reduce_unemployment | `{'public_works': 'on', 'sector_subsidy_level': 25}` | `{'public_works': 'on', 'sector_subsidy_level': 25}` | `{}` | `{'public_works': 'on', 'sector_subsidy_level': 25}` | none | $91,496 | $58,471 | 27.2% |
| 93 | NORMAL | reduce_unemployment | `{'minimum_wage_policy': 'low', 'bailout_policy': 'sector', 'bailout_target': 'services', 'bailout_budget': 5000}` | `{'minimum_wage_policy': 'low', 'bailout_target': 'services'}` | `{}` | `{'minimum_wage_policy': 'low', 'bailout_target': 'services'}` | none | $60,866 | $61,015 | 34.6% |
| 119 | NORMAL | reduce_unemployment | `{'bailout_budget': '10000', 'social_spending': 'high'}` | `{'bailout_budget': 10000, 'social_spending': 'high'}` | `{}` | `{'bailout_budget': 10000, 'social_spending': 'high'}` | none | $76,025 | $62,704 | 26.7% |
| 145 | NORMAL | support_growth | `{'profit_tax_rate': 0.15, 'wage_tax_rate': 0.1}` | `{'profit_tax_rate': 0.15, 'wage_tax_rate': 0.1}` | `{}` | `{'profit_tax_rate': 0.15, 'wage_tax_rate': 0.1}` | none | $80,988 | $58,557 | 4.9% |
| 171 | LOW_CASH | essential_sector_support | `{'sector_subsidy_level': 50, 'bailout_budget': 25000}` | `{'sector_subsidy_level': 50, 'bailout_budget': 25000}` | `{}` | `{'sector_subsidy_level': 50, 'bailout_budget': 25000}` | none | $73,014 | $55,008 | 2.6% |
| 197 | LOW_CASH | essential_sector_support | `{'bailout_target': 'food', 'infrastructure_spending': 'low'}` | `{'bailout_target': 'food', 'infrastructure_spending': 'low'}` | `{}` | `{'bailout_target': 'food', 'infrastructure_spending': 'low'}` | none | $61,899 | $47,936 | 11.3% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 3 | $25.0 | $5.00 | $-1,066,013 | $0 | $-1,049,679 | $-128 | -9493.3 | neg_cash, neg_profit, neg_net_worth, survival, burn |
| 2 | housing | True | 49 | $36.0 | $5.00 | $2,587,888 | $0 | $22,588,893 | $-2,153 | 1198.2 | neg_profit |
| 3 | services | True | 2 | $36.0 | $7.61 | $-16,621 | $9,124 | $-24,664 | $-76 | -220.8 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 20 | $20.0 | $10.70 | $-28,975 | $0 | $-27,971 | $-143 | -72.1 | neg_cash, neg_profit, neg_net_worth |
| 5 | food | False | 1 | $45.0 | $4.69 | $4,744 | $71 | $5,803 | $-36 | 96.1 | neg_profit |
| 6 | food | False | 2 | $45.0 | $4.05 | $4,390 | $238 | $5,287 | $-85 | 43.2 | neg_profit |
| 7 | food | False | 2 | $45.0 | $5.42 | $104 | $1,067 | $5,520 | $-77 | 2.0 | neg_profit, survival, burn |
| 8 | food | False | 2 | $45.0 | $4.67 | $9,383 | $161 | $10,714 | $-58 | 92.2 | neg_profit |
| 9 | food | False | 2 | $45.0 | $4.21 | $11,567 | $0 | $17,014 | $57 | 200.1 | ok |
| 10 | food | False | 3 | $45.0 | $4.73 | $2,155 | $1,643 | $14,824 | $405 | 12.0 | ok |
| 11 | food | False | 18 | $45.0 | $5.84 | $5,309 | $12,162 | $30,495 | $608 | 5.8 | ok |
| 12 | food | False | 5 | $45.0 | $4.21 | $1,097 | $1,709 | $14,508 | $306 | 3.2 | ok |
| 13 | food | False | 11 | $45.0 | $5.35 | $157,902 | $0 | $202,868 | $1,161 | 256.8 | ok |
| 14 | food | False | 22 | $45.0 | $5.14 | $40,641 | $0 | $84,409 | $653 | 32.4 | ok |
| 15 | food | False | 25 | $45.0 | $4.35 | $29,777 | $0 | $73,165 | $633 | 21.5 | ok |
| 16 | food | False | 31 | $45.0 | $3.78 | $39,985 | $0 | $83,670 | $942 | 22.4 | ok |
| 17 | food | False | 19 | $45.0 | $4.29 | $10,689 | $6,323 | $46,936 | $909 | 8.7 | ok |
| 18 | food | False | 26 | $45.0 | $4.61 | $16,913 | $0 | $60,226 | $586 | 12.6 | ok |
| 23 | services | False | 143 | $36.0 | $10.63 | $13,823 | $0 | $98,914 | $-289 | 2.5 | neg_profit |
| 25 | services | False | 147 | $36.9 | $10.41 | $44,092 | $0 | $115,070 | $-1,100 | 6.7 | neg_profit |
| 26 | services | False | 102 | $45.0 | $12.02 | $-226 | $6,850 | $83,931 | $-106 | -0.0 | neg_cash, neg_profit, survival |
| 28 | services | False | 66 | $48.8 | $17.10 | $2,181 | $0 | $54,279 | $-102 | 0.6 | neg_profit, survival |
| 29 | services | False | 112 | $25.0 | $13.00 | $33,902 | $0 | $86,943 | $-1,700 | 5.0 | neg_profit |
| 31 | services | False | 1 | $25.0 | $13.45 | $7,016 | $166 | $7,972 | $-34 | 170.3 | neg_profit |
| 32 | publicworks | True | 14 | $45.0 | $5.00 | $111,590 | $0 | $112,759 | $-734 | 153.1 | neg_profit |
| 33 | food | False | 3 | $45.0 | $5.51 | $16,146 | $0 | $27,461 | $271 | 98.1 | ok |
| 34 | food | False | 2 | $45.0 | $5.49 | $7,811 | $0 | $19,679 | $385 | 67.9 | ok |
| 35 | food | False | 18 | $45.0 | $5.52 | $10,109 | $18,167 | $18,769 | $796 | 11.3 | ok |
| 36 | food | False | 15 | $45.0 | $5.92 | $6,902 | $3,885 | $22,568 | $551 | 9.2 | ok |
| 37 | food | False | 1 | $45.0 | $7.67 | $22,074 | $0 | $31,525 | $139 | 433.8 | ok |
