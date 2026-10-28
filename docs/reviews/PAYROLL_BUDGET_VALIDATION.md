# Funded private work and received-income budgets: local validation

PAYROLL-BUDGET-01 / rules v1.20, implementation `558a6a005c25ea47ce0c0a58a68b59b580ebe53f`, control `a7a8cf38e09cbd02629eec94ca599e85082d10a7`, authoritative main `8a8d380`. Owner selected affordable private staffing before work and budgets after actual wages/benefits. The standard early-pay flow is the reference; exact sequence names remain in test and experiment records. The default-sequence migration is not silently made here.

## What changed

Ordinary private Food/Services first resolve actual contracts, including skill/experience premiums, offer floors and scheduled raises. A pre-work check uses available cash and one bank-approved working-capital request, capped by the existing per-firm amount, leverage and underwriting. It adds no Treasury fallback or relaxed debt-coverage rule. If funding is insufficient, new hires are cancelled first and remaining staffing reduced until complete contracts are affordable. Cancelled workers gain no work experience, produce no output and create no new current wage claim. Older earned balances retain their existing owner and repayment path.

Only the matched private households' history updates are deferred until final funding; other households retain their application path. Roster and raise traversal/RNG order are preserved. Private wage expectations now see the raised pre-work contract, an explicit timing change in the contract. Services retains installed space, resets recovery evidence after financial cuts and permits one funded restart from zero workers; further recovery still needs three strong-sales observations. Public Services installation requires a retained, paid extra hire and never creates a slot for a rejected worker.

Shopping decisions use this tick's canonical funded net wages and benefits. Current cash already contains those receipts, so no forecast cash is added; savings drawdown excludes them. Signed cash, accessible deposits, priority bills, tax ownership, old-claim receipts and held CEO pay remain distinct. Normal seller decisions still run once per tick; performance-mode full-plan refresh/reuse retains its existing five-tick cadence, with actual-cash checks at purchase. The later-pay comparison and old payment sequence retain their declared timing. No new seller search, re-shopping or household wage-reliability model is added.

Baseline providers, Housing and Healthcare are outside the private staffing gate. Baseline Healthcare keeps the minimum-base-wage/profit-bonus rule and medical staffing protections requested by the owner. This preserves its mechanism; it does not turn that wage floor into a newly funded public guarantee. Baseline-provider unpaid wages remain a separate disclosed issue. Research models, rates, minimum wage policy, public transfers and UI are unchanged.

## Checks executed

- **67 new focused cases**: private actual-payroll funding, genuine registered bank claims/repayment/mirrors, denial/capped credit, actual matching premiums and raises, history/output/roster/events, prior claims, Services recovery and real public installer; actual income, savings, signed cash/deposits/bills, benefits, CEO holds, receipt timestamps and normal/cached cadence.
- **135 focused cases passed** in the final arithmetic/care/payment selection; scoped Ruff and diff checks passed.
- **Final configured Linux suite: 1,569 passed, two skipped, eight deselected, one expected failure**, 188.48 seconds. Receipt prints implementation HEAD 558a6a0, interpreter and assigned-worktree backend imports. This is a Linux result, not a new Windows full-suite claim.
- The initial full suite had 1,557 passes and two test-double signature failures. Fixed-plan mocks were updated to accept the existing planner's settled-income keyword; their economic assertions were retained. The old full-step partial-private-pay tax fixture now explicitly uses a baseline employer, since private current-pay prorating is the selected behavior being removed. Direct settlement partial-pay tests remain intact; new real matching tests cover private rejection/funding.

Logs are preserved under `C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/payroll-affordability-followup/`: initial/final focused selections and both Linux full-suite receipts. No thresholds, expected macro outcomes or snapshot hashes were weakened to pass.

## Independent review and correction

A read-only Terra scout mapped existing fixtures, actual matching, financing and medical boundaries. An independent Sol integration review recommended splitting contract assignment from work history, avoiding snapshots or reapplying a stateful household decision. A fresh Sol code review independently passed the original 57 new cases and compared six old/new labor-phase cases on the old payment sequence (ticks 50/52/100, weekly skill learning on/off); every serialized agent field matched in those cases.

The code reviewer found one P2: subtracting a huge dismissed wage from a rounded total could authorize a slightly underfunded retained worker and fail only after production. The parent corrected that finding using compensated cash-gap calculation and exact affordable-suffix selection on the distress path. Fully funded private settlement now pays contracts directly rather than introducing proportional roundoff, and unrepresentable bank cash movements are not originated. Ten numerical boundary regressions were added; all 67 new cases are included in the final full suite. The correction was verified by the parent instead of commissioning another review for this small finding. No other selected-scope P1/P2 was found in the independent review.

This is source and integration evidence, not proof of economic benefit or a runtime pass. Full pstack certification remains incomplete; the architecture/scout/review evidence does not retroactively certify the older incomplete workflow.

## Engine screen and pending measurements

The frozen recorder compares the same cash-funded research model in both source arms, isolating the declared payroll/budget package rather than changing research simultaneously. Frozen control a7a8cf3 contains 217 backend files; candidate 558a6a0 contains 220. Recorder SHA-256 is `98516502b73d0e0a12ec1efd61f6b70189cbd00117f92fe6e7f491e766e73620`.

The corrected two-case pilot completed 20 ticks per arm with matched initialization/profile/RNG/configuration and passing accounting checks. Maximum money residue was 0.0000000242144 and clearing residue 0.000000000106695. Candidate private current short-pay and wage-claim stocks were zero. The control's 20 recorded economic rows and initial state/RNG reproduce the prior cash-case prefix exactly after excluding timing and the five new diagnostics. This is a short integration screen, not a welfare/runtime result or proof of full hidden-state identity.

The first pilot failed on a recorder-only undefined-ID reference introduced while fixing identity reuse; its script, failed capture, protocol and logs are retained. The recorder was corrected before formal runs. Identity-epoch keys now preserve just-exited firm flows without confusing a replacement firm using the same numeric ID. No simulator source or calibration changed for this recorder error.

The bounded formal comparison is prepared: 12 normal-mode economy cases, 200 ticks each, three seeds and both timings; then 40 serial timing cases, 80 ticks each, 1k/10k households and five repeats of seed 42. Official outcome window is weeks 101-200; timing window weeks 41-80. Paired p50/p95 intervals, provenance/control replay, private claim/payment invariants, actual jobs/wages, real delivery/access, wellbeing, debts/defaults and cash stocks remain required before interpreting the package. New fully paid work can mean fewer jobs/output if financing fails; bank credit can preserve jobs while adding lender/default exposure. GDP alone will not settle acceptance.

External evidence and execution scope are in `C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/payroll-budget-experiment/`. Frozen inputs and older experiment artifacts remain unchanged. No economic or 5% performance acceptance is claimed yet. The parent owns final interpretation and the follow-up results report.

OpenWiki refresh remains due: the approved local command is unavailable and generated pages were not hand-edited. GitHub Actions remain disabled. Code and evidence are local; no PR, push or merge was performed.

## Completed comparison and PR preparation

The [completed results](PAYROLL_BUDGET_RESULTS.md) and [portable per-seed evidence](PAYROLL_BUDGET_EVIDENCE.json) supersede the pending-measurement status above. All 12 economic cases / 2,400 ticks completed; six baseline recorded prefixes matched and initialization/accounting checks passed. Private current unpaid wages and claim stocks were zero throughout the candidate cases. Standard-flow mean jobs, paid wages and Services rose, while Food purchases and health fell in all three seeds; bank debt and recorded writeoffs increased. One seed lost jobs and GDP. These are mixed within-model effects, not a universal welfare result.

The owner stopped the oversized timing panel after 31 completed cases. No engine workers or replacement runs remain; the interrupted case, completed captures and earlier failure evidence are preserved. The full runtime acceptance gate is incomplete. Routine fix experiments use 1,000 households; large-population checks require a specific scaling question and a separate proportional run budget rather than automatically matching the small-run repetitions.

Current main was merged cleanly for PR preparation. Backend files and Python test configuration are unchanged from the full-suite-tested 558a6a0 candidate. A fresh focused run passed 236 tests in 3.73 seconds on the integrated branch, with worktree imports verified; scoped Ruff and diff checks passed. Research variants remain opt-in with the compatible `instant` default. The earlier default-sequence migration remains outside this PR. GitHub Actions remain disabled and OpenWiki refresh remains due.
