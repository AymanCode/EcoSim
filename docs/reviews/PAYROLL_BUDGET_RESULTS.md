# Funded payroll and received-income budgets: saved results

No additional simulations were run for this readout. Economic comparison: 12 completed cases, 1,000 households, seeds 42/43/44, 200 weeks each. Every seed has a before/after pair for each payment timing. Both sources use the same cash-funded research model. Control a7a8cf38e09cbd02629eec94ca599e85082d10a7; candidate 558a6a005c25ea47ce0c0a58a68b59b580ebe53f. Results describe these frozen commits, not subsequent GitHub main changes.

The package funds ordinary private Food/Services contracts before work, cancels unaffordable hires or reduces staffing when existing cash and approved finance cannot cover contracts, and calculates standard shopping budgets after funded wages and benefits arrive. Public-provider funding is outside this change. This comparison does not isolate the two components.

## Core mechanism

All six candidate economic cases recorded zero private Food/Services current unpaid gross and zero private wage-claim stock on every observed week. That is 1,200 candidate firm-system observations, not a claim about every possible configuration. Fresh initialization starts without old private arrears; focused tests separately cover preserving old claims.

In the standard flow, average week-200 private arrears were $28,534 before versus $0 after. Over weeks 101–200, baseline private current short-pay averaged $289/week across seeds; candidate short-pay was zero. Candidate firms cancelled about 1.05 attempted hires and made 0.66 financial layoffs per week across the whole economy in that window. These are event flows, not counts of permanently unemployed people.

Total wage claims did not disappear: public/baseline providers remain outside the private staffing rule. The late-window total averaged $293,992 before and $286,859 after in the standard flow. The Healthcare staffing and minimum-base-wage/profit-bonus exception was preserved; no new Treasury guarantee was added.

## Standard-flow economic results

Numbers below are equally weighted three-seed means of weekly values during weeks 101–200. Percentages compare those means, rather than averaging individual seed percentage changes. Paid wages are household wage-ledger receipts. GDP is the model's nominal revenue proxy, not real output or welfare.

| Measure | Before | After | Change |
|---|---:|---:|---:|
| Employed households | 534.73 | 547.60 | +2.41% |
| Household paid wages/week | $26,900.16 | $28,395.66 | +5.56% |
| Food units bought/week | 3,596.02 | 3,524.81 | −1.98% |
| Services units bought/week | 1,030.18 | 1,116.99 | +8.43% |
| Households buying Services/week | 853.12 | 871.69 | +18.57 |
| Housed households | 964.50 | 997.39 | +32.89 |
| Nominal GDP/week | $42,195.06 | $44,249.89 | +4.87% |
| Mean happiness, 0–1 | 0.4575 | 0.4623 | +0.0048 |
| Mean health, 0–1 | 0.6672 | 0.6586 | −0.0086 |
| Household cash | $205,055.95 | $207,548.10 | +1.22% |
| Household deposits | $3,242,283.67 | $3,226,978.35 | −0.47% |
| Firm cash, all firms | $1,181,122.81 | $1,224,391.90 | +3.66% |
| Firm bank debt | $72,869.58 | $85,739.03 | +17.66% |
| Treasury cash | $30,876.52 | $35,931.82 | +16.37% |

### Variation and adverse effects

The averages are not universal gains. In seed order 42/43/44, employed-household changes were +45.87/−14.26/+7.00; Services units changed +219.59/−43.68/+84.53; GDP changed +$6,656/−$1,322/+$830 per week. Seed 43 lost jobs, wage receipts, Services units and GDP. Food units and mean health fell in all three seeds. Housing access improved in all three; the large mean increase was dominated by seed 42 (+96.09 housed households versus +1.25/+1.32).

Bank-funded contractual writeoffs, recorded in the bank's cumulative loss field, were zero at week 200 in the controls and averaged $5,444.85 in the candidate. More jobs and larger debt balances are accompanied by real lender losses. These fields cover bank-funded claims broadly; the package comparison does not establish which specific new loan caused each loss. The observed post-work payroll-credit-funded diagnostic was zero in the late window, so the higher debt should not be attributed specifically to the new gate's loan requests. Existing earlier financing and changed economic feedback are also present.

The data establishes fewer Food purchases and lower health together, but does not isolate the causal channel. It also does not establish why all observed debt, housing and Services responses differ. Those are follow-up questions, not authorization for more changes or simulations now.

## Later-pay comparison

Late-window three-seed means: jobs +4.64%, paid wages +7.77%, Services units +9.85%, nominal GDP +6.12%, Food units +0.81%, happiness +0.0025 and health +0.0053. Jobs, wages, Services units and GDP rose in all three seeds. Services access nevertheless fell by 3.59 households on average; more units did not imply more distinct customers. Mean bank debt rose 17.64%; week-200 cumulative bank-funded writeoffs averaged $3,622.24 versus zero. Private current short-pay and claims were zero throughout all candidate cases here too. These results retain the later-pay liquidity constraint.

## Checks and runtime limits

The economy analyzer reports all paired initialization/profile/RNG/configuration checks passing. All six baseline initial states and their 200 recorded economic rows matched the earlier cash-research controls after symmetrically excluding runtime fields and the five new payroll diagnostics. This is recorded-prefix compatibility, not complete hidden-state equality across different horizons.

Maximum absolute money residual was $0.0000071563; clearing residue was $0.000000000569. These checks are within the declared tolerances. The separate final configured Linux suite previously passed 1,569 tests with two skipped, eight deselected and one expected failure. No new suite was run for this report.

The owner curtailed the oversized runtime panel. There are 31 completed timing cases: 20 at 1,000 households and 11 at 10,000. The next large case was interrupted. Delegate and remaining worker were stopped; completed files and previous interrupted evidence were preserved. No replacement worker or experiment was started.

For the completed matched timing cells, using weeks 41–80 and geometric means of five paired run ratios: standard 1k median ratio 0.9013 and p95 ratio 0.8772; later-pay 1k median 1.0215 and p95 1.0047; standard 10k median 0.8954 and p95 0.8741. There is no completed later-pay 10k pair. These are descriptive point estimates from seed 42 with changed economic work. The planned full-panel interval gate is incomplete; this report claims no blanket 5% runtime pass, isolated overhead reduction or general speedup.

Routine fix experiments now use 1,000 households. Large scale checks require a specific question and separate proportional budget; they do not automatically receive the same repetitions. No more runs are scheduled by this report.

## PR integration and local verification

Merged current main `b233cd74fc570ab0b38665fcc94187f6ca37ef27` into the branch without changing the tested backend or Python test configuration. The backend remains byte-identical to the previously full-suite-tested candidate. A fresh focused run on the integrated branch passed **236 tests** in 3.73 seconds, with imports verified against this worktree. No frontend changes are introduced by this PR. The research selector retains its compatible `instant` default; the delayed research variants, including `project_cash`, remain explicit Python configuration choices. The private payroll and received-budget fixes apply to their declared funded-payment paths independently of the research selector.

[Portable per-seed evidence](PAYROLL_BUDGET_EVIDENCE.json) contains source/capture hashes, initialization/configuration fingerprints, all recorded economic metric means and endpoints, and test-log hashes. Raw simulation captures remain local in the external experiment directory named below.

## Evidence and scope

- `economy/analysis.json`: 12 cases, 2,400 ticks, initialization and accounting checks.
- `economy/raw-summary.json`: per-case endpoint and late-window measurements.
- `economy/control-replay.json` and `continuation/owner-stop-integrity-check.json`: six control prefixes, original 484 artifact hashes, frozen sources and recorder checks.
- `economy/cases/` and `timing/cases/`: retained raw measurements.
- `continuation/OWNER_STOP.md`: owner-directed cancellation and future run budget.
- `continuation/`: preserved execution logs; the earlier failed comparison and interrupted attempts remain separately recorded.

The core private payroll constraint worked in this bounded screen. Broader economic effects are mixed, and the package is not a universal wellbeing improvement. No new economic mechanism was added while preparing this readout. Full parent pstack certification remains incomplete. OpenWiki refresh remains due; Actions remain disabled. No push, PR, merge, server-default migration or additional simulation was performed for this report.

External raw evidence: `C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/payroll-budget-experiment/`. Portable repository evidence is linked above so reviewers can inspect per-seed values without that local directory.
