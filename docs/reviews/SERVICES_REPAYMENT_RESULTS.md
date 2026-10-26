# SERVICES-02 validation and results

Follow-up validated before PR publication on `codex/services-decision-coherence`, based on fetched authoritative main d71485e7276cb2bf988eee6ff8ae9ecada3b73be. Compare against the preceding SERVICES-01 package, not original main. [Selected contract](SERVICES_REPAYMENT_CONTRACT.md), active rules v1.16. The owner subsequently authorized publication together with SERVICES-01. No merge or UI change is authorized. [Compact aggregate data and source hashes](evidence/services/README.md) are included for review.

## Implemented scope

The only additional production edit is `FirmAgent._service_pricing_costs`. Planned quote cash coverage uses scheduled bank installments (which include infrastructure) plus direct Treasury installments. Each mirror is bounded by its nonnegative outstanding balance. This protects against the existing named Treasury collector retaining a schedule after payoff. Planning does not debit another payment, change a debt claim or treat principal repayment as a new accounting/tax operating expense.

The markup target remains stable, and measured markup/stabilization inherit the updated planning denominator. Existing utilization interpolation, tax gross-up and 20% quote smoothing remain. The effective transaction floor is intentionally unchanged: this experiment does not add an immediate debt surcharge at checkout. Customer choice, the bank's 35% coverage gate, loan sizes/terms, full staffed-space condition, three-week hiring recovery, other sectors and update cadence remain.

## Functional evidence and review

- Focused related suites: 162 passed, 1 xfailed before the final stabilization cases were added.
- All 17 new repayment regressions pass: zero debt, Treasury and bank obligations, infrastructure counted once within the bank mirror, mixed debts, final outstanding balances, direct Treasury payoff through real collection, no planning-side cash/profit debit, stable quotes and the unchanged transaction floor. The final two cases directly cover stabilized markup with repayments under both named sequences.
- The first implementation's five focused failures exposed stale/last-payment schedules affecting the quote. Capping each schedule by its outstanding balance resolved these without changing collection or the shared all-sector debt helper.
- Initial default backend run under Ubuntu/WSL: 1218 passed, 2 skipped, 8 research deselected, 1 xfailed; one economic prompt golden failed. That failure was investigated rather than suppressed. The frozen SERVICES-01 source reproduced the old `cd9c42...` digest, while repayment-aware pricing produced `851297...`. Both prompt texts and their diff were preserved. The prompt templates/public-debt logic were unchanged; economic input values changed. The economic reference was updated and its focused test passed.
- Final pre-publication full default backend rerun, including all 55 new Services regressions: **1221 passed, 2 skipped, 8 research deselected, 1 xfailed**, with one third-party deprecation warning, in 217.74 seconds. Ubuntu24.04/WSL, Python3.12.3, project-lock-constrained environment; the real Windows Git bridge and worktree import isolation are the same as SERVICES-01. This final run includes the refreshed economic reference and both added stabilization cases. Log: `services-pr-final-tests.log` in the external evidence directory; its hash is in the published evidence manifest.
- Ruff and `git diff --check` passed.
- Independent Sol medium review found no selected-scope blocker. It suggested stabilization-with-repayment and real bank-payoff coverage. The former was added; the latter's general collector remains covered by existing payment-loan tests, while this change tests a final bank balance directly. The reviewer did not execute tests or simulations.

The aggregate bank balance cap does not calculate every final installment of multiple concurrent claims independently. These are planning mirrors, not a new amortization engine. Existing registered claim collection remains authoritative.

## Matched simulation experiment

Status: complete: 16/16 cases, 8 matched pairs, 1,280/1,280 weekly ticks; zero failed cases or raw tick errors. This is a short synthetic experiment, not a calibrated policy result.

Frozen baseline: external `services-component-experiment/sources/P1E1H1` (the prior complete Services package). Frozen candidate: current production source with only the additional repayment helper change. Both cases use normal mode, 80 weekly ticks, warmup 10, factory firms-per-category argument 10, `PYTHONHASHSEED=0` and identical initialization. Reference order: `income_first`, then `income_late`.

Bounded panel: three seeds (42,43,44) at 1,000 households and seed42 at 10,000, each with before/repayment arms; 16 sequential runs, eight matched pairs. Within-seed order alternates. No other heavy tests/benchmarks run concurrently. No patience, customer, credit or loan-size sweep. Each control endpoint must reproduce its prior SERVICES-01 panel endpoint before interpretation.

The external observer preserves actor state/RNG, joins firm plans using identity epochs, and records complete common initial state and random fingerprints. Payroll-book observation occurs after the goods phase, where actual funded income has settled; this corrects the preceding component screen's excluded pre-payroll counters. The analysis checked all eight exact initial profile/state/RNG pair fingerprints, all eight prior SERVICES-01 control endpoints (maximum absolute difference below 1e-7 on shared fields), frozen worker/source hashes against the live candidate, and every raw run/tick record. Frozen `economy.py` and `payment_government.py` hashes match across arms; the only `agents.py` difference is the selected `_service_pricing_costs` repayment term. Injection-adjusted cash includes bank reserves and named payment holds. Its maximum absolute residual was $0.0001101; maximum clearing-cash residual was $0.0000000210, below the stated $0.001 and $0.000001 ceilings respectively.

### Economic outcomes

Each arrow is preceding SERVICES-01 package → repayment-aware quote. Values at week 80 are three-seed means for 1k and a single seed for 10k. Units are real Services purchases, while GDP and prices are nominal. Access counts households with a Services purchase in that week; employment is Services workers / all employed households.

| Sequence, households | GDP | Services units | Access | Employment | Posted Services price | Mean happiness / health |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `income_first`, 1k | 17,349 → 19,849 | 230.4 → 225.6 | 874 → 880 | 63 / 290 → 62 / 291 | 20.98 → 32.72 | .396 / .580 → .401 / .609 |
| `income_first`, 10k | 677,342 → 723,002 | 7,989 → 8,263 | 9,988 → 9,990 | 2,010 / 5,089 → 2,135 / 5,311 | 74.18 → 75.99 | .402 / .631 → .407 / .631 |
| `income_late`, 1k | 18,296 → 22,426 | 248.8 → 283.4 | 928 → 917 | 66 / 297 → 74 / 320 | 21.05 → 31.94 | .401 / .596 → .410 / .631 |
| `income_late`, 10k | 669,533 → 717,341 | 7,956 → 8,471 | 9,966 → 9,968 | 1,983 / 5,130 → 2,140 / 5,294 | 74.93 → 76.21 | .385 / .614 → .392 / .616 |

The GDP increase occurs in all eight matched pairs, but it must be read beside real access and wellbeing. In `income_first` 1k, real Services units fell in every seed (−3.7, −6.8, −4.0); endpoint happiness rose in each. In `income_late` 1k, the mean unit increase is driven by seed 43 (+111.3), while seeds 42 and 44 fell (−3.5, −4.0), and endpoint access fell in all three seeds. Over weeks 41–80, mean happiness was slightly lower with repayment in both 1k cells (.5045 → .5031 and .5061 → .5047), despite higher endpoint happiness. The 10k cells each have only seed 42.

| Sequence, households | Services cash | Household cash | Services bank debt | Services Treasury debt | Services wage arrears | Funded Services gross wages, weeks 41–80 mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `income_first`, 1k | 320.5k → 394.2k | 163.6k → 167.9k | 1.5k → 1.5k | 190.9k → 190.9k | 0 → 0 | 3,009 → 3,007 |
| `income_first`, 10k | 1.814m → 1.818m | 2.851m → 2.930m | 1.088m → 1.216m | .875m → .906m | .420m → .371m | 290,127 → 299,097 |
| `income_late`, 1k | 317.8k → 390.8k | 177.0k → 185.6k | 4.2k → 8.0k | 185.3k → 185.5k | 0 → 0 | 3,240 → 3,449 |
| `income_late`, 10k | 1.868m → 1.866m | 3.007m → 3.144m | 1.092m → 1.245m | .928m → .884m | .396m → .435m | 287,060 → 300,347 |

Higher requested prices therefore coincided with higher nominal output and often more real activity at 10k, but did not uniformly improve real Services delivery, access, late-window happiness, debt or arrears. Bank reserves at week 80 fell in all four cells (4.319m → 4.235m, 43.761m → 43.351m, 4.309m → 4.223m, 43.662m → 43.128m respectively); the matched runs include endogenous borrowing and spending, so these are whole-economy outcomes rather than a direct price-payment identity. Weeks 41–80 mean GDP and real Services units respectively were 36,211 → 38,942 and 235.1 → 233.7 (`income_first` 1k); 771,013 → 794,129 and 7,040 → 7,171 (`income_first` 10k); 36,789 → 39,993 and 254.1 → 269.2 (`income_late` 1k); 764,916 → 796,627 and 7,004 → 7,295 (`income_late` 10k). Per-seed endpoints and full late-window measures are retained in `analysis.json`.

Latency pairs use the same weeks 41–80 as the late outcome window. Repayment/before p50 ratios were .998–1.062 (`income_first` 1k), .988 (`income_first` 10k), .988–1.084 (`income_late` 1k), and .993 (`income_late` 10k); p95 ratios were .982–1.093, .971, .949–1.121, and .947 respectively. There is only one timing repeat per seed, one 10k seed, and endogenous changes in work. This is exploratory engine timing; two 1k pairs exceed +5% p50, and no 5% runtime-budget pass or unqualified speedup is established. The selected code adds only constant-time scalar bounds; there is no new per-household search, history, state field or decision-frequency change. Runtime/application/browser cost is not assessed here.

External artifacts: `C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/services-repayment-experiment/` (including `analysis.json`, `sources.json`, all 16 case/raw records), `services_repayment_experiment.py`, `services_repayment_analysis.py`, `services_repayment_prompt.py` and `services-repayment-full-tests.log`. Frozen source/worker hashes, prompt pairs and their diff are retained.

## Delivery boundary

Rules, contract, tests and CHANGELOG are updated. Generated OpenWiki refresh remains due: the approved OpenWiki0.3.0 tooling and OpenRouter key were unavailable as recorded in SERVICES-01; generated pages were not hand-edited. This local experiment is not a merge or a claim that every firm becomes viable.
