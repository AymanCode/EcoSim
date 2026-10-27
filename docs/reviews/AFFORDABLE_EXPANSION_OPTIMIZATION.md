# Final bounded household optimization validation

**Declared measurements complete; economic replay passed with the source-path fingerprint qualification below. Integrated 5% performance acceptance remains inconclusive.** Every fresh macro point estimate is below 1.05, but this panel has one timing realization per seed and only one 10k seed. No further optimization or economic tuning was performed.

## Frozen scope and sources

Validation started clean on `codex/services-affordable-expansion`, docs HEAD `091176931e555bda44e4c018bf356deca3fc5ef7`. Verified local `origin/main` at `d71485e7276cb2bf988eee6ff8ae9ecada3b73be`, 12 ahead / 0 behind; the parent supplied the fresh fetch. Backend content at HEAD equals O3. PR66 remains untouched. This worker edits only this report; the parent owns review and commit.

Rules v1.17, product intent, the ecosim-firm-design skill and [selected contract](AFFORDABLE_EXPANSION_CONTRACT.md) govern this validation. Wiki navigation covered quickstart, ownership, agents/markets and testing/performance. The [original results](AFFORDABLE_EXPANSION_RESULTS.md), including its subsequent optimization section, and the household/financing reports remain frozen historical evidence.

| Arm | Exact committed source | Python files | Source-manifest SHA256 |
| --- | --- | --- | --- |
| B | `cca042a939214d882d6a130d711b8274d1f2a102` | 198 | `d10702198cd2d62ebbc1e3861b2dbe21c5a4dddb3b1041e4a8075e80894c2aeb` |
| F | `72c486374e1529767a20ab82333ed130b85f4345` | 199 | `20d2c5fd2f928be342474391d9f110a7a6c67ce8de4de6107cd2264b78c5ae04` |
| HF | `236773134e2a47664ee5806a9d611c139be1ca97` | 200 | `2f40f14f43664880f3fa52bbfd880b809fd3d7a63bcb09ec15b51b0813299d65` |
| O3 | `785d326b713970a89af8bb4976012bc3ec274880` | 200 | `36ee8abd942966709745b701683db5ac039af015c81beb83b5589dc606daca06` |

The independent checker compared every manifest file to its frozen bytes and to `git archive` of the exact commit. O3 skips the funded-envelope lookup/general formula only for immutable zero subsidy share, and omits fully fulfilled private quote records. Positive-share logic, buyers/sellers, payments, shortage signals, RNG and cadence retain the selected behavior. The EPS correction is exactly `qty <= EPS or qty < fundable`.

Earlier O/O2 snapshots are intermediate/rejected evidence. Round 1 found the wanted `1.5e-6` / stock `0.75e-6` shortage edge; O3 includes its 12 regressions. Parent-recorded final evidence is 135 selected passes and 2400 exact market comparisons; independent round 2 records 30 sector passes and 1800 exact comparisons. These overlapping counts are not summed and were not rerun here. The retained `zero-subsidy/equivalence.json` and external fastpath script preserve the parent evidence.

## Functional gate and executed inventory

Before heavy timing, verified completion of the parent's final O3 full-suite log: **1333 passed, 2 skipped, 8 research deselected, 1 xfailed, 1 third-party warning in 207.78s** (WSL Ubuntu24.04 / Python3.12.3). This worker did not launch a duplicate suite. Log SHA256: `bbfa16112380dc11b3ac3a36254c04e48dcdd52f1b173cf836c86477ec6de1cd`. The older O2 1321-pass log does not certify O3; the original HF log remains unchanged.

The protocol was declared before final timing in `zero-subsidy/protocol.json`. Execution used the root CPython3.11.9 Windows interpreter on Ryzen9 3900X / Windows build26200, sequential workers, normal mode and no concurrent validation workload. Engine timers surround only actual `Economy.step()`; restore/fingerprint/observation and native memory collection are outside timers.

- **32 completed cost blocks / 160 timed steps:** B/F/HF/O3, both scenarios, four alternating blocks, five restored trials per block. Reused the validated 3,784,911-byte B week40 checkpoint with its 4000 read-only arrays, alias/cache/CONFIG checks and pre-state fingerprint; no capture or dependency installation.
- **16 fresh macro runs / 1280 ticks:** B/O3, both named sequences, 1k seeds42/43/44 and 10k seed42, 80 ticks, warmup10, alternating pair order. Exact key set, unique cases, all tick sequences, finite fields, evaluator hashes and source manifests independently verified. All 16 cases match every historical model row and final RNG: fresh B -> old B; O3 -> old HF. Only `engine_ms` is excluded from row equality; memory is outside the rows. Initial profile/RNG/config also match historical runs and paired arms. Initial-profile hashing is not a complete initial-state checkpoint.
- Every macro tick has absolute clearing cash below `1e-6` and bank/holds-inclusive injection-adjusted cash residual below `0.001`; maxima **1.90775608644e-08** and **0.000110030174255**. This is the declared cash-stock perimeter, not proof of all claims or universal conservation.

### Fingerprint qualification and interruption

The originally requested raw cross-arm post-state hashes **do not match**. On first independent comparison, the driver was stopped before macro timing. An untimed HF/O3 replay and complete recursive state-tree comparison found exactly four differing leaves: `co_filename` strings in unchanged `payments.py` default-factory code, pointing to the respective frozen HF/O3 source directories. No values, bytecode, defaults, arrays, aliases or other leaves differed. The raw fingerprints and trees are preserved, not rewritten.

After this diagnosis the unchanged driver resumed its completed blocks; one interrupted rich-B block had no result artifact and was excluded. Its partial step count was not recoverable. No completed result block was discarded or rerun. After all macro timing, separate rich HF/O3 replays found the same four path-only differences. Replacing only those verified source-root strings gives exact tree equality in both scenarios. Each diagnostic raw tree reproduces the corresponding raw hash in all four completed cost blocks. All recorded HF/O3 outcomes and RNG match exactly in both scenarios. Thus logical state equality is established with an explicit pathname qualification, rather than claiming literal raw-hash equality.

There were four successful separate untimed diagnosis steps and one failed diagnostic restore before any step (the wrapper initially omitted `__main__.restore_factory`, then supplied it). No profile timing is pooled and no additional optimization pass occurred. `diagnose_fingerprint.py`, full trees, `fingerprint-differences.json`, stop-process receipt and normalized checks in `analysis.json` retain this evidence.

## Fresh integrated runtime

Completed weeks41-80; median and nearest-rank p95 of each run's 40 engine timings, milliseconds. Ratios compare fresh O3 with its fresh B pair, not historical runtimes.

| Sequence | HH | Seed | B p50 / p95 | O3 p50 / p95 | O3/B p50 / p95 |
| --- | --- | --- | --- | --- | --- |
| income_first | 1,000 | 42 | 372.52 / 436.75 | 371.61 / 446.29 | 0.998 / 1.022 |
| income_first | 1,000 | 43 | 372.91 / 441.79 | 375.94 / 447.59 | 1.008 / 1.013 |
| income_first | 1,000 | 44 | 374.49 / 440.99 | 380.02 / 459.45 | 1.015 / 1.042 |
| income_first | 10,000 | 42 | 4272.30 / 5185.95 | 4123.04 / 5250.57 | 0.965 / 1.012 |
| income_late | 1,000 | 42 | 361.07 / 433.93 | 374.90 / 444.32 | 1.038 / 1.024 |
| income_late | 1,000 | 43 | 384.33 / 463.18 | 371.49 / 456.28 | 0.967 / 0.985 |
| income_late | 1,000 | 44 | 369.67 / 468.41 | 379.25 / 453.09 | 1.026 / 0.967 |
| income_late | 10,000 | 42 | 4192.15 / 5236.18 | 4170.53 / 5130.80 | 0.995 / 0.980 |

Equal-weight means of the three 1k per-run ratios are **1.007 / 1.026** for income_first and **1.010 / 0.992** for income_late. These are descriptive means, not pooled quantiles or independent-repeat confidence intervals. **All four sequence/population cells are inconclusive for acceptance, with within-target observed point estimates.** Seeds change economic workloads; no independent timing-repeat interval exists, and each 10k cell has only one seed. Fresh results are more favorable than historical HF timing, but across-session historical differences cannot isolate an optimization speedup.

## Common-state processing cost

Twenty restored trials per row; block medians expose temporal variation. Rich assigns each household cash1,000,000 identically as a cost diagnostic, not macro calibration. HF/O3 outcomes are exactly equal in both scenarios; F/O3 recorded outcomes also match exactly in the rich scenario. Unconditioned B/F differ in expansion/activity, so their whole runtime difference cannot be called household bookkeeping.

| Scenario | Arm | p50 / p95 ms | Four block medians ms |
| --- | --- | --- | --- |
| Unconditioned | B | 420.20 / 449.98 | 424.79, 418.97, 419.39, 423.35 |
| Unconditioned | F | 435.57 / 461.71 | 436.32, 450.33, 428.35, 432.23 |
| Unconditioned | HF | 467.75 / 508.83 | 479.34, 464.14, 466.88, 464.45 |
| Unconditioned | O3 | 442.03 / 490.87 | 463.45, 452.06, 428.52, 428.66 |
| Artificial rich | B | 396.03 / 420.63 | 393.97, 394.48, 408.61, 395.32 |
| Artificial rich | F | 397.54 / 417.74 | 410.36, 397.26, 395.02, 395.23 |
| Artificial rich | HF | 454.71 / 501.91 | 456.04, 455.09, 454.34, 448.58 |
| Artificial rich | O3 | 417.90 / 446.51 | 425.07, 415.91, 418.06, 425.17 |

At unchanged HF outcomes, O3 saves **25.72ms median /17.96ms p95** unconditioned and **36.81ms /55.40ms** rich. Rich O3 still costs **20.36ms median /28.77ms p95 above F**, ratios **1.051 /1.069**; against B it is **1.055 /1.062**. Unconditioned O3/F is **1.015 /1.063**, O3/B **1.052 /1.091**. These residuals remain visible even though the fresh integrated macro ratios are below1.05. Four alternating blocks on one checkpoint are not independent towns or representative 10k acceptance evidence. No unconditional 5% pass follows from either experiment.

## Memory, economics and handoff

Native macro snapshots, MiB; ranges cover the three 1k seeds or the single 10k seed across both sequences. All individual paired bytes remain in `analysis.json`.

| HH | Arm | Final working set | Process peak working set | Private bytes |
| --- | --- | --- | --- | --- |
| 1,000 | B | 68.52-69.74 | 68.67-70.22 | 792.77-795.11 |
| 1,000 | O3 | 69.26-70.69 | 69.74-70.70 | 793.92-795.52 |
| 10,000 | B | 322.43-322.86 | 323.52-323.58 | 1047.18-1048.26 |
| 10,000 | O3 | 326.68-326.86 | 327.30-327.47 | 1051.43-1052.32 |

Fresh paired O3 final working set is about0.74-1.50MiB higher at1k and3.83-4.43MiB higher at10k. These process snapshots include runtime, retained 80 observation rows and allocator retention; process peak includes initialization. Private bytes and working set measure different perimeters. This is not Python-heap attribution, proof of a memory leak, or an HF->O3 memory-saving measurement. Original macro memory was null and cannot supply that comparison. No numeric memory ceiling was selected.

There is **no new economic benefit from O3**: exact replay retains the original combined mechanism's GDP, Services quantities/access, employment, paid wages, debt/arrears, prices, happiness and health. The [original results](AFFORDABLE_EXPANSION_RESULTS.md) remain the economic interpretation: strong1k financing-driven output/jobs gains coexist with mixed10k access/wellbeing effects. New lending/interest fields cover all borrowers, not Services-only lending. More GDP, lending or Services units does not imply universal welfare improvement.

Remaining household work is O(H + existing order visits), including current-resource affordability and fundable-shortage allocation. Sparse tick-local records reduce constant work without reducing decisions; their bound remains O(H + orders). Financing quotes retain constant-time field/arithmetic work and existing indexed underwriting. No behavior/cadence reduction is proposed. Parent review/adoption of equivalent O3 is separate from acceptance of the cumulative performance budget; any further performance tradeoff needs new owner direction. This bounded pass stops here.

## Retained evidence

External root: `C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/`. New results/analysis/diagnosis are under `affordable-expansion-panel/zero-subsidy/`; original28 cases and all **1034 original artifact hashes** were independently reverified unchanged. Original manifest remains SHA256 `64680c93be42d3e7d76cb988fcd7329264714d8818f0f3f22e264047c0d38137`.

| Final artifact | SHA256 |
| --- | --- |
| `zero-subsidy/analysis.json` | `0cfd8f261210bd6f6e926f9f4f0f930d32ddb3e82b2a58e87274d4f9538d72b8` |
| `affordable_expansion_optimized_panel.py` | `865e62cc30cb0a303019cd74acf8a65f166f8218ca9a8c6d5a97dc8d2f75f4e8` |
| `affordable_expansion_optimized_cost_probe.py` | `5c00c1590a78aedee5a77e5a95b1b881a2fb59e02594ff635d90a12afba8b1b6` |

`zero-subsidy/artifact-hashes-final.json` separately hashes final sources, protocol, evaluators, results, diagnosis, review inputs, equivalence evidence, full-test receipt and this report. It excludes itself and pycache. No production, tests, rules, other repository docs, agents, PR, push, merge or memory writes were performed. Generated OpenWiki remains untouched; approved tooling is unavailable and refresh remains due. No credential request or workflow was started.
