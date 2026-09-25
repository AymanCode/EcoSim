# EcoSim Simulation Throughput Benchmark

## Runtime Context

- Commit: `4f69389`
- Python: `3.13.2`
- Platform: `macOS-27.0-arm64-arm-64bit-Mach-O`
- Logical CPUs: `10`

## Overall

- Ticks measured: `100`
- p50 tick latency: `36.248 ms`
- p95 tick latency: `126.374 ms`
- p99 tick latency: `131.715 ms`
- Throughput: `21.2099 ticks/sec`

## By Household Scale

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| 1000 | 100 | 36.248 | 126.374 | 131.715 | 21.2099 | 1272.59 |

## By Tick Phase

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| full_private_market | 11 | 37.744 | 126.374 | 126.374 | 18.4364 | 1106.18 |
| private_firm_ramp | 79 | 36.126 | 129.081 | 132.842 | 20.5594 | 1233.56 |
| warmup | 10 | 10.85 | 102.896 | 102.896 | 36.2846 | 2177.08 |

## Evidence Summary

- The Python agent-based simulator was measured toward the 10k+ agents target at `1000` households, with p50/p95/p99 tick latency and `1272.59` simulated weeks/minute at `126.374 ms` p95 tick latency on the recorded local environment.
- The harness records commit/runtime metadata, CSV/JSON outputs, and optional profiles so results can be compared and reproduced.
