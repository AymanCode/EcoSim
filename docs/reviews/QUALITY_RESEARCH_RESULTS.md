# Food and Services quality research results

Measured on 2026-10-27 UTC against frozen sources for QUALITY-RESEARCH-01. These results inform the choice of an opt-in model. They do not select a new default or establish calibration.

The compatibility default remains `instant`. A is `project_outcome`, B is `project_cost`, and `scale_only` is the no-research control on the new starting scale. All three new models remain opt-in. This worker changed only this report in the repository and preserved the simulator, tests, contracts, frozen sources, and measurement scripts.

## Measured outcome

All 18 new-model economy cases have lower late-window nominal GDP than their matched original baseline. Happiness is mixed. Under income_first, A lowers happiness in all three seeds and B raises it only in seed 43. Under income_late, both project variants raise happiness only in seed 43. Neither variant has a uniform GDP-and-wellbeing benefit.

A produces higher final mean private quality than B in every matched seed. Its final means range from 1.790 to 2.169, versus 1.386 to 1.776 for B. No new-model private firm reaches raw quality 9.5. The highest observed raw quality is 4.426. These are economy observations, separate from the fully funded probe.

The table counts late-window improvements against each arm's matched original baseline. A count of three means all three seeds improved on that measure. It does not establish an overall benefit.

| Sequence | Arm | GDP higher | Happiness higher | Jobs higher | Food units higher | Services units higher |
| --- | --- | --- | --- | --- | --- | --- |
| income_first | scale_only | 0 | 0 | 0 | 2 | 0 |
| income_first | project_outcome | 0 | 0 | 0 | 1 | 0 |
| income_first | project_cost | 0 | 1 | 0 | 1 | 0 |
| income_late | scale_only | 0 | 0 | 0 | 1 | 0 |
| income_late | project_outcome | 0 | 1 | 0 | 1 | 0 |
| income_late | project_cost | 0 | 1 | 0 | 1 | 0 |

Paired late-window changes below give the mean across three seeds and their minimum and maximum in brackets. The complete per-seed values follow later.

| Sequence | Arm | Compared with | GDP change % | Food units change % | Services units change % | Jobs change | Happiness change |
| --- | --- | --- | --- | --- | --- | --- | --- |
| income_first | scale_only | baseline | -24.71 [-30.78, -18.84] | -1.73 [-10.21, 4.01] | -33.62 [-45.29, -19.84] | -187.66 [-283.34, -107.88] | -0.0450 [-0.0535, -0.0318] |
| income_first | project_outcome | baseline | -17.83 [-21.33, -12.10] | -3.46 [-9.06, 2.37] | -25.90 [-34.83, -12.46] | -160.28 [-223.71, -74.36] | -0.0529 [-0.0806, -0.0301] |
| income_first | project_cost | baseline | -15.74 [-26.97, -2.92] | -1.59 [-6.57, 5.34] | -20.52 [-30.41, -8.35] | -133.05 [-193.19, -39.46] | -0.0283 [-0.1180, 0.0511] |
| income_first | project_outcome | scale_only | 9.28 [5.88, 13.66] | -1.65 [-4.65, 1.28] | 12.20 [8.28, 19.12] | 27.38 [-11.01, 59.63] | -0.0080 [-0.0272, 0.0017] |
| income_first | project_cost | scale_only | 11.92 [-3.28, 19.63] | 0.28 [-4.50, 4.06] | 22.03 [-3.70, 42.58] | 54.60 [-58.63, 132.29] | 0.0167 [-0.0646, 0.0829] |
| income_late | scale_only | baseline | -25.34 [-38.01, -15.34] | -5.37 [-21.08, 5.03] | -33.14 [-48.88, -22.37] | -194.44 [-323.62, -124.02] | -0.0432 [-0.0602, -0.0108] |
| income_late | project_outcome | baseline | -18.62 [-34.55, -4.61] | -8.64 [-25.91, 3.58] | -23.17 [-36.55, -15.24] | -156.37 [-265.23, -92.92] | -0.0395 [-0.0820, 0.0146] |
| income_late | project_cost | baseline | -22.63 [-37.03, -10.96] | -8.30 [-26.03, 3.22] | -32.38 [-42.63, -25.08] | -201.20 [-293.47, -133.78] | -0.0574 [-0.1269, 0.0107] |
| income_late | project_outcome | scale_only | 8.67 [5.58, 12.67] | -3.68 [-6.12, -1.39] | 16.03 [6.00, 24.12] | 38.07 [24.73, 58.39] | 0.0037 [-0.0235, 0.0254] |
| income_late | project_cost | scale_only | 3.46 [1.59, 5.17] | -3.34 [-6.27, -1.73] | 2.47 [-9.11, 12.23] | -6.76 [-52.33, 30.15] | -0.0142 [-0.0684, 0.0215] |

GDP is the nominal sales proxy `sum(last_tick_revenue.values())`. Real delivered units, access, employment, and wellbeing therefore remain separate evidence. A higher GDP value alone does not endorse an arm.

Scale-only changes starting quality and removes instant Food and Services research together. Its baseline contrast does not isolate starting quality. Project contrasts with scale-only include research costs, quality gains, and recipient transfers. A versus B bundles cost, duration, outcome odds, and gain curve. It does not isolate elasticity.

All constants are experimental. No parameters or household utility were tuned to raise GDP or happiness. The earlier Housing capital patch remains parked.

## Sources and completed evidence

The worktree starts at `7acf1e47f08a98292b6b8e96e8536a8e53696c97`. Its locally recorded `origin/main` is `8a8d38005d914681ad95bc82d6b3523793be03be`, with three commits ahead and zero behind. The parent supplied its same-turn fetch evidence. This worker used no network.

The baseline capture contains 212 backend files from `8a8d38005d914681ad95bc82d6b3523793be03be`. The candidate contains 216 from implementation `6673c4ab8c11393b1d23c8c3825f144b50454f29`. Every captured file matches its manifest and its local Git object. Current HEAD's backend also matches the candidate capture.

The factory opens Treasury cash at 3,000 per household, wage tax at 15%, profit tax at 20%, and unemployment benefits and transfer budget at zero. The benchmark helper only suppresses factory output. These fixed factory conditions are not a claim about every town setup. The investment-tax rate remains 10%.

[Preflight hashes and retained-evidence hashes](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/preflight.json). [Independent Git-content check](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/source-git-check.json). [Readiness record](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/harness-ready.json).

The economy panel completed 24 cases and 12,480 formal ticks. Each sequence has seeds 42, 43, and 44, 1,000 initial households, four arms, and 520 weekly ticks. The timing panel completed 60 cases and 4,800 ticks. It uses both sequences, 1,000 and 10,000 households, one seed, three arms, five repeats, and 80 ticks.

The original analyzer validates all case identities, complete tick sequences, worker hashes, source manifests, comparable config, initial non-quality profiles, initial RNG, and common new-model starting quality. The supplementary analysis independently checks case counts, exact windows, quality bounds, observed completion gains, and the rolling 52-tick gain cap. The 25 existing validator-only integrity diagnostics also passed before execution. They ran no simulations.

[Economy protocol](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/economy/protocol.json). [Economy analyzer result](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/economy/analysis.json). [Economy details](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/economy-details.json). [All per-seed metrics](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/economy-per-case.csv).

[Performance protocol](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/performance/protocol.json). [Performance analyzer result](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/performance/analysis.json). [Performance details](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/performance-details.json).

The parent reran the shared `panel.validate_case` for all 84 cases. Separate parent code recomputed headline late GDP/Services/jobs/happiness comparisons and all runtime intervals, and verified the 695 worker artifact hashes before these documentation corrections. The case-validation implementation itself is shared, not independently reimplemented. [Parent arithmetic and hash checks](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/parent-review.json). [Household and pause recomputation](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/parent-corrections/household-check.json).

The retained default replay matched all recorded economic fields, comparable config, and initial and final RNG for 20 real ticks per source and named sequence. This is 80 replay ticks, not full hidden-state equivalence. [Replay evidence](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/default-compatibility/analysis.json).

The retained fully funded firm-method probe has 200 trajectories per model and starting quality, 14 cells, and 520 ticks. At starting quality 0.61, final means are 3.7039 for A and 3.1807 for B. At starting quality 9, they are 9.1298 and 9.2003. Source, script, upper-range, and rolling-gain checks pass. These are not economy runs. [Quality-only evidence](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/quality-probe.json).

Parent validation remains separate. Its independent focused review passed 149 cases. The preserved configured Linux suite reports 1,456 passed, two skipped, eight deselected, and one expected failure in 178.32 seconds. The earlier Windows log retains 68 SIGALRM and three encoding failures. This worker made no environment-related product change and did not rerun those suites. [Linux suite log](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/validation/full-tests-linux-1.log). [Windows failure log](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/validation/full-tests-1.log).

## Late weeks and final values

Each paired cell gives the mean over weeks 421 through 520, then the final week-520 value, separated by a semicolon. Units are model currency per week for GDP and wages, model units per week for delivery, households for access and jobs, and dimensionless scores for happiness and health. No row averages away a seed.

The housing-rule exclusion does not imply unchanged housing outcomes. In seed 44, late-window households meeting housing need fall from 992.4 to 591.4 / 703.8 / 770.0 under scale-only / A / B in income_first, and from 993.4 to 620.3 / 802.7 / 757.0 in income_late. These are counts out of 1,000. Health and Services access fall in those cells too. The loss also occurs without project research, so funded projects are not necessary for it; they may still change its severity. Starting quality and removal of instant research transfers remain joint candidate explanations, not identified causes.

Across all 18 new-model cases, late household deposits are 12.7%–59.6% lower, active-firm cash 4.1%–32.7% higher, and Treasury cash 12.5%–93.2% lower than matched baseline. Household cash falls in 17 cases. These are shifts in stocks across different runs, not identified direct transfers. Outstanding wage claims fall 35.9%–46.3% in every case alongside lower employment; payroll reliability has not been isolated. These effects belong beside GDP and happiness when judging the experiment.

Food and Services access count households with positive delivered units, not complete fulfillment of needs. Housing access uses `met_housing_need`. The unchanged happiness calculation rewards food sufficiency, Services use, housing, and wage satisfaction. It does not directly reward raw product quality, so this score does not value every quality benefit.

### income_first

| Seed | Arm | GDP | Happiness | Health | Jobs | Food units | Services units |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | baseline | 55,121; 50,984 | 0.3568; 0.3055 | 0.6189; 0.6248 | 934.8; 935.0 | 3,639.1; 3,671.0 | 2,440.9; 2,390.6 |
| 42 | scale_only | 41,622; 39,554 | 0.3033; 0.2660 | 0.6248; 0.6286 | 827.0; 799.0 | 3,675.9; 3,630.8 | 1,956.7; 1,885.9 |
| 42 | project_outcome | 44,069; 45,489 | 0.2762; 0.2459 | 0.6208; 0.6254 | 860.5; 822.0 | 3,504.9; 3,670.5 | 2,136.9; 2,064.3 |
| 42 | project_cost | 40,257; 38,818 | 0.2388; 0.1885 | 0.6192; 0.6234 | 768.3; 731.0 | 3,510.5; 3,546.9 | 1,884.4; 1,699.0 |
| 43 | baseline | 44,256; 40,191 | 0.2436; 0.2075 | 0.6149; 0.6172 | 869.5; 838.0 | 3,396.3; 3,258.2 | 2,090.0; 1,953.5 |
| 43 | scale_only | 35,916; 30,477 | 0.2118; 0.1449 | 0.6176; 0.5957 | 697.7; 605.0 | 3,532.3; 3,442.1 | 1,343.4; 1,051.4 |
| 43 | project_outcome | 38,900; 33,745 | 0.2135; 0.1634 | 0.6149; 0.5864 | 686.7; 617.0 | 3,476.6; 3,321.6 | 1,454.6; 1,244.2 |
| 43 | project_cost | 42,965; 39,273 | 0.2947; 0.2605 | 0.6256; 0.6275 | 830.0; 778.0 | 3,577.8; 3,401.2 | 1,915.4; 1,785.5 |
| 44 | baseline | 37,160; 36,908 | 0.2070; 0.1824 | 0.6094; 0.6204 | 786.5; 743.0 | 3,460.9; 3,639.2 | 1,848.4; 1,718.5 |
| 44 | scale_only | 25,721; 20,310 | 0.1573; 0.1195 | 0.5254; 0.4669 | 503.2; 417.0 | 3,107.4; 2,658.5 | 1,011.2; 744.4 |
| 44 | project_outcome | 29,233; 25,449 | 0.1589; 0.1267 | 0.5203; 0.4742 | 562.8; 485.0 | 3,147.3; 3,047.9 | 1,204.6; 920.8 |
| 44 | project_cost | 30,717; 27,560 | 0.1890; 0.1445 | 0.5577; 0.5054 | 593.3; 552.0 | 3,233.5; 3,032.2 | 1,286.4; 1,124.3 |

| Seed | Arm | Food access | Services access | Housing access | Funded wage receipts | Wage claims | Dividends |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | baseline | 1,000.0; 1,000.0 | 991.0; 990.0 | 994.4; 990.0 | 48,822; 45,903 | 486,202; 498,401 | 5,450; 4,692 |
| 42 | scale_only | 1,000.0; 1,000.0 | 996.6; 996.0 | 1,000.0; 1,000.0 | 39,550; 38,280 | 305,946; 306,305 | 3,948; 3,722 |
| 42 | project_outcome | 1,000.0; 1,000.0 | 996.9; 1,000.0 | 999.1; 1,000.0 | 40,856; 39,353 | 296,182; 297,226 | 4,473; 4,710 |
| 42 | project_cost | 1,000.0; 1,000.0 | 995.1; 998.0 | 999.4; 1,000.0 | 37,646; 36,553 | 302,443; 302,574 | 3,993; 3,588 |
| 43 | baseline | 1,000.0; 1,000.0 | 989.5; 989.0 | 993.1; 994.0 | 41,923; 38,377 | 538,234; 554,896 | 3,201; 2,986 |
| 43 | scale_only | 1,000.0; 1,000.0 | 956.1; 784.0 | 968.1; 715.0 | 35,038; 29,864 | 306,347; 312,111 | 3,072; 2,153 |
| 43 | project_outcome | 1,000.0; 1,000.0 | 952.8; 803.0 | 961.5; 800.0 | 35,177; 32,630 | 316,011; 325,808 | 3,620; 2,475 |
| 43 | project_cost | 1,000.0; 1,000.0 | 995.5; 996.0 | 999.5; 1,000.0 | 40,993; 37,672 | 311,217; 314,271 | 3,420; 3,320 |
| 44 | baseline | 1,000.0; 1,000.0 | 986.8; 988.0 | 992.4; 993.0 | 34,575; 33,324 | 593,088; 614,827 | 1,768; 1,768 |
| 44 | scale_only | 1,000.0; 1,000.0 | 651.1; 470.0 | 591.4; 486.0 | 24,180; 20,200 | 335,178; 335,920 | 1,369; 1,028 |
| 44 | project_outcome | 1,000.0; 1,000.0 | 799.6; 697.0 | 703.8; 561.0 | 28,302; 25,016 | 345,088; 342,858 | 1,421; 1,043 |
| 44 | project_cost | 1,000.0; 1,000.0 | 830.5; 804.0 | 770.0; 707.0 | 29,140; 27,791 | 356,768; 360,371 | 1,335; 1,004 |

| Seed | Arm | Household cash | Household deposits | Active-firm cash | Firm bank debt | Firm debt to Treasury | Private net profit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | baseline | 87,548; 64,859 | 1,752,211; 1,578,175 | 2,709,407; 2,903,058 | 84,948; 68,746 | 19,631; 14,650 | 7,303; 6,460 |
| 42 | scale_only | 48,367; 50,350 | 1,040,801; 874,380 | 3,485,143; 3,651,195 | 57,516; 47,365 | 0; 0 | 3,652; 3,110 |
| 42 | project_outcome | 65,187; 81,724 | 1,166,713; 1,016,968 | 3,338,514; 3,491,319 | 68,748; 58,996 | 0; 0 | 4,777; 7,201 |
| 42 | project_cost | 38,807; 33,578 | 947,231; 745,331 | 3,596,648; 3,814,618 | 51,510; 42,338 | 0; 0 | 4,383; 4,418 |
| 43 | baseline | 44,426; 47,112 | 1,040,694; 851,085 | 3,461,894; 3,662,167 | 57,695; 49,361 | 2,395; 2,125 | 4,069; 3,629 |
| 43 | scale_only | 26,849; 20,239 | 537,745; 378,840 | 4,011,882; 4,212,670 | 15,726; 12,242 | 0; 0 | 2,906; 2,820 |
| 43 | project_outcome | 37,770; 24,629 | 630,894; 446,631 | 3,956,987; 4,176,395 | 58,973; 48,868 | 0; 0 | 5,254; 3,357 |
| 43 | project_cost | 52,500; 43,582 | 908,231; 737,956 | 3,604,137; 3,799,375 | 55,589; 48,556 | 0; 0 | 3,718; 3,698 |
| 44 | baseline | 42,809; 40,697 | 771,177; 576,331 | 3,796,562; 4,013,850 | 76,184; 63,455 | 15,791; 14,521 | 4,034; 5,017 |
| 44 | scale_only | 19,240; 16,669 | 342,912; 225,494 | 4,263,463; 4,380,934 | 26,859; 22,003 | 0; 0 | 3,520; 2,565 |
| 44 | project_outcome | 22,769; 22,563 | 391,385; 281,841 | 4,232,512; 4,335,396 | 50,683; 41,756 | 0; 0 | 2,746; 2,795 |
| 44 | project_cost | 24,462; 26,021 | 460,459; 320,753 | 4,185,491; 4,312,141 | 77,124; 64,082 | 0; 0 | 3,311; 1,966 |

| Seed | Arm | Treasury cash | Closing misc pool | Private Food sales share | Private Services sales share | Entries | Exits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | baseline | 130,898; 121,506 | 12,772; 11,068 | 1.000; 1.000 | 1.000; 1.000 | 1 | 1 |
| 42 | scale_only | 79,902; 68,066 | 4,251; 2,874 | 0.985; 0.986 | 0.961; 0.962 | 1 | 0 |
| 42 | project_outcome | 92,788; 68,451 | 6,222; 2,767 | 0.999; 0.999 | 0.990; 0.993 | 1 | 0 |
| 42 | project_cost | 67,619; 53,738 | 2,827; 972 | 0.998; 0.998 | 0.983; 0.984 | 1 | 0 |
| 43 | baseline | 100,553; 84,239 | 8,136; 5,693 | 1.000; 1.000 | 1.000; 1.000 | 1 | 0 |
| 43 | scale_only | 42,872; 6,495 | 1,007; 707 | 0.984; 0.983 | 0.979; 0.976 | 1 | 0 |
| 43 | project_outcome | 37,704; 6,718 | 1,253; 929 | 0.999; 0.999 | 0.997; 0.997 | 1 | 0 |
| 43 | project_cost | 87,997; 65,659 | 5,689; 3,001 | 0.998; 0.998 | 0.996; 0.995 | 1 | 0 |
| 44 | baseline | 63,144; 32,158 | 3,427; 2,087 | 1.000; 1.000 | 1.000; 1.000 | 1 | 0 |
| 44 | scale_only | 4,915; 3,570 | 678; 627 | 0.984; 0.983 | 0.970; 0.971 | 1 | 0 |
| 44 | project_outcome | 5,856; 4,748 | 942; 882 | 0.999; 0.999 | 0.995; 0.995 | 1 | 0 |
| 44 | project_cost | 7,885; 5,427 | 1,063; 891 | 0.998; 0.998 | 0.992; 0.992 | 1 | 0 |

### income_late

| Seed | Arm | GDP | Happiness | Health | Jobs | Food units | Services units |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | baseline | 52,279; 48,189 | 0.3519; 0.3007 | 0.6143; 0.6214 | 925.1; 918.0 | 3,616.8; 3,512.4 | 2,425.4; 2,330.9 |
| 42 | scale_only | 40,422; 40,182 | 0.2934; 0.2672 | 0.6248; 0.6289 | 801.0; 742.0 | 3,614.6; 3,778.1 | 1,882.9; 1,718.5 |
| 42 | project_outcome | 43,554; 40,676 | 0.2700; 0.2326 | 0.6208; 0.6228 | 832.1; 757.0 | 3,487.3; 3,496.1 | 1,995.9; 1,728.2 |
| 42 | project_cost | 41,879; 40,757 | 0.2251; 0.1723 | 0.6205; 0.6249 | 748.7; 684.0 | 3,541.4; 3,543.2 | 1,711.3; 1,460.5 |
| 43 | baseline | 44,516; 41,614 | 0.2394; 0.2079 | 0.6115; 0.6139 | 864.3; 849.0 | 3,456.5; 3,452.0 | 2,028.9; 2,008.6 |
| 43 | scale_only | 37,689; 31,232 | 0.2285; 0.1681 | 0.6231; 0.6222 | 728.6; 642.0 | 3,630.5; 3,221.9 | 1,457.6; 1,178.1 |
| 43 | project_outcome | 42,463; 39,678 | 0.2539; 0.2030 | 0.6214; 0.6264 | 753.4; 701.0 | 3,580.2; 3,548.7 | 1,719.6; 1,515.8 |
| 43 | project_cost | 39,639; 37,301 | 0.2501; 0.2014 | 0.6224; 0.6251 | 730.5; 679.0 | 3,567.7; 3,528.4 | 1,520.1; 1,357.4 |
| 44 | baseline | 37,680; 36,417 | 0.2032; 0.1777 | 0.6090; 0.6215 | 791.4; 760.0 | 3,456.1; 3,460.0 | 1,872.7; 1,654.3 |
| 44 | scale_only | 23,356; 19,948 | 0.1429; 0.1039 | 0.4263; 0.3536 | 467.8; 406.0 | 2,727.6; 2,461.9 | 957.3; 771.5 |
| 44 | project_outcome | 24,660; 21,991 | 0.1521; 0.1179 | 0.4292; 0.3510 | 526.2; 468.0 | 2,560.7; 2,526.9 | 1,188.2; 1,029.1 |
| 44 | project_cost | 23,729; 22,492 | 0.1473; 0.1166 | 0.4010; 0.3462 | 498.0; 468.0 | 2,556.6; 2,706.1 | 1,074.4; 889.6 |

| Seed | Arm | Food access | Services access | Housing access | Funded wage receipts | Wage claims | Dividends |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | baseline | 998.7; 999.0 | 993.1; 993.0 | 992.2; 992.0 | 45,967; 44,135 | 465,777; 483,434 | 5,139; 4,503 |
| 42 | scale_only | 1,000.0; 1,000.0 | 995.8; 996.0 | 1,000.0; 1,000.0 | 38,719; 35,693 | 298,687; 300,422 | 4,021; 3,879 |
| 42 | project_outcome | 999.9; 1,000.0 | 997.1; 1,000.0 | 999.6; 1,000.0 | 39,689; 37,217 | 293,629; 296,953 | 4,519; 4,534 |
| 42 | project_cost | 999.7; 1,000.0 | 996.1; 996.0 | 999.8; 1,000.0 | 37,844; 36,361 | 288,548; 287,625 | 4,153; 4,153 |
| 43 | baseline | 997.7; 999.0 | 990.6; 990.0 | 993.6; 992.0 | 41,641; 39,084 | 563,575; 583,080 | 3,029; 2,686 |
| 43 | scale_only | 999.3; 1,000.0 | 994.7; 989.0 | 1,000.0; 1,000.0 | 36,212; 31,971 | 302,633; 304,369 | 2,952; 2,674 |
| 43 | project_outcome | 999.3; 1,000.0 | 996.8; 1,000.0 | 1,000.0; 1,000.0 | 39,153; 38,022 | 310,472; 314,261 | 3,366; 2,859 |
| 43 | project_cost | 999.1; 1,000.0 | 995.8; 995.0 | 999.9; 1,000.0 | 37,046; 34,400 | 308,184; 310,886 | 3,115; 3,112 |
| 44 | baseline | 998.4; 997.0 | 988.8; 994.0 | 993.4; 996.0 | 35,089; 34,315 | 601,531; 626,550 | 1,768; 1,610 |
| 44 | scale_only | 975.2; 974.0 | 802.2; 562.0 | 620.3; 479.0 | 22,311; 20,291 | 333,361; 333,979 | 1,339; 958 |
| 44 | project_outcome | 983.0; 970.0 | 869.7; 742.0 | 802.7; 536.0 | 24,801; 22,145 | 344,818; 344,552 | 1,337; 961 |
| 44 | project_cost | 986.3; 987.0 | 858.0; 737.0 | 757.0; 523.0 | 23,941; 22,451 | 345,674; 345,165 | 1,132; 893 |

| Seed | Arm | Household cash | Household deposits | Active-firm cash | Firm bank debt | Firm debt to Treasury | Private net profit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | baseline | 104,895; 90,681 | 1,684,687; 1,508,943 | 2,765,655; 2,954,091 | 95,018; 78,230 | 18,075; 11,688 | 7,348; 5,663 |
| 42 | scale_only | 69,440; 64,828 | 984,088; 817,202 | 3,517,089; 3,695,382 | 61,011; 48,388 | 0; 0 | 3,290; 5,853 |
| 42 | project_outcome | 74,427; 69,137 | 1,093,110; 891,164 | 3,397,279; 3,616,449 | 67,735; 55,093 | 0; 0 | 5,362; 5,155 |
| 42 | project_cost | 74,663; 68,274 | 935,040; 740,246 | 3,542,274; 3,780,658 | 30,912; 21,842 | 2,459; 4,849 | 5,443; 6,095 |
| 43 | baseline | 73,553; 73,192 | 1,005,527; 828,372 | 3,452,288; 3,637,974 | 50,844; 43,287 | 1,528; 863 | 4,533; 4,449 |
| 43 | scale_only | 59,075; 44,705 | 562,627; 402,058 | 3,927,536; 4,144,315 | 13,686; 10,651 | 0; 0 | 3,442; 1,629 |
| 43 | project_outcome | 66,934; 60,094 | 749,157; 526,218 | 3,767,417; 4,006,569 | 65,107; 53,963 | 0; 0 | 4,947; 3,693 |
| 43 | project_cost | 68,558; 60,625 | 725,809; 543,360 | 3,754,383; 3,977,398 | 19,393; 14,319 | 0; 0 | 4,287; 4,606 |
| 44 | baseline | 65,338; 68,830 | 803,476; 600,891 | 3,728,912; 3,944,816 | 80,604; 69,283 | 13,538; 13,260 | 3,983; 3,778 |
| 44 | scale_only | 35,127; 31,609 | 324,556; 215,440 | 4,263,412; 4,370,091 | 37,352; 29,789 | 0; 0 | 3,098; 2,600 |
| 44 | project_outcome | 38,718; 35,577 | 400,499; 281,135 | 4,203,518; 4,316,258 | 58,483; 47,979 | 0; 0 | 1,847; 2,493 |
| 44 | project_cost | 39,273; 39,183 | 347,511; 243,935 | 4,253,178; 4,346,739 | 54,827; 45,801 | 0; 0 | 1,781; 2,522 |

| Seed | Arm | Treasury cash | Closing misc pool | Private Food sales share | Private Services sales share | Entries | Exits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | baseline | 125,072; 112,587 | 12,282; 9,460 | 1.000; 1.000 | 1.000; 1.000 | 1 | 1 |
| 42 | scale_only | 73,765; 56,683 | 3,356; 605 | 0.985; 0.987 | 0.959; 0.959 | 1 | 0 |
| 42 | project_outcome | 84,592; 63,772 | 4,828; 2,468 | 0.999; 0.999 | 0.990; 0.992 | 1 | 0 |
| 42 | project_cost | 62,866; 18,058 | 2,914; 973 | 0.998; 0.998 | 0.984; 0.984 | 1 | 0 |
| 43 | baseline | 97,898; 83,587 | 8,077; 5,967 | 1.000; 1.000 | 1.000; 1.000 | 1 | 0 |
| 43 | scale_only | 51,980; 7,167 | 1,319; 707 | 0.984; 0.984 | 0.979; 0.978 | 1 | 0 |
| 43 | project_outcome | 66,735; 46,940 | 2,596; 929 | 0.999; 0.999 | 0.997; 0.997 | 1 | 0 |
| 43 | project_cost | 57,295; 19,868 | 2,183; 1,145 | 0.997; 0.998 | 0.995; 0.996 | 1 | 0 |
| 44 | baseline | 68,609; 41,519 | 3,908; 2,084 | 1.000; 1.000 | 1.000; 1.000 | 1 | 0 |
| 44 | scale_only | 4,650; 3,524 | 678; 627 | 0.986; 0.986 | 0.969; 0.973 | 1 | 0 |
| 44 | project_outcome | 5,359; 4,042 | 917; 831 | 0.999; 0.999 | 0.995; 0.995 | 1 | 0 |
| 44 | project_cost | 5,136; 4,776 | 934; 839 | 0.998; 0.999 | 0.992; 0.992 | 1 | 0 |

Household cash and deposits are stocks, not household net worth. Firm cash and debt cover active firms. Firm debt to Treasury is a borrower obligation, not government debt. Private net profit is the harness's sum of `FirmAgent.net_profit` for active private Food and Services firms, not cash after research spending or loan-principal repayment. Wage receipts are funded household ledger amounts. Claims are outstanding stocks.

The frozen harness records Treasury cash and the closing miscellaneous pool, not separate gross Treasury receipts, gross miscellaneous receipts, or household payouts from that pool. Research spending below is observed, but these stocks cannot identify each recipient flow. The unchanged source routes investment tax to Treasury and the after-tax research payment through `_collect_misc_revenue`, which applies its own tax skim. Receipt decomposition remains an evidence gap.

## Quality and research intensity

Raw-quality means cover active private Food and Services firms. Quantiles and maximum below are final values. Effective quality is raw quality times the unchanged government technology multiplier, capped at 10. The near-perfect cutoff is at least 9.5. Near-perfect counts are cumulative firm-weeks across all 520 ticks, not unique firms.

| Sequence | Seed | Arm | Raw mean, late; final | Final raw median | Final raw p90 | Final raw max | Effective max, late; final | Raw near-perfect firm-weeks | Effective near-perfect firm-weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| income_first | 42 | baseline | 8.845; 8.896 | 10.000 | 10.000 | 10.000 | 10.000; 10.000 | 8633 | 8633 |
| income_first | 42 | scale_only | 0.574; 0.574 | 0.539 | 0.904 | 1.065 | 1.065; 1.065 | 0 | 0 |
| income_first | 42 | project_outcome | 1.740; 1.792 | 1.065 | 4.071 | 4.426 | 4.291; 4.426 | 0 | 0 |
| income_first | 42 | project_cost | 1.358; 1.406 | 0.849 | 3.170 | 3.406 | 3.210; 3.406 | 0 | 0 |
| income_first | 43 | baseline | 8.390; 8.395 | 10.000 | 10.000 | 10.000 | 10.000; 10.000 | 7766 | 7766 |
| income_first | 43 | scale_only | 0.569; 0.569 | 0.544 | 0.752 | 0.882 | 0.882; 0.882 | 0 | 0 |
| income_first | 43 | project_outcome | 1.874; 1.943 | 1.479 | 3.773 | 4.072 | 3.921; 4.072 | 0 | 0 |
| income_first | 43 | project_cost | 1.714; 1.776 | 1.714 | 2.903 | 3.360 | 3.107; 3.360 | 0 | 0 |
| income_first | 44 | baseline | 8.578; 8.586 | 10.000 | 10.000 | 10.000 | 10.000; 10.000 | 8901 | 8901 |
| income_first | 44 | scale_only | 0.633; 0.633 | 0.637 | 0.931 | 1.044 | 1.044; 1.044 | 0 | 0 |
| income_first | 44 | project_outcome | 2.101; 2.169 | 1.926 | 3.670 | 4.234 | 4.082; 4.234 | 0 | 0 |
| income_first | 44 | project_cost | 1.656; 1.705 | 1.386 | 3.139 | 3.553 | 3.382; 3.553 | 0 | 0 |
| income_late | 42 | baseline | 8.942; 8.974 | 10.000 | 10.000 | 10.000 | 10.000; 10.000 | 8614 | 8614 |
| income_late | 42 | scale_only | 0.574; 0.574 | 0.539 | 0.904 | 1.065 | 1.065; 1.065 | 0 | 0 |
| income_late | 42 | project_outcome | 1.735; 1.790 | 1.045 | 4.085 | 4.426 | 4.291; 4.426 | 0 | 0 |
| income_late | 42 | project_cost | 1.344; 1.386 | 0.853 | 3.218 | 3.406 | 3.216; 3.406 | 0 | 0 |
| income_late | 43 | baseline | 8.381; 8.392 | 10.000 | 10.000 | 10.000 | 10.000; 10.000 | 7894 | 7894 |
| income_late | 43 | scale_only | 0.569; 0.569 | 0.544 | 0.752 | 0.882 | 0.882; 0.882 | 0 | 0 |
| income_late | 43 | project_outcome | 1.895; 1.961 | 1.581 | 3.773 | 4.072 | 3.947; 4.072 | 0 | 0 |
| income_late | 43 | project_cost | 1.637; 1.685 | 1.570 | 2.920 | 3.604 | 3.464; 3.604 | 0 | 0 |
| income_late | 44 | baseline | 8.544; 8.544 | 10.000 | 10.000 | 10.000 | 10.000; 10.000 | 8899 | 8899 |
| income_late | 44 | scale_only | 0.633; 0.633 | 0.637 | 0.931 | 1.044 | 1.044; 1.044 | 0 | 0 |
| income_late | 44 | project_outcome | 2.112; 2.166 | 2.172 | 3.620 | 4.234 | 4.082; 4.234 | 0 | 0 |
| income_late | 44 | project_cost | 1.649; 1.683 | 1.394 | 3.275 | 3.553 | 3.382; 3.553 | 0 | 0 |

Every new-model baseline Food and Services provider stays at or below quality 0.1. Maximum raw quality across those cases is 4.4260. The largest observed 52-tick completed gain is 1.000000, against a cap of 1.0. All observed quality bounds pass.

For unclipped rows, the effective maximum divided by the raw maximum identifies the common technology multiplier. Multiplying the raw mean and quantiles by that multiplier recovers the following effective summaries. Every new-model row in the late window has positive private quality and is unclipped. Capped original-baseline summaries remain unobserved rather than inferred from a clipped maximum.

| Sequence | Seed | Arm | Effective mean, late; final | Final effective median | Final effective p90 |
| --- | --- | --- | --- | --- | --- |
| income_first | 42 | scale_only | 0.574; 0.574 | 0.539 | 0.904 |
| income_first | 42 | project_outcome | 1.740; 1.792 | 1.065 | 4.071 |
| income_first | 42 | project_cost | 1.358; 1.406 | 0.849 | 3.170 |
| income_first | 43 | scale_only | 0.569; 0.569 | 0.544 | 0.752 |
| income_first | 43 | project_outcome | 1.874; 1.943 | 1.479 | 3.773 |
| income_first | 43 | project_cost | 1.714; 1.776 | 1.714 | 2.903 |
| income_first | 44 | scale_only | 0.633; 0.633 | 0.637 | 0.931 |
| income_first | 44 | project_outcome | 2.101; 2.169 | 1.926 | 3.670 |
| income_first | 44 | project_cost | 1.656; 1.705 | 1.386 | 3.139 |
| income_late | 42 | scale_only | 0.574; 0.574 | 0.539 | 0.904 |
| income_late | 42 | project_outcome | 1.735; 1.790 | 1.045 | 4.085 |
| income_late | 42 | project_cost | 1.344; 1.386 | 0.853 | 3.218 |
| income_late | 43 | scale_only | 0.569; 0.569 | 0.544 | 0.752 |
| income_late | 43 | project_outcome | 1.895; 1.961 | 1.581 | 3.773 |
| income_late | 43 | project_cost | 1.637; 1.685 | 1.570 | 2.920 |
| income_late | 44 | scale_only | 0.633; 0.633 | 0.637 | 0.931 |
| income_late | 44 | project_outcome | 2.112; 2.166 | 2.172 | 3.620 |
| income_late | 44 | project_cost | 1.649; 1.683 | 1.394 | 3.275 |

Research spending below is cumulative over all 520 ticks. Baseline-provider spending is a firm debit, not automatically Treasury spending. Aggregate private-quality changes can reflect entry and composition as well as within-firm research.

| Sequence | Seed | Arm | Baseline research spend | Private research spend | Private Food spend | Private Services spend | Derived investment-tax receipts | Derived gross misc receipts | Open projects, late; final |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| income_first | 42 | baseline | 4,811 | 1,971,967 | 999,334 | 972,633 | 197,678 | 1,779,100 | 0.0; 0.0 |
| income_first | 42 | scale_only | 0 | 0 | 0 | 0 | 0 | 0 | 0.0; 0.0 |
| income_first | 42 | project_outcome | 0 | 189,960 | 127,800 | 62,160 | 18,996 | 170,964 | 30.8; 31.0 |
| income_first | 42 | project_cost | 0 | 263,975 | 175,785 | 88,190 | 26,398 | 237,578 | 30.8; 31.0 |
| income_first | 43 | baseline | 4,698 | 1,750,355 | 974,288 | 776,067 | 175,505 | 1,579,547 | 0.0; 0.0 |
| income_first | 43 | scale_only | 0 | 0 | 0 | 0 | 0 | 0 | 0.0; 0.0 |
| income_first | 43 | project_outcome | 0 | 238,710 | 163,140 | 75,570 | 23,871 | 214,839 | 31.8; 32.0 |
| income_first | 43 | project_cost | 0 | 377,734 | 261,044 | 116,690 | 37,773 | 339,960 | 31.7; 32.0 |
| income_first | 44 | baseline | 4,877 | 1,621,350 | 975,809 | 645,541 | 162,623 | 1,463,604 | 0.0; 0.0 |
| income_first | 44 | scale_only | 0 | 0 | 0 | 0 | 0 | 0 | 0.0; 0.0 |
| income_first | 44 | project_outcome | 0 | 259,830 | 196,950 | 62,880 | 25,983 | 233,847 | 29.8; 30.0 |
| income_first | 44 | project_cost | 0 | 326,961 | 242,217 | 84,744 | 32,696 | 294,265 | 29.9; 30.0 |
| income_late | 42 | baseline | 4,814 | 1,904,768 | 970,758 | 934,009 | 190,958 | 1,718,624 | 0.0; 0.0 |
| income_late | 42 | scale_only | 0 | 0 | 0 | 0 | 0 | 0 | 0.0; 0.0 |
| income_late | 42 | project_outcome | 0 | 189,330 | 126,120 | 63,210 | 18,933 | 170,397 | 30.8; 31.0 |
| income_late | 42 | project_cost | 0 | 256,289 | 176,992 | 79,297 | 25,629 | 230,660 | 29.9; 30.0 |
| income_late | 43 | baseline | 4,700 | 1,784,764 | 975,153 | 809,611 | 178,946 | 1,610,518 | 0.0; 0.0 |
| income_late | 43 | scale_only | 0 | 0 | 0 | 0 | 0 | 0 | 0.0; 0.0 |
| income_late | 43 | project_outcome | 0 | 246,630 | 172,620 | 74,010 | 24,663 | 221,967 | 31.8; 32.0 |
| income_late | 43 | project_cost | 0 | 352,760 | 246,312 | 106,448 | 35,276 | 317,484 | 31.8; 32.0 |
| income_late | 44 | baseline | 4,872 | 1,557,258 | 973,719 | 583,539 | 156,213 | 1,405,917 | 0.0; 0.0 |
| income_late | 44 | scale_only | 0 | 0 | 0 | 0 | 0 | 0 | 0.0; 0.0 |
| income_late | 44 | project_outcome | 0 | 259,920 | 197,910 | 62,010 | 25,992 | 233,928 | 29.8; 30.0 |
| income_late | 44 | project_cost | 0 | 315,349 | 230,089 | 85,260 | 31,535 | 283,814 | 29.9; 30.0 |

The two derived receipt columns cover Food and Services research only. The factory's investment-tax rate stays at 10% in this fixed protocol, so observed spending implies a 10% Treasury receipt and a 90% gross payment to `_collect_misc_revenue`. The latter applies its own 0% to 20% skim before adding net revenue to the pool. That skim, total Treasury receipts, and subsequent miscellaneous payouts remain unobserved. These derived research components are not presented as measured gross fiscal totals.

| Sequence | Seed | Arm | Completed | Positive gain | Failed | Successful zero gain | Paused firm-weeks | Abandoned at exit | Abandoned spending |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| income_first | 42 | project_outcome | 142 | 130 | 12 | 0 | 8918 | 0 | 0 |
| income_first | 42 | project_cost | 129 | 122 | 7 | 0 | 9202 | 0 | 0 |
| income_first | 43 | project_outcome | 180 | 153 | 27 | 0 | 8022 | 0 | 0 |
| income_first | 43 | project_cost | 192 | 173 | 19 | 0 | 7430 | 0 | 0 |
| income_first | 44 | project_outcome | 198 | 171 | 27 | 0 | 6378 | 0 | 0 |
| income_first | 44 | project_cost | 160 | 148 | 12 | 0 | 7966 | 0 | 0 |
| income_late | 42 | project_outcome | 142 | 131 | 11 | 0 | 8955 | 0 | 0 |
| income_late | 42 | project_cost | 125 | 117 | 8 | 0 | 8902 | 0 | 0 |
| income_late | 43 | project_outcome | 188 | 155 | 33 | 0 | 7758 | 0 | 0 |
| income_late | 43 | project_cost | 177 | 159 | 18 | 0 | 7954 | 0 | 0 |
| income_late | 44 | project_outcome | 198 | 171 | 27 | 0 | 6372 | 0 | 0 |
| income_late | 44 | project_cost | 155 | 144 | 11 | 0 | 8138 | 0 | 0 |

The next table counts only weeks 421 through 520. Its spending is a window total, not a weekly average. Across the twelve project cases, 64.0%–83.3% of open project-weeks in that window are paused. A paused project retains progress, but progress is not advancing during those weeks.

| Sequence | Seed | Arm | Late completions | Late positive gain | Late failures | Late private spend | Late paused firm-weeks | Late abandoned projects |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| income_first | 42 | project_outcome | 17 | 15 | 2 | 24,330 | 2289 | 0 |
| income_first | 42 | project_cost | 16 | 16 | 0 | 41,926 | 2397 | 0 |
| income_first | 43 | project_outcome | 22 | 19 | 3 | 31,110 | 2163 | 0 |
| income_first | 43 | project_cost | 24 | 24 | 0 | 59,791 | 2145 | 0 |
| income_first | 44 | project_outcome | 22 | 20 | 2 | 32,820 | 1906 | 0 |
| income_first | 44 | project_cost | 15 | 14 | 1 | 47,595 | 2212 | 0 |
| income_late | 42 | project_outcome | 18 | 16 | 2 | 24,000 | 2300 | 0 |
| income_late | 42 | project_cost | 14 | 14 | 0 | 41,927 | 2300 | 0 |
| income_late | 43 | project_outcome | 25 | 19 | 6 | 32,880 | 2104 | 0 |
| income_late | 43 | project_cost | 20 | 18 | 2 | 55,316 | 2250 | 0 |
| income_late | 44 | project_outcome | 21 | 18 | 3 | 29,670 | 2011 | 0 |
| income_late | 44 | project_cost | 9 | 9 | 0 | 31,566 | 2491 | 0 |

No project abandonment at exit occurred in these twelve project cases. The macro panel therefore does not exercise that branch. [Late project flows and unclipped effective summaries](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/economy-window-flows.csv).

Completion gains and pause counts are observed. The harness records no-gain completions rather than the internal failure counter. This analysis reconstructs the frozen purpose-keyed outcome from seed, stable initial or entry identity, and project sequence, then matches every predicted committed gain to its recorded gain. This separates a failed attempt from a successful outcome capped to zero. Abandoned spending is the paid balance of an open project at observed exit and receives no refund.

The funding reserve protects cash at the research spending boundary. It uses capped scheduled future dues and does not forecast unaccrued interest. Later dividends retain their existing weaker buffer. A low closing cash balance therefore does not by itself establish a breach at the earlier research boundary.

Quality distributions in the recorder are summaries. It records raw mean, median, p90, and maximum, plus effective maximum and threshold counts. It does not retain the underlying full effective-quality distribution. The unclipped derivation above adds effective summaries without modifying raw evidence. Sector quality, output, prices, Services staffing and slots, and all late and final fields remain in the per-case CSV.

## Normal-mode runtime

These are integrated engine timings with in-engine observer wrappers disabled. The timed region is `Economy.step()` only. Post-step recording, process startup, browser, server, and warehouse time are excluded. Macro-panel `engine_ms` includes observer wrappers and remains exploratory.

The measurement machine is Windows with Python 3.11.9 and an AMD Ryzen 9 3900X, 12 cores and 24 logical processors. Startup reported 1% CPU load and no Python workers. Only one simulation worker ran at a time. The controller reverses arm order between adjacent repeat clusters. Background desktop activity was not controlled.

Each run's p50 is the median of its 40 tick times for weeks 41 through 80. Its p95 is nearest-rank 95%, the 38th sorted value. The original analyzer's engine percentiles cover weeks after week 10. This report uses the supplementary 41-through-80 fields. Ratios pair the same sequence, population, seed, and repeat. The point is the geometric mean of five paired ratios. The percentile 95% bootstrap interval resamples five complete repeat clusters 100,000 times with analysis seed 20261027. Intervals are per cell, not a joint family-wise interval.

A measured-window working-budget pass requires both the point and interval upper bound to be at most 1.05 for p50 and p95. A crossing interval is inconclusive. No cases were repeated to seek a favorable result.

Fifteen of sixteen percentile checks meet that rule. A's income_late p95 at 1,000 households is inconclusive, with point 0.9965 and interval 0.9505 to 1.0594. A therefore has no overall working-budget pass; any further confirmation needs a new, predeclared measurement rather than a selective repeat. B meets the threshold in all tested normal-mode windows. These are workload-qualified results, not isolated research-overhead or unqualified speedup claims.

| Sequence | Households | Arm | Percentile | Paired ratio | 95% interval | Repeat ratio range | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| income_first | 1000 | project_outcome | p50 | 0.9913 | 0.9877 to 0.9948 | 0.9850 to 0.9958 | within measured window |
| income_first | 1000 | project_outcome | p95 | 0.9815 | 0.9555 to 1.0286 | 0.9520 to 1.0761 | within measured window |
| income_first | 1000 | project_cost | p50 | 0.9989 | 0.9953 to 1.0025 | 0.9931 to 1.0031 | within measured window |
| income_first | 1000 | project_cost | p95 | 0.9740 | 0.9630 to 0.9934 | 0.9628 to 1.0121 | within measured window |
| income_first | 10000 | project_outcome | p50 | 0.9928 | 0.9917 to 0.9942 | 0.9912 to 0.9952 | within measured window |
| income_first | 10000 | project_outcome | p95 | 0.9884 | 0.9780 to 0.9956 | 0.9685 to 0.9968 | within measured window |
| income_first | 10000 | project_cost | p50 | 0.9905 | 0.9882 to 0.9934 | 0.9880 to 0.9957 | within measured window |
| income_first | 10000 | project_cost | p95 | 0.9905 | 0.9813 to 0.9979 | 0.9729 to 1.0005 | within measured window |
| income_late | 1000 | project_outcome | p50 | 0.9817 | 0.9740 to 0.9896 | 0.9717 to 0.9921 | within measured window |
| income_late | 1000 | project_outcome | p95 | 0.9965 | 0.9505 to 1.0594 | 0.9288 to 1.1172 | inconclusive |
| income_late | 1000 | project_cost | p50 | 0.9753 | 0.9639 to 0.9919 | 0.9603 to 1.0083 | within measured window |
| income_late | 1000 | project_cost | p95 | 0.9700 | 0.9470 to 0.9899 | 0.9281 to 1.0037 | within measured window |
| income_late | 10000 | project_outcome | p50 | 0.9894 | 0.9869 to 0.9920 | 0.9848 to 0.9938 | within measured window |
| income_late | 10000 | project_outcome | p95 | 1.0001 | 0.9923 to 1.0054 | 0.9849 to 1.0062 | within measured window |
| income_late | 10000 | project_cost | p50 | 0.9899 | 0.9872 to 0.9926 | 0.9858 to 0.9930 | within measured window |
| income_late | 10000 | project_cost | p95 | 1.0011 | 0.9920 to 1.0068 | 0.9833 to 1.0077 | within measured window |

[All absolute per-run timings and phase counts](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/performance-per-case.csv). [All paired per-run timings and ratios](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/performance-pairs.csv). [Bootstrap results](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/performance-bootstrap.csv).

The preserved separate baseline profile attributes 26.93 of 63.28 engine seconds to household planning, including 25.19 seconds in consumption planning. Goods clearing accounts for 12.96 seconds. The profile establishes that household planning and funded goods settlement dominate that 1,000-household run. Its times are profiled, not reported benchmark samples. It does not isolate research overhead or prove the same percentages at 10,000 households. [Preserved profile summary](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/profiling/summary.json).

Active and queued firm counts match across the three arms within each observed timing window. The models still change settled purchases, financial flows, and research work. The ratios measure that combined economic workload, not isolated research overhead. Five repeats of one seed establish limited runtime repeatability, not economy uncertainty.

### Work actually present in weeks 41 through 80

| Sequence | Households | Arm | Recorded phase-weeks across five repeats | Active firm range | Queued firm range | Active project firm-weeks | Paused project firm-weeks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| income_first | 1000 | baseline | private_ramp=200 | 36 to 36 | 9 to 9 | 0 | 0 |
| income_first | 1000 | project_outcome | private_ramp=200 | 36 to 36 | 9 to 9 | 4475 | 1125 |
| income_first | 1000 | project_cost | private_ramp=200 | 36 to 36 | 9 to 9 | 4215 | 1025 |
| income_first | 10000 | baseline | full_private_market=200 | 301 to 301 | 0 to 0 | 0 | 0 |
| income_first | 10000 | project_outcome | full_private_market=200 | 301 to 301 | 0 to 0 | 33200 | 2575 |
| income_first | 10000 | project_cost | full_private_market=200 | 301 to 301 | 0 to 0 | 32620 | 2110 |
| income_late | 1000 | baseline | private_ramp=200 | 36 to 36 | 9 to 9 | 0 | 0 |
| income_late | 1000 | project_outcome | private_ramp=200 | 36 to 36 | 9 to 9 | 4440 | 1200 |
| income_late | 1000 | project_cost | private_ramp=200 | 36 to 36 | 9 to 9 | 3975 | 1185 |
| income_late | 10000 | baseline | full_private_market=200 | 301 to 301 | 0 to 0 | 0 | 0 |
| income_late | 10000 | project_outcome | full_private_market=200 | 301 to 301 | 0 to 0 | 32735 | 2890 |
| income_late | 10000 | project_cost | full_private_market=200 | 301 to 301 | 0 to 0 | 32015 | 2280 |

All 1,000-household windows have 36 active firms and nine queued firms, so they remain private_ramp. All 10,000-household windows have 301 active firms and no queued firms throughout weeks 41 through 80, so they reach the controller's full_private_market label. Both active and paused project states occur. The label means a fully activated cohort, not that baseline providers have retired or that the economy has reached a long-run equilibrium. Completion-event counts are unobserved in this timing mode because their wrappers are disabled.

### Process memory

Values are MiB, measured at worker completion. They include interpreter, imports, simulation, post-step recorder rows, completion and lifecycle state, and harness overhead. Peak RSS is the process peak working set. These snapshots do not isolate algorithm state and do not prove memory savings.

| Sequence | Households | Arm | Median final RSS | Final RSS range | Median peak RSS | Peak RSS range | Median change from baseline, final; peak |
| --- | --- | --- | --- | --- | --- | --- | --- |
| income_first | 1000 | baseline | 77.57 | 77.43 to 77.66 | 77.62 | 77.49 to 77.66 | 0.00; 0.00 |
| income_first | 1000 | project_outcome | 75.96 | 75.75 to 76.20 | 77.35 | 77.07 to 77.69 | -1.61; -0.28 |
| income_first | 1000 | project_cost | 75.84 | 75.80 to 75.96 | 77.33 | 77.16 to 77.78 | -1.73; -0.29 |
| income_first | 10000 | baseline | 385.52 | 385.42 to 385.60 | 385.79 | 385.59 to 385.82 | 0.00; 0.00 |
| income_first | 10000 | project_outcome | 377.26 | 377.14 to 377.41 | 377.41 | 377.14 to 377.61 | -8.26; -8.39 |
| income_first | 10000 | project_cost | 376.21 | 376.10 to 376.29 | 376.80 | 376.71 to 376.99 | -9.30; -8.99 |
| income_late | 1000 | baseline | 77.38 | 77.09 to 77.52 | 77.91 | 77.84 to 78.06 | 0.00; 0.00 |
| income_late | 1000 | project_outcome | 76.41 | 75.96 to 76.56 | 77.75 | 77.24 to 77.86 | -0.97; -0.15 |
| income_late | 1000 | project_cost | 76.43 | 76.41 to 76.54 | 77.66 | 77.38 to 77.74 | -0.95; -0.25 |
| income_late | 10000 | baseline | 385.47 | 385.30 to 385.52 | 386.01 | 385.96 to 386.04 | 0.00; 0.00 |
| income_late | 10000 | project_outcome | 376.97 | 376.86 to 377.05 | 377.41 | 377.30 to 377.52 | -8.50; -8.61 |
| income_late | 10000 | project_cost | 377.64 | 377.46 to 377.75 | 377.95 | 377.84 to 378.09 | -7.83; -8.06 |

The reviewed algorithm keeps one optional project and at most two rolling gain records per eligible firm. The source has no added household-by-firm scan and adds work bounded by firms and registered loans. No retained-object or heap-attribution measurement was performed.

## Accounting and evidence limits

| Panel | Cases | Ticks | Maximum absolute money residual | Maximum absolute clearing residual |
| --- | --- | --- | --- | --- |
| economy | 24 | 12480 | 3.38982790709e-05 | 7.9634787653e-10 |
| performance | 60 | 4800 | 7.16224312782e-05 | 1.53454493557e-08 |

Both frozen analyzer gates use model currency. The protocol money tolerance is 0.001 and clearing tolerance is 0.000001. No failed output was repaired or silently promoted. Preparatory captures, including the rejected 520-tick baseline, remain outside formal economy cases and are not formal evidence.

The new models preserve household utility, awareness, re-shopping, wage behavior, capacity rules, payment ownership, normal-mode cadence, Housing, Healthcare, and baseline retirement rules. Defaults and the retained short replay provide bounded compatibility evidence. Long-run effects of the opt-in arms are intentionally different.

Three seeds support this finite within-model comparison. They do not estimate real-world uncertainty, establish external calibration, or choose a welfare weighting. Gross receipt decomposition, capped effective-quality distributions, the ramping 1,000-household workload, and later high-quality research states remain evidence limits. The 10,000-household window does cover a fully activated private cohort under the controller's definition. A production choice also requires the parent's independent result inspection.

## Reproduction and handoff

[Frozen controller and analyzer](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/panel.py). [Supplementary analysis](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion_analysis.py). [Report generator](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion_report.py). [Economy controller log](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/economy-controller.log). [Performance controller log](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/performance-controller.log).

The exact execution commands use the supplied Python environment and source roots.

```powershell
$PY = 'C:/Users/ayman/Documents/EcoSim/.venv/Scripts/python.exe'
$HERE = 'C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment'
& $PY -B $HERE/panel.py run --baseline-source $HERE/sources/baseline --candidate-source $HERE/sources/candidate --run-dir economy --sequences income_first,income_late --populations 1000 --seeds 42,43,44 --arms baseline,scale_only,project_outcome,project_cost --ticks 520 --late-start 421
& $PY -B $HERE/panel.py analyze --run-dir economy
& $PY -B $HERE/completion_analysis.py economy
& $PY -B $HERE/panel.py run --baseline-source $HERE/sources/baseline --candidate-source $HERE/sources/candidate --run-dir performance --sequences income_first,income_late --populations 1000,10000 --seeds 42 --arms baseline,project_outcome,project_cost --repeats 5 --ticks 80 --late-start 41 --no-observer
& $PY -B $HERE/panel.py analyze --run-dir performance
& $PY -B $HERE/completion_analysis.py performance
```

The additional late-flow and effective-summary command is `& $PY -B $HERE/completion_windows.py`.

The controller retains validated completed cases on resume. Analyzer and supplemental outputs use exclusive creation and cannot be overwritten silently. Existing outputs must be retained and a new analysis version used if analysis changes.

The approved OpenWiki CLI is absent from PATH. Generated wiki refresh remains due. No Actions were enabled or requested. No commit, push, PR, production edit, test edit, contract edit, skill edit, memory edit, or subagent was created by this worker.

The generated wiki's PAY-01 section still describes the named payment package as unimplemented. Current source and these executed named-sequence runs take precedence over that historical description. The refresh must reconcile that drift.

The worker ledger's pre-review check exits 0 with the following output. This is form and integrity evidence for this bounded role, not a parent full-pstack pass. The parent ledger remains incomplete and its formal architecture-bakeoff gap remains open.

```text
READY FOR INDEPENDENT REVIEW (not final; only the review row may stay pending)
done 95, not-applicable 30, overridden 37, substituted 2
exit_code=0
```

[Final source, protocol, script, retained-evidence, and scope checks](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/final-integrity.json). [Bounded worker ledger](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-preflight/panel-completion/ledger.json).

[Worker decision trail](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/decisions.tsv). [Decision-trail self-audit and correction](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/decision-log-audit.json). [Pre-review output](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/pre-review-check.txt). [Artifact SHA256 manifest with explicit boundaries](C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/quality-research-experiment/completion/artifact-manifest.json).

Principles changed concrete choices. Model the Domain and Foundational Thinking set explicit case keys and windows. Boundary Discipline and Prove It Works require source and case checks before arithmetic. Build the Lever keeps rerunnable external scripts. Laziness Protocol preserves the reviewed harness. Sequence Work into Verifiable Units separates and validates the panels. Explain the Number keeps runtime intervals, phase counts, and memory limits visible. Never Block on the Human permits the already authorized runs without routine questions.

Independent inspection and economic acceptance remain with the parent. This measurement worker does not choose or ship a model.


Parent correction after cross-model review: the original worker report is preserved byte-for-byte at `quality-research-experiment/parent-corrections/worker-results-before.md`. These changes clarify household effects, pause prevalence, debt labels and verification limits. They change no source, tests, protocols or simulation cases. The reviewer's statement that projects did not cause the housing loss is read narrowly here: scale-only establishes that project funding is not necessary for the loss, not that projects have no causal effect.
