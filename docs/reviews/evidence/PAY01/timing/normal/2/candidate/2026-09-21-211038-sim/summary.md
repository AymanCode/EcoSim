# EcoSim Simulation Throughput Benchmark

## Runtime Context

- Commit: `4f69389`
- Python: `3.13.2`
- Platform: `macOS-27.0-arm64-arm-64bit-Mach-O`
- Logical CPUs: `10`

## Overall

- Ticks measured: `100`
- p50 tick latency: `89.941 ms`
- p95 tick latency: `126.907 ms`
- p99 tick latency: `130.337 ms`
- Throughput: `10.9984 ticks/sec`

## By Household Scale

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| 1000 | 100 | 89.941 | 126.907 | 130.337 | 10.9984 | 659.91 |

## By Tick Phase

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| full_private_market | 53 | 90.874 | 129.388 | 132.61 | 10.0245 | 601.47 |
| private_firm_ramp | 37 | 81.904 | 117.8 | 118.81 | 11.8952 | 713.71 |
| warmup | 10 | 60.621 | 104.012 | 104.012 | 14.3959 | 863.75 |

## Evidence Summary

- The Python agent-based simulator was measured toward the 10k+ agents target at `1000` households, with p50/p95/p99 tick latency and `659.91` simulated weeks/minute at `126.907 ms` p95 tick latency on the recorded local environment.
- The harness records commit/runtime metadata, CSV/JSON outputs, and optional profiles so results can be compared and reproduced.
