# Before/after with the job-switcher vacancy fix on by default

Same runs and settings as `table.md`; the "after" side is re-run at commit `a017498`, where `CONFIG.labor_market.fix_switcher_vacancies` defaults to `True` (owner decision 2026-09-29). The "before" side is the unchanged pre-remediation run (`17d5c0b`). `table.md` is kept as the record from before that decision.

### seed 42, legacy

| Metric | ticks 11-40 | ticks 41-100 | ticks 101-200 | ticks 201-300 |
|---|---|---|---|---|
| Unemployment % | 10.2 → 29.3 | 11.8 → 33.6 | 5.3 → 8.8 | 20.7 → 5.6 |
| Median wage (employed) | 44.5 → 43.5 | 49.7 → 55.1 | 55.7 → 57.6 | 50.0 → 56.8 |
| Median household cash | 289 → 340 | 136 → 169 | 113 → 128 | 76 → 79 |
| Cash inequality (Gini) | 0.674 → 0.644 | 0.647 → 0.617 | 0.641 → 0.604 | 0.602 → 0.623 |
| Businesses | 43.7 → 43.9 | 44.9 → 45.7 | 45.0 → 45.0 | 45.0 → 45.0 |
| Sales per week | 56,540 → 59,922 | 91,244 → 122,336 | 104,892 → 107,588 | 75,386 → 100,914 |
| Homeless households | 0 → 0 | 0 → 0 | 1 → 1 | 0 → 0 |
| Mean happiness | 0.657 → 0.655 | 0.251 → 0.387 | 0.107 → 0.172 | 0.076 → 0.103 |
| Town hall cash | 456,246 → 343,136 | 161,471 → 144,999 | 165,765 → 168,528 | 74,714 → 171,075 |
| Money created by tick 300 (total) | -572,381 → 307,432 | | | |
| of which recorded outside money | 0 → 280,203 | | | |

### seed 7, legacy

| Metric | ticks 11-40 | ticks 41-100 | ticks 101-200 | ticks 201-300 |
|---|---|---|---|---|
| Unemployment % | 10.7 → 28.9 | 11.5 → 30.4 | 8.1 → 7.9 | 26.2 → 5.6 |
| Median wage (employed) | 44.0 → 42.7 | 47.8 → 55.0 | 53.8 → 58.5 | 49.4 → 54.7 |
| Median household cash | 283 → 345 | 116 → 175 | 107 → 133 | 74 → 85 |
| Cash inequality (Gini) | 0.709 → 0.667 | 0.675 → 0.633 | 0.656 → 0.625 | 0.576 → 0.588 |
| Businesses | 43.4 → 43.9 | 45.0 → 45.3 | 45.0 → 45.0 | 45.0 → 45.0 |
| Sales per week | 63,311 → 59,030 | 82,122 → 126,165 | 96,122 → 114,638 | 70,516 → 96,052 |
| Homeless households | 0 → 0 | 0 → 0 | 0 → 0 | 1 → 1 |
| Mean happiness | 0.650 → 0.659 | 0.214 → 0.402 | 0.089 → 0.187 | 0.065 → 0.098 |
| Town hall cash | 427,619 → 363,011 | 142,073 → 176,946 | 150,371 → 185,888 | 26,697 → 160,314 |
| Money created by tick 300 (total) | -947,794 → 354,339 | | | |
| of which recorded outside money | 0 → 323,426 | | | |

### seed 11, legacy

| Metric | ticks 11-40 | ticks 41-100 | ticks 101-200 | ticks 201-300 |
|---|---|---|---|---|
| Unemployment % | 10.4 → 28.5 | 12.7 → 30.9 | 8.7 → 7.9 | 28.7 → 6.1 |
| Median wage (employed) | 44.5 → 43.6 | 48.0 → 55.0 | 53.8 → 56.5 | 45.8 → 58.5 |
| Median household cash | 297 → 335 | 129 → 164 | 111 → 118 | 84 → 84 |
| Cash inequality (Gini) | 0.618 → 0.607 | 0.636 → 0.630 | 0.651 → 0.638 | 0.560 → 0.604 |
| Businesses | 43.5 → 43.9 | 44.9 → 45.4 | 44.9 → 45.0 | 45.0 → 45.0 |
| Sales per week | 57,348 → 62,079 | 84,759 → 122,147 | 92,166 → 111,261 | 66,712 → 102,027 |
| Homeless households | 0 → 0 | 1 → 0 | 0 → 0 | 0 → 0 |
| Mean happiness | 0.649 → 0.648 | 0.228 → 0.356 | 0.080 → 0.166 | 0.067 → 0.096 |
| Town hall cash | 436,752 → 357,288 | 156,147 → 168,435 | 146,129 → 190,658 | -4,025 → 164,717 |
| Money created by tick 300 (total) | -647,269 → 340,221 | | | |
| of which recorded outside money | 0 → 307,936 | | | |

### seed 42, income_first

| Metric | ticks 11-40 | ticks 41-100 | ticks 101-200 | ticks 201-300 |
|---|---|---|---|---|
| Unemployment % | 7.9 → 40.8 | 24.4 → 48.2 | 12.2 → 17.0 | 34.2 → 5.3 |
| Median wage (employed) | 43.7 → 40.1 | 45.7 → 54.9 | 46.2 → 58.0 | 44.9 → 61.3 |
| Median household cash | 149 → 158 | 14 → 45 | 39 → 40 | 44 → 47 |
| Cash inequality (Gini) | 0.828 → 0.804 | 0.905 → 0.791 | 0.810 → 0.817 | 0.748 → 0.778 |
| Businesses | 43.9 → 43.9 | 46.0 → 46.0 | 46.0 → 46.0 | 46.0 → 46.0 |
| Sales per week | 47,396 → 41,642 | 61,221 → 92,182 | 82,005 → 114,487 | 42,705 → 108,836 |
| Homeless households | 26 → 20 | 33 → 15 | 21 → 4 | 17 → 4 |
| Mean happiness | 0.513 → 0.516 | 0.075 → 0.137 | 0.061 → 0.099 | 0.052 → 0.095 |
| Town hall cash | 308,024 → 210,601 | 243,084 → 216,784 | 287,318 → 356,689 | 130,233 → 319,036 |
| Money created by tick 300 (total) | 0 → 0 | | | |
| of which recorded outside money | 0 → 0 | | | |

### Legacy average of seeds 42, 7, 11 (spread = max-min across seeds, before code)

| Metric | Window | Before | After | Change | Before seed spread |
|---|---|---|---|---|---|
| Unemployment % | 11-40 | 10.4 | 28.9 | +18.5 | 0.5 |
| Unemployment % | 41-100 | 12.0 | 31.6 | +19.6 | 1.2 |
| Unemployment % | 101-200 | 7.4 | 8.2 | +0.8 | 3.4 |
| Unemployment % | 201-300 | 25.2 | 5.7 | -19.5 | 8.0 |
| Median wage (employed) | 11-40 | 44.3 | 43.3 | -1.1 | 0.5 |
| Median wage (employed) | 41-100 | 48.5 | 55.0 | +6.5 | 1.9 |
| Median wage (employed) | 101-200 | 54.4 | 57.5 | +3.1 | 1.9 |
| Median wage (employed) | 201-300 | 48.4 | 56.7 | +8.3 | 4.2 |
| Median household cash | 11-40 | 290 | 340 | +50 | 15 |
| Median household cash | 41-100 | 127 | 169 | +42 | 21 |
| Median household cash | 101-200 | 110 | 127 | +16 | 6 |
| Median household cash | 201-300 | 78 | 83 | +5 | 10 |
| Cash inequality (Gini) | 11-40 | 0.667 | 0.639 | -0.028 | 0.091 |
| Cash inequality (Gini) | 41-100 | 0.652 | 0.627 | -0.026 | 0.039 |
| Cash inequality (Gini) | 101-200 | 0.649 | 0.622 | -0.027 | 0.015 |
| Cash inequality (Gini) | 201-300 | 0.579 | 0.605 | +0.026 | 0.042 |
| Businesses | 11-40 | 43.5 | 43.9 | +0.4 | 0.3 |
| Businesses | 41-100 | 44.9 | 45.5 | +0.6 | 0.1 |
| Businesses | 101-200 | 44.9 | 45.0 | +0.1 | 0.1 |
| Businesses | 201-300 | 45.0 | 45.0 | +0.0 | 0.0 |
| Sales per week | 11-40 | 59,066 | 60,344 | +1,277 | 6,771 |
| Sales per week | 41-100 | 86,042 | 123,549 | +37,508 | 9,121 |
| Sales per week | 101-200 | 97,727 | 111,162 | +13,436 | 12,726 |
| Sales per week | 201-300 | 70,872 | 99,664 | +28,793 | 8,674 |
| Homeless households | 11-40 | 0 | 0 | -0 | 0 |
| Homeless households | 41-100 | 0 | 0 | -0 | 1 |
| Homeless households | 101-200 | 0 | 0 | -0 | 1 |
| Homeless households | 201-300 | 0 | 0 | +0 | 0 |
| Mean happiness | 11-40 | 0.652 | 0.654 | +0.002 | 0.008 |
| Mean happiness | 41-100 | 0.231 | 0.382 | +0.151 | 0.037 |
| Mean happiness | 101-200 | 0.092 | 0.175 | +0.083 | 0.026 |
| Mean happiness | 201-300 | 0.069 | 0.099 | +0.030 | 0.011 |
| Town hall cash | 11-40 | 440,206 | 354,479 | -85,727 | 28,627 |
| Town hall cash | 41-100 | 153,230 | 163,460 | +10,230 | 19,398 |
| Town hall cash | 101-200 | 154,088 | 181,691 | +27,603 | 19,636 |
| Town hall cash | 201-300 | 32,462 | 165,369 | +132,906 | 78,739 |
