# QUALITY-CASH-01: invest actual post-payment cash

Rules v1.19, source `469cf39ef1e17fe59b9210bbccffd6f94c491fb1`, authoritative main `8a8d380`. The owner selected this local experiment after the prior panel: "it should just use however much money they have left post paying" and the old cash stock is an indicator of funds they could spend. The parent disclosed retaining the existing six-week operating/debt reserve and paying the program over its months. No publication or default promotion is selected.

## Problem and selected change

The prior A model imposes two limits: a recent-cash-generation share and a fixed 1,200 project quote, or 30 per funded week. An isolated actual-method probe with 100,000 starting cash paid the same 30/week at supplied generation of 1,000 and 5,000/week, and paid zero at generation 100 despite ample cash. This is decision evidence, not an economy experiment. Merely loosening the profit cap leaves the quote ceiling intact.

Add one `project_cash` alternative over A's existing lifecycle. The research program's initial budget is all eligible post-payment cash above the existing reserve. With cash 10,600 and a reserve of 600, a program quotes 10,000 and pays 250 per funded tick for 40 ticks. Recent profits can be negative; they do not veto affordable research. With less than 1,200 eligible spare cash, no new program starts: preserve the existing minimum resource requirement rather than permitting free quality from arbitrarily small payments.

This is an owner-selected cash-allocation experiment, not an empirically calibrated research production function. It commits a larger research-service budget without promising a larger or faster gain. A failed project still buys an uncertain attempt. Earlier evidence supports uncertainty and liquidity effects; it does not establish that spending all spare cash is optimal. The comparison must expose adverse effects rather than tune to restore old GDP.

## Data, timing and cash boundary

Use the existing optional `ResearchState`/`ResearchProject`, fixed installment, funded-tick counter and bounded gain history. Add a variant tag, not another lifecycle or cash account. At program start: `budget = max(0, min(current_cash, available_cash) - reserve)`, where reserve is six current operating-cost periods plus capped future bank/direct-Treasury schedules. Quote the budget only if it reaches 1,200. Store its installment as budget / 40. The unpaid program budget is a discretionary commitment, not an escrow, payable claim or debt.

Every installment is bounded by that same fresh headroom. Full installment advances one funded tick; otherwise pause and keep progress. Wage arrears and the coordinator's debt-delinquency/restricted-cash blockers remain. For this alternative only, do not let the opening `survival_mode` flag veto a now-affordable post-sales payment: the fresh reserve and unpaid-obligation checks replace it. Other firm survival decisions remain unchanged.

For a cash program, the future operating reserve uses current earned operating costs plus ongoing funded CEO pay. Older wage claims already paid reduce cash once; they are not multiplied into six more weeks of future payroll. The existing conservative earnings observation can still subtract funded older claims, but that observation does not ration this program. On the final installment only, `math.isclose` with relative tolerance `1e-12` and the common absolute `MONEY_EPS` tolerates floating-point subtraction error at different program sizes; actual spending never exceeds headroom and is the amount sent to recipients. A meaningful cash shortfall still pauses progress.

Keep phase 11.6, the existing phase-9.5 post-debt snapshot and the pre-installation cash ceiling. New public installation receipts cannot immediately enlarge the budget. Cash is a stock, potentially including earlier startup/working-capital financing; it is not earnings. This alternative originates no new research loan and changes no loan collector or claim priority. Later capital spending and dividends can compete for cash and cause future pauses; neither is redesigned.

An active program retains its quoted installment, variant and funding policy when switching between project-model selectors. Mode choice affects the next program. The earnings EMA remains available as existing observation state, but does not cap a cash program's funding. Risk tolerance still affects other firm behavior; it does not ration this owner-selected all-spare-cash allocation.

## Quality and counterparties

Reuse A exactly: 40 funded ticks; 15% failure; successful gain `0.35 * (1-q/10)^1.5 * min(3, exp(N(0,.5)))`, keyed by firm identity/project sequence. Keep the 1.0 rolling-52-tick cap, no automatic decay, baseline quality 0.1/no research and unchanged private starting products. A and cash programs with identical identities, starting quality and funded schedules have identical outcomes. More money buys a larger program, not extra completions or guaranteed quality. The existing recipient route remains the explicitly abstract research service.

Each actual installment debits the firm once, credits investment tax and the existing miscellaneous route once, and advances only once per tick. Household decisions, funded demand, staffing/capacity, wages, dividends, tax rates, Housing and Healthcare are outside this change. `instant` remains default. New work is O(1) per eligible firm with no new history/search/cadence.

## Proof and comparison

Prove cash-rich/loss-making funding, fixed total quote, gradual drawdown, no reserve crossing, minimum start budget, pause/resume, active-variant consistency, idempotence and exact A outcome equivalence. Use real `Economy.step` in both named sequences to prove actual debt/CEO/old-wage payment priority, restricted installation cash, recipients, payroll freeze and cash/claim reconciliation. Run existing A/B/default tests unchanged.

Compare old behavior, current A and cash funding with frozen sources and common non-quality initial profiles/config/RNG. Start with a bounded screen, then examine the late horizon needed for the prior seed-44 housing/access concern. Report private Food/Services and total firm cash, actual research spending/completions/pauses, wages/jobs, real units/access, household cash/deposits, Treasury cash, debt/arrears and GDP/wellbeing. Cash remaining above working reserves and unpaid program commitments have different meanings; do not label all retained cash hoarding. Old aggregate cash is a reference, not a target forced by tuning. Preserve controls, rejected attempts and provenance. Keep all work local, Actions off and generated OpenWiki untouched pending approved tooling.
