Measured on `17d5c0b` plus the 2026-09-28 session's uncommitted change, not on the ported code. This folder was copied unchanged (apart from this line and the note below) when the change was ported onto the remediation code on 2026-09-29; the ported code's before/after runs are in [../2026-09-29-income-timing-port/](../2026-09-29-income-timing-port/README.md).

> Port note (2026-09-29): links to `../2026-09-28-agent-scenarios/` and the scenario runner (`backend/tools/checks/run_agent_scenarios.py`) resolve once part 2 of the port lands. The benchmark and fixed-state scripts compare `17d5c0b` with that session's engine; running them on a later engine measures that later engine.

# Income before shopping: verification

This directory records the September 28 correction to default household shopping timing. The behavior and accounting boundary are defined in the [change note](../../reviews/2026-09-28-household-income-timing.md).

## Behavior

The [small scenario report](scenarios/report.md) runs the public scenario CLI against the changed engine. Its JSON includes exact starting states, household/business traces and source hashes. Compare the complete-week payday row with the [pre-change report](../2026-09-28-agent-scenarios/report.md).

All **30/30 scenario checks** passed. The full backend suite reported **633 passed, 8 deselected, 1 expected failure**; the expected failure is the existing distressed three-worker firm's layoff floor. Ruff and diff whitespace checks passed. The final engine hash matches both the scenario evidence and the performance records.

Run the same cases from the repository root:

```bash
.venv/bin/python -m backend.tools.checks.run_agent_scenarios \
  --output-dir benchmarks/results/household-income-timing
.venv/bin/python -m pytest backend/tests_contracts/test_household_income_timing.py
```

## Performance method

Baseline source is `backend/economy.py` from commit `17d5c0b`. The candidate is identified by its SHA-256 in `benchmark.json`; agents, configuration and the world factory are held fixed. The baseline manifest records the workload declared before the core edits.

Each independent subprocess seeds Python and NumPy with 1337 and builds the same baseline economy for 40 weeks. It then runs either the baseline or candidate engine for 12 measured weeks. The workload uses 1,000 or 10,000 households and normal or performance mode. Five baseline/candidate pairs are interleaved per cell, with order reversed on alternating pairs. Inconclusive cells receive additional pairs; every original observation is retained.

Reported median and p95 times are medians of the corresponding per-run statistic. Percentage changes use paired run ratios. The 95% ranges bootstrap those paired ratios 10,000 times with seed 937. The p95 estimates describe this short twelve-week workload, which includes periodic full planning; they are not a general long-run latency guarantee. Peak process RSS includes development/warmup. Engine measurements do not include browser rendering.

Each pair starts from the same developed world. Economic trajectories can diverge during the measurement window because income timing changes purchases, sales and later business decisions. Initial and final firm counts are recorded to make that workload difference visible. These measurements assess the integrated change; they do not isolate pure instruction cost or establish economic calibration.

The project working limit is at most 5% added median and p95 tick time, including the uncertainty range, in each cell. It is an engineering threshold, not a percentage supplied by Ayman.

## Reproduce

Extract the old engine to a temporary file, then run the saved measurement script with the repository's Python environment:

```bash
git show 17d5c0b:backend/economy.py > /tmp/ecosim-before-household-income.py
.venv/bin/python docs/evals/2026-09-28-household-income-timing/benchmark.py \
  --baseline /tmp/ecosim-before-household-income.py \
  --output /tmp/ecosim-household-income-benchmark.json
```

Use the recorded candidate source and dependency hashes when reproducing these numbers. Running against a later engine measures that later engine. To extend an inconclusive cell while retaining its samples:

```bash
.venv/bin/python docs/evals/2026-09-28-household-income-timing/benchmark.py \
  --baseline /tmp/ecosim-before-household-income.py \
  --output /tmp/ecosim-household-income-benchmark.json \
  --append --sizes 1000 --modes performance --repeats 9
```

The reproduction script reformats the original measurement driver and adds checkpointing, source guards and selective continuation. Its warmup, timing, workload and bootstrap calculations are the same.

## Measured engine timing

Five pairs were sufficient in three cells. The 1,000-household performance cell was extended to nine pairs because an original sample had a large latency spike. All original samples remain in `benchmark-initial.json` and `benchmark.json`.

| Households | Mode | Pairs | Median ms, before → after | Paired median change (95% range) | p95 ms, before → after | Paired p95 change (95% range) |
| --- | --- | --- | --- | --- | --- | --- |
| 1,000 | normal | 5 | 84.83 → 78.82 | -5.80% [-9.07, +3.40] | 117.99 → 111.11 | -5.86% [-6.04, -3.06] |
| 1,000 | performance | 9 | 28.89 → 25.52 | -10.64% [-13.04, -10.20] | 112.39 → 106.96 | -3.98% [-5.70, -2.38] |
| 10,000 | normal | 5 | 954.69 → 886.39 | -6.98% [-11.35, -5.29] | 1325.40 → 1238.67 | -6.98% [-12.34, -2.47] |
| 10,000 | performance | 5 | 345.26 → 342.19 | -0.86% [-2.08, -0.47] | 1181.40 → 1179.65 | -0.06% [-2.42, +0.99] |

All four cells are within the declared 5% engineering budget for both statistics, including their bootstrap ranges. Their point estimates show no added tick time. These are workload-specific observations, not a guarantee for every population, configuration or machine.

| Households | Mode | Peak RSS MiB, before → after | Initial firms | Final firms, before → after |
| --- | --- | --- | --- | --- |
| 1,000 | normal | 73.28 → 73.86 | 29 | 30 → 30 |
| 1,000 | performance | 72.23 → 72.16 | 30 | 30 → 30 |
| 10,000 | normal | 273.78 → 283.14 | 251 | 199 → 188 |
| 10,000 | performance | 269.17 → 273.98 | 239 | 181 → 145 |

At 10,000 households, peak process memory increased by about 9.36 MiB in normal mode and 4.81 MiB in performance mode. New cached fields grow linearly with households. The difference also includes changed economic state; RSS does not isolate cache size.

The changed business survival counts are a reason to follow up with economic calibration. A favorable runtime measurement does not establish that those outcomes are desirable.

## Fixed-state check and memory-cleanup diagnosis

Because business counts diverged in the 10,000-household runs, a supplementary check starts each measured step from an identical copy of the baseline town at weeks 40 and 41. These cover a full shopping refresh and an intermediate cached week. Python and NumPy random states are restored before each step. Copying and warmup are outside the timed region.

The first version, preserved in `fixed-state-with-copy-gc.json` and `fixed_state_benchmark_initial.py`, reported about 7.6% overhead on the full performance-mode refresh. Its docstring said garbage collection was excluded, but that was only true of the explicit collection before timing: automatic collection still ran inside the measured step.

Instrumentation with `gc.callbacks` found the cause. In three repeated full-refresh pairs, baseline cyclic garbage collection took 26–28 ms, while the candidate took 148–153 ms, including one generation-2 collection of about 120–124 ms. Both the original town and its large copied object graph were live. After subtracting the measured collection pauses, candidate decision time was slightly lower in each pair. Raw callback timings are in `gc-probe.json`.

The revised supplementary measurement disables cyclic garbage collection only during each timed step to isolate decision cost from copied-graph cleanup. This is a diagnostic measurement, not the production performance gate. The primary independent-process runs above retain ordinary garbage collection and remain the evidence for integrated simulation latency. No production garbage-collection setting changed.

```bash
.venv/bin/python docs/evals/2026-09-28-household-income-timing/fixed_state_benchmark.py \
  --baseline /tmp/ecosim-before-household-income.py \
  --output /tmp/ecosim-fixed-state.json
```

| Mode | Week | Initial firms | Decision ms, before → after | Paired change (95% range) |
| --- | --- | --- | --- | --- |
| normal | 40 | 251 | 1180.08 → 1147.44 | -2.98% [-3.33, -2.56] |
| normal | 41 | 248 | 859.03 → 823.27 | -4.22% [-5.07, -2.41] |
| performance | 40 | 239 | 1129.21 → 1105.63 | -2.16% [-2.60, -0.68] |
| performance | 41 | 238 | 297.14 → 302.31 | +0.63% [-18.11, +2.18] |

The fixed-state checks support bounded decision cost: full planning was faster, while cached-week budget updates had a small positive point estimate. All upper ranges were below 5%. An unusually slow baseline cached-week sample is retained in the raw observations and widens that diagnostic interval.
