# Small inflation scenarios

Seed 1337. Checks: 8/8.

## What the controlled price cases establish

These are decision fixtures with fixed financial inputs and an imposed price path. They isolate measurement and pay rules; they do not claim those prices emerge from a complete town or that wages settle here. Full-step contract/payroll integration is tested separately.

| Annual price path | Cash available at review | Wage at week 52 | Wage at week 104 | Real wage at week 104 |
|---|---:|---:|---:|---:|
| 0% | 10000.00 | 40.00 | 40.00 | 40.00 |
| 5% | 10000.00 | 42.00 | 44.10 | 40.00 |
| 5% | 320.00 | 40.00 | 40.00 | 36.28 |
| -5% | 10000.00 | 40.00 | 40.00 | 44.32 |

## Market-generated prices under temporary shocks

Each case runs real engine weeks for one Food firm and 12 households with a funded external buyer. Demand doubles in weeks 13–20, or labor productivity halves in weeks 13–20, then returns to its original input. Prices, hiring, production, loans, capital and firm survival respond through their normal rules. Households do not shop in these business-isolation cases. These are sector experiments, not aggregate inflation estimates; only Food (35% of the basket) has matched quotes.

| Case | Weeks completed | Week 12 sale price | Week 20 sale price | Final sale price | Final workers | Final price index |
|---|---:|---:|---:|---:|---:|---:|
| control | 105 | 7.73 | 4.91 | 4.71 | 3 | 81.48 |
| temporary_demand | 105 | 7.73 | 8.13 | 4.71 | 3 | 81.48 |
| temporary_supply | 105 | 7.73 | 7.47 | 4.71 | 3 | 81.48 |

## Purchasing power

| Food price | Same shopping budget | Planned units |
|---:|---:|---:|
| 10.00 | 43.80 | 4.3796 |
| 11.00 | 43.80 | 3.9815 |
| 20.00 | 43.80 | 2.1898 |

## Checks

- PASS: market_receipts_supply_and_payroll
- PASS: first_year_unavailable_before_week_52
- PASS: healthy_firm_reviews_at_52_and_104
- PASS: five_percent_prices_receive_five_percent_review
- PASS: cash_limit_blocks_raise
- PASS: deflation_does_not_cut_nominal_pay
- PASS: doubling_food_price_halves_quantity
- PASS: flat_prices_hold_pay
