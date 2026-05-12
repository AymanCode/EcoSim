# EcoSim LLM Government Run

- Run ID: `20260512_033645`
- Model: `openai/gpt-oss-120b` via `groq`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$14,306`
- Min gov cash: `$-44,878`
- Avg GDP: `$45,104`
- Final GDP: `$38,715`
- Avg unemployment: `21.4%`
- Final unemployment: `28.1%`
- Avg health: `0.805`
- Final health: `0.760`
- Avg happiness: `0.298`
- Final happiness: `0.089`
- Median wage: `$44.3`
- Mean wage: `$47.1`
- Median firm price: `$5.5`
- Mean firm price: `$7.9`
- Housing rent / median wage: `0.11`
- Target sector price / median wage: `0.11`
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
- Denied firms by reason: `{'policy_off': 30}`
- Received by firm id: `{}`

## Decision Quality

- Accepted decision rate: `100.0%` (8/8)
- Rejection rate: `0.0%` (0/19)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `94.4%` (34/36)
- Evidence audit counts: `{'matched_metric': 33, 'value_mismatch': 2, 'matched_policy': 1}`

## Final Policy

- `wage_tax_rate`: `0.1`
- `profit_tax_rate`: `0.0`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `low`
- `unemployment_benefit_level`: `15.0`
- `public_works`: `off`
- `minimum_wage_policy`: `neutral`
- `sector_subsidy_target`: `food`
- `sector_subsidy_level`: `25`
- `infrastructure_spending`: `high`
- `technology_spending`: `none`
- `price_stabilization_target`: `food`
- `price_stabilization_level`: `monitor`
- `rent_stabilization_level`: `off`
- `bailout_policy`: `off`
- `bailout_target`: `none`
- `bailout_budget`: `0`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | LOW_CASH | reduce_unemployment | `{'profit_tax_rate': '0.15', 'infrastructure_spending': 'low'}` | `{'profit_tax_rate': 0.15, 'infrastructure_spending': 'low'}` | `{}` | `{'profit_tax_rate': 0.15, 'infrastructure_spending': 'low'}` | none | $490,541 | $17,239 | 30.4% |
| 41 | NORMAL | reduce_unemployment | `{'profit_tax_rate': '0.1', 'infrastructure_spending': 'medium'}` | `{'profit_tax_rate': 0.1, 'infrastructure_spending': 'medium'}` | `{}` | `{'profit_tax_rate': 0.1, 'infrastructure_spending': 'medium'}` | none | $83,007 | $42,503 | 18.6% |
| 67 | LOW_CASH | stabilize_cash | `{'profit_tax_rate': '0.05', 'wage_tax_rate': '0.1'}` | `{'profit_tax_rate': 0.05, 'wage_tax_rate': 0.1}` | `{}` | `{'profit_tax_rate': 0.05, 'wage_tax_rate': 0.1}` | none | $33,367 | $50,103 | 29.6% |
| 93 | CASH_CRISIS | stabilize_cash | `{'wage_tax_rate': '0.15', 'price_stabilization_target': 'food', 'price_stabilization_level': 'monitor'}` | `{'wage_tax_rate': 0.15, 'price_stabilization_target': 'food', 'price_stabilization_level': 'monitor'}` | `{}` | `{'wage_tax_rate': 0.15, 'price_stabilization_target': 'food', 'price_stabilization_level': 'monitor'}` | none | $-36,665 | $56,452 | 36.3% |
| 119 | CASH_CRISIS | reduce_unemployment | `{'benefit_level': 'low', 'profit_tax_rate': 0.1}` | `{'benefit_level': 'low', 'profit_tax_rate': 0.1}` | `{}` | `{'benefit_level': 'low', 'profit_tax_rate': 0.1}` | none | $-44,878 | $49,147 | 32.6% |
| 145 | NORMAL | reduce_unemployment | `{'profit_tax_rate': '0.05', 'infrastructure_spending': 'high'}` | `{'profit_tax_rate': 0.05, 'infrastructure_spending': 'high'}` | `{}` | `{'profit_tax_rate': 0.05, 'infrastructure_spending': 'high'}` | none | $68,680 | $46,444 | 10.7% |
| 171 | NORMAL | reduce_unemployment | `{'wage_tax_rate': '0.1', 'sector_subsidy_target': 'food', 'sector_subsidy_level': '10'}` | `{'wage_tax_rate': 0.1, 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{}` | `{'wage_tax_rate': 0.1, 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | none | $65,861 | $44,315 | 20.6% |
| 197 | LOW_CASH | reduce_unemployment | `{'profit_tax_rate': '0.0', 'sector_subsidy_target': 'food', 'sector_subsidy_level': '25'}` | `{'profit_tax_rate': 0.0, 'sector_subsidy_level': 25}` | `{}` | `{'profit_tax_rate': 0.0, 'sector_subsidy_level': 25}` | none | $25,620 | $39,203 | 28.8% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 3 | $36.0 | $5.00 | $-1,066,059 | $0 | $-1,049,679 | $-128 | -9493.8 | neg_cash, neg_profit, neg_net_worth, survival, burn |
| 2 | housing | True | 50 | $36.0 | $5.00 | $2,546,939 | $0 | $22,547,944 | $-2,199 | 1154.7 | neg_profit |
| 3 | services | True | 2 | $36.0 | $7.38 | $-17,555 | $9,081 | $-25,555 | $-81 | -233.3 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 20 | $20.0 | $10.45 | $-30,099 | $0 | $-29,094 | $-149 | -74.9 | neg_cash, neg_profit, neg_net_worth |
| 5 | food | False | 1 | $36.0 | $4.69 | $6,989 | $0 | $8,121 | $-26 | 170.3 | neg_profit |
| 6 | food | False | 1 | $36.0 | $3.99 | $7,239 | $0 | $8,489 | $-33 | 132.7 | neg_profit |
| 7 | food | False | 1 | $36.0 | $5.42 | $2,766 | $0 | $4,975 | $-24 | 55.6 | neg_profit |
| 8 | food | False | 1 | $36.0 | $4.38 | $11,527 | $0 | $14,083 | $7 | 223.4 | ok |
| 9 | food | False | 2 | $36.0 | $4.22 | $13,380 | $484 | $18,523 | $87 | 233.1 | ok |
| 10 | food | False | 3 | $36.0 | $4.73 | $3,178 | $0 | $17,814 | $420 | 21.8 | ok |
| 11 | food | False | 26 | $36.0 | $5.84 | $4,486 | $10,454 | $32,518 | $625 | 3.4 | ok |
| 12 | food | False | 6 | $36.0 | $4.39 | $1,762 | $1,787 | $14,760 | $362 | 6.2 | ok |
| 13 | food | False | 13 | $36.0 | $5.35 | $184,758 | $87 | $230,277 | $1,364 | 252.6 | ok |
| 14 | food | False | 25 | $36.0 | $5.14 | $49,494 | $0 | $93,491 | $790 | 34.1 | ok |
| 15 | food | False | 32 | $36.0 | $3.86 | $22,329 | $0 | $66,361 | $665 | 13.1 | ok |
| 16 | food | False | 35 | $36.0 | $3.78 | $53,628 | $0 | $98,051 | $1,114 | 27.5 | ok |
| 17 | food | False | 31 | $36.0 | $4.52 | $12,269 | $7,321 | $48,013 | $501 | 7.3 | ok |
| 18 | food | False | 35 | $36.0 | $4.01 | $19,493 | $0 | $63,163 | $630 | 10.5 | ok |
| 25 | services | False | 59 | $36.0 | $11.15 | $-29 | $0 | $85,955 | $-11 | -0.0 | neg_cash, neg_profit, survival |
| 29 | services | False | 48 | $36.0 | $12.79 | $1,746 | $0 | $64,420 | $-138 | 0.7 | neg_profit, survival |
| 31 | services | False | 1 | $36.0 | $13.92 | $-326 | $0 | $796 | $-39 | -3.4 | neg_cash, neg_profit, survival |
| 32 | services | False | 66 | $36.0 | $9.99 | $3,042 | $4,211 | $48,408 | $72 | 1.2 | survival |
| 33 | food | False | 3 | $36.0 | $5.51 | $17,306 | $211 | $28,634 | $291 | 114.9 | ok |
| 34 | services | False | 58 | $36.0 | $16.03 | $3,498 | $19,176 | $33,656 | $-398 | 2.7 | neg_profit |
| 35 | services | False | 60 | $36.0 | $10.87 | $10,978 | $4,952 | $53,041 | $9 | 4.6 | ok |
| 36 | services | False | 41 | $36.0 | $14.24 | $8,518 | $16,357 | $29,933 | $632 | 5.1 | ok |
| 37 | services | False | 39 | $36.0 | $13.59 | $13,552 | $9,671 | $41,094 | $683 | 8.2 | ok |
| 38 | services | False | 17 | $36.0 | $12.83 | $9,418 | $15,130 | $8,523 | $289 | 13.1 | ok |
| 39 | services | False | 18 | $36.0 | $12.89 | $22,783 | $13,041 | $24,384 | $237 | 30.0 | ok |
| 40 | services | False | 5 | $36.0 | $10.62 | $18,949 | $20,462 | $5,692 | $0 | 87.6 | ok |
