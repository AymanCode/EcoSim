# W05 performance verification

**Completed 2026-09-21.** All four measured population/mode cells stayed within the proposed 5% median and p95 engine-tick budget. These are observed point estimates, not a statistical guarantee of a sub-5% difference on every workload.

Baseline was the frozen archive of `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`; candidate was the corrected working tree. Engine-file hashes, full configurations, per-tick timings, phases, counts, errors and source artifacts are retained in the [machine-readable report](evidence/ECONOMIC_CONCRETE_PERFORMANCE.json) and its eight linked raw JSON files.

| Mode | Households | Baseline median ms | Candidate median ms | Median change | Baseline p95 ms | Candidate p95 ms | p95 change |
|---|---:|---:|---:|---:|---:|---:|---:|
| normal | 1,000 | 86.82 | 90.34 | +4.05% | 126.61 | 128.12 | +1.20% |
| normal | 10,000 | 978.68 | 990.32 | +1.19% | 1441.84 | 1443.60 | +0.12% |
| performance | 1,000 | 32.73 | 32.44 | -0.88% | 120.28 | 119.47 | -0.67% |
| performance | 10,000 | 346.13 | 352.52 | +1.85% | 1320.43 | 1335.02 | +1.10% |

## Workload and variability

32 runs and 3,200 engine ticks were measured. Each run used 100 weekly ticks, 10 warmup ticks, and 10 initial firms per category via the existing public factory. Normal mode used seeds 42, 43 and 44, twice each at both 1,000 and 10,000 households. Performance mode used seed 42 twice at both scales. Both modes included recorded `full_private_market` ticks; the normal 1,000-household cases retained a small queued population, documented in the raw phase/count records. Performance mode changes economic planning cadence, so its levels are not presented as equivalent economic outcomes to normal mode.

The existing `run_sim_bench` harness measured engine step time, using nearest-rank percentiles. No heavy tests, builds or concurrent simulation workers ran during the timing windows. Routine source/document reads and edits continued. The hosted Fable review finished before candidate timing. Baseline and candidate were measured sequentially, not randomized/interleaved, so host drift is a limitation.

| Mode/version | Repeat median range, 1,000 households (ms) | Repeat median range, 10,000 households (ms) | Peak process RSS (MiB) |
|---|---:|---:|---:|
| normal:baseline | 85.04–90.54 | 959.08–1006.33 | 339.53 |
| normal:candidate | 89.89–90.90 | 986.99–994.85 | 339.47 |
| performance:baseline | 32.64–32.79 | 345.71–347.21 | 307.25 |
| performance:candidate | 31.97–32.61 | 349.15–355.43 | 303.31 |

The normal 1,000-household baseline medians differed by about 6.5% between repetitions, exceeding the proposed 5% budget. Candidate values overlap this variation. We therefore report the measured changes and the noise, without claiming to have isolated a precise implementation cost. At 10,000 households, the corrections also changed later firm counts (normal baseline final counts 201/206/204 by seed; candidate 207/198/203). Some runtime difference can reflect changed economic workload.

RSS is the existing harness’s macOS `ru_maxrss` high-water reading, not live per-population memory. The source variants showed no increase in peak process RSS in these matched run sequences. This does not establish a long-horizon memory bound.

The benchmark covers engine timing. It does not include optional comparison-evidence serialization, plotting, browser rendering, warehouse writes or provider calls. Those sidecar writes are outside `Economy.step`; comparison-runner functional checks verify their output and lack of economic/RNG effects.

## Reproduction

Use the project virtual environment and [benchmark_concrete_package.py](benchmark_concrete_package.py), passing either the Git archive directory or the candidate root. Each version runs separately. The original baseline job was stopped after two fully recorded normal-mode repetitions; an unfinished extra repetition has no results and is excluded.

```bash
.venv/bin/python docs/reviews/benchmark_concrete_package.py --source-root /path/to/baseline --output-root /tmp/baseline-normal
.venv/bin/python docs/reviews/benchmark_concrete_package.py --source-root . --output-root /tmp/candidate-normal
.venv/bin/python docs/reviews/benchmark_concrete_package.py --source-root /path/to/baseline --output-root /tmp/baseline-performance --performance-mode --seeds 42
.venv/bin/python docs/reviews/benchmark_concrete_package.py --source-root . --output-root /tmp/candidate-performance --performance-mode --seeds 42
```

The recording environment was Python 3.13.2 / NumPy 2.4.6 on macOS 27.0 arm64, with 10 logical CPUs. Full metadata and configuration live in each raw artifact. The summary can be regenerated with [summarize_concrete_performance.py](summarize_concrete_performance.py) using the recorded directory layout.
