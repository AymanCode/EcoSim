# WebSocket protocol (frame-2)

One connection is one simulation session. The first server message is
`{"type": "SESSION", "sessionId": "..."}`. Every command is a JSON object with a
`command` key. Errors are `{"error": "<text>"}`. A full server rejects the
connection at open with an error and close code 1013, before SESSION.

## Commands

| Command | Payload | Reply |
|---|---|---|
| `SETUP` | `config`: `SetupConfig` fields. New in frame-2: `experiment_id`, `arm_label`, `arm_count` (1..4), `experiment_owner`, `initial_policy` (lever vector, schema names), `frame_profile` (`"legacy"`, the default, or `"lean"`; see [Frame profiles](#frame-profiles)), `horizon_ticks` (1..5200; when omitted, 260 under `lean` and no horizon under `legacy`), `tracked_households` (1..200; when omitted, 40 under `lean` and 12 under `legacy`). Legacy `wage_tax`/`profit_tax` are folded into `initial_policy`. | `SETUP_COMPLETE` with `config`, including `experiment` (`id`, `armLabel`, `armCount`, `householdCap`), `applied_policy`, `frame_profile`, and the `horizon_ticks` (an integer or `null`) and `tracked_households` in force; and `trackedProfiles`: `{"<household id>": traits}` for the initial sample, keyed by the id as a string, in both profiles (traits as in the frame's `traits`). A failed SETUP leaves no runnable economy. |
| `START` | none | `STARTED`, then one tick frame per tick. Without a prior SETUP it builds a default economy under the `legacy` profile (no horizon, 12 tracked households). After a `FINISH` before the horizon, `START` reopens the finished warehouse run first, or replies with an error (`START failed: ...`) if it cannot. At the horizon it reopens nothing (the finished run stays finished) and the loop answers with `HORIZON_REACHED` again. |
| `STOP` | none | Waits for the loop to stop, or replies with an error (`STOP failed: ...`) if it will not. Then applies queued CONFIG actions in order, sending each `CONFIG_APPLIED`, and sends `STOPPED`. |
| `CONFIG` | `config`: camelCase aliases or canonical lever names. | Paused: `CONFIG_APPLIED`. Running: `CONFIG_QUEUED` now, `CONFIG_APPLIED` at the next tick boundary with the same `actionId`. Receipt keys: `actionId`, `requested`, `applied`, `rejected` (lever name to reason), `effectiveTick`. Replay resends `applied` unchanged. Canonical lever names are validated exactly as SETUP's `initial_policy` (no snapping, no bool conversion) and apply SETUP's canonical value; the camelCase aliases keep the old dashboard's coercion (integer levers snap to the nearest option, a bool `publicWorks` becomes `on`/`off`) before the same per-lever check. A bad value rejects only its own lever. Group rules (a sector subsidy level above 0 needs a target; a bailout policy needs a target and a budget) apply only under the `lean` profile, to the merged policy, and reject only the requested levers of the failing group, with the rule as the reason; `legacy` applies levers one by one. While the run is finished (after `FINISH`, with or without a warehouse, until `SETUP`, `RESET`, `EXTEND`, or a `START` before the horizon; a `START` at the horizon only repeats `HORIZON_REACHED`) CONFIG changes nothing and replies `{"error": "CONFIG failed: the run is finished; send EXTEND to continue, or START if it finished before its horizon"}`. |
| `TRACK` | `action`: `pin`, `unpin`, `follow`, `reshuffle`; `householdId` (an integer) for the first three. | `TRACKED` with `tracked`, `pinned`, `tick` and `profiles`: traits of the households this command added to the sample (`follow` of an untracked household, `reshuffle`), keyed by the id as a string; `{}` for `pin`, `unpin` and a `follow` of a household already tracked. Sampling uses its own RNG; the economy is unaffected. |
| `FINISH` | none | Waits for the loop to stop, or replies with an error (`FINISH failed: ...`) if it will not. Then applies queued CONFIG actions in order, sending each `CONFIG_APPLIED`, and sends `FINISHED` with `tick`, `analysisReady`, `runId`, `drained` (number of queued actions applied). Marks the warehouse run completed, keeps the session and the run open; a later disconnect or server error keeps it completed unless the final flush fails. |
| `EXTEND` | `ticks` (1..5200) | `EXTENDED` with `horizonTick`, `tick`, `resumed`. Reopens a finalized run and resumes the loop; no START needed. Replies with an error (`EXTEND failed: ...`) when the run cannot be reopened. |
| `RESET` | none | `RESET`. Legacy: zeroes the tick without rebuilding the economy and discards queued CONFIG actions. The new client sends `SETUP` again instead. |
| `STABILIZERS` | as before | `STABILIZERS_UPDATED`. While the run is finished (as for CONFIG) it changes nothing and replies `{"error": "STABILIZERS failed: the run is finished; send EXTEND to continue, or START if it finished before its horizon"}`. |

When the tick reaches the horizon the loop pauses, applies CONFIG actions queued during the last tick
(sending each `CONFIG_APPLIED`), and then sends `{"type": "HORIZON_REACHED", "tick": n}` once per horizon.

## Household budget

`experiment_id` groups sessions. The first arm fixes the owner (`experiment_owner`),
the arm count and the shared world (seed, firms per sector, stabilizers, payment
rules). The server rejects a `SETUP` that would take an arm above `10000 // arm_count`,
exceed 10,000 in total, duplicate an `arm_label`, add a fifth arm, come from a
different owner, or use a different world. Reservations are released on
disconnect or on the session's next `SETUP`.

## Frame profiles

`frame_profile` chosen at SETUP decides what each tick frame carries and whether CONFIG enforces the lever
group rules at runtime: `lean` enforces them, `legacy` does not (see `CONFIG`). It is not part of an
experiment's shared world. Apart from that CONFIG rule it changes only what frames carry, never the economy or
the session's random streams.

- `"legacy"` (the default, for the current dashboard): every key of the previous frame with its old meaning,
  plus the frame-2 keys below, with the pre-frame-2 defaults (no horizon, 12 tracked households) when SETUP
  omits them.
- `"lean"` (for the new client), which differs from legacy in the CONFIG group rules above and in these omissions:
  - Each `metrics.trackedSubjects` entry omits `history`, `traits`, `expectedWageReason` and `recentEvents`,
    unless its household is pinned (`metrics.pinnedHouseholdIds`); pinned entries keep all four. Every other
    subject field is sent as in legacy. The server keeps sampling each tracked household's history either way,
    so a household pinned later arrives with its history.
  - `metrics.trackedFirms` and the top-level `firm_stats` are absent (not `null`).
  - Traits travel out of band instead: `SETUP_COMPLETE.trackedProfiles` for the initial sample and
    `TRACKED.profiles` for households added later. Traits do not change during a run.

## Tick frame

All keys of the previous frame are unchanged (the `lean` profile omits the ones listed under
[Frame profiles](#frame-profiles)). Added at the top level, every tick:

- `schemaVersion`: `"frame-2"`.
- `frameProfile`: `"legacy"` or `"lean"`, as chosen at SETUP.
- `arm`: `{"experimentId", "armLabel", "armCount"}` as given at SETUP; `experimentId` and `armLabel` are
  `null` and `armCount` is `1` when the session is not part of an experiment.
- `horizonTick`: the tick at which the loop pauses with `HORIZON_REACHED` (an integer, or `null` when no
  horizon is set).
- `events`: this tick's typed events, each sent once, at most 50, firm/policy/default/shock/regime events
  first. Each is `{"id", "tick", "type", "householdId", "firmId", "firmName", "sector", "value", "text"}`;
  `type` is `firm_opened`, `firm_closed`, `policy_changed`, `loan_default`, `shock`, `regime`, `hired`,
  `laid_off`, `care_denied` or `care_completed`. Events about a household (hires, layoffs, care, household
  loan defaults and household regime events such as `eviction`) carry `householdId` and appear only for
  tracked households; firm regime events carry `firmId` and `firmName`. `value` by type:
  - `firm_opened`: staff at opening; `firm_closed`: `null` (`text` is the bankruptcy reason code, or `null`).
  - `policy_changed`: the lever value when numeric, else `null` (`text` is `lever=value`). Its `id` is
    `<tick>:policy_changed:<actionId or auto>:<lever>:<n>`, where `n` counts this frame's policy events from 0,
    so two changes of one lever in a tick keep distinct ids.
  - `loan_default`: currency written off.
  - `shock`: magnitude (cash per household for `shock_demand`, productivity factor for `shock_supply`,
    health change for `shock_health`; `text` is the shock type).
  - `regime`: the event's metric, or its severity when it has none (`text` is the regime event type).
  - `hired`, `laid_off`: wage; `care_denied`, `care_completed`: visit price.
- `eventCounts`: this tick's totals over the whole economy (`hired`, `laidOff`, `careDenied`,
  `careCompleted`, `firmsOpened`, `firmsClosed`, `loanDefaults`, `policyChanges`, `shocks`, `regime`),
  plus `detailed` (events sent) and `dropped` (events over the cap).
- `firmsClosed`: firms closed in the last 52 ticks, each `{"id", "name", "sector", "closedTick", "lastStaff"}`.
- `projectionMs`: milliseconds the server spent building this tick's events, `curated`, `firms` and the
  payment snapshot that `metrics.payment` also carries.
- `curated`: newcomer-facing figures, each computed fresh this tick from the economy unless noted:
  - `householdsTotal`: number of households.
  - `peopleOutOfWorkPer100`: households able to work with no employer, per 100 households able to work;
    `0.0` when nobody can work.
  - `typicalWeeklyPay`: median wage of employed households, currency per tick; `0.0` when nobody is employed.
  - `foodSpendPerHousehold`: mean food spend per household this tick (goods-market receipts), currency.
  - `priceFood`, `priceHousing`, `priceServices`, `priceHealthcare`: mean posted price of that sector's firms,
    currency per unit; `null` when the sector has no firm.
  - `townHallCash`: government cash balance, currency, negative when in debt.
  - `homelessHouseholds`: households without housing, from the housing diagnostics; `0.0` when absent.
  - `careDenials`: healthcare visits denied as unaffordable this tick, from the health diagnostics; `null`
    when the diagnostics are absent or do not report it.
  - `firmsOpen`: operating firms; `firmsStruggling`, `firmsGrowing`, `firmsSteady`: those firms counted by
    `state` (see `firms`).
  - `bankActiveLoans`: the bank's active loans, a count; `null` without a bank.
  - `bankDefaultAmountThisTick`: currency the bank wrote off this tick; `null` without a bank.
  - `bankDefaultsTotal`: defaulted loan claims so far, a count, the same value as
    `metrics.payment.loans.defaults_total`; `null` under the legacy payment sequence.
  - `publicWorksJobs`: workers employed by public-works firms, a count.
  - `gini`, `wealthP10`, `wealthP50`, `wealthP90`: Gini coefficient of household cash and its 10th, 50th and
    90th percentiles (currency). Stride-cached: recomputed every 5 ticks, on the first tick after SETUP and
    on LLM-decision ticks; `wealthAsOfTick` is the tick they were computed on. `null` when the economy has
    no households.
- `firms`: every operating firm, richest first (`cash` descending), every tick. Each is `{"id", "name",
  "sector", "cash", "staff", "price", "lastRevenue", "lastProfit", "state", "isBaseline"}`: `name` is the
  firm's good name, `cash` and this tick's `lastRevenue`/`lastProfit` are currency, `staff` is the employee
  count, `price` the posted price, `isBaseline` is `true` for government baseline firms. `state` is
  `struggling` (cash at or below zero, burn or survival mode, or more than two ticks at zero cash), else
  `growing` (hires planned), else `steady`.
- `frameBytesPrev`: size in UTF-8 bytes of the previous tick frame as sent, an integer; `0` on the first
  frame after SETUP.
- `serializeMsPrev`: milliseconds the server spent encoding the previous tick frame to JSON (a float);
  `0.0` on the first frame after SETUP. A frame cannot carry its own size or encoding time, so both describe
  the frame before it.

A legacy `RESET` also restarts event collection: the closed-firm list empties and earlier policy
changes and defaults are not reported again. It also clears the stride-cached figures, so the first tick
after it recomputes them and `curated.wealthAsOfTick` restarts at `1`.

Added inside `metrics`:

- `pinnedHouseholdIds`: ids of the pinned households, every tick.
- Per tracked household in `metrics.trackedSubjects`: `rentArrears` (rent owed,
  `0.0` under the legacy payment sequence) and `leaseRenewalTick` (tick of the
  next lease renewal, `-1` when the household has no lease), every tick.
- Policy-change records in `metrics.policyChanges` carry `actionId`: a
  12-character id for user actions and `null` for automatic ones.
- Per tracked household, `recentEvents` lists its last five events as
  `{"tick", "type", "firmName", "value"}` (under `lean`, pinned households only).
