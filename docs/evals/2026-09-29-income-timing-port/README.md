# Income-timing port before/after, 2026-09-29

Same simulation on main before the port (`37dde4c`) and on the ported branch (legacy income before shopping, cached-plan budget refresh, B28 fixes and goods-market float buffers; commits `2782e62`..`aa7bec7`).

- Settings: 1,500 households, 10 firms per category, 300 ticks, normal mode, `create_large_economy` built exactly as `regression_snapshot.py` builds it. Each run is its own process.
- Runs: seed 42 on `legacy` and seed 42 on `income_first` only (owner time cap for the port; seeds 7 and 11 were not run). Metrics are averaged over ticks 11-40, 41-100, 101-200 and 201-300; money is the change from construction to tick 300.
- Reproduce with `before_after.py` (paths inside point at the session scratchpad and the SDD workspace; "before" is a `git archive 37dde4c backend` extraction).

Headline:

- `income_first` is identical in every window and every metric, as expected: the port does not touch the named payment arms.
- Legacy seed 42: unemployment is unchanged through tick 100 (29.3% → 29.3% in ticks 11-40; 33.6% → 33.3% in 41-100) and slightly higher later (8.8% → 9.4% in 101-200; 5.6% → 6.4% in 201-300). Median household cash is 4-9 higher in every window and mean happiness is higher from tick 41 (0.172 → 0.226 in 101-200). Cash inequality rises (Gini 0.617 → 0.654 in 41-100, 0.623 → 0.743 in 201-300), sales per week are within 1% through tick 100 and 10% lower in 201-300 (100,914 → 91,292), and the town hall holds less cash from tick 41 (for example 171,075 → 145,703 in 201-300). Money created by tick 300 is 307,432 → 359,558, of which recorded outside money (legacy entrant seed cash and the demand shock, K02) is 280,203 → 330,425; the remainder, bankrupt firms' negative cash leaving on exit, is 27,229 → 29,133.

One seed only: the phase 6 seed spreads for legacy (max minus min over seeds 42/7/11, phase 6 flag-off runs before the port) were 0.8 / 0.7 / 1.9 unemployment points and 0.016 / 0.034 / 0.080 Gini in ticks 41-100 / 101-200 / 201-300, so the unemployment moves here are inside seed noise and the late Gini rise is the only change clearly larger than it. It needs a three-seed check before being read as an effect of the timing change.

[table.md](table.md) has the full per-window table.
