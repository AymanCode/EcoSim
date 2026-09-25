# Economic implementation: Sol builds, Codex reviews

**Current follow-through, 2026-09-22:** Ayman authorized the complete accepted queue. The [execution record](ECONOMIC_IMPLEMENTATION_EXECUTION.md) and [implementation review](reviews/ECONOMIC_IMPLEMENTATION_REVIEW.md) supersede the PAY-01-only status below. PAY-02–04 and the selected household, firm, bank, care, housing and public-project mechanisms are integrated in the original working checkout; composed verification and performance evidence are recorded there. The new scenario exceeds the 5% speed target, so performance acceptance remains open. Long-term inflation/governance institutions remain separate design work.

**Selected workflow, 2026-09-21.** Ayman initially selected AGY CLI with `gemini-3.8-flash-high`, then authorized Sol low/medium or Luna max after the trial needed repeated correction. The current implementation worker is **Sol (`gpt-5.6-sol`) on medium**. Codex owns assignments, shared interfaces, independent source review, verification and integration. Fable remains an additional reviewer for the composed payment change. A successful model response is not an acceptance result.

The starting contract is [PS3.1](proposals/agent_round_02/PAYMENT_SEQUENCE.md), qualified by the [independent payment audit](proposals/agent_round_02/ORCHESTRATOR_PAYMENT_AUDIT.md) and [resolved review findings](proposals/agent_round_02/PAYMENT_AUDIT_DISPOSITIONS.md). Preserve the [agent rules](ECONOMIC_AGENT_RULES.md) and [implementation contract](ECONOMIC_AGENT_WORKING_CONTRACT.md). The six proposal reviews remain historical evidence; coding does not rewrite them.

## Assignment and review loop

```mermaid
flowchart LR
    A[Codex defines one bounded ticket] --> B[Sol implements in an isolated checkout]
    B --> C[Codex reads the diff and exercises the behavior]
    C -->|Defect or missing case| B
    C -->|Checks pass| D[Integrate the reviewed patch]
    D --> E[Composed economy checks and Fable review]
```

Each ticket names its source snapshot, exact writable files/symbols, economic behavior, counterparties, preserved assumptions and acceptance cases. Workers share interfaces through that contract and recorded coordinator decisions. They do not concurrently rewrite `Economy.step`, or independently decide who debits a shared balance. Initial implementation uses one Sol writer; independent components may run in parallel after their interfaces are fixed.

## Build order

| Stage | Deliverable | Acceptance boundary |
|---|---|---|
| PAY-01 — Wage consistency — integrated | Preserve existing contract-wage decisions across employer/household records and keep current earnings distinct from late changes to future pay. | [Functional checks passed](reviews/ECONOMIC_PAY01_IMPLEMENTATION.md): raises, cuts, healthcare resets, switching, layoffs and roster repair agree; current production cost, ordinary wage receipt and wage tax use the same earned wage. No payment-order change in this slice. |
| PAY-02 — Shared payment state | Define and implement the PS3.1 cash restrictions, due-claim identity, settlement receipts and tick-local books as tested components. | Every affected balance/claim has one owner; actual cash, promises and physical quantities are distinguishable. Components alone do not activate a partial payment sequence. |
| PAY-03 — Income and payment adapters | Implement funded ordinary wages/arrears/withholding and prior-funded benefits; adapt goods, rent, care and household loans to the common books. | Shortages and failure paths reconcile on both sides. The exact Food → rent → care → debt → residual-purchases order uses actual available funds. |
| PAY-04 — Complete tick integration | Connect the adapters as one named scenario contract; remove duplicate legacy settlement in that path; integrate treasury guards, exit recovery, CEO holds, payouts and measurement. | Run the complete PS3.1 sequence across successive ticks in both modes. No half-enabled combination that pays income or sellers twice. Every existing treasury debit respects the selected restrictions. |
| PAY-05 — Comparison and performance evidence | Run paired scenarios, independent review of the actual diff, and interleaved baseline/candidate measurements. | Same initialization/RNG discipline, capabilities and metrics except the declared intervention; inspect subgroup effects and scarcity. Assess cumulative median/p95 runtime and memory, not one favorable run. |

PAY-01 is a narrow accounting/contract correction that can be reviewed independently. Later cash-limited wages and benefits intentionally change the model's financing institutions: an early-versus-late payday comparison must use the same funding constraints in both arms. Merely moving the household update earlier would mix several interventions and replay existing payments.

For integration, preserve the real dirty working-tree baseline, including the completed W01–W05 fixes. The baseline commit is `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`, verified equal to freshly fetched `origin/main`; file hashes identify the additional local work. An isolated candidate starts from those actual files, not just the commit. Copy back only reviewed changes after checking that their originals have not changed meanwhile.

## What follows the payment foundation

The [17 proposals](proposals/agent_round_02/README.md) were implemented as coordinated slices under the subsequent full-queue authorization: household take-home expectations; firm investment and funded entry; versioned lending and settled-income underwriting; qualified healthcare access; housing rents/arrears and funded supply; and explicit uses of public receipts. Selected diagnostic-only variants remain diagnostic. Each role's objections and the [coordinator qualifications](proposals/agent_round_02/FINAL_COORDINATOR_REVIEW.md) still govern the interpretation. Inflation-control institutions and ownership/governance presets need their own selected specifications. Progressive-tax redesign is not a main priority.

## Evidence required before acceptance

- Exercise real `Economy.step` transitions as well as focused shortage, double-payment, job-change and claim-lifecycle cases. Test both normal and performance modes where the changed paths run.
- Codex independently inspects code and reruns checks; the worker's tests and Fable's agreement supplement that evidence. Existing tests must not be weakened to fit a patch.
- Preserve actor IDs, traits, decision cadence and random streams unless a ticket explicitly changes them. Report intentional outcome differences rather than force an obsolete baseline result.
- The integrated runtime target remains at most 5% added median **and** p95 tick time, with interleaved repeated matched runs at 1,000 and 10,000 households in both modes, including a developed private economy. Report uncertainty and memory; an interval spanning the target is inconclusive.
- Refresh generated OpenWiki through the repository's approved tooling when changed behavior is integrated, or record why refresh remains due. Do not hand-edit generated pages.

## PAY-01 history

PAY-01 was completed by Sol medium in an isolated checkout, independently reviewed and integrated by Codex. The AGY trial did reach the exact requested model, but encountered access/workspace problems, repeated large-file reads, an invalid patch and incorrect test assumptions. Codex rejected the first draft, supplied concrete corrections, then stopped the trial when Ayman authorized a model change. Sol reviewed and completed the resulting candidate. The seven temporary AGY access rules were removed; existing permissions were preserved.

The PAY-01 candidate passed **358 tests, with 8 deselected and 1 existing expected failure**, including 12 new regressions. Codex's independent 55-tick probe reported zero wage-record and earned-pay mismatches in both modes; the new tests and probe also passed in the original checkout after integration. [That implementation record](reviews/ECONOMIC_PAY01_IMPLEMENTATION.md) preserves its source archives, hashes, model provenance and early timing. It describes that earlier slice; current full-queue results belong to the execution and review records linked above.
