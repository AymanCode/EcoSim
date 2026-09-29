# Remediation before/after, 2026-09-29

Same simulation run on the code before the agents/economy remediation (commit `17d5c0b`) and on the branch head (`8e68b40`, all Phase 6 flags at their default `False`).

- Settings: 1,500 households, 10 firms per category, 300 ticks, `create_large_economy` built exactly as `regression_snapshot.py` builds it.
- Runs: seeds 42, 7 and 11 on the default `legacy` payment sequence, and seed 42 on `income_first`. Each run is a separate process.
- Metrics are averaged over tick windows 11-40, 41-100, 101-200 and 201-300. The last table averages the three legacy seeds and shows the before-code seed spread as a noise yardstick.
- "Money created" is the change in household, firm, queued-firm, government, misc-pool and bank-reserve cash from construction to tick 300. "Recorded outside money" is the new `external_injection_total` (legacy firm-entry seed cash and the legacy demand shock, owner decision 2026-09-29); the before code does not record it.

Reproduce with `before_after.py` (paths inside point at the session scratchpad; adjust `ROOTS` to a checkout of each commit).

Headline (legacy, three-seed average): unemployment falls in every window after warm-up (41-100: 12.0% → 8.0%; 201-300: 25.2% → 6.9%), sales per week rise 26-52%, median household cash rises by about 50, happiness roughly doubles, and the town hall ends with about 168k instead of 32k. The before code loses 570k-950k of money over 300 ticks; the after code gains 555k-682k, of which 506k-636k is recorded outside money and the remaining 46k-52k comes from bankrupt firms whose negative cash disappears on exit. The `income_first` run conserves money exactly in both versions.

Three seeds only; windows whose change is smaller than the seed spread are not distinguishable from noise.
