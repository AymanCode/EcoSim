# Inflation implementation: performance evidence

## Result

The final implementation meets the existing 5% runtime budget on this measured workload. All four population/mode cells have upper paired bootstrap intervals below 5% for both median and p95 tick time. Negative changes mean faster measured execution; small changes can reflect noise and changed economic decisions.

| Households | Mode | Pairs | Median change (95% interval) | p95 change (95% interval) |
|---:|---|---:|---:|---:|
| 1,000 | normal | 15 | -0.38% [-2.11, +0.72] | +0.20% [-0.65, +1.24] |
| 1,000 | performance | 5 | -2.13% [-2.91, -1.99] | +0.50% [-1.59, +3.33] |
| 10,000 | normal | 5 | -0.42% [-0.83, -0.19] | -1.42% [-7.93, +0.07] |
| 10,000 | performance | 5 | +0.85% [-1.92, +3.00] | +0.39% [-4.24, +0.95] |

## Method and limits

- Baseline: pre-inflation working tree over `17d5c0b`, including the earlier household income timing correction. The saved baseline engine hash is in [baseline-manifest.json](baseline-manifest.json); [baseline-economy.patch](baseline-economy.patch) reconstructs that engine from the commit.
- Both arms use the current compatible agents/config. The added guard in the old wage-cut method is inactive in the baseline. The removed forced price escalator applies only with firm stabilizers disabled; stabilizers are enabled here. The new configuration defaults have no old-engine reader.
- Seed 1337, large-economy factory, five initial firms per category. Prepare 62 weeks with the baseline, then restore the same checkpoint, configuration and Python/NumPy RNG state in each independent worker. Detached price observations and review anchors in preparation let the timed continuation include annual reviews. Each worker measures 12 weeks, with normal garbage collection enabled after clearing deserialization garbage.
- Baseline/candidate process order alternates. Start with five pairs in every cell. The 1,000-household normal-mode p95 interval remained too wide at five and nine pairs, so that cell was extended to 15 pairs. Every sample, including outliers, is retained. Other cells remain at five pairs. No further performance sampling was needed.
- Calculate median and p95 within each worker, then the percentage change for each pair. Report the median paired change and a percentile interval from 10,000 paired bootstrap resamples (seed 937). These small, adaptively extended samples are a practical regression check, not a population-wide statistical guarantee. The raw per-week times are retained in [benchmark.json](benchmark.json).
- Source hashes identify the final engine, dependencies and benchmark. Tests were not run concurrently with these timing measurements. Results apply to this machine and continuation window; they do not establish five-year stability or empirical calibration.

### Runtime and memory

| Households | Mode | Median ms, before → after | p95 ms, before → after | Peak RSS MiB, before → after | Firms, initial → baseline / candidate final |
|---:|---|---:|---:|---:|---|
| 1,000 | normal | 80.03 → 79.87 | 115.87 → 116.73 | 78.52 → 78.94 | 30 → 30 / 30 |
| 1,000 | performance | 28.62 → 28.03 | 111.29 → 110.04 | 77.03 → 76.80 | 30 → 30 / 30 |
| 10,000 | normal | 944.38 → 939.30 | 1315.53 → 1302.03 | 356.83 → 357.39 | 148 → 140 / 145 |
| 10,000 | performance | 363.63 → 365.42 | 1243.58 → 1248.38 | 358.52 → 361.53 | 114 → 116 / 119 |

Times in this table are medians across workers. Their ratio need not equal the median paired percentage above. RSS is the median process peak, not an exact measure of added allocations. The candidate has five extra surviving firms in 10k normal and three in 10k performance; timing therefore includes a behaviorally different continuation, not only the isolated cost of calculating an index. Index history is bounded to 53 points by default, with previous quotes and review state proportional to live firms.

## Reproduce

From the repository root, reconstruct the baseline in a fresh temporary directory:

```bash
baseline_dir=$(mktemp -d)
git show 17d5c0bedf560d8deb7e76ba5615ceb2789eb24e:backend/economy.py > "$baseline_dir/economy.py"
patch "$baseline_dir/economy.py" < docs/evals/2026-09-28-inflation/baseline-economy.patch
.venv/bin/python docs/evals/2026-09-28-inflation/benchmark.py \
  --baseline "$baseline_dir/economy.py" --output "$baseline_dir/benchmark.json" --repeats 5
.venv/bin/python docs/evals/2026-09-28-inflation/benchmark.py \
  --baseline "$baseline_dir/economy.py" --output "$baseline_dir/benchmark.json" \
  --sizes 1000 --modes normal --repeats 15 --append
```

Use a fresh output directory to create fresh checkpoints. Run against the source hashes in the saved result to reproduce this implementation. The retained [benchmark-before-exit-cleanup.json](benchmark-before-exit-cleanup.json) describes an earlier engine revision; it is historical evidence and is not used for the final gate.
