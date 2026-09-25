# Concurrent frame benchmark and phase-1 gate (2026-09-24)

This directory holds the evidence for the backend half of the performance budget in section 8 of [the frontend learning redesign spec](../../superpowers/specs/2026-09-24-frontend-learning-redesign-design.md): frame size at 1,000 households with 40 tracked households and all firms at most 60 KB, and projection plus serialization at most 10 percent of loop tick time. It also checks that the live WebSocket session path reproduces the headless newcomer smoke runner for the same seed.

All outcomes describe EcoSim's synthetic economy. They are not real-world forecasts or policy recommendations.

## Result

Update, 2026-09-25: with the SETUP option `frame_profile: "lean"` (the new client's frame) the same command passes the phase gate; see [Lean profile gate (2026-09-25)](#lean-profile-gate-2026-09-25). The result below is run 1's frame, every per-household key for 40 tracked households, which the `legacy` profile (the current dashboard's) still sends; legacy samples 12 households unless SETUP asks for more.

**The phase-1 gate fails on frame size.** At two towns of 1,000 households, warehouse off, both towns miss the byte budget: the p95 frame is 186,587 bytes for Town A and 188,160 for Town B against a limit of 61,440 (60 KB), about three times over. The other two checks pass: projection plus serialization is 1.9 percent of the median tick for each town (limit 10 percent), and the live session matched the headless runner at every checkpoint. The CLI exited `1`.

| Run | Role | Exit code | Bytes p95 (Town A) | Overhead share (p50) | Equivalence |
|---|---|---|---|---|---|
| 2 x 1,000, 260 ticks, warehouse off | phase gate | `1` | 186,587 | 1.9% | matched at 7 of 7 checkpoints |
| 2 x 1,000, 260 ticks, warehouse on | recorded | `1` | 186,586 | 1.9% | matched at 7 of 7 checkpoints |
| 2 x 5,000, 52 ticks, warehouse off | recorded | `1` | 143,972 | 0.7% | not checked (`--skip-equivalence`) |
| 4 x 2,500, 52 ticks, warehouse off | recorded | `1` | 127,306 | 0.9% | not checked (`--skip-equivalence`) |

Run 1 comes from the reviewed tool. Runs 2 to 4 were produced before the review fixes and are kept as recorded: their gate section checks Town A only, and in runs 3 and 4 `'equivalence': True` means "not checked". The reviewed tool checks every arm, reports a skipped check as `"skipped"`, and exits `0` only for a phase-gate pass, `2` for a matrix run whose measured checks pass with equivalence skipped, and `1` otherwise. Runs 3 and 4 would still exit `1` because every arm misses the byte budget. Runs 2 to 4 inform phase 2 and do not gate phase 1.

## What was run

`backend/tools/benchmarks/run_frame_bench.py` starts a real Uvicorn server (`backend.server:app`, one worker, `ECOSIM_MAX_SESSIONS=8`), opens one WebSocket per arm and runs all arms at once through SETUP, START, the horizon and FINISH. Every arm shares one experiment id, owner, seed and five firms per sector; Town A has no initial policy and the other towns start with `benefit_level: high`. Per frame it records the UTF-8 byte length received, `metrics.tickComputeMs`, `projectionMs`, the server's `serializeMsPrev` (time `json.dumps` took for the previous frame), the receive time and `curated.peopleOutOfWorkPer100`. A percentile p takes the sorted value at index round(p x (n - 1)) with no interpolation (Python's `round`, so an exact half goes to the even index); the serialization percentile skips the first frame, which carries no previous value. The gate checks both budgets for every arm and names the arms that miss one; equivalence uses Town A. Each receive is bounded (60 s without a message, 30 minutes per arm), a server error fails the arm with its text, and a frame missing any of the recorded fields fails the run instead of counting as zero. All arms share one server process and event loop, so an arm's inter-frame time includes the other arms' ticks and the loop's 50 ms minimum sleep; `tickComputeMs` covers one arm's own tick, including projection but not serialization. The client also runs every arm on one asyncio event loop in one process. In run 4, with four arms, frames arrive about 880 ms apart for a median tick near 210 ms. Sharing one client loop, like sharing the server loop, inflates only the inter-frame times: frame bytes are counted per message, and `tickComputeMs`, `projectionMs` and `serializeMsPrev` are measured by the server inside each arm's own tick.

The equivalence check runs `run_newcomer_smoke.run_arm` for the baseline arm (same seed, households, ticks, five firms per sector, legacy payment sequence) and compares the session's `peopleOutOfWorkPer100` at frame tick `t` with 100 times the `unemployment_rate` of the smoke row stamped `t - 1` (the smoke runner stamps rows with the pre-step tick), with an absolute tolerance of `1e-6`.

Environment: Apple M4 (10 cores, 16 GB), macOS 27.0, Python 3.13.2, Uvicorn 0.41.0, websockets 16.0, Starlette 1.0.0. Code: branch `feat/frontend-redesign-phase1`; runs 2 to 4 at `303a253` plus the Task 8 changes committed in `b97943d`, run 1 re-run with the review fixes committed with this update. The warehouse-on run wrote two completed, analysis-ready SQLite runs with 520 tick-metric rows.

## Commands and complete summaries

### Run 1 (phase gate)

```bash
.venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 1000 --ticks 260 --arms 2 --seed 1337
```

Exit code `1`. Data: [`data/arms2-hh1000-t260-seed1337-whoff.json`](data/arms2-hh1000-t260-seed1337-whoff.json). `summary.md`:

```markdown
# Frame bench: 2 arms x 1000 households, 260 ticks, seed 1337, warehouse off

- wall clock: 53.6 s

## Town A
- bytes p50 / p95 / max: 152465 / 186587 / 195871
- tick compute ms p50 / p95: 93.4 / 131.7
- projection ms p50 / p95: 0.35 / 0.40
- serialize ms p50 / p95: 1.44 / 1.90
- inter-frame ms p50 / p95: 203.9 / 245.7

## Town B
- bytes p50 / p95 / max: 154780 / 188160 / 198180
- tick compute ms p50 / p95: 93.4 / 131.3
- projection ms p50 / p95: 0.36 / 0.44
- serialize ms p50 / p95: 1.46 / 1.92
- inter-frame ms p50 / p95: 194.9 / 273.3

## Gate
- Town A: bytes p95 186587 (limit 61440, over); overhead share of tick (p50) 1.9% (limit 10%, ok)
- Town B: bytes p95 188160 (limit 61440, over); overhead share of tick (p50) 1.9% (limit 10%, ok)
- failing arms: ['Town A', 'Town B']
- checks: {'bytesP95': False, 'overheadShare': True, 'equivalence': True}
- measured checks passed: False
- phase gate passed: False
- result: failed: bytesP95 (exit 1)

## Equivalence with the headless smoke runner
| frame tick | session | smoke (tick-1) | match |
|---|---|---|---|
| 13 | 2.1 | 2.1 | True |
| 26 | 8.2 | 8.200000000000001 | True |
| 52 | 19.4 | 19.400000000000002 | True |
| 104 | 25.881168177240685 | 25.88116817724068 | True |
| 156 | 19.611848825331972 | 19.611848825331972 | True |
| 208 | 29.7741273100616 | 29.774127310061605 | True |
| 260 | 36.69724770642202 | 36.69724770642202 | True |
```

### Run 2 (recorded)

```bash
.venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 1000 --ticks 260 --arms 2 --seed 1337 --warehouse
```

Exit code `1`. Data: [`data/arms2-hh1000-t260-seed1337-whon.json`](data/arms2-hh1000-t260-seed1337-whon.json). `summary.md`:

```markdown
# Frame bench: 2 arms x 1000 households, 260 ticks, seed 1337, warehouse on

- wall clock: 57.5 s

## Town A
- bytes p50 / p95 / max: 152464 / 186586 / 195871
- tick compute ms p50 / p95: 92.9 / 131.6
- projection ms p50 / p95: 0.34 / 0.38
- serialize ms p50 / p95: 1.43 / 1.90
- inter-frame ms p50 / p95: 223.4 / 263.9

## Town B
- bytes p50 / p95 / max: 154779 / 188160 / 198180
- tick compute ms p50 / p95: 92.3 / 129.5
- projection ms p50 / p95: 0.35 / 0.39
- serialize ms p50 / p95: 1.45 / 1.92
- inter-frame ms p50 / p95: 208.8 / 293.3

## Gate
- overhead share of tick (p50): 1.9%
- checks: {'bytesP95': False, 'overheadShare': True, 'equivalence': True}
- passed: False

## Equivalence with the headless smoke runner
| frame tick | session | smoke (tick-1) | match |
|---|---|---|---|
| 13 | 2.1 | 2.1 | True |
| 26 | 8.2 | 8.200000000000001 | True |
| 52 | 19.4 | 19.400000000000002 | True |
| 104 | 25.881168177240685 | 25.88116817724068 | True |
| 156 | 19.611848825331972 | 19.611848825331972 | True |
| 208 | 29.7741273100616 | 29.774127310061605 | True |
| 260 | 36.69724770642202 | 36.69724770642202 | True |
```

### Run 3 (recorded)

```bash
.venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 5000 --ticks 52 --arms 2 --seed 1337 --skip-equivalence
```

Exit code `1`. Data: [`data/arms2-hh5000-t52-seed1337-whoff.json`](data/arms2-hh5000-t52-seed1337-whoff.json). `summary.md`:

```markdown
# Frame bench: 2 arms x 5000 households, 52 ticks, seed 1337, warehouse off

- wall clock: 46.3 s

## Town A
- bytes p50 / p95 / max: 141600 / 143972 / 152351
- tick compute ms p50 / p95: 432.9 / 642.5
- projection ms p50 / p95: 2.06 / 2.70
- serialize ms p50 / p95: 1.11 / 1.22
- inter-frame ms p50 / p95: 875.5 / 1151.8

## Town B
- bytes p50 / p95 / max: 141288 / 143582 / 152883
- tick compute ms p50 / p95: 425.1 / 579.5
- projection ms p50 / p95: 2.11 / 2.93
- serialize ms p50 / p95: 1.10 / 1.18
- inter-frame ms p50 / p95: 861.7 / 1269.9

## Gate
- overhead share of tick (p50): 0.7%
- checks: {'bytesP95': False, 'overheadShare': True, 'equivalence': True}
- passed: False
```

### Run 4 (recorded)

```bash
.venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 2500 --ticks 52 --arms 4 --seed 1337 --skip-equivalence
```

Exit code `1`. Data: [`data/arms4-hh2500-t52-seed1337-whoff.json`](data/arms4-hh2500-t52-seed1337-whoff.json). `summary.md`:

```markdown
# Frame bench: 4 arms x 2500 households, 52 ticks, seed 1337, warehouse off

- wall clock: 46.3 s

## Town A
- bytes p50 / p95 / max: 123685 / 127306 / 139369
- tick compute ms p50 / p95: 214.2 / 327.1
- projection ms p50 / p95: 0.96 / 1.18
- serialize ms p50 / p95: 0.99 / 1.10
- inter-frame ms p50 / p95: 887.7 / 1098.6

## Town B
- bytes p50 / p95 / max: 125389 / 128644 / 140274
- tick compute ms p50 / p95: 211.7 / 297.5
- projection ms p50 / p95: 0.94 / 1.22
- serialize ms p50 / p95: 1.01 / 1.08
- inter-frame ms p50 / p95: 872.5 / 1099.7

## Town C
- bytes p50 / p95 / max: 125389 / 128646 / 140274
- tick compute ms p50 / p95: 214.8 / 296.3
- projection ms p50 / p95: 0.94 / 1.10
- serialize ms p50 / p95: 1.00 / 1.12
- inter-frame ms p50 / p95: 871.0 / 1153.0

## Town D
- bytes p50 / p95 / max: 125389 / 128645 / 140275
- tick compute ms p50 / p95: 210.9 / 287.0
- projection ms p50 / p95: 0.92 / 1.13
- serialize ms p50 / p95: 1.00 / 1.09
- inter-frame ms p50 / p95: 892.8 / 1177.7

## Gate
- overhead share of tick (p50): 0.9%
- checks: {'bytesP95': False, 'overheadShare': True, 'equivalence': True}
- passed: False
```

## Lean profile gate (2026-09-25)

The frame contract change deferred from phase 1 landed as a SETUP option, `frame_profile` (see `docs/WEBSOCKET_PROTOCOL.md`). `"legacy"`, the default, keeps every old frame key for the current dashboard. `"lean"`, for the new client, sends `history`, `traits`, `expectedWageReason` and `recentEvents` only for pinned households, omits `metrics.trackedFirms` and the top-level `firm_stats`, and delivers traits once, in `SETUP_COMPLETE.trackedProfiles` and `TRACKED.profiles`. The bench now sends `frame_profile` in every arm's SETUP (`--frame-profile`, default `lean`); the world, seed and arms are the same as run 1, and lean's default sample is run 1's 40 tracked households. No float rounding was needed. After this run the bench also started sending `tracked_households: 40` explicitly, so a `--frame-profile legacy` run measures the same 40 households instead of legacy's default 12; for lean the explicit value equals the default it resolved here, so the frames are unchanged.

```bash
.venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 1000 --ticks 260 --arms 2 --seed 1337
```

Exit code `0`: the phase gate passes. Data: [`data/arms2-hh1000-t260-seed1337-whoff-lean.json`](data/arms2-hh1000-t260-seed1337-whoff-lean.json). Complete output (`summary.md`):

```markdown
# Frame bench: 2 arms x 1000 households, 260 ticks, seed 1337, warehouse off, frame profile lean

- wall clock: 51.6 s

## Town A
- bytes p50 / p95 / max: 41227 / 43876 / 44710
- tick compute ms p50 / p95: 92.6 / 129.3
- projection ms p50 / p95: 0.33 / 0.38
- serialize ms p50 / p95: 0.31 / 0.35
- inter-frame ms p50 / p95: 195.1 / 236.8

## Town B
- bytes p50 / p95 / max: 42795 / 45379 / 46186
- tick compute ms p50 / p95: 92.2 / 130.1
- projection ms p50 / p95: 0.34 / 0.40
- serialize ms p50 / p95: 0.32 / 0.36
- inter-frame ms p50 / p95: 186.9 / 261.3

## Gate
- Town A: bytes p95 43876 (limit 61440, ok); overhead share of tick (p50) 0.7% (limit 10%, ok)
- Town B: bytes p95 45379 (limit 61440, ok); overhead share of tick (p50) 0.7% (limit 10%, ok)
- failing arms: []
- checks: {'bytesP95': True, 'overheadShare': True, 'equivalence': True}
- measured checks passed: True
- phase gate passed: True
- result: phase gate passed (exit 0)

## Equivalence with the headless smoke runner
| frame tick | session | smoke (tick-1) | match |
|---|---|---|---|
| 13 | 2.1 | 2.1 | True |
| 26 | 8.2 | 8.200000000000001 | True |
| 52 | 19.4 | 19.400000000000002 | True |
| 104 | 25.881168177240685 | 25.88116817724068 | True |
| 156 | 19.611848825331972 | 19.611848825331972 | True |
| 208 | 29.7741273100616 | 29.774127310061605 | True |
| 260 | 36.69724770642202 | 36.69724770642202 | True |
```

| Frame (2 x 1,000 households, 260 ticks, seed 1337) | Bytes p95, Town A | Bytes p95, Town B | Overhead share (p50) | Equivalence |
|---|---|---|---|---|
| before: run 1, every subject key for 40 households (what `legacy` sends at that sample size) | 186,587 | 188,160 | 1.9% | 7 of 7 |
| after: `lean` | 43,876 | 45,379 | 0.7% | 7 of 7 |

The lean p95 frame is about 76 percent smaller than before and at least 26 percent under the 61,440-byte budget. Serialization fell from about 1.45 ms to 0.31 ms per frame (p50), which accounts for nearly all of the drop in overhead share. The equivalence rows are identical to run 1's: in a run without CONFIG actions, such as this one, the profile changes only what is sent, never the economy or the session's random stream.

## Equivalence

| Frame tick | Session | Smoke (tick - 1) | Match |
|---|---|---|---|
| 13 | 2.1 | 2.1 | yes |
| 26 | 8.2 | 8.200000000000001 | yes |
| 52 | 19.4 | 19.400000000000002 | yes |
| 104 | 25.881168177240685 | 25.88116817724068 | yes |
| 156 | 19.611848825331972 | 19.611848825331972 | yes |
| 208 | 29.7741273100616 | 29.774127310061605 | yes |
| 260 | 36.69724770642202 | 36.69724770642202 | yes |

The live session path matched the headless smoke runner at every checkpoint in both 1,000-household runs (warehouse off and on); the remaining differences are floating-point rounding in the last digit. No server change was needed to align the two paths.

## Where the bytes go

A separate single-arm capture of the same world (1,000 households, 260 ticks, seed 1337, warehouse off) summed the encoded size of each key over every frame:

| Key | Mean bytes per frame | Share of mean frame |
|---|---|---|
| `metrics.trackedSubjects` (40 households) | 115,383 | 78.4% |
| of which `history` | 44,071 | 29.9% |
| of which `traits` | 15,215 | 10.3% |
| of which `recentEvents` | 14,978 | 10.2% |
| of which `expectedWageReason` | 13,369 | 9.1% |
| `firm_stats` | 9,392 | 6.4% |
| `metrics.trackedFirms` | 6,902 | 4.7% |
| `firms` | 6,153 | 4.2% |
| everything else | about 9,400 | 6.4% |

The mean frame was 147,235 bytes. Each tracked household's `history` holds five series sampled at tick 1 and every 25 ticks, so it grows through the run; `traits` does not change after SETUP. On the tick-260 frame (195,182 bytes), removing candidate payloads gives:

| Tick-260 frame variant | Bytes |
|---|---|
| as sent | 195,182 |
| without `history` (the plan's example: history only every 25 ticks) | 113,114 |
| also without `traits` and `expectedWageReason` | 82,594 |
| also without `recentEvents` | 64,220 |
| as the previous row, with floats rounded to 2 decimal places | 53,551 |
| without `trackedSubjects` at all | 39,182 |

Sending history only on sampling ticks is not enough on its own: the p95 frame would still be about 110 KB. Meeting 60 KB with 40 tracked households needs most of the per-household detail off the per-tick frame. The current dashboard reads `history` and `expectedWageReason` from every frame (`frontend-react/src/screens/Population.jsx`), so that is a protocol decision for phase 2 rather than a backend-only trim.
