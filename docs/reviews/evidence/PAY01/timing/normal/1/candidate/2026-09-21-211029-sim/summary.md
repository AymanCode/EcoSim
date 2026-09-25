# EcoSim Simulation Throughput Benchmark

## Runtime Context

- Commit: `4f69389`
- Python: `3.13.2`
- Platform: `macOS-27.0-arm64-arm-64bit-Mach-O`
- Logical CPUs: `10`

## Overall

- Ticks measured: `100`
- p50 tick latency: `90.604 ms`
- p95 tick latency: `126.981 ms`
- p99 tick latency: `129.814 ms`
- Throughput: `10.9663 ticks/sec`

## By Household Scale

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| 1000 | 100 | 90.604 | 126.981 | 129.814 | 10.9663 | 657.98 |

## By Tick Phase

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| full_private_market | 53 | 91.877 | 128.73 | 134.609 | 9.9762 | 598.57 |
| private_firm_ramp | 37 | 82.36 | 116.713 | 118.986 | 11.875 | 712.5 |
| warmup | 10 | 60.673 | 102.355 | 102.355 | 14.4841 | 869.05 |

## Evidence Summary

- The Python agent-based simulator was measured toward the 10k+ agents target at `1000` households, with p50/p95/p99 tick latency and `657.98` simulated weeks/minute at `126.981 ms` p95 tick latency on the recorded local environment.
- The harness records commit/runtime metadata, CSV/JSON outputs, and optional profiles so results can be compared and reproduced.
