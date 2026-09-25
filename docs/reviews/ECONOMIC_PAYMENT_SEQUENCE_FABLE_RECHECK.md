**Verdict: all ten findings are addressed for a proposed pilot.** PS3.1 closes PSF01–PSF10 with written, source-locatable rules. No blocking ambiguity remains. Implementation, performance and empirical claims stay unproven: nothing was run, and the cumulative runtime budget is unmeasured.

## PSF01–PSF10 disposition

| Finding | PS3.1 rule | Basis | Status |
|---|---|---|---|
| PSF01 wage mirrors | Write-through of both mirrors at every existing writer; frozen phase-5 payroll separate | Coordinator-selected over my 5a-only fix; Firm, Household, Housing, Care, Government acknowledge | Closed. The stronger rule is correct: a 5a-only write-back would not survive the roster sync after a phase-9 cut |
| PSF02 payout before wages | Arrears above tolerance block dividends and discretionary care bonuses at 16 | Coordinator-selected stricter gate; Firm and Household explicitly accept; Housing, Care, Government acknowledge | Closed. Unchanged 9.5 lender priority is disclosed by Bank, Firm and Household |
| PSF03 fiscal-close clock | After phase-16 payouts, before household ledger finalization; post-exit unemployment count; investment tax excluded from A fraction | Coordinator-selected end-16; Government accepts exactly; Housing, Care acknowledge | Closed. Verified locatable: dividends end at `economy.py:2101`, ledger finalization starts at `economy.py:2103` |
| PSF04 unpaid employed | No new exit trigger; B-ineligible; count, shortfall, claim and duration reported | Coordinator-selected limitation; Firm, Household, Housing, Care, Government accept | Closed as monitored limitation, not solved |
| PSF05 exit recovery | Recovery before write-off; named claim survives layoff; gross moves to protected Economy hold; paid through next 5a book | Coordinator added the hold (OA02); Firm, Household, Government accept the tax clock; Bank pre-accepted worker-first exit only | Closed. Near-zero recovery stated as inference, not measurement |
| PSF06 phase-9 order | Clearing credit, tax debit, streak, metrics, then dual-mirror wage commits | Firm and Housing acknowledge | Closed |
| PSF07 treasury routes | Seed cash and treasury-funded firm loans, including phase-1 bridge, under the free-cash guard | Government accepts | Closed |
| PSF08 Services floor write | Kept once at book build, then frozen | Coordinator disposition; no role acknowledgment | Closed. None needed; goods owner is Economy |
| PSF09 rollback | Re-initialization under K07 discipline; no saved-state claim | Coordinator disposition; no role acknowledgment | Closed |
| PSF10 phase-10 collector | Named, kept after 9.5, before exits and dividends, claim-ID deduplicated | Government accepts | Closed |

## Orchestrator additions OA03–OA05

Source checks confirm the premises. Rent credits the landlord directly at `economy.py:5896`, while the tax snapshot builder and phase-15 statistics read only the goods sale book. The fiscal-pressure denominator first sums each firm's stored revenue, which is set inside the firm's sales method, so broadening that field with rent would silently move the denominator. PS3.1 pins all three readers to one typed goods/care proxy and keeps Housing cash and occupancy separate. The subsidy cap in `fiscal_guards.py:97` does apply a floor of one to the denominator; PS3.1 preserves it and replaces raw cash with unencumbered cash. Firm, Housing and Government acknowledge these rules. They do not claim national accounts, and PS3.1 says so.

## One non-blocking wording gap from OA04/OA05

The written fallback chain for the G denominator is current, then prior comparable proxy, then floor 1. Source's trailing helper at `fiscal_guards.py:24` has a fourth step before the floor: a population-scaled fallback of 25 per household when no history exists. PS3.1 drops it without saying so, while OA05 says the existing floor is preserved. This affects only the first tick or two and hits both arms equally, so it does not bias the comparison. It still lets two implementers set different opening subsidy caps.

Exact fix, one sentence in §5: "The G denominator chain is most recent positive goods/care proxy, then last committed goods/care revenue, then `max(1, 25 × households)` as in the existing trailing helper; no other fallback."

## Record notes on acceptance

- **Bank** has no PS3.1 section. Its file ends with the pre-Fable final acknowledgment. That earlier text already accepts worker-first exit ahead of bank claims and the credit gate, which is all the corrections touch on the bank side. Bank's acceptance of the recovery hold itself is not on record and should not be inferred.
- **Housing** labels its acknowledgment "conditionally accepted." The stated condition is that the one 5b draw and the current-rent, arrears and notice rules stay unchanged. PS3.1 §§3–4 keep them, so the condition is met. Housing and Care both name the early 5a CEO hold debit as a provider-liquidity cost before 6.6 repairs and 6.6b mortgage service.
- **Household** now records Bank's actual relayed replies, superseding its failed-send note.
- PSF08 and PSF09 rest on coordinator dispositions alone. Both are Economy-owner or infrastructure rules, so no role signature is required.

## Retained limits

Core actors, progressive brackets, heterogeneous traits, bounded cadence and development-only role LLMs remain. The contract proposes source changes that do not yet exist: the payroll book, claims, holds, guards and the exit-recovery path. Paper cases in §6 were arithmetic checks, not executions. No effectiveness or welfare claim is authorized, and the 5% cumulative runtime target has not been measured.
