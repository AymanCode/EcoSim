# BANK-STARTUP-01: 1,000-household exploratory comparison

Status: local implementation and exploratory evidence; parent interpretation pending. No real-world forecast, welfare calibration, benefits fix, or 5% integrated performance acceptance is established. The owner clarified that an approved bank-funded recurring entrant can remain ownerless; a founder is required when using founder-equity fallback.

## Outcomes: income_first, then income_late

In income_first, happiness fell in all six seed/policy comparisons in weeks 60-80 and in five of six in weeks 104-140; GDP rose in two and three comparisons respectively. In income_late, happiness fell in all six comparisons in both windows; GDP fell in all six early comparisons and rose in three late comparisons. Pooled benefit dollars per eligible fell in every comparison across both windows. These are within-model observations, with genuine GDP and household tradeoffs, not a causal welfare claim.

Each cell is the mean across completed weekly ticks in the stated inclusive window, shown old → new. GDP is the nominal sales/revenue proxy; happiness is a 0–1 mean. Benefit dollars per eligible are the pooled sum paid / sum eligible at `settle_benefits`, including eligible zero recipients. Full weekly and subgroup measures are retained in the machine-readable files.

| Sequence | Benefits | Seed | Window | Nominal GDP old → new | Happiness old → new | Employed old → new | Benefit $/eligible old → new |
|---|---|---:|---|---:|---:|---:|---:|
| income_first | neutral | 4242 | 60-80 | 34,302.5 → 35,465.6 | 0.5205 → 0.5031 | 431.7 → 447.0 | 24.30 → 19.12 |
| income_first | neutral | 4242 | 104-140 | 30,696.4 → 41,058.1 | 0.4044 → 0.4134 | 401.5 → 535.3 | 21.31 → 19.99 |
| income_first | neutral | 101 | 60-80 | 36,088.2 → 33,396.6 | 0.5099 → 0.4747 | 437.1 → 420.0 | 25.18 → 17.48 |
| income_first | neutral | 101 | 104-140 | 41,369.0 → 37,993.9 | 0.4641 → 0.3876 | 489.0 → 491.2 | 28.82 → 18.21 |
| income_first | neutral | 777 | 60-80 | 34,777.8 → 34,312.1 | 0.5359 → 0.5061 | 445.0 → 441.7 | 23.14 → 16.60 |
| income_first | neutral | 777 | 104-140 | 35,588.1 → 38,891.2 | 0.4242 → 0.4073 | 436.8 → 503.4 | 22.53 → 16.93 |
| income_first | high | 4242 | 60-80 | 38,487.3 → 36,461.1 | 0.5152 → 0.5037 | 403.6 → 375.1 | 21.16 → 15.51 |
| income_first | high | 4242 | 104-140 | 43,494.8 → 42,415.1 | 0.4103 → 0.3690 | 464.6 → 473.9 | 25.66 → 17.81 |
| income_first | high | 101 | 60-80 | 39,867.6 → 41,495.0 | 0.5296 → 0.5230 | 413.3 → 425.0 | 23.43 → 19.74 |
| income_first | high | 101 | 104-140 | 48,342.2 → 48,119.7 | 0.4498 → 0.4304 | 507.8 → 527.2 | 32.33 → 25.32 |
| income_first | high | 777 | 60-80 | 39,984.7 → 37,213.4 | 0.5232 → 0.5070 | 415.0 → 393.5 | 21.78 → 15.50 |
| income_first | high | 777 | 104-140 | 42,942.0 → 43,766.1 | 0.4030 → 0.3807 | 451.2 → 482.6 | 24.40 → 17.92 |
| income_late | neutral | 4242 | 60-80 | 34,011.7 → 32,738.6 | 0.5211 → 0.4971 | 433.7 → 417.5 | 24.31 → 17.91 |
| income_late | neutral | 4242 | 104-140 | 28,896.3 → 38,540.7 | 0.4032 → 0.3907 | 382.2 → 506.1 | 20.60 → 18.61 |
| income_late | neutral | 101 | 60-80 | 36,224.7 → 31,103.9 | 0.5028 → 0.4667 | 437.4 → 397.3 | 25.22 → 16.64 |
| income_late | neutral | 101 | 104-140 | 41,298.2 → 36,218.0 | 0.4425 → 0.3649 | 485.1 → 471.2 | 28.93 → 17.27 |
| income_late | neutral | 777 | 60-80 | 33,909.4 → 31,136.8 | 0.5270 → 0.4946 | 428.8 → 408.8 | 22.35 → 15.65 |
| income_late | neutral | 777 | 104-140 | 33,260.0 → 35,359.0 | 0.4012 → 0.3778 | 407.2 → 462.7 | 20.88 → 15.23 |
| income_late | high | 4242 | 60-80 | 34,784.0 → 31,218.2 | 0.5070 → 0.4890 | 372.7 → 338.1 | 20.06 → 14.01 |
| income_late | high | 4242 | 104-140 | 36,699.6 → 36,714.1 | 0.3727 → 0.3400 | 404.4 → 431.9 | 21.60 → 15.71 |
| income_late | high | 101 | 60-80 | 38,261.5 → 37,818.1 | 0.5133 → 0.4986 | 400.5 → 398.6 | 22.81 → 18.39 |
| income_late | high | 101 | 104-140 | 48,218.6 → 45,850.8 | 0.4344 → 0.4037 | 506.3 → 508.8 | 32.31 → 23.77 |
| income_late | high | 777 | 60-80 | 36,647.3 → 33,441.4 | 0.5115 → 0.4786 | 393.3 → 365.5 | 20.56 → 14.59 |
| income_late | high | 777 | 104-140 | 39,640.3 → 38,070.6 | 0.3761 → 0.3491 | 422.4 → 436.2 | 22.49 → 15.59 |

Other new-minus-old outcomes below show the minimum to maximum of the six seed/policy window means within each sequence. Housing is the count of households with `met_housing_need`, care is completed weekly visits, and the low-cash subgroup is fixed at setup.

| Sequence | Window | Mean price | Food and Services units sold | Housing met | Care visits | Mean health | Initial low-cash happiness | Initial low-cash liquid wealth |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| income_first | 60-80 | -0.24 to 0.68 | -163.9 to 140.2 | -177.8 to -55.8 | -3.8 to -0.2 | -0.0127 to 0.0013 | -0.0229 to 0.0008 | 423.8 to 912.1 |
| income_first | 104-140 | -2.94 to -0.25 | -18.1 to 715.2 | -198.4 to -17.7 | -19.4 to 5.2 | -0.0724 to 0.0043 | -0.0242 to 0.0189 | 264.2 to 959.1 |
| income_late | 60-80 | -0.31 to 0.54 | -331.2 to -108.0 | -16.0 to -6.3 | -3.4 to -0.6 | -0.0490 to -0.0201 | -0.0181 to -0.0048 | 440.1 to 872.2 |
| income_late | 104-140 | -2.98 to -0.35 | -324.5 to 586.7 | -88.4 to -13.7 | -20.2 to 3.2 | -0.2148 to -0.1115 | -0.0280 to -0.0012 | 206.6 to 777.7 |

High minus neutral, within version and seed (weekly window means):

| Sequence | Version | Seed | Window | GDP Δ | Happiness Δ | Benefit $/eligible Δ |
|---|---|---:|---|---:|---:|---:|
| income_first | old | 4242 | 60-80 | 4,184.8 | -0.0053 | -3.14 |
| income_first | old | 4242 | 104-140 | 12,798.4 | 0.0059 | 4.35 |
| income_first | new | 4242 | 60-80 | 995.5 | 0.0006 | -3.61 |
| income_first | new | 4242 | 104-140 | 1,356.9 | -0.0444 | -2.18 |
| income_first | old | 101 | 60-80 | 3,779.4 | 0.0197 | -1.75 |
| income_first | old | 101 | 104-140 | 6,973.3 | -0.0143 | 3.50 |
| income_first | new | 101 | 60-80 | 8,098.5 | 0.0483 | 2.26 |
| income_first | new | 101 | 104-140 | 10,125.8 | 0.0429 | 7.11 |
| income_first | old | 777 | 60-80 | 5,206.9 | -0.0128 | -1.36 |
| income_first | old | 777 | 104-140 | 7,353.9 | -0.0211 | 1.87 |
| income_first | new | 777 | 60-80 | 2,901.3 | 0.0009 | -1.10 |
| income_first | new | 777 | 104-140 | 4,874.9 | -0.0266 | 0.99 |
| income_late | old | 4242 | 60-80 | 772.3 | -0.0141 | -4.25 |
| income_late | old | 4242 | 104-140 | 7,803.3 | -0.0306 | 1.00 |
| income_late | new | 4242 | 60-80 | -1,520.4 | -0.0081 | -3.90 |
| income_late | new | 4242 | 104-140 | -1,826.6 | -0.0508 | -2.90 |
| income_late | old | 101 | 60-80 | 2,036.8 | 0.0105 | -2.41 |
| income_late | old | 101 | 104-140 | 6,920.4 | -0.0081 | 3.38 |
| income_late | new | 101 | 60-80 | 6,714.3 | 0.0319 | 1.75 |
| income_late | new | 101 | 104-140 | 9,632.8 | 0.0388 | 6.50 |
| income_late | old | 777 | 60-80 | 2,738.0 | -0.0155 | -1.79 |
| income_late | old | 777 | 104-140 | 6,380.3 | -0.0251 | 1.61 |
| income_late | new | 777 | 60-80 | 2,304.6 | -0.0160 | -1.06 |
| income_late | new | 777 | 104-140 | 2,711.6 | -0.0287 | 0.36 |

| Sequence | Benefits | Seed | Window | Eligible old -> new | Paid old -> new | Denied old -> new | Weekly mean $/eligible old -> new | Pooled $/eligible old -> new | Pooled coverage old -> new |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| income_first | neutral | 4242 | 60-80 | 568.3 -> 553.0 | 13,813.0 -> 10,571.0 | 3,237.0 -> 6,017.5 | 24.32 -> 19.13 | 24.30 -> 19.12 | 1.000 -> 1.000 |
| income_first | neutral | 4242 | 104-140 | 598.5 -> 464.7 | 12,754.2 -> 9,289.4 | 5,201.2 -> 4,650.9 | 21.31 -> 20.14 | 21.31 -> 19.99 | 1.000 -> 1.000 |
| income_first | neutral | 101 | 60-80 | 562.9 -> 580.0 | 14,174.2 -> 10,139.5 | 2,711.6 -> 7,261.9 | 25.19 -> 17.49 | 25.18 -> 17.48 | 1.000 -> 1.000 |
| income_first | neutral | 101 | 104-140 | 511.0 -> 508.8 | 14,729.2 -> 9,264.7 | 600.8 -> 5,998.8 | 28.90 -> 18.30 | 28.82 -> 18.21 | 1.000 -> 1.000 |
| income_first | neutral | 777 | 60-80 | 555.0 -> 558.3 | 12,844.5 -> 9,265.5 | 3,805.5 -> 7,483.1 | 23.15 -> 16.60 | 23.14 -> 16.60 | 1.000 -> 1.000 |
| income_first | neutral | 777 | 104-140 | 563.2 -> 496.6 | 12,690.7 -> 8,409.6 | 4,206.6 -> 6,488.2 | 22.55 -> 17.02 | 22.53 -> 16.93 | 1.000 -> 1.000 |
| income_first | high | 4242 | 60-80 | 596.4 -> 624.9 | 12,620.6 -> 9,688.6 | 14,216.5 -> 18,429.9 | 21.17 -> 15.52 | 21.16 -> 15.51 | 1.000 -> 1.000 |
| income_first | high | 4242 | 104-140 | 535.4 -> 526.1 | 13,738.2 -> 9,372.1 | 10,352.6 -> 14,304.0 | 25.77 -> 17.98 | 25.66 -> 17.81 | 1.000 -> 1.000 |
| income_first | high | 101 | 60-80 | 586.7 -> 575.0 | 13,747.9 -> 11,353.2 | 12,652.1 -> 14,523.9 | 23.44 -> 19.75 | 23.43 -> 19.74 | 1.000 -> 1.000 |
| income_first | high | 101 | 104-140 | 492.2 -> 472.8 | 15,910.4 -> 11,968.7 | 6,236.9 -> 9,306.5 | 32.54 -> 25.50 | 32.33 -> 25.32 | 1.000 -> 1.000 |
| income_first | high | 777 | 60-80 | 585.0 -> 606.5 | 12,741.4 -> 9,400.8 | 13,583.6 -> 17,890.7 | 21.79 -> 15.50 | 21.78 -> 15.50 | 1.000 -> 1.000 |
| income_first | high | 777 | 104-140 | 548.8 -> 517.4 | 13,388.1 -> 9,273.2 | 11,305.9 -> 14,007.6 | 24.44 -> 18.03 | 24.40 -> 17.92 | 1.000 -> 1.000 |
| income_late | neutral | 4242 | 60-80 | 566.3 -> 582.5 | 13,767.3 -> 10,432.1 | 3,222.7 -> 7,043.6 | 24.32 -> 17.92 | 24.31 -> 17.91 | 1.000 -> 1.000 |
| income_late | neutral | 4242 | 104-140 | 617.8 -> 493.9 | 12,726.1 -> 9,191.0 | 5,808.2 -> 5,624.9 | 20.61 -> 18.78 | 20.60 -> 18.61 | 1.000 -> 1.000 |
| income_late | neutral | 101 | 60-80 | 562.6 -> 602.7 | 14,190.3 -> 10,026.6 | 2,688.2 -> 8,053.4 | 25.23 -> 16.65 | 25.22 -> 16.64 | 1.000 -> 1.000 |
| income_late | neutral | 101 | 104-140 | 514.9 -> 528.8 | 14,897.3 -> 9,133.1 | 551.0 -> 6,730.4 | 28.98 -> 17.46 | 28.93 -> 17.27 | 1.000 -> 1.000 |
| income_late | neutral | 777 | 60-80 | 571.2 -> 591.2 | 12,767.3 -> 9,252.0 | 4,368.4 -> 8,483.8 | 22.38 -> 15.67 | 22.35 -> 15.65 | 1.000 -> 1.000 |
| income_late | neutral | 777 | 104-140 | 592.8 -> 537.3 | 12,378.0 -> 8,183.3 | 5,405.5 -> 7,934.8 | 20.90 -> 15.32 | 20.88 -> 15.23 | 1.000 -> 1.000 |
| income_late | high | 4242 | 60-80 | 627.3 -> 661.9 | 12,583.3 -> 9,272.1 | 15,646.7 -> 20,511.4 | 20.07 -> 14.04 | 20.06 -> 14.01 | 1.000 -> 1.000 |
| income_late | high | 4242 | 104-140 | 595.6 -> 568.1 | 12,862.0 -> 8,924.0 | 13,939.8 -> 16,640.9 | 21.62 -> 15.86 | 21.60 -> 15.71 | 1.000 -> 1.000 |
| income_late | high | 101 | 60-80 | 599.5 -> 601.4 | 13,672.4 -> 11,057.0 | 13,304.1 -> 16,005.1 | 22.82 -> 18.39 | 22.81 -> 18.39 | 1.000 -> 1.000 |
| income_late | high | 101 | 104-140 | 493.7 -> 491.2 | 15,949.9 -> 11,678.4 | 6,266.8 -> 10,427.6 | 32.58 -> 23.98 | 32.31 -> 23.77 | 1.000 -> 1.000 |
| income_late | high | 777 | 60-80 | 606.7 -> 634.5 | 12,473.9 -> 9,255.6 | 14,826.1 -> 19,298.0 | 20.57 -> 14.59 | 20.56 -> 14.59 | 1.000 -> 1.000 |
| income_late | high | 777 | 104-140 | 577.6 -> 563.8 | 12,992.8 -> 8,792.9 | 13,001.4 -> 16,579.8 | 22.59 -> 15.65 | 22.49 -> 15.59 | 1.000 -> 1.000 |

Paid, denied, and eligible are weekly means; pooled coverage is total positive recipients divided by total eligible person-weeks. A positive partial payment counts as a recipient, so full recipient coverage does not mean the requested amount was fully paid.

The benefits Compare question remains parked. The restriction/headcount and Misc payout behavior were not changed; lower or higher measured payments here do not establish a benefits fix. Welcome stimulus is reported separately in weekly data.

## Banking and reconciliation

| Sequence | Benefits | Seed | Bank startup approvals / refusals | Bank principal originated | Principal repaid | Interest paid | Principal / interest written off | Final startup principal | Treasury startup outflow, old | Founder equity, old → new |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| income_first | neutral | 4242 | 26 / 0 | 650,000.0 | 383,452.3 | 62,906.2 | 0.0 / 0.0 | 266,547.7 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_first | neutral | 101 | 26 / 0 | 650,000.0 | 383,102.2 | 62,907.2 | 0.0 / 0.0 | 266,897.8 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_first | neutral | 777 | 26 / 0 | 650,000.0 | 379,408.6 | 62,537.7 | 14,314.5 / 0.0 | 256,276.9 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_first | high | 4242 | 26 / 0 | 650,000.0 | 383,213.1 | 62,906.4 | 0.0 / 0.0 | 266,786.9 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_first | high | 101 | 26 / 0 | 650,000.0 | 379,413.8 | 62,491.0 | 14,309.3 / 0.0 | 256,276.9 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_first | high | 777 | 26 / 0 | 650,000.0 | 380,394.7 | 62,607.1 | 13,328.4 / 0.0 | 256,276.9 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_late | neutral | 4242 | 26 / 0 | 650,000.0 | 383,452.3 | 62,906.2 | 0.0 / 0.0 | 266,547.7 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_late | neutral | 101 | 26 / 0 | 650,000.0 | 383,158.7 | 62,906.7 | 0.0 / 0.0 | 266,841.3 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_late | neutral | 777 | 26 / 0 | 650,000.0 | 379,678.7 | 62,551.0 | 14,044.4 / 0.0 | 256,276.9 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_late | high | 4242 | 26 / 0 | 650,000.0 | 382,548.7 | 62,905.0 | 11,051.3 / 4.3 | 256,400.0 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_late | high | 101 | 26 / 0 | 650,000.0 | 379,562.6 | 62,521.1 | 14,160.5 / 0.0 | 256,276.9 | 650,000.0 | 5,000.0 → 5,000.0 |
| income_late | high | 777 | 26 / 0 | 650,000.0 | 379,861.1 | 62,550.5 | 13,862.0 / 0.0 | 256,276.9 | 650,000.0 | 5,000.0 → 5,000.0 |

Across all 26 cases, maximum startup principal residual is `5.82076609e-10`; maximum bank/firm origination cash-pair residual is `0`; maximum claim count mismatch is `0` and principal mismatch `0`. Maximum clearing cash magnitude is `4.65661287e-10`; maximum global net-of-injections money drift is `2.93180346e-06`. These are diagnostics under the existing model and do not by themselves establish full economy conservation.

All 12 enabled primary cases approved 26 queued requests of 25,000 each and recorded no refusals. No recurring 20,000 or 30,000 bank-startup request occurred in this panel; that route has focused tests, not economy-panel exposure.

Old Treasury startup credit is a direct pooled claim. The retained `treasury_startup_pooled_repayments` and outstanding amounts track that firm pool, which can also contain later direct credit; they are not attributed solely to startup principal or split into principal and interest. Bank startup claims use the registered amortizing v2 book and actual bank funder. Queued firms’ 10,000 opening endowments are not loan flows. Deposits are not added to bank reserves a second time.

## Exposure, method, and controls

Experiment flag defaults true on this branch; false restores the prior named entry/activation behavior, and `payment_sequence="legacy"` remains unchanged. Eligible pre-operating private firms can receive one bank-only claim, capped at 30,000 and 208 ticks. Queued activation requests 25,000/208; recurring credit tiers request 30,000 or 20,000/156. A denied recurring request may fall back to founder equity, and a failed fallback publishes no entrant. The shared v2 ledger treats principal at or below its 1e-6 currency tolerance as zero and refuses it; the selected routes request at least 20,000. Ordinary credit underwriting and other products retain their existing rules. Startup rates use the existing risk-adjusted bank quote plus the configured new-loan shift; amortizing interest is different from the old Treasury total-due convention.

Each case uses 1,000 households, five requested firms per category, 140 completed ticks, 10 warmup ticks, normal mode, LLM off, and standard stabilizers. Two workers ran separately with `PYTHONHASHSEED=0`. Inclusive windows are 60–80 and 104–140; full weekly rows, warmup week 10, first post-warmup week 11, initial profiles and IDs, RNG state, and final snapshots are retained. Initial nonworking means no employer at setup; initial low-cash is the lowest quartile of liquid wealth, ties by ID. Subgroups remain fixed even when members change employment or resources.

Initial profile/RNG, initial component, and full resolved configuration except the added flag match in 12/12 old/new pairings. The comparison excludes only the new flag and startup-only firm fields. Component digests cover the evaluator’s documented projections and do not prove equality of every internal model field.
- `income_first-neutral-4242-new-flag-off`: initial profiles/RNG pass; all 140 component projections pass; weekly rows pass; observed events pass.
- `income_first-neutral-4242-old-replay`: initial profiles/RNG pass; all 140 component projections pass; weekly rows pass; observed events pass.

Firm IDs are retained each tick for entry and survival checks. The old allocator can recycle a departed ID, so an old-source final-ID survival count can overstate continuity; the enabled named entry route uses a monotonic private counter. Other entity allocation paths are not globally redesigned. Concurrent two-worker timing is descriptive; per-case memory was not recorded and this is not an integrated speed test.

The primary mechanism source is [Robb and Robinson, The Capital Structure Decisions of New Firms, NBER Working Paper 16272](https://www.nber.org/papers/w16272). It documents outside debt, including bank debt, among first-year firms; it does not calibrate the simulator’s amount, interest rate, risk, or economic effects.

## Verification and artifacts

Focused and affected contract/server/integration tests: 165 passed. Ruff passed for touched Python, and `git diff --check` passed. The later separate mortgage exclusion probe passed for both named sequences. Earlier failed test-fixture logs, observer revisions, and interrupted panel attempts are preserved in the artifacts; the completed primary results use one consistent frozen evaluator.

Artifact root: `C:\Users\ayman\.t3\userdata\artifacts\ecosim-bank-startup-loans-20261028-034219`. `manifest.json` contains source/evaluator SHA-256 hashes and runtime configuration; `candidate-v5-source.zip` is the frozen candidate. `cases/` contains complete per-case rows, events, initial profiles/RNG and state-component digests; `weekly.csv`, `comparisons.csv`, and `summary.json` provide common machine-readable output. Full logs and the incomplete attempts are retained. To reproduce the final resumed panel from its manifest: `python C:\Users\ayman\.t3\userdata\artifacts\ecosim-bank-startup-loans-20261028-034219\resume_missing.py C:\Users\ayman\.t3\userdata\artifacts\ecosim-bank-startup-loans-20261028-034219`; the original evaluator runner is `candidate-v5/backend/tools/benchmarks/run_bank_startup_panel.py`. The resume command skips already completed case files.

OpenWiki refresh is due; generated wiki files were not hand-edited and the manual GitHub Actions refresh was prohibited.
