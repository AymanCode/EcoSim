# Economic implementation execution record

**Integrated implementation, 2026-09-22.** Ayman authorized the accepted economic improvements, including the coordinated payment cycle. Sol medium implemented bounded modules in an isolated candidate; Codex reviewed, corrected, exercised and integrated the changes into the original working checkout. Fable independently audited two frozen source snapshots. The [review record](reviews/ECONOMIC_IMPLEMENTATION_REVIEW.md) separates correctness evidence, economic assumptions and the unmet 5% performance target. No per-agent LLM runs inside the simulation.

## Authority and common contract

The frozen starting state is the live `origin/main` commit `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`, plus the existing local changes and integrated PAY-01. Preserve those changes. The implementation follows [PS3.1](proposals/agent_round_02/PAYMENT_SEQUENCE.md), its [independent audit](proposals/agent_round_02/ORCHESTRATOR_PAYMENT_AUDIT.md), and [coordinator qualifications](proposals/agent_round_02/FINAL_COORDINATOR_REVIEW.md). Historical reports stay unchanged; this record reports implementation separately.

The core scenario has one authoritative income record, one actual deposit-access pass, a shared price/supply book for both goods passes, and one claim owner per loan or arrear. It follows paid income → essential Food → current rent/arrears → funded care → household debt → residual goods. Actual funding and physical capacity constrain every stage. Cash in a clearing account or a restricted envelope is counted once and cannot be reused. Persistent agent identities and decision cadence remain intact. No per-agent LLM is added to a simulation run.

Named new-run options are `payment_sequence=legacy|income_first|income_late`, `payment_care_mode=patient_pay|covered`, and `payment_assistance=reserve|care|rent|mixed`. The timing arms share funding and claim conventions; only the release of paid net wages/benefits differs. Existing library defaults retain `legacy` for compatibility. The application must explicitly select and display its new-run scenario; an active run cannot change its payment convention.

## Ownership during the payment implementation

| Worker | Exclusive write ownership | Main review boundary |
|---|---|---|
| Payment integration | `backend/economy.py`, `backend/agents.py`, `backend/config.py`, `backend/payments.py`, `test_payment_core.py` | Payroll/benefits, restricted cash, holds, exits, once-only tick integration and telemetry |
| Sector payments | `backend/payment_sectors.py`, `test_payment_sectors.py` | Food and residual goods share supply/prices; rent mirrors/notices; qualified, fully funded care |
| Loan payments | `backend/payment_loans.py`, `test_payment_loans.py` | Versioned due index, actual-funder settlement, default/discharge and atomic medical credit |
| Coordinator | New independent acceptance tests, implementation records; public wiring assigned after module handoff | Cross-module accounting, public configuration, full-step behavior, scenario evidence, cumulative performance and integration |

The concrete module interface is communicated directly among workers. `PaymentBook` owns actual income and goods/care cash/payables; sector code owns stock/throughput and delivered service; loan code owns indexed scheduled dues and lender claims. No worker edits another worker's file without a recorded transfer of ownership.

## Complete queue

| Package | Selected result | Current state |
|---|---|---|
| PAY-01 | Paired wage contracts and immutable current earnings | Integrated; verification in the linked implementation plan |
| PAY-02–04 | Full PS3.1 payment and funding scenario, public selection and reported shortages | Integrated; tested through the public tick, setup and websocket boundaries |
| Household | Lagged ordinary take-home estimate; obligation-aware desired budget; observable net-offer diagnostic | Implemented; observed-offer arithmetic remains diagnostic |
| Firm | Settled capital-payment routing; sellable investment gate; funded entry/exit; selectable benefit-linked wage floor | Integrated; composed cash reconciliation covers both timing arms and execution modes |
| Government | Actual-receipt destinations and one staffed, funded Services-capacity project | Implemented; the project is an explicit opt-in experiment |
| Bank | Versioned schedules and due index; settled-income underwriting; separately named quote stress experiment | Implemented; new bank entry credit requires history and is denied for an unestablished firm |
| Care | Qualified capacity and full-price funded delivery; persistent need and charge-sensitive requests | Implemented; denied visits retain their episode without becoming new arrivals |
| Housing | Partial rent and notices; separate ask/contract renewal; funded delayed construction | Implemented across self, mortgage and long-term funding routes |
| PAY-05 | Independent composed audit, paired scenario evidence, repeatable replay, cumulative performance | Audit and evidence recorded; the new scenario exceeds the 5% speed target and is not performance-accepted |

The selected minimum versions preserve diagnostic-only net-job-gain and quote experiments where behavior is not established. General inflation control, calibrated triage/training, and ownership/government-system presets still require their own institution specifications; an inflation target or regime label alone is not an implemented mechanism.

## Selected assumptions and public access

These constants close implementation choices; they are not estimates calibrated from real economies. Research motivation and cross-role objections remain in the [reviewed proposal pack](proposals/agent_round_02/README.md).

| Mechanism | Selected assumption | Why it exists / practical limit |
|---|---|---|
| Paid-income timing | Early by explicit dashboard default; late comparison; legacy library default | Compare the within-week liquidity effect under the same funded-payment rules. Opening stocks still finance the first cycle. |
| Care request | Charge slope 0.5; 0 and 1 available for sensitivity | Separate having a need from requesting a priced visit. Qualified supply and full payment still gate delivery. |
| Housing contracts | 52-tick renewal, soft 5% / strict 2% cap per renewal | Stable contracts separate tenant rent from a provider's current vacancy ask. |
| Housing supply | 1,000 per whole unit, at most 4 per project, four-tick lag; zero-lag comparison | Capacity needs an actual payer and a completion date. Construction remains an implicit recipient sector, not a material/labor production chain. |
| Loan distress | V2 default after 8 consecutive missed installments; 4/12 sensitivity; 26-tick cooldown | Partial payments count as misses; repayment, writeoff and borrower discharge refer to one claim. Mortgages only gain miss telemetry. |
| New credit | Debt service at most 35% of prior settled repayment income, after existing dues | Future promised wages/sales do not fund today's loan approval. A new firm has no history, so its bank seed tier is denied; fully debited founder funds or funded Treasury seeds remain possible. |
| Interest experiment | New-bank quote shift bounded to ±5 annual percentage points | Existing fixed-rate contracts are unchanged. This is not an inflation target or central-bank reaction rule. |
| Benefit-related wage floor | Existing 1.5 multiplier or 0, for Food/Services | Isolate this existing wage-floor rule while preserving other minimum-wage constraints. |
| Public capacity project | Off by default; full 1,000 quote, one incremental paid worker-week, one Services slot from the next tick | Public spending needs fiscal space, a worker, an actual payment and delivered capacity. It does not create doctors or housing. |
| Rent relief | Initially active tenancy, frozen low pre-policy liquidity, verified current rent shortfall | The prior-receipt envelope pays the landlord directly; current shortfall precedes old arrears, capped at one weekly rent. Later tenants do not silently inherit eligibility. |
| Random cash disturbances | New scenarios route positive shocks from free Treasury cash and negative shocks back to Treasury | Keeps an explicit counterparty and preserves reserved funds; this is a fiscal-shock abstraction, not money creation or an inflation mechanism. Legacy retains its original exogenous shocks. |

The dashboard exposes payment timing, care funding and use of receipts at launch. Advanced sensitivity parameters are validated `SETUP` inputs, persisted in the session/warehouse configuration and the immutable payment-parameter evidence snapshot. `metrics.payment` exports paid and denied income, wage claims, rent/care outcomes, restricted cash, claim/default status and projects. Internal diagnostics are not a complete checkpoint format.

## Acceptance

Exercise the public `Economy.step()` boundary in both normal and performance modes, including shortage, stale cached desire, changing jobs, loan final installments/default, provider exit, late income and multiple ticks. Reconcile cash and claims between actual counterparties and stock/capacity with delivery. Test public new-run configuration and session isolation. Preserve progressive taxation; reject invalid values rather than silently clipping an invalid net payment.

Benchmark baseline/candidate in interleaved repeated runs at 1,000 and 10,000 households in both modes. Report median/p95 changes, variability, workload composition and memory against the shared 5% engineering target. A changing number of firms is not evidence of faster algorithms. A confidence range crossing the target remains inconclusive. Refresh generated Wiki using its approved tool after integration. Final status must state what is implemented, executed, audited, performance-accepted, or still incomplete.
