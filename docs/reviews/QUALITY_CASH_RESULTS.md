# Cash-funded Food/Services research: results

The cash-funded alternative meets the selected spending goal without restoring instant quality gains. Over 520 weeks, it spends much more than fixed-price A, holds less private-firm cash, and has better late-period employment, real delivery and average happiness in all six paired cases. The negative early pilot was not the lasting jobs/output result relative to A. Against the original instant-research model, outcomes remain mixed: late Services units are slightly lower on average, and jobs fall in four of six seeds even though the mean rises. Household cash and deposits rise in every late comparison. These are controlled within-model results, not calibration or an optimal-spending recommendation.

Owner steering after the pilot: retain the existing research-service payment route and the current R&D mechanism. The 50-beneficiary route predates this change and is not classified as a new defect. An active-bank response to spare deposits is a separate follow-up; no bank behavior was changed. Mechanism acceptance does not itself promote an experimental default or authorize publication.

## What was compared

- **Original instant:** main `8a8d38005d914681ad95bc82d6b3523793be03be`, with its old starting quality and immediate research. This is the old behavior, not a baseline provider.
- **Fixed-price A:** the new low starting-quality scale and 40-funded-week uncertain research, but a fixed 1,200 programme and a recent-profit funding cap.
- **Cash-funded:** A's starting-quality scale, project duration, uncertain outcomes and yearly gain cap. It removes the recent-profit veto and quotes all eligible post-payment cash above the disclosed six-week operating/debt reserve, paid over 40 funded weeks. Payments pause rather than cross that reserve. Source `362237b1463c90eb68fc222b5a66d5b876297965`; rules v1.19 / QUALITY-CASH-01.

Cash versus A tests the selected cash-allocation package, including fresh-cash eligibility and the earned-cost reserve treatment; it does not isolate just one coefficient. Cash versus original also changes starting quality, baseline research and the research institution. Do not attribute that entire contrast to funding alone. All-spare-cash spending is an owner-selected experiment; larger expenditure does not purchase faster or guaranteed quality. The earlier Housing generic-capital change remains parked.

## Economy: late weeks 421-520

Normal mode; 1,000 households; seeds 42, 43 and 44; 520 weeks per case. Each cell below is an arithmetic mean of the three seed-level 100-week means. Quantities are aggregate units per week; jobs/access are household counts; cash, debt and claims are stocks averaged over the window. Cash/deposits do not measure wealth distribution. Full endpoint and per-seed data are in `parent-economy.csv` and `parent-analysis.json` under the external evidence directory.


### income_first

| Measure | Original instant | Fixed-price A | Cash-funded |
| --- | --- | --- | --- |
| Private Food/Services quality | 8.604 | 1.905 | 2.164 |
| Private Food/Services cash | 771,792 | 1,565,767 | 339,391 |
| All firm cash | 3,322,621 | 3,842,671 | 2,779,953 |
| Household cash | 58,261 | 41,909 | 107,048 |
| Household deposits | 1,188,027 | 729,664 | 1,644,892 |
| Treasury cash | 98,198 | 45,449 | 114,752 |
| Bank cash reserves | 2,608,408 | 2,159,665 | 3,079,204 |
| Employed households | 863.6 | 703.3 | 875.1 |
| Household wage receipts/week | 41,774 | 34,778 | 45,807 |
| Unpaid wage-claim stock | 539,174 | 319,094 | 365,454 |
| Real Services units/week | 2,126 | 1,599 | 2,078 |
| Households receiving Services | 989.1 | 916.4 | 993.2 |
| Food units/week | 3,499 | 3,376 | 3,723 |
| Households with housing need met | 993.3 | 888.1 | 995.8 |
| Mean happiness | 0.269 | 0.216 | 0.337 |
| Mean health | 0.614 | 0.585 | 0.625 |
| Nominal GDP/week | 45,512 | 37,401 | 51,087 |
| Firm debt to bank | 72,942 | 59,468 | 64,719 |
| Firm debt to Treasury | 12,606 | 0 | 117 |

### income_late

| Measure | Original instant | Fixed-price A | Cash-funded |
| --- | --- | --- | --- |
| Private Food/Services quality | 8.622 | 1.914 | 2.076 |
| Private Food/Services cash | 776,913 | 1,491,904 | 338,071 |
| All firm cash | 3,315,618 | 3,789,405 | 2,771,252 |
| Household cash | 81,262 | 60,026 | 131,786 |
| Household deposits | 1,164,564 | 747,589 | 1,621,931 |
| Treasury cash | 97,193 | 52,229 | 113,216 |
| Bank cash reserves | 2,593,671 | 2,188,060 | 3,064,722 |
| Employed households | 860.3 | 703.9 | 879.5 |
| Household wage receipts/week | 40,899 | 34,548 | 44,563 |
| Unpaid wage-claim stock | 543,628 | 316,306 | 357,040 |
| Real Services units/week | 2,109 | 1,635 | 2,093 |
| Households receiving Services | 990.8 | 954.5 | 996.8 |
| Food units/week | 3,510 | 3,209 | 3,688 |
| Households with housing need met | 993.1 | 934.1 | 999.6 |
| Mean happiness | 0.265 | 0.225 | 0.338 |
| Mean health | 0.612 | 0.557 | 0.621 |
| Nominal GDP/week | 44,825 | 36,892 | 50,420 |
| Firm debt to bank | 75,489 | 63,775 | 64,664 |
| Firm debt to Treasury | 11,047 | 0 | 42 |


## Seed differences and early/late tradeoffs

Relative to A, late jobs, Food/Services units, nominal GDP, private quality, household cash/deposits and happiness rise in every seed. Private Food/Services cash falls in every seed, by about 77-78% on the mean paired percentage measure. Cumulative private research payments are about 12 times A's total. Access is not uniformly better: Services access falls slightly in seed 42, and housing access falls slightly in seed 42 of income_first and seeds 42-43 of income_late. Wage-claim stocks increase in every seed versus A, with higher employment and wage receipts; the extra claims still matter and do not establish a reliability improvement.

Against original instant behavior, the late mean job count rises by 11.5 households in income_first and 19.2 in income_late, but seed 43 drives those mean gains. Seeds 42 and 44 have fewer jobs in both sequences. Services units fall in four of six seeds; the mean paired percentage differences are -2.10% and -0.60%. Food units, household cash/deposits, health and happiness rise in all six. Nominal GDP falls in seed 42 in both sequences despite its positive three-seed means. Wage-claim stocks are lower in all six than original. These observations do not justify calling every household or business better off.

Late averages by seed:


| Timing | Seed | Model | Jobs | Services units | Housing access | Happiness | GDP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| income_first | 42 | Original instant | 934.8 | 2,441 | 994.4 | 0.357 | 55,121 |
| income_first | 42 | Fixed-price A | 860.5 | 2,137 | 999.1 | 0.276 | 44,069 |
| income_first | 42 | Cash-funded | 920.4 | 2,359 | 996.9 | 0.401 | 52,656 |
| income_first | 43 | Original instant | 869.5 | 2,090 | 993.1 | 0.244 | 44,256 |
| income_first | 43 | Fixed-price A | 686.7 | 1,455 | 961.5 | 0.214 | 38,900 |
| income_first | 43 | Cash-funded | 920.1 | 2,027 | 991.9 | 0.347 | 56,715 |
| income_first | 44 | Original instant | 786.5 | 1,848 | 992.4 | 0.207 | 37,160 |
| income_first | 44 | Fixed-price A | 562.8 | 1,205 | 703.8 | 0.159 | 29,233 |
| income_first | 44 | Cash-funded | 784.7 | 1,850 | 998.8 | 0.262 | 43,890 |
| income_late | 42 | Original instant | 925.1 | 2,425 | 992.2 | 0.352 | 52,279 |
| income_late | 42 | Fixed-price A | 832.1 | 1,996 | 999.6 | 0.270 | 43,554 |
| income_late | 42 | Cash-funded | 920.1 | 2,343 | 999.2 | 0.389 | 50,705 |
| income_late | 43 | Original instant | 864.3 | 2,029 | 993.6 | 0.239 | 44,516 |
| income_late | 43 | Fixed-price A | 753.4 | 1,720 | 1,000.0 | 0.254 | 42,463 |
| income_late | 43 | Cash-funded | 929.1 | 2,082 | 999.8 | 0.364 | 56,741 |
| income_late | 44 | Original instant | 791.4 | 1,873 | 993.4 | 0.203 | 37,680 |
| income_late | 44 | Fixed-price A | 526.2 | 1,188 | 802.7 | 0.152 | 24,660 |
| income_late | 44 | Cash-funded | 789.2 | 1,853 | 999.9 | 0.260 | 43,815 |


The previous seed-44 housing loss is not reproduced at the same severity by cash funding: A's late housing access is 703.82 in income_first and 802.69 in income_late; cash funding yields 998.76 and 999.92. Housing code is unchanged, so these are indirect economic outcomes, not proof of a housing fix.

The seed-42 income_first pilot at week 80 had fewer jobs (437 to 373) and lower Services delivery (574 to 384) for cash versus A. At late weeks 421-520 the same contrast has more jobs (860.48 to 920.41) and Services units (2,136.90 to 2,358.86). Both observations are retained. The captures establish a horizon-dependent response, not a full causal decomposition of why it changes.

Week-520 endpoints, averaged across three seeds:


| Timing | Model | Jobs | Services units | Private F/S cash | HH deposits | Quality | Housing access |
| --- | --- | --- | --- | --- | --- | --- | --- |
| income_first | Original instant | 838.7 | 2,021 | 778,949 | 1,001,864 | 8.625 | 992.3 |
| income_first | Fixed-price A | 641.3 | 1,410 | 1,604,270 | 581,813 | 1.968 | 787.0 |
| income_first | Cash-funded | 865.3 | 2,030 | 316,825 | 1,485,098 | 2.276 | 997.0 |
| income_late | Original instant | 842.3 | 1,998 | 786,936 | 979,402 | 8.636 | 993.3 |
| income_late | Fixed-price A | 642.0 | 1,424 | 1,549,534 | 566,172 | 1.972 | 845.3 |
| income_late | Cash-funded | 863.7 | 2,021 | 310,954 | 1,477,929 | 2.175 | 999.7 |


## Research output, pauses and bank exposure

The maximum observed raw private quality under cash funding is 4.426, including starting products. No actual or effective near-perfect private product is observed in the cash captures; the independent completion-event check finds no rolling 52-week gain above 1 plus numerical tolerance. Mean private quality at week 520 is 2.276 for income_first and 2.175 for income_late, rather than the original model's approximately 8.63. The cash model produces more completed attempts than A because projects are funded more often, not because an installment buys immediate quality. Changes in average quality also include firm entry/exit composition.

The table contains mean totals per 520-week case, except the final two columns. Pauses are the unweighted mean across seeds of paused/open project-weeks in weeks 421-520. Unpaid programmes are discretionary remaining quotes, not debt, escrow or a payable claim.


| Timing | Model | Private R&D paid | Completed attempts | No-gain attempts | Paused late | Unpaid quotes at 520 |
| --- | --- | --- | --- | --- | --- | --- |
| income_first | Original instant | 1,781,224 | not a project model | not measured | not applicable | 0 |
| income_first | Fixed-price A | 229,500 | 173.3 | 22.0 | 68.8% | 15,700 |
| income_first | Cash-funded | 2,821,241 | 209.3 | 23.3 | 49.8% | 103,036 |
| income_late | Original instant | 1,748,930 | not a project model | not measured | not applicable | 0 |
| income_late | Fixed-price A | 231,960 | 176.0 | 23.7 | 69.5% | 16,440 |
| income_late | Cash-funded | 2,794,153 | 197.7 | 23.3 | 55.9% | 130,465 |


Cash programmes still pause in roughly half of late open-project weeks. Quoting a large budget does not escrow it: later operating bills, dividends and expansion can compete with research. The six-week reserve and minimum project resources remain intentional boundaries. More research-service payments flow through the existing investment-tax/miscellaneous route; the experiment adds no research workers or suppliers. Their selected household recipients and banks can accumulate balances while real output follows a different path. Gross research-receipt, deposit and withdrawal flows were not decomposed by this recorder; higher deposits cannot establish that every household saved more or spent less.

No cash case ends with a currently delinquent registered firm loan. Four cases show zero bank-funded writeoffs throughout. income_first seed 42 records 0.877 of cumulative written-off contractual balances; income_late seed 42 records 3,514.207, versus A's 3,144.011 and original's zero in that seed. That case also reaches one concurrently delinquent firm loan earlier. These diagnostics are not isolated research-loan defaults: this change originates no R&D loans, and the metric covers all bank-funded claims. Contractual writeoff balances are not necessarily cash losses. Increased aggregate bank reserves do not prove increased useful lending. A bank-incentive audit is noted separately; no lending gates, rates or borrowers were changed here.

## Runtime

Separate normal-mode timing: 1,000 and 10,000 households, both sequences, seed 42, five paired repeats, 80 ticks. Observer wrappers are disabled, post-step recording remains. Each run's median and nearest-rank p95 use exactly weeks 41-80 (40 observations, p95 is sorted element 38). The displayed ratio is the geometric mean of five same-repeat candidate/control ratios. Intervals use 100,000 paired bootstrap resamples of the five whole repeat clusters, NumPy default_rng seed 20261027. Repeated seeds do not measure uncertainty across economies; only execution variability within this screen.

**Overall 5% performance acceptance remains inconclusive.** income_first / 1,000 / p95 crosses the budget against both A and original. Against A its point estimate is also above 1.05. No additional repeats were selected after seeing this result. All other displayed interval upper bounds are below 1.05. Runtime is integrated engine cost with changed economic work, not isolated R&D overhead or an unqualified speedup. Weeks 41-80 remain private-firm ramp at 1,000 households and fully activated at 10,000. Whole-process RSS includes the harness and does not establish a memory saving.


| Timing | Households | Control | Median ratio [95% interval] | p95 ratio [95% interval] |
| --- | --- | --- | --- | --- |
| income_first | 1,000 | Fixed-price A | 0.9983 [0.9625, 1.0243] | 1.0542 [0.9673, 1.1509] |
| income_first | 1,000 | Original instant | 0.9802 [0.9606, 0.9971] | 0.9616 [0.8848, 1.0843] |
| income_first | 10,000 | Fixed-price A | 0.9784 [0.9105, 1.0307] | 0.8938 [0.6805, 1.0427] |
| income_first | 10,000 | Original instant | 1.0123 [0.9956, 1.0351] | 1.0180 [0.9922, 1.0482] |
| income_late | 1,000 | Fixed-price A | 1.0038 [0.9987, 1.0080] | 0.9885 [0.9749, 0.9987] |
| income_late | 1,000 | Original instant | 0.9902 [0.9690, 1.0111] | 0.9839 [0.9485, 1.0140] |
| income_late | 10,000 | Fixed-price A | 0.9979 [0.9714, 1.0212] | 0.9997 [0.9817, 1.0123] |
| income_late | 10,000 | Original instant | 0.9806 [0.9360, 1.0125] | 0.9933 [0.9577, 1.0183] |


## Verification and boundaries

The formal panels completed 78 cases / 14,160 ticks (18 long cases and 60 timing cases), with zero failed captures. The prior two-case / 160-tick pilot remains separate. Parent analysis independently checked all 654 hashes in the worker manifest, source identity/worker hashes, row identity/order, initial profile/RNG/comparable configuration, new-quality parity, all three diagnostics on every formal row, and accounting tolerances. It compared all 12 long-run original/A controls to earlier raw economic rows and initial/final RNG exactly, excluding only two timing fields and the three newly added diagnostics. These are recorded-output checks, not proof of complete hidden-state equivalence. Parent arithmetic does not import the simulator or reuse the shared case validator.

Maximum formal money residual: 0.0000716224 (timing); maximum clearing residual: 0.0000000154064. Both remain below the frozen tolerance. This is evidence for the panel's defined money/account boundaries, not a universal conservation proof. Parent completion-event arithmetic independently checks the yearly gain constraint. Raw cases and source/worker manifests are preserved.

A fresh read-only Sol results review reproduced 228 checked table/endpoint values, the seed-direction claims, research/quality/pause diagnostics and all 16 paired timing estimates/intervals. It also reverified all 654 manifest hashes and the accounting/yearly-quality bounds. It found no material selected-results defect or omitted adverse outcome. One minor label was corrected: the earlier Windows failures were platform failures, not Git-bridge failures. The review checked saved test receipts and did not rerun tests or simulations. Its scope does not certify the incomplete pstack workflow.

The final configured Linux suite previously passed **1,502 tests**, with two skips, eight deselections and one expected failure. The cash funding focused selection passed 195 tests. These receipts cover implementation source 362237b; no source changed during/after the panels. See [QUALITY_CASH_VALIDATION.md](QUALITY_CASH_VALIDATION.md) for debt/current and old payroll/CEO/restricted-cash/recipient proofs and the corrected numerical stall. These are Linux full-suite results, not a claim that the earlier Windows platform failures disappeared: that prior attempt recorded 68 Unix-only SIGALRM failures and three default-encoding failures. Household wage receipts use the completed wage ledger and can include funded older claims; they are not just current earned payroll.

Pstack certification remains incomplete. The delegate's pre-review exits 3 (blocked), with unavailable Cursor create-skill substitution and transcript-audit gaps recorded; the older parent workflow is also incomplete. No full protocol pass is asserted. These process gaps are separate from the passing source, test and panel checks.

Source/default status: local branch only; `instant` remains the default. No push, PR, merge, release, new banking behavior or GitHub Actions run was performed. Actions remain disabled. OpenWiki refresh remains due because approved local tooling is unavailable and generated pages were not hand-edited.

## Reproduction and evidence

External evidence directory: `C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/research-spending-followup/`.

- Worker receipt: `RUN_RECEIPT.md`, `run-receipt.json`, `evidence-checks.json`.
- Frozen inputs/outputs: `economy/`, `performance/`, `sources/candidate/`; prior frozen main remains in `quality-research-experiment/sources/baseline/`.
- Worker artifact manifest: `artifact-manifest.json`, SHA-256 `3be6cf06aed86f06cc669e01992464b5ccf4aad9fa4629e3fa33fffb53775859`; 429 local, 213 separate baseline and 12 prior control entries verified.
- Independent parent arithmetic: `parent_analysis.py`, `parent-analysis.json`, `parent-economy.csv`, `parent-contrasts.csv`, `parent-timing.csv`. The script creates new files exclusively to preserve evidence; rerunning requires a fresh output location/version.
- Report renderer: `build_parent_report.py`; owner comparison: `cash-research-comparison.html`.
- Independent results review: `parent-results-review.md`; parent completion snapshot: `parent-final-manifest.json`.
- Decisions: immutable worker-era `decisions.tsv` plus append-only `parent-decisions.tsv`; validation logs and pilot remain separate from final panels.

The next product conversation can select a default from the tested mechanisms with these tradeoffs visible. No further household, bank, wage or Housing changes are bundled into that decision.

