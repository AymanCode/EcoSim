# MONEY-P01: fund named-payment R&D before recording it

2026-10-22. Owner-approved accounting correction. Baseline: `14c79298fb6355ba9a6505b530db76ccede37dbb`; implementation: `aafa5eac8abcea980b7b06fd0f1fe18661f87af8`. Later evidence commits do not change engine code.

The town runs `payment_sequence="legacy"`: all five paired seeds are identical in every per-week state digest and in the full-precision row fingerprint over 312 weeks. The optional budget is omitted on legacy; its overdraft/exit conventions remain unchanged. Its largest observed absolute money residual is $0.000003796071.

## Mechanism and counterparties

`FirmAgent.apply_rd_and_quality_update` accepts optional `available_cash`. The named-arm `Economy._phase_institutional_close` call supplies nonnegative cash after registered bank and direct treasury debt collection. Actual R&D is the smaller of unchanged desired spending and that budget, before any accumulated-investment, cash or quality write. Investment tax and the miscellaneous tax/pool route use the same returned amount. There is one shared R&D call for scalar/batch settlement and normal/performance modes. No phase, desired rate, eligibility, cadence, existing decay, config switch, lender or exit rule changes.

For a $20 profitable Food sale leaving $0.50 after debt, actual R&D is $0.50. At 10% investment tax, treasury receives $0.05 plus its existing miscellaneous skim from the remaining $0.45; the pool receives the balance and later pays households. Accumulated R&D and quality gain use $0.50. If debt leaves no cash, spending and recipient credits are zero; the existing eligible-firm quality decay still runs. Healthcare and survival-mode early returns keep their previous behavior.

Cash-constrained businesses therefore buy less quality improvement; tax/pool recipients can receive less. Later demand, jobs, GDP, household resources and wellbeing can change. At the same input state, fully funded businesses retain their planned spending. These are bounded simulator results, not real-world policy estimates.

## Paired default panels

1,000 households, 5 firms/category, seeds 42-46, 312 ticks, normal cadence, all stabilizers on, LLM government off, `PYTHONHASHSEED=0`. Changes are branch minus same-seed main, averaged over the five seed-specific window means. Share changes are percentage points. The table was recomputed independently from raw rows. Food/Services cash is the total over active firms; quality is the unweighted mean over active firms; R&D is actual weekly payments, including firms that later exit. Per-seed ranges and medians are in [the acceptance JSON](evidence/money-p01/acceptance.json).

### income_first

| Metric | Weeks 201-312: main | Change | Weeks 261-312: main | Change |
|---|---:|---:|---:|---:|
| Nominal GDP ($/week) | 55424.538227 | -196.198919 | 53117.770300 | -406.832740 |
| Real GDP (GDP / CPI x 100; $/week) | 41515.207786 | -98.829830 | 40062.914594 | -193.207719 |
| Poverty: liquid < $200 (%) | 63.233929 | +0.544643 | 65.414231 | +1.220000 |
| Happiness (index) | 0.328164 | -0.000831 | 0.307837 | -0.001854 |
| Health (index) | 0.625861 | -0.000040 | 0.621862 | -0.000045 |
| Minimum food satisfied (%) | 97.357321 | -0.059107 | 97.326923 | -0.126538 |
| Labour-force unemployment (%) | 2.076663 | +0.148657 | 1.818061 | +0.342430 |
| Food firms: total cash ($) | 496255.165090 | +665.915789 | 522842.958858 | +1475.378833 |
| Services firms: total cash ($) | 779956.296477 | +169.899896 | 691763.659187 | +476.417269 |
| Food firms: actual R&D ($/week) | 2005.103562 | -11.020071 | 1992.137965 | -21.378720 |
| Services firms: actual R&D ($/week) | 1462.126576 | +41.849149 | 925.693780 | +86.336830 |
| Food firms: mean quality | 8.154697 | -0.000594 | 8.171770 | -0.001234 |
| Services firms: mean quality | 8.209509 | +0.000010 | 8.223858 | +0.000020 |

### income_late

| Metric | Weeks 201-312: main | Change | Weeks 261-312: main | Change |
|---|---:|---:|---:|---:|
| Nominal GDP ($/week) | 56244.561322 | +0.067853 | 53498.920754 | -1.458179 |
| Real GDP (GDP / CPI x 100; $/week) | 42032.594615 | +14.476451 | 40327.783665 | +31.337429 |
| Poverty: liquid < $200 (%) | 62.516250 | -0.016071 | 66.135769 | -0.030385 |
| Happiness (index) | 0.329248 | +0.000067 | 0.307624 | +0.000134 |
| Health (index) | 0.623083 | -0.000008 | 0.618570 | -0.000012 |
| Minimum food satisfied (%) | 97.329821 | -0.000179 | 97.298462 | -0.002692 |
| Labour-force unemployment (%) | 0.978230 | -0.002284 | 0.933114 | -0.003289 |
| Food firms: total cash ($) | 518497.576603 | +68.247915 | 559532.292499 | +115.038566 |
| Services firms: total cash ($) | 752505.444093 | -15.058525 | 645019.677013 | -22.448755 |
| Food firms: actual R&D ($/week) | 2087.558625 | +0.914274 | 2054.910153 | +2.210450 |
| Services firms: actual R&D ($/week) | 1228.649751 | +10.373506 | 701.297423 | +18.133881 |
| Food firms: mean quality | 8.163592 | -0.000155 | 8.180213 | -0.000272 |
| Services firms: mean quality | 8.162446 | +0.019795 | 8.238483 | +0.042630 |

All 33 default-panel runs (including three baseline repeats) pass the unchanged money gate; maximum absolute residual $0.000010914169. The ten fixed named runs record zero unfunded positive R&D payments across 89,557 calls. Legacy identity is 5/5 seeds; baseline deterministic replay is checked by the native evaluator.

## Exact poverty-4 seed-44 replay

`income_first`, profit tax 0%, soft Services price controls, 312 ticks. The preserved main reproduction has final drift +$0.296819603071 and maximum absolute drift $0.296820553020 (58 unfunded positive R&D payments in its independent flow trace). Its main default-control state fingerprint matches the fresh main default-control fingerprint in this panel. The fresh fixed default control also matches the fixed default panel fingerprint; the extra read-only observers do not change these states.

The fixed package ends at +0.000006999820 dollars, with maximum absolute drift $0.000006999820, below $0.0001. Zero unfunded payments were observed across 8,666 R&D calls. The native fixed candidate/default/repeat panel exits 0 with money, bounds and deterministic replay passing. No deficit was clamped at exit and no tolerance was relaxed.

A fresh original-main package replay reproduces the preserved state fingerprint and money results exactly and observes the same 58 unfunded payments. Its native panel exits 1 as expected; the fixed native panel exits 0. These same-host package means show the downstream effect of the correction for this one selected seed:

| Metric | Weeks 201-312: main package | Fixed package | Change |
|---|---:|---:|---:|
| Nominal GDP ($/week) | 35421.248617 | 35861.490671 | +440.242053 |
| Real GDP (GDP / CPI x 100; $/week) | 17042.865838 | 17225.419528 | +182.553691 |
| Poverty: liquid < $200 (%) | 66.784821 | 66.896429 | +0.111607 |
| Happiness (index) | 0.287457 | 0.288199 | +0.000742 |
| Health (index) | 0.251117 | 0.252037 | +0.000921 |
| Minimum food satisfied (%) | 41.821429 | 40.416964 | -1.404464 |
| Labour-force unemployment (%) | 0.169212 | 0.117589 | -0.051623 |
| Food firms: total cash ($) | 489796.183420 | 496458.034933 | +6661.851514 |
| Services firms: total cash ($) | 1025805.474686 | 1029144.633938 | +3339.159253 |
| Food firms: actual R&D ($/week) | 1101.037599 | 1110.950599 | +9.913000 |
| Services firms: actual R&D ($/week) | 1978.488571 | 2003.851441 | +25.362869 |
| Food firms: mean quality | 7.888590 | 7.831120 | -0.057470 |
| Services firms: mean quality | 8.639716 | 8.642582 | +0.002867 |

## Tests and compatibility

- 26 new regressions pass: zero/partial/ample funding, zero/loss profit or revenue, survival, healthcare, signed pre-existing cash, omitted-budget exact arithmetic, and 16 public-step debt fixtures (both sequences, both modes, bank/direct treasury, zero/partial residual cash). The fixtures reconcile tax and pool credits, next-tick household redistribution and every completed boundary through actual 12-zero-cash streak exit, using $1e-9 absolute money tolerance.
- Focused existing payment acceptance/loans/sectors, healthcare, integration and hot-path suites: 161 pass, 1 expected failure on both main and branch.
- Full configured backend suite: main 1066 passed, 71 failed, 1 expected failure; branch 1092 passed, 71 failed, 1 expected failure. The exact failing test-ID sets match; the 26 extra branch cases pass. Complete raw failure output and JUnit XML are preserved in the external artifact directory. Ubuntu CI remains authoritative; it is left to the parent thread.
- Economic-agent rules v1.14 records only the owner-approved named-payment R&D funding clarification and preserves v1.13 otherwise.

## Provenance, cost and limits

Windows / CPython 3.11.9 / NumPy 2.4.6, local non-reference evidence. Six default-panel workers plus one exact-replay worker: at most seven. A launch-only external `sitecustomize` guard checks free physical RAM before each worker and pauses below 3 GiB; minimum recorded free RAM at launch was 10.096 GiB. Numeric-library thread counts are 1. The observer wraps the existing method once, records input cash and returned spending, and reads completed stocks; it consumes no randomness and changes no model state. Identical legacy rows and replay/control hashes guard observer behavior.

The patch adds constant work per eligible firm and no persistent state or history. Concurrent panel elapsed times are not performance acceptance; no speedup or cumulative 5% runtime-budget pass is claimed. Full-scale performance-mode economic effects, other policies/seeds/horizons and resumed pre-existing overdrafts are not certified by this panel. The focused composed regression covers performance mode.

Generated wiki still describes older legacy/fiscal behavior; current source and rules take precedence. OpenWiki refresh remains due: the approved CLI and provider key are unavailable locally (`openwiki` absent; `OPENROUTER_API_KEY` unset). No generated wiki file was edited. Refresh after integration with the approved workflow.

Raw artifacts: `C:/Users/ayman/Documents/ecosim-review/money-p01-evidence/` (`defaults/`, `poverty4-fixed/`, `acceptance.json`); logs and launch records: `C:/Users/ayman/Documents/ecosim-review/money-p01-*.log`, `money-p01-launches.jsonl`. Commands are retained in each native panel manifest. The report uses original research artifacts as the failing main control and does not overwrite them.

Reproduce with `python -m backend.tools.benchmarks.run_evidence_panel --arm main --root main <main-checkout> --arm money-p01 --root money-p01 <branch-checkout> --baseline main --sequences legacy,income_first,income_late --seeds 42,43,44,45,46 --ticks 312 --jobs 6 --no-escalate --metrics-plugin docs/reviews/evidence/money-p01/metrics.py --out <out>` in the branch checkout. Set `PYTHONPATH=<branch>;<branch>/backend`, `PYTHONHASHSEED=0` and use the specified EcoSim venv interpreter. Apply the 3-GiB launch guard on shared Windows hosts. For the exact replay use both arms from the branch, seed 44, income_first, and the original three `lever.*` overrides above. The native panel adds baseline repeats.
