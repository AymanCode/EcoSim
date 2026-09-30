# Business behaviour with controlled demand

Seed: 1337. Default legacy rules, normal mode.

152/152 harness/accounting checks passed across 19 runs.

Demand is a funded external customer's requested units, independent of household shopping. Actual sales remain limited by supply and buyer cash. Opening demand seeds one prior observation; later observations come from real sales and unfilled orders, with no look-ahead.

Each run uses one private Food or Services firm and a small worker pool. Full engine weeks handle hiring, production, wages, taxes, credit (when enabled), investment and exit. Warmup, random shocks, new competitors, government stabilizers, household shopping and health/wellbeing changes are excluded to isolate business responses. Healthy nonemployees may search normally; unavailable workers start too ill to work. This is a controlled business test, not a calibrated closed town.

Posted wages, existing contracts and wages actually paid are different. Food capacity limits output units; Services capacity counts worker slots. Capital stock and actual output are recorded separately. PASS checks verify the harness and affected receipts, not whether every business rule is desirable.

## Summary

| Run | Cash, start → end | Workers, start → end | Posted wage, start → end | Capacity limit, start → end | Closed? |
| --- | --- | --- | --- | --- | --- |
| cash_0 | 0 → 758.717 | 3 → 1 | 40 → 36 | 200 → 200 | no |
| cash_120 | 120 → 932.293 | 3 → 1 | 40 → 36 | 200 → 200 | no |
| cash_10000 | 10000 → 10120.402 | 3 → 1 | 40 → 36 | 200 → 200 | no |
| startup_no_cash | 0 → 4105.571 | 0 → 5 | 40 → 36 | 200 → 200 | no |
| startup_funded | 10000 → 12424.486 | 0 → 5 | 40 → 36 | 200 → 200 | no |
| hiring_available | 10000 → 10760.542 | 3 → 5 | 40 → 36 | 200 → 200 | no |
| hiring_no_applicants | 10000 → 11607.739 | 3 → 3 | 40 → 36 | 200 → 200 | no |
| hiring_high_reservations | 10000 → 11582.995 | 3 → 5 | 40 → 36 | 200 → 200 | no |
| wages_rising_sales | 10000 → 9785.876 | 3 → 4 | 40 → 36 | 200 → 200 | no |
| wages_falling_sales | 10000 → 7624.844 | 3 → 3 | 40 → 36 | 200 → 200 | no |
| wages_competing_for_workers | 10000 → 11582.995 | 3 → 5 | 40 → 36 | 200 → 200 | no |
| services_weak_sales_wages | 10000 → 7895.845 | 3 → 1 | 60 → 36 | 3 → 3 | no |
| food_expansion | 10000 → 10760.542 | 3 → 5 | 40 → 36 | 200 → 200 | no |
| services_expansion_funded | 10000 → 12155.894 | 3 → 12 | 40 → 40 | 3 → 14 | no |
| services_expansion_no_bank | 10000 → 6156.581 | 3 → 3 | 40 → 40 | 3 → 3 | no |
| no_sales | 10000 → 8520 | 3 → 1 | 40 → 36 | 200 → 200 | no |
| no_sales_no_cash | 0 → -1080 | 3 → 3 | 40 → 36 | 200 → 200 | yes |
| services_no_sales | 10000 → 7340 | 3 → 3 | 60 → 60 | 3 → 3 | no |
| demand_crash_then_recovery | 10000 → 9517.65 | 3 → 2 | 40 → 36 | 200 → 200 | no |

Intermediate rises and falls appear in the weekly tables below; matching start/end values can hide a temporary wage or demand change.

## cash_0

Food; opening business cash 0; 3 workers; 9 potential applicants in a population of 12; opening demand 30; weekly demand (30.0,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 30 | 30 | 0 | 144 | 300 | 144 | yes |
| 2 | 30 | 30 | 144 | 274.74 | 283.425 | 130.74 | yes |
| 3 | 30 | 30 | 274.74 | 411.744 | 291.255 | 137.004 | yes |
| 4 | 30 | 30 | 411.744 | 555.184 | 299.301 | 143.44 | yes |
| 5 | 30 | 30 | 555.184 | 738.482 | 307.569 | 214.055 | yes |
| 6 | 30 | 30 | 738.482 | 909.885 | 290.576 | 200.461 | yes |
| 7 | 30 | 30 | 909.885 | 570.05 | 274.522 | 187.617 | yes |
| 8 | 30 | 30 | 570.05 | 719.598 | 259.354 | 175.484 | yes |
| 9 | 30 | 30 | 719.598 | 859.116 | 245.025 | 164.02 | yes |
| 10 | 30 | 30 | 859.116 | 498.634 | 245.025 | 164.02 | yes |
| 11 | 30 | 30 | 498.634 | 628.675 | 231.488 | 153.19 | yes |
| 12 | 30 | 30 | 628.675 | 758.717 | 231.488 | 153.19 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 2 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 3 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 4 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 5 | 0 | 0 | 2 | 2 | 1 | 36 | 40 | 40 |
| 6 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 7 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 8 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 9 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 10 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 11 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 12 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 30.401 | 200 | 82.362 | 14.85 | 0.401 | 10 |
| 2 | 30.427 | 200 | 82.155 | 14.701 | 0.828 | 9.448 |
| 3 | 30.453 | 200 | 81.949 | 14.554 | 1.281 | 9.708 |
| 4 | 30.479 | 200 | 81.744 | 14.409 | 1.76 | 9.977 |
| 5 | 40.024 | 200 | 39.924 | 14.265 | 11.784 | 10.252 |
| 6 | 39.924 | 200 | 39.824 | 14.122 | 21.708 | 9.686 |
| 7 | 40.511 | 200 | 40.409 | 14.971 | 32.219 | 9.151 |
| 8 | 25.637 | 200 | 40.308 | 14.821 | 27.856 | 8.645 |
| 9 | 32.336 | 200 | 40.207 | 14.673 | 30.192 | 8.168 |
| 10 | 28.785 | 200 | 40.772 | 15.516 | 28.977 | 8.168 |
| 11 | 30.672 | 200 | 40.67 | 15.361 | 29.649 | 7.716 |
| 12 | 29.667 | 200 | 40.568 | 15.208 | 29.316 | 7.716 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** Cash goes negative before sales; legacy payroll is still paid even without enough opening funds.
**Observed:** A lower posted wage does not necessarily lower existing workers' contracts that week.

## cash_120

Food; opening business cash 120; 3 workers; 9 potential applicants in a population of 12; opening demand 30; weekly demand (30.0,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 30 | 30 | 120 | 264 | 300 | 144 | yes |
| 2 | 30 | 30 | 264 | 394.74 | 283.425 | 130.74 | yes |
| 3 | 30 | 30 | 394.74 | 531.744 | 291.255 | 137.004 | yes |
| 4 | 30 | 30 | 531.744 | 709.254 | 299.301 | 207.44 | yes |
| 5 | 30 | 30 | 709.254 | 892.552 | 307.569 | 214.055 | yes |
| 6 | 30 | 30 | 892.552 | 563.955 | 290.576 | 200.461 | yes |
| 7 | 30 | 30 | 563.955 | 724.12 | 274.522 | 187.617 | yes |
| 8 | 30 | 30 | 724.12 | 873.668 | 259.354 | 175.484 | yes |
| 9 | 30 | 30 | 873.668 | 523.216 | 259.354 | 175.484 | yes |
| 10 | 30 | 30 | 523.216 | 662.734 | 245.025 | 164.02 | yes |
| 11 | 30 | 30 | 662.734 | 802.252 | 245.025 | 164.02 | yes |
| 12 | 30 | 30 | 802.252 | 932.293 | 231.488 | 153.19 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 2 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 3 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 4 | 0 | 0 | 2 | 2 | 1 | 36 | 40 | 40 |
| 5 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 6 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 7 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 8 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 9 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 10 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 11 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 12 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 30.401 | 200 | 82.362 | 14.85 | 0.401 | 10 |
| 2 | 30.427 | 200 | 82.155 | 14.701 | 0.828 | 9.448 |
| 3 | 30.453 | 200 | 81.949 | 14.554 | 1.281 | 9.708 |
| 4 | 40.125 | 200 | 40.024 | 14.409 | 11.406 | 9.977 |
| 5 | 40.024 | 200 | 39.924 | 14.265 | 21.43 | 10.252 |
| 6 | 40.606 | 200 | 40.504 | 15.112 | 32.036 | 9.686 |
| 7 | 25.894 | 200 | 40.402 | 14.961 | 27.93 | 9.151 |
| 8 | 32.195 | 200 | 40.301 | 14.811 | 30.125 | 8.645 |
| 9 | 28.863 | 200 | 40.862 | 15.653 | 28.988 | 8.645 |
| 10 | 30.629 | 200 | 40.759 | 15.497 | 29.617 | 8.168 |
| 11 | 29.691 | 200 | 40.657 | 15.342 | 29.308 | 8.168 |
| 12 | 30.19 | 200 | 40.555 | 15.188 | 29.498 | 7.716 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** A lower posted wage does not necessarily lower existing workers' contracts that week.

## cash_10000

Food; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 30; weekly demand (30.0,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 30 | 30 | 10000 | 9678 | 300 | 208 | yes |
| 2 | 30 | 30 | 9678 | 9344.398 | 283.425 | 194.74 | yes |
| 3 | 30 | 30 | 9344.398 | 8999.834 | 267.766 | 182.213 | yes |
| 4 | 30 | 30 | 8999.834 | 9144.914 | 252.972 | 170.378 | yes |
| 5 | 30 | 30 | 9144.914 | 9280.211 | 238.996 | 159.197 | yes |
| 6 | 30 | 30 | 9280.211 | 9415.508 | 238.996 | 159.197 | yes |
| 7 | 30 | 30 | 9415.508 | 9541.562 | 225.791 | 148.633 | yes |
| 8 | 30 | 30 | 9541.562 | 9667.616 | 225.791 | 148.633 | yes |
| 9 | 30 | 30 | 9667.616 | 9784.938 | 213.316 | 138.653 | yes |
| 10 | 30 | 30 | 9784.938 | 9902.259 | 213.316 | 138.653 | yes |
| 11 | 30 | 30 | 9902.259 | 10011.331 | 201.531 | 129.225 | yes |
| 12 | 30 | 30 | 10011.331 | 10120.402 | 201.531 | 129.225 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 2 | 2 | 1 | 36 | 40 | 40 |
| 2 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 3 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 4 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 5 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 6 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 7 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 8 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 9 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 10 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 11 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 12 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 41.086 | 200 | 40.983 | 15.84 | 11.086 | 10 |
| 2 | 41.615 | 200 | 41.511 | 16.672 | 22.702 | 9.448 |
| 3 | 40.02 | 200 | 42.014 | 17.495 | 32.721 | 8.926 |
| 4 | 24.784 | 200 | 41.909 | 17.32 | 27.506 | 8.432 |
| 5 | 32.761 | 200 | 41.803 | 17.147 | 30.266 | 7.967 |
| 6 | 28.574 | 200 | 41.699 | 16.975 | 28.84 | 7.967 |
| 7 | 30.777 | 200 | 41.594 | 16.806 | 29.617 | 7.526 |
| 8 | 29.615 | 200 | 41.49 | 16.637 | 29.232 | 7.526 |
| 9 | 30.229 | 200 | 41.385 | 16.471 | 29.462 | 7.111 |
| 10 | 29.904 | 200 | 41.282 | 16.306 | 29.365 | 7.111 |
| 11 | 30.077 | 200 | 41.178 | 16.143 | 29.442 | 6.718 |
| 12 | 29.985 | 200 | 41.075 | 15.982 | 29.427 | 6.718 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.


## startup_no_cash

Food; opening business cash 0; 0 workers; 12 potential applicants in a population of 12; opening demand 30; weekly demand (120,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 120 | 40.429 | 0 | 250.601 | 404.287 | 291.03 | yes |
| 2 | 120 | 82.362 | 250.601 | 729.936 | 823.621 | 561.697 | yes |
| 3 | 120 | 99.048 | 729.936 | 1312.826 | 1017.844 | 684.675 | yes |
| 4 | 120 | 114.221 | 1312.826 | 1995.159 | 1206.19 | 802.952 | yes |
| 5 | 120 | 113.935 | 1995.159 | 2698.64 | 1236.401 | 827.12 | yes |
| 6 | 120 | 120 | 2698.64 | 2940.976 | 1338.195 | 876.156 | yes |
| 7 | 120 | 120 | 2940.976 | 3209.19 | 1375.162 | 905.73 | yes |
| 8 | 120 | 120 | 3209.19 | 3456.619 | 1299.185 | 877.348 | yes |
| 9 | 120 | 120 | 3456.619 | 3653.804 | 1227.406 | 819.925 | yes |
| 10 | 120 | 120 | 3653.804 | 3850.988 | 1227.406 | 819.925 | yes |
| 11 | 120 | 120 | 3850.988 | 4000.703 | 1159.593 | 765.674 | yes |
| 12 | 120 | 120 | 4000.703 | 4105.571 | 1095.526 | 714.421 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 0 | 0 | 1 | 36 | 40.5 | 40.5 |
| 2 | 2 | 2 | 0 | 0 | 3 | 36 | 40.5 | 121.5 |
| 3 | 1 | 1 | 0 | 0 | 4 | 36 | 40.5 | 162 |
| 4 | 1 | 1 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 5 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 6 | 1 | 1 | 0 | 0 | 6 | 36 | 40.5 | 243 |
| 7 | 0 | 0 | 0 | 0 | 6 | 36 | 40.5 | 243 |
| 8 | 0 | 0 | 1 | 1 | 5 | 36 | 40.5 | 202.5 |
| 9 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 10 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 11 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 12 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 40.429 | 200 | 40.327 | 14.85 | 0 | 10 |
| 2 | 82.362 | 200 | 82.155 | 14.701 | 0 | 10 |
| 3 | 99.048 | 200 | 98.8 | 14.554 | 0 | 10.276 |
| 4 | 114.221 | 200 | 113.935 | 14.409 | 0 | 10.56 |
| 5 | 113.935 | 200 | 113.649 | 14.265 | 0 | 10.852 |
| 6 | 130.133 | 200 | 129.807 | 15.112 | 10.133 | 11.152 |
| 7 | 131.903 | 200 | 131.572 | 15.951 | 22.036 | 11.46 |
| 8 | 118.658 | 200 | 118.36 | 16.782 | 20.694 | 10.827 |
| 9 | 120.085 | 200 | 119.784 | 17.604 | 20.779 | 10.228 |
| 10 | 121.45 | 200 | 121.145 | 18.418 | 22.23 | 10.228 |
| 11 | 122.757 | 200 | 122.449 | 19.224 | 24.987 | 9.663 |
| 12 | 124.011 | 200 | 123.7 | 20.021 | 28.998 | 9.129 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** Cash goes negative before sales; legacy payroll is still paid even without enough opening funds.
**Observed:** Unfilled demand did not raise the installed capacity limit during this run; inspect finance and expansion gates.

## startup_funded

Food; opening business cash 10000; 0 workers; 12 potential applicants in a population of 12; opening demand 30; weekly demand (120,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 120 | 40.429 | 10000 | 10250.601 | 404.287 | 291.03 | yes |
| 2 | 120 | 83.715 | 10250.601 | 10239.406 | 837.15 | 572.52 | yes |
| 3 | 120 | 102.242 | 10239.406 | 10345.272 | 1050.665 | 710.932 | yes |
| 4 | 120 | 103.495 | 10345.272 | 10480.713 | 1092.917 | 744.733 | yes |
| 5 | 120 | 120 | 10480.713 | 10730.268 | 1302.221 | 879.777 | yes |
| 6 | 120 | 120 | 10730.268 | 11005.005 | 1338.195 | 908.556 | yes |
| 7 | 120 | 120 | 11005.005 | 11305.618 | 1375.162 | 938.13 | yes |
| 8 | 120 | 120 | 11305.618 | 11632.824 | 1413.151 | 968.52 | yes |
| 9 | 120 | 120 | 11632.824 | 11905.376 | 1335.075 | 906.06 | yes |
| 10 | 120 | 120 | 11905.376 | 12126.295 | 1261.313 | 847.05 | yes |
| 11 | 120 | 120 | 12126.295 | 12298.433 | 1191.626 | 791.301 | yes |
| 12 | 120 | 120 | 12298.433 | 12424.486 | 1125.789 | 738.632 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 0 | 0 | 1 | 36 | 40.5 | 40.5 |
| 2 | 2 | 2 | 0 | 0 | 3 | 36 | 40.5 | 121.5 |
| 3 | 1 | 1 | 0 | 0 | 4 | 36 | 40.5 | 162 |
| 4 | 0 | 0 | 0 | 0 | 4 | 36 | 40.5 | 162 |
| 5 | 1 | 1 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 6 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 7 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 8 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 9 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 10 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 11 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |
| 12 | 0 | 0 | 0 | 0 | 5 | 36 | 40.5 | 202.5 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 40.429 | 200 | 40.327 | 14.85 | 0 | 10 |
| 2 | 83.715 | 200 | 83.505 | 15.691 | 0 | 10 |
| 3 | 102.242 | 200 | 101.986 | 16.525 | 0 | 10.276 |
| 4 | 103.495 | 200 | 103.235 | 17.349 | 0 | 10.56 |
| 5 | 121.033 | 200 | 120.729 | 18.166 | 1.033 | 10.852 |
| 6 | 122.357 | 200 | 122.05 | 18.974 | 3.39 | 11.152 |
| 7 | 123.627 | 200 | 123.317 | 19.774 | 7.017 | 11.46 |
| 8 | 124.848 | 200 | 124.534 | 20.567 | 11.865 | 11.776 |
| 9 | 126.021 | 200 | 125.705 | 21.351 | 17.886 | 11.126 |
| 10 | 127.152 | 200 | 126.833 | 22.128 | 25.038 | 10.511 |
| 11 | 128.242 | 200 | 127.92 | 22.896 | 33.28 | 9.93 |
| 12 | 129.294 | 200 | 128.97 | 23.657 | 42.574 | 9.382 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** Unfilled demand did not raise the installed capacity limit during this run; inspect finance and expansion gates.

## hiring_available

Food; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 120; weekly demand (120,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 120 | 120 | 10000 | 10146.8 | 1200 | 766.8 | yes |
| 2 | 120 | 120 | 10146.8 | 10348.805 | 1233.15 | 825.32 | yes |
| 3 | 120 | 120 | 10348.805 | 10503.118 | 1165.019 | 770.815 | yes |
| 4 | 120 | 120 | 10503.118 | 10657.431 | 1165.019 | 770.815 | yes |
| 5 | 120 | 120 | 10657.431 | 10811.744 | 1165.019 | 770.815 | yes |
| 6 | 120 | 120 | 10811.744 | 10921.001 | 1100.652 | 719.322 | yes |
| 7 | 120 | 120 | 10921.001 | 10987.69 | 1039.842 | 670.674 | yes |
| 8 | 120 | 120 | 10987.69 | 11014.164 | 982.391 | 624.713 | yes |
| 9 | 120 | 120 | 11014.164 | 11002.645 | 928.115 | 581.292 | yes |
| 10 | 120 | 120 | 11002.645 | 10955.231 | 876.837 | 540.27 | yes |
| 11 | 120 | 120 | 10955.231 | 10873.905 | 828.392 | 501.514 | yes |
| 12 | 120 | 120 | 10873.905 | 10760.542 | 782.624 | 464.899 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 3 | 0 | 0 | 6 | 36 | 40.25 | 241.5 |
| 2 | 0 | 0 | 1 | 1 | 5 | 36 | 40.3 | 201.5 |
| 3 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 4 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 5 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 6 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 7 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 8 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 9 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 10 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 11 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 12 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 131.673 | 200 | 131.342 | 15.84 | 11.673 | 10 |
| 2 | 118.463 | 200 | 118.166 | 16.672 | 10.136 | 10.276 |
| 3 | 119.899 | 200 | 119.598 | 17.495 | 10.035 | 9.708 |
| 4 | 121.272 | 200 | 120.968 | 18.31 | 11.307 | 9.708 |
| 5 | 122.587 | 200 | 122.279 | 19.117 | 13.893 | 9.708 |
| 6 | 123.848 | 200 | 123.537 | 19.916 | 17.741 | 9.172 |
| 7 | 125.059 | 200 | 124.745 | 20.707 | 22.8 | 8.665 |
| 8 | 126.225 | 200 | 125.908 | 21.489 | 29.025 | 8.187 |
| 9 | 127.348 | 200 | 127.028 | 22.265 | 36.373 | 7.734 |
| 10 | 128.431 | 200 | 128.109 | 23.032 | 44.805 | 7.307 |
| 11 | 129.478 | 200 | 129.153 | 23.792 | 54.282 | 6.903 |
| 12 | 130.489 | 200 | 130.161 | 24.544 | 64.771 | 6.522 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.


## hiring_no_applicants

Food; opening business cash 10000; 3 workers; 0 potential applicants in a population of 12; opening demand 120; weekly demand (120,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 120 | 83.912 | 10000 | 9991.386 | 839.124 | 575.299 | yes |
| 2 | 120 | 84.993 | 9991.386 | 10006.77 | 873.406 | 602.724 | yes |
| 3 | 120 | 86.023 | 10006.77 | 10046.66 | 908.414 | 630.731 | yes |
| 4 | 120 | 87.008 | 10046.66 | 10111.598 | 944.196 | 659.357 | yes |
| 5 | 120 | 87.951 | 10111.598 | 10202.156 | 980.797 | 688.638 | yes |
| 6 | 120 | 88.856 | 10202.156 | 10318.937 | 1018.259 | 718.608 | yes |
| 7 | 120 | 89.725 | 10318.937 | 10462.575 | 1056.625 | 749.3 | yes |
| 8 | 120 | 90.561 | 10462.575 | 10633.73 | 1095.936 | 780.749 | yes |
| 9 | 120 | 91.367 | 10633.73 | 10833.092 | 1136.231 | 812.985 | yes |
| 10 | 120 | 92.145 | 10833.092 | 11061.379 | 1177.553 | 846.042 | yes |
| 11 | 120 | 92.895 | 11061.379 | 11319.337 | 1219.939 | 879.951 | yes |
| 12 | 120 | 93.621 | 11319.337 | 11607.739 | 1263.432 | 914.745 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 2 | 2 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 3 | 2 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 4 | 2 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 5 | 2 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 6 | 2 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 7 | 2 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 8 | 2 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 9 | 2 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 10 | 2 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 11 | 1 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 12 | 1 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 83.912 | 200 | 83.702 | 15.84 | 0 | 10 |
| 2 | 84.993 | 200 | 84.779 | 16.672 | 0 | 10.276 |
| 3 | 86.023 | 200 | 85.807 | 17.495 | 0 | 10.56 |
| 4 | 87.008 | 200 | 86.79 | 18.31 | 0 | 10.852 |
| 5 | 87.951 | 200 | 87.73 | 19.117 | 0 | 11.152 |
| 6 | 88.856 | 200 | 88.633 | 19.916 | 0 | 11.46 |
| 7 | 89.725 | 200 | 89.5 | 20.707 | 0 | 11.776 |
| 8 | 90.561 | 200 | 90.334 | 21.489 | 0 | 12.102 |
| 9 | 91.367 | 200 | 91.138 | 22.265 | 0 | 12.436 |
| 10 | 92.145 | 200 | 91.913 | 23.032 | 0 | 12.779 |
| 11 | 92.895 | 200 | 92.662 | 23.792 | 0 | 13.132 |
| 12 | 93.621 | 200 | 93.386 | 24.544 | 0 | 13.495 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** Some requested hires are not filled; inspect the labor outcomes and failure reasons.
**Observed:** Unfilled demand did not raise the installed capacity limit during this run; inspect finance and expansion gates.
**Observed:** A lower posted wage does not necessarily lower existing workers' contracts that week.

## hiring_high_reservations

Food; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 120; weekly demand (120,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 120 | 83.912 | 10000 | 9991.386 | 839.124 | 575.299 | yes |
| 2 | 120 | 84.993 | 9991.386 | 10006.77 | 873.406 | 602.724 | yes |
| 3 | 120 | 86.023 | 10006.77 | 10034.66 | 908.414 | 618.731 | yes |
| 4 | 120 | 87.008 | 10034.66 | 10060.598 | 944.196 | 620.357 | yes |
| 5 | 120 | 87.951 | 10060.598 | 10086.381 | 980.797 | 623.863 | yes |
| 6 | 120 | 107.126 | 10086.381 | 10213.513 | 1227.633 | 749.896 | yes |
| 7 | 120 | 108.174 | 10213.513 | 10372.71 | 1273.888 | 786.585 | yes |
| 8 | 120 | 109.183 | 10372.71 | 10565.082 | 1321.281 | 824.5 | yes |
| 9 | 120 | 120 | 10565.082 | 10841.58 | 1492.305 | 925.728 | yes |
| 10 | 120 | 120 | 10841.58 | 11146.935 | 1533.529 | 958.708 | yes |
| 11 | 120 | 120 | 11146.935 | 11392.981 | 1448.803 | 890.927 | yes |
| 12 | 120 | 120 | 11392.981 | 11582.995 | 1368.757 | 826.89 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 2 | 2 | 0 | 0 | 0 | 3 | 45 | 40 | 120 |
| 3 | 2 | 0 | 0 | 0 | 3 | 56.25 | 45 | 135 |
| 4 | 2 | 0 | 0 | 0 | 3 | 66.99 | 56.25 | 168.75 |
| 5 | 2 | 0 | 0 | 0 | 3 | 70.331 | 66.99 | 200.969 |
| 6 | 1 | 1 | 0 | 0 | 4 | 70.462 | 72.566 | 290.263 |
| 7 | 1 | 0 | 0 | 0 | 4 | 36 | 72.664 | 290.656 |
| 8 | 1 | 0 | 0 | 0 | 4 | 38.748 | 72.664 | 290.656 |
| 9 | 1 | 1 | 0 | 0 | 5 | 39.545 | 67.029 | 335.144 |
| 10 | 0 | 0 | 0 | 0 | 5 | 36 | 67.029 | 335.144 |
| 11 | 0 | 0 | 0 | 0 | 5 | 36 | 67.029 | 335.144 |
| 12 | 0 | 0 | 0 | 0 | 5 | 36 | 67.029 | 335.144 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 83.912 | 200 | 83.702 | 15.84 | 0 | 10 |
| 2 | 84.993 | 200 | 84.779 | 16.672 | 0 | 10.276 |
| 3 | 86.023 | 200 | 85.807 | 17.495 | 0 | 10.56 |
| 4 | 87.008 | 200 | 86.79 | 18.31 | 0 | 10.852 |
| 5 | 87.951 | 200 | 87.73 | 19.117 | 0 | 11.152 |
| 6 | 107.126 | 200 | 106.857 | 19.916 | 0 | 11.46 |
| 7 | 108.174 | 200 | 107.903 | 20.707 | 0 | 11.776 |
| 8 | 109.183 | 200 | 108.909 | 21.489 | 0 | 12.102 |
| 9 | 127.348 | 200 | 127.028 | 22.265 | 7.348 | 12.436 |
| 10 | 128.431 | 200 | 128.109 | 23.032 | 15.779 | 12.779 |
| 11 | 129.478 | 200 | 129.153 | 23.792 | 25.257 | 12.073 |
| 12 | 130.489 | 200 | 130.161 | 24.544 | 35.746 | 11.406 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** Some requested hires are not filled; inspect the labor outcomes and failure reasons.
**Observed:** Unfilled demand did not raise the installed capacity limit during this run; inspect finance and expansion gates.
**Observed:** A lower posted wage does not necessarily lower existing workers' contracts that week.

## wages_rising_sales

Food; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 10; weekly demand (100,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 100 | 24.82 | 10000 | 10077.737 | 248.196 | 102.557 | yes |
| 2 | 100 | 40.99 | 10077.737 | 9816.812 | 387.25 | 277.8 | yes |
| 3 | 100 | 41.523 | 9816.812 | 9567.002 | 403.128 | 290.502 | yes |
| 4 | 100 | 65.955 | 9567.002 | 9463.195 | 658.013 | 461.994 | yes |
| 5 | 100 | 86.836 | 9463.195 | 9489.55 | 890.27 | 615.383 | yes |
| 6 | 100 | 100 | 9489.55 | 9597.802 | 1053.55 | 713.607 | yes |
| 7 | 100 | 100 | 9597.802 | 9726.427 | 1082.654 | 736.89 | yes |
| 8 | 100 | 100 | 9726.427 | 9813.181 | 1022.838 | 689.037 | yes |
| 9 | 100 | 100 | 9813.181 | 9860.377 | 966.327 | 643.829 | yes |
| 10 | 100 | 100 | 9860.377 | 9870.2 | 912.938 | 601.117 | yes |
| 11 | 100 | 100 | 9870.2 | 9844.716 | 862.499 | 560.766 | yes |
| 12 | 100 | 100 | 9844.716 | 9785.876 | 814.846 | 522.644 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 2 | 0 | 0 | 2 | 2 | 1 | 36 | 40 | 40 |
| 3 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 4 | 1 | 1 | 0 | 0 | 2 | 36 | 40.26 | 80.521 |
| 5 | 1 | 1 | 0 | 0 | 3 | 36 | 40.347 | 121.042 |
| 6 | 1 | 1 | 0 | 0 | 4 | 36 | 40.385 | 161.542 |
| 7 | 0 | 0 | 0 | 0 | 4 | 36 | 40.385 | 161.542 |
| 8 | 0 | 0 | 0 | 0 | 4 | 36 | 40.385 | 161.542 |
| 9 | 0 | 0 | 0 | 0 | 4 | 36 | 40.385 | 161.542 |
| 10 | 0 | 0 | 0 | 0 | 4 | 36 | 40.385 | 161.542 |
| 11 | 0 | 0 | 0 | 0 | 4 | 36 | 40.385 | 161.542 |
| 12 | 0 | 0 | 0 | 0 | 4 | 36 | 40.385 | 161.542 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 24.82 | 200 | 82.362 | 14.85 | 0 | 10 |
| 2 | 40.99 | 200 | 40.887 | 15.691 | 0 | 9.448 |
| 3 | 41.523 | 200 | 41.419 | 16.525 | 0 | 9.708 |
| 4 | 65.955 | 200 | 65.79 | 17.349 | 0 | 9.977 |
| 5 | 86.836 | 200 | 86.618 | 18.166 | 0 | 10.252 |
| 6 | 105.837 | 200 | 105.572 | 18.974 | 5.837 | 10.536 |
| 7 | 106.936 | 200 | 106.668 | 19.774 | 12.773 | 10.827 |
| 8 | 107.991 | 200 | 107.72 | 20.567 | 20.764 | 10.228 |
| 9 | 109.006 | 200 | 108.733 | 21.351 | 29.771 | 9.663 |
| 10 | 109.984 | 200 | 109.708 | 22.128 | 39.755 | 9.129 |
| 11 | 110.927 | 200 | 110.649 | 22.896 | 50.682 | 8.625 |
| 12 | 111.838 | 200 | 111.557 | 23.657 | 62.52 | 8.148 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** Unfilled demand did not raise the installed capacity limit during this run; inspect finance and expansion gates.
**Observed:** A lower posted wage does not necessarily lower existing workers' contracts that week.

## wages_falling_sales

Food; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 100; weekly demand (5,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 5 | 5 | 10000 | 9389.5 | 50 | -110.5 | yes |
| 2 | 5 | 5 | 9389.5 | 8820.381 | 51.381 | -69.119 | yes |
| 3 | 5 | 5 | 8820.381 | 8248.424 | 48.542 | -71.958 | yes |
| 4 | 5 | 5 | 8248.424 | 8176.466 | 48.542 | -71.958 | yes |
| 5 | 5 | 5 | 8176.466 | 8104.509 | 48.542 | -71.958 | yes |
| 6 | 5 | 5 | 8104.509 | 8034.961 | 48.542 | -69.548 | yes |
| 7 | 5 | 5 | 8034.961 | 7967.775 | 48.542 | -67.186 | yes |
| 8 | 5 | 5 | 7967.775 | 7901.08 | 46.719 | -66.695 | yes |
| 9 | 5 | 5 | 7901.08 | 7834.234 | 44.299 | -66.847 | yes |
| 10 | 5 | 5 | 7834.234 | 7766.787 | 41.476 | -67.447 | yes |
| 11 | 5 | 5 | 7766.787 | 7697.275 | 38.488 | -69.512 | yes |
| 12 | 5 | 5 | 7697.275 | 7624.844 | 35.569 | -72.431 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 0 | 0 | 4 | 36 | 40.125 | 160.5 |
| 2 | 0 | 0 | 1 | 1 | 3 | 36 | 40.167 | 120.5 |
| 3 | 0 | 0 | 0 | 0 | 3 | 36 | 40.167 | 120.5 |
| 4 | 0 | 0 | 0 | 0 | 3 | 36 | 40.167 | 120.5 |
| 5 | 0 | 0 | 0 | 0 | 3 | 36 | 39.363 | 120.5 |
| 6 | 0 | 0 | 0 | 0 | 3 | 36 | 38.576 | 118.09 |
| 7 | 0 | 0 | 0 | 0 | 3 | 36 | 37.805 | 115.728 |
| 8 | 0 | 0 | 0 | 0 | 3 | 36 | 37.048 | 113.414 |
| 9 | 0 | 0 | 0 | 0 | 3 | 36 | 36.307 | 111.145 |
| 10 | 0 | 0 | 0 | 0 | 3 | 36 | 35.581 | 108.922 |
| 11 | 0 | 0 | 0 | 0 | 3 | 36 | 35.28 | 108 |
| 12 | 0 | 0 | 0 | 0 | 3 | 36 | 35.28 | 108 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 101.166 | 200 | 100.912 | 15.84 | 96.166 | 10 |
| 2 | 0 | 200 | 84.779 | 16.672 | 91.166 | 10.276 |
| 3 | 0 | 200 | 85.807 | 17.495 | 86.166 | 9.708 |
| 4 | 0 | 200 | 85.592 | 17.32 | 81.166 | 9.708 |
| 5 | 0 | 200 | 85.377 | 17.147 | 76.166 | 9.708 |
| 6 | 0 | 200 | 85.163 | 16.975 | 71.166 | 9.708 |
| 7 | 0 | 200 | 84.949 | 16.806 | 66.166 | 9.708 |
| 8 | 0 | 200 | 84.736 | 16.637 | 61.166 | 9.344 |
| 9 | 0 | 200 | 84.523 | 16.471 | 56.166 | 8.86 |
| 10 | 0 | 200 | 84.311 | 16.306 | 51.166 | 8.295 |
| 11 | 0 | 200 | 84.1 | 16.143 | 46.166 | 7.698 |
| 12 | 0 | 200 | 83.889 | 15.982 | 41.166 | 7.114 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.


## wages_competing_for_workers

Food; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 120; weekly demand (120,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 120 | 83.912 | 10000 | 9991.386 | 839.124 | 575.299 | yes |
| 2 | 120 | 84.993 | 9991.386 | 10006.77 | 873.406 | 602.724 | yes |
| 3 | 120 | 86.023 | 10006.77 | 10034.66 | 908.414 | 618.731 | yes |
| 4 | 120 | 87.008 | 10034.66 | 10060.598 | 944.196 | 620.357 | yes |
| 5 | 120 | 87.951 | 10060.598 | 10086.381 | 980.797 | 623.863 | yes |
| 6 | 120 | 107.126 | 10086.381 | 10213.513 | 1227.633 | 749.896 | yes |
| 7 | 120 | 108.174 | 10213.513 | 10372.71 | 1273.888 | 786.585 | yes |
| 8 | 120 | 109.183 | 10372.71 | 10565.082 | 1321.281 | 824.5 | yes |
| 9 | 120 | 120 | 10565.082 | 10841.58 | 1492.305 | 925.728 | yes |
| 10 | 120 | 120 | 10841.58 | 11146.935 | 1533.529 | 958.708 | yes |
| 11 | 120 | 120 | 11146.935 | 11392.981 | 1448.803 | 890.927 | yes |
| 12 | 120 | 120 | 11392.981 | 11582.995 | 1368.757 | 826.89 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 2 | 2 | 0 | 0 | 0 | 3 | 45 | 40 | 120 |
| 3 | 2 | 0 | 0 | 0 | 3 | 56.25 | 45 | 135 |
| 4 | 2 | 0 | 0 | 0 | 3 | 66.99 | 56.25 | 168.75 |
| 5 | 2 | 0 | 0 | 0 | 3 | 70.331 | 66.99 | 200.969 |
| 6 | 1 | 1 | 0 | 0 | 4 | 70.462 | 72.566 | 290.263 |
| 7 | 1 | 0 | 0 | 0 | 4 | 36 | 72.664 | 290.656 |
| 8 | 1 | 0 | 0 | 0 | 4 | 38.748 | 72.664 | 290.656 |
| 9 | 1 | 1 | 0 | 0 | 5 | 39.545 | 67.029 | 335.144 |
| 10 | 0 | 0 | 0 | 0 | 5 | 36 | 67.029 | 335.144 |
| 11 | 0 | 0 | 0 | 0 | 5 | 36 | 67.029 | 335.144 |
| 12 | 0 | 0 | 0 | 0 | 5 | 36 | 67.029 | 335.144 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 83.912 | 200 | 83.702 | 15.84 | 0 | 10 |
| 2 | 84.993 | 200 | 84.779 | 16.672 | 0 | 10.276 |
| 3 | 86.023 | 200 | 85.807 | 17.495 | 0 | 10.56 |
| 4 | 87.008 | 200 | 86.79 | 18.31 | 0 | 10.852 |
| 5 | 87.951 | 200 | 87.73 | 19.117 | 0 | 11.152 |
| 6 | 107.126 | 200 | 106.857 | 19.916 | 0 | 11.46 |
| 7 | 108.174 | 200 | 107.903 | 20.707 | 0 | 11.776 |
| 8 | 109.183 | 200 | 108.909 | 21.489 | 0 | 12.102 |
| 9 | 127.348 | 200 | 127.028 | 22.265 | 7.348 | 12.436 |
| 10 | 128.431 | 200 | 128.109 | 23.032 | 15.779 | 12.779 |
| 11 | 129.478 | 200 | 129.153 | 23.792 | 25.257 | 12.073 |
| 12 | 130.489 | 200 | 130.161 | 24.544 | 35.746 | 11.406 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** Some requested hires are not filled; inspect the labor outcomes and failure reasons.
**Observed:** Unfilled demand did not raise the installed capacity limit during this run; inspect finance and expansion gates.
**Observed:** A lower posted wage does not necessarily lower existing workers' contracts that week.

## services_weak_sales_wages

Services; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 12; weekly demand (1,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 10000 | 9350 | 30 | -150 | yes |
| 2 | 1 | 1 | 9350 | 9198.418 | 28.418 | -151.582 | yes |
| 3 | 1 | 1 | 9198.418 | 9044.145 | 25.727 | -154.273 | yes |
| 4 | 1 | 1 | 9044.145 | 8891.319 | 23.574 | -152.826 | yes |
| 5 | 1 | 1 | 8891.319 | 8740.239 | 21.792 | -151.08 | yes |
| 6 | 1 | 1 | 8740.239 | 8591.131 | 20.307 | -149.108 | yes |
| 7 | 1 | 1 | 8591.131 | 8444.167 | 19.062 | -146.964 | yes |
| 8 | 1 | 1 | 8444.167 | 8299.471 | 18.01 | -144.696 | yes |
| 9 | 1 | 1 | 8299.471 | 8157.131 | 17.112 | -142.339 | yes |
| 10 | 1 | 1 | 8157.131 | 8017.209 | 16.341 | -139.922 | yes |
| 11 | 1 | 1 | 8017.209 | 7930.788 | 15.67 | -86.421 | yes |
| 12 | 1 | 1 | 7930.788 | 7895.845 | 15.082 | -34.943 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 2 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 3 | 0 | 0 | 0 | 0 | 3 | 57 | 58.8 | 180 |
| 4 | 0 | 0 | 0 | 0 | 3 | 54 | 57.624 | 176.4 |
| 5 | 0 | 0 | 0 | 0 | 3 | 51 | 56.472 | 172.872 |
| 6 | 0 | 0 | 0 | 0 | 3 | 48 | 55.342 | 169.415 |
| 7 | 0 | 0 | 0 | 0 | 3 | 45 | 54.235 | 166.026 |
| 8 | 0 | 0 | 0 | 0 | 3 | 42 | 53.151 | 162.706 |
| 9 | 0 | 0 | 0 | 0 | 3 | 39 | 52.088 | 159.452 |
| 10 | 0 | 0 | 0 | 0 | 3 | 36 | 51.046 | 156.263 |
| 11 | 0 | 0 | 1 | 1 | 2 | 36 | 50.025 | 102.092 |
| 12 | 0 | 0 | 1 | 1 | 1 | 36 | 49.024 | 50.025 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 12.031 | 3 | 12.031 | 15.84 | 0 | 30 |
| 2 | 12.031 | 3 | 12.031 | 15.682 | 0 | 28.418 |
| 3 | 12.031 | 3 | 12.031 | 15.525 | 0 | 25.727 |
| 4 | 12.031 | 3 | 12.031 | 15.37 | 0 | 23.574 |
| 5 | 12.031 | 3 | 12.031 | 15.216 | 0 | 21.792 |
| 6 | 12.031 | 3 | 12.031 | 15.064 | 0 | 20.307 |
| 7 | 12.031 | 3 | 12.031 | 14.913 | 0 | 19.062 |
| 8 | 12.031 | 3 | 12.031 | 14.764 | 0 | 18.01 |
| 9 | 12.031 | 3 | 12.031 | 14.616 | 0 | 17.112 |
| 10 | 12.031 | 3 | 12.031 | 14.47 | 0 | 16.341 |
| 11 | 8.021 | 3 | 8.021 | 14.325 | 0 | 15.67 |
| 12 | 4.01 | 3 | 4.01 | 14.182 | 0 | 15.082 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.


## food_expansion

Food; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 120; weekly demand (120,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 120 | 120 | 10000 | 10146.8 | 1200 | 766.8 | yes |
| 2 | 120 | 120 | 10146.8 | 10348.805 | 1233.15 | 825.32 | yes |
| 3 | 120 | 120 | 10348.805 | 10503.118 | 1165.019 | 770.815 | yes |
| 4 | 120 | 120 | 10503.118 | 10657.431 | 1165.019 | 770.815 | yes |
| 5 | 120 | 120 | 10657.431 | 10811.744 | 1165.019 | 770.815 | yes |
| 6 | 120 | 120 | 10811.744 | 10921.001 | 1100.652 | 719.322 | yes |
| 7 | 120 | 120 | 10921.001 | 10987.69 | 1039.842 | 670.674 | yes |
| 8 | 120 | 120 | 10987.69 | 11014.164 | 982.391 | 624.713 | yes |
| 9 | 120 | 120 | 11014.164 | 11002.645 | 928.115 | 581.292 | yes |
| 10 | 120 | 120 | 11002.645 | 10955.231 | 876.837 | 540.27 | yes |
| 11 | 120 | 120 | 10955.231 | 10873.905 | 828.392 | 501.514 | yes |
| 12 | 120 | 120 | 10873.905 | 10760.542 | 782.624 | 464.899 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 3 | 0 | 0 | 6 | 36 | 40.25 | 241.5 |
| 2 | 0 | 0 | 1 | 1 | 5 | 36 | 40.3 | 201.5 |
| 3 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 4 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 5 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 6 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 7 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 8 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 9 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 10 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 11 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |
| 12 | 0 | 0 | 0 | 0 | 5 | 36 | 40.3 | 201.5 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 131.673 | 200 | 131.342 | 15.84 | 11.673 | 10 |
| 2 | 118.463 | 200 | 118.166 | 16.672 | 10.136 | 10.276 |
| 3 | 119.899 | 200 | 119.598 | 17.495 | 10.035 | 9.708 |
| 4 | 121.272 | 200 | 120.968 | 18.31 | 11.307 | 9.708 |
| 5 | 122.587 | 200 | 122.279 | 19.117 | 13.893 | 9.708 |
| 6 | 123.848 | 200 | 123.537 | 19.916 | 17.741 | 9.172 |
| 7 | 125.059 | 200 | 124.745 | 20.707 | 22.8 | 8.665 |
| 8 | 126.225 | 200 | 125.908 | 21.489 | 29.025 | 8.187 |
| 9 | 127.348 | 200 | 127.028 | 22.265 | 36.373 | 7.734 |
| 10 | 128.431 | 200 | 128.109 | 23.032 | 44.805 | 7.307 |
| 11 | 129.478 | 200 | 129.153 | 23.792 | 54.282 | 6.903 |
| 12 | 130.489 | 200 | 130.161 | 24.544 | 64.771 | 6.522 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.


## services_expansion_funded

Services; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 100; weekly demand (100,) (last value repeats); bank reserves 100000.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 100 | 48.124 | 10000 | 10080.65 | 1443.716 | 734.973 | yes |
| 2 | 100 | 48.124 | 10080.65 | 10143.621 | 1418.462 | 714.77 | yes |
| 3 | 100 | 48.124 | 10143.621 | 10176.669 | 1375.713 | 680.571 | yes |
| 4 | 100 | 48.124 | 10176.669 | 10246.382 | 1428.093 | 722.474 | yes |
| 5 | 100 | 48.124 | 10246.382 | 10283.92 | 1483.091 | 766.473 | yes |
| 6 | 100 | 48.124 | 10283.92 | 10507.078 | 1748.26 | 978.608 | yes |
| 7 | 100 | 48.124 | 10507.078 | 10662.238 | 1651.122 | 900.897 | yes |
| 8 | 100 | 48.124 | 10662.238 | 10862.157 | 1715.063 | 952.05 | yes |
| 9 | 100 | 48.124 | 10862.157 | 11109.073 | 1782.201 | 1005.761 | yes |
| 10 | 100 | 48.124 | 11109.073 | 11405.336 | 1852.697 | 1062.157 | yes |
| 11 | 100 | 48.124 | 11405.336 | 11753.412 | 1926.717 | 1121.373 | yes |
| 12 | 100 | 48.124 | 11753.412 | 12155.894 | 2004.438 | 1183.55 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 9 | 9 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 2 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 3 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 4 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 5 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 6 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 7 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 8 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 9 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 10 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 11 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |
| 12 | 0 | 0 | 0 | 0 | 12 | 40 | 43.75 | 525 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 48.124 | 13 | 48.124 | 25.74 | 0 | 30 |
| 2 | 48.124 | 13 | 48.124 | 26.473 | 0 | 29.475 |
| 3 | 48.124 | 13 | 48.124 | 27.198 | 0 | 28.587 |
| 4 | 48.124 | 13 | 48.124 | 27.916 | 0 | 29.675 |
| 5 | 48.124 | 14 | 48.124 | 28.627 | 0 | 30.818 |
| 6 | 48.124 | 14 | 48.124 | 29.33 | 0 | 36.328 |
| 7 | 48.124 | 14 | 48.124 | 30.027 | 0 | 34.31 |
| 8 | 48.124 | 14 | 48.124 | 30.717 | 0 | 35.639 |
| 9 | 48.124 | 14 | 48.124 | 31.4 | 0 | 37.034 |
| 10 | 48.124 | 14 | 48.124 | 32.076 | 0 | 38.498 |
| 11 | 48.124 | 14 | 48.124 | 32.745 | 0 | 40.037 |
| 12 | 48.124 | 14 | 48.124 | 33.408 | 0 | 41.652 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.


## services_expansion_no_bank

Services; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 100; weekly demand (100,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 100 | 12.031 | 10000 | 9656.65 | 360.929 | 192.743 | yes |
| 2 | 100 | 12.031 | 9656.65 | 9287.604 | 324.22 | 163.376 | yes |
| 3 | 100 | 12.031 | 9287.604 | 8927.281 | 336.681 | 173.345 | yes |
| 4 | 100 | 12.031 | 8927.281 | 8576.117 | 349.765 | 183.812 | yes |
| 5 | 100 | 12.031 | 8576.117 | 8234.569 | 363.503 | 194.803 | yes |
| 6 | 100 | 12.031 | 8234.569 | 7903.119 | 377.928 | 206.343 | yes |
| 7 | 100 | 12.031 | 7903.119 | 7582.271 | 393.075 | 218.46 | yes |
| 8 | 100 | 12.031 | 7582.271 | 7272.556 | 408.979 | 231.183 | yes |
| 9 | 100 | 12.031 | 7272.556 | 6974.531 | 425.678 | 244.542 | yes |
| 10 | 100 | 12.031 | 6974.531 | 6688.778 | 443.211 | 258.569 | yes |
| 11 | 100 | 12.031 | 6688.778 | 6415.914 | 461.622 | 273.298 | yes |
| 12 | 100 | 12.031 | 6415.914 | 6156.581 | 480.953 | 288.762 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 2 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 3 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 4 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 5 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 6 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 7 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 8 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 9 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 10 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 11 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |
| 12 | 0 | 0 | 0 | 0 | 3 | 40 | 40 | 120 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 12.031 | 3 | 12.031 | 15.84 | 0 | 30 |
| 2 | 12.031 | 3 | 12.031 | 16.672 | 0 | 26.949 |
| 3 | 12.031 | 3 | 12.031 | 17.495 | 0 | 27.985 |
| 4 | 12.031 | 3 | 12.031 | 18.31 | 0 | 29.072 |
| 5 | 12.031 | 3 | 12.031 | 19.117 | 0 | 30.214 |
| 6 | 12.031 | 3 | 12.031 | 19.916 | 0 | 31.413 |
| 7 | 12.031 | 3 | 12.031 | 20.707 | 0 | 32.672 |
| 8 | 12.031 | 3 | 12.031 | 21.489 | 0 | 33.994 |
| 9 | 12.031 | 3 | 12.031 | 22.265 | 0 | 35.382 |
| 10 | 12.031 | 3 | 12.031 | 23.032 | 0 | 36.839 |
| 11 | 12.031 | 3 | 12.031 | 23.792 | 0 | 38.369 |
| 12 | 12.031 | 3 | 12.031 | 24.544 | 0 | 39.976 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** Unfilled demand did not raise the installed capacity limit during this run; inspect finance and expansion gates.

## no_sales

Food; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 30; weekly demand (0,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 10000 | 9460 | 0 | -40 | yes |
| 2 | 0 | 0 | 9460 | 8920 | 0 | -40 | yes |
| 3 | 0 | 0 | 8920 | 8880 | 0 | -40 | yes |
| 4 | 0 | 0 | 8880 | 8840 | 0 | -40 | yes |
| 5 | 0 | 0 | 8840 | 8800 | 0 | -40 | yes |
| 6 | 0 | 0 | 8800 | 8760 | 0 | -40 | yes |
| 7 | 0 | 0 | 8760 | 8720 | 0 | -40 | yes |
| 8 | 0 | 0 | 8720 | 8680 | 0 | -40 | yes |
| 9 | 0 | 0 | 8680 | 8640 | 0 | -40 | yes |
| 10 | 0 | 0 | 8640 | 8600 | 0 | -40 | yes |
| 11 | 0 | 0 | 8600 | 8560 | 0 | -40 | yes |
| 12 | 0 | 0 | 8560 | 8520 | 0 | -40 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 2 | 2 | 1 | 36 | 40 | 40 |
| 2 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 3 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 4 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 5 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 6 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 7 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 8 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 9 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 10 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 11 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 12 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 41.086 | 200 | 40.983 | 15.84 | 41.086 | 10 |
| 2 | 0 | 200 | 41.511 | 16.672 | 41.086 | 9.448 |
| 3 | 0 | 200 | 41.407 | 16.505 | 41.086 | 8.926 |
| 4 | 0 | 200 | 41.303 | 16.34 | 41.086 | 8.926 |
| 5 | 0 | 200 | 41.199 | 16.176 | 41.086 | 8.926 |
| 6 | 0 | 200 | 41.096 | 16.015 | 41.086 | 8.481 |
| 7 | 0 | 200 | 40.993 | 15.855 | 41.086 | 7.676 |
| 8 | 0 | 200 | 40.89 | 15.696 | 41.086 | 6.828 |
| 9 | 0 | 200 | 40.787 | 15.539 | 41.086 | 6.073 |
| 10 | 0 | 200 | 40.685 | 15.384 | 41.086 | 5.402 |
| 11 | 0 | 200 | 40.583 | 15.23 | 41.086 | 4.805 |
| 12 | 0 | 200 | 40.481 | 15.077 | 41.086 | 4.709 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** The business retains workers during zero-demand weeks; retention floors and adjustment delays remain visible.

## no_sales_no_cash

Food; opening business cash 0; 3 workers; 9 potential applicants in a population of 12; opening demand 30; weekly demand (0,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 0 | -120 | 0 | -120 | yes |
| 2 | 0 | 0 | -120 | -240 | 0 | -120 | yes |
| 3 | 0 | 0 | -240 | -360 | 0 | -120 | yes |
| 4 | 0 | 0 | -360 | -480 | 0 | -120 | yes |
| 5 | 0 | 0 | -480 | -600 | 0 | -120 | yes |
| 6 | 0 | 0 | -600 | -720 | 0 | -120 | yes |
| 7 | 0 | 0 | -720 | -840 | 0 | -120 | yes |
| 8 | 0 | 0 | -840 | -960 | 0 | -120 | yes |
| 9 | 0 | 0 | -960 | -1080 | 0 | -120 | no |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 2 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 3 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 4 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 5 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 6 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 7 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 8 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |
| 9 | 0 | 0 | 0 | 0 | 3 | 36 | 40 | 120 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 30.401 | 200 | 82.362 | 14.85 | 30.401 | 10 |
| 2 | 30.427 | 200 | 82.155 | 14.701 | 60.828 | 9.448 |
| 3 | 30.453 | 200 | 81.949 | 14.554 | 91.281 | 8.926 |
| 4 | 30.479 | 200 | 81.744 | 14.409 | 121.76 | 8.432 |
| 5 | 30.505 | 200 | 81.538 | 14.265 | 152.264 | 7.52 |
| 6 | 30.531 | 200 | 81.334 | 14.122 | 182.795 | 6.689 |
| 7 | 30.557 | 200 | 81.13 | 13.981 | 213.352 | 5.95 |
| 8 | 30.583 | 200 | 80.926 | 13.841 | 243.935 | 5.293 |
| 9 | 30.609 | 200 | 80.723 | 13.703 | 274.543 | 4.709 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** Cash goes negative before sales; legacy payroll is still paid even without enough opening funds.
**Observed:** The business retains workers during zero-demand weeks; retention floors and adjustment delays remain visible.
**Observed:** A lower posted wage does not necessarily lower existing workers' contracts that week.

## services_no_sales

Services; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 12; weekly demand (0,) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 10000 | 9320 | 0 | -180 | yes |
| 2 | 0 | 0 | 9320 | 9140 | 0 | -180 | yes |
| 3 | 0 | 0 | 9140 | 8960 | 0 | -180 | yes |
| 4 | 0 | 0 | 8960 | 8780 | 0 | -180 | yes |
| 5 | 0 | 0 | 8780 | 8600 | 0 | -180 | yes |
| 6 | 0 | 0 | 8600 | 8420 | 0 | -180 | yes |
| 7 | 0 | 0 | 8420 | 8240 | 0 | -180 | yes |
| 8 | 0 | 0 | 8240 | 8060 | 0 | -180 | yes |
| 9 | 0 | 0 | 8060 | 7880 | 0 | -180 | yes |
| 10 | 0 | 0 | 7880 | 7700 | 0 | -180 | yes |
| 11 | 0 | 0 | 7700 | 7520 | 0 | -180 | yes |
| 12 | 0 | 0 | 7520 | 7340 | 0 | -180 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 2 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 3 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 4 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 5 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 6 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 7 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 8 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 9 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 10 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 11 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |
| 12 | 0 | 0 | 0 | 0 | 3 | 60 | 60 | 180 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 12.031 | 3 | 12.031 | 15.84 | 0 | 30 |
| 2 | 12.031 | 3 | 12.031 | 15.682 | 0 | 28.418 |
| 3 | 12.031 | 3 | 12.031 | 15.525 | 0 | 25.727 |
| 4 | 12.031 | 3 | 12.031 | 15.37 | 0 | 23.574 |
| 5 | 12.031 | 3 | 12.031 | 15.216 | 0 | 21.851 |
| 6 | 12.031 | 3 | 12.031 | 15.064 | 0 | 20.473 |
| 7 | 12.031 | 3 | 12.031 | 14.913 | 0 | 19.371 |
| 8 | 12.031 | 3 | 12.031 | 14.764 | 0 | 18.489 |
| 9 | 12.031 | 3 | 12.031 | 14.616 | 0 | 17.784 |
| 10 | 12.031 | 3 | 12.031 | 14.47 | 0 | 17.219 |
| 11 | 12.031 | 3 | 12.031 | 14.325 | 0 | 16.768 |
| 12 | 12.031 | 3 | 12.031 | 14.182 | 0 | 16.406 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** The business retains workers during zero-demand weeks; retention floors and adjustment delays remain visible.
**Observed:** The Services weak-demand counter never advances beyond one despite repeated zero-sales weeks; this can delay wage/headcount recovery rules.

## demand_crash_then_recovery

Food; opening business cash 10000; 3 workers; 9 potential applicants in a population of 12; opening demand 30; weekly demand (30.0, 30.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 90.0, 90.0, 90.0, 90.0) (last value repeats); bank reserves 0.

### Money and demand

| week | demand | sold | cash before | cash after | revenue | profit | firm open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 30 | 30 | 10000 | 9678 | 300 | 208 | yes |
| 2 | 30 | 30 | 9678 | 9344.398 | 283.425 | 194.74 | yes |
| 3 | 30 | 30 | 9344.398 | 8999.834 | 267.766 | 182.213 | yes |
| 4 | 0 | 0 | 8999.834 | 8959.834 | 0 | -40 | yes |
| 5 | 0 | 0 | 8959.834 | 8919.834 | 0 | -40 | yes |
| 6 | 0 | 0 | 8919.834 | 8879.834 | 0 | -40 | yes |
| 7 | 0 | 0 | 8879.834 | 8839.834 | 0 | -40 | yes |
| 8 | 0 | 0 | 8839.834 | 8799.834 | 0 | -40 | yes |
| 9 | 90 | 57.506 | 8799.834 | 9029.847 | 374.305 | 267.444 | yes |
| 10 | 90 | 41.385 | 9029.847 | 9165.576 | 239.613 | 159.69 | yes |
| 11 | 90 | 41.282 | 9165.576 | 9305.506 | 245.614 | 164.491 | yes |
| 12 | 90 | 64.615 | 9305.506 | 9517.65 | 395.063 | 251.65 | yes |

### Hiring and pay

| week | hires planned | hired | layoffs planned | laid off | workers | wage offer after | mean contract after | wages paid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 2 | 2 | 1 | 36 | 40 | 40 |
| 2 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 3 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 4 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 5 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 6 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 7 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 8 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 9 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 10 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 11 | 0 | 0 | 0 | 0 | 1 | 36 | 40 | 40 |
| 12 | 1 | 1 | 0 | 0 | 2 | 36 | 40.25 | 80.5 |

### Production and capacity

| week | production | capacity limit | productive capacity | capital | inventory | price |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 41.086 | 200 | 40.983 | 15.84 | 11.086 | 10 |
| 2 | 41.615 | 200 | 41.511 | 16.672 | 22.702 | 9.448 |
| 3 | 40.02 | 200 | 42.014 | 17.495 | 32.721 | 8.926 |
| 4 | 24.784 | 200 | 41.909 | 17.32 | 57.506 | 8.432 |
| 5 | 0 | 200 | 41.803 | 17.147 | 57.506 | 7.967 |
| 6 | 0 | 200 | 41.699 | 16.975 | 57.506 | 7.526 |
| 7 | 0 | 200 | 41.594 | 16.806 | 57.506 | 7.526 |
| 8 | 0 | 200 | 41.49 | 16.637 | 57.506 | 7.167 |
| 9 | 0 | 200 | 41.385 | 16.471 | 0 | 6.509 |
| 10 | 41.385 | 200 | 41.282 | 16.306 | 0 | 5.79 |
| 11 | 41.282 | 200 | 41.178 | 16.143 | 0 | 5.95 |
| 12 | 64.615 | 200 | 64.453 | 15.982 | 0 | 6.114 |

- PASS: Sales never exceed the funded order or real supply.
- PASS: The external buyer pays the recorded sales revenue once.
- PASS: The firm's recorded revenue equals the external receipt.
- PASS: The buyer cannot spend beyond its opening funds.
- PASS: Recorded payroll equals workers' gross wage receipts.
- PASS: Live employment links agree with the business roster.
- PASS: Closing the firm releases its workers.
- PASS: All numeric weekly observations are finite.

**Observed:** The business retains workers during zero-demand weeks; retention floors and adjustment delays remain visible.
**Observed:** Unfilled demand did not raise the installed capacity limit during this run; inspect finance and expansion gates.

## Raw evidence

results.json contains starting settings, full config, source hashes, every weekly plan, labor outcomes, market receipts, worker contracts, firm diagnostics and registered firm loans. Infinite diagnostic runway when no payroll is due is encoded as the string Infinity; numeric weekly observations must remain finite. Some engine diagnostics can persist across ticks; the copied plans, receipts and states establish the current week's actions. Existing economy-wide accounting limitations are outside these checks.
