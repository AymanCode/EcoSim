# EcoSim LLM Government Run

- Run ID: `20260512_034421`
- Model: `gemma-4-26B-A4B-it-Q4_K_M.gguf` via `lmstudio`
- Seed: `42`
- Ticks: `200`
- Decision interval: `26`

## Summary

- Final gov cash: `$23,876`
- Min gov cash: `$23,876`
- Avg GDP: `$47,300`
- Final GDP: `$43,072`
- Avg unemployment: `22.4%`
- Final unemployment: `29.7%`
- Avg health: `0.806`
- Final health: `0.762`
- Avg happiness: `0.291`
- Final happiness: `0.088`
- Median wage: `$44.4`
- Mean wage: `$48.2`
- Median firm price: `$5.4`
- Mean firm price: `$7.3`
- Housing rent / median wage: `0.11`
- Target sector price / median wage: `0.25`
- Price increases limited: `0`
- Rent increases limited: `0`
- Homeless households: `0`
- Housing unaffordable failures: `0`
- Bailout spend this tick: `$0`
- Bailout budget remaining: `$0`
- Bailout cycle disbursed: `$5,000`
- Last cycle bailout disbursed: `$0`
- Last cycle bailout firms assisted: `0`

## Bailout Diagnostics

- Eligible firms by sector: `{}`
- Denied firms by reason: `{'no_bailout_budget_remaining': 30}`
- Received by firm id: `{}`

## Decision Quality

- Accepted decision rate: `87.5%` (7/8)
- Rejection rate: `9.1%` (2/22)
- Fiscal rejection rate: `0.0%`
- Invalid enum rate: `0.0%`
- Evidence match rate: `56.2%` (18/32)
- Evidence audit counts: `{'matched_metric': 18, 'unknown_key': 14}`

## Final Policy

- `wage_tax_rate`: `0.15`
- `profit_tax_rate`: `0.25`
- `investment_tax_rate`: `0.1`
- `benefit_level`: `neutral`
- `unemployment_benefit_level`: `30.0`
- `public_works`: `off`
- `minimum_wage_policy`: `neutral`
- `sector_subsidy_target`: `food`
- `sector_subsidy_level`: `25`
- `infrastructure_spending`: `none`
- `technology_spending`: `none`
- `price_stabilization_target`: `healthcare`
- `price_stabilization_level`: `monitor`
- `rent_stabilization_level`: `off`
- `bailout_policy`: `all`
- `bailout_target`: `none`
- `bailout_budget`: `5000`

## LLM Decisions

| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |
|---:|---|---|---|---|---|---|---|---:|---:|---:|
| 15 | LOW_CASH | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | `{}` | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 5000}` | none | $490,541 | $17,239 | 30.4% |
| 41 | LOW_CASH | essential_sector_support | `{'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': '10000', 'price_stabilization_target': 'healthcare', 'price_stabilization_level': 'monitor'}` | `{'bailout_budget': 10000, 'price_stabilization_target': 'healthcare', 'price_stabilization_level': 'monitor'}` | `{}` | `{'bailout_budget': 10000, 'price_stabilization_target': 'healthcare', 'price_stabilization_level': 'monitor'}` | none | $97,713 | $43,672 | 18.5% |
| 67 | LOW_CASH | essential_sector_support | `{'bailout_policy': 'all', 'bailout_target': 'none', 'bailout_budget': 10000}` | `{'bailout_policy': 'all', 'bailout_target': 'none'}` | `{}` | `{'bailout_policy': 'all', 'bailout_target': 'none'}` | none | $105,407 | $56,153 | 30.1% |
| 93 | LOW_CASH | stabilize_cash | `{'bailout_budget': '5000', 'profit_tax_rate': '0.25'}` | `{'bailout_budget': 5000, 'profit_tax_rate': 0.25}` | `{}` | `{'bailout_budget': 5000, 'profit_tax_rate': 0.25}` | none | $68,427 | $59,924 | 34.1% |
| 119 | LOW_CASH | essential_sector_support | `{'bailout_policy': 'all', 'bailout_target': 'none', 'bailout_budget': 10000, 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{'bailout_budget': 10000, 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | `{}` | `{'bailout_budget': 10000, 'sector_subsidy_target': 'food', 'sector_subsidy_level': 10}` | none | $65,484 | $49,637 | 28.9% |
| 145 | NORMAL | essential_sector_support | `{'sector_subsidy_level': '25'}` | `{'sector_subsidy_level': 25}` | `{}` | `{'sector_subsidy_level': 25}` | none | $87,995 | $54,814 | 12.7% |
| 171 | LOW_CASH | essential_sector_support | `{'group sector_subsidy': {'sector_subsidy_target': 'food', 'sector_subsidy_level': '50'}, 'group bailout': {'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 10000}}` | `{}` | `{}` | `{}` | group sector_subsidy={'sector_subsidy_target': 'food', 'sector_subsidy_level': '50'} (unknown_lever); group bailout={'bailout_policy': 'sector', 'bailout_target': 'food', 'bailout_budget': 10000} (unknown_lever) | $72,228 | $47,057 | 20.1% |
| 197 | LOW_CASH | stabilize_cash | `{'bailout_budget': 5000}` | `{'bailout_budget': 5000}` | `{}` | `{'bailout_budget': 5000}` | none | $34,726 | $44,051 | 29.7% |

## Final Firm Financials

| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | food | True | 3 | $36.0 | $5.00 | $-1,066,028 | $0 | $-1,049,679 | $-128 | -9493.5 | neg_cash, neg_profit, neg_net_worth, survival, burn |
| 2 | housing | True | 50 | $36.0 | $5.00 | $2,455,443 | $0 | $22,456,447 | $-2,201 | 1112.9 | neg_profit |
| 3 | services | True | 2 | $36.0 | $7.51 | $-17,219 | $9,085 | $-25,224 | $-78 | -228.8 | neg_cash, neg_profit, neg_net_worth, survival |
| 4 | healthcare | True | 20 | $20.0 | $10.91 | $-28,638 | $0 | $-27,633 | $-149 | -71.2 | neg_cash, neg_profit, neg_net_worth |
| 5 | food | False | 1 | $45.0 | $4.69 | $6,519 | $0 | $7,648 | $-41 | 118.5 | neg_profit |
| 6 | food | False | 1 | $45.0 | $3.99 | $7,388 | $11 | $8,612 | $-33 | 137.8 | neg_profit |
| 7 | food | False | 1 | $45.0 | $5.42 | $2,216 | $0 | $4,480 | $-26 | 44.7 | neg_profit |
| 8 | food | False | 1 | $45.0 | $4.38 | $11,140 | $0 | $13,681 | $4 | 216.0 | ok |
| 9 | food | False | 1 | $45.0 | $4.04 | $10,838 | $0 | $16,260 | $63 | 187.6 | ok |
| 10 | food | False | 3 | $45.0 | $4.73 | $1,005 | $1,630 | $14,180 | $333 | 7.0 | ok |
| 11 | food | False | 17 | $45.0 | $6.09 | $3,082 | $13,720 | $26,672 | $548 | 3.4 | ok |
| 12 | food | False | 4 | $45.0 | $4.65 | $1,390 | $1,605 | $13,280 | $236 | 5.5 | ok |
| 13 | food | False | 11 | $45.0 | $5.35 | $139,327 | $0 | $184,369 | $1,034 | 225.1 | ok |
| 14 | food | False | 22 | $45.0 | $5.14 | $30,771 | $0 | $73,979 | $608 | 24.7 | ok |
| 15 | food | False | 26 | $45.0 | $4.34 | $11,416 | $4,858 | $49,848 | $558 | 7.9 | ok |
| 16 | food | False | 32 | $45.0 | $3.78 | $26,880 | $0 | $70,345 | $830 | 15.0 | ok |
| 17 | food | False | 20 | $45.0 | $5.03 | $7,982 | $10,593 | $39,063 | $538 | 7.3 | ok |
| 18 | food | False | 24 | $45.0 | $4.21 | $11,188 | $4,878 | $49,728 | $671 | 7.4 | ok |
| 25 | services | False | 82 | $36.0 | $13.29 | $2,037 | $0 | $91,224 | $392 | 0.5 | survival |
| 29 | services | False | 53 | $36.0 | $16.09 | $3,914 | $3,776 | $63,009 | $-34 | 1.3 | neg_profit, survival |
| 31 | services | False | 1 | $36.0 | $13.83 | $0 | $356 | $766 | $-37 | 0.6 | neg_profit, survival |
| 32 | services | False | 104 | $36.0 | $10.21 | $14,773 | $13,322 | $51,551 | $147 | 3.5 | ok |
| 33 | food | False | 3 | $45.0 | $5.51 | $15,504 | $81 | $26,770 | $252 | 90.9 | ok |
| 34 | food | False | 3 | $45.0 | $5.41 | $8,315 | $1,333 | $18,085 | $317 | 72.8 | ok |
| 35 | services | False | 60 | $36.0 | $14.11 | $8,024 | $20,036 | $36,999 | $604 | 3.3 | ok |
| 36 | services | False | 63 | $36.0 | $13.26 | $11,053 | $14,386 | $46,167 | $754 | 4.2 | ok |
| 37 | services | False | 58 | $36.0 | $13.93 | $16,359 | $5,034 | $59,989 | $634 | 6.6 | ok |
| 38 | food | False | 15 | $45.0 | $6.04 | $10,789 | $1,165 | $32,851 | $758 | 12.6 | ok |
| 39 | food | False | 3 | $45.0 | $5.91 | $24,984 | $287 | $32,534 | $128 | 215.5 | ok |
| 40 | food | False | 3 | $45.0 | $7.50 | $16,524 | $19,860 | $7,925 | $523 | 97.8 | ok |
