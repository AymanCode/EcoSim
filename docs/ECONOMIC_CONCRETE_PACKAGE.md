# Concrete economic corrections: W01–W05

**Implemented and verified, 2026-09-21.** Baseline: `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`, checked against live GitHub main before editing. This is the bounded Group A package from [the readiness split](ECONOMIC_WORK_READINESS.md). It preserves progressive taxation, the agents' existing roles, and existing planning cadence. The requested Fable design work for W06–W18 is separate and requires a coordinator audit before any further implementation.

## Accounting decisions

`BankAgent.active_loans` is a **servicing ledger**. Its `govt_backed` flag already means the principal was paid from treasury cash; it does not model a contingent government guarantee. A payment on that loan now goes back to the treasury. An ordinary bank-funded payment goes to bank reserves. Each decreases the same remaining contractual claim and the borrower's debt. The aggregate `total_loans_outstanding`, `last_tick_repayments`, and `last_tick_defaults` continue to include both funding sources for compatibility.

The existing loan convention is retained: total promised repayment equals principal × (1 + stored rate), divided into scheduled instalments. This package does not introduce amortization, compound interest, or a new annual-rate interpretation. Actual receipts, including partial payments, are split proportionally between principal and interest using the contractual schedule. Treasury-funded interest belongs to the treasury; no bank servicing fee is assumed. Only bank-owned interest can fund deposit interest. Zero payment earns no interest and does not reset the missed-payment streak. Payment cannot exceed the remaining claim.

A write-off removes the remaining contractual claim without moving cash. Bank-owned write-offs remain in `loan_loss_provision`; treasury-owned write-offs are reported separately in `government_loan_writeoffs`. Both include the remaining contracted interest, so they are not principal-only capital losses or a full accrual-accounting system. The government does not incur a second cash outflow at default.

Registered medical loans have one servicing phase: `Economy._collect_bank_loan_repayments`, before household settlement. The loan record owns the remaining amount and schedule; household fields mirror it. `medical_loan_bank_serviced` blocks the scalar fallback and therefore the batch path that calls it. Payoff and eight consecutive missed payments clear the corresponding household fields. Consumption-loan default does not reset an unrelated medical schedule.

The legacy unregistered medical fallback remains available under its previous conditions, including employed borrowers if both formal sources cannot fund the loan. Its existing wage-floor-based payment still goes to the treasury. Its origination lacks a funding counterparty; this is an explicitly retained W06 modeling issue, not a claim of complete economy-wide reconciliation.

## Ownership, counterparties, timing, consumers

The integration owner owns this package's shared code. Future workers must request changes to another row's settlement interface before editing it.

| State / interface | Authoritative writer and timing | Counterparty / mirrored state | Consumers and compatibility |
|---|---|---|---|
| Loan `remaining`, `term_remaining`, `missed_payments`; bank `total_loans_outstanding` | `BankAgent.originate_loan`, `collect_repayment`, `write_off_loan`; orchestrated by `Economy._collect_bank_loan_repayments` in phase 9.5 | Borrower cash/debt; treasury or bank reserve recipient selected by funding flag | Bank serialization, credit scoring, deposit-interest budget, aggregate metrics. Serviced portfolio totals retain their existing scope. |
| Firm `bank_loan_remaining`, service-infrastructure sub-balance | Origination paths plus `Economy._collect_bank_loan_repayments` | Registered firm loan claims | Firm serialization / investment and emergency-credit decisions. Direct government-loan repayment remains a separate existing path. |
| Household `medical_loan_*`, new `medical_loan_bank_serviced` | `_issue_medical_loan` at origination; bank collector at repayment/default; `take_medical_loan` only for unregistered fallback | One registered medical claim; household cash and `last_tick_ledger['bank']` | Household serialization adds the servicer flag. No change to frozen forecasting columns. |
| Household cash during legacy medical settlement | `HouseholdAgent.make_medical_loan_payment`, called from `_batch_apply_household_updates` after income/tax settlement | Treasury receives the returned amount; skipped for registered loans | Preserve the fallback's rate/payment assumptions. No per-household loan-ledger scan. |
| Bank-owned vs treasury-owned interest and default telemetry | `collect_repayment` / `write_off_loan`; reset via `reset_tick_telemetry` | Actual funder receives cash; default has no cash counterparty | Add `last_tick_government_repayments`, `last_tick_government_interest_income`, `last_tick_government_defaults`, cumulative `government_loan_writeoffs`. Bank-only interest supports deposits. |
| Run conditions and metric/source definitions | New `backend/run_evidence.py`; comparison runners at initialization, applied policy, changed tick boundaries, completion/failure | Read-only snapshots; no agent or RNG mutation | Standalone versioned JSON sidecar; existing CSV/parquet feature columns preserved. Source hashing stays outside the tick engine. |
| Legacy inflation target capability | Static description in `run_evidence.CONTROL_CAPABILITIES`; controls text in `Config.jsx` | Stored government target is distinct from measured price changes | Existing legacy input remains accepted; clearly inactive, without a new monetary mechanism. |

No agent-network calls, new economic markets, or household-by-loan nested scans are added. Normal and performance modes share the corrected settlement phase; performance mode retains its existing planning/wellbeing cadence.

## Comparison evidence contract

Both comparison CLIs save schema `ecosim.comparison-evidence.v1`:

- `backend.tools.benchmarks.run_policy_sweep` writes `comparison-evidence.json` alongside existing rows/raw/summary files. A failed run has null unavailable outcomes, an error phase and completed-step count, and makes the CLI return nonzero.
- `policy_forecasting.sweep.wrapper` writes `<output-stem>.evidence.json` alongside its existing `.metadata.json`. Successful parquet rows preserve the V1 feature contract. A failed policy arm saves evidence and raises rather than publishing its partial rows as a completed dataset.

Each record captures the seed, factory arguments, effective full configuration at start/end, actual applied government levers (including bracket scalers), stored target, derived benefit/wage/subsidy settings, stabilizer overrides, bank presence, warmup, mode, policy application boundary, observed setting changes, completion count and failure phase. Model identity includes the Git commit, dirty state and individual/aggregate SHA-256 hashes of Python source, so a modified working tree is distinguishable from its parent commit. Platform and runtime versions accompany it. Files are replaced atomically. Planned arms/seeds identify incomplete sweeps; dispatch/export failures are separate from completed simulation records.

Current policy arms apply their changes **after initialization, before the first step**. Same seeds identify independently initialized arms. These manifests do not implement W10 branching or certify matched policy-independent shocks. Settings are observed at step boundaries; this is not a full intra-tick event ledger. The fixed CLI configuration is copied at both ends; future runners that change arbitrary configuration inside a tick need their own explicit configuration events.

Metric definitions describe current calculations, not improved W07 measures. GDP is a nominal sales proxy; `mean_price`/forecasting `price_index` is an unweighted firm-price mean, not CPI; cash-only Gini excludes deposits and claims. The benchmark's unemployment measure is jobless share of all households, while the engine/forecasting metric follows `count_cannot_work_as_unemployed`. The evidence records this distinction. Frozen forecasting composite welfare definitions remain in the source-hashed `distress.py` and `snapshot_manifest` functions; the sidecar lists schema columns, aliases, and source locations.

## Verification and performance

Verification completed:

- **358 passed, 8 research tests deselected, 1 existing expected failure**, across backend contracts, server, data and forecasting tests. The expected failure is the pre-existing three-worker survival-mode layoff issue. [JUnit result](reviews/evidence/ECONOMIC_CONCRETE_TEST_RESULTS.xml).
- Loan checks cover both funders, partial payments, capped payoff, zero collection, missing treasury recipient before mutation, eight-miss default, fallback repayment, consumption/medical default isolation and full ticks in both execution modes.
- Updated E06 records borrower cash −11, treasury cash +11 and unchanged bank cash. Updated E07 records one 10.45 payment, zero extra treasury charge and both medical balances at 532.95. These are **model currency units**. E08–E10 still reproduce their unchanged baseline findings. [Probe output](reviews/evidence/ECONOMIC_CONCRETE_PROBE_RESULTS.jsonl); [reproduction script](reviews/verify_fable_findings.py).
- Observation tests preserve economic rows and Python/NumPy RNG states. Initialization, policy-application, step and dataset-export failures are retained in evidence. Verbose failure reporting is covered.
- Actual benchmark comparison: 8 completed runs; actual forecasting export: 24 rows from two processes/seeds. [Benchmark evidence](reviews/evidence/comparisons/benchmark-comparison-evidence.json), [rows](reviews/evidence/comparisons/benchmark-policy-rows.csv), [forecast evidence](reviews/evidence/comparisons/forecast.evidence.json), [parquet](reviews/evidence/comparisons/forecast.parquet). These are short **functional smoke runs**, not economic policy estimates.
- The frozen forecasting config is byte-identical to HEAD, and `snapshot_manifest` has an unchanged AST. Saved comparison evidence hashes match the delivered backend/forecasting source.
- Ruff passed for backend, forecasting and review scripts. Config screen tests passed (2), the frontend production build passed, and Chrome accessibility/screenshot inspection confirmed the new inflation notice is visible and readable. This was a controls check with the backend offline, not an application-performance claim.

Performance: 32 matched runs / 3,200 ticks. All four population/mode cells met the proposed 5% median and p95 budget **in the observed samples**. Median changes were +4.05% and +1.19% in normal mode (1,000 / 10,000 households), and −0.88% and +1.85% in performance mode. Peak process RSS did not increase. See [the report](reviews/ECONOMIC_CONCRETE_PERFORMANCE.md) for variability, phase/count differences, memory semantics and limitations; host variability means these are not exact causal overhead estimates.

Performance decision before candidate timing: retain the working contract's proposed **5% median and p95 tick-time budget** for this integrated package; this is an engineering target, not an economic calibration or user-imposed threshold. Compare identical factory inputs, seeds, mode, phases, and counts; report repeated timing variability and process RSS. Real economic changes can also change later workload. Benchmark source and raw records are preserved with the results; claims will be limited to measured populations and horizons.

**OpenWiki refresh remains due:** the approved `openwiki` CLI is not installed in this environment. Generated pages were not hand-edited. `docs/BANKING_SYSTEM.md` was updated directly, including correction of its older claim that registered household repayment happens after wages; the actual phase remains before household settlement.

[Fable’s W06–W18 proposal](reviews/ECONOMIC_DESIGN_FABLE_PROPOSALS.md) is complete and preserved. The [coordinator audit](reviews/ECONOMIC_DESIGN_COORDINATOR_AUDIT.md) identifies eleven required corrections/qualifications and a narrower next queue; it is the current disposition of that proposal, not authorization to implement all of it.
