# Economic-model audit: verification and disposition

**Later implementation update:** W01/W02 have been corrected and verified in the [concrete package](../ECONOMIC_CONCRETE_PACKAGE.md). The findings and pre-fix results below are retained as historical evidence.

Prepared by Codex on 2026-09-21 after the requested [Claude Fable 5.1 review](ECONOMIC_MODEL_FABLE_AUDIT.md). Read this alongside the [original proposal](../ECONOMIC_MODEL_PROPOSAL.md) and [shared working contract](../ECONOMIC_AGENT_WORKING_CONTRACT.md).

## Review provenance and limits

Claude Code successfully authenticated with the requested account. Its primary review model was `claude-fable-5-1`, confirmed by initialization and returned model-usage metadata. The review completed successfully after 54 repository read/search calls, with no reported read errors. Claude had no code-execution or file-write tools. Its report is preserved as returned; the coordinator saved it to disk. The [run manifest](ECONOMIC_MODEL_FABLE_AUDIT_RUN.json) records model identity, input hashes, economic-source hashes, the earlier failed authentication attempt, and the report hash.

The economic source still matches audited commit `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`, which was checked against GitHub main again before the successful review. No economic-engine changes were made. Fable inspected code but did not run the probes or independently open the economic research URLs. Its recommendations are review input, not empirical validation or an approved implementation plan.

## Additional checks performed by Codex

The following bounded diagnostics were executed after reading the relevant source. They demonstrate particular mechanisms, not the size of their effect in a full policy comparison.

| ID | Check | Observed result | Implication |
|---|---|---|---|
| E06 | Government-funded bank loan: principal 100, repayment obligation 110 over 10 ticks; collect one repayment | Borrower cash falls by 11; bank reserves and government cash do not increase; loan balance falls to 99 | The repayment path lacks a cash recipient. [A01] [A02] |
| E07 | Issue one bank medical loan of 520; run bank collection, then household settlement with no tax/transfer/purchase plan | Bank receives 10.45; treasury additionally receives 1.50; bank loan remaining is 532.95 while the household field is 531.45 | The same loan reaches two repayment paths and its records diverge. This does not measure lifetime overpayment. [A02] [A03] [A04] |
| E08 | Call the surplus-spending method with treasury cash 55,000, 60,000, and 65,000 | Payments are respectively 0, 0, and 1,800 | Spending is 12% of cash above the 50,000 reserve **only when the surplus exceeds 10,000**, so the cash trigger is strictly greater than 60,000. [A05] |
| E09 | Create the seeded 200-household economy and inspect baseline-firm owners | All four baseline firms have household owner IDs | The baseline designation does not establish public ownership of their surplus claims. [A06] |
| E10 | Give a non-baseline firm price 100 and disable its stabilizers; call its pricing planner | Planned next price is 102 | The switch changes the private pricing algorithm. Subsequent settlement, constraints, and index construction determine realized inflation. [A07] |

Reproduce these observations from the repository root:

```bash
PYTHONPATH=backend python3 -B docs/reviews/verify_fable_findings.py
```

The [probe source](verify_fable_findings.py) contains the setup and assertions; [machine-readable results](ECONOMIC_MODEL_AUDIT_PROBE_RESULTS.json) record the executed checks and source hash. The probes perform no provider calls or persisted simulation runs. After a correction, update the diagnostic expectations instead of treating the current faults as desired regression behavior. E01–E05 remain in the original proposal.

## Disposition of Fable's findings

These are coordinator assessments of the review, not approvals from Ayman.

| Finding | Disposition | What carries forward |
|---|---|---|
| F01: fiscal closure | Accept with corrections | The current asymmetric closure needs to be explicit: transfers can create negative treasury cash, discretionary investment has cash conditions, and surplus recycling reaches the miscellaneous-pool beneficiaries. Use E08's exact threshold. Claims that this is the **largest** bias or explains **most** of a tax comparison remain unmeasured. |
| F02: additional accounting paths | Accept for investigation; two paths reproduced | Prioritize reconciliation of government-funded repayments and medical debt alongside entry, exit, shocks, and the miscellaneous pool. New entrant inventory is category-specific: Food receives 100 units; Services, Housing, and Healthcare receive zero in the inspected constructor. Initial capital and housing capacity also need an explicit interpretation. [A08] |
| F03: existing owners | Accept | Reuse the existing ownership representation where possible. Record that initial baseline firms have household owners while the entrant constructor does not assign owners. Owner funding is one candidate institution, not a universal requirement for every type of entrant. [A06] [A08] |
| F04: stabilizer bundles | Accept with scope qualification | Add the private price rule and the government-side effects to the toggle inventory. A repeated 2% price-plan rule does not by itself establish realized annual CPI inflation. [A07] |
| F05: random streams and interventions | Accept in part | Existing keyed RNGs deserve credit; inspect keys that depend on policy-sensitive amounts and sampling populations. Identical-seed E01 results remain valid for their recorded state. A comparison needs two branches or identical pre-intervention replays; applying one policy at tick T in only one run does not create a counterfactual. Verify copied economy, configuration, lookup references, and RNG state before relying on deep copies. |
| F06: metrics and consumers | Accept compatibility concern; narrow suggested formula | Prefer additive/versioned metrics with a consumer migration plan. Cash plus deposits minus medical/consumption loans is a partial financial position, **not comprehensive net worth**: ownership claims, education debt, and other assets/liabilities require a valuation convention. Keep the observation time consistent. |
| F07: household budget | Accept timing concern; proposed shortcut needs evaluation | Previous taxes paid could be a cheap input, but lagged tax alone does not make a newly announced tax change enter expected take-home income immediately. Specify the expectation rule and update scalar/batch paths consistently. Disclose the existing tax schedule without prioritizing bracket redesign. |
| F08: production scope | Accept as a staging option | A small investment-delivery abstraction may precede new input markets. Caps, delays, and diminishing returns still need economic justification and sensitivity analysis; low computational cost is not evidence of economic validity. |
| F09: inflation and healthcare | Accept scope direction | Label inert controls accurately across their consumers. A zero patient copayment must still reconcile provider payment, government financing, capacity, and medical debt; a payer flag alone is not a validated healthcare system. |
| F10: worker integration | Accept missing dispatch artifacts; correct one characterization | The original contract already names the integration owner for metrics. It does not yet provide a completed field-level writer map for a selected package. That map and exclusive shared-symbol assignments must precede coupled parallel work. A hand-selected prime in an RNG seed expression does not guarantee independent, collision-free streams. |
| F11: ticket detail | Accept with baseline distinction | Add explicit scalar/batch, execution-mode, config, RNG, consumer, baseline, and wiki fields. Require equivalence for unchanged/refactored behavior; document intended divergence for accounting corrections. A permanent default-off flag for every bug fix is not a universal rule. |
| F12: performance | Accept evidence gap; numeric recommendations remain proposals | Measure variation and relevant lifecycle phases on this machine. A 200-tick run or five repeats may be useful starting points, but neither guarantees coverage or precision. Do not automatically relax a runtime budget because measurements are noisy. Distinguish normal mode from performance mode and report uncertainty. |
| F13: implementation comments and taxes | Accept as disclosure items | Function comments and actual telemetry updates differ; cash-percentile profit-tax selection and random surcharge assumptions deserve disclosure. These observations do not reopen tax-bracket redesign as a main priority. |

The review's proposed wiki correction is not established: replanning every fifth tick can mean reusing the resulting plan for the four intervening ticks. Clarify cadence if needed; the wording alone does not demonstrate conflicting behavior. Generated wiki pages were not hand-edited.

One suggested metric also needs correction before implementation: **do not sum negative treasury balances over time and label the result public debt.** That would repeatedly count the same shortfall. A defined financing gap is a stock at a point in time; debt requires a stated financing and accounting convention, consistent with P02.

## Revised sequencing recommendation

The review supports a small first package, before dispatching several implementation workers:

1. Define the paired experiment, common pre-policy state or replay procedure, complete configuration, effective tax burdens, stabilizer settings, mode, and outcome definitions.
2. Add a diagnostic reconciliation of existing flows and complete the writer/counterparty map. Measure which paths materially affect the intended comparison.
3. Add clearly named resource, poverty, price, and output measures with consumer compatibility and consistent timing.
4. Correct selected accounting paths together with their counterparties. Validate both the intended corrections and unaffected behavior.
5. Make the current fiscal closure explicit, then define alternative closures for the chosen comparison. The source cannot determine which closure Ayman wants to compare.

Full bond markets, elaborate capital/input markets, additional labor choices, insurance institutions, and political-economic presets can remain staged extensions. This does not reject those goals; it keeps the first package bounded and testable. The shared contract now includes the additional ticket fields and coordination requirements. No worker implementation tickets have been dispatched.

## Source anchors for the additional checks

[A01]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L6510-L6575
[A02]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L5970-L6054
[A03]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L6727-L6778
[A04]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L1223-L1226
[A05]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L7122-L7164
[A06]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/tools/runners/run_large_simulation.py#L250-L260
[A07]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L4545-L4550
[A08]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L4783-L4829
