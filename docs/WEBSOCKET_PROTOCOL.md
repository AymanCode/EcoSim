# WebSocket protocol (frame-2)

One connection is one simulation session. The first server message is
`{"type": "SESSION", "sessionId": "..."}`. Every command is a JSON object with a
`command` key. Errors are `{"error": "<text>"}`. A full server rejects the
connection at open with an error and close code 1013, before SESSION.

## Commands

| Command | Payload | Reply |
|---|---|---|
| `SETUP` | `config`: `SetupConfig` fields. New in frame-2: `experiment_id`, `arm_label`, `arm_count` (1..4), `experiment_owner`, `initial_policy` (lever vector, schema names), `horizon_ticks` (default 260), `tracked_households` (default 40). Legacy `wage_tax`/`profit_tax` are folded into `initial_policy`. | `SETUP_COMPLETE` with `config`, including `experiment` (`id`, `armLabel`, `armCount`, `householdCap`) and `applied_policy`. A failed SETUP leaves no runnable economy. |
| `START` | none | `STARTED`, then one tick frame per tick. After a `FINISH`, `START` reopens the finished warehouse run first, or replies with an error (`START failed: ...`) if it cannot. |
| `STOP` | none | Waits for the loop to stop, or replies with an error (`STOP failed: ...`) if it will not. Then applies queued CONFIG actions in order, sending each `CONFIG_APPLIED`, and sends `STOPPED`. |
| `CONFIG` | `config`: camelCase aliases or canonical lever names. | Paused: `CONFIG_APPLIED`. Running: `CONFIG_QUEUED` now, `CONFIG_APPLIED` at the next tick boundary with the same `actionId`. Receipt keys: `actionId`, `requested`, `applied`, `rejected` (lever or `_group`), `effectiveTick`. Replay resends `applied` unchanged. |
| `TRACK` | `action`: `pin`, `unpin`, `follow`, `reshuffle`; `householdId` (an integer) for the first three. | `TRACKED` with `tracked`, `pinned`, `tick`. Sampling uses its own RNG; the economy is unaffected. |
| `FINISH` | none | Waits for the loop to stop, or replies with an error (`FINISH failed: ...`) if it will not. Then applies queued CONFIG actions in order, sending each `CONFIG_APPLIED`, and sends `FINISHED` with `tick`, `analysisReady`, `runId`, `drained` (number of queued actions applied). Marks the warehouse run completed, keeps the session and the run open. |
| `EXTEND` | `ticks` (1..5200) | `EXTENDED` with `horizonTick`, `tick`, `resumed`. Reopens a finalized run and resumes the loop; no START needed. Replies with an error (`EXTEND failed: ...`) when the run cannot be reopened. |
| `RESET` | none | `RESET`. Legacy: zeroes the tick without rebuilding the economy and discards queued CONFIG actions. The new client sends `SETUP` again instead. |
| `STABILIZERS` | as before | `STABILIZERS_UPDATED`. |

When the tick reaches the horizon the loop pauses and sends
`{"type": "HORIZON_REACHED", "tick": n}` once per horizon.

## Household budget

`experiment_id` groups sessions. The first arm fixes the owner (`experiment_owner`),
the arm count and the shared world (seed, firms per sector, stabilizers, payment
rules). The server rejects a `SETUP` that would take an arm above `10000 // arm_count`,
exceed 10,000 in total, duplicate an `arm_label`, add a fifth arm, come from a
different owner, or use a different world. Reservations are released on
disconnect or on the session's next `SETUP`.

## Tick frame

All keys of the previous frame are unchanged. Added inside `metrics`:

- `pinnedHouseholdIds`: ids of the pinned households, every tick.
- Per tracked household in `metrics.trackedSubjects`: `rentArrears` (rent owed,
  `0.0` under the legacy payment sequence) and `leaseRenewalTick` (tick of the
  next lease renewal, `-1` when the household has no lease), every tick.
- Policy-change records in `metrics.policyChanges` carry `actionId`: a
  12-character id for user actions and `null` for automatic ones.
