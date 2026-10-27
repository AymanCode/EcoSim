# AFFORDABLE-EXPANSION-01 macro and performance validation

Validation complete for the declared 28-case panel; **integrated performance acceptance remains open**. This is bounded simulator evidence, not a redesign, calibration, release approval, or universal welfare claim. No production/test/shared-rule changes, cadence reductions, new mechanisms, network service calls, other agents, PR changes, push or merge were performed by this validation worker.

## Snapshot and evidence boundary

Started clean on `codex/services-affordable-expansion`, docs HEAD `468c2dcd06a509282f10f5b5b2636ca50c081887`. The local `origin/main` reference was `d71485e7276cb2bf988eee6ff8ae9ecada3b73be`, with HEAD 7 ahead / 0 behind; no remote refresh was attempted under the no-network instruction. Current backend content equals combined snapshot `236773134e2a47664ee5806a9d611c139be1ca97`. PR 66 remains baseline `cca042a`; no PR action was taken.

| Arm | Frozen committed source | Meaning |
| --- | --- | --- |
| B | `cca042a939214d882d6a130d711b8274d1f2a102` | PR 66 control |
| H | `7f9bf642b92c50f91415e01da6ebb07640ad2dc8` | household change alone |
| F | `72c486374e1529767a20ab82333ed130b85f4345` | Services financing alone |
| HF | `236773134e2a47664ee5806a9d611c139be1ca97` | combined production |

Rules v1.17, product intent and the [selected contract](AFFORDABLE_EXPANSION_CONTRACT.md) govern interpretation. Wiki-first navigation covered quickstart, ownership routes, agents/markets, tick lifecycle and testing/performance; generated wiki text is not authority for the new behavior. The household and finance reports preserve source/functional-review evidence. This worker did not rerun their tests: parent records 338 integrated focused passes, then the full WSL/Python 3.12.3 default backend gate **1321 passed, 2 skipped, 8 research deselected, 1 xfailed, 1 third-party warning**, 211.08s. Verified retained full-log SHA256: `c41c5fd4114d2992359d038c89f65bf4524e024e5224da37d73c6feaba7e81cc`. Parent-provided independent review evidence was 246 household tests +1600 market diagnostics +4 five-week live-planner cases, and 125 finance tests +4 real-claim cases; parent finance regressions 48. These counts overlap and are not added. No golden was changed.

## Completed panel and integrity

The inherited sequential driver was kept running without a duplicate or simultaneous heavy benchmark. **28/28 successful cases, 2240/2240 completed ticks, 0 failed simulation cases, 0 missing/duplicate cases**: each named sequence has 12 factorial 1k cases (seeds 42/43/44, B/H/F/HF) and 2 10k cases (seed 42, B/HF). Every run used normal mode,80 ticks,warmup 10, factory firms argument 10, one realization per seed. Engine wall time surrounds only actual `Economy.step()`; observers run afterward without replanning. Late windows below are completed weeks 41-80, with equal seed weights at 1k. Hardware/runtime: Ryzen 9 3900X, Windows build 26200, CPython 3.11.9; engine only, excluding UI/server/warehouse latency.

Independent analysis required the exact 28-case key set before writing final results, verified all 80-row tick sequences and finite numeric rows, worker hashes, immutable source manifests/files (B 198/H 199/F 199/HF 200 Python files), and initial profile/RNG/config equality in all 8 matched groups. Separate provenance imports resolve 18 source modules per arm inside their selected frozen backend. All 8 available prior SERVICES-02 control endpoints reproduced 7 shared fields within 1e-7. The initial-profile hash covers the declared sampled actor/firm fields; it is not a complete checkpoint hash.

Every tick passed clearing-cash <1e-6 and bank/holds-inclusive injection-adjusted cash drift <0.001; maxima were **1.90775608644e-08** and **0.000110030174255** model currency respectively. This perimeter includes households, active/queued firms, treasury, miscellaneous pool, bank cash and all declared payment holds; deposit claims are not counted a second time. It is a measured cash-stock reconciliation, not proof of every financial claim or a general conservation theorem.

The two old evaluator-v1 pilots (160 historical ticks) remain in `pilot-v1/` and are excluded. They used current-firm last revenue as GDP. The current evaluator instead reports published nominal GDP as `sum(last_tick_revenue.values())` and keeps the old proxy under `firm_revenue_sum`. Corrected 1k income_first seed 42 B/F pilots were reused economically; their timings cannot be claimed as strictly isolated because focused author/review work may have overlapped.

## Economic results

Units are simulator quantities/currency. Access counts households with any positive Services purchase, so quantity and breadth can move differently. Price is the unweighted mean posted Services quote after the tick, not a paid-price index or household CPI. Wage income is the paid gross wage ledger, including released CEO pay and arrears receipts; it is not net disposable income. Slots, workers and firm cash/debt/arrears include baseline and private Services providers. **B/F shortage signals are raw unmet intentions; H/HF signals are fundable residual stockouts.** Their levels are not interchangeable measures of latent need; hardship persists even when an unfundable order produces zero market signal.

### income_first

Late-window means:

| HH | Arm | Nominal GDP | Price | Services units | Private shortage signal | Access | Workers/slots | Jobs | Paid wages | Happy | Health |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1,000 | B | 24,419 | 32.85 | 233.7 | 1,745.4 | 951.6 | 63.0/68.3 | 340.9 | 15,945 | 0.503 | 0.729 |
| 1,000 | H | 27,418 | 32.82 | 234.5 | 1,777.1 | 887.5 | 63.0/68.3 | 367.7 | 17,428 | 0.503 | 0.776 |
| 1,000 | F | 32,329 | 28.90 | 458.9 | 1,963.4 | 991.4 | 122.7/131.4 | 425.2 | 20,361 | 0.542 | 0.773 |
| 1,000 | HF | 32,947 | 29.08 | 463.1 | 1,971.7 | 950.0 | 123.7/135.8 | 432.4 | 20,666 | 0.537 | 0.781 |
| 10,000 | B | 665,465 | 76.76 | 7,170.8 | 9,378.7 | 9,830.9 | 1,874.9/2,129.3 | 5,380.2 | 473,089 | 0.438 | 0.646 |
| 10,000 | HF | 669,641 | 78.60 | 7,281.0 | 9,396.0 | 9,519.8 | 1,879.0/2,135.6 | 5,430.0 | 476,560 | 0.436 | 0.654 |

Late-window financial state; new lending and interest are cumulative weeks 1-80, averaged across the three 1k seeds. The bank telemetry covers **all borrowers**, not Services-only lending; registered lending may include distinct ledger funders, while interest is the bank-recipient series. Services Treasury debt is the separate firm mirror, not new fallback financing introduced by this change. Full loan-book exposure/defaults and borrower splits were not recorded by this panel.

| HH | Arm | Services cash | Services bank debt | Services Treasury debt | Wage arrears | Bank cash | All new lending | Bank interest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1,000 | B | 400,548 | 1,551 | 226,152 | 0 | 4,280,956 | 38,985 | 688 |
| 1,000 | H | 400,477 | 1,551 | 226,009 | 0 | 4,293,150 | 28,541 | 527 |
| 1,000 | F | 91,971 | 5,361 | 250,194 | 366 | 4,536,029 | 48,930 | 815 |
| 1,000 | HF | 91,099 | 6,632 | 249,808 | 395 | 4,544,041 | 39,304 | 657 |
| 10,000 | B | 1,522,055 | 972,870 | 581,553 | 116,419 | 44,991,943 | 2,209,351 | 42,052 |
| 10,000 | HF | 1,335,067 | 901,377 | 578,989 | 118,489 | 45,110,884 | 1,936,229 | 36,014 |

Per-seed week 80 endpoints (all other endpoint fields are retained in `analysis.json` and raw cases):

| HH | Seed | Arm | Nominal GDP | Services units | Jobs | Happy | Health |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1,000 | 42 | B | 18,670 | 232.0 | 275 | 0.386 | 0.581 |
| 1,000 | 42 | H | 26,153 | 234.5 | 341 | 0.403 | 0.719 |
| 1,000 | 42 | F | 27,901 | 411.6 | 364 | 0.460 | 0.718 |
| 1,000 | 42 | HF | 31,024 | 412.1 | 384 | 0.458 | 0.725 |
| 1,000 | 43 | B | 20,309 | 214.5 | 306 | 0.409 | 0.624 |
| 1,000 | 43 | H | 25,836 | 213.9 | 352 | 0.425 | 0.718 |
| 1,000 | 43 | F | 31,902 | 482.9 | 431 | 0.505 | 0.725 |
| 1,000 | 43 | HF | 33,120 | 487.7 | 446 | 0.504 | 0.730 |
| 1,000 | 44 | B | 20,569 | 230.4 | 292 | 0.407 | 0.622 |
| 1,000 | 44 | H | 26,914 | 232.3 | 355 | 0.417 | 0.728 |
| 1,000 | 44 | F | 31,393 | 465.2 | 397 | 0.475 | 0.728 |
| 1,000 | 44 | HF | 35,610 | 557.4 | 426 | 0.469 | 0.736 |
| 10,000 | 42 | B | 723,002 | 8,263.5 | 5,311 | 0.407 | 0.631 |
| 10,000 | 42 | HF | 730,965 | 8,638.5 | 5,384 | 0.404 | 0.632 |

### income_late

Late-window means:

| HH | Arm | Nominal GDP | Price | Services units | Private shortage signal | Access | Workers/slots | Jobs | Paid wages | Happy | Health |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1,000 | B | 25,514 | 32.28 | 269.2 | 1,974.0 | 958.9 | 70.4/76.2 | 353.6 | 16,655 | 0.505 | 0.735 |
| 1,000 | H | 25,483 | 32.30 | 269.2 | 1,971.7 | 959.1 | 70.4/76.2 | 352.9 | 16,613 | 0.504 | 0.734 |
| 1,000 | F | 32,953 | 28.88 | 478.4 | 1,963.2 | 987.3 | 127.7/136.6 | 432.6 | 20,684 | 0.538 | 0.773 |
| 1,000 | HF | 32,918 | 28.88 | 476.8 | 1,963.1 | 987.2 | 127.4/136.3 | 431.8 | 20,653 | 0.539 | 0.773 |
| 10,000 | B | 668,771 | 77.26 | 7,294.9 | 9,389.7 | 9,761.8 | 1,886.7/2,151.6 | 5,399.8 | 475,114 | 0.429 | 0.639 |
| 10,000 | HF | 668,783 | 76.96 | 7,332.7 | 9,264.1 | 9,763.6 | 1,890.6/2,133.4 | 5,398.1 | 472,218 | 0.428 | 0.639 |

Late-window financial state; new lending and interest are cumulative weeks 1-80, averaged across the three 1k seeds. The bank telemetry covers **all borrowers**, not Services-only lending; registered lending may include distinct ledger funders, while interest is the bank-recipient series. Services Treasury debt is the separate firm mirror, not new fallback financing introduced by this change. Full loan-book exposure/defaults and borrower splits were not recorded by this panel.

| HH | Arm | Services cash | Services bank debt | Services Treasury debt | Wage arrears | Bank cash | All new lending | Bank interest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1,000 | B | 396,028 | 6,444 | 220,402 | 0 | 4,268,960 | 42,128 | 823 |
| 1,000 | H | 396,017 | 6,444 | 220,399 | 0 | 4,268,171 | 42,568 | 828 |
| 1,000 | F | 94,826 | 6,993 | 251,092 | 395 | 4,513,641 | 48,373 | 795 |
| 1,000 | HF | 94,557 | 6,832 | 250,870 | 385 | 4,514,263 | 47,685 | 787 |
| 10,000 | B | 1,546,259 | 1,003,510 | 585,303 | 133,397 | 44,719,616 | 1,980,765 | 39,529 |
| 10,000 | HF | 1,392,711 | 937,692 | 574,541 | 112,150 | 44,784,602 | 1,958,325 | 37,664 |

Per-seed week 80 endpoints (all other endpoint fields are retained in `analysis.json` and raw cases):

| HH | Seed | Arm | Nominal GDP | Services units | Jobs | Happy | Health |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1,000 | 42 | B | 19,570 | 232.0 | 290 | 0.381 | 0.597 |
| 1,000 | 42 | H | 20,247 | 232.2 | 295 | 0.380 | 0.595 |
| 1,000 | 42 | F | 27,793 | 408.7 | 364 | 0.449 | 0.709 |
| 1,000 | 42 | HF | 28,525 | 406.9 | 367 | 0.448 | 0.709 |
| 1,000 | 43 | B | 26,712 | 389.6 | 368 | 0.442 | 0.668 |
| 1,000 | 43 | H | 26,716 | 389.5 | 365 | 0.441 | 0.668 |
| 1,000 | 43 | F | 33,124 | 533.4 | 443 | 0.513 | 0.726 |
| 1,000 | 43 | HF | 32,491 | 538.2 | 439 | 0.513 | 0.725 |
| 1,000 | 44 | B | 20,997 | 228.7 | 301 | 0.408 | 0.629 |
| 1,000 | 44 | H | 21,428 | 228.7 | 304 | 0.406 | 0.625 |
| 1,000 | 44 | F | 32,356 | 529.9 | 407 | 0.476 | 0.729 |
| 1,000 | 44 | HF | 32,819 | 527.5 | 422 | 0.477 | 0.729 |
| 10,000 | 42 | B | 717,341 | 8,470.9 | 5,294 | 0.392 | 0.616 |
| 10,000 | 42 | HF | 736,205 | 8,814.2 | 5,413 | 0.389 | 0.617 |

Interpretation must consider both scale and counterparties. In the 1k reference sequence, financing drives most of the Services output/staffing gain; the household fix alone improves employment/health while Services output stays close to B. The combined case uses substantially more Services firm cash and carries changed debt/arrears, rather than creating costless supply. In the 10k reference town, output and jobs improve only modestly over the late window, access falls and happiness is slightly lower; greater nominal GDP/credit does not establish a universal benefit. The per-seed and secondary-sequence results above show the limits. No claim is made that prior unmet demand was mostly fictitious, that fundable unmet must fall, or that every firm/household benefits.

At 10k on income_late, late-window nominal GDP is nearly flat (668771->668783), Services units rise 7294.9->7332.7, jobs are nearly flat 5399.8->5398.1, and paid gross wage income falls 475114->472218. Services wage arrears fall 133397->112150 and bank debt falls 1003510->937692; happiness is slightly lower and mean health is essentially unchanged. Those benefits and costs coexist.

## Performance and cost diagnosis

The operational target is at most 5% extra median **and** p95 integrated engine time; it is a project working threshold, not owner-supplied calibration. Quantiles below use 40 late-window ticks per run (median and nearest-rank p95). Seeds vary economic workloads; they are not same-state timing repeats. The 1k estimates exceed the target, while one 10k seed and no independent repeated runs cannot establish unconditional compliance. No mode/cadence/behavior was reduced to obtain these numbers.

Classification: income_first 1k and income_late 1k are over budget in the observed medians; income_first 10k and income_late 10k are **inconclusive for acceptance**, with within-budget point estimates from a single seed. The integrated 5% budget is not accepted. No confidence interval from independent timing repeats is available.

Late-window actor counts match across arms: 36 active firms /9 queued at 1k, 301 active /0 queued at 10k. Employment, paid transactions, capacity, care and credit paths can still differ substantially; equal firm counts do not establish equal engine work. The unusually high income_first 10k B p95 (8440.78ms versus HF 5807.45ms) is retained, not removed as an outlier or interpreted as an established tail-latency improvement.

| Sequence | HH | Seed | B p50/p95 ms | HF p50/p95 ms | HF/B p50 | HF/B p95 |
| --- | --- | --- | --- | --- | --- | --- |
| income_first | 1,000 | 42 | 357.40/426.82 | 414.91/495.17 | 1.161 | 1.160 |
| income_first | 1,000 | 43 | 377.79/467.69 | 410.88/489.86 | 1.088 | 1.047 |
| income_first | 1,000 | 44 | 383.52/462.84 | 473.34/554.79 | 1.234 | 1.199 |
| income_first | 10,000 | 42 | 4,629.74/8,440.78 | 4,681.21/5,807.45 | 1.011 | 0.688 |
| income_late | 1,000 | 42 | 366.34/445.83 | 421.90/502.16 | 1.152 | 1.126 |
| income_late | 1,000 | 43 | 395.85/494.71 | 445.38/535.12 | 1.125 | 1.082 |
| income_late | 1,000 | 44 | 388.63/477.90 | 428.20/500.80 | 1.102 | 1.048 |
| income_late | 10,000 | 42 | 4,777.70/5,689.11 | 4,836.18/5,739.51 | 1.012 | 1.009 |

Four preparatory captures were rejected before any timed trials: missing slotted-dataclass traversal (40 executed steps), two strict fingerprint rejections later isolated to marshal reference/intern metadata (41 steps each), and an import guard that incorrectly treated interpreter site-packages as repository source (42 steps). Their full logs and probe-source versions are retained. These 164 preparatory step calls are excluded from all timings; no macro case failed or was rerun.

Dependency-free common-state replay passed: 4000 read-only arrays, within-graph aliases/static-trait cache, all logical state and RNG reproduced both before and after the uninterrupted B week 40->41 step; 25 shared panel week 41 fields also matched within 1e-7. No dependency was installed. The checkpoint is 3,784,911 bytes; its hash and replay evidence are retained in `cost-diagnostic/checkpoint.json`.

The predeclared sequential probe ran 20 restored one-step wall-time trials per arm/scenario, in four alternating 5-trial blocks. Restore, fingerprint and observation work is outside the timer. A separate cProfile step per B/H/HF arm/scenario is excluded from wall-time samples. These are repeated measurements of one 1k reference state, not independent-town replicates or representative 10k engine evidence.

| Scenario | Arm | p50/p95 ms | p50/B | p95/B | Four block medians ms |
| --- | --- | --- | --- | --- | --- |
| unconditioned | B | 456.11/536.00 | 1.000 | 1.000 | 461.90, 487.24, 458.03, 417.29 |
| unconditioned | H | 506.73/571.46 | 1.111 | 1.066 | 524.71, 508.18, 518.28, 474.39 |
| unconditioned | F | 472.83/529.28 | 1.037 | 0.987 | 478.05, 502.71, 466.61, 451.86 |
| unconditioned | HF | 511.75/672.97 | 1.122 | 1.256 | 500.32, 559.86, 515.10, 498.90 |
| artificial rich | B | 399.10/419.97 | 1.000 | 1.000 | 400.85, 416.32, 395.83, 393.89 |
| artificial rich | H | 454.91/487.39 | 1.140 | 1.161 | 451.23, 458.80, 459.91, 448.98 |
| artificial rich | F | 405.24/429.27 | 1.015 | 1.022 | 418.02, 402.30, 400.77, 400.30 |
| artificial rich | HF | 456.56/479.77 | 1.144 | 1.142 | 469.03, 453.71, 446.47, 456.10 |


The artificial-rich scenario, if present, assigns every household 1,000,000 cash identically before the step to remove the opening-ceiling constraint. It is an intentional resource intervention for cost discrimination, not economic acceptance or calibration. Outcome/work-count equality and profile attribution must be read alongside the ratios; any changed quantities/jobs/care/loans prevent treating the whole difference as bookkeeping overhead.

Cost-probe final native process working sets span 148.71-175.52 MiB; maximum process peak working set is 206.55 MiB. This includes imported runtime, checkpoint restoration and diagnostic allocator retention, not the macro-only heap. Per-arm/block bytes are retained in raw diagnostic files.

Executed diagnostic accounting: 32 successful timing-block invocations, 160 timed one-step trials, 6 separate profiled steps, and 1 valid 42-step capture/replay. Together with the 4 rejected preparatory captures (164 steps), that is 39 successful /4 rejected probe invocations and 372 total `Economy.step()` calls. No timed trial failed. The 2 excluded evaluator-v1 macro pilots add 160 historical ticks outside the 2240-tick main panel; they are not pooled with it.

Cost attribution: the unconditioned common input produces 429 jobs /65 Services slots in B/H and 529 jobs /175 slots in F/HF. It therefore demonstrates real expansion/activity changes. With artificial common rich households, B/H and F/HF each match **every recorded outcome exactly**, including prices, GDP, purchase entries, receipt units, care, jobs, wage income, cash/debt, claims and RNG. H adds 55.81ms median /67.42ms p95 against B (1.140/1.161); HF adds 51.32ms /50.50ms against F (1.127/1.118). This verifies added household order-processing cost on this matched-work scenario; it does not allocate the entire macro slowdown or establish a representative 10k percentage. Purchase-entry counts are merged PaymentBook good-name entries, not raw commit counts; receipt units include goods/care booked there.

The artificial matched-work cProfile records the same 19923 `_buy` calls for B/H, but `_sale_quantity` rises 9173->28667 and H makes 18924 `_goods_subsidy_available` calls. Profiled `_buy` cumulative time rises 188.33->286.84ms and `finish` 54.80->127.18ms. These totals are nested and must not be added, and profiling inflates costs; they locate work rather than estimate unprofiled wall time. By comparison, HF has 11 `_fund_service_expansion` calls totaling 0.202ms cumulative, including 0.167ms of funding quotes. This cash-expansion checkpoint does not benchmark added mixed-loan/default servicing costs. Bank/slot/job changes in the real macro runs remain part of the integrated workload.

Bounded parent proposal, **not implemented**: prototype an algebraically identical zero-subsidy path in `PaymentGoodsMarket._buy` and `finish`, skipping funded-subsidy envelope lookups when the immutable target share is exactly zero and using the equivalent private-cash quantity bound. The captured town has subsidy target none/rate 0 (`subsidy-inputs.json`); the 18924 envelope calls alone consume 31.68ms cumulative under profiling. Preserve current-quote checks before stock, the largest cumulative fundable quote, final priority-aware residual allocation, EPS/rounding and positive-subsidy exhaustion behavior. Verify exact recorded decisions/quantities/cash/claims/shortage signals/RNG on both sequences, then repeat interleaved 1k/10k timing. This is a concrete overhead candidate, not a measured optimization or assurance that the integrated 5% target will be met. New funded activity and necessary shortage accounting still cost time.

Replay scope: the logical fingerprint covers actor fields, container aliasing, array contents/writeability and declared function-code fields, with CONFIG identity and static-trait/lookup aliases checked explicitly. This verifies the recorded one-step baseline replay; it is not a general checkpoint-branching guarantee or a claim about identical physical array layout/global cache warmth.

## Memory, artifacts and parent handoff

The 28 macro workers all returned null memory records because `psutil` is absent; **no macro final-RSS or process-peak delta is established**. Sparse native OS samples in `os-memory-samples.jsonl` are process working-set observations at the recorded times, not final snapshots or Python-heap measurements. Cost-probe working sets, if recorded, include its checkpoint bytes, restoration/fingerprint workspace and repeated-trial allocator retention; they cannot substitute for representative macro memory acceptance. No numeric memory ceiling is specified in the rules. New household/order records remain tick-local/bounded by existing actors/orders; this source bound does not make their storage free.

| Sparse OS sample group | Samples | Observed working-set range MiB | Largest observed process peak MiB |
| --- | --- | --- | --- |
| income_late / 1000 / HF | 2 | 58.61-62.81 | 66.13 |
| income_late / 10000 / B | 1 | 297.70-297.70 | 319.07 |
| income_late / 10000 / HF | 2 | 192.09-323.06 | 325.91 |

Samples occur at different unknown model ticks; these ranges do not estimate an HF/B memory increase. The panel did not record heap/object allocation peaks, retained-order-record byte sizes, or matched final process memory.

External root: `C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/`. Retained evidence:

- `affordable-expansion-panel/{sequence}-{population}-s{seed}-r0-{arm}.json` and `.log`: all 28 raw cases/worker logs; `sources/{arm}/source.json` plus frozen backend files.
- `affordable-expansion-panel/analysis.json`: exact completeness/integrity, per-case endpoint/late-window values and timing; `provenance.json`: module/source verification; `os-memory-samples.jsonl`: declared-perimeter OS samples.
- `affordable_expansion_panel.py` (immutable evaluator), `affordable_expansion_driver.py` (inherited controller), strengthened `affordable_expansion_analysis.py`, `affordable_expansion_provenance.py`, and `affordable_expansion_write_report.py`.
- `affordable-expansion-panel/cost-protocol.json`, `cost-diagnostic/`: protocol, checkpoint/replay evidence, restored-step trials, optional profiles/analysis and complete diagnostic failure logs. The original unrun cloudpickle draft is preserved; this worker installed no dependency.
- `affordable-expansion-full-tests.log`: verified parent full functional-gate log. `affordable-expansion-panel/artifact-hashes.json` records SHA256 for retained cases, logs, source manifests, evaluators, analysis and diagnostic artifacts; that manifest excludes itself and this report to avoid circular hashes.

Final inventory: 1034 hashed artifacts. Manifest SHA256: `64680c93be42d3e7d76cb988fcd7329264714d8818f0f3f22e264047c0d38137`.

| Primary artifact relative to external root | SHA256 |
| --- | --- |
| `affordable_expansion_panel.py` | `344ace994e530ffa07bfcf659bbe7ef7fe2ac338cf6acdeed32ebdbb5f239a45` |
| `affordable-expansion-panel/analysis.json` | `735e819a1b54e4e61f1c6e8743ce298bc9d3881b143be6d97eafce6c072ee484` |
| `affordable-expansion-panel/cost-diagnostic/analysis.json` | `ccc83c8c5d1af59d979c520573f3d3497a3a93b9891b84e27c1ccec1e8facfe3` |
| `affordable-expansion-panel/cost-diagnostic/baseline-week40.pickle` | `2e08d3638d54238c7ad831185f4285439c68c22644cf03fb3e1e31fa30db6ade` |

Parent handoff: all 28 macro cases are complete and evidence is retained; functional/accounting evidence supports further integration review, with the economic tradeoffs and open performance/memory limits above. Only this result document is changed in the repository; no local commit was made by this worker. Keep performance acceptance open. A bounded follow-up may reduce measured order-processing overhead while preserving exact prices, allocations, claim ordering, shortage signals, RNG and cadence, then rerun interleaved matched 1k/10k timing with a declared uncertainty method. Do not tune economic behavior to force a 5% result. Generated OpenWiki refresh remains due because approved tooling/key is unavailable; no secret was requested and generated pages were untouched.
