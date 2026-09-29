# Remediation before/after, 2026-09-29

Same simulation run on the code before the agents/economy remediation (commit `17d5c0b`) and on the branch head (`8e68b40`, all Phase 6 flags at their default `False`).

- Settings: 1,500 households, 10 firms per category, 300 ticks, `create_large_economy` built exactly as `regression_snapshot.py` builds it.
- Runs: seeds 42, 7 and 11 on the default `legacy` payment sequence, and seed 42 on `income_first`. Each run is a separate process.
- Metrics are averaged over tick windows 11-40, 41-100, 101-200 and 201-300. The last table averages the three legacy seeds and shows the before-code seed spread as a noise yardstick.
- "Money created" is the change in household, firm, queued-firm, government, misc-pool and bank-reserve cash from construction to tick 300. "Recorded outside money" is the new `external_injection_total` (legacy firm-entry seed cash and the legacy demand shock, owner decision 2026-09-29); the before code does not record it.

Reproduce with `before_after.py` (paths inside point at the session scratchpad; adjust `ROOTS` to a checkout of each commit).

Headline (legacy, three-seed average): unemployment falls in every window after warm-up (41-100: 12.0% → 8.0%; 201-300: 25.2% → 6.9%), sales per week rise 26-52%, median household cash rises by about 50, happiness roughly doubles, and the town hall ends with about 168k instead of 32k. The before code loses 570k-950k of money over 300 ticks; the after code gains 555k-682k, of which 506k-636k is recorded outside money and the remaining 46k-52k comes from bankrupt firms whose negative cash disappears on exit. The `income_first` run conserves money exactly in both versions.

After the owner decision of 2026-09-29 the job-switcher vacancy fix (`CONFIG.labor_market.fix_switcher_vacancies`, audit B13/B14) is on by default, which removes the old code's largest hiring channel for the unemployed. Re-running the "after" side at commit `a017498` with the same settings ([table_switcher_permanent.md](table_switcher_permanent.md); `table.md` above is the record from before that decision): legacy unemployment, three-seed average, is now higher than the pre-remediation code early on and lower late (11-40: 10.4% → 28.9%; 41-100: 12.0% → 31.6%; 101-200: 7.4% → 8.2%; 201-300: 25.2% → 5.7%). The early rise is well outside the seed spread (0.5 and 1.2 points); the 101-200 change is inside it (3.4). Sales per week are still higher from tick 41 on (+14% to +44%), median household cash is higher by 42-50 before tick 100, by 16 over 101-200 and by 5 over 201-300 (seed spread 10), and happiness is higher in every window after warm-up. Money over 300 ticks now grows by 307k-354k, of which 280k-323k is recorded outside money and 27k-32k comes from bankrupt firms' negative cash disappearing on exit. `income_first` still conserves money exactly; its unemployment is 40.8% and 48.2% in ticks 11-40 and 41-100 (before code 7.9% and 24.4%) and 5.3% in 201-300 (34.2%). Unemployment stays high after warm-up until firms plan hiring from demand, which is a follow-up.

Three seeds only; windows whose change is smaller than the seed spread are not distinguishable from noise.
