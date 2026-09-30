# Inflation port: switch off vs on, 2026-09-29

The same code (the branch after the inflation port, commit `9e24ef1`) run twice per seed: once with `CONFIG.inflation.enabled = False` (the old weekly wage rules) and once with it `True` (the default: annual private pay review and the posted price index).

- Settings: 1,500 households, 10 firms per category, 300 ticks, normal mode, built as `regression_snapshot.py` builds it. Seeds 42, 7 and 11 on `legacy`, and seed 42 on `income_first`. Each run is its own process; runs were sequential. Metrics are averaged over ticks 11-40, 41-100, 101-200 and 201-300; money is the change from construction to tick 300.
- Reproduce with `on_off.py all` then `on_off.py table` (its output folder points at the SDD workspace).
- Definitions. Unfilled vacancies: the sum over firms of this week's planned hires minus the hires actually made this week, floored at 0. Real median wage: median wage of the employed x 100 / a shadow price index. The shadow index uses the engine's exact definition (`ConsumerPriceIndex`, same weights) but is observed by the script after every post-warm-up tick in both arms, so the "off" arm has a price level too; it is read-only (the index never changes a firm). It differs a little from the engine's own index in the "on" arm (end-of-tick quotes after firm exits and a base one week later, versus the engine's opening quotes), so the table shows both year-on-year rates.

## Headline (legacy, average of seeds 42, 7 and 11; off → on)

**With the annual pay review on, fewer people have jobs.** Unemployment is higher in every window: 29.0% → 32.0% (ticks 11-40), 31.3% → 36.8% (41-100), 9.2% → 10.6% (101-200) and 6.0% → 9.8% (201-300). Each gap is larger than the spread between seeds (0.4 to 3.0 points). Private Food and Services firms no longer raise their pay offer when they fail to hire; they wait for their yearly review. The rise starts before any review is due (the first ones fall around tick 63), so it comes from dropping the weekly offer changes, not from the review decisions.

- **Unfilled vacancies**: none in either arm through tick 100. In ticks 101-200 they average 21 → 50 a week, and in 201-300 76 → 56. The seed spread is 26 to 80 in both windows, so neither change can be told apart from noise.
- **Pay**: the nominal median wage of the employed is higher with the switch on (55.0 → 69.9 in 41-100, 57.9 in 201-300 against 53.9). Reviewed firms stop cutting pay week to week (the B20 decay, the revenue-ratio cut), so wages stay near where firms set them. Prices rise more too. The price level is higher (shadow index 139.6 → 172.2 in 101-200), and year-on-year inflation in the first year after warm-up is 25% → 36%. After that it is small or negative in both arms (on: 1.3% then -4.9%, engine index). **Real median wage** is about the same or lower: 36.3 → 36.6, 37.5 → 42.0, 41.2 → 36.5 and 39.9 → 37.0. Seed spreads are 5 to 15, so none of these moves is clearly real.
- **Sales per week** are higher with the switch on: 122,632 → 130,492 (41-100), 108,052 → 120,666 (101-200) and 91,547 → 99,475 (201-300). The last two windows are beyond the seed spread. Nominal sales are higher partly because prices are higher.
- **Businesses**: unchanged, 45 in both arms. **Median household cash** is higher in every window (89 → 119 in 201-300).
- **Money**: the price index moves no money. Money created by tick 300, net of recorded outside money (legacy entrant seed cash and the demand shock, K02), is 29,133 / 28,207 / 21,703 off and 24,105 / 22,545 / 22,797 on (seeds 42 / 7 / 11), the same order of size as before.
- **`income_first`** is identical in every quantity. The review applies only to `legacy`. The engine's index is still measured there (the on-arm year-on-year row), but measuring it moves nothing.

A small-town stress case shows the same mechanism: in the contract test town (10 households, high minimum wage 50), every firm offers exactly 50 and the new Food firms cannot hire anyone away from the baseline firms. Nobody makes food, and employment falls to zero by week 65. With the switch off, those firms raise offers each week and hire (`test_policy_sensitivity.py`, strict xfail with the switch on).

[table.md](table.md) has the per-seed tables and the full three-seed table with seed spreads.
